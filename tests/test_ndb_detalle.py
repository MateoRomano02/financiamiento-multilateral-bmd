"""Las etiquetas con que la ficha del NDB nombra el monto vigente.

La ficha nombra el monto vigente de varias formas; reconocer solo una dejaba operaciones sin monto.
"""

import pytest

from scripts.descargar_ndb_detalle import monto_de_la_ficha


@pytest.mark.parametrize("texto, esperado", [
    ("<p>NDB Financing USD 300 million</p>", "USD 300 million"),
    ("<p>Current limit of financing USD 250 million</p>", "USD 250 million"),
    ("<p>Current Limit of NDB Financing Amount USD 300 million</p>", "USD 300 million"),
    ("<p>Current Limit of NDB Borrowing USD 1 billion</p>", "USD 1 billion"),
    ("<p>Current Limit of NDB Financing: CHF 500 million</p>", "CHF 500 million"),
])
def test_reconoce_las_etiquetas_del_monto_vigente(texto, esperado):
    assert monto_de_la_ficha(texto).get("monto_aprobado") == esperado


def test_el_limite_propuesto_no_cuenta_como_aprobado():
    ficha = monto_de_la_ficha("<p>Proposed Limit of NDB Financing USD 100 million</p>")
    assert "monto_aprobado" not in ficha and ficha.get("monto_propuesto") == "USD 100 million"


def test_lee_el_estado_que_declara_la_ficha():
    ficha = monto_de_la_ficha("<p>Country Russia Status Cancelled Area Of Operation Transport</p>")
    assert ficha.get("estado_ficha") == "Cancelled"
