# Diccionario de variables del corpus consolidado

Generado por `scripts/diccionario_variables.py` el 2026-09-29, a partir de las definiciones de `src/common/esquema.py` y del corpus del período 2014 a 2025. No se edita a mano: si una definición cambia, se cambia en el esquema y se regenera.

El corpus tiene 17.796 operaciones de 12 ventanillas y 22 variables.

## Institución

| Variable | Definición | Tipo | Obligatoria |
|---|---|---|---|
| `banco_grupo` | Grupo bancario al que pertenece la ventanilla: GBM, GBID, CAF, NDB, AIIB, FONPLATA o BCIE. | texto | sí |
| `institucion` | Ventanilla concreta que aprobó la operación, por ejemplo BIRF o BID Invest. | texto | sí |
| `tipo_ventanilla` | Soberana si presta a Estados, no soberana si presta a empresas o bancos. En la mayoría de las instituciones es fija por diseño; en el AIIB y el NDB la fuente la declara fila por fila. | texto | no |

## Proyecto

| Variable | Definición | Tipo | Obligatoria |
|---|---|---|---|
| `id_proyecto` | Identificador que le asigna el banco. Es único dentro de cada institución, no entre ellas. | texto | sí |
| `nombre` | Nombre de la operación tal como lo publica el banco. | texto | no |
| `pais` | País receptor, o una etiqueta de agregado regional cuando la operación financia varios países a la vez. | texto | sí |
| `url_proyecto` | Ficha pública de la operación, para poder auditar cada fila contra la fuente. | texto | no |

## Fechas y estado

| Variable | Definición | Tipo | Obligatoria |
|---|---|---|---|
| `fecha_aprobacion` | Fecha de aprobación del directorio, en formato ISO. Es la que ordena las series anuales. | fecha | sí |
| `anio_aprobacion` | Año de la fecha de aprobación. | entero | no |
| `estado` | Estado de la operación en el catálogo común: propuesto, aprobado, en implementación, cerrado, cancelado o desconocido. | texto | no |
| `estado_original` | Estado tal como lo publica el banco, sin traducir, para poder revisar el mapeo al catálogo común. | texto | no |

## Montos

| Variable | Definición | Tipo | Obligatoria |
|---|---|---|---|
| `monto_aprobado_usd` | Monto comprometido por el banco al aprobar la operación, en dólares corrientes y en unidades, no en millones. Si la fuente publica en otra moneda, se convierte con el promedio anual del tipo de cambio del año de aprobación. | número | sí |
| `monto_desembolsado_usd` | Monto efectivamente desembolsado hasta la fecha de la fuente, en dólares corrientes. Queda vacío cuando el banco no lo publica. | número | no |
| `moneda_original` | Moneda en que la fuente publica el monto, en código ISO 4217. | texto | no |
| `monto_original` | Monto en su moneda original, antes de convertir a dólares. | número | no |
| `costo_total_proyecto_usd` | Costo total del proyecto, que incluye el aporte del banco más el de otras fuentes y la contraparte local. Permite medir qué proporción del proyecto financia el banco. | número | no |

## Clasificación del banco

| Variable | Definición | Tipo | Obligatoria |
|---|---|---|---|
| `instrumento` | Tipo de operación según el banco: préstamo, garantía, inversión de capital, cooperación técnica. | texto | no |
| `sector` | Sector tal como lo clasifica el banco. Cada institución usa su propio catálogo, así que no es comparable entre bancos. | texto | no |

## Trazabilidad

| Variable | Definición | Tipo | Obligatoria |
|---|---|---|---|
| `fuente_url` | Dirección de la descarga de la que salió la fila. | texto | sí |
| `fecha_relevamiento` | Fecha de esa descarga, en formato ISO. | fecha | sí |

## Reservadas

| Variable | Definición | Tipo | Obligatoria |
|---|---|---|---|
| `clasificacion_te` | Reservada para la clasificación temática del equipo de investigación. Hoy vacía. | número | no |
| `categoria_te` | Reservada para la categoría temática del equipo de investigación. Hoy vacía. | número | no |

## Cobertura por ventanilla

Porcentaje de operaciones con la variable informada. Solo se listan las variables que no están completas en todas las ventanillas.

| Variable | AIIB | BCIE | BID | BID Invest | BID Lab | BIRF | CAF | FONPLATA | IDA | IFC | MIGA | NDB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `tipo_ventanilla` | 100% | 0% | 100% | 100% | 100% | 100% | 0% | 0% | 100% | 100% | 100% | 100% |
| `pais` | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| `url_proyecto` | 100% | 96% | 0% | 100% | 0% | 100% | 100% | 0% | 100% | 100% | 62% | 100% |
| `estado_original` | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 0% | 94% |
| `monto_aprobado_usd` | 99% | 100% | 100% | 88% | 100% | 100% | 100% | 100% | 100% | 100% | 99% | 94% |
| `monto_desembolsado_usd` | 0% | 77% | 0% | 0% | 0% | 79% | 46% | 97% | 65% | 0% | 0% | 0% |
| `moneda_original` | 99% | 100% | 0% | 99% | 0% | 0% | 100% | 100% | 0% | 0% | 0% | 94% |
| `monto_original` | 99% | 100% | 0% | 88% | 0% | 0% | 100% | 100% | 0% | 0% | 0% | 94% |
| `costo_total_proyecto_usd` | 0% | 0% | 100% | 0% | 100% | 0% | 0% | 0% | 0% | 0% | 0% | 23% |
| `instrumento` | 0% | 0% | 100% | 78% | 100% | 0% | 0% | 0% | 0% | 99% | 100% | 100% |
| `sector` | 100% | 100% | 97% | 94% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |

Vacías en todas las ventanillas: `clasificacion_te`, `categoria_te`.
