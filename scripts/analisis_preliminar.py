"""Los cuatro análisis preliminares sobre el corpus consolidado.

Produce las tablas del primer informe de resultados. Cada análisis responde a algo concreto que
alguien pidió o que la bibliografía del proyecto usa como vocabulario común:

1. **Ventanillas soberanas contra no soberanas.** Desde 2014 las ventanillas que prestan al sector privado deberían haber
   crecido frente a las soberanas, porque el paradigma vigente empuja el financiamiento privado.

2. **Concentración de los primeros cinco países.** Es la métrica que usan tres de los cinco textos
   de la bibliografía sin explicarla, porque la dan por conocida. Mide qué porción de la cartera
   de cada institución se lleva su primer decil de receptores.

3. **Composición de cartera por institución y año.** Es el insumo que el equipo que lee las
   memorias anuales necesita para contrastar lo que cada banco declara contra lo que aprobó.

4. **Velocidad de aprobación a firma.** Un proxy medible del costo no financiero de tomarle
   prestado a cada banco. Se calcula sobre las fuentes que publican las dos fechas.

Uso:
    uv run python scripts/analisis_preliminar.py            # tablas a pantalla
    uv run python scripts/analisis_preliminar.py --markdown # en markdown, para el informe
    uv run python scripts/analisis_preliminar.py --csv      # composición por banco, para el equipo
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
PROCESADO = RAIZ / "data" / "processed"
COMPOSICION = PROCESADO / "composicion-por-banco"

# Las ventanillas que prestan al sector privado dentro de cada grupo, y su par soberano.
# La comparación solo tiene sentido dentro del mismo grupo bancario: comparar la IFC contra el
# BID mezclaría el efecto del paradigma con el del tamaño de cada institución.
PARES = {
    "Grupo Banco Mundial": {"soberana": ["BIRF", "IDA"], "no_soberana": ["IFC", "MIGA"]},
    "Grupo BID": {"soberana": ["BID"], "no_soberana": ["BID Invest", "BID Lab"]},
}


def a_markdown(tabla: pd.DataFrame) -> str:
    """Tabla en markdown sin depender de `tabulate`, que no vale una dependencia extra."""
    cols = list(tabla.columns)
    filas = [[("" if pd.isna(v) else str(v)) for v in fila] for fila in tabla.itertuples(index=False)]
    return "\n".join(
        ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
        + ["| " + " | ".join(f) + " |" for f in filas]
    )


def cargar() -> pd.DataFrame:
    ruta = PROCESADO / "corpus_2014_2025.csv"
    if not ruta.exists():
        raise SystemExit("falta el corpus. Correr antes: uv run python scripts/consolidar.py")
    return pd.read_csv(ruta)


# ---------------------------------------------------------------------------
# 1. Ventanillas
# ---------------------------------------------------------------------------


def ventanillas(df: pd.DataFrame) -> pd.DataFrame:
    """Participación anual de la ventanilla no soberana sobre el total de cada grupo."""
    filas = []
    for grupo, lados in PARES.items():
        todas = lados["soberana"] + lados["no_soberana"]
        sub = df[df["institucion"].isin(todas) & df["monto_aprobado_usd"].notna()]
        for anio, tramo in sub.groupby("anio_aprobacion"):
            sob = tramo[tramo["institucion"].isin(lados["soberana"])]["monto_aprobado_usd"].sum()
            nos = tramo[tramo["institucion"].isin(lados["no_soberana"])]["monto_aprobado_usd"].sum()
            total = sob + nos
            if not total:
                continue
            filas.append(
                {
                    "grupo": grupo,
                    "anio": int(anio),
                    "soberana_mm": round(sob / 1e6),
                    "no_soberana_mm": round(nos / 1e6),
                    "pct_no_soberana": round(100 * nos / total, 1),
                }
            )
    return pd.DataFrame(filas)


# ---------------------------------------------------------------------------
# 2. Concentración
# ---------------------------------------------------------------------------


# Etiquetas que no son un país receptor sino un agregado regional o global. Son 23 en el
# corpus y se llevan el 5% del monto. Se detectan por palabra completa, de modo que
# "South Africa", "Central African Republic" y "Dominican Republic" no caen por error.
RE_AGREGADO = re.compile(
    r"\b(Region|Regional|Regions|World|Multicountry|Multi-country|Multi-Regional|Subregion|Global)\b",
    re.I,
)


def es_pais_real(valor: object) -> bool:
    return bool(valor) and not RE_AGREGADO.search(str(valor))


def concentracion(df: pd.DataFrame, top: int = 5) -> pd.DataFrame:
    """Porción de la cartera de cada institución que se llevan sus `top` países receptores.

    Se excluyen las operaciones sin país y las asignadas a un agregado regional, porque no
    tienen un receptor único: contarlas mezclaría "se lo lleva Brasil" con "se lo lleva una
    facilidad para toda la región", que es exactamente lo contrario de concentración.
    """
    sub = df[df["monto_aprobado_usd"].notna() & df["pais"].apply(es_pais_real)]
    filas = []
    for institucion, tramo in sub.groupby("institucion"):
        por_pais = tramo.groupby("pais")["monto_aprobado_usd"].sum().sort_values(ascending=False)
        total = por_pais.sum()
        if not total:
            continue
        del_banco = df[df["institucion"] == institucion]
        regional = del_banco[~del_banco["pais"].apply(es_pais_real)]["monto_aprobado_usd"].sum()
        filas.append(
            {
                "institucion": institucion,
                "paises": len(por_pais),
                "pct_top5": round(100 * por_pais.head(top).sum() / total, 1),
                "pct_regional": round(100 * regional / (total + regional), 1) if total + regional else 0.0,
                "principales": ", ".join(por_pais.head(3).index.astype(str)),
            }
        )
    return pd.DataFrame(filas).sort_values("pct_top5", ascending=False)


# ---------------------------------------------------------------------------
# 3. Composición de cartera
# ---------------------------------------------------------------------------


def composicion(df: pd.DataFrame) -> pd.DataFrame:
    """Operaciones y monto por institución, año y sector, tal como lo clasifica cada banco."""
    sub = df[df["sector"].notna()]
    tabla = (
        sub.groupby(["institucion", "anio_aprobacion", "sector"])
        .agg(operaciones=("id_proyecto", "size"), usd_millones=("monto_aprobado_usd", "sum"))
        .reset_index()
    )
    tabla["usd_millones"] = (tabla["usd_millones"] / 1e6).round(1)
    tabla["anio_aprobacion"] = tabla["anio_aprobacion"].astype(int)
    return tabla.sort_values(["institucion", "anio_aprobacion", "usd_millones"], ascending=[True, True, False])


# ---------------------------------------------------------------------------
# 4. Velocidad
# ---------------------------------------------------------------------------


def velocidad() -> pd.DataFrame:
    """Días entre la aprobación y la firma, por institución.

    Se lee del crudo y no del corpus porque la fecha de firma no entra al esquema común: no la
    publican todas las fuentes y no es parte de la unidad de análisis. Es un proxy del costo no
    financiero de operar con cada banco, no la medida completa, que incluiría la preparación
    previa a la aprobación y esa no la publica ninguna.
    """
    import csv
    import json
    import xml.etree.ElementTree as ET
    from datetime import datetime

    from src.common.normalizar import CRUDO, ultima_descarga

    def dias(a: str, b: str, formato: str) -> int | None:
        """Dias entre dos fechas, o None si alguna no se puede interpretar.

        Se corta por la 'T' de la marca horaria y no por longitud fija: '13-Jul-2000' tiene
        once caracteres y un truncado a diez lo convertia en '13-Jul-200', que no parsea.
        """
        try:
            n = (
                datetime.strptime(str(b).split("T")[0].strip(), formato)
                - datetime.strptime(str(a).split("T")[0].strip(), formato)
            ).days
        except Exception:
            return None
        return n if 0 < n < 3000 else None

    medidas: dict[str, list[int]] = {}

    ifc = json.loads(ultima_descarga("gbm/ifc_inversiones_*.json").read_text(encoding="utf-8"))["data"]
    medidas["IFC"] = [d for d in (dias(str(r.get("ifc_approval_date", "")), str(r.get("ifc_signed_date", "")), "%d-%b-%Y") for r in ifc) if d]

    raiz = ET.parse(ultima_descarga("gbid/bid-invest_proyectos_*.xml")).getroot()
    bi = [{h.tag: (h.text or "").strip() for h in it} for it in raiz]
    medidas["BID Invest"] = [d for d in (dias(r.get("approval_date", ""), r.get("signed_date", ""), "%Y-%m-%d") for r in bi) if d]

    with ultima_descarga("gbid/bid_proyectos_*.csv").open(encoding="utf-8-sig") as f:
        bid = list(csv.DictReader(f))
    medidas["BID"] = [d for d in (dias(r.get("apprvl_dt", ""), r.get("sign_dt", ""), "%Y-%m-%d") for r in bid) if d]

    return pd.DataFrame(
        [
            {
                "institucion": k,
                "operaciones": len(v),
                "mediana_dias": int(pd.Series(v).median()),
                "media_dias": int(pd.Series(v).mean()),
            }
            for k, v in medidas.items()
            if v
        ]
    ).sort_values("mediana_dias")


# ---------------------------------------------------------------------------


def main() -> int:
    md = "--markdown" in sys.argv
    df = cargar()

    def imprimir(titulo: str, tabla: pd.DataFrame) -> None:
        print(f"\n## {titulo}\n" if md else f"\n=== {titulo} ===")
        print(a_markdown(tabla) if md else tabla.to_string(index=False))

    print(f"Corpus: {len(df):,} operaciones, 2014 a 2025, sin canceladas.")

    imprimir("Ventanilla no soberana sobre el total de cada grupo", ventanillas(df))
    imprimir("Concentración de los primeros cinco países receptores", concentracion(df))
    imprimir("Velocidad: días entre aprobación y firma", velocidad())

    comp = composicion(df)
    imprimir("Composición de cartera (muestra)", comp.head(15))

    if "--csv" in sys.argv:
        COMPOSICION.mkdir(parents=True, exist_ok=True)
        for institucion, tramo in comp.groupby("institucion"):
            nombre = str(institucion).lower().replace(" ", "-")
            tramo.to_csv(COMPOSICION / f"{nombre}.csv", index=False)
        print(f"\nComposición por banco escrita en {COMPOSICION.relative_to(RAIZ)}/")

    return 0


if __name__ == "__main__":
    sys.exit(main())
