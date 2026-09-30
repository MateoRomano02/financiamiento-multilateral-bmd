"""Tests de la union entre las operaciones del Banco Mundial y su estado de prestamos.

La union se decidio el 29/09/2026 midiendo tres reglas sobre el corpus real. Cada test congela
uno de los casos que hicieron descartar la regla ingenua de sumar todo por proyecto.
"""

import pandas as pd

from src.common import normalizar


def operaciones(*filas):
    return pd.DataFrame(
        [{"institucion": v, "id_proyecto": p, "fecha_aprobacion": f, "monto_aprobado_usd": a,
          "monto_desembolsado_usd": None} for v, p, f, a in filas]
    )


def prestamos(*filas):
    return pd.DataFrame(
        [{"project_id": p, "ventanilla": v, "fecha_prestamo": pd.Timestamp(f), "original": o,
          "desembolsado": d} for p, v, f, o, d in filas]
    )


def unir(monkeypatch, ops, prest):
    monkeypatch.setattr(normalizar, "prestamos_banco_mundial", lambda: prest)
    return normalizar._desembolsos_banco_mundial(ops)["monto_desembolsado_usd"].tolist()


def test_el_financiamiento_adicional_no_se_le_suma_al_proyecto_original(monkeypatch):
    """El prestamo de la ampliacion queda bajo el proyecto original pero con otra fecha."""
    ops = operaciones(("BIRF", "P1", "2016-05-10", 100e6))
    prest = prestamos(("P1", "BIRF", "2016-05-12", 100e6, 80e6),
                      ("P1", "BIRF", "2020-03-01", 50e6, 50e6))
    assert unir(monkeypatch, ops, prest) == [80e6]


def test_si_los_montos_no_coinciden_la_operacion_queda_sin_desembolso(monkeypatch):
    """Siete casos del corpus tienen un prestamo de 2 a 17 veces el aprobado: es otra cosa."""
    ops = operaciones(("BIRF", "P2", "2021-01-01", 18e6))
    prest = prestamos(("P2", "BIRF", "2021-01-01", 304e6, 300e6))
    assert pd.isna(unir(monkeypatch, ops, prest)[0])


def test_las_ventanillas_no_se_mezclan(monkeypatch):
    """Un proyecto mixto tiene una operacion BIRF y otra IDA con el mismo identificador."""
    ops = operaciones(("BIRF", "P3", "2018-06-01", 60e6), ("IDA", "P3", "2018-06-01", 40e6))
    prest = prestamos(("P3", "BIRF", "2018-06-01", 60e6, 10e6),
                      ("P3", "IDA", "2018-06-01", 40e6, 30e6))
    assert unir(monkeypatch, ops, prest) == [10e6, 30e6]


def test_la_diferencia_de_cambio_de_la_ida_se_tolera(monkeypatch):
    """Los creditos en Derechos Especiales de Giro valen distinto en dolares al cierre."""
    ops = operaciones(("IDA", "P4", "2019-02-01", 100e6))
    prest = prestamos(("P4", "IDA", "2019-02-20", 108e6, 104e6))
    assert unir(monkeypatch, ops, prest) == [104e6]
