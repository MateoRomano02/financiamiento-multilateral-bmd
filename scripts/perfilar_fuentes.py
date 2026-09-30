"""Perfila las fuentes descargadas y produce el resumen de variables por institución.

Este programa contesta la pregunta que la dirección del proyecto viene pidiendo desde el 25 de
agosto: qué variables publica realmente cada institución, con qué nivel de completitud, y cuáles
de ellas alimentan cada columna del esquema común.

No consulta las fuentes en vivo. Lee las descargas fechadas que están en `data/raw/`, de modo que
el resultado es reproducible y corresponde a un estado verificable del dato.

La parte que importa no es el inventario de campos, que cualquiera puede sacar abriendo el
archivo, sino el **mapeo**: qué campo de cada institución alimenta cada columna del esquema, y
dónde no hay ninguno. Un campo del esquema sin origen en una institución es un hueco que hay que
decidir, no un descuido.

Uso:
    uv run python scripts/perfilar_fuentes.py            # informe a pantalla
    uv run python scripts/perfilar_fuentes.py --markdown # informe en markdown, para el entregable
"""

from __future__ import annotations

import csv
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.common.esquema import COLUMNAS  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
CRUDO = RAIZ / "data/raw"

IATI = "{http://www.w3.org/XML/1998/namespace}"


# ---------------------------------------------------------------------------
# Lectores. Uno por formato, porque cada institución publica en el suyo.
# ---------------------------------------------------------------------------


def _leer_json_lista(ruta: Path, clave: str) -> list[dict]:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    filas = datos.get(clave, datos)
    if isinstance(filas, dict):  # el Banco Mundial devuelve un diccionario indexado por id
        filas = list(filas.values())
    return [f for f in filas if isinstance(f, dict)]


def _leer_csv(ruta: Path) -> list[dict]:
    with ruta.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _leer_xml_items(ruta: Path) -> list[dict]:
    """XML plano del tipo <response><item><campo>valor</campo>...</item></response>."""
    raiz = ET.parse(ruta).getroot()
    return [{hijo.tag: (hijo.text or "").strip() for hijo in item} for item in raiz]


def _leer_iati(ruta: Path) -> list[dict]:
    """XML del estándar IATI. Se aplana a los campos que el corpus necesita.

    IATI es un estándar anidado y extenso; aplanarlo entero produciría cientos de columnas
    irrelevantes. Se extrae lo que mapea al esquema y se cuenta el resto como no utilizado.
    """
    raiz = ET.parse(ruta).getroot()
    filas = []
    for act in raiz:
        fila: dict[str, str] = {}
        fila["iati-identifier"] = (act.findtext("iati-identifier") or "").strip()
        fila["title"] = "".join(act.find("title").itertext()).strip() if act.find("title") is not None else ""
        fila["description"] = (
            "".join(act.find("description").itertext()).strip() if act.find("description") is not None else ""
        )
        fila["activity-status"] = (
            act.find("activity-status").get("code", "") if act.find("activity-status") is not None else ""
        )
        fila["default-currency"] = act.get("default-currency", "")
        for fecha in act.findall("activity-date"):
            fila[f"activity-date@{fecha.get('type')}"] = fecha.get("iso-date", "")
        paises = [p.get("code", "") for p in act.findall("recipient-country")]
        fila["recipient-country"] = ";".join(filter(None, paises))
        sectores = [s.get("code", "") for s in act.findall("sector")]
        fila["sector"] = ";".join(filter(None, sectores))
        presupuesto = act.find("budget/value")
        fila["budget/value"] = (presupuesto.text or "").strip() if presupuesto is not None else ""
        for tx in act.findall("transaction"):
            nodo_tipo = tx.find("transaction-type")
            tipo = nodo_tipo.get("code", "") if nodo_tipo is not None else ""
            valor = tx.find("value")
            if tipo and valor is not None:
                # IATI codifica el tipo de transaccion: 2 es compromiso, 3 desembolso.
                fila[f"transaction@{tipo}"] = (valor.text or "").strip()
                fila[f"transaction@{tipo}/currency"] = valor.get("currency", "")
                fila[f"transaction@{tipo}/date"] = valor.get("value-date", "")
        filas.append(fila)
    return filas


def _leer_js_aiib(ruta: Path) -> list[dict]:
    """El buscador del AIIB se alimenta de un `var data=[...]` en un archivo .js."""
    texto = ruta.read_text(encoding="utf-8", errors="replace")
    arreglo = texto[texto.index("[") : texto.rindex("]") + 1]
    # El archivo termina en "},\n\t\n];": la coma final es valida en JavaScript pero no en JSON.
    arreglo = re.sub(r",\s*]$", "]", arreglo.strip())
    return json.loads(arreglo)


