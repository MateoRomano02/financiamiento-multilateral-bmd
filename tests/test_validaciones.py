"""Tests de las validaciones del esquema comun.

Cada test construye una base minima valida y le introduce UN defecto, para verificar que la
validacion correspondiente lo detecta y que las demas no se disparan de mas.
"""

import pandas as pd
import pytest

from src.common.esquema import COLUMNAS
from src.common import validaciones as v


@pytest.fixture
def base_valida() -> pd.DataFrame:
    """Dos filas que cumplen el esquema completo."""
    filas = [
        {
            "banco_grupo": "GBID", "institucion": "BID", "tipo_ventanilla": "soberana",
            "id_proyecto": "AR-L1234", "nombre": "Proyecto de energia renovable",
            "pais": "Argentina", "url_proyecto": "https://iadb.org/p/AR-L1234",
            "fecha_aprobacion": pd.Timestamp("2019-05-10"), "anio_aprobacion": 2019,
            "estado": "cerrado", "estado_original": "Closed",
            "monto_aprobado_usd": 100_000_000.0, "monto_desembolsado_usd": 95_000_000.0,
            "moneda_original": "USD", "monto_original": 100_000_000.0,
            "instrumento": "prestamo", "sector": "Energia",
            "fuente_url": "https://iadb.org/projects", "fecha_relevamiento": "2026-08-21",
            "clasificacion_te": None, "categoria_te": None,
        },
        {
            "banco_grupo": "GBM", "institucion": "IFC", "tipo_ventanilla": "no_soberana",
            "id_proyecto": "40123", "nombre": "Prestamo a empresa",
            "pais": "Argentina", "url_proyecto": "https://disclosures.ifc.org/p/40123",
            "fecha_aprobacion": pd.Timestamp("2022-11-02"), "anio_aprobacion": 2022,
            "estado": "en_implementacion", "estado_original": "Active",
            "monto_aprobado_usd": 25_000_000.0, "monto_desembolsado_usd": 10_000_000.0,
            "moneda_original": "USD", "monto_original": 25_000_000.0,
            "instrumento": "prestamo", "sector": "Financiero",
            "fuente_url": "https://disclosures.ifc.org", "fecha_relevamiento": "2026-08-21",
            "clasificacion_te": None, "categoria_te": None,
        },
    ]
    return pd.DataFrame(filas, columns=list(COLUMNAS))


def test_base_valida_no_tiene_errores(base_valida):
    errores = {k: e for k, e in v.validar_todo(base_valida).items() if e}
    assert errores == {}, f"la base de referencia deberia pasar todo: {errores}"


def test_detecta_columna_faltante(base_valida):
    assert v.validar_columnas(base_valida.drop(columns=["sector"]))


def test_detecta_columna_de_mas(base_valida):
    assert v.validar_columnas(base_valida.assign(columna_inventada=1))


def test_detecta_obligatoria_nula(base_valida):
    base_valida.loc[0, "id_proyecto"] = None
    assert v.validar_obligatorias(base_valida)


def test_detecta_id_duplicado_en_la_misma_institucion(base_valida):
    duplicada = pd.concat([base_valida, base_valida.iloc[[0]]], ignore_index=True)
    assert v.validar_ids_unicos(duplicada)


def test_mismo_id_en_instituciones_distintas_es_valido(base_valida):
    """Dos bancos pueden usar el mismo numero de proyecto sin que sea un duplicado."""
    otra = base_valida.iloc[[0]].copy()
    otra["institucion"] = "BID Invest"
    otra["tipo_ventanilla"] = "no_soberana"
    assert not v.validar_ids_unicos(pd.concat([base_valida, otra], ignore_index=True))


def test_detecta_estado_fuera_del_catalogo(base_valida):
    base_valida.loc[0, "estado"] = "en_tramite"
    assert v.validar_catalogos(base_valida)


def test_detecta_monto_negativo(base_valida):
    base_valida.loc[0, "monto_aprobado_usd"] = -1.0
    assert v.validar_montos(base_valida)


def test_detecta_desembolso_mayor_al_aprobado(base_valida):
    """Sintoma tipico de mezclar millones con unidades."""
    base_valida.loc[0, "monto_desembolsado_usd"] = 200_000_000.0
    assert v.validar_montos(base_valida)


def test_detecta_anio_anterior_al_relevamiento(base_valida):
    base_valida.loc[0, "anio_aprobacion"] = 2001
    assert v.validar_fechas(base_valida)


def test_detecta_ventanilla_incoherente_con_la_institucion(base_valida):
    """La IFC solo presta al sector privado: marcarla como soberana es un error de mapeo."""
    base_valida.loc[1, "tipo_ventanilla"] = "soberana"
    assert v.validar_ventanilla(base_valida)
