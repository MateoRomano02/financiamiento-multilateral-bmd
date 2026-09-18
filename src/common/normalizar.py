"""Normalización de cada fuente al esquema común.

Cada institución publica en su propio formato, con su propio catálogo de estados, su propia
unidad de análisis y sus propias unidades de monto. Este módulo traduce todo eso a las columnas
de `esquema.py`, dejando por escrito cada decisión de criterio.

Tres cosas que conviene entender antes de leer el código, porque son las que más condicionan el
resultado y ninguna es obvia:

**Las unidades de monto no son las mismas.** La IFC publica en millones de dólares, el AIIB en
texto libre del tipo "USD100 million", y el resto en unidades. Sumar sin convertir da un número
que parece plausible y está mal por seis órdenes de magnitud en las filas de la IFC.

**La fila no siempre es la operación.** BID Invest publica una fila por idioma, así que sus 4.757
filas son 2.084 operaciones. MIGA publica una fila por garantía emitida y un proyecto puede tener
varias, incluso en el mismo año. La IFC publica a nivel documento, aunque en la práctica casi
todas sus operaciones traen un solo documento.

**BIRF e IDA comparten descarga pero son dos ventanillas.** Se separan por el monto comprometido
de cada una. Una operación que tiene compromiso de las dos genera dos filas, una por ventanilla,
porque es la única forma de que los totales por institución cierren.

Las canceladas se normalizan y se marcan, no se descartan acá: el criterio acordado de excluirlas
se aplica en el análisis, para que el corpus conserve la traza de lo que la fuente publicaba.
"""

from __future__ import annotations

import csv
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import pandas as pd

from .esquema import COLUMNAS, VENTANILLA_POR_INSTITUCION
from .tipo_de_cambio import a_dolares, normalizar_moneda

RAIZ = Path(__file__).resolve().parent.parent.parent
CRUDO = RAIZ / "data" / "raw"


# ---------------------------------------------------------------------------
# Utilidades de conversión
# ---------------------------------------------------------------------------

FORMATOS_FECHA = ("%Y-%m-%d", "%d-%b-%Y", "%d %B %Y", "%Y")


def a_fecha(valor: object) -> str | None:
    """Devuelve la fecha en ISO, o None si no se puede interpretar.

    Las fuentes usan cuatro formatos distintos: ISO con o sin hora, el `13-Jul-2000` de los
    portales del Banco Mundial, el `24 August 2026` del listado del NDB, y el año suelto del
    AIIB. Un valor que no encaje en ninguno devuelve None en lugar de romper, porque varias
    fuentes usan guiones o cadenas vacías para decir que no hay dato.
    """
    if valor is None:
        return None
    texto = str(valor).strip()
    if not texto or texto in {"-", "NULL", "None", "TBD"}:
        return None
    texto = texto.split("T")[0].strip()
    for formato in FORMATOS_FECHA:
        try:
            fecha = datetime.strptime(texto, formato)
            # El AIIB publica solo el año: se ancla al 1 de enero y se documenta la imprecisión.
            return fecha.date().isoformat()
        except ValueError:
            continue
    return None


def a_numero(valor: object, factor: float = 1.0) -> float | None:
    """Convierte a float aplicando un factor de unidad. None si no es un número."""
    if valor is None:
        return None
    texto = str(valor).strip().replace(",", "")
    if not texto or texto in {"-", "NULL", "None", "TBD"}:
        return None
    try:
        return float(texto) * factor
    except ValueError:
        return None


# CAF publica el receptor como codigo ISO de dos letras, mientras el resto del corpus usa el
# nombre del pais. Sin traducir, CAF queda fuera de cualquier agregacion por pais. Son los 18
# codigos que aparecen en su archivo; uno nuevo se veria como codigo crudo y hay que sumarlo aca.
PAISES_ISO2 = {
    "AR": "Argentina", "BB": "Barbados", "BO": "Bolivia", "BR": "Brazil", "CL": "Chile",
    "CO": "Colombia", "CR": "Costa Rica", "DO": "Dominican Republic", "EC": "Ecuador",
    "ES": "Spain", "MX": "Mexico", "PA": "Panama", "PE": "Peru", "PY": "Paraguay",
    "SV": "El Salvador", "TT": "Trinidad and Tobago", "UY": "Uruguay", "VE": "Venezuela",
}


