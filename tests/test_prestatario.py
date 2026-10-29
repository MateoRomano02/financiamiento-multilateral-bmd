"""La clasificación del prestatario de CAF, FONPLATA y BCIE por su nombre.

Los casos son prestatarios privados confirmados en comunicados de CAF, y las trampas que llevaron a crear las categorías de revisión.
"""

import xml.etree.ElementTree as ET

import pytest

from src.common.prestatario import clasifica_nombre, prestatario_iati


@pytest.mark.parametrize("nombre, esperado", [
    ("Ministerio de Transportes", "soberana"),
    ("República de Panamá", "soberana"),
    ("Banco Improsa S.A.", "no_soberana"),
    ("Genneia S.A.", "no_soberana"),
    # Bancos públicos de desarrollo: toman deuda con o sin garantía soberana, se revisan a mano.
    ("Banco do Nordeste S.A.", "banco_publico"),
    ("Corporación Nacional de Finanzas Populares", "banco_publico"),
    # Lo subnacional se evalúa antes que "Ministerio": un ministerio provincial no es soberano.
    ("Ministerio de Educación de Jujuy", "subnacional"),
    ("Prefeitura de Fortaleza", "subnacional"),
    ("Estados Unidos Méxicanos", "soberana"),
    ("Países accionistas o entes subnacionales con garantía soberana", "soberana"),
    ("Pan American Energy SL", "no_soberana"),
    ("Instituto de Crédito Oficial - ICO", "banco_publico"),
    ("", "sin_dato"),
])
def test_clasifica_nombre(nombre, esperado):
    assert clasifica_nombre(nombre, None)[0] == esperado


def test_bcie_receptor_privado_declarado():
    act = ET.fromstring(
        '<iati-activity><transaction><transaction-type code="2"/>'
        '<receiver-org type="70"><narrative>Ministerio de algo</narrative></receiver-org>'
        '</transaction></iati-activity>')
    assert prestatario_iati(act, "BCIE", None)[1] == "no_soberana"


def test_caf_capital_accionario_es_no_soberano():
    act = ET.fromstring(
        '<iati-activity><participating-org role="4"><narrative>Fondo Regional</narrative>'
        '</participating-org><default-finance-type code="510"/></iati-activity>')
    assert prestatario_iati(act, "CAF", None)[1] == "no_soberana"
