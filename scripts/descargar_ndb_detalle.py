"""Descarga el monto de cada proyecto del NDB desde su ficha individual.

El listado del NDB no publica montos, que era el hueco más serio del corpus: la única
institución sin ninguna cifra. Pero **la ficha de cada proyecto sí los trae**, etiquetados: el
aporte del propio banco bajo "NDB" y el co-financiamiento bajo "Other Sources".

Hay que pedir una página por proyecto, unas 170. El sitio responde en unos cuatro segundos, así
que en serie la descarga lleva doce minutos: se usan seis conexiones en paralelo, que es suficiente
para bajarlo en dos y sigue siendo respetuoso con un sitio público.

Uso:
    uv run python scripts/descargar_ndb_detalle.py
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path

import httpx

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "data" / "raw" / "ndb"
CONTACTO = os.environ.get("CONTACTO", "sin-contacto-declarado")
USER_AGENT = f"proyecto-academico-UNSAM/1.0 (Licenciatura en Ciencia de Datos; contacto: {CONTACTO})"
CONCURRENCIA = 6
TIMEOUT = 25.0


def urls_del_listado() -> list[str]:
    """Las fichas de proyecto que aparecen en el listado ya descargado."""
    listados = sorted(DESTINO.glob("ndb_proyectos_*.html"))
    if not listados:
        raise SystemExit("falta el listado. Correr antes: descargar_fuentes.py ndb_proyectos")
    texto = listados[-1].read_text(encoding="utf-8", errors="replace")
    return list(dict.fromkeys(re.findall(r'class="card-link" href="(https://www\.ndb\.int/project/[^"]+)"', texto)))


def monto_de_la_ficha(pagina: str) -> dict:
    """Extrae los datos etiquetados de una ficha del NDB.

    El sitio usa dos formatos segun el estado del proyecto, y el monto esta en los dos pero con
    etiquetas distintas. Este es el detalle que hacia que un extractor pensado para uno solo
    recuperara apenas 22 de 170 fichas:

    - **Aprobados**: una tabla de aportantes, con el del banco bajo la etiqueta "NDB" y el resto
      bajo "Other Sources...". Es el monto efectivamente aprobado.
    - **Propuestos**: un bloque "Quick Facts" con "Proposed Limit of NDB Financing", que es un
      tope previsto y no un monto aprobado.

    Los dos se devuelven en campos separados, porque no significan lo mismo y mezclarlos inflaria
    la cartera con operaciones que todavia no se aprobaron.

    **Las etiquetas estan enumeradas, no adivinadas.** Se recorrieron las 170 fichas listando toda
    etiqueta que precede a un monto, en lugar de buscar la que esperabamos encontrar. El NDB usa
    tres para el aporte del banco y significan cosas distintas:

    - "Current Limit of NDB Financing": 126 fichas. Limite vigente, ya aprobado.
    - "Proposed Limit of NDB Financing": 31 fichas. Todavia no aprobado.
    - "Initial Limit of NDB Financing": 1 ficha. Aprobado originalmente, sin revisar.

    Ninguna ficha trae dos de las tres a la vez, verificado sobre las 170, asi que no hay que
    decidir cual gana. Si en una descarga futura aparecieran juntas, **manda la vigente**: es la
    que refleja el compromiso de hoy.

    **El costo total del proyecto no es un campo.** Sirve para calcular que proporcion de cada
    proyecto pone el banco. Aparece en apenas 37 de
    las 170 fichas y siempre dentro de una frase, no como dato etiquetado. Se captura donde esta y
    se declara la cobertura, porque con el 22% no se puede construir una serie.
    """
    limpio = re.sub(r"<script.*?</script>|<style.*?</style>", "", pagina, flags=re.S)
    plano = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", limpio)))

    resultado: dict[str, str] = {}
    monto = r"((?:USD|EUR|CNY|RMB|ZAR|INR|BRL|RUB|CHF)\s?[\d.,]+(?:\s?(?:million|billion))?)"
    etiquetas = {
        "monto_propuesto": rf"Proposed Limit of NDB Financing\s*{monto}",
        # En prosa, no como campo. Solo 37 de 170 fichas lo traen.
        "costo_total": rf"(?:total cost of the Project is estimated at|Project is estimated to be|Total Project Cost)\s*{monto}",
        # La ficha nombra el monto vigente de varias formas: "NDB Financing", "Current limit of
        # financing", "Current Limit of NDB Financing Amount", "Current Limit of NDB Borrowing". Se
        # reconocen todas para no dejar operaciones sin monto.
        "monto_aprobado": (rf"(?:(?<!Proposed )(?:Current |Initial )?Limit of (?:NDB )?(?:Financing|Borrowing)"
                           rf"(?: Amount)?|(?<!Limit of )NDB Financing)\s*:?\s*{monto}"),
        # El estado que declara la ficha. El listado no lo trae, y es la única forma de saber que una
        # operación se canceló.
        "estado_ficha": r"Status\s+([A-Za-z ]+?)\s+Area Of Operation",
        "fecha_aprobacion": r"(?<!Concept )Approval Date\s*(\d{1,2} [A-Za-z]+ \d{4})",
        "fecha_concepto": r"Concept Approval Date\s*(\d{1,2} [A-Za-z]+ \d{4})",
    }
    for campo, patron in etiquetas.items():
        m = re.search(patron, plano, re.I)
        if m:
            resultado[campo] = m.group(1).strip()

    # Formato de los aprobados: tabla de aportantes. El del banco es el monto aprobado real.
    for bloque in re.findall(r"<(?:div|li|tr|p)[^>]*>(.*?)</(?:div|li|tr|p)>", limpio, re.S):
        campos = [c.strip() for c in html.unescape(re.sub(r"<[^>]+>", "|", bloque)).split("|") if c.strip()]
        if len(campos) == 2 and re.fullmatch(monto, campos[1].strip(), re.I):
            if campos[0].strip().lower() == "ndb":
                resultado["monto_ndb"] = campos[1].strip()
            elif "other sources" in campos[0].lower():
                resultado["monto_otras_fuentes"] = campos[1].strip()
            elif campos[0].strip().lower() in ("total", "total project cost"):
                resultado.setdefault("costo_total", campos[1].strip())
    return resultado


def main() -> int:
    urls = urls_del_listado()
    print(f"{len(urls)} fichas a descargar, con {CONCURRENCIA} conexiones en paralelo\n", flush=True)

    limites = httpx.Limits(max_connections=CONCURRENCIA, max_keepalive_connections=CONCURRENCIA)
    hechas = 0

    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT,
                      follow_redirects=True, limits=limites) as cliente:

        def una(url: str) -> dict:
            nonlocal hechas
            try:
                pagina = cliente.get(url).raise_for_status().text
                fila = {"url": url, **monto_de_la_ficha(pagina)}
            except Exception as error:  # noqa: BLE001 - se reporta y se sigue con las demas
                fila = {"url": url, "error": f"{type(error).__name__}: {error}"}
            hechas += 1
            if hechas % 25 == 0 or hechas == len(urls):
                print(f"  {hechas}/{len(urls)}", flush=True)
            return fila

        with ThreadPoolExecutor(max_workers=CONCURRENCIA) as pool:
            filas = list(pool.map(una, urls))

    fallidas = sum(1 for f in filas if f.get("error"))
    con_monto = sum(1 for f in filas if f.get("monto_ndb") or f.get("monto_propuesto") or f.get("monto_aprobado"))
    ruta = DESTINO / f"ndb_montos_{date.today():%Y-%m-%d}.json"
    ruta.write_text(json.dumps(filas, ensure_ascii=False, indent=1), encoding="utf-8")

    manifiesto = DESTINO / "manifest.json"
    m = json.loads(manifiesto.read_text(encoding="utf-8"))
    m["descargas"].append({
        "archivo": ruta.name,
        "institucion": "NDB",
        "url_origen": "https://www.ndb.int/project/<proyecto>/",
        "fecha_descarga": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bytes": ruta.stat().st_size,
        "registros": con_monto,
        "descripcion": "Monto por proyecto, leido de la ficha individual. El listado no lo publica.",
        "version_endpoint": None,
    })
    manifiesto.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n  con monto: {con_monto}/{len(urls)}   fallidas: {fallidas}")
    print(f"  escrito en {ruta.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