def nombre_de_pais(codigo: object) -> str | None:
    """Traduce el codigo ISO2 de CAF al nombre que usa el resto del corpus."""
    if codigo is None:
        return None
    partes = [PAISES_ISO2.get(c.strip(), c.strip()) for c in str(codigo).split(";") if c.strip()]
    return ";".join(partes) or None


RE_MONTO_TEXTO = re.compile(r"(?P<moneda>[A-Z]{3})\s*(?P<valor>[\d.,]+)\s*(?P<escala>million|billion)?", re.I)


def monto_desde_texto(valor: object) -> tuple[float | None, str | None]:
    """Interpreta los montos en texto del AIIB, del tipo 'USD100 million'.

    Devuelve (monto en unidades, moneda). El AIIB usa cinco variantes de la misma cadena, con y
    sin espacio y con 'million' en mayúscula o minúscula, así que el patrón las cubre a todas.
    """
    if valor is None:
        return None, None
    m = RE_MONTO_TEXTO.search(str(valor).strip())
    if not m:
        return None, None
    numero = a_numero(m.group("valor"))
    if numero is None:
        return None, None
    escala = (m.group("escala") or "").lower()
    factor = 1e9 if escala == "billion" else 1e6 if escala == "million" else 1.0
    return numero * factor, m.group("moneda").upper()


# ---------------------------------------------------------------------------
# Catálogos de estado. El valor original se preserva siempre en estado_original.
# ---------------------------------------------------------------------------

ESTADOS_POR_FUENTE: dict[str, dict[str, str]] = {
    # `status` del servicio del Banco Mundial. "Dropped" es un proyecto que no llegó a
    # aprobarse, que es lo que el criterio acordado trata como cancelado.
    "gbm": {
        "Closed": "cerrado",
        "Active": "en_implementacion",
        "Pipeline": "propuesto",
        "Dropped": "cancelado",
    },
    "ifc": {
        "Completed": "cerrado",
        "Active": "en_implementacion",
        "Pending Disbursement": "aprobado",
        "Pending Signing": "aprobado",
        "Pending Approval": "propuesto",
        # "Hold" no dice si la operación sigue viva: no se fuerza a ninguna categoría.
        "Hold": "desconocido",
    },
    "bid": {
        "Closed": "cerrado",
        "Implementation": "en_implementacion",
        "Cancelled": "cancelado",
        "Preparation": "propuesto",
    },
    "bid_invest": {
        "Repaid": "cerrado",
        "Closed": "cerrado",
        "In implementation": "en_implementacion",
        "Approved": "aprobado",
        "Proposed": "propuesto",
        # "Inactive" y "Hold" son ambiguos en la fuente: podrían ser cerrados o cancelados.
        "Inactive": "desconocido",
        "Hold": "desconocido",
    },
    # Códigos del estándar IATI: 2 es implementación, 4 es cerrado.
    "caf": {"1": "propuesto", "2": "en_implementacion", "3": "en_implementacion", "4": "cerrado",
            "5": "cancelado", "6": "desconocido"},
    "aiib": {
        "Approved": "aprobado",
        "Proposed": "propuesto",
        "Terminated / Cancelled": "cancelado",
        "On Hold": "desconocido",
    },
}


def mapear_estado(catalogo: str, valor: object) -> str:
    return ESTADOS_POR_FUENTE.get(catalogo, {}).get(str(valor).strip(), "desconocido")


def _fila_base(institucion: str, grupo: str, fuente_url: str, relevamiento: str) -> dict:
    return {
        "banco_grupo": grupo,
        "institucion": institucion,
        "tipo_ventanilla": VENTANILLA_POR_INSTITUCION.get(institucion),
        "fuente_url": fuente_url,
        "fecha_relevamiento": relevamiento,
        "clasificacion_te": None,
        "categoria_te": None,
        "monto_original": None,
        "moneda_original": None,
        "monto_desembolsado_usd": None,
    }


def _cerrar(filas: list[dict]) -> pd.DataFrame:
    """Completa las columnas faltantes y deriva el año, para que toda salida tenga la misma forma."""
    df = pd.DataFrame(filas)
    for col in COLUMNAS:
        if col not in df.columns:
            df[col] = None
    df["anio_aprobacion"] = pd.to_datetime(df["fecha_aprobacion"], errors="coerce").dt.year
    return df[list(COLUMNAS)]


