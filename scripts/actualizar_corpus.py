"""Actualiza el corpus de punta a punta con un solo comando.

El plan de trabajo compromete dejar automatizado el procedimiento de actualización, para que el
corpus se pueda volver a construir cuando los bancos publiquen datos nuevos sin que nadie tenga que
acordarse del orden de los pasos. Hasta el 29 de septiembre de 2026 eran seis programas que había
que correr a mano y en el orden correcto, y uno de los insumos, el deflactor, ni siquiera tenía
programa.

Cada paso es uno de los scripts que ya existen: este archivo solo los encadena. Frena en el primer
error, porque un corpus armado con un paso roto se ve bien y está mal. Al final compara contra la
corrida anterior, institución por institución, que es la forma de notar si una fuente cambió algo
sin avisar.

Uso:
    export CONTACTO="tu.correo@institucion.edu"
    uv run python scripts/actualizar_corpus.py               # descarga y reprocesa todo
    uv run python scripts/actualizar_corpus.py --sin-descarga # reprocesa lo ya descargado
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
CORPUS = RAIZ / "data" / "processed" / "corpus_2014_2025.csv"
REGISTRO = RAIZ / "data" / "processed" / "ultima_actualizacion.json"

DESCARGAS = [
    ("Fuentes de los bancos", ["scripts/descargar_fuentes.py"]),
    ("Fichas individuales del NDB", ["scripts/descargar_ndb_detalle.py"]),
    ("Tipos de cambio y deflactor", ["scripts/descargar_tipos_de_cambio.py"]),
]
PROCESO = [
    ("Normalización y consolidación", ["scripts/consolidar.py"]),
    ("Análisis y tablas", ["scripts/analisis_preliminar.py", "--csv"]),
    ("Diccionario de variables", ["scripts/diccionario_variables.py"]),
    ("Tablas para los tableros", ["scripts/tablas_tableros.py"]),
    ("Explorador del corpus", ["scripts/explorador_corpus.py"]),
]


def resumen_corpus() -> dict[str, dict[str, float]]:
    """Operaciones y monto por institución, para comparar una corrida contra la anterior."""
    if not CORPUS.exists():
        return {}
    df = pd.read_csv(CORPUS, low_memory=False)
    grupos = df.groupby("institucion")
    return {
        inst: {"operaciones": int(len(g)), "usd_millones": round(g["monto_aprobado_usd"].sum() / 1e6)}
        for inst, g in grupos
    }


def correr(nombre: str, argumentos: list[str]) -> tuple[bool, float]:
    print(f"\n=== {nombre} ===", flush=True)
    inicio = time.monotonic()
    resultado = subprocess.run(["uv", "run", "python", *argumentos], cwd=RAIZ)
    return resultado.returncode == 0, round(time.monotonic() - inicio, 1)


def comparar(antes: dict, despues: dict) -> list[str]:
    lineas = []
    for inst in sorted(set(antes) | set(despues)):
        a, d = antes.get(inst), despues.get(inst)
        if a is None:
            lineas.append(f"  {inst:12s} nueva: {d['operaciones']:,} operaciones, USD {d['usd_millones']:,} M")
        elif d is None:
            lineas.append(f"  {inst:12s} DESAPARECIÓ del corpus")
        elif a != d:
            lineas.append(
                f"  {inst:12s} {a['operaciones']:,} a {d['operaciones']:,} operaciones, "
                f"USD {a['usd_millones']:,} a {d['usd_millones']:,} M"
            )
    return lineas or ["  sin cambios respecto de la corrida anterior"]


def main() -> int:
    sin_descarga = "--sin-descarga" in sys.argv
    pasos = PROCESO if sin_descarga else DESCARGAS + PROCESO
    antes = resumen_corpus()
    registro = {"inicio": datetime.now().isoformat(timespec="seconds"), "pasos": []}

    for nombre, argumentos in pasos:
        ok, segundos = correr(nombre, argumentos)
        registro["pasos"].append({"paso": nombre, "ok": ok, "segundos": segundos})
        if not ok:
            print(f"\nFALLÓ: {nombre}. Se frena acá para no armar un corpus con un paso roto.")
            registro["resultado"] = f"falló en {nombre}"
            REGISTRO.write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
            return 1

    despues = resumen_corpus()
    cambios = comparar(antes, despues)
    registro.update(resultado="ok", fin=datetime.now().isoformat(timespec="seconds"), cambios=cambios)
    REGISTRO.write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== Cambios respecto de la corrida anterior ===")
    print("\n".join(cambios))
    print(f"\nListo en {sum(p['segundos'] for p in registro['pasos']):.0f} segundos. "
          f"Registro en {REGISTRO.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
