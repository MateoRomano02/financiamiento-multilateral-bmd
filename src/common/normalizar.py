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
import html
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from functools import lru_cache, partial
from pathlib import Path

import pandas as pd

from .esquema import COLUMNAS, VENTANILLA_POR_INSTITUCION
from .prestatario import prestatario_iati
from .ndb_anexo import URL_INFORME, emparejar, leer_anexo
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


# Los bancos que publican en IATI (CAF, FONPLATA, BCIE) dan el receptor como codigo ISO de dos
# letras, mientras el resto del corpus usa el nombre del pais. Sin traducir, quedan fuera de toda
# agregacion por pais. Son los codigos que aparecen en sus archivos; uno nuevo se veria como
# codigo crudo en el corpus y hay que sumarlo aca.
PAISES_ISO2 = {
    "AR": "Argentina", "BB": "Barbados", "BO": "Bolivia", "BR": "Brazil", "BZ": "Belize",
    "CL": "Chile", "CO": "Colombia", "CR": "Costa Rica", "CU": "Cuba", "DO": "Dominican Republic",
    "EC": "Ecuador", "ES": "Spain", "GT": "Guatemala", "HN": "Honduras", "MX": "Mexico",
    "NI": "Nicaragua", "PA": "Panama", "PE": "Peru", "PY": "Paraguay", "SV": "El Salvador",
    "TT": "Trinidad and Tobago", "UY": "Uruguay", "VE": "Venezuela",
}

# Codigos no estandar que publica algun banco, llevados al ISO. El BCIE escribe RD para Republica
# Dominicana en lugar de DO, en 9 actividades (verificado el 29/09/2026). Sin esto quedaba un pais
# llamado literalmente "RD" en el corpus, sin ningun error que lo avisara.
ALIAS_PAIS = {"RD": "DO"}


