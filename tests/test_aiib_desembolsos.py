"""Tests de la unión de desembolsos del AIIB con su corpus."""

import pandas as pd

from src.common.aiib_desembolsos import cruzar, nombre_clave, slug_de_url, unir_desembolsos
from src.common import aiib_desembolsos

URL = "https://www.aiib.org/en/projects/details/2020/approved/"


def corpus(*filas):
    return pd.DataFrame([{"nombre": n, "url_proyecto": u, "monto_desembolsado_usd": None} for n, u in filas])


def lista(*filas):
    return pd.DataFrame([{"nombre": n, "slug": s, "desembolso_musd": d} for n, s, d in filas])


def test_slug_ignora_los_pdf_y_pasa_a_minusculas():
    assert slug_de_url(f"Refer to the Project Document: {URL}India-Solar-Project.html ") == "india-solar-project"
    assert slug_de_url("Refer to the PCN: https://www.aiib.org/en/projects/details/2020/_download/X/a.pdf") is None


def test_nombre_con_prefijo_de_pais_y_siglas_cruza():
    assert nombre_clave("Ecuador: CONAFIPS Credit Line (CCL) Project") == nombre_clave("CONAFIPS Credit Line Project")
    c = cruzar(corpus(("Ecuador: Linea de Credito Project (LCP)", None)), lista(("Linea de Credito Project", None, 5.0)))
    assert c.to_dict("records") == [{"indice": 0, "fila_lista": 0, "paso": "nombre"}]


def test_un_desembolso_no_se_asigna_a_dos_operaciones():
    # Dos operaciones del corpus con el mismo nombre (años distintos) y una sola fila en la lista.
    c = cruzar(corpus(("Peru: Airport Project", None), ("Peru: Airport Project", None)),
               lista(("Airport Project", None, 5.0)))
    assert c.empty
    # Una fila de la lista con una ficha que dos operaciones comparten tampoco se reparte.
    c = cruzar(corpus(("A", URL + "x.html"), ("B", URL + "x.html")), lista(("C", "x", 5.0)))
    assert c.empty


def test_cada_fila_de_la_lista_se_usa_una_vez_entre_pasos():
    # La primera cruza por ficha; la segunda tiene el mismo nombre que la fila ya usada y no puede tomarla.
    c = cruzar(corpus(("Pais: Uno", URL + "uno.html"), ("Uno", None)), lista(("Uno", "uno", 5.0)))
    assert c["fila_lista"].is_unique and len(c) == 1 and c.loc[0, "paso"] == "ficha"


def test_unir_carga_el_desembolso_en_dolares_y_no_pisa_el_aprobado(monkeypatch):
    monkeypatch.setattr(aiib_desembolsos, "leer_lista",
                        lambda ruta: lista(("Proyecto", None, 2.5), ("Oculto", None, float("nan"))))
    df = corpus(("Pais: Proyecto", None), ("Pais: Oculto", None))
    df["monto_aprobado_usd"] = [9e6, 9e6]
    out = unir_desembolsos(df, None)
    assert out.loc[0, "monto_desembolsado_usd"] == 2.5e6
    assert pd.isna(out.loc[1, "monto_desembolsado_usd"])
    assert out["monto_aprobado_usd"].tolist() == [9e6, 9e6]