# ---------------------------------------------------------------------------
# Un normalizador por institución
# ---------------------------------------------------------------------------


def normalizar_gbm(ruta: Path, relevamiento: str) -> pd.DataFrame:
    """BIRF e IDA, que comparten descarga y se separan por el compromiso de cada ventanilla.

    Una operación con compromiso de las dos genera dos filas. Es la única forma de que el total
    por institución cierre contra lo que el propio Banco Mundial reporta por ventanilla, y de que
    no haya que elegir arbitrariamente a cuál asignarla.
    """
    datos = json.loads(ruta.read_text(encoding="utf-8"))["projects"]
    registros = list(datos.values()) if isinstance(datos, dict) else datos
    url = "https://search.worldbank.org/api/v3/projects"
    filas = []
    for r in registros:
        comunes = {
            "id_proyecto": r.get("id"),
            "nombre": r.get("project_name"),
            "pais": r.get("countryshortname"),
            "url_proyecto": f"https://projects.worldbank.org/en/projects-operations/project-detail/{r.get('id')}",
            "fecha_aprobacion": a_fecha(r.get("boardapprovaldate")),
            "estado": mapear_estado("gbm", r.get("status")),
            "estado_original": r.get("status"),
            # El servicio no expone el instrumento de préstamo en ninguna forma (verificado
            # contra el catálogo completo de campos el 15/09/2026).
            "instrumento": None,
            "sector": (r.get("mjsector") or "").split(",")[0].strip() or None,
        }
        for institucion, campo in (("BIRF", "curr_ibrd_commitment"), ("IDA", "idacommamt")):
            monto = a_numero(r.get(campo))
            if not monto:
                continue
            filas.append(
                {**_fila_base(institucion, "GBM", url, relevamiento), **comunes,
                 "id_proyecto": f"{r.get('id')}", "monto_aprobado_usd": monto}
            )
    return _cerrar(filas)


def normalizar_ifc(ruta: Path, relevamiento: str) -> pd.DataFrame:
    """IFC. Sus montos vienen en millones y su fila es el documento, no la operación."""
    registros = json.loads(ruta.read_text(encoding="utf-8"))["data"]
    url = "https://datacatalogapi.worldbank.org/dexapps/fone/api/apiservice?datasetId=DS00499"
    vistos: set[str] = set()
    filas = []
    for r in registros:
        pid = str(r.get("project_number") or "").strip()
        # Solo 17 operaciones traen más de un documento, y en las 17 el monto y la fecha
        # coinciden entre filas, así que quedarse con la primera no pierde información.
        if not pid or pid in vistos:
            continue
        vistos.add(pid)
        filas.append(
            {**_fila_base("IFC", "GBM", url, relevamiento),
             "id_proyecto": pid,
             "nombre": r.get("project_name"),
             "pais": r.get("country"),
             "url_proyecto": r.get("project_url"),
             "fecha_aprobacion": a_fecha(r.get("ifc_approval_date")),
             "estado": mapear_estado("ifc", r.get("status")),
             "estado_original": r.get("status"),
             "monto_aprobado_usd": a_numero(
                 r.get("total_ifc_investment_as_approved_by_boardmillion__usd"), 1e6),
             "instrumento": r.get("product_line"),
             "sector": r.get("industry")}
        )
    return _cerrar(filas)


def normalizar_miga(ruta: Path, relevamiento: str) -> pd.DataFrame:
    """MIGA. Emite garantías, no préstamos, y publica una fila por garantía emitida.

    Un mismo proyecto puede tener varias garantías, incluso en el mismo año fiscal, así que el
    identificador de proyecto no alcanza como clave: se compone con el año y un correlativo.
    """
    registros = json.loads(ruta.read_text(encoding="utf-8"))["data"]
    url = "https://datacatalogapi.worldbank.org/dexapps/fone/api/apiservice?datasetId=DS00988"
    contador: dict[tuple, int] = {}
    filas = []
    for r in registros:
        clave = (str(r.get("project_id")), str(r.get("issued_fy")))
        contador[clave] = contador.get(clave, 0) + 1
        filas.append(
            {**_fila_base("MIGA", "GBM", url, relevamiento),
             "id_proyecto": f"{clave[0]}-{clave[1]}-{contador[clave]}",
             "nombre": r.get("project_name"),
             "pais": r.get("host_country"),
             "url_proyecto": r.get("project_links"),
             "fecha_aprobacion": a_fecha(r.get("project_start_date")),
             # MIGA no publica estado en ninguna forma.
             "estado": "desconocido",
             "estado_original": None,
             "monto_aprobado_usd": a_numero(r.get("gross_issued_amount")),
             "instrumento": r.get("product_line"),
             "sector": r.get("business_sector")}
        )
    return _cerrar(filas)