def nombre_de_pais(codigo: object) -> str | None:
    """Traduce el codigo ISO2 de las fuentes IATI al nombre que usa el resto del corpus."""
    if codigo is None:
        return None
    partes = []
    for c in str(codigo).split(";"):
        c = ALIAS_PAIS.get(c.strip(), c.strip())
        if c:
            partes.append(PAISES_ISO2.get(c, c))
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
    # Codigos del estandar IATI, comunes a CAF, FONPLATA y BCIE: 2 es implementacion, 4 cerrado.
    "iati": {"1": "propuesto", "2": "en_implementacion", "3": "en_implementacion", "4": "cerrado",
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
    fecha = pd.to_datetime(df["fecha_aprobacion"], errors="coerce")
    df["anio_aprobacion"] = fecha.dt.year
    # El Grupo Banco Mundial cierra el año en junio: lo aprobado en julio de 2024 es del año
    # fiscal 2025. Lo pidió la dirección el 8/10 para poder contrastar contra sus informes anuales.
    df["anio_fiscal"] = (fecha.dt.year + (fecha.dt.month >= 7)).where(df["banco_grupo"] == "GBM")
    return df[list(COLUMNAS)]


# ---------------------------------------------------------------------------
# Un normalizador por institución
# ---------------------------------------------------------------------------


# Tolerancias de la union entre los proyectos del Banco Mundial y su estado de prestamos. Se
# midieron sobre las 3.500 operaciones del periodo que cruzan (29/09/2026): la fecha absorbe
# diferencias de registro entre sistemas, y el margen de monto absorbe el tipo de cambio de los
# creditos de la IDA pactados en Derechos Especiales de Giro o en euros, sin aceptar los siete
# casos en que los dos sistemas difieren entre dos y diecisiete veces sobre el monto.
DIAS_TOLERANCIA_PRESTAMO = 60
MONTO_TOLERANCIA_PRESTAMO = 0.20


# La IDA no publica si cada crédito es préstamo o donación: lo dice el prefijo del número. Los
# IDAD, IDAE e IDAH no tienen cronograma de repago ni registran ningún pago, y los IDAG son
# garantías parciales de riesgo (verificado el 8/10/2026 sobre el estado de créditos; el archivo no
# trae diccionario de prefijos). El resto son créditos.
FORMA_PREFIJO_IDA = {"IDAD": "donacion", "IDAE": "donacion", "IDAH": "donacion", "IDAG": "garantia"}


@lru_cache(maxsize=1)
def prestamos_banco_mundial() -> pd.DataFrame:
    """Una fila por prestamo del BIRF y por credito o donacion de la IDA, de la ultima foto."""
    fuentes = {
        "BIRF": ("ibrd_prestamos_*.json", {"original_principal_amount": "original",
                                           "disbursed_amount": "desembolsado"}),
        "IDA": ("ida_creditos_*.json", {"original_principal_amount_us_": "original",
                                        "disbursed_amount_us_": "desembolsado"}),
    }
    partes = []
    for ventanilla, (patron, renombre) in fuentes.items():
        archivos = sorted((CRUDO / "gbm").glob(patron))
        if not archivos:
            continue
        d = pd.DataFrame(json.loads(archivos[-1].read_text(encoding="utf-8"))["data"]).rename(columns=renombre)
        d["ventanilla"] = ventanilla
        d["fecha_prestamo"] = pd.to_datetime(d["board_approval_date"], format="%d-%b-%Y", errors="coerce")
        for col in ("original", "desembolsado"):
            d[col] = pd.to_numeric(d[col], errors="coerce")
        if ventanilla == "BIRF":
            d["forma"] = d["loan_type"].map(lambda t: "garantia" if t in ("GURB", "GUBF") else "prestamo")
        else:
            prefijo = d["credit_number"].str.extract(r"^([A-Z]+)", expand=False)
            d["forma"] = prefijo.map(lambda p: FORMA_PREFIJO_IDA.get(p, "prestamo"))
        partes.append(d[["project_id", "ventanilla", "fecha_prestamo", "original", "desembolsado", "forma"]])
    if not partes:
        return pd.DataFrame(columns=["project_id", "ventanilla", "fecha_prestamo", "original", "desembolsado", "forma"])
    return pd.concat(partes, ignore_index=True)


def _desembolsos_banco_mundial(df: pd.DataFrame) -> pd.DataFrame:
    """Asigna a cada operacion del BIRF y de la IDA lo desembolsado de sus prestamos.

    El servicio de proyectos no publica desembolsos; el estado de prestamos de Finances One si,
    pero por prestamo y no por operacion. La union no puede ser solo por proyecto: los
    financiamientos adicionales se aprueban como proyecto nuevo pero su prestamo queda registrado
    bajo el proyecto original, y sumar por proyecto le atribuia al original la plata de sus
    ampliaciones (463 operaciones desembolsando mas de lo aprobado). Por eso cada prestamo se
    asigna a la operacion del mismo proyecto y ventanilla aprobada en la misma fecha, y solo si el
    monto del prestamo coincide con el aprobado. Si no coincide, la operacion queda sin
    desembolso: es preferible un hueco visible a una cifra atribuida al proyecto equivocado.
    """
    prestamos = prestamos_banco_mundial()
    if prestamos.empty:
        return df
    base = df[["institucion", "id_proyecto", "fecha_aprobacion", "monto_aprobado_usd"]].reset_index()
    base["fecha"] = pd.to_datetime(base["fecha_aprobacion"], errors="coerce")
    unidos = base.merge(prestamos, left_on=["id_proyecto", "institucion"],
                        right_on=["project_id", "ventanilla"])
    unidos = unidos[(unidos["fecha_prestamo"] - unidos["fecha"]).dt.days.abs() <= DIAS_TOLERANCIA_PRESTAMO]
    por_operacion = unidos.groupby("index").agg(original=("original", "sum"),
                                                desembolsado=("desembolsado", "sum"))
    aprobado = base.set_index("index").loc[por_operacion.index, "monto_aprobado_usd"]
    coincide = (por_operacion["original"] / aprobado - 1).abs() <= MONTO_TOLERANCIA_PRESTAMO
    df["monto_desembolsado_usd"] = df["monto_desembolsado_usd"].astype("float64")
    df.loc[por_operacion.index[coincide], "monto_desembolsado_usd"] = por_operacion.loc[coincide, "desembolsado"]
    # La forma no depende del monto: alcanza con que el préstamo sea de la misma operación. Una
    # operación de la IDA que combina crédito y donación queda como mixta.
    formas = unidos.groupby("index")["forma"].agg(lambda f: f.iloc[0] if f.nunique() == 1 else "mixto")
    df.loc[formas.index, "forma_financiamiento"] = formas
    return df


# Forma del financiamiento, criterio de la dirección del 8/10: préstamo, donación, garantía u otro
# (capital accionario, gestión de riesgo, bonos). "mixto" cuando la fuente declara más de una para la
# misma operación sin separar el monto. El mapeo de cada fuente y su evidencia: research/forma-de-financiamiento.md.
FORMA_IFC = {"Loan": "prestamo", "Guarantee": "garantia", "Equity": "otro", "Risk Management": "otro"}
FORMA_IATI = {"421": "prestamo", "410": "prestamo", "110": "donacion", "1100": "garantia", "510": "otro"}
FORMA_BID = {"Loan Operation": "prestamo", "Container": "prestamo", "Technical Cooperation": "donacion",
             "Investment Grants": "donacion", "Grant Financing Product": "donacion",
             "Guarantee": "garantia", "Equity": "otro"}


def _forma_bid(r: dict) -> str | None:
    """El tipo de operación del BID, corregido por modalidad: hay garantías y donaciones dentro de
    las operaciones de préstamo y de los contenedores."""
    if (r.get("modality_cd") or "").strip() in ("PBG", "PCG", "TFP") or (r.get("facility_typ_cd") or "").strip() == "IGF":
        return "garantia"
    if (r.get("facility_typ_cd") or "").strip() == "FFG":
        return "donacion"
    return FORMA_BID.get((r.get("opertyp_nm") or "").strip())


def _forma_bid_invest(valor: str | None) -> str | None:
    v = (valor or "").replace("&amp;", "&").strip()
    if not v or v == "Not Specified":
        return None
    if "&" in v:
        return "mixto"
    if "Loan" in v:
        return "prestamo"
    if v == "Guarantee":
        return "garantia"
    return "otro"  # capital, fondos y bonos


def _limpiar_texto(valor: object) -> str | None:
    """Texto plano de una descripción: sin etiquetas HTML, entidades ni espacios repetidos."""
    if not valor or not isinstance(valor, str):
        return None
    texto = html.unescape(html.unescape(valor))
    texto = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", texto)).strip()
    return texto or None


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
            "descripcion": _limpiar_texto(r.get("project_abstract")),
        }
        # Los fondos de terceros que administra el banco (donantes, fondos fiduciarios) van aparte
        # del aporte del banco, por criterio de la dirección del 8/10. Se anotan en una sola de las
        # filas del proyecto para que sumar la columna no los cuente dos veces.
        terceros = a_numero(r.get("grantamt")) or None
        for institucion, campo in (("BIRF", "curr_ibrd_commitment"), ("IDA", "idacommamt")):
            monto = a_numero(r.get(campo))
            if not monto:
                continue
            filas.append(
                {**_fila_base(institucion, "GBM", url, relevamiento), **comunes,
                 "id_proyecto": f"{r.get('id')}", "monto_aprobado_usd": monto,
                 "aporte_terceros_usd": terceros}
            )
            terceros = None
    return _desembolsos_banco_mundial(_cerrar(filas))


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
             "forma_financiamiento": FORMA_IFC.get(r.get("product_line")),
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
             # MIGA emite garantías de inversión (seguro de riesgo político y afines), todo su
             # catálogo es garantía.
             "forma_financiamiento": "garantia",
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
             # El BID es la unica fuente del corpus que publica el costo total del proyecto como
             # campo estructurado, en 27.286 de sus 27.329 filas. La direccion lo pidio el 18/09
             # para poder medir que proporcion de cada proyecto pone el banco y cuanta contraparte
             # local aporta el pais. El NDB lo trae en prosa y solo en 37 de 170 fichas.
             "costo_total_proyecto_usd": a_numero(r.get("totl_cost_orig")),
             "instrumento": r.get("opertyp_nm"),
             "forma_financiamiento": _forma_bid(r),
             "descripcion": _limpiar_texto(r.get("objtv")),
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
             "forma_financiamiento": _forma_bid_invest(r.get("Investment_instrument")),
             "descripcion": _limpiar_texto(r.get("description")),
             "sector": (r.get("sector") or "").strip() or None}
        )
    return _cerrar(filas)


