"""Conversión a dólares de los montos que la fuente publica en moneda local.

Solo el NDB lo necesita hoy: publica 44 de sus 146 operaciones en rand, yuan, rupias, reales y
euros. El resto del corpus viene ya en dólares desde la fuente.

Criterio de conversión: **promedio anual del año de aprobación**, no el tipo de cambio del día.
Son tres razones. La fecha que publica el NDB es la de aprobación del directorio, y el desembolso
puede ocurrir meses después, así que el tipo de cambio de ese día concreto no corresponde a ningún
movimiento real de fondos. El promedio anual es lo que usan los propios informes anuales de los
bancos, que es contra lo que después se contrasta. Y una operación aprobada el 31 de diciembre no
debería quedar valuada de forma sustancialmente distinta a una del 2 de enero siguiente.

La contracara, que hay que decir en el informe: en un año de devaluación fuerte la conversión por
promedio anual puede desviarse bastante del valor del día. Para el rand y el real, que son las
monedas más volátiles del grupo, esa desviación es la principal fuente de error de estas cifras.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
REFERENCIA = RAIZ / "data" / "raw" / "referencia"

# "RMB" es el nombre popular de la moneda china y "CNY" su código ISO. El NDB usa los dos en sus
# fichas, a veces en el mismo año. Son la misma moneda, así que se unifican.
ALIAS = {"RMB": "CNY"}


@lru_cache(maxsize=1)
def serie_tipos_de_cambio() -> dict[tuple[str, int], float]:
    """Unidades de moneda por dólar, por moneda y año, de la descarga fechada más reciente."""
    archivos = sorted(REFERENCIA.glob("tipos_de_cambio_*.csv"))
    if not archivos:
        raise FileNotFoundError(
            "faltan las series de tipo de cambio en data/raw/referencia/. "
            "Se descargan con scripts/descargar_tipos_de_cambio.py"
        )
    with archivos[-1].open(encoding="utf-8") as f:
        return {(r["moneda"], int(r["anio"])): float(r["unidades_por_dolar"]) for r in csv.DictReader(f)}


def normalizar_moneda(moneda: str | None) -> str | None:
    """Lleva el código de moneda a ISO, resolviendo los nombres populares."""
    if not moneda:
        return None
    codigo = moneda.strip().upper()
    return ALIAS.get(codigo, codigo)


def a_dolares(monto: float | None, moneda: str | None, anio: int | None) -> float | None:
    """Convierte un monto en moneda local a dólares del mismo año.

    Devuelve None cuando falta algún insumo o cuando no hay serie para esa moneda y año. Prefiere
    dejar el hueco visible antes que inventar un tipo de cambio: una operación sin convertir se ve
    en el conteo de faltantes, una convertida mal no se ve en ningún lado.
    """
    codigo = normalizar_moneda(moneda)
    if monto is None or codigo is None or anio is None:
        return None
    if codigo == "USD":
        return monto
    try:
        anio_entero = int(anio)
    except (TypeError, ValueError):
        return None
    tasa = serie_tipos_de_cambio().get((codigo, anio_entero))
    return None if tasa is None else monto / tasa
