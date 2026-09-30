"""Descarga de FRED las series de referencia del corpus: tipos de cambio y deflactor.

Son dos usos de la misma fuente. Los tipos de cambio convierten a dólares los montos publicados
en moneda local, y el deflactor implícito del PBI de Estados Unidos (serie A191RD3A086NBEA)
expresa la serie en dólares constantes. Hasta el 29 de septiembre de 2026 el deflactor se había
bajado a mano y ningún programa lo volvía a traer, así que el corpus no era reproducible de punta
a punta. Ahora se baja acá.

Por qué existe. El NDB publica 44 de sus 146 operaciones con monto en moneda local: rand, yuan,
rupias, reales y euros. Contarlas como dólares multiplicaba su cartera por cinco. La dirección del
proyecto lo advirtió el 17 de septiembre de 2026, antes de ver el dato: "NDB presta mucho en moneda
local, ahí habrá que primero convertir a USD".

Las series salen de FRED, la misma fuente que el deflactor, para que todo el tratamiento de valor
del corpus venga de un solo lugar citable. Se baja la serie diaria completa y el promedio anual se
calcula acá, en lugar de pedirle a FRED que agregue: el parámetro de agregación de su exportador no
está documentado y no conviene apoyar una cifra del informe en un comportamiento que puede cambiar
sin aviso.

Uso:
    uv run python scripts/descargar_tipos_de_cambio.py
"""

from __future__ import annotations

import csv
import io
from datetime import date
from pathlib import Path

import httpx

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "data" / "raw" / "referencia"
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={serie}"
SERIE_DEFLACTOR = "A191RD3A086NBEA"

# Cada moneda con la serie de FRED que le corresponde. `invertida` marca las que FRED publica como
# dólares por unidad de moneda en lugar de unidades de moneda por dólar, que es el caso del euro.
SERIES = {
    "CNY": {"serie": "DEXCHUS", "invertida": False, "nombre": "yuan chino"},
    "ZAR": {"serie": "DEXSFUS", "invertida": False, "nombre": "rand sudafricano"},
    "INR": {"serie": "DEXINUS", "invertida": False, "nombre": "rupia india"},
    "BRL": {"serie": "DEXBZUS", "invertida": False, "nombre": "real brasileño"},
    "EUR": {"serie": "DEXUSEU", "invertida": True, "nombre": "euro"},
}


def promedios_anuales(csv_crudo: str, invertida: bool) -> dict[int, float]:
    """Promedio anual de la serie diaria, expresado siempre en unidades de moneda por dólar.

    FRED marca los feriados con un punto. Esas filas se saltean en lugar de contarlas como cero,
    que sería un tipo de cambio inventado.
    """
    por_anio: dict[int, list[float]] = {}
    for fila in list(csv.reader(io.StringIO(csv_crudo)))[1:]:
        if len(fila) < 2 or fila[1] in ("", "."):
            continue
        valor = float(fila[1])
        if invertida:
            valor = 1 / valor
        por_anio.setdefault(int(fila[0][:4]), []).append(valor)
    return {anio: sum(v) / len(v) for anio, v in por_anio.items()}


def main() -> int:
    DESTINO.mkdir(parents=True, exist_ok=True)
    hoy = date.today().isoformat()
    filas = []

    for moneda, cfg in SERIES.items():
        respuesta = httpx.get(FRED.format(serie=cfg["serie"]), timeout=60, follow_redirects=True)
        respuesta.raise_for_status()
        promedios = promedios_anuales(respuesta.text, cfg["invertida"])
        for anio, valor in sorted(promedios.items()):
            filas.append([moneda, anio, f"{valor:.6f}", cfg["serie"]])
        ultimo = max(promedios)
        print(f"{moneda} ({cfg['nombre']}): {len(promedios)} años, {ultimo} = {promedios[ultimo]:.4f} por dólar")

    # El deflactor se guarda crudo, tal como lo publica FRED: src/common/deflactor.py lo lee así.
    respuesta = httpx.get(FRED.format(serie=SERIE_DEFLACTOR), timeout=60, follow_redirects=True)
    respuesta.raise_for_status()
    deflactor = DESTINO / f"deflactor_pbi_eeuu_{hoy}.csv"
    deflactor.write_text(respuesta.text, encoding="utf-8")
    print(f"Deflactor {SERIE_DEFLACTOR}: {len(respuesta.text.splitlines()) - 1} años, escrito {deflactor.relative_to(RAIZ)}")

    salida = DESTINO / f"tipos_de_cambio_{hoy}.csv"
    with salida.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["moneda", "anio", "unidades_por_dolar", "serie_fred"])
        w.writerows(filas)
    print(f"\nEscrito {salida.relative_to(RAIZ)} con {len(filas)} filas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
