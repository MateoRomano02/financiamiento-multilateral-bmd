# -*- coding: utf-8 -*-
"""
Descarga el dato crudo de cada institucion desde su fuente oficial.

Como se usa:
  uv run python scripts/descargar_fuentes.py              # todas las fuentes
  uv run python scripts/descargar_fuentes.py caf bid      # solo algunas

Cada descarga va a data/raw/<banco>/ con la fecha en el nombre del archivo, y queda
registrada en el manifest.json de ese directorio con la URL de origen, la fecha ISO, el
tamano y el conteo de registros obtenido.

Ese registro no es burocracia: los conjuntos de los bancos son vivos y su numero de filas
cambia entre descargas, asi que la unica forma de detectar un cambio brusco es comparar
contra el conteo anterior. Por eso el pipeline nunca fija un numero esperado de filas.

Las URLs y el veredicto de oficialidad de cada fuente estan en docs/accesos-a-los-datos.md.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import httpx

RAIZ = Path(__file__).resolve().parent.parent
CRUDO = RAIZ / "data" / "raw"

# Identificarse es parte del acceso respetuoso: si una institucion necesita contactar
# a quien esta consumiendo su servicio, tiene como hacerlo. La direccion se toma del
# entorno para que no quede escrita en el codigo y para que cada quien use la suya.
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
            # Fechas y estado. projectstatusdisplay vuelve vacio siempre: el estado real
            # esta en `status` (Closed / Dropped / Active / Pipeline).
            "boardapprovaldate,closingdate,approvalfy,status,"
            # Montos. curr_ibrd_commitment es el campo que separa la ventanilla BIRF de
            # la de IDA; el nombre `ibrdcommamt` que figura en documentacion no existe en
            # el servicio y volvia vacio en silencio.
            "totalamt,curr_total_commitment,curr_ibrd_commitment,idacommamt,"
            "grantamt,lendprojectcost,"
            # Quien recibe y quien ejecuta: el equipo los necesita y no los teniamos
            "borrower,impagency,"
            # Clasificacion sectorial. El servicio NO expone instrumento de prestamo:
            # lendinginstr, prodline, sector1 y theme1 no existen en v3.
            "mjsector,major_sectors,major_sector_name,sectorcode,"
            # Salvaguardas: esrc_ovrl_risk_rate es la calificacion de riesgo ambiental
            # y social, directamente pertinente al eje de normativa del proyecto
            "esrc_ovrl_risk_rate,envassesmentcategorycode,cons_serv_reqd_ind,"
            "teamleadname"
        ),
        extension="json",
        descripcion=(
            "API de proyectos del Banco Mundial, version 3. Paginada. Se usa v3 y no v2 "
            "porque conviven ambas y v3 es mas completa: 28.081 proyectos contra 22.729, "
            "y 381 de Argentina contra 255."
        ),
    ),
    Fuente(
        clave="ibrd_prestamos",
        institucion="BIRF, estado de prestamos",
        carpeta="gbm",
        url=(
            "https://datacatalogapi.worldbank.org/dexapps/fone/api/apiservice"
            "?datasetId=DS00047&resourceId=RS00005&type=json&top=20000"
        ),
        extension="json",
        descripcion=(
            "IBRD Statement of Loans and Guarantees, ultima foto disponible, via Finances One. Una "
            "fila por prestamo, con monto original, desembolsado, no desembolsado y cancelado. Es la "
            "fuente de los desembolsos del BIRF: el servicio de proyectos no los publica."
        ),
    ),
    Fuente(
        clave="ida_creditos",
        institucion="IDA, estado de creditos",
        carpeta="gbm",
        url=(
            "https://datacatalogapi.worldbank.org/dexapps/fone/api/apiservice"
            "?datasetId=DS00001&resourceId=RS00001&type=json&top=20000"
        ),
        extension="json",
        descripcion=(
            "IDA Statement of Credits, Grants and Guarantees, ultima foto disponible, via Finances "
            "One. Una fila por credito o donacion. Es la fuente de los desembolsos de la IDA."
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
        url="",  # se resuelve en tiempo de ejecucion, ver resolver_iati()
        extension="xml",
        descripcion=(
            "Archivo de actividades IATI de CAF. La URL del recurso cambia con cada "
            "publicacion, por eso se resuelve contra el registro y no se hardcodea."
        ),
    ),
    Fuente(
        clave="fonplata_actividades",
        institucion="FONPLATA",
        carpeta="fonplata",
        url="",  # se resuelve en tiempo de ejecucion, ver resolver_iati()
        extension="xml",
        descripcion=(
            "Archivo de actividades IATI de FONPLATA. 127 operaciones en la version de julio de "
            "2026, todas en dolares."
        ),
    ),
    Fuente(
        clave="bcie_actividades",
        institucion="BCIE",
        carpeta="bcie",
        url="",  # se resuelve en tiempo de ejecucion, ver resolver_iati()
        extension="xml",
        descripcion=(
            "Archivo de actividades IATI del BCIE. El banco lo actualiza sin cambiarle el nombre: "
            "suma operaciones con cada actualizacion."
        ),
    ),
    Fuente(
        clave="iati_sector",
        institucion="IATI, lista de codigos de sector",
        carpeta="referencia",
        url="https://iatistandard.org/reference_downloads/203/codelists/downloads/clv3/json/en/Sector.json",
        extension="json",
        descripcion=(
            "Lista oficial de codigos de sector del CAD de la OCDE, 333 codigos. El BCIE publica el "
            "sector solo como codigo, sin nombre, y esta lista es la que lo traduce."
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
        clave="ndb_informe_anual",
        institucion="NDB",
        carpeta="ndb",
        url="https://www.ndb.int/wp-content/uploads/2026/07/NDB_AnnualReport2025.pdf",
        extension="pdf",
        descripcion=(
            "Informe anual 2025 del NDB. Su anexo 'List of Projects Approved by NDB' (paginas 181 a "
            "189 del PDF) lista las 139 operaciones aprobadas 2016-2025 con el monto aprobado "
            "original y las notas de cancelacion; lo lee src/common/ndb_anexo.py. La URL lleva el "
            "mes de publicacion: si el banco publica el informe 2026, hay que actualizarla."
        ),
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


class ClienteConReintentos(httpx.Client):
    """Reintenta las respuestas 429 y 5xx, que en estas fuentes son pasajeras.

    Un 503 en la pagina 23 de 29 frenaria la actualizacion entera. Un error del servidor que se resuelve solo no deberia obligar
    a volver a descargar todo. Los errores 4xx no se reintentan: dicen que el pedido esta mal.
    """

    ESPERAS = (5, 20, 60)

    def send(self, request, **kwargs):
        for espera in self.ESPERAS:
            respuesta = super().send(request, **kwargs)
            if respuesta.status_code != 429 and respuesta.status_code < 500:
                return respuesta
            print(f"    {respuesta.status_code}, reintento en {espera} s", flush=True)
            respuesta.close()
            time.sleep(espera)
        return super().send(request, **kwargs)


API_CKAN_BID = "https://data.iadb.org/api/3/action/package_show?id=idb-projects-dataset"
REGISTRO_IATI = "https://iatiregistry.org/api/3/action/package_search?fq=organization:{organizacion}&rows=50"

# Organizacion de cada banco en el registro IATI. Cada uno publica dos paquetes, el de actividades
# (las operaciones, que es el que interesa) y el de organizacion (presupuestos institucionales). El
# de actividades es el unico cuyo nombre contiene "act": caf-actfile, fonplata_act_trans y
# bcie-activity.
ORGANIZACION_IATI = {"caf_actividades": "caf", "fonplata_actividades": "fonplata", "bcie_actividades": "bcie"}


def resolver_iati(cliente: httpx.Client, organizacion: str) -> str:
    """Devuelve la URL vigente del archivo de actividades de un banco en el registro IATI.

    La URL cambia con cada publicacion, porque el nombre del archivo lleva la fecha, asi que se
    resuelve contra el registro en lugar de fijarla. Sirve para los tres bancos del corpus que
    publican en el estandar: CAF, FONPLATA y BCIE.
    """
    datos = cliente.get(REGISTRO_IATI.format(organizacion=organizacion)).raise_for_status().json()
    for paquete in datos["result"]["results"]:
        if "act" not in paquete["name"]:
            continue
        for recurso in paquete.get("resources", []):
            if recurso.get("url"):
                return recurso["url"]
    raise RuntimeError(f"no se encontro el archivo de actividades de {organizacion} en el registro IATI")


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


def paginar_ndb(cliente: httpx.Client, url_base: str) -> bytes:
    """Recorre el listado de proyectos del NDB, que sirve doce por pagina.

    El sitio no declara cuantas paginas hay ni cuantos proyectos en total. Se avanza hasta que
    una pagina no trae ninguna tarjeta. Las paginas se concatenan en un solo HTML para que el
    perfilado las lea como un unico documento.
    """
    paginas: list[bytes] = []
    numero = 1
    while True:
        url = url_base if numero == 1 else f"{url_base.rstrip('/')}/page/{numero}/"
        respuesta = cliente.get(url)
        if respuesta.status_code == 404:
            break
        respuesta.raise_for_status()
        contenido = respuesta.content
        tarjetas = contenido.count(b"project-card card")
        if not tarjetas:
            break
        paginas.append(contenido)
        print(f"    pagina {numero}: {tarjetas} proyectos", flush=True)
        numero += 1
        if numero > 60:  # guarda contra un listado que pagine infinito
            print("    corte de seguridad a las 60 paginas", flush=True)
            break
    return b"\n<!-- pagina -->\n".join(paginas)


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
    if ruta.suffix == ".html":
        # El listado del NDB rinde una tarjeta por proyecto.
        return contenido.count(b"project-card card")
    if ruta.suffix == ".js":
        # El buscador del AIIB trae un objeto JSON por proyecto.
        return contenido.count(b'{"date"')
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
        if fuente.clave in ORGANIZACION_IATI or fuente.clave == "bid_proyectos":
            url = (resolver_iati(cliente, ORGANIZACION_IATI[fuente.clave])
                   if fuente.clave in ORGANIZACION_IATI else resolver_bid(cliente))
            fuente = Fuente(**{**fuente.__dict__, "url": url})
            print(f"    resuelto a {url}", flush=True)

        if fuente.clave == "birf-ida_proyectos":
            contenido = json.dumps(
                paginar_worldbank(cliente, fuente.url), ensure_ascii=False
            ).encode("utf-8")
        elif fuente.clave == "ndb_proyectos":
            contenido = paginar_ndb(cliente, fuente.url)
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
    with ClienteConReintentos(headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT) as cliente:
        resultados = [descargar(f, cliente) for f in fuentes]

    ok = sum(resultados)
    print(f"\n{ok}/{len(resultados)} descargas exitosas.")
    return 0 if ok == len(resultados) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
