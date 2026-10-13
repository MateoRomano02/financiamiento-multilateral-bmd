"""Esquema armonizado de proyectos aprobados por bancos multilaterales de desarrollo.

Toda base, venga del banco que venga, se normaliza a estas columnas antes de consolidarse.
Los catalogos cerrados existen para que un valor nuevo e inesperado falle ruidosamente en los
tests en vez de colarse silenciosamente a la base final.

BORRADOR: los catalogos se ajustan cuando el perfilado de las bases heredadas confirme que
valores reales usa cada banco (ver docs/perfil-bases.md). Todo cambio se documenta en
docs/criterios-codificacion.md.
"""

from __future__ import annotations

# Variables del esquema comun, en orden, con su grupo y su definicion. Es la unica fuente de las
# definiciones: el diccionario de variables se genera desde aca (scripts/diccionario_variables.py),
# asi que cambiar una definicion es cambiarla en un solo lugar. El pipeline de cada banco debe
# producir exactamente estas columnas.
VARIABLES: dict[str, tuple[str, str]] = {
    "banco_grupo": ("Institución",
        "Grupo bancario al que pertenece la ventanilla: GBM, GBID, CAF, NDB, AIIB, FONPLATA o BCIE."),
    "institucion": ("Institución",
        "Ventanilla concreta que aprobó la operación, por ejemplo BIRF o BID Invest."),
    "tipo_ventanilla": ("Institución",
        "Soberana si presta a Estados, no soberana si presta a empresas o bancos. En la mayoría de "
        "las instituciones es fija por diseño; en el AIIB y el NDB la fuente la declara fila por fila."),
    "tipo_prestatario": ("Institución",
        "Quién recibe el préstamo en CAF, FONPLATA y BCIE, que no publican la ventanilla: soberana "
        "(Estado nacional), no_soberana (empresa o banco privado), subnacional, banco_publico, "
        "empresa_publica, multilateral o sin_dato. Sale de reglas sobre el nombre del prestatario; "
        "las tres categorías intermedias quedan para revisión y no se cuentan en ninguna ventanilla."),
    "prestatario": ("Institución",
        "Nombre del prestatario o, en CAF, del ejecutor, tal como lo publica la fuente IATI."),
    "id_proyecto": ("Proyecto",
        "Identificador que le asigna el banco. Es único dentro de cada institución, no entre ellas."),
    "nombre": ("Proyecto", "Nombre de la operación tal como lo publica el banco."),
    "descripcion": ("Proyecto",
        "Descripción u objetivo de la operación tal como lo publica el banco, en texto plano. El "
        "Banco Mundial publica el resumen del proyecto, el BID el objetivo y los bancos IATI la "
        "descripción de la actividad. La IFC, MIGA, el AIIB y el NDB no la traen en sus descargas."),
    "pais": ("Proyecto",
        "País receptor, o una etiqueta de agregado regional cuando la operación financia varios "
        "países a la vez."),
    "url_proyecto": ("Proyecto",
        "Ficha pública de la operación, para poder auditar cada fila contra la fuente."),
    "fecha_aprobacion": ("Fechas y estado",
        "Fecha de aprobación del directorio, en formato ISO. Es la que ordena las series anuales."),
    "anio_aprobacion": ("Fechas y estado", "Año de la fecha de aprobación."),
    "anio_fiscal": ("Fechas y estado",
        "Año fiscal del banco cuando no coincide con el calendario. En el Grupo Banco Mundial va de "
        "julio a junio y lleva el número del año en que termina, que es como cierran sus informes "
        "anuales. Vacío en los bancos que usan año calendario."),
    "estado": ("Fechas y estado",
        "Estado de la operación en el catálogo común: propuesto, aprobado, en implementación, "
        "cerrado, cancelado o desconocido."),
    "estado_original": ("Fechas y estado",
        "Estado tal como lo publica el banco, sin traducir, para poder revisar el mapeo al catálogo común."),
    "monto_aprobado_usd": ("Montos",
        "Monto comprometido por el banco al aprobar la operación, en dólares corrientes y en "
        "unidades, no en millones. Si la fuente publica en otra moneda, se convierte con el "
        "promedio anual del tipo de cambio del año de aprobación."),
    "monto_aprobado_original_usd": ("Montos",
        "Monto que aprobó el directorio en la aprobación, antes de cancelaciones parciales, cuando "
        "la fuente lo publica aparte del vigente, en dólares corrientes y en unidades. Hoy solo el "
        "NDB, desde el anexo de su informe anual; en el resto de las instituciones queda vacío."),
    "monto_desembolsado_usd": ("Montos",
        "Monto efectivamente desembolsado hasta la fecha de la fuente, en dólares corrientes. "
        "Queda vacío cuando el banco no lo publica."),
    "moneda_original": ("Montos", "Moneda en que la fuente publica el monto, en código ISO 4217."),
    "monto_original": ("Montos", "Monto en su moneda original, antes de convertir a dólares."),
    "costo_total_proyecto_usd": ("Montos",
        "Costo total del proyecto, que incluye el aporte del banco más el de otras fuentes y la "
        "contraparte local. Permite medir qué proporción del proyecto financia el banco. Lo traen "
        "el BID y BID Lab (campo estructurado), el Banco Mundial (BIRF e IDA, campo lendprojectcost, "
        "anotado en una sola fila por proyecto aunque tenga fila BIRF e IDA) y el NDB (en prosa, "
        "en una minoría de fichas). IFC, MIGA, BID Invest, CAF, FONPLATA, BCIE y AIIB no lo publican."),
    "aporte_terceros_usd": ("Montos",
        "Fondos de otros aportantes que acompañan la operación, aparte del monto aprobado por el "
        "banco. Banco Mundial: donaciones de fondos fiduciarios y donantes que el banco administra "
        "(campo grantamt), en una sola fila por proyecto. NDB: lo que ponen otras fuentes según la "
        "tabla de aportantes de la ficha, convertido a dólares. El resto de las instituciones no lo "
        "publican; el BID publica el costo total pero no discrimina quién pone la diferencia."),
    "instrumento": ("Clasificación del banco",
        "Tipo de operación según el banco: préstamo, garantía, inversión de capital, cooperación técnica."),
    "forma_financiamiento": ("Clasificación del banco",
        "Forma del financiamiento con el criterio de la dirección: prestamo, donacion, garantia u otro "
        "(capital accionario, bonos, gestión de riesgo), y mixto si la operación combina más de una "
        "sin separar el monto. Sale del campo de cada fuente, o de un cruce con otra base cuando la fuente no lo trae (BIRF e IDA con el estado de préstamos, BID Invest con la ficha del BID que cita); en FONPLATA y BCIE la fuente declara "
        "préstamo para todas sus operaciones, y en el AIIB y el NDB queda vacía porque no la publican."),
    "sector": ("Clasificación del banco",
        "Sector tal como lo clasifica el banco. Cada institución usa su propio catálogo, así que no "
        "es comparable entre bancos."),
    "fuente_url": ("Trazabilidad", "Dirección de la descarga de la que salió la fila."),
    "fecha_relevamiento": ("Trazabilidad", "Fecha de esa descarga, en formato ISO."),
    "origen_fila": ("Trazabilidad",
        "Solo CAF: de dónde sale la fila. iati si viene del archivo IATI (2023 en adelante, y los "
        "años anteriores que la base heredada no cubre), heredada si viene de la base del "
        "relevamiento 2022 reconstruida desde los informes anuales, heredada_iati si esa fila cruzó con "
        "una operación IATI y tomó sus atributos. Vacío en el resto de las instituciones."),
    "clasificacion_te": ("Reservadas",
        "Reservada para la clasificación temática del equipo de investigación. Hoy vacía."),
    "categoria_te": ("Reservadas",
        "Reservada para la categoría temática del equipo de investigación. Hoy vacía."),
}

COLUMNAS: tuple[str, ...] = tuple(VARIABLES)

BANCOS_GRUPO = ("GBM", "GBID", "CAF", "NDB", "AIIB", "FONPLATA", "BCIE")

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
