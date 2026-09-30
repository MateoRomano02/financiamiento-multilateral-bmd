"""Genera el diccionario de variables del esquema común, con su cobertura por institución.

El plan de trabajo compromete un diccionario de variables del corpus consolidado. No se escribe a
mano: las definiciones viven en `src/common/esquema.py` y la cobertura se mide sobre el corpus, así
que el documento no puede quedar desactualizado respecto del código. Si una definición cambia, se
cambia en el esquema y se vuelve a correr esto.

Es distinto del resumen de variables por fuente (`scripts/perfilar_fuentes.py`), que describe los
campos crudos que publica cada banco antes de normalizar.

Uso:
    uv run python scripts/diccionario_variables.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from src.common.esquema import COLUMNAS_OBLIGATORIAS, VARIABLES  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
CORPUS = RAIZ / "data" / "processed" / "corpus_2014_2025.csv"
SALIDA = RAIZ / "docs" / "diccionario-de-variables.md"


def tipo(serie: pd.Series, nombre: str) -> str:
    if nombre.startswith("fecha_"):
        return "fecha"
    if nombre == "anio_aprobacion":
        return "entero"
    if pd.api.types.is_numeric_dtype(serie):
        return "número"
    return "texto"


def main() -> int:
    if not CORPUS.exists():
        raise SystemExit("falta el corpus. Correr antes: uv run python scripts/consolidar.py")
    df = pd.read_csv(CORPUS, low_memory=False)
    instituciones = sorted(df["institucion"].dropna().unique())

    lineas = [
        "# Diccionario de variables del corpus consolidado",
        "",
        f"Generado por `scripts/diccionario_variables.py` el {date.today().isoformat()}, a partir de "
        "las definiciones de `src/common/esquema.py` y del corpus del período 2014 a 2025. No se "
        "edita a mano: si una definición cambia, se cambia en el esquema y se regenera.",
        "",
        f"El corpus tiene {len(df):,} operaciones de {len(instituciones)} ventanillas y "
        f"{len(VARIABLES)} variables.".replace(",", "."),
        "",
    ]

    grupo_actual = None
    for nombre, (grupo, definicion) in VARIABLES.items():
        if grupo != grupo_actual:
            lineas += [f"## {grupo}", "", "| Variable | Definición | Tipo | Obligatoria |", "|---|---|---|---|"]
            grupo_actual = grupo
        oblig = "sí" if nombre in COLUMNAS_OBLIGATORIAS else "no"
        lineas.append(f"| `{nombre}` | {definicion} | {tipo(df[nombre], nombre)} | {oblig} |")
        siguiente = list(VARIABLES).index(nombre) + 1
        if siguiente == len(VARIABLES) or VARIABLES[list(VARIABLES)[siguiente]][0] != grupo:
            lineas.append("")

    # Cobertura: solo las variables que no están completas en todas las ventanillas, que son las
    # que dicen algo. Una variable al 100% en todas no necesita tabla.
    cobertura = df.groupby("institucion")[list(VARIABLES)].agg(lambda s: s.notna().mean() * 100)
    incompletas = [v for v in VARIABLES if (cobertura[v] < 99.95).any() and cobertura[v].max() > 0]
    vacias = [v for v in VARIABLES if cobertura[v].max() == 0]

    lineas += [
        "## Cobertura por ventanilla",
        "",
        "Porcentaje de operaciones con la variable informada. Solo se listan las variables que no "
        "están completas en todas las ventanillas.",
        "",
        "| Variable | " + " | ".join(instituciones) + " |",
        "|---|" + "---|" * len(instituciones),
    ]
    for v in incompletas:
        celdas = [f"{cobertura.loc[i, v]:.0f}%" for i in instituciones]
        lineas.append(f"| `{v}` | " + " | ".join(celdas) + " |")
    lineas.append("")
    if vacias:
        lineas += [
            "Vacías en todas las ventanillas: " + ", ".join(f"`{v}`" for v in vacias) + ".",
            "",
        ]

    SALIDA.write_text("\n".join(lineas), encoding="utf-8")
    print(f"Escrito {SALIDA.relative_to(RAIZ)}: {len(VARIABLES)} variables, "
          f"{len(incompletas)} con cobertura parcial, {len(vacias)} vacías")
    return 0


if __name__ == "__main__":
    sys.exit(main())
