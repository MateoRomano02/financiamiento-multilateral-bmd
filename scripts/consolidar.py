"""Consolida las fuentes en el corpus armonizado y lo valida.

Lee las descargas fechadas de `data/raw/`, las normaliza al esquema común y escribe el corpus
en `data/processed/`. Es el paso que convierte ocho formatos distintos en una sola tabla sobre
la que se puede comparar entre instituciones.

El corpus se escribe completo, con toda la historia y con las operaciones canceladas incluidas y
marcadas como tales. El criterio acordado de excluir canceladas y el recorte 2014-2025 se aplican
en el análisis, no acá, para que el corpus conserve la traza de lo que la fuente publicaba.

Uso:
    uv run python scripts/consolidar.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from src.common.esquema import ANIO_INICIO  # noqa: E402
from src.common.normalizar import normalizar_todo  # noqa: E402
from src.common.validaciones import validar_todo  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "data" / "processed"
ANIO_FIN = 2025


def periodo_de_analisis(df: pd.DataFrame) -> pd.DataFrame:
    """El recorte sobre el que se analiza: el período del proyecto, sin canceladas."""
    return df[
        df["anio_aprobacion"].between(ANIO_INICIO, ANIO_FIN) & (df["estado"] != "cancelado")
    ].copy()


def main() -> int:
    SALIDA.mkdir(parents=True, exist_ok=True)

    print("Normalizando las fuentes...")
    corpus = normalizar_todo()
    analisis = periodo_de_analisis(corpus)

    corpus.to_csv(SALIDA / "corpus_completo.csv", index=False)
    analisis.to_csv(SALIDA / "corpus_2014_2025.csv", index=False)

    print(f"\nCorpus completo: {len(corpus):,} filas")
    print(f"Período 2014-2025 sin canceladas: {len(analisis):,} filas")
    print(f"Volumen del período: USD {analisis['monto_aprobado_usd'].sum() / 1e9:,.1f} mil millones\n")

    resumen = (
        analisis.groupby(["banco_grupo", "institucion"])
        .agg(
            operaciones=("id_proyecto", "size"),
            con_monto=("monto_aprobado_usd", lambda s: int(s.notna().sum())),
            usd_millones=("monto_aprobado_usd", lambda s: round(s.sum() / 1e6)),
        )
        .reset_index()
    )
    print(resumen.to_string(index=False))

    # Huecos conocidos, documentados en docs/resumen-de-variables.md y en el informe de calidad.
    # No son fallas del pipeline sino limites de la fuente: operaciones cuyo monto la fuente no
    # publica en ninguno de los campos o etiquetas revisados, operaciones sin pais receptor, y
    # sobredesembolsos que la fuente registra por encima del compromiso publicado.
    HUECOS_CONOCIDOS = ("pais: ", "monto_aprobado_usd: ", "sobredesembolso: ")

    print("\nValidaciones sobre el período de análisis:")
    fallas = 0
    for nombre, errores in validar_todo(analisis).items():
        reales = [e for e in errores if not e.startswith(HUECOS_CONOCIDOS)]
        conocidos = [e for e in errores if e.startswith(HUECOS_CONOCIDOS)]
        fallas += len(reales)
        if reales:
            print(f"  {nombre:<24} FALLA: {'; '.join(reales)}")
        elif conocidos:
            print(f"  {nombre:<24} OK, con huecos conocidos: {'; '.join(conocidos)}")
        else:
            print(f"  {nombre:<24} OK")

    sin_monto = analisis[analisis["monto_aprobado_usd"].isna()]
    if not sin_monto.empty:
        print("\n  Operaciones sin monto, por institución (el campo que usa el corpus viene vacío en la fuente):")
        for inst, n in sin_monto["institucion"].value_counts().items():
            print(f"    {inst:<12} {n:>4}")

    print(f"\nEscrito en {SALIDA.relative_to(RAIZ)}/")
    return 0 if fallas == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
