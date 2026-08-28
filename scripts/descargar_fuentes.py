# -*- coding: utf-8 -*-
"""
Descarga el dato crudo de cada institucion desde su fuente oficial.

Como se usa:
  export CONTACTO="tu.correo@institucion.edu"    # se envia en el user-agent
  uv run python scripts/descargar_fuentes.py              # todas las fuentes
  uv run python scripts/descargar_fuentes.py caf bid      # solo algunas

Cada descarga va a data/raw/<banco>/ con la fecha en el nombre del archivo, y queda
registrada en el manifest.json de ese directorio con la URL de origen, la fecha ISO, el
tamano y el conteo de registros obtenido.

Ese registro no es burocracia: los conjuntos de los bancos son vivos y su numero de filas
cambia entre descargas, asi que la unica forma de detectar un cambio brusco es comparar
contra el conteo anterior. Por eso el pipeline nunca fija un numero esperado de filas.

Las URLs y el veredicto de oficialidad de cada fuente estan en docs/accesos-a-los-datos.md.
La evidencia de como se verifico cada una, en research/relevamiento-de-fuentes.md.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import httpx

RAIZ = Path(__file__).resolve().parent.parent
CRUDO = RAIZ / "data" / "raw"

# Identificarse es parte del acceso respetuoso a estos servicios: si una institucion
# necesita contactar a quien esta consumiendo sus datos, tiene como hacerlo. El correo se
# toma de la variable de entorno CONTACTO para que cada persona use el suyo.
CONTACTO = os.environ.get("CONTACTO", "sin-contacto-declarado")
USER_AGENT = (
    f"proyecto-academico-UNSAM/1.0 (Licenciatura en Ciencia de Datos; contacto: {CONTACTO})"
)
TIMEOUT = httpx.Timeout(120.0, connect=30.0)


@dataclass(frozen=True)
class Fuente:
    """Una fuente descargable de una institucion."""

    clave: str
    institucion: str
    carpeta: str
    url: str
    extension: str
    descripcion: str

    @property
    def nombre_archivo(self) -> str:
        return f"{self.clave}_{date.today().isoformat()}.{self.extension}"


FUENTES: tuple[Fuente, ...] = (
    Fuente(
        clave="birf-ida_proyectos",
        institucion="BIRF/IDA",
        carpeta="gbm",
        url=(
            "https://search.worldbank.org/api/v3/projects"
            "?format=json&rows=1000&fl="
            # Identificacion y ubicacion
            "id,proj_id,project_name,project_abstract,countryname,countrycode,"
            "countryshortname,regionname,"
            # Fechas y estado
            "boardapprovaldate,closingdate,approvalfy,status,projectstatusdisplay,"
            # Montos
            "totalamt,totalcommamt,curr_total_commitment,ibrdcommamt,idacommamt,"
            "grantamt,lendprojectcost,"
            # Quien recibe y quien ejecuta: el equipo los necesita y no los teniamos
            "borrower,impagency,"
            # Clasificacion sectorial y de instrumento
            "mjsector,major_sectors,sector1,theme1,lendinginstr,prodline,"
            # Salvaguardas: esrc_ovrl_risk_rate es la calificacion de riesgo ambiental
            # y social, directamente pertinente al eje de normativa del proyecto
            "esrc_ovrl_risk_rate,envassesmentcategorycode,cons_serv_reqd_ind,"
            "teamleadname,url,source"
        ),
        extension="json",
        descripcion=(
            "API de proyectos del Banco Mundial, version 3. Paginada. Se usa v3 y no v2 "
            "porque conviven ambas y v3 es mas completa: 28.081 proyectos contra 22.729, "
            "y 381 de Argentina contra 255 (verificado el 21/08/2026)."
        ),
    ),
    Fuente(
        clave="ifc_inversiones",
        institucion="IFC",
        carpeta="gbm",
        url=(
            "https://datacatalogapi.worldbank.org/dexapps/fone/api/apiservice"
            "?datasetId=DS00499&resourceId=RS00448&type=json&top=20000"
        ),
        extension="json",
        descripcion="IFC Investment Services Projects, via Finances One. Una fila por documento.",
    ),
    Fuente(
        clave="miga_garantias",
        institucion="MIGA",
        carpeta="gbm",
        url=(
            "https://datacatalogapi.worldbank.org/dexapps/fone/api/apiservice"
            "?datasetId=DS00988&resourceId=RS00918&type=json&top=5000"
        ),
        extension="json",
        descripcion="MIGA Issued Projects, via Finances One.",
    ),
    Fuente(
        clave="bid_proyectos",
        institucion="BID",
        carpeta="gbid",
        url="",  # se resuelve en tiempo de ejecucion, ver resolver_bid()
        extension="csv",
        descripcion=(
            "Catalogo de datos abiertos del BID (CKAN), DOI 10.60966/ihisavwe, CC-BY 4.0. "
            "Incluye BID Lab, filtrable por lending_instrmnt_cd == 'MIF'."
        ),
    ),
    Fuente(
        clave="bid-invest_proyectos",
        institucion="BID Invest",
        carpeta="gbid",
        url="https://idbinvest.org/en/projects.xml",
        extension="xml",
        descripcion="Descarga completa de la cartera de BID Invest.",
    ),
    Fuente(
        clave="caf_actividades",
        institucion="CAF",
        carpeta="caf",
        url="",  # se resuelve en tiempo de ejecucion, ver resolver_caf()
        extension="xml",
        descripcion=(
            "Archivo de actividades IATI de CAF. La URL del recurso cambia con cada "
            "publicacion, por eso se resuelve contra el registro y no se hardcodea."
        ),
    ),
    Fuente(
        clave="ndb_proyectos",
        institucion="NDB",
        carpeta="ndb",
        url="https://www.ndb.int/projects/all-projects/",
        extension="html",
        descripcion="Listado de proyectos del NDB en HTML estatico.",
    ),
    Fuente(
        clave="aiib_proyectos",
        institucion="AIIB",
        carpeta="aiib",
        url="https://www.aiib.org/en/projects/list/.content/all-projects-data.js",
        extension="js",
        descripcion=(
            "Conjunto que alimenta el buscador de AIIB. OJO CON LA LICENCIA: AIIB "
            "prohibe obra derivada sin consentimiento escrito, ver docs/accesos-a-los-datos.md."
        ),
    ),
)

REGISTRO_IATI_CAF = "https://iatiregistry.org/api/3/action/package_search?fq=organization:caf&rows=50"
API_CKAN_BID = "https://data.iadb.org/api/3/action/package_show?id=idb-projects-dataset"


def resolver_caf(cliente: httpx.Client) -> str:
    """Devuelve la URL del archivo de actividades vigente de CAF en el registro IATI.

    CAF publica dos archivos: el de actividades (las operaciones, que es el que interesa) y
    el de organizacion (presupuestos institucionales). La URL de cada uno cambia con cada
    publicacion, asi que se resuelve contra el registro en vez de fijarla.
    """
    datos = cliente.get(REGISTRO_IATI_CAF).raise_for_status().json()
    for paquete in datos["result"]["results"]:
        if "actfile" not in paquete["name"]:
            continue
        for recurso in paquete.get("resources", []):
            if recurso.get("url"):
                return recurso["url"]
    raise RuntimeError("no se encontro el archivo de actividades de CAF en el registro IATI")


def resolver_bid(cliente: httpx.Client, idioma: str = "EN") -> str:
    """Devuelve la URL del CSV vigente del BID, consultando su API de datos abiertos.

    El BID publica el mismo conjunto en dos idiomas, cada uno con su propio identificador
    de archivo. Esos identificadores cambian cuando el banco republica, asi que se los
    resuelve por API en vez de fijarlos. El dataset tiene DOI 10.60966/ihisavwe.
    """
    datos = cliente.get(API_CKAN_BID).raise_for_status().json()
    for recurso in datos["result"].get("resources", []):
        if recurso.get("format") == "CSV" and recurso.get("name", "").startswith(idioma):
            return recurso["url"]
    raise RuntimeError(f"no se encontro el CSV en {idioma} del BID en su API")


def paginar_worldbank(cliente: httpx.Client, url_base: str) -> dict:
    """Recorre la API de proyectos del Banco Mundial, que devuelve de a 1000 por pagina."""
    proyectos: dict = {}
    offset, total = 0, None
    while True:
        pagina = cliente.get(f"{url_base}&os={offset}").raise_for_status().json()
        if total is None:
            total = int(pagina.get("total", 0))
        lote = pagina.get("projects", {})
        if not lote:
            break
        proyectos.update(lote)
        offset += len(lote)
        print(f"    {len(proyectos)}/{total}", flush=True)
        if offset >= total:
            break
    return {"total": total, "descargados": len(proyectos), "projects": proyectos}


def contar_registros(ruta: Path, contenido: bytes) -> int | None:
    """Cuenta registros segun el formato. Devuelve None si no se puede determinar."""
    if ruta.suffix == ".csv":
        # Hay saltos de linea dentro de campos citados, asi que contarlos sobreestima:
        # el CSV del BID da 29.294 saltos para 27.329 filas reales.
        import csv as _csv
        import io as _io
        texto = contenido.decode("utf-8", errors="replace")
        return sum(1 for _ in _csv.DictReader(_io.StringIO(texto)))
    if ruta.suffix == ".xml":
        # BID Invest usa <item, IATI usa <iati-activity.
        return contenido.count(b"<item ") or contenido.count(b"<iati-activity")
    if ruta.suffix == ".json":
        try:
            datos = json.loads(contenido)
        except json.JSONDecodeError:
            return None
        if isinstance(datos, dict):
            if "descargados" in datos:
                return datos["descargados"]
            if isinstance(datos.get("data"), list):
                return len(datos["data"])
            if isinstance(datos.get("projects"), dict):
                return len(datos["projects"])
        return None
    return None


def actualizar_manifest(fuente: Fuente, ruta: Path, tamano: int, registros: int | None) -> None:
    """Registra la descarga en el manifest.json del directorio del banco."""
    manifest_path = ruta.parent / "manifest.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.exists()
        else {
            "descripcion": "Descargas desde las fuentes oficiales. Se regeneran con scripts/descargar_fuentes.py.",
            "descargas": [],
        }
    )
    manifest["descargas"].append(
        {
            "archivo": ruta.name,
            "institucion": fuente.institucion,
            "url_origen": fuente.url,
            "fecha_descarga": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "bytes": tamano,
            "registros": registros,
            "descripcion": fuente.descripcion,
            # La URL completa queda arriba, pero la version del endpoint se registra aparte
            # porque es lo primero que se rompe: el Banco Mundial tiene v2 y v3 activas con
            # 5.352 proyectos de diferencia, y la mas completa no figura en su documentacion.
            "version_endpoint": next(
                (parte for parte in fuente.url.split("/") if parte.startswith("v") and parte[1:].isdigit()),
                None,
            ),
        }
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def descargar(fuente: Fuente, cliente: httpx.Client) -> bool:
    destino = CRUDO / fuente.carpeta
    destino.mkdir(parents=True, exist_ok=True)
    ruta = destino / fuente.nombre_archivo

    print(f"  {fuente.institucion} ...", flush=True)
    try:
        if fuente.clave in ("caf_actividades", "bid_proyectos"):
            url = resolver_caf(cliente) if fuente.clave == "caf_actividades" else resolver_bid(cliente)
            fuente = Fuente(**{**fuente.__dict__, "url": url})
            print(f"    resuelto a {url}", flush=True)

        if fuente.clave == "birf-ida_proyectos":
            contenido = json.dumps(
                paginar_worldbank(cliente, fuente.url), ensure_ascii=False
            ).encode("utf-8")
        else:
            contenido = cliente.get(fuente.url, follow_redirects=True).raise_for_status().content

        ruta.write_bytes(contenido)
        registros = contar_registros(ruta, contenido)
        actualizar_manifest(fuente, ruta, len(contenido), registros)
        print(
            f"    OK  {len(contenido):>12,} bytes"
            f"{f'  {registros:,} registros' if registros is not None else ''}"
            f"  -> {ruta.relative_to(RAIZ)}",
            flush=True,
        )
        return True
    except Exception as error:  # noqa: BLE001 - se reporta y se sigue con las demas fuentes
        print(f"    FALLO  {type(error).__name__}: {error}", flush=True)
        return False


def main(claves: list[str]) -> int:
    fuentes = [f for f in FUENTES if not claves or f.clave in claves or f.carpeta in claves]
    if not fuentes:
        print(f"Ninguna fuente coincide con {claves}.")
        print("Disponibles:", ", ".join(f.clave for f in FUENTES))
        return 1

    print(f"Descargando {len(fuentes)} fuente(s) a {CRUDO.relative_to(RAIZ)}/\n")
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT) as cliente:
        resultados = [descargar(f, cliente) for f in fuentes]

    ok = sum(resultados)
    print(f"\n{ok}/{len(resultados)} descargas exitosas.")
    return 0 if ok == len(resultados) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
