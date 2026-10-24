"""Conversión de dólares corrientes a dólares constantes.

Se usa el deflactor implícito del PBI
de Estados Unidos, serie A191RD3A086NBEA del Bureau of Economic Analysis publicada en FRED, con
**año base 2025**.

Por qué importa: el período de análisis abarca doce años, y una serie en dólares corrientes mezcla
crecimiento real con inflación. Un dólar de 2014 equivale a 1,34 dólares de 2025, así que comparar
2014 contra 2025 sin deflactar subestima el pasado en un tercio.

Dos advertencias que el pipeline no puede resolver solo:

- La deflactación solo es válida sobre operaciones **originalmente denominadas en dólares**. Una
  operación en moneda local ya convertida a dólares por la fuente arrastra el tipo de cambio de su
  fecha, y deflactarla mezcla dos efectos distintos.
- El NDB presta buena parte de su cartera en moneda local. Ahí hay que convertir a dólares antes
  de deflactar, y esa conversión todavía no está hecha.

Por eso el corpus conserva siempre la columna en dólares corrientes y agrega la constante al lado,
en lugar de reemplazarla.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
REFERENCIA = RAIZ / "data" / "raw" / "referencia"
ANIO_BASE = 2025


@lru_cache(maxsize=1)
def serie_deflactor() -> dict[int, float]:
    """El deflactor por año, leído de la descarga fechada más reciente."""
    archivos = sorted(REFERENCIA.glob("deflactor_pbi_eeuu_*.csv"))
    if not archivos:
        raise FileNotFoundError(
            "falta la serie del deflactor en data/raw/referencia/. "
            "Se descarga de https://fred.stlouisfed.org/graph/fredgraph.csv?id=A191RD3A086NBEA"
        )
    with archivos[-1].open(encoding="utf-8") as f:
        filas = list(csv.reader(f))
    return {int(r[0][:4]): float(r[1]) for r in filas[1:] if r[1] not in ("", ".")}


def factor(anio: int) -> float | None:
    """Cuánto hay que multiplicar un dólar de `anio` para expresarlo en dólares del año base."""
    serie = serie_deflactor()
    if anio not in serie or ANIO_BASE not in serie:
        return None
    return serie[ANIO_BASE] / serie[anio]


def a_constantes(monto: float | None, anio: int | None) -> float | None:
    """Convierte un monto en dólares corrientes del año dado a dólares del año base.

    Devuelve None cuando falta el monto, falta el año o el año cae fuera de la serie. Varias
    operaciones del corpus no traen fecha de aprobación y no se pueden deflactar: es preferible
    que queden nulas y se vean, a inventarles un año.
    """
    if monto is None or anio is None:
        return None
    try:
        anio_entero = int(anio)
    except (TypeError, ValueError):  # NaN de pandas en las filas sin fecha
        return None
    f = factor(anio_entero)
    return None if f is None else monto * f
