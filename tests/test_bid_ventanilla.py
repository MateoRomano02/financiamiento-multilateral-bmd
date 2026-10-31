"""La cartera privada que el BID aprobó hasta 2015 y los montos viejos de BID Invest.

Criterio de la dirección (30/10/2026): los préstamos sin garantía soberana del BID con instrumento IIC
son no soberanos. La misma operación figura en el archivo de BID Invest y se cuenta una vez.
"""

import csv

import pandas as pd

from src.common import normalizar as nz
from src.common import validaciones as v

CAMPOS_BID = ["oper_num", "oper_nm", "cntry_nm", "apprvl_dt", "publc_sts_nm", "orig_apprvd_useq_amnt",
              "totl_cost_orig", "opertyp_nm", "objtv", "sector_nm", "lending_instrmnt_cd", "lending_typ_cd"]


def _bid(tmp_path, filas):
    ruta = tmp_path / "bid.csv"
    with ruta.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_BID)
        w.writeheader()
        for oper, instr, tipo in filas:
            w.writerow({"oper_num": oper, "oper_nm": oper, "cntry_nm": "Argentina", "apprvl_dt": "2015-06-01",
                        "publc_sts_nm": "Closed", "orig_apprvd_useq_amnt": "50000000", "totl_cost_orig": "",
                        "opertyp_nm": "Loan Operation", "objtv": "", "sector_nm": "", "lending_instrmnt_cd": instr,
                        "lending_typ_cd": tipo})
    return ruta


def test_la_cartera_privada_del_bid_es_no_soberana(tmp_path):
    df = nz.normalizar_bid(_bid(tmp_path, [("AR-L1", "IIC", "NSG"), ("AR-L2", "LON", "SG"), ("AR-T3", "MIF", "NSG")]),
                           "2026-10-30")
    assert df.set_index("id_proyecto")["tipo_ventanilla"].to_dict() == {
        "AR-L1": "no_soberana", "AR-L2": "soberana", "AR-T3": "no_soberana"}
    assert df.set_index("id_proyecto")["institucion"].to_dict() == {"AR-L1": "BID", "AR-L2": "BID", "AR-T3": "BID Lab"}


def test_bid_invest_toma_el_monto_viejo_solo_si_falta_el_propio(tmp_path):
    xml = """<root>
<item><Language>English</Language><project_number>AR-L1</project_number><approval_date>2015-06-01</approval_date>
<iic_financing_amount></iic_financing_amount><project_idb_fin_amount>40000000</project_idb_fin_amount>
<Investment_instrument>Loan</Investment_instrument></item>
<item><Language>English</Language><project_number>12345-01</project_number><approval_date>2019-03-01</approval_date>
<iic_financing_amount>20000000</iic_financing_amount><project_idb_fin_amount>90000000</project_idb_fin_amount>
<Investment_instrument>Loan</Investment_instrument></item>
</root>"""
    ruta = tmp_path / "bi.xml"
    ruta.write_text(xml, encoding="utf-8")
    df = nz.normalizar_bid_invest(ruta, "2026-10-30")
    assert df.set_index("id_proyecto")["monto_aprobado_usd"].to_dict() == {"AR-L1": 40e6, "12345-01": 20e6}


def test_la_operacion_repetida_queda_una_vez_del_lado_del_bid():
    df = pd.DataFrame([
        {"institucion": "BID", "id_proyecto": "AR-L1", "tipo_ventanilla": "no_soberana", "estado": "cerrado", "anio_aprobacion": 2014},
        {"institucion": "BID Invest", "id_proyecto": "AR-L1", "tipo_ventanilla": "no_soberana", "estado": "cerrado", "anio_aprobacion": 2014},
        {"institucion": "BID", "id_proyecto": "AR-L2", "tipo_ventanilla": "soberana", "estado": "cerrado", "anio_aprobacion": 2014},
        {"institucion": "BID Invest", "id_proyecto": "AR-L2", "tipo_ventanilla": "no_soberana", "estado": "cerrado", "anio_aprobacion": 2014},
        {"institucion": "BID", "id_proyecto": "AR-L3", "tipo_ventanilla": "no_soberana", "estado": "cancelado", "anio_aprobacion": 2015},
        {"institucion": "BID Invest", "id_proyecto": "AR-L3", "tipo_ventanilla": "no_soberana", "estado": "cerrado", "anio_aprobacion": 2015},
        {"institucion": "BID Invest", "id_proyecto": "AR-L1", "tipo_ventanilla": "no_soberana", "estado": "cerrado", "anio_aprobacion": 2020},
    ])
    out = nz.sin_doble_bid(df)
    assert list(zip(out["institucion"], out["id_proyecto"], out["anio_aprobacion"])) == [
        ("BID", "AR-L1", 2014), ("BID", "AR-L2", 2014), ("BID Invest", "AR-L2", 2014), ("BID", "AR-L3", 2015),
        ("BID Invest", "AR-L3", 2015), ("BID Invest", "AR-L1", 2020)]


def test_la_validacion_acepta_la_cartera_privada_vieja_y_no_la_nueva():
    df = pd.DataFrame([{"institucion": "BID", "tipo_ventanilla": "no_soberana", "anio_aprobacion": 2015},
                       {"institucion": "BID", "tipo_ventanilla": "soberana", "anio_aprobacion": 2018}])
    assert v.validar_ventanilla(df) == []
    df.loc[1, "tipo_ventanilla"] = "no_soberana"
    assert v.validar_ventanilla(df)