def normalizar_bid(ruta: Path, relevamiento: str) -> pd.DataFrame:
    """BID y BID Lab, que comparten archivo y se separan por código de instrumento.

    BID Lab no tiene fuente propia: son las operaciones con instrumento MIF, herencia del
    Fondo Multilateral de Inversiones. El criterio reproduce exactamente la clasificación que
    el relevamiento anterior había hecho a mano.
    """
    with ruta.open(encoding="utf-8-sig") as f:
        registros = list(csv.DictReader(f))
    url = "https://data.iadb.org/dataset/idb-projects-dataset"
    filas = []
    for r in registros:
        es_lab = (r.get("lending_instrmnt_cd") or "").strip() == "MIF"
        institucion = "BID Lab" if es_lab else "BID"
        filas.append(
            {**_fila_base(institucion, "GBID", url, relevamiento),
             "id_proyecto": (r.get("oper_num") or "").strip(),
             "nombre": r.get("oper_nm"),
             "pais": r.get("cntry_nm"),
             "fecha_aprobacion": a_fecha(r.get("apprvl_dt")),
             "estado": mapear_estado("bid", r.get("publc_sts_nm")),
             "estado_original": r.get("publc_sts_nm"),
             "monto_aprobado_usd": a_numero(r.get("orig_apprvd_useq_amnt")),
             "instrumento": r.get("opertyp_nm"),
             "sector": (r.get("sector_nm") or "").strip() or None}
        )
    return _cerrar(filas)


def normalizar_bid_invest(ruta: Path, relevamiento: str) -> pd.DataFrame:
    """BID Invest. Publica una fila por idioma, así que hay que quedarse con uno solo."""
    raiz = ET.parse(ruta).getroot()
    registros = [{h.tag: (h.text or "").strip() for h in item} for item in raiz]
    url = "https://idbinvest.org/en/projects"
    vistos: set[str] = set()
    filas = []
    for r in registros:
        # El mismo proyecto se publica en inglés, español y portugués. Quedarse con el inglés
        # deja 2.084 operaciones de las 4.757 filas. Las 245 que aún se repiten dentro del
        # inglés difieren solo en la fecha de directorio, así que se toma la primera.
        if r.get("Language") != "English":
            continue
        pid = (r.get("project_number") or "").strip()
        if not pid or pid in vistos:
            continue
        vistos.add(pid)
        filas.append(
            {**_fila_base("BID Invest", "GBID", url, relevamiento),
             "id_proyecto": pid,
             "nombre": r.get("project_name"),
             "pais": r.get("country"),
             "url_proyecto": r.get("project_url"),
             "fecha_aprobacion": a_fecha(r.get("approval_date")),
             "estado": mapear_estado("bid_invest", r.get("status")),
             "estado_original": r.get("status"),
             "monto_aprobado_usd": a_numero(r.get("iic_financing_amount")),
             "monto_original": a_numero(r.get("iic_financing_amount")),
             "moneda_original": (r.get("currency") or "").strip() or None,
             "instrumento": (r.get("Investment_instrument") or "").replace("&amp;", "y") or None,
             "sector": (r.get("sector") or "").strip() or None}
        )
    return _cerrar(filas)


