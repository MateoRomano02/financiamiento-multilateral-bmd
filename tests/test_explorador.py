"""Contrato del generador del explorador: la tabla de países del mapa y la página resultante."""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import explorador_corpus as ex

from src.common.colores import COLORES_GRUPO


def test_cada_pais_tiene_iso3_codigo_numerico_y_zona_validos():
    assert len(ex.GEO) > 150
    for iso, g in ex.GEO.items():
        assert re.fullmatch(r"[A-Z]{3}", iso)
        assert g["z"] in ex.ZONAS
        # Kosovo no tiene código numérico y se une por nombre.
        assert re.fullmatch(r"\d{3}", g["n"]) or iso == "XKX"
    numeros = [g["n"] for iso, g in ex.GEO.items() if iso != "XKX"]
    assert len(numeros) == len(set(numeros))


def test_variantes_de_nombre_van_al_mismo_pais_y_los_agregados_a_ninguno():
    assert ex.iso_de("Türkiye") == ex.iso_de("Turkiye") == "TUR"
    assert ex.iso_de("Egypt") == ex.iso_de("Egypt, Arab Republic of") == "EGY"
    assert ex.iso_de("Brazil") == "BRA"
    for agregado in ["Regional", "World Region", "Pacific 1", "Caribbean", "DRC - Angola", None, ""]:
        assert ex.iso_de(agregado) is None


def test_la_pagina_solo_carga_scripts_de_cdns_permitidos():
    urls = re.findall(r'<script src="([^"]+)"', ex.PAGINA)
    assert urls
    assert all(u.startswith(("https://cdn.jsdelivr.net/npm/", "https://cdnjs.cloudflare.com/")) for u in urls)
    assert chr(0x2014) not in ex.PAGINA


def test_el_globo_se_baja_solo_al_elegir_la_vista_y_con_hash_de_integridad():
    assert "globe.gl" not in "".join(re.findall(r'<script src="([^"]+)"', ex.PAGINA))
    assert re.search(r"const U_GLOBE=\['https://[^']+globe\.gl[^']+','sha384-[^']+'\]", ex.PAGINA)
    assert "s.integrity=sri" in ex.PAGINA and "s.crossOrigin='anonymous'" in ex.PAGINA
    assert ex.PAGINA.count("cargarScript(U_GLOBE)") == 1
    assert "if(!GL.cargando&&!GL.fallo)montarGlobo()" in ex.PAGINA


def test_un_clic_en_un_pais_del_globo_lo_usa_como_filtro_y_esc_lo_saca():
    assert re.search(r"onPolygonClick\(f=>\{[^}]*filtro\('f-iso'", ex.PAGINA)
    assert "e.key==='Escape'" in ex.PAGINA


def test_no_queda_rastro_del_tablero_creativo_en_la_pagina():
    assert "creativo" not in ex.PAGINA.lower()
    assert not hasattr(ex, "ENLACE_CREATIVO") and not hasattr(ex, "MOSTRAR_ENLACE_CREATIVO")


def test_las_pestanas_son_resumen_mapa_composicion_y_membrecia_y_el_globo_es_una_vista_del_mapa():
    tabs = re.search(r"const TABS=\[(.+?)\];", ex.PAGINA).group(1)
    assert re.findall(r"\['(\w+)','([^']+)'\]", tabs) == [
        ("resumen", "Resumen"), ("mapa", "Mapa"), ("comp", "Composición"), ("membre", "Membrecía y concentración"),
        ("sobre", "Sobre el proyecto")]
    for k in ["resumen", "mapa", "comp", "membre", "sobre"]:
        assert f'<section id="p-{k}"' in ex.PAGINA
    assert 'id="p-globo"' not in ex.PAGINA
    botones = re.findall(r'<button type="button" data-v="(\w+)"[^>]*>([^<]+)</button>', _seccion("p-mapa"))
    assert botones == [("plano", "Plano"), ("globo", "Globo")]
    # Los controles de año son uno solo para las dos vistas.
    assert _seccion("p-mapa").count('type="range"') == 1


def _node(js: str) -> str:
    """Corre un trozo de la página en node; las funciones se extraen de PAGINA, no se copian."""
    node = shutil.which("node")
    if not node:
        pytest.skip("falta node")
    return subprocess.run([node, "-e", js], capture_output=True, text=True, check=True).stdout.strip()


def _trozo(desde: str, hasta: str) -> str:
    return re.search(rf"{re.escape(desde)}.*?(?={re.escape(hasta)})", ex.PAGINA, re.DOTALL).group(0)


