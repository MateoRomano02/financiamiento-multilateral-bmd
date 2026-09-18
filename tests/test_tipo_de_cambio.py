"""Tests de la conversion de moneda local a dolares.

Existen porque este modulo sostiene una cifra del informe. El NDB publica 44 de sus 146 operaciones
en moneda local, y leerlas como dolares multiplicaba su cartera por cinco. El error no daba ninguna
senal: producia un numero grande y plausible. Estos tests congelan el comportamiento que lo evita.
"""

import pytest

from src.common import tipo_de_cambio as tc


def _hay_series() -> bool:
    return any(tc.REFERENCIA.glob("tipos_de_cambio_*.csv"))


# El repositorio publico no versiona datos, asi que las series no estan hasta correr el
# descargador. Los tests que las necesitan se saltean con un mensaje que dice como conseguirlas,
# en lugar de dejar el gate en rojo por una ausencia esperada.
necesita_series = pytest.mark.skipif(
    not _hay_series(),
    reason="faltan las series; correr scripts/descargar_tipos_de_cambio.py",
)


def test_rmb_y_cny_son_la_misma_moneda():
    """El NDB usa los dos nombres para la moneda china, a veces en el mismo anio."""
    assert tc.normalizar_moneda("RMB") == "CNY"
    assert tc.normalizar_moneda("rmb") == "CNY"
    assert tc.normalizar_moneda(" cny ") == "CNY"


def test_los_dolares_pasan_sin_tocarse():
    assert tc.a_dolares(1_000.0, "USD", 2020) == 1_000.0


@necesita_series
def test_la_moneda_local_se_divide_por_la_tasa_no_se_multiplica():
    """El error de signo aca es el que inflaba el NDB: hay que dividir, no multiplicar.

    El rand cotizo alrededor de 16 por dolar en 2020, asi que 16.000 millones de rand tienen que
    dar del orden de 1.000 millones de dolares y nunca 256.000 millones.
    """
    resultado = tc.a_dolares(16_000.0, "ZAR", 2020)
    assert resultado is not None
    assert 700 < resultado < 1_400


@necesita_series
def test_el_euro_vale_mas_que_el_dolar_no_menos():
    """La serie del euro viene invertida en FRED y se corrige al descargar.

    Si la inversion se perdiera, un monto en euros daria menos dolares en lugar de mas, y este
    test es el que lo caza.
    """
    resultado = tc.a_dolares(100.0, "EUR", 2022)
    assert resultado is not None
    assert resultado > 100.0


@necesita_series
def test_sin_insumos_devuelve_nulo_en_vez_de_inventar():
    """Un hueco visible es preferible a una conversion inventada."""
    assert tc.a_dolares(None, "ZAR", 2020) is None
    assert tc.a_dolares(100.0, None, 2020) is None
    assert tc.a_dolares(100.0, "ZAR", None) is None
    assert tc.a_dolares(100.0, "XYZ", 2020) is None  # moneda sin serie
    assert tc.a_dolares(100.0, "ZAR", 1970) is None  # anio fuera de la serie


@necesita_series
@pytest.mark.parametrize("moneda", ["CNY", "ZAR", "INR", "BRL", "EUR"])
def test_estan_las_cinco_monedas_que_usa_el_ndb(moneda):
    serie = tc.serie_tipos_de_cambio()
    anios = [a for (m, a) in serie if m == moneda]
    assert anios, f"falta la serie de {moneda}"
    assert min(anios) <= 2016 and max(anios) >= 2025, f"la serie de {moneda} no cubre el periodo"
