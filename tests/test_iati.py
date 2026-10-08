"""Tests del normalizador IATI, comun a CAF, FONPLATA y BCIE.

Cada test congela un comportamiento que el 29/09/2026 destapo un error silencioso: codigo que no
tiraba ninguna excepcion y producia datos mal. Estan escritos contra un archivo minimo armado a
mano, asi que no dependen de ninguna descarga.
"""

import pandas as pd
import pytest

from src.common.normalizar import normalizar_iati, sectores_cad
from src.common.validaciones import validar_montos

ACTIVIDAD = """<iati-activities version="2.03">
  <iati-activity default-currency="USD">
    <iati-identifier>XM-DAC-46007-500001</iati-identifier>
    <reporting-org ref="XM-DAC-46007"/>
    <title><narrative>Carretera de prueba</narrative></title>
    <activity-status code="2"/>
    <activity-date type="1" iso-date="2023-03-10"/>
    <activity-date type="2" iso-date="2024-06-01"/>
    <recipient-country code="{pais}"/>
    {sectores}
    <transaction><transaction-type code="2"/><transaction-date iso-date="2022-03-10"/><value>100000000</value></transaction>
    <transaction><transaction-type code="3"/><transaction-date iso-date="2022-09-01"/><value>30000000</value></transaction>
    <transaction><transaction-type code="3"/><transaction-date iso-date="2023-02-01"/><value>25000000</value></transaction>
  </iati-activity>
</iati-activities>"""


def normalizar(tmp_path, pais="NI", sectores='<sector vocabulary="1" code="21020"/>'):
    ruta = tmp_path / "actividades.xml"
    ruta.write_text(ACTIVIDAD.format(pais=pais, sectores=sectores), encoding="utf-8")
    return normalizar_iati(ruta, "2026-09-29", institucion="BCIE").iloc[0]


def test_los_desembolsos_en_cuotas_se_suman(tmp_path):
    """FONPLATA y BCIE publican cada desembolso como una transaccion aparte. Antes se tomaba la
    ultima cuota y el desembolsado salia muy por debajo del real."""
    assert normalizar(tmp_path)["monto_desembolsado_usd"] == 55_000_000


def test_la_fecha_es_la_del_compromiso_y_no_el_primer_campo_de_fecha(tmp_path):
    """En el BCIE el primer activity-date es el tipo 1, que resulta ser el compromiso mas un anio.
    Tomarlo corria un anio las 119 operaciones con compromiso."""
    fila = normalizar(tmp_path)
    assert fila["fecha_aprobacion"] == "2022-03-10"
    assert fila["anio_aprobacion"] == 2022


def test_el_codigo_no_estandar_de_republica_dominicana(tmp_path):
    """El BCIE escribe RD en lugar de DO. Sin el alias quedaba un pais llamado "RD"."""
    assert normalizar(tmp_path, pais="RD")["pais"] == "Dominican Republic"


def test_se_prefiere_el_sector_con_nombre_aunque_no_sea_el_primero(tmp_path):
    """En FONPLATA el primer sector es un codigo sin nombre y el nombre viene despues."""
    sectores = ('<sector vocabulary="1" code="21020"/>'
                '<sector vocabulary="99" code="X"><narrative>Transporte vial</narrative></sector>')
    assert normalizar(tmp_path, sectores=sectores)["sector"] == "Transporte vial"


def test_sin_nombre_el_codigo_cad_se_traduce(tmp_path):
    """El BCIE nunca publica el nombre del sector, solo el codigo CAD."""
    if not sectores_cad():
        pytest.skip("falta la lista de sectores; correr scripts/descargar_fuentes.py iati_sector")
    assert normalizar(tmp_path)["sector"] == sectores_cad()["21020"]


def test_la_validacion_distingue_error_de_unidad_de_sobredesembolso():
    """Un error de unidad multiplica por mil; un sobredesembolso real del BCIE fue de 1,5 veces."""
    base = {"institucion": ["BCIE"], "monto_original": [None]}
    unidad = validar_montos(pd.DataFrame({**base, "monto_aprobado_usd": [100.0], "monto_desembolsado_usd": [100_000.0]}))
    assert any("unidades" in e for e in unidad)
    menor = validar_montos(pd.DataFrame({**base, "monto_aprobado_usd": [100.0], "monto_desembolsado_usd": [150.0]}))
    assert menor and all(e.startswith("sobredesembolso: ") for e in menor)
    redondeo = validar_montos(pd.DataFrame({**base, "monto_aprobado_usd": [41_942_761.0],
                                            "monto_desembolsado_usd": [41_942_761.0000001]}))
    assert redondeo == []


def test_una_fecha_de_relleno_no_se_toma_como_aprobacion(tmp_path):
    """CAF publico dos prestamos de 2025 con el compromiso fechado 1900-01-01."""
    ruta = tmp_path / "actividades.xml"
    xml = ACTIVIDAD.format(pais="NI", sectores="").replace('iso-date="2022-03-10"/><value>100000000',
                                                          'iso-date="1900-01-01"/><value>100000000')
    ruta.write_text(xml, encoding="utf-8")
    assert normalizar_iati(ruta, "2026-09-29", institucion="CAF").iloc[0]["fecha_aprobacion"] == "2024-06-01"


def test_las_fotos_se_unen_sin_perder_las_viejas_ni_duplicar_republicadas():
    """CAF saco del archivo nuevo las operaciones terminadas y republico una con otro identificador."""
    from src.common.normalizar import acumular_fotos

    def foto(fecha, filas):
        return pd.DataFrame([{"id_proyecto": i, "nombre": n, "anio_aprobacion": a, "monto_aprobado_usd": m,
                              "fecha_relevamiento": fecha} for i, n, a, m in filas])

    vieja = foto("2026-08-21", [("A", "Ruta norte", 2015, 10), ("B", "Apoyo covid", 2020, 350), ("C", "Agua", 2019, 5)])
    nueva = foto("2026-09-29", [("C", "Agua", 2019, 6), ("D", "Apoyo covid", 2020, 350)])
    union = acumular_fotos([vieja, nueva]).set_index("id_proyecto")
    assert sorted(union.index) == ["A", "C", "D"]
    assert union.loc["C", "monto_aprobado_usd"] == 6
    assert union.loc["A", "fecha_relevamiento"] == "2026-08-21"


def test_un_campo_que_la_foto_nueva_deja_vacio_conserva_el_valor_anterior():
    """CAF dejo de publicar desembolsos en su archivo del 9/09; el dato de agosto no se pierde."""
    from src.common.normalizar import acumular_fotos

    vieja = pd.DataFrame([{"id_proyecto": "A", "nombre": "Ruta", "anio_aprobacion": 2016,
                           "monto_desembolsado_usd": 80.0, "fecha_relevamiento": "2026-08-21"}])
    nueva = pd.DataFrame([{"id_proyecto": "A", "nombre": "Ruta", "anio_aprobacion": 2016,
                           "monto_desembolsado_usd": None, "fecha_relevamiento": "2026-09-29"}])
    fila = acumular_fotos([vieja, nueva]).iloc[0]
    assert fila["monto_desembolsado_usd"] == 80.0
    assert fila["fecha_relevamiento"] == "2026-09-29"