def test_un_link_viejo_con_tab_globo_abre_el_mapa_en_vista_globo():
    tabs = re.search(r"const TABS=\[.+?\];", ex.PAGINA).group(0)
    js = tabs + _trozo("function estadoDeHash", "function aplicarHash") + """
    const r=h=>JSON.stringify(estadoDeHash(new URLSearchParams(h)));
    console.log([r('tab=globo'),r('tab=mapa&vista=globo'),r('tab=mapa'),r('tab=nada&vista=globo')].join('|'))"""
    assert _node(js) == ('{"tab":"mapa","vista":"globo"}|{"tab":"mapa","vista":"globo"}|'
                         '{"tab":"mapa","vista":"plano"}|{"tab":"resumen","vista":"globo"}')


def test_la_pestana_va_en_el_hash_solo_si_no_es_el_resumen():
    assert re.search(r"if\(TAB==='resumen'\)q\.delete\('tab'\);else q\.set\('tab',TAB\)", ex.PAGINA)
    assert "q.get('tab')" in ex.PAGINA


def _seccion(id_: str) -> str:
    return re.search(rf'<section id="{id_}"[^>]*>(.*?)</section>', ex.PAGINA, re.DOTALL).group(1)


def test_el_resumen_conserva_el_orden_de_siempre():
    titulos = [re.sub(r"<[^>]+>|\s+", " ", t).strip() for t in re.findall(r"<h2>(.*?)</h2>", _seccion("p-resumen"), re.DOTALL)]
    assert titulos == [
        "Monto aprobado por año y grupo bancario", "Por forma del financiamiento", "Comparación entre bancos",
        "Ventanilla no soberana, por banco", "Fuentes y fecha de descarga",
        "Diez principales países", "Diez principales sectores", "Operaciones"]
    antes = ex.PAGINA[: ex.PAGINA.index('<section id="p-resumen"')]
    orden = [antes.index(x) for x in ['id="guia"', 'id="tableros"', 'id="ficha"', 'id="barra"', 'class="kpis"']]
    assert orden == sorted(orden)


def _ids_fb() -> dict[str, str]:
    html = ex.PAGINA[: ex.PAGINA.index("<script>")]
    return dict(re.findall(r'data-fb="([^"]+)" data-fb-label="([^"]+)"', html))


def test_las_tablas_de_referencia_van_plegadas_y_las_advertencias_se_dicen_una_vez():
    for titulo in ["CAF según sus informes anuales", "Ventanilla no soberana, por banco", "Fuentes y fecha de descarga"]:
        assert re.search(rf'<details class="ref"><summary><h2>{titulo}</h2><span class="ver">Ver tabla</span></summary>', ex.PAGINA)
    assert 'class="ref" open' not in ex.PAGINA
    textos = ex.PAGINA + " ".join(ex.FICHAS.values())
    assert textos.count("cartera privada del BID") == 1
    assert textos.count("No cambia con los filtros") == 1
    assert textos.count("un cuarto de lo") == 1


def test_los_comentarios_van_por_elemento_y_el_resumen_ya_no_tiene_la_seccion_del_equipo():
    assert "Comentarios del equipo" not in ex.PAGINA
    for viejo in ["c-seccion", "c-texto", "c-enviar", "c-lista"]:
        assert f'id="{viejo}"' not in ex.PAGINA
    assert '<button type="button" id="fb-btn"' in ex.PAGINA and ">Feedback</button>" in ex.PAGINA
    assert "Elegí un elemento para comentar · Esc para salir" in ex.PAGINA
    assert "prompt(" not in ex.PAGINA and "prompt(" not in ex.CARGADOR


def test_cada_elemento_comentable_tiene_un_id_unico_y_una_etiqueta_que_entra_en_seccion():
    html = ex.PAGINA[: ex.PAGINA.index("<script>")]
    ids = re.findall(r'data-fb="([^"]+)"', html)
    assert len(ids) == len(set(ids)) > 30
    assert len(re.findall(r"data-fb-label=", html)) == len(ids)
    # seccion lleva la etiqueta y las reglas la limitan a 60 caracteres.
    assert all(len(i) <= 60 for i in ids) and all(len(e) <= 60 for e in _ids_fb().values())
    # Solo en el HTML estático: una plantilla de JS repetiría ids.
    assert not re.search(r'data-fb="[a-z]', ex.PAGINA[ex.PAGINA.index("<script>"):])
    for esperado in ["kpi-ops", "filtro-grupo", "mapa-monto-pais", "mapa-vista", "resumen-operaciones", "membre-grafico"]:
        assert esperado in ids


