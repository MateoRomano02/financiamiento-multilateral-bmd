"""Tests de CAF 2014-2022 desde la base heredada cruzada con el IATI.

Protegen el contrato de la decisión del 9/10: para 2014-2022 la base de operaciones de CAF es la
heredada, el IATI aporta atributos sin duplicar, y el total anual queda dentro de 3% del informe.
Los de cruce usan filas armadas a mano; los de totales leen las descargas reales.
"""

import pandas as pd
import pytest

from src.common import caf_heredada as ch
from src.common.esquema import COLUMNAS
from src.common.normalizar import CRUDO, _fecha_del_nombre, acumular_fotos, normalizar_iati


def _fila(**kw) -> dict:
    base = {c: None for c in COLUMNAS}
    base.update(banco_grupo="CAF", institucion="CAF", fuente_url="x", fecha_relevamiento="2026-10-09")
    base.update(kw)
    return base


def _heredada(*filas: dict) -> pd.DataFrame:
    return pd.DataFrame([_fila(origen_fila=ch.ORIGEN_HEREDADA, estado="desconocido", **f) for f in filas])[list(COLUMNAS)]


def _iati(*filas: dict) -> pd.DataFrame:
    return pd.DataFrame([_fila(**f) for f in filas])[list(COLUMNAS)]


def test_cruce_iati_con_heredada_aporta_atributos_y_no_duplica():
    h = _heredada(dict(id_proyecto="CAF-H-2016-aaaa", nombre="Programa Vial Norte", pais="Bolivia",
                       anio_aprobacion=2016, fecha_aprobacion="2016-01-01", monto_aprobado_usd=100e6,
                       tipo_prestatario="soberana", tipo_ventanilla="soberana"))
    i = _iati(dict(id_proyecto="XI-IATI-1", nombre="Programa vial del norte", pais="Bolivia",
                   anio_aprobacion=2017, fecha_aprobacion="2017-02-03", monto_aprobado_usd=101e6,
                   url_proyecto="https://caf/ficha", monto_desembolsado_usd=40e6, estado="cerrado",
                   prestatario="Ministerio de Obras", tipo_prestatario="empresa_publica"))
    pares = ch.cruzar(h, i)
    assert pares == [(0, 0)]
    fila = ch.enriquecer(h, i, pares).iloc[0]
    assert fila["origen_fila"] == ch.ORIGEN_HEREDADA_IATI
    assert fila["url_proyecto"] == "https://caf/ficha" and fila["monto_desembolsado_usd"] == 40e6
    assert fila["estado"] == "cerrado" and fila["prestatario"] == "Ministerio de Obras"
    # El monto y el año los manda la heredada: es la que suma al informe, aunque el IATI caiga en otro año.
    assert fila["monto_aprobado_usd"] == 100e6 and fila["anio_aprobacion"] == 2016
    assert fila["fecha_aprobacion"] == "2016-01-01"
    assert fila["id_proyecto"] == "CAF-H-2016-aaaa" and "XI-IATI-1" in fila["fuente_url"]


@pytest.mark.parametrize("cambio", [dict(pais="Peru"), dict(anio_aprobacion=2019),
                                    dict(monto_aprobado_usd=110e6)])
def test_no_cruza_si_falla_pais_anio_o_monto(cambio):
    h = _heredada(dict(id_proyecto="h", nombre="A", pais="Bolivia", anio_aprobacion=2016, monto_aprobado_usd=100e6))
    datos = dict(id_proyecto="i", nombre="A", pais="Bolivia", anio_aprobacion=2016, monto_aprobado_usd=100e6)
    assert ch.cruzar(h, _iati({**datos, **cambio})) == []


