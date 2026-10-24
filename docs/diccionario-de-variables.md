# Diccionario de variables del corpus consolidado

Generado por `scripts/diccionario_variables.py` a partir de las definiciones de `src/common/esquema.py` y del corpus del período 2014 a 2025. No se edita a mano: si una definición cambia, se cambia en el esquema y se regenera.

El corpus tiene 18.930 operaciones de 12 ventanillas y 30 variables.

## Institución

| Variable | Definición | Tipo | Obligatoria |
|---|---|---|---|
| `banco_grupo` | Grupo bancario al que pertenece la ventanilla: GBM, GBID, CAF, NDB, AIIB, FONPLATA o BCIE. | texto | sí |
| `institucion` | Ventanilla concreta que aprobó la operación, por ejemplo BIRF o BID Invest. | texto | sí |
| `tipo_ventanilla` | Soberana si presta a Estados, no soberana si presta a empresas o bancos. En la mayoría de las instituciones es fija por diseño; en el AIIB y el NDB la fuente la declara fila por fila. | texto | no |
| `tipo_prestatario` | Quién recibe el préstamo en CAF, FONPLATA y BCIE, que no publican la ventanilla: soberana (Estado nacional), no_soberana (empresa o banco privado), subnacional, banco_publico, empresa_publica, multilateral o sin_dato. Sale de reglas sobre el nombre del prestatario; las tres categorías intermedias quedan para revisión y no se cuentan en ninguna ventanilla. | texto | no |
| `prestatario` | Nombre del prestatario o, en CAF, del ejecutor, tal como lo publica la fuente IATI. | texto | no |

## Proyecto

| Variable | Definición | Tipo | Obligatoria |
|---|---|---|---|
| `id_proyecto` | Identificador que le asigna el banco. Es único dentro de cada institución, no entre ellas. | texto | sí |
| `nombre` | Nombre de la operación tal como lo publica el banco. | texto | no |
| `descripcion` | Descripción u objetivo de la operación tal como lo publica el banco, en texto plano. El Banco Mundial publica el resumen del proyecto, el BID el objetivo y los bancos IATI la descripción de la actividad. La IFC, MIGA, el AIIB y el NDB no la traen en sus descargas. | texto | no |
| `pais` | País receptor, o una etiqueta de agregado regional cuando la operación financia varios países a la vez. | texto | sí |
| `url_proyecto` | Ficha pública de la operación, para poder auditar cada fila contra la fuente. | texto | no |

## Fechas y estado

| Variable | Definición | Tipo | Obligatoria |
|---|---|---|---|
| `fecha_aprobacion` | Fecha de aprobación del directorio, en formato ISO. Es la que ordena las series anuales. | fecha | sí |
| `anio_aprobacion` | Año de la fecha de aprobación. | entero | no |
| `anio_fiscal` | Año fiscal del banco cuando no coincide con el calendario. En el Grupo Banco Mundial va de julio a junio y lleva el número del año en que termina, que es como cierran sus informes anuales. Vacío en los bancos que usan año calendario. | número | no |
| `estado` | Estado de la operación en el catálogo común: propuesto, aprobado, en implementación, cerrado, cancelado o desconocido. | texto | no |
| `estado_original` | Estado tal como lo publica el banco, sin traducir, para poder revisar el mapeo al catálogo común. | texto | no |

## Montos

| Variable | Definición | Tipo | Obligatoria |
|---|---|---|---|
| `monto_aprobado_usd` | Monto comprometido por el banco al aprobar la operación, en dólares corrientes y en unidades, no en millones. Si la fuente publica en otra moneda, se convierte con el promedio anual del tipo de cambio del año de aprobación. | número | sí |
| `monto_aprobado_original_usd` | Monto que aprobó el directorio en la aprobación, antes de cancelaciones parciales, cuando la fuente lo publica aparte del vigente, en dólares corrientes y en unidades. Hoy solo el NDB, desde el anexo de su informe anual; en el resto de las instituciones queda vacío. | número | no |
| `monto_desembolsado_usd` | Monto efectivamente desembolsado hasta la fecha de la fuente, en dólares corrientes. Queda vacío cuando el banco no lo publica. | número | no |
| `moneda_original` | Moneda en que la fuente publica el monto, en código ISO 4217. | texto | no |
| `monto_original` | Monto en su moneda original, antes de convertir a dólares. | número | no |
| `costo_total_proyecto_usd` | Costo total del proyecto, que incluye el aporte del banco más el de otras fuentes y la contraparte local. Permite medir qué proporción del proyecto financia el banco. Lo traen el BID y BID Lab (campo estructurado), el Banco Mundial (BIRF e IDA, campo lendprojectcost, anotado en una sola fila por proyecto aunque tenga fila BIRF e IDA) y el NDB (en prosa, en una minoría de fichas). IFC, MIGA, BID Invest, CAF, FONPLATA, BCIE y AIIB no lo publican. | número | no |
| `aporte_terceros_usd` | Fondos de otros aportantes que acompañan la operación, aparte del monto aprobado por el banco. Banco Mundial: donaciones de fondos fiduciarios y donantes que el banco administra (campo grantamt), en una sola fila por proyecto. NDB: lo que ponen otras fuentes según la tabla de aportantes de la ficha, convertido a dólares. El resto de las instituciones no lo publican; el BID publica el costo total pero no discrimina quién pone la diferencia. | número | no |

