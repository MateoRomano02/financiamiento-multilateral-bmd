"""Esquema armonizado de proyectos aprobados por bancos multilaterales de desarrollo.

Toda base, venga del banco que venga, se normaliza a estas columnas antes de consolidarse.
Los catalogos cerrados existen para que un valor nuevo e inesperado falle ruidosamente en los
tests en vez de colarse silenciosamente a la base final.

BORRADOR: los catalogos se ajustan cuando el perfilado de las bases heredadas confirme que
valores reales usa cada banco (ver docs/perfil-bases.md). Todo cambio se documenta en
docs/criterios-codificacion.md.
"""

from __future__ import annotations

# Columnas del esquema comun, en orden. El pipeline de cada banco debe producir exactamente estas.
COLUMNAS: tuple[str, ...] = (
    # Identificacion de la institucion
    "banco_grupo",            # GBM | GBID | CAF | NDB | AIIB
    "institucion",            # BIRF, IDA, IFC, MIGA, BID, BID Invest, BID Lab, CAF, NDB, AIIB
    "tipo_ventanilla",        # soberana | no_soberana
    # Identificacion del proyecto
    "id_proyecto",            # identificador del banco; unico dentro de la institucion
    "nombre",
    "pais",
    "url_proyecto",           # ficha publica del proyecto, para poder auditar cada fila
    # Fechas y estado
    "fecha_aprobacion",       # date
    "anio_aprobacion",        # int, derivado de fecha_aprobacion
    "estado",                 # catalogo comun, ver ESTADOS
    "estado_original",        # texto tal cual lo publica el banco, sin traducir
    # Montos
    "monto_aprobado_usd",     # float, unidades de dolar (NO millones)
    "monto_desembolsado_usd", # float, unidades de dolar; nulo si el banco no lo publica
    "moneda_original",        # ISO 4217
    "monto_original",         # float, en moneda_original
    # Clasificacion del banco
    "instrumento",            # prestamo, garantia, inversion de capital, cooperacion tecnica...
    "sector",                 # sector tal cual lo clasifica el banco
    # Trazabilidad
    "fuente_url",             # de donde se obtuvo el dato
    "fecha_relevamiento",     # date ISO de la descarga
    # Reservadas para la clasificacion tematica del equipo de investigacion (nice-to-have)
    "clasificacion_te",
    "categoria_te",
)

BANCOS_GRUPO = ("GBM", "GBID", "CAF", "NDB", "AIIB")

TIPOS_VENTANILLA = ("soberana", "no_soberana")

# Mapeo institucion -> ventanilla. Fijo por diseno institucional: el BIRF presta a Estados,
# la IFC a empresas. Sirve como validacion cruzada del dato relevado.
VENTANILLA_POR_INSTITUCION: dict[str, str] = {
    "BIRF": "soberana",
    "IDA": "soberana",
    "IFC": "no_soberana",
    "MIGA": "no_soberana",
    "BID": "soberana",
    "BID Invest": "no_soberana",
    "BID Lab": "no_soberana",
    # CAF, NDB y AIIB operan ambas ventanillas sin separarlas institucionalmente:
    # su ventanilla se determina fila por fila, no por institucion.
}

# Catalogo comun de estados. El valor original del banco se preserva en estado_original.
ESTADOS = (
    "propuesto",       # en preparacion, aun no aprobado por el directorio
    "aprobado",        # aprobado, sin desembolsos todavia
    "en_implementacion",
    "cerrado",         # completado
    "cancelado",       # incluye retirado y rechazado
    "desconocido",     # el banco no publica estado, o el valor no mapea a ninguno de los anteriores
)

# Corte temporal del relevamiento: 2014 es un anio antes del Acuerdo de Paris (2015).
ANIO_INICIO = 2014

# Columnas que nunca pueden venir vacias: sin ellas la fila no es analizable.
COLUMNAS_OBLIGATORIAS = (
    "banco_grupo",
    "institucion",
    "id_proyecto",
    "pais",
    "fecha_aprobacion",
    "monto_aprobado_usd",
    "fuente_url",
    "fecha_relevamiento",
)
