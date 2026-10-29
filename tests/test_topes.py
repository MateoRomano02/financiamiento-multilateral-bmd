"""Los topes de facilidad que la fuente anota enteros en cada banco participante no son montos aprobados."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from analisis_preliminar import topes_de_facilidad_repetidos


def _fila(i, inst, fecha, monto):
    return {"id_proyecto": i, "institucion": inst, "fecha_aprobacion": fecha, "anio_aprobacion": int(fecha[:4]),
            "monto_aprobado_usd": monto}


def test_marca_el_tope_anotado_el_mismo_dia_y_no_los_prestamos_redondos_del_anio():
    tope = [_fila(f"g{k}", "IFC", "2022-12-15", 3.115e9) for k in range(7)]
    redondos = [_fila(f"b{k}", "BIRF", f"2021-{k + 1:02d}-15", 5e8) for k in range(12)]
    anclados = [_fila(f"c{k}", "CAF", "2025-01-01", 5e8) for k in range(6)]
    chicos = [_fila(f"t{k}", "BID", "2024-01-23", 2e5) for k in range(12)]
    df = pd.DataFrame(tope + redondos + anclados + chicos)
    assert topes_de_facilidad_repetidos(df).tolist() == [True] * 7 + [False] * 30