@lru_cache(maxsize=1)
def sectores_cad() -> dict[str, str]:
    """Nombre de cada codigo de sector del CAD de la OCDE, desde la lista oficial del estandar IATI."""
    archivos = sorted((CRUDO / "referencia").glob("iati_sector_*.json"))
    if not archivos:
        return {}
    datos = json.loads(archivos[-1].read_text(encoding="utf-8"))
    return {x["code"]: x["name"] for x in datos.get("data", datos)}


def _sector_iati(act: ET.Element) -> str | None:
    """El sector con nombre legible si el banco lo publica, y si no el codigo CAD traducido.

    Antes se tomaba el primer <sector> del documento. En CAF funcionaba porque es el unico y trae
    nombre; en FONPLATA el primero es siempre un codigo sin nombre y en el BCIE no hay ninguno con
    nombre, asi que las dos quedaban con el sector vacio en el 100% de las operaciones.
    """
    sectores = act.findall("sector")
    for s in sectores:
        if s.get("vocabulary") in ("98", "99"):  # vocabulario propio del banco, con narrativa
            texto = "".join(s.itertext()).strip()
            if texto:
                return texto
    cad = [(float(s.get("percentage") or 0), s.get("code") or "")
           for s in sectores if s.get("vocabulary") in (None, "1")]
    if not cad:
        return None
    codigo = max(cad)[1]  # el de mayor porcentaje, cuando la operacion reparte entre varios
    return sectores_cad().get(codigo, codigo)


