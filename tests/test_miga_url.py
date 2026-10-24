"""MIGA no publica enlaces rotos: url_proyecto queda vacío."""

import json

from src.common import normalizar


def test_miga_deja_vacio_url_proyecto_aunque_la_fuente_traiga_enlace(tmp_path):
    ruta = tmp_path / "miga.json"
    ruta.write_text(json.dumps({"data": [{
        "project_id": "7041", "issued_fy": "2016", "project_name": "Oyu Tolgoi Project",
        "host_country": "Mongolia", "project_links": "https://www.miga.org/node/1972",
        "project_start_date": "2015-12-16", "gross_issued_amount": "1000000000",
    }]}), encoding="utf-8")
    df = normalizar.normalizar_miga(ruta, "2026-10-13")
    assert df["url_proyecto"].isna().all()
