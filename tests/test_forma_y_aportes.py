"""Tests de la forma de financiamiento recuperada por cruces y de los aportes de terceros (8/10/2026)."""

import json

import pandas as pd

from src.common import normalizar


def ops(*filas):
    return pd.DataFrame(
        [{"institucion": v, "id_proyecto": p, "pais": c, "fecha_aprobacion": f, "monto_aprobado_usd": a,
          "monto_desembolsado_usd": None, "forma_financiamiento": None} for v, p, c, f, a in filas]
    )


def prestamos(*filas):
    return pd.DataFrame(
        [{"project_id": p, "ventanilla": v, "country": c, "fecha_prestamo": pd.Timestamp(f), "original": o,
          "desembolsado": 0.0, "forma": forma} for p, v, c, f, o, forma in filas]
    )


def test_el_financiamiento_adicional_toma_la_forma_por_pais_fecha_y_monto(monkeypatch):
    """El prestamo del adicional queda bajo otro proyecto: no une por proyecto, si por pais+fecha+monto."""
    monkeypatch.setattr(normalizar, "prestamos_banco_mundial", lambda: prestamos(
        ("P0", "IDA", "Benin", "2020-03-10", 100e6, "donacion")))
    df = normalizar._desembolsos_banco_mundial(ops(("IDA", "P9", "Benin", "2020-03-01", 102e6)))
    assert df["forma_financiamiento"].tolist() == ["donacion"]
    assert df["monto_desembolsado_usd"].isna().all()  # el cruce por pais no atribuye desembolsos


def test_el_cruce_por_pais_no_asigna_si_los_candidatos_discrepan_o_el_monto_no_cierra(monkeypatch):
    monkeypatch.setattr(normalizar, "prestamos_banco_mundial", lambda: prestamos(
        ("P0", "IDA", "Benin", "2020-03-10", 100e6, "donacion"),
        ("P1", "IDA", "Benin", "2020-03-12", 100e6, "prestamo"),
        ("P2", "IDA", "Chad", "2020-03-10", 150e6, "prestamo")))
    df = normalizar._desembolsos_banco_mundial(ops(
        ("IDA", "P9", "Benin", "2020-03-01", 100e6),   # dos formas compiten
        ("IDA", "P8", "Chad", "2020-03-01", 100e6)))   # el monto difiere mas de 5%
    assert df["forma_financiamiento"].isna().all()


def test_bid_invest_sin_instrumento_toma_la_forma_de_la_ficha_del_bid_que_cita(monkeypatch):
    """El enlace esta en HTML escapado, que la limpieza de texto descarta: se busca en la descripcion cruda."""
    monkeypatch.setattr(normalizar, "formas_bid_por_operacion",
                        lambda: {"DR-L1060": "prestamo", "DR-X1008": "garantia", "ES-L1": "prestamo"})
    cita = '&lt;a href=&quot;https://www.iadb.org/en/project/DR-L1060&quot;&gt;Projects&lt;/a&gt;'
    assert normalizar._forma_por_ficha_bid(cita) == "prestamo"
    assert normalizar._forma_por_ficha_bid(cita + cita.replace("DR-L1060", "DR-X1008")) is None
    assert normalizar._forma_por_ficha_bid("sin enlace") is None


def test_gbm_anota_costo_total_y_terceros_en_una_sola_fila_por_proyecto(monkeypatch, tmp_path):
    monkeypatch.setattr(normalizar, "prestamos_banco_mundial",
                        lambda: pd.DataFrame(columns=["project_id", "ventanilla", "fecha_prestamo", "original",
                                                      "desembolsado", "forma", "country"]))
    ruta = tmp_path / "p.json"
    ruta.write_text(json.dumps({"projects": {"P1": {
        "id": "P1", "boardapprovaldate": "2019-01-01T00:00:00Z", "curr_ibrd_commitment": "60000000",
        "idacommamt": "40000000", "grantamt": "5000000", "lendprojectcost": "300000000"}}}))
    df = normalizar.normalizar_gbm(ruta, "2026-10-08")
    assert df["costo_total_proyecto_usd"].notna().sum() == 1
    assert df["costo_total_proyecto_usd"].sum() == 300e6
    assert df["aporte_terceros_usd"].sum() == 5e6


def test_ndb_otras_fuentes_van_a_aporte_de_terceros_en_dolares(tmp_path):
    (tmp_path / "ndb_montos_2026-09-29.json").write_text(json.dumps([
        {"url": "https://www.ndb.int/project/x/", "monto_aprobado": "USD 75 million",
         "monto_ndb": "USD 75 million", "monto_otras_fuentes": "USD 225 million",
         "fecha_aprobacion": "10 May 2019"}]))
    ruta = tmp_path / "ndb_proyectos_2026-09-29.html"
    ruta.write_text('<div class="project-card card x"><a class="card-link" href="https://www.ndb.int/project/x/">'
                    '</a><div class="project-card-type text-medium-bold">Sovereign</div>'
                    '<div class="project-card-title">X</div>\n</div>')
    df = normalizar.normalizar_ndb(ruta, "2026-09-29")
    assert df["aporte_terceros_usd"].tolist() == [225e6]
