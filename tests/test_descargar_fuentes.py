"""Tests del programa de descarga que no necesitan red.

Una constante borrada por error no se detecta hasta descargar, y la descarga no corre en los
tests. Este test revisa que todo nombre global que usa cada funcion del modulo exista.
"""

import builtins
import importlib.util
import inspect
import sys
from pathlib import Path

RUTA = Path(__file__).resolve().parent.parent / "scripts" / "descargar_fuentes.py"


def cargar():
    spec = importlib.util.spec_from_file_location("descargar_fuentes", RUTA)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo  # las dataclasses del modulo lo buscan ahi
    spec.loader.exec_module(modulo)
    return modulo


def test_ninguna_funcion_usa_un_nombre_global_inexistente():
    modulo = cargar()
    faltan = {}
    for nombre, funcion in inspect.getmembers(modulo, inspect.isfunction):
        if funcion.__module__ != modulo.__name__:
            continue
        sueltos = [n for n in funcion.__code__.co_names
                   if not hasattr(modulo, n) and not hasattr(builtins, n)
                   and n not in _atributos(funcion)]
        if sueltos:
            faltan[nombre] = sueltos
    assert not faltan, faltan


def _atributos(funcion) -> set[str]:
    """co_names mezcla globales con atributos (x.get) e imports locales. Se descartan esos."""
    import dis
    return {i.argval for i in dis.get_instructions(funcion)
            if i.opname in ("LOAD_ATTR", "LOAD_METHOD", "STORE_ATTR", "IMPORT_NAME", "IMPORT_FROM")}


def pedidos_con_respuestas(codigos):
    import httpx
    restantes = list(codigos)
    vistos = []

    def responder(request):
        vistos.append(request.url)
        return httpx.Response(restantes.pop(0))

    return httpx.MockTransport(responder), vistos


def test_un_error_pasajero_del_servidor_se_reintenta(monkeypatch):
    """Un 503 pasajero no debe frenar la actualizacion entera."""
    modulo = cargar()
    monkeypatch.setattr(modulo.ClienteConReintentos, "ESPERAS", (0, 0, 0))
    transporte, vistos = pedidos_con_respuestas([503, 503, 200])
    with modulo.ClienteConReintentos(transport=transporte) as cliente:
        assert cliente.get("https://ejemplo.org").status_code == 200
    assert len(vistos) == 3


def test_un_pedido_mal_hecho_no_se_reintenta(monkeypatch):
    modulo = cargar()
    monkeypatch.setattr(modulo.ClienteConReintentos, "ESPERAS", (0, 0, 0))
    transporte, vistos = pedidos_con_respuestas([404])
    with modulo.ClienteConReintentos(transport=transporte) as cliente:
        assert cliente.get("https://ejemplo.org").status_code == 404
    assert len(vistos) == 1