# Fechas de relleno: el archivo de CAF del 9/09/2026 trae compromisos fechados 1900-01-01 (dos
# prestamos de 2025 por USD 850 millones) y un inicio 1970-01-01, que es el cero de los relojes de
# computadora. No son fechas, son campos vacios con otro disfraz.
FECHAS_DE_RELLENO = {"1900-01-01", "1970-01-01"}


def _fecha_de_compromiso(act: ET.Element) -> str | None:
    """La fecha de la transaccion de compromiso, que es la aprobacion.

    Antes se tomaba el primer activity-date del documento. En CAF y FONPLATA coincidia por el orden
    de los campos; en el BCIE el primero es el de tipo 1, que resulta ser el compromiso mas 365 dias
    exactos, y corria un anio las 119 operaciones con compromiso (verificado el 29/09/2026). Si hay
    varios compromisos, manda el primero.
    """
    fechas = []
    for tx in act.findall("transaction"):
        tipo = tx.find("transaction-type")
        fecha = tx.find("transaction-date")
        if tipo is not None and tipo.get("code") == "2" and fecha is not None and fecha.get("iso-date"):
            fechas.append(fecha.get("iso-date"))
    fechas = [f for f in fechas if f[:10] not in FECHAS_DE_RELLENO]
    if fechas:
        return min(fechas)
    # Sin transaccion de compromiso: el inicio efectivo, nunca el tipo 1 por lo dicho arriba.
    return next((d.get("iso-date") for d in act.findall("activity-date")
                 if d.get("type") == "2" and (d.get("iso-date") or "")[:10] not in FECHAS_DE_RELLENO), None)