def _leer_html_ndb(ruta: Path) -> list[dict]:
    """El NDB no publica archivo ni servicio: hay que leer su listado HTML.

    Es la única institución del corpus en esa situación, y por eso es la más frágil: cualquier
    rediseño del sitio rompe la extracción. Se deja explícito en el informe.
    """
    texto = ruta.read_text(encoding="utf-8", errors="replace")
    bloques = re.findall(r'<div class="project-card card[^"]*">(.*?)\n</div>', texto, re.S)

    def _texto(patron: str, bloque: str) -> str:
        m = re.search(patron, bloque, re.S)
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""

    filas = []
    for b in bloques:
        enlace = re.search(r'class="card-link" href="([^"]+)"', b)
        filas.append(
            {
                "categoria": _texto(r'class="project-card-cat text-small-bold">(.*?)</div>', b),
                "pais": _texto(r'class="project-card-country text-small-bold">(.*?)</div>', b),
                "titulo": _texto(r'class="project-card-title[^"]*">(.*?)</div>', b),
                "url": enlace.group(1) if enlace else "",
                "tipo": _texto(r'class="project-card-type text-medium-bold">(.*?)</div>', b),
                "fecha": _texto(r'class="project-card-date text-small-bold">(.*?)</div>', b),
            }
        )
    return filas


# ---------------------------------------------------------------------------
# Catálogo de fuentes, con el mapeo al esquema común.
# ---------------------------------------------------------------------------


@dataclass
class Fuente:
    institucion: str
    grupo: str
    archivo: str
    lector: str
    unidad: str
    """Qué representa una fila. Es el dato que más condiciona la comparación entre bancos."""
    mapeo: dict[str, str] = field(default_factory=dict)
    """columna del esquema -> campo de la fuente. Ausente significa que la fuente no lo publica."""
    nota: str = ""