def normalizar_caf(ruta: Path, relevamiento: str) -> pd.DataFrame:
    """CAF, publicada en el estándar IATI.

    Es la única fuente del corpus con monto desembolsado explícito: la transacción de tipo 3.
    La de tipo 2 es el compromiso. Sus sectores usan un vocabulario propio, pero cada uno trae
    su nombre en texto, así que no hace falta una tabla de traducción.
    """
    raiz = ET.parse(ruta).getroot()
    url = "https://d-portal.org/ctrack.html?reporting_ref=XM-DAC-46008"
    filas = []
    for act in raiz:
        transacciones: dict[str, float] = {}
        for tx in act.findall("transaction"):
            nodo = tx.find("transaction-type")
            valor = tx.find("value")
            if nodo is not None and valor is not None:
                monto = a_numero(valor.text)
                if monto is not None:
                    transacciones[nodo.get("code", "")] = monto
        sector = act.find("sector")
        titulo = act.find("title")
        estado = act.find("activity-status")
        fecha = next((d.get("iso-date") for d in act.findall("activity-date")), None)
        paises = [p.get("code", "") for p in act.findall("recipient-country")]
        codigo = estado.get("code") if estado is not None else None
        filas.append(
            {**_fila_base("CAF", "CAF", url, relevamiento),
             "id_proyecto": (act.findtext("iati-identifier") or "").strip(),
             "nombre": "".join(titulo.itertext()).strip() if titulo is not None else None,
             "pais": nombre_de_pais(";".join(filter(None, paises))),
             "fecha_aprobacion": a_fecha(fecha),
             "estado": mapear_estado("caf", codigo),
             "estado_original": codigo,
             "monto_aprobado_usd": transacciones.get("2"),
             "monto_desembolsado_usd": transacciones.get("3"),
             "moneda_original": act.get("default-currency"),
             "sector": "".join(sector.itertext()).strip() if sector is not None else None}
        )
    return _cerrar(filas)


def normalizar_aiib(ruta: Path, relevamiento: str) -> pd.DataFrame:
    """AIIB. Declara la ventanilla fila por fila y publica el monto como texto.

    No tiene identificador de proyecto, así que se usa la ruta de su ficha pública, que es
    única y además sirve para auditar cada fila contra la fuente.
    """
    texto = ruta.read_text(encoding="utf-8", errors="replace")
    arreglo = re.sub(r",\s*]$", "]", texto[texto.index("[") : texto.rindex("]") + 1].strip())
    registros = json.loads(arreglo)
    url = "https://www.aiib.org/en/projects/list"
    filas = []
    for r in registros:
        monto, moneda = monto_desde_texto(r.get("approved_funding"))
        ventanilla = "soberana" if str(r.get("financing_type", "")).lower().startswith("sover") else "no_soberana"
        filas.append(
            {**_fila_base("AIIB", "AIIB", url, relevamiento),
             "tipo_ventanilla": ventanilla,
             "id_proyecto": (r.get("path") or "").strip(),
             "nombre": (r.get("name") or "").strip(),
             "pais": r.get("economy"),
             "url_proyecto": f"https://www.aiib.org{r.get('path', '')}",
             # El AIIB publica solo el año de aprobación, no la fecha.
             "fecha_aprobacion": a_fecha(r.get("date")),
             "estado": mapear_estado("aiib", r.get("status")),
             "estado_original": r.get("status"),
             "monto_aprobado_usd": monto if moneda == "USD" else None,
             "monto_original": monto,
             "moneda_original": moneda,
             "sector": r.get("sector")}
        )
    return _cerrar(filas)