def test_las_secciones_viejas_se_llevan_a_un_elemento_que_existe_o_a_general():
    viejas = dict(re.findall(r"'([^']+)':'([^']+)'", re.search(r"const SECCION_VIEJA=\{(.+?)\};", ex.PAGINA).group(1)))
    assert set(viejas) == {"General", "Explorador", "Mapa", "Comparación entre bancos", "Ventanillas",
                           "Países y sectores", "Algo que me gustaría ver"}
    assert all(v == "general" or v in _ids_fb() for v in viejas.values())


def test_el_estado_de_la_vista_que_se_guarda_no_lleva_la_clave_del_link():
    js = _trozo("function vistaSinClave", "function estadoVistaActual") + """
    console.log(vistaSinClave('#k=SECRETA&tab=mapa&vista=globo&g=CAF'));
    console.log(vistaSinClave('tab=mapa&k=SECRETA'));
    console.log(vistaSinClave('#' + 'x=1&'.repeat(600)).length)"""
    salida = _node(js).splitlines()
    assert salida[0] == "tab=mapa&vista=globo&g=CAF" and salida[1] == "tab=mapa"
    assert int(salida[2]) <= 1000 and "SECRETA" not in "".join(salida)


def test_la_composicion_lleva_las_miniaturas_no_soberanas():
    assert 'id="e-mini"' in _seccion("p-comp")


def test_los_hitos_estan_en_los_graficos_de_tiempo_y_en_los_controles_de_ano():
    hitos = re.search(r"const HITOS=\[(.+?)\];", ex.PAGINA, re.DOTALL).group(1)
    assert re.findall(r"a:(\d+),c:'([^']+)'", hitos) == [("2015", "París"), ("2016", "AIIB y NDB"), ("2020", "COVID-19")]
    assert ex.PAGINA.count("hitosSvg(") >= 3 and ex.PAGINA.count("hitosSlider(") >= 2
    for id_ in ["m-hitos", "mb-hitos"]:
        assert f'id="{id_}"' in ex.PAGINA


def _pasos_del_recorrido() -> str:
    return re.search(r"const PASOS=\[.*?(?=const INSTITUCIONES)", ex.PAGINA, re.DOTALL).group(0)


def test_el_recorrido_resalta_elementos_que_existen_y_nombra_los_sectores_en_la_pagina():
    pasos = _pasos_del_recorrido()
    filtros = re.findall(r"'(filtro-\w+)'", re.search(r"const FILTROS_FB=\[(.+?)\]", ex.PAGINA).group(1))
    usados = set(filtros)
    for lista in re.findall(r"fb:\[([^\]]*)\]", pasos):
        usados |= set(re.findall(r"'([\w-]+)'", lista))
    assert len(usados) > 15
    assert usados <= set(_ids_fb()), usados - set(_ids_fb())
    assert 'id="fb-btn"' in ex.PAGINA and "sel:'#fb-btn'" in pasos
    assert re.findall(r"tab:'(\w+)'", pasos) and set(re.findall(r"tab:'(\w+)'", pasos)) <= {"resumen", "mapa", "comp", "membre"}


def test_el_texto_del_recorrido_no_trae_cifras_escritas_a_mano():
    # Los números salen de ${...} calculado con los datos cargados; el resto del texto no lleva ningún dígito.
    texto = re.sub(r"\$\{[^}]*\}", "", _pasos_del_recorrido())
    texto = re.sub(r"(?:fb|tab|sel):(?:\[[^\]]*\]|'[^']*')", "", texto)
    assert not re.search(r"\d", texto), re.search(r".{30}\d.{30}", texto).group(0)


def test_los_eventos_de_visita_que_manda_la_pagina_son_los_esperados():
    eventos = set(re.findall(r"tourVisita\('(\w+)'", ex.PAGINA)) | set(re.findall(r"'(recorrido_\w+)'", ex.PAGINA))
    assert eventos == {"inicio", "recorrido_completo", "recorrido_salteado"}
    # El nombre del recorrido y el de los comentarios son el mismo campo guardado.
    assert ex.PAGINA.count("'explorador-nombre'") == 2


def test_el_recorrido_arranca_solo_la_primera_vez_y_se_puede_repetir():
    assert "localStorage.getItem('explorador-recorrido')!==TOUR_VERSION)setTimeout(tourIniciar" in ex.PAGINA
    assert re.search(r'<button type="button" id="b-recorrido"[^>]*>Recorrido</button>', ex.PAGINA)


