"""Tests del esquema comun como fuente de las definiciones.

El diccionario de variables se genera desde `VARIABLES`. Si una columna entra al esquema sin
definicion, el diccionario sale con un hueco y nadie lo nota hasta que alguien lo lee. Estos tests
lo frenan antes.
"""

from src.common.esquema import COLUMNAS, COLUMNAS_OBLIGATORIAS, VARIABLES


def test_toda_columna_tiene_grupo_y_definicion():
    for nombre, (grupo, definicion) in VARIABLES.items():
        assert grupo.strip(), f"{nombre} no tiene grupo"
        assert len(definicion.strip()) >= 15, f"{nombre} tiene una definicion vacia o de relleno"


def test_las_columnas_salen_de_las_variables_en_el_mismo_orden():
    assert COLUMNAS == tuple(VARIABLES)


def test_las_obligatorias_existen_en_el_esquema():
    assert set(COLUMNAS_OBLIGATORIAS) <= set(COLUMNAS)


def test_ninguna_definicion_usa_guion_largo():
    """El proyecto prohibe el guion largo en todo texto que llega a un lector."""
    for nombre, (_, definicion) in VARIABLES.items():
        assert "—" not in definicion, f"{nombre} usa guion largo"