## Clasificación del banco

| Variable | Definición | Tipo | Obligatoria |
|---|---|---|---|
| `instrumento` | Tipo de operación según el banco: préstamo, garantía, inversión de capital, cooperación técnica. | texto | no |
| `forma_financiamiento` | Forma del financiamiento con el criterio acordado: prestamo, donacion, garantia u otro (capital accionario, bonos, gestión de riesgo), y mixto si la operación combina más de una sin separar el monto. Sale del campo de cada fuente, o de un cruce con otra base cuando la fuente no lo trae (BIRF e IDA con el estado de préstamos, BID Invest con la ficha del BID que cita); en FONPLATA y BCIE la fuente declara préstamo para todas sus operaciones, y en el AIIB y el NDB queda vacía porque no la publican. | texto | no |
| `sector` | Sector tal como lo clasifica el banco. Cada institución usa su propio catálogo, así que no es comparable entre bancos. | texto | no |

## Trazabilidad

| Variable | Definición | Tipo | Obligatoria |
|---|---|---|---|
| `fuente_url` | Dirección de la descarga de la que salió la fila. | texto | sí |
| `fecha_relevamiento` | Fecha de esa descarga, en formato ISO. | fecha | sí |
| `origen_fila` | Solo CAF: de dónde sale la fila. iati si viene del archivo IATI (2026, y los años anteriores que las otras dos bases no cubren), heredada si viene de la base del relevamiento 2022 reconstruida desde los informes anuales (2014-2022), informe si viene del listado de operaciones de los informes anuales 2023-2025, heredada_iati o informe_iati si esa fila cruzó con una operación IATI y tomó sus atributos. Vacío en el resto de las instituciones. | texto | no |

## Reservadas

| Variable | Definición | Tipo | Obligatoria |
|---|---|---|---|
| `clasificacion_te` | Reservada para la clasificación temática del equipo de investigación. Hoy vacía. | número | no |
| `categoria_te` | Reservada para la categoría temática del equipo de investigación. Hoy vacía. | número | no |

## Cobertura por ventanilla

Porcentaje de operaciones con la variable informada. Solo se listan las variables que no están completas en todas las ventanillas.

| Variable | AIIB | BCIE | BID | BID Invest | BID Lab | BIRF | CAF | FONPLATA | IDA | IFC | MIGA | NDB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `tipo_ventanilla` | 100% | 87% | 100% | 100% | 100% | 100% | 77% | 53% | 100% | 100% | 100% | 100% |
| `tipo_prestatario` | 0% | 100% | 0% | 0% | 0% | 0% | 100% | 100% | 0% | 0% | 0% | 0% |
| `prestatario` | 0% | 100% | 0% | 0% | 0% | 0% | 96% | 84% | 0% | 0% | 0% | 0% |
| `descripcion` | 0% | 100% | 100% | 97% | 100% | 82% | 71% | 100% | 75% | 0% | 0% | 0% |
| `pais` | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| `url_proyecto` | 100% | 96% | 0% | 100% | 0% | 100% | 17% | 0% | 100% | 100% | 0% | 100% |
| `anio_fiscal` | 0% | 0% | 0% | 0% | 0% | 100% | 0% | 0% | 100% | 100% | 100% | 0% |
| `estado_original` | 100% | 100% | 100% | 100% | 100% | 100% | 17% | 100% | 100% | 100% | 0% | 100% |
| `monto_aprobado_usd` | 99% | 100% | 100% | 88% | 100% | 100% | 100% | 100% | 100% | 100% | 99% | 100% |
| `monto_aprobado_original_usd` | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 88% |
| `monto_desembolsado_usd` | 43% | 77% | 0% | 0% | 0% | 79% | 16% | 97% | 65% | 0% | 0% | 0% |
| `moneda_original` | 99% | 100% | 0% | 99% | 0% | 0% | 0% | 100% | 0% | 0% | 0% | 100% |
| `monto_original` | 99% | 100% | 0% | 88% | 0% | 0% | 0% | 100% | 0% | 0% | 0% | 100% |
| `costo_total_proyecto_usd` | 0% | 0% | 100% | 0% | 100% | 79% | 0% | 0% | 83% | 0% | 0% | 22% |
| `aporte_terceros_usd` | 0% | 0% | 0% | 0% | 0% | 16% | 0% | 0% | 21% | 0% | 0% | 6% |
| `instrumento` | 0% | 0% | 100% | 78% | 100% | 0% | 88% | 0% | 0% | 99% | 100% | 100% |
| `forma_financiamiento` | 0% | 100% | 100% | 84% | 100% | 99% | 99% | 100% | 93% | 99% | 100% | 0% |
| `sector` | 100% | 100% | 97% | 94% | 100% | 100% | 70% | 100% | 100% | 100% | 100% | 100% |
| `origen_fila` | 0% | 0% | 0% | 0% | 0% | 0% | 100% | 0% | 0% | 0% | 0% | 0% |

Vacías en todas las ventanillas: `clasificacion_te`, `categoria_te`.