def normalizar_iati(ruta: Path, relevamiento: str, institucion: str) -> pd.DataFrame:
    """Los bancos que publican en el estandar IATI: CAF, FONPLATA y BCIE.

    Un solo normalizador para los tres, porque el estandar es el mismo. La transaccion de tipo 2 es
    el compromiso y la de tipo 3 el desembolso, y son las unicas tres fuentes del corpus que
    publican desembolsos por operacion. Las transacciones del mismo tipo se suman: el estandar
    admite desembolsos en cuotas.
    """
    raiz = ET.parse(ruta).getroot()
    reporta = raiz.find("iati-activity/reporting-org")
    ref = reporta.get("ref") if reporta is not None else ""
    url = f"https://d-portal.org/ctrack.html?reporting_ref={ref}"
    filas = []
    for act in raiz:
        moneda = act.get("default-currency")
        transacciones: dict[str, float] = {}
        for tx in act.findall("transaction"):
            nodo = tx.find("transaction-type")
            valor = tx.find("value")
            if nodo is not None and valor is not None:
                monto = a_numero(valor.text)
                if monto is not None:
                    codigo_tx = nodo.get("code", "")
                    transacciones[codigo_tx] = transacciones.get(codigo_tx, 0.0) + monto
        titulo = act.find("title")
        estado = act.find("activity-status")
        paises = [p.get("code", "") for p in act.findall("recipient-country")]
        # Una operacion multipais sin pais unico se marca como regional, igual que en el resto del
        # corpus, en lugar de quedar vacia.
        pais = nombre_de_pais(";".join(filter(None, paises))) or (
            "Regional" if act.find("recipient-region") is not None else None)
        fecha = a_fecha(_fecha_de_compromiso(act))
        anio = int(fecha[:4]) if fecha else None
        codigo = estado.get("code") if estado is not None else None
        prestatario, tipo_prestatario, _ = prestatario_iati(act, institucion, pais)
        tipo_fin = act.find("default-finance-type")
        descripcion = act.find("description")
        filas.append(
            {**_fila_base(institucion, institucion, url, relevamiento),
             "prestatario": prestatario or None,
             "tipo_prestatario": tipo_prestatario,
             # Solo los casos claros entran a una ventanilla; los intermedios quedan para revisión.
             "tipo_ventanilla": tipo_prestatario if tipo_prestatario in ("soberana", "no_soberana") else None,
             "id_proyecto": (act.findtext("iati-identifier") or "").strip(),
             "nombre": "".join(titulo.itertext()).strip() if titulo is not None else None,
             "pais": pais,
             "url_proyecto": next((d.get("url") for d in act.findall("document-link") if d.get("url")), None),
             "fecha_aprobacion": fecha,
             "estado": mapear_estado("iati", codigo),
             "estado_original": codigo,
             "monto_aprobado_usd": a_dolares(transacciones.get("2"), moneda, anio),
             "monto_desembolsado_usd": a_dolares(transacciones.get("3"), moneda, anio),
             "moneda_original": normalizar_moneda(moneda),
             "monto_original": transacciones.get("2"),
             "forma_financiamiento": FORMA_IATI.get(tipo_fin.get("code") if tipo_fin is not None else None),
             "descripcion": _limpiar_texto("".join(descripcion.itertext()) if descripcion is not None else None),
             "sector": _sector_iati(act)}
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
        fecha = a_fecha(r.get("date"))
        filas.append(
            {**_fila_base("AIIB", "AIIB", url, relevamiento),
             "tipo_ventanilla": ventanilla,
             "id_proyecto": (r.get("path") or "").strip(),
             "nombre": (r.get("name") or "").strip(),
             "pais": r.get("economy"),
             "url_proyecto": f"https://www.aiib.org{r.get('path', '')}",
             # El AIIB publica solo el año de aprobación, no la fecha.
             "fecha_aprobacion": fecha,
             "estado": mapear_estado("aiib", r.get("status")),
             "estado_original": r.get("status"),
             # 12 de las 338 operaciones con monto estan en euros. Hasta el 23 de septiembre de
             # 2026 se descartaban, asi que quedaban fuera de toda suma sin que nada lo avisara.
             # Se convierten con el mismo criterio que el NDB.
             "monto_aprobado_usd": a_dolares(monto, moneda, int(fecha[:4]) if fecha else None),
             "monto_original": monto,
             "moneda_original": normalizar_moneda(moneda),
             "sector": r.get("sector")}
        )
    return _cerrar(filas)


def _unir_anexo_ndb(filas: list[dict], ruta: Path, relevamiento: str) -> list[dict]:
    """Une al corpus del NDB el anexo de operaciones aprobadas de su informe anual.

    La ficha web publica el monto vigente: deja sin monto a las operaciones canceladas y muestra el
    remanente de las canceladas en parte. El anexo trae lo que aprobó el directorio, y con eso:
    el monto original va en su propia columna sin tocar el vigente; si la ficha no tiene monto se
    completa con el del anexo; las canceladas por completo pasan a "cancelado"; y la operación que
    el listado web no tiene se agrega como fila, con la fuente apuntando al PDF.

    Sin PDF descargado devuelve las filas como vienen, para que el corpus se pueda armar igual.

    Krasnodar Cable Car (Rusia, 2019) está en el listado web y no figura en el anexo. El informe
    2019 solo habla de su preparación, así que probablemente nunca se aprobó, pero eso no está
    probado: su estado queda como lo publica la ficha y se reporta aparte.
    """
    informes = sorted(ruta.parent.glob("ndb_informe_anual_*.pdf"))
    if not informes:
        return filas

    por_fila: dict[int, list] = {}
    faltantes = []
    for operacion in leer_anexo(informes[-1]):
        i = emparejar(operacion, filas)
        if i is None:
            faltantes.append(operacion)
        else:
            por_fila.setdefault(i, []).append(operacion)

    def original_usd(operaciones: list) -> float | None:
        # Promedio anual del año de aprobación que declara el anexo, igual que el resto del corpus.
        montos = [a_dolares(o.monto_millones * 1e6, o.moneda_monto, o.anio_aprobacion) for o in operaciones]
        return None if any(m is None for m in montos) else sum(montos)

    for i, operaciones in por_fila.items():
        fila = filas[i]
        fila["monto_aprobado_original_usd"] = original_usd(operaciones)
        if fila["monto_aprobado_usd"] is None or pd.isna(fila["monto_aprobado_usd"]):
            fila["monto_aprobado_usd"] = fila["monto_aprobado_original_usd"]
            if len(operaciones) == 1 and fila["monto_original"] is None:
                fila["monto_original"] = operaciones[0].monto_millones * 1e6
                fila["moneda_original"] = normalizar_moneda(operaciones[0].moneda_monto)
        if all(o.cancelada_total for o in operaciones):
            nota = "; ".join(f"Cancelled in {o.anio_cancelacion} (informe anual)" for o in operaciones)
            fila["estado"] = "cancelado"
            fila["estado_original"] = f"{fila['estado_original']}; {nota}" if fila["estado_original"] else nota
        elif fila["estado"] == "desconocido":
            # La ficha no publicaba monto y el estado quedaba sin derivar; el anexo es de operaciones
            # aprobadas y sin nota de cancelación total, así que está aprobada.
            fila["estado"] = "aprobado"
            fila["estado_original"] = "Approved (informe anual)"

    for o in faltantes:
        nota = f"{o.nota.rstrip('.')} (informe anual)" if o.nota else None
        filas.append(
            {**_fila_base("NDB", "NDB", URL_INFORME, relevamiento),
             "tipo_ventanilla": "soberana" if o.tipo == "soberana" else "no_soberana",
             "id_proyecto": f"{URL_INFORME}#{o.numero}",
             "nombre": o.nombre,
             "pais": o.pais,
             "url_proyecto": None,
             "fecha_aprobacion": a_fecha(o.anio_aprobacion),
             "estado": "cancelado" if o.cancelada_total else "aprobado",
             "estado_original": nota or "Approved (informe anual)",
             "monto_aprobado_usd": original_usd([o]),
             "monto_aprobado_original_usd": original_usd([o]),
             "monto_original": o.monto_millones * 1e6,
             "moneda_original": normalizar_moneda(o.moneda_monto),
             "instrumento": "Sovereign" if o.tipo == "soberana" else "Non-Sovereign"}
        )
    return filas


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

        # Costo total del proyecto, pedido por la direccion el 18/09 para saber que proporcion
        # pone el banco. Solo 37 de las 170 fichas lo traen y siempre en prosa, nunca como campo.
        costo, moneda_costo = monto_desde_texto(ficha.get("costo_total"))
        costo_usd = a_dolares(costo, normalizar_moneda(moneda_costo), anio)

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
             "costo_total_proyecto_usd": costo_usd,
             "instrumento": tipo,
             "sector": campo(r'class="project-card-cat text-small-bold">(.*?)</div>', b)}
        )
    return _cerrar(_unir_anexo_ndb(filas, ruta, relevamiento))