FUENTES: tuple[Fuente, ...] = (
    Fuente(
        institucion="BIRF e IDA",
        grupo="GBM",
        archivo="gbm/birf-ida_proyectos_2026-08-23.json",
        lector="json:projects",
        unidad="una fila por proyecto aprobado",
        mapeo={
            "id_proyecto": "id",
            "nombre": "project_name",
            "pais": "countryshortname",
            "url_proyecto": "url",
            "fecha_aprobacion": "boardapprovaldate",
            "estado_original": "projectstatusdisplay",
            "monto_aprobado_usd": "curr_total_commitment",
            "instrumento": "lendinginstr",
            "sector": "sector1",
        },
        nota="Separa el compromiso de BIRF y de IDA en ibrdcommamt e idacommamt, lo que "
        "permite dividir las dos ventanillas dentro de la misma descarga.",
    ),
    Fuente(
        institucion="IFC",
        grupo="GBM",
        archivo="gbm/ifc_inversiones_2026-08-21.json",
        lector="json:data",
        unidad="una fila por documento, NO por operación",
        mapeo={
            "id_proyecto": "project_number",
            "nombre": "project_name",
            "pais": "country",
            "url_proyecto": "project_url",
            "fecha_aprobacion": "ifc_approval_date",
            "estado_original": "status",
            "monto_aprobado_usd": "total_ifc_investment_as_approved_by_boardmillion__usd",
            "instrumento": "product_line",
            "sector": "industry",
        },
        nota="Requiere deduplicar a nivel proyecto antes de poder agregarse: es el hallazgo H2, "
        "el portal publica una fila por documento. **Sus montos están en millones**, no en "
        "unidades, y vienen además desagregados por instrumento (préstamo, capital, garantía, "
        "gestión de riesgo), lo que permite separar la cartera sin recurrir a otra fuente.",
    ),
    Fuente(
        institucion="MIGA",
        grupo="GBM",
        archivo="gbm/miga_garantias_2026-08-21.json",
        lector="json:data",
        unidad="una fila por garantía emitida",
        mapeo={
            "id_proyecto": "project_id",
            "nombre": "project_name",
            "pais": "host_country",
            "url_proyecto": "project_links",
            "fecha_aprobacion": "project_start_date",
            "monto_aprobado_usd": "gross_issued_amount",
            "instrumento": "product_line",
            "sector": "business_sector",
        },
        nota="Emite garantías, no préstamos: no hay monto desembolsado y no lo va a haber. Solo "
        "cubre las emitidas, no el pipeline propuesto que sí muestra su portal. Ojo: "
        "`project_start_date` es el inicio de la garantía, no la fecha de aprobación; para "
        "series anuales conviene `issued_fy`, que es año fiscal y está al 100%.",
    ),
    Fuente(
        institucion="BID y BID Lab",
        grupo="GBID",
        archivo="gbid/bid_proyectos_2026-08-21.csv",
        lector="csv",
        unidad="una fila por operación aprobada",
        mapeo={
            "id_proyecto": "oper_num",
            "nombre": "oper_nm",
            "pais": "cntry_nm",
            "fecha_aprobacion": "apprvl_dt",
            "estado_original": "publc_sts_nm",
            "monto_aprobado_usd": "orig_apprvd_useq_amnt",
            "instrumento": "lending_instrmnt_nm",
            "sector": "sector_nm",
        },
        nota="BID Lab sale de este mismo archivo por código de instrumento MIF, hallazgo H3. "
        "Trae además subsector, modalidad y clasificación ambiental.",
    ),
    Fuente(
        institucion="BID Invest",
        grupo="GBID",
        archivo="gbid/bid-invest_proyectos_2026-08-21.xml",
        lector="xml:item",
        unidad="una fila por operación",
        mapeo={
            "id_proyecto": "project_number",
            "nombre": "project_name",
            "pais": "country",
            "url_proyecto": "project_url",
            "fecha_aprobacion": "approval_date",
            "estado_original": "status",
            "monto_aprobado_usd": "iic_financing_amount",
            "moneda_original": "currency",
            "instrumento": "Investment_instrument",
            "sector": "sector",
        },
        nota="Descarga completa sin consulta selectiva. Trae además `project_idb_fin_amount`, "
        "que es el aporte del BID en operaciones conjuntas, y `mobilization`, que mide el "
        "capital privado movilizado: los dos son directamente pertinentes a la hipótesis sobre "
        "el crecimiento de las ventanillas no soberanas. Contiene datos de contacto de clientes "
        "que **no deben publicarse**.",
    ),
    Fuente(
        institucion="CAF",
        grupo="CAF",
        archivo="caf/caf_actividades_2026-08-21.xml",
        lector="iati",
        unidad="una actividad IATI por operación",
        mapeo={
            "id_proyecto": "iati-identifier",
            "nombre": "title",
            "pais": "recipient-country",
            "fecha_aprobacion": "activity-date@2",
            "estado_original": "activity-status",
            "monto_aprobado_usd": "transaction@2",
            "monto_desembolsado_usd": "transaction@3",
            "moneda_original": "default-currency",
            "sector": "sector",
        },
        nota="Fuente incompleta, hallazgo H9: cubre entre el 13% y el 48% del volumen que la "
        "propia CAF reporta en sus informes anuales. Se usa junto con la base heredada, no en "
        "lugar de ella. **Es la única fuente del corpus con monto desembolsado explícito**, en la "
        "transacción IATI de tipo 3, presente en el 98% de las actividades. Sus sectores vienen "
        "en código numérico del estándar, no en texto, así que requieren traducción.",
    ),
    Fuente(
        institucion="AIIB",
        grupo="AIIB",
        archivo="aiib/aiib_proyectos_2026-08-21.js",
        lector="js",
        unidad="una fila por proyecto",
        mapeo={
            "nombre": "name",
            "pais": "economy",
            "fecha_aprobacion": "date",
            "url_proyecto": "path",
            "estado_original": "status",
            "monto_aprobado_usd": "approved_funding",
            "sector": "sector",
            "tipo_ventanilla": "financing_type",
        },
        nota="Declara la ventanilla fila por fila en `financing_type`, igual que el NDB. "
        "**Su monto viene como texto**, del tipo \"USD100 million\", y hay que parsearlo. Su "
        "campo de fecha es solo el año. `project_type` está al 31% y no sirve como estado: el "
        "estado real está en `status`, al 100%. Ojo con la licencia: restringe la redistribución.",
    ),
    Fuente(
        institucion="NDB",
        grupo="NDB",
        archivo="ndb/ndb_proyectos_2026-09-06.html",
        lector="html",
        unidad="una fila por proyecto, extraída del listado web",
        mapeo={
            "nombre": "titulo",
            "pais": "pais",
            "url_proyecto": "url",
            "fecha_aprobacion": "fecha",
            "sector": "categoria",
            "tipo_ventanilla": "tipo",
        },
        nota="Única institución sin archivo ni servicio: hay que leer el sitio, y el listado "
        "pagina de a doce sin declararlo. **No publica monto**, que es el campo que más falta "
        "hace. Declara la ventanilla fila por fila, igual que el AIIB.",
    ),
)

LECTORES = {
    "json:projects": lambda p: _leer_json_lista(p, "projects"),
    "json:data": lambda p: _leer_json_lista(p, "data"),
    "csv": _leer_csv,
    "xml:item": _leer_xml_items,
    "iati": _leer_iati,
    "js": _leer_js_aiib,
    "html": _leer_html_ndb,
}


# ---------------------------------------------------------------------------
# Perfilado
# ---------------------------------------------------------------------------


def _completitud(filas: list[dict], campo: str) -> float:
    if not filas:
        return 0.0
    llenos = sum(1 for f in filas if str(f.get(campo, "")).strip() not in ("", "None", "NULL", "-"))
    return 100 * llenos / len(filas)