def normalizar_ndb(ruta: Path, relevamiento: str) -> pd.DataFrame:
    """NDB. El listado no publica montos, pero la ficha de cada proyecto sí.

    Lo señaló la dirección del proyecto el 17 de septiembre de 2026, y resultó cierto: hay que
    pedir una página por proyecto, pero el dato está. Con eso el NDB deja de ser la única
    institución del corpus sin ninguna cifra.

    El sitio usa dos formatos según el estado. Los proyectos aprobados publican el aporte del
    banco en una tabla de aportantes; los que están en concepto publican un "límite propuesto de
    financiamiento", que es un tope previsto y no un monto aprobado. Se distinguen, porque
    tratarlos igual inflaría la cartera con operaciones que todavía no se aprobaron.
    """
    texto = ruta.read_text(encoding="utf-8", errors="replace")
    bloques = re.findall(r'<div class="project-card card[^"]*">(.*?)\n</div>', texto, re.S)
    url = "https://www.ndb.int/projects/all-projects/"

    # Los montos vienen de la descarga de fichas individuales, que es un archivo aparte.
    detalle: dict[str, dict] = {}
    fichas = sorted((ruta.parent).glob("ndb_montos_*.json"))
    if fichas:
        detalle = {d["url"].rstrip("/"): d for d in json.loads(fichas[-1].read_text(encoding="utf-8"))}

    def campo(patron: str, bloque: str) -> str:
        m = re.search(patron, bloque, re.S)
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""

    filas = []
    for b in bloques:
        enlace = re.search(r'class="card-link" href="([^"]+)"', b)
        proyecto = enlace.group(1) if enlace else ""
        tipo = campo(r'class="project-card-type text-medium-bold">(.*?)</div>', b)
        ficha = detalle.get(proyecto.rstrip("/"), {})

        # El monto aprobado sale de la tabla de aportantes o de la etiqueta de financiamiento;
        # el límite propuesto solo aplica a los que siguen en etapa de concepto.
        aprobado, moneda_apr = monto_desde_texto(ficha.get("monto_ndb") or ficha.get("monto_aprobado"))
        propuesto, moneda_prop = monto_desde_texto(ficha.get("monto_propuesto"))
        en_concepto = aprobado is None and propuesto is not None

        monto = propuesto if en_concepto else aprobado
        moneda = moneda_prop if en_concepto else moneda_apr

        fecha = (a_fecha(ficha.get("fecha_aprobacion"))
                 or a_fecha(ficha.get("fecha_concepto"))
                 or a_fecha(campo(r'class="project-card-date text-small-bold">(.*?)</div>', b)))

        # El NDB presta buena parte de su cartera en moneda local: rand, yuanes, rupias, reales y
        # euros. Lo advirtio la direccion del proyecto el 17 de septiembre de 2026 y el dato lo
        # confirma: 44 de 146 operaciones. Tomarlas como dolares multiplicaba la cartera por
        # cinco. Se convierten con el promedio anual del año de aprobacion, y el monto original se
        # conserva con su moneda para que la conversion sea auditable.
        moneda = normalizar_moneda(moneda)
        anio = int(fecha[:4]) if fecha else None
        en_dolares = a_dolares(monto, moneda, anio)

        filas.append(
            {**_fila_base("NDB", "NDB", url, relevamiento),
             "tipo_ventanilla": "soberana" if tipo == "Sovereign" else "no_soberana",
             "id_proyecto": proyecto,
             "nombre": campo(r'class="project-card-title[^"]*">(.*?)</div>', b),
             "pais": campo(r'class="project-card-country text-small-bold">(.*?)</div>', b),
             "url_proyecto": proyecto or None,
             "fecha_aprobacion": fecha,
             # El listado no declara estado; se deriva de qué publica la ficha.
             "estado": "propuesto" if en_concepto else ("aprobado" if aprobado is not None else "desconocido"),
             "estado_original": "Concept" if en_concepto else ("Approved" if aprobado is not None else None),
             "monto_aprobado_usd": en_dolares,
             "monto_original": monto,
             "moneda_original": moneda,
             "instrumento": tipo,
             "sector": campo(r'class="project-card-cat text-small-bold">(.*?)</div>', b)}
        )
    return _cerrar(filas)


NORMALIZADORES = {
    "gbm": ("gbm/birf-ida_proyectos_*.json", normalizar_gbm),
    "ifc": ("gbm/ifc_inversiones_*.json", normalizar_ifc),
    "miga": ("gbm/miga_garantias_*.json", normalizar_miga),
    "bid": ("gbid/bid_proyectos_*.csv", normalizar_bid),
    "bid_invest": ("gbid/bid-invest_proyectos_*.xml", normalizar_bid_invest),
    "caf": ("caf/caf_actividades_*.xml", normalizar_caf),
    "aiib": ("aiib/aiib_proyectos_*.js", normalizar_aiib),
    "ndb": ("ndb/ndb_proyectos_*.html", normalizar_ndb),
}


def ultima_descarga(patron: str) -> Path:
    """La descarga más reciente que coincida con el patrón, por fecha en el nombre."""
    candidatos = sorted(CRUDO.glob(patron))
    if not candidatos:
        raise FileNotFoundError(f"no hay descargas que coincidan con {patron}")
    return candidatos[-1]


def normalizar_todo() -> pd.DataFrame:
    """Normaliza las ocho fuentes y devuelve el corpus consolidado."""
    partes = []
    for clave, (patron, funcion) in NORMALIZADORES.items():
        ruta = ultima_descarga(patron)
        # La fecha del relevamiento sale del nombre del archivo, que es el que fija el manifiesto.
        marca = re.search(r"(\d{4}-\d{2}-\d{2})", ruta.name)
        partes.append(funcion(ruta, marca.group(1) if marca else ""))
    return pd.concat(partes, ignore_index=True)
