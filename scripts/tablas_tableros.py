"""Tablas agregadas que alimentan los tableros, sin depender de la herramienta que se elija.

El plan de trabajo compromete tableros por grupo bancario y un tablero integrado. La herramienta
todavía no está definida: depende de quién los va a usar y quién los mantiene después. Lo que sí se puede hacer sin esa
decisión es preparar los datos, porque cualquier herramienta va a necesitar las mismas tablas.

Todas van en formato largo, una fila por combinación y todos los grupos en el mismo archivo con una
columna que los distingue. Es el formato que leen sin transformar Looker Studio, Power BI, Tableau,
una planilla o un tablero en Python, y el que permite filtrar por grupo en lugar de mantener un
archivo por banco.

No se recalcula nada acá: se reusan las funciones de `analisis_preliminar.py`, así que una cifra
del tablero y la misma cifra del informe salen del mismo código.

Uso:
    uv run python scripts/tablas_tableros.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from scripts.analisis_preliminar import (  # noqa: E402
    PROCESADO,
    cargar,
    complemento_caf,
    composicion,
    concentracion,
    moneda_local,
    region_de,
    ventanillas,
)

DESTINO = PROCESADO / "tableros"


def serie_anual(df: pd.DataFrame) -> pd.DataFrame:
    """Operaciones y monto aprobado por institución y año, en corrientes y en constantes."""
    d = df[df["anio_aprobacion"].notna()]
    return (
        d.groupby(["banco_grupo", "institucion", "tipo_ventanilla", "anio_aprobacion"], dropna=False)
        .agg(operaciones=("id_proyecto", "size"),
             usd_corrientes_mm=("monto_aprobado_usd", lambda s: round(s.sum() / 1e6, 1)),
             usd_constantes_mm=("monto_constante_usd", lambda s: round(s.sum() / 1e6, 1)),
             usd_desembolsado_mm=("monto_desembolsado_usd", lambda s: round(s.sum() / 1e6, 1)))
        .reset_index()
        .astype({"anio_aprobacion": int})
    )


def por_pais(df: pd.DataFrame) -> pd.DataFrame:
    """Monto por institución y país receptor en el período, con la región del mapeo propio."""
    d = df[df["monto_aprobado_usd"].notna()].copy()
    d["region"] = d["pais"].apply(region_de)
    return (
        d.groupby(["banco_grupo", "institucion", "pais", "region"], dropna=False)
        .agg(operaciones=("id_proyecto", "size"),
             usd_corrientes_mm=("monto_aprobado_usd", lambda s: round(s.sum() / 1e6, 1)))
        .reset_index()
        .sort_values(["institucion", "usd_corrientes_mm"], ascending=[True, False])
    )


def indicadores(df: pd.DataFrame) -> pd.DataFrame:
    """Una fila por institución con los indicadores de resumen, para las tarjetas del tablero."""
    base = df.groupby(["banco_grupo", "institucion"]).agg(
        operaciones=("id_proyecto", "size"),
        usd_corrientes_mm=("monto_aprobado_usd", lambda s: round(s.sum() / 1e6)),
        usd_constantes_mm=("monto_constante_usd", lambda s: round(s.sum() / 1e6)),
    ).reset_index()
    conc = concentracion(df)[["institucion", "paises", "pct_top5", "pct_regional"]]
    loc = moneda_local(df)[["institucion", "pct_ops"]].rename(columns={"pct_ops": "pct_moneda_local"})
    return base.merge(conc, on="institucion", how="left").merge(loc, on="institucion", how="left")


def main() -> int:
    df = cargar()
    DESTINO.mkdir(parents=True, exist_ok=True)
    tablas = {
        "serie_anual.csv": serie_anual(df),
        "ventanillas.csv": ventanillas(df),
        "por_pais.csv": por_pais(df),
        "por_sector.csv": composicion(df),
        "indicadores.csv": indicadores(df),
        "complemento_caf.csv": complemento_caf(df),
    }
    for nombre, tabla in tablas.items():
        tabla.to_csv(DESTINO / nombre, index=False)
        print(f"  {nombre:18s} {len(tabla):6,} filas, {len(tabla.columns)} columnas")
    print(f"Escritas en {DESTINO.relative_to(PROCESADO.parent.parent)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