def perfilar(fuente: Fuente) -> dict:
    ruta = CRUDO / fuente.archivo
    if not ruta.exists():
        return {"fuente": fuente, "error": f"no existe {fuente.archivo}"}
    try:
        filas = LECTORES[fuente.lector](ruta)
    except Exception as exc:  # el informe debe decir que falló, no romperse
        return {"fuente": fuente, "error": f"{type(exc).__name__}: {exc}"}

    campos: Counter[str] = Counter()
    for f in filas:
        campos.update(f.keys())

    perfil = []
    for campo in sorted(campos):
        ejemplo = next(
            (str(f[campo])[:48] for f in filas if str(f.get(campo, "")).strip() not in ("", "None", "NULL", "-")),
            "",
        )
        perfil.append({"campo": campo, "completitud": _completitud(filas, campo), "ejemplo": ejemplo})

    return {"fuente": fuente, "filas": len(filas), "campos": perfil, "error": None}


def informe(perfiles: list[dict], markdown: bool = False) -> str:
    sal: list[str] = []
    esc = "\n"

    if markdown:
        sal.append("# Resumen de variables por institución\n")
        sal.append(
            "Qué publica realmente cada institución del corpus, con qué completitud, y qué campo "
            "alimenta cada columna del esquema común. Generado con "
            "`scripts/perfilar_fuentes.py` sobre las descargas fechadas de `data/raw/`.\n"
        )

    # --- panorama ---
    sal.append("## Panorama" if markdown else "== PANORAMA ==")
    sal.append("")
    if markdown:
        sal.append("| Institución | Grupo | Registros | Campos | Unidad de análisis |")
        sal.append("|---|---|---|---|---|")
    for p in perfiles:
        f = p["fuente"]
        if p["error"]:
            linea = f"| {f.institucion} | {f.grupo} | error | | {p['error']} |"
        else:
            linea = f"| {f.institucion} | {f.grupo} | {p['filas']:,} | {len(p['campos'])} | {f.unidad} |"
        sal.append(linea if markdown else linea.replace("|", " ").strip())
    sal.append("")

    # --- cobertura del esquema: lo que de verdad importa ---
    sal.append("## Cobertura del esquema común" if markdown else "== COBERTURA DEL ESQUEMA ==")
    sal.append("")
    sal.append(
        "Cada celda dice qué campo de la fuente alimenta esa columna. Una celda vacía significa "
        "que **la institución no publica ese dato**, y es una decisión pendiente, no un descuido."
        if markdown
        else ""
    )
    sal.append("")
    relevantes = [c for c in COLUMNAS if c not in ("banco_grupo", "institucion", "fuente_url", "fecha_relevamiento", "anio_aprobacion", "estado", "clasificacion_te", "categoria_te")]
    if markdown:
        sal.append("| Columna del esquema | " + " | ".join(p["fuente"].institucion for p in perfiles) + " |")
        sal.append("|---" * (len(perfiles) + 1) + "|")
    for col in relevantes:
        celdas = []
        for p in perfiles:
            origen = p["fuente"].mapeo.get(col, "")
            celdas.append(f"`{origen}`" if origen else "no publica")
        sal.append(f"| **{col}** | " + " | ".join(celdas) + " |")
    sal.append("")

    # --- detalle por institución ---
    sal.append("## Detalle por institución" if markdown else "== DETALLE ==")
    for p in perfiles:
        f = p["fuente"]
        sal.append("")
        sal.append(f"### {f.institucion}" if markdown else f"-- {f.institucion} --")
        sal.append("")
        if p["error"]:
            sal.append(f"**No se pudo perfilar:** {p['error']}")
            sal.append("")
            if f.nota:
                sal.append(f.nota)
            continue
        sal.append(f"Archivo `{f.archivo}`, {p['filas']:,} registros, {len(p['campos'])} campos.")
        sal.append("")
        sal.append(f"Unidad de análisis: **{f.unidad}**.")
        if f.nota:
            sal.append("")
            sal.append(f.nota)
        sal.append("")
        if markdown:
            sal.append("| Campo | Completitud | Ejemplo |")
            sal.append("|---|---|---|")
        for c in p["campos"]:
            ej = c["ejemplo"].replace("|", "/")
            sal.append(f"| `{c['campo']}` | {c['completitud']:.0f} % | {ej} |")

    return esc.join(sal)


def main() -> int:
    md = "--markdown" in sys.argv
    perfiles = [perfilar(f) for f in FUENTES]
    print(informe(perfiles, markdown=md))
    fallidos = [p for p in perfiles if p["error"]]
    if fallidos and not md:
        print(f"\n{len(fallidos)} fuente(s) no se pudieron perfilar.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