def test_los_colores_de_grupo_del_explorador_salen_de_colores_py():
    assert set(ex.ORDEN_GRUPOS) == set(COLORES_GRUPO)
    for k, g in enumerate(ex.ORDEN_GRUPOS):
        assert f"--g{k + 1}:{COLORES_GRUPO[g]};" in ex.CSS_COLORES_GRUPO
    assert "const GR=__GRUPOS__;" in ex.PAGINA and "'GBM','GBID'" not in ex.PAGINA


def test_los_grupos_se_listan_en_un_solo_orden():
    assert ex.ORDEN_GRUPOS == ("GBM", "GBID", "CAF", "BCIE", "FONPLATA", "AIIB", "NDB")
    assert "enOrden(unicos('banco_grupo'))" in ex.PAGINA


def _csv_membrecia(tmp_path, monkeypatch, filas):
    (tmp_path / "membrecia_2026-01-01.csv").write_text(
        "institucion,pais,fecha_ingreso,tipo,fuente_url\n" + "\n".join(filas) + "\n", encoding="utf-8")
    monkeypatch.setattr(ex, "MEMBRECIA", tmp_path)


def test_membrecia_al_31_de_diciembre_con_fecha_vacia_solo_anio_y_prospectivos(tmp_path, monkeypatch):
    _csv_membrecia(tmp_path, monkeypatch, [
        "X,A,,pleno,u", "X,B,2015-12-31,pleno,u", "X,C,2016,pleno,u", "X,D,2016-06-30,pleno,u", "X,E,,prospectivo,u"])
    assert ex.membrecia_por_anio([2014, 2015, 2016, 2017])["X"] == {"2014": 1, "2015": 2, "2016": 4, "2017": 4}


def test_membrecia_sin_la_tabla_devuelve_vacio(tmp_path, monkeypatch):
    monkeypatch.setattr(ex, "MEMBRECIA", tmp_path)
    assert ex.membrecia_por_anio([2014]) == {}


@pytest.mark.skipif(not list(ex.MEMBRECIA.glob("membrecia_*.csv")), reason="falta la tabla de membrecía")
def test_membrecia_real_coincide_con_la_verificacion():
    m = ex.membrecia_por_anio(list(range(2014, 2026)))
    assert (m["AIIB"]["2014"], m["AIIB"]["2025"]) == (0, 106)
    assert (m["NDB"]["2014"], m["NDB"]["2025"]) == (0, 9)
    assert (m["BID"]["2014"], m["BID Invest"]["2014"], m["BID Invest"]["2025"]) == (48, 45, 48)


def test_filtros_compartibles_conservan_las_claves_viejas_y_suman_pais_y_zona():
    claves = re.search(r"const S=\{([^}]+)\}", ex.PAGINA).group(1)
    for k in ["g:", "i:", "v:", "d:", "h:", "p:", "t:", "f:", "usd:", "c:", "r:"]:
        assert k in claves


def test_la_pagina_es_solo_clara():
    assert "prefers-color-scheme" not in ex.PAGINA
    assert "color-scheme:light" in ex.PAGINA


@pytest.mark.skipif(not ex.CORPUS.exists(), reason="falta el corpus procesado")
def test_todo_nombre_del_corpus_mapea_o_es_un_agregado():
    import analisis_preliminar as ap

    df = ap.cargar()
    sin = {p for p in df["pais"].dropna().unique() if ex.iso_de(p) is None}
    # Un país real sin mapear dejaría plata fuera del mapa sin avisar.
    reales = {p for p in sin if ap.es_pais_real(p) and p not in AGREGADOS_SIN_PALABRA_CLAVE}
    assert not reales, reales


# Agregados que el informe no detecta por palabra clave (es_pais_real los toma por país) y que el
# mapa deja correctamente fuera.
AGREGADOS_SIN_PALABRA_CLAVE = {
    "Western and Central Africa", "Eastern and Southern Africa", "Regional Development Bank",
    "Southern Africa", "Central Asia", "Central Asia and Turkiye Region", "Caribbean",
    "Country Name Pending", "Central Africa", "Western Balkans", "Pacific 1", "Pacific 2", "Africa",
    "DRC - Angola", "OECS Countries", "Unknown", "Horn of Africa", "Europe and Central Asia",
    "Southwest Indian Ocean", "East Asia and Pacific", "South Asia", "Middle East and North Africa",
    "Pacific Islands", "Cen Afr, and Anglophne W Africa Region", "Southern Europe Subregion",
    "Eastern Europe Subregion", "Central Europe Subregion", "Central America Subregion",
    "Southeast Asia Subregion", "Caribbean Subregion",
}