NORMALIZADORES = {
    "gbm": ("gbm/birf-ida_proyectos_*.json", normalizar_gbm),
    "ifc": ("gbm/ifc_inversiones_*.json", normalizar_ifc),
    "miga": ("gbm/miga_garantias_*.json", normalizar_miga),
    "bid": ("gbid/bid_proyectos_*.csv", normalizar_bid),
    "bid_invest": ("gbid/bid-invest_proyectos_*.xml", normalizar_bid_invest),
    "caf": ("caf/caf_actividades_*.xml", partial(normalizar_iati, institucion="CAF")),
    "fonplata": ("fonplata/fonplata_actividades_*.xml", partial(normalizar_iati, institucion="FONPLATA")),
    "bcie": ("bcie/bcie_actividades_*.xml", partial(normalizar_iati, institucion="BCIE")),
    "aiib": ("aiib/aiib_proyectos_*.js", normalizar_aiib),
    "ndb": ("ndb/ndb_proyectos_*.html", normalizar_ndb),
}


def ultima_descarga(patron: str) -> Path:
    """La descarga más reciente que coincida con el patrón, por fecha en el nombre."""
    candidatos = sorted(CRUDO.glob(patron))
    if not candidatos:
        raise FileNotFoundError(f"no hay descargas que coincidan con {patron}")
    return candidatos[-1]


