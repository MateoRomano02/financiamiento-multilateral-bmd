"""Validaciones del esquema comun.

Se corren sobre cada base normalizada antes de consolidarla. La logica esta separada de los
tests para que tambien pueda invocarse desde los scripts de pipeline y desde un notebook.

Cada validacion devuelve una lista de mensajes de error; lista vacia significa que paso.
"""

from __future__ import annotations

import pandas as pd

from .esquema import (
    ANIO_INICIO,
    BANCOS_GRUPO,
    COLUMNAS,
    COLUMNAS_OBLIGATORIAS,
    ESTADOS,
    TIPOS_VENTANILLA,
    VENTANILLA_POR_INSTITUCION,
)


def validar_columnas(df: pd.DataFrame) -> list[str]:
    """Estan todas las columnas del esquema, y ninguna de mas."""
    faltan = [c for c in COLUMNAS if c not in df.columns]
    sobran = [c for c in df.columns if c not in COLUMNAS]
    errores = []
    if faltan:
        errores.append(f"faltan columnas del esquema: {faltan}")
    if sobran:
        errores.append(f"columnas fuera del esquema: {sobran}")
    return errores


def validar_obligatorias(df: pd.DataFrame) -> list[str]:
    """Ninguna columna obligatoria tiene nulos."""
    return [
        f"{col}: {int(df[col].isna().sum())} filas sin valor"
        for col in COLUMNAS_OBLIGATORIAS
        if col in df.columns and df[col].isna().any()
    ]


def validar_ids_unicos(df: pd.DataFrame) -> list[str]:
    """El id de proyecto es unico dentro de cada institucion."""
    if not {"institucion", "id_proyecto"}.issubset(df.columns):
        return ["no se puede validar unicidad: faltan institucion o id_proyecto"]
    duplicados = df.duplicated(subset=["institucion", "id_proyecto"], keep=False)
    if not duplicados.any():
        return []
    ejemplos = df.loc[duplicados, ["institucion", "id_proyecto"]].head(5).to_dict("records")
    return [f"{int(duplicados.sum())} filas con (institucion, id_proyecto) duplicado. Ej: {ejemplos}"]


def validar_catalogos(df: pd.DataFrame) -> list[str]:
    """Los valores caen dentro de los catalogos cerrados del esquema."""
    errores = []
    for col, catalogo in (
        ("banco_grupo", BANCOS_GRUPO),
        ("estado", ESTADOS),
        ("tipo_ventanilla", TIPOS_VENTANILLA),
    ):
        if col not in df.columns:
            continue
        fuera = sorted(set(df[col].dropna()) - set(catalogo))
        if fuera:
            errores.append(f"{col}: valores fuera del catalogo {fuera}")
    return errores


def validar_montos(df: pd.DataFrame) -> list[str]:
    """Los montos son no negativos y lo desembolsado no supera lo aprobado.

    Un desembolso mayor al monto aprobado casi siempre delata un error de unidad
    (millones mezclados con unidades), no un desembolso real mayor.
    """
    errores = []
    for col in ("monto_aprobado_usd", "monto_desembolsado_usd", "monto_original"):
        if col in df.columns and (df[col] < 0).any():
            errores.append(f"{col}: {int((df[col] < 0).sum())} filas con monto negativo")

    if {"monto_aprobado_usd", "monto_desembolsado_usd"}.issubset(df.columns):
        aprobado = pd.to_numeric(df["monto_aprobado_usd"], errors="coerce")
        desembolsado = pd.to_numeric(df["monto_desembolsado_usd"], errors="coerce")
        # Donde el aprobado es cero la razon no existe; un desembolso ahi cuenta como sobredesembolso.
        razon = (desembolsado / aprobado.where(aprobado > 0)).fillna(0)
        # Un error de unidad deja una huella inconfundible: el desembolsado da mil o un millon de
        # veces el aprobado. Eso es una falla del pipeline y frena la consolidacion.
        unidad = razon >= 10
        if unidad.any():
            errores.append(
                f"monto_desembolsado_usd supera diez veces o mas al aprobado en {int(unidad.sum())} "
                "filas (revisar unidades: millones vs unidades)"
            )
        # Un sobredesembolso menor es un dato de la fuente, no del pipeline: el prestamo se amplio
        # sin registrar un compromiso nuevo, o se publica solo el compromiso original. Se informa, no se corrige ni se recorta.
        # La tolerancia de un dolar absorbe el redondeo de sumar cuotas con decimales.
        menor = (desembolsado > aprobado.fillna(0) + 1) & (razon < 10)
        if menor.any():
            instituciones = ", ".join(sorted(df.loc[menor, "institucion"].dropna().unique()))
            errores.append(
                f"sobredesembolso: {int(menor.sum())} filas con desembolsado mayor al aprobado, "
                f"dato de la fuente ({instituciones})"
            )
    return errores


def validar_fechas(df: pd.DataFrame) -> list[str]:
    """Los anios de aprobacion caen en el rango del relevamiento."""
    if "anio_aprobacion" not in df.columns:
        return []
    anios = pd.to_numeric(df["anio_aprobacion"], errors="coerce")
    fuera = anios.dropna()[(anios < ANIO_INICIO) | (anios > 2100)]
    if fuera.empty:
        return []
    return [f"anio_aprobacion: {len(fuera)} filas fuera de [{ANIO_INICIO}, 2100]: {sorted(set(fuera))[:5]}"]


def validar_ventanilla(df: pd.DataFrame) -> list[str]:
    """La ventanilla declarada coincide con la que corresponde a la institucion.

    Solo aplica a las instituciones que tienen ventanilla fija (ver VENTANILLA_POR_INSTITUCION).
    """
    if not {"institucion", "tipo_ventanilla"}.issubset(df.columns):
        return []
    errores = []
    for institucion, esperada in VENTANILLA_POR_INSTITUCION.items():
        filas = df[df["institucion"] == institucion]
        mal = filas[filas["tipo_ventanilla"] != esperada]
        if not mal.empty:
            errores.append(
                f"{institucion}: {len(mal)} filas con ventanilla distinta de '{esperada}'"
            )
    return errores


VALIDACIONES = (
    validar_columnas,
    validar_obligatorias,
    validar_ids_unicos,
    validar_catalogos,
    validar_montos,
    validar_fechas,
    validar_ventanilla,
)


def validar_todo(df: pd.DataFrame) -> dict[str, list[str]]:
    """Corre todas las validaciones y devuelve {nombre_validacion: [errores]}."""
    return {f.__name__: f(df) for f in VALIDACIONES}