def test_cruce_es_uno_a_uno_y_prefiere_el_mismo_nombre():
    h = _heredada(
        dict(id_proyecto="h1", nombre="Linea de credito Banco Uno", pais="Chile", anio_aprobacion=2018, monto_aprobado_usd=50e6),
        dict(id_proyecto="h2", nombre="Acueducto Sur", pais="Chile", anio_aprobacion=2018, monto_aprobado_usd=50e6))
    i = _iati(dict(id_proyecto="i1", nombre="Acueducto Sur", pais="Chile", anio_aprobacion=2018, monto_aprobado_usd=50e6))
    assert ch.cruzar(h, i) == [(1, 0)]


def test_solo_se_quita_la_fila_identica_en_todas_las_columnas(tmp_path):
    cols = ["Nombre del proyecto", "País", "Prestatario", "Fecha de aprobación", "Monto Financiado",
            "Sector", "Tipo de inversión/financiamiento", "Tipo de Préstamo", "Breve Descripción"]
    linea = ["Línea revolvente", "Brasil", "Banco A", 2016, 200e6, "Finanzas", "Línea de Crédito", "No soberano", "d"]
    otro_banco = [*linea[:2], "Banco B", *linea[3:]]
    ruta = tmp_path / "h.xlsx"
    pd.DataFrame([linea, linea, otro_banco], columns=cols).to_excel(ruta, index=False)
    df = ch.leer_heredada(ruta)
    assert len(df) == 2 and df["id_proyecto"].is_unique
    assert set(df["pais"]) == {"Brazil"} and set(df["origen_fila"]) == {ch.ORIGEN_HEREDADA}
    assert df["id_proyecto"].str.startswith("CAF-H-2016-").all()
    assert set(df["tipo_ventanilla"]) == {"no_soberana"} and set(df["forma_financiamiento"]) == {"prestamo"}


# --- Contra las descargas reales ---------------------------------------------------------------

@pytest.fixture(scope="module")
def caf():
    archivos = sorted(CRUDO.glob("caf/caf_actividades_*.xml"))
    if not archivos or not ch.RUTA_HEREDADA.exists() or not ch.RUTA_INFORMES:
        pytest.skip("faltan las descargas o la base heredada")
    fotos = [normalizar_iati(r, _fecha_del_nombre(r), institucion="CAF") for r in archivos]
    return ch.construir_caf(acumular_fotos(fotos))


def test_total_anual_2014_2022_dentro_de_3_por_ciento_del_informe(caf):
    informe = pd.read_csv(ch.RUTA_INFORMES[-1]).set_index("anio")["total_aprobado_musd"]
    totales = caf.groupby("anio_aprobacion")["monto_aprobado_usd"].sum() / 1e6
    for anio in range(2014, 2023):
        razon = totales[anio] / informe[anio]
        # Sin pasarse: la IATI sin cruce nunca lleva el año por encima del informe.
        assert 0.97 <= razon <= 1.0 + 0.003, f"{anio}: {razon:.3f}"


def test_id_proyecto_unico_y_origen_declarado(caf):
    assert caf["id_proyecto"].is_unique
    assert caf["origen_fila"].isin([ch.ORIGEN_IATI, ch.ORIGEN_HEREDADA, ch.ORIGEN_HEREDADA_IATI]).all()
    assert caf[caf["origen_fila"] != ch.ORIGEN_IATI]["anio_aprobacion"].between(2014, 2022).all()
    assert caf.loc[caf["origen_fila"] != ch.ORIGEN_IATI, "monto_aprobado_usd"].notna().all()


def test_cada_operacion_iati_aparece_una_sola_vez(caf):
    # Una IATI cruzada lleva su identificador en la fuente de la fila heredada; no puede estar además como fila propia.
    propias = set(caf.loc[caf["origen_fila"] == ch.ORIGEN_IATI, "id_proyecto"])
    for url in caf.loc[caf["origen_fila"] == ch.ORIGEN_HEREDADA_IATI, "fuente_url"]:
        assert url.split("atributos del IATI ")[1] not in propias


def test_2023_en_adelante_sigue_siendo_solo_iati(caf):
    assert set(caf.loc[caf["anio_aprobacion"] >= 2023, "origen_fila"]) == {ch.ORIGEN_IATI}