# Fuentes que sacan operaciones de su archivo cuando terminan. El 9/09/2026 CAF republico su
# archivo IATI con 286 actividades en lugar de 478: saco 225, y 217 de ellas estaban en estado
# posterior a la finalizacion. Usar solo la ultima foto le quitaba al corpus la mitad de CAF
# 2014-2025. Para estas fuentes se unen todas las fotos descargadas (ver acumular_fotos).
ACUMULAN_FOTOS = {"caf"}


def _fecha_del_nombre(ruta: Path) -> str:
    # La fecha del relevamiento sale del nombre del archivo, que es el que fija el manifiesto.
    marca = re.search(r"(\d{4}-\d{2}-\d{2})", ruta.name)
    return marca.group(1) if marca else ""


def acumular_fotos(fotos: list[pd.DataFrame]) -> pd.DataFrame:
    """Une varias fotos de una misma fuente, de la mas vieja a la mas nueva.

    De cada operacion queda la version de la foto mas nueva que la trae. Una operacion que solo
    esta en una foto vieja se conserva, con la fecha de relevamiento de esa foto. Hay una
    excepcion: si la foto nueva trae una operacion con el mismo nombre y el mismo anio bajo otro
    identificador, la vieja se descarta, porque es la misma operacion republicada. Pasa en CAF con
    un prestamo de Colombia de 2020 por USD 350 millones.
    """
    union = pd.concat(fotos, ignore_index=True)
    # De cada operacion manda la foto mas nueva, campo por campo: si la nueva trae un campo vacio,
    # queda el valor de la anterior. El archivo de CAF del 9/09 dejo de publicar casi todos los
    # desembolsos (28 transacciones contra 467) y tomar la fila entera de la foto nueva se los
    # borraba a 215 operaciones.
    union = union.groupby("id_proyecto", sort=False).last().reset_index()
    clave = union["nombre"].fillna("").str.lower().str.strip() + "|" + union["anio_aprobacion"].astype(str)
    mas_nueva = union.groupby(clave)["fecha_relevamiento"].transform("max")
    republicada = (union["fecha_relevamiento"] < mas_nueva) & (clave.str.len() > 5)
    return union[~republicada].reset_index(drop=True)


def normalizar_todo() -> pd.DataFrame:
    """Normaliza todas las fuentes y devuelve el corpus consolidado."""
    partes = []
    for clave, (patron, funcion) in NORMALIZADORES.items():
        if clave in ACUMULAN_FOTOS:
            fotos = [funcion(r, _fecha_del_nombre(r)) for r in sorted(CRUDO.glob(patron))]
            partes.append(acumular_fotos(fotos))
            continue
        ruta = ultima_descarga(patron)
        partes.append(funcion(ruta, _fecha_del_nombre(ruta)))
    return pd.concat(partes, ignore_index=True)
