"""Tests del anexo de operaciones aprobadas del informe anual del NDB.

Leen el PDF descargado en data/raw/ndb/. Si no está (un clon sin datos), se saltean.
"""

from pathlib import Path

import pytest

from src.common.ndb_anexo import leer_anexo
from src.common.normalizar import normalizar_ndb
from src.common.tipo_de_cambio import a_dolares

NDB = Path(__file__).resolve().parent.parent / "data" / "raw" / "ndb"
PDFS = sorted(NDB.glob("ndb_informe_anual_*.pdf"))
HTMLS = sorted(NDB.glob("ndb_proyectos_*.html"))

# Total 2016-2025 del anexo, en millones de dólares y sin el programa de locomotoras, que está en francos suizos.
TOTAL_SIN_CHF_M = 42_527

pytestmark = pytest.mark.skipif(not PDFS, reason="falta la descarga del informe anual del NDB")


@pytest.fixture(scope="module")
def anexo():
    return leer_anexo(PDFS[-1])


def test_devuelve_las_139_operaciones_numeradas(anexo):
    assert [f.numero for f in anexo] == list(range(1, 140))
    assert all(f.monto_millones > 0 for f in anexo)
    assert all(f.nombre and f.pais and f.moneda for f in anexo)


def test_total_en_dolares_coincide_con_la_investigacion(anexo):
    total = 0.0
    for f in anexo:
        if f.moneda_monto == "CHF":
            continue
        total += a_dolares(f.monto_millones, f.moneda_monto, f.anio_aprobacion)
    assert abs(total - TOTAL_SIN_CHF_M) / TOTAL_SIN_CHF_M < 0.01


def test_el_franco_suizo_se_convierte(anexo):
    locomotoras = next(f for f in anexo if f.numero == 51)
    assert locomotoras.moneda_monto == "CHF"
    assert a_dolares(locomotoras.monto_millones, "CHF", 2019) is not None


def test_operaciones_por_anio(anexo):
    cuentas = {}
    for f in anexo:
        cuentas[f.anio_aprobacion] = cuentas.get(f.anio_aprobacion, 0) + 1
    assert cuentas == {2016: 8, 2017: 6, 2018: 17, 2019: 22, 2020: 19,
                       2021: 10, 2022: 14, 2023: 9, 2024: 15, 2025: 19}


def test_notas_de_cancelacion_con_su_anio(anexo):
    por_numero = {f.numero: f for f in anexo}
    assert por_numero[2].cancelada_total and por_numero[2].anio_cancelacion == 2018
    assert por_numero[100].cancelada_total and por_numero[100].anio_cancelacion == 2024
    # Una cancelación parcial no es una cancelación total.
    assert not por_numero[3].cancelada_total and "Partially cancelled" in por_numero[3].nota


def test_monto_en_dolares_equivalentes(anexo):
    # "USD 1.000 equivalent" aunque la operación sea en euros
    assert (anexo[74].moneda, anexo[74].moneda_monto, anexo[74].monto_millones) == ("EUR", "USD", 1000.0)


@pytest.mark.skipif(not HTMLS, reason="falta el listado web del NDB")
def test_corpus_ndb_une_el_anexo():
    df = normalizar_ndb(HTMLS[-1], "2026-10-08")
    # Solo falta en el listado web la operación 100 (Sudáfrica, cancelada en 2024)
    agregadas = df[df["url_proyecto"].isna()]
    assert list(agregadas["nombre"]) == ["Network Modernisation and Broadband Connectivity Enhancement Project"]
    assert agregadas.iloc[0]["estado"] == "cancelado"

    canara = df[df["nombre"].str.startswith("Canara")].iloc[0]
    assert canara["estado"] == "cancelado"
    assert canara["monto_aprobado_usd"] == pytest.approx(250e6)
    assert canara["monto_aprobado_original_usd"] == pytest.approx(250e6)

    # El monto vigente de una cancelada en parte no se toca: el original va en su columna
    lingang = df[df["nombre"].str.startswith("Lingang")].iloc[0]
    assert lingang["monto_aprobado_usd"] < lingang["monto_aprobado_original_usd"]
