# Criterios de codificación

Las decisiones técnicas propias, las que no vienen del equipo de investigación. Van acá porque
condicionan el resultado tanto como los criterios acordados, y porque un valor derivado sin su
criterio escrito no es auditable: nadie puede saber después si un número salió de una regla o de
una casualidad.

Lo que decidió el equipo está en [criterios-acordados.md](criterios-acordados.md). Lo que se
descubrió y llevó a estas decisiones está en [hallazgos.md](hallazgos.md).

Cada entrada dice qué se decidió, qué alternativas había y por qué esta.

**Documento en elaboración.** Se completa a medida que el pipeline normaliza cada institución.

Última actualización: 6 de septiembre de 2026.

---

## Identificación de BID Lab

**Decidido:** BID Lab se identifica por código de instrumento dentro del conjunto del BID, no por
una fuente propia, porque no la tiene.

**Alternativa descartada:** marcar las operaciones a mano, que es lo que hizo el relevamiento
anterior con 2.703 filas.

**Por qué:** la clasificación automática reproduce exactamente ese conjunto manual, sin una sola
discordancia, e identifica 591 operaciones adicionales. El criterio es auditable y el manual no.
Ver el la identificación por código de instrumento.

## Deduplicación de la IFC

**Decidido:** pendiente de definir cuál documento prevalece cuando dos del mismo proyecto difieren.

**El problema:** el portal de la IFC publica una fila por documento, no por operación, y la fuente
actual devuelve 7.088 filas a nivel documento. La normalización tiene que colapsar a una fila por
proyecto, y eso obliga a elegir.

**Por qué queda abierto:** es una decisión de criterio, no una regla mecánica. El código heredado
concatenaba los valores distintos, que evita perder información pero produce campos que no se
pueden agregar. La fuente publica una fila por documento y varios documentos
comparten operación.

## Monedas y montos

**Decidido:** cada operación conserva `moneda_original` y `monto_original`, y lleva además
`monto_aprobado_usd` en dólares corrientes.

**Alternativa descartada:** guardar solo el monto en dólares.

**Por qué:** perder la moneda original impide auditar la conversión y hace irreproducible
cualquier revisión del tipo de cambio. El criterio lo fijó la dirección; el detalle está en
criterios-acordados.md. La conversión a dólares constantes queda fuera de esta etapa.

## Versión del punto de acceso

**Decidido:** cada descarga registra en su manifiesto qué versión del servicio usó, además del
origen, la fecha y la cantidad de registros.

**Por qué:** el Banco Mundial mantiene dos versiones de su interfaz operando en paralelo, que
devuelven 22.729 y 28.081 proyectos, y la más completa no figura en la documentación oficial. Dos
personas consultando "la API del Banco Mundial" pueden obtener corpus distintos sin enterarse. Ver
el Banco Mundial mantiene dos versiones de su interfaz operando en paralelo, que
devuelven 22.729 y 28.081 proyectos, y la más completa no figura en su documentación oficial.

## Control de completitud

**Decidido:** no se fija nunca un conteo esperado de filas como control de completitud. Se registra
el conteo obtenido con su fecha.

**Por qué:** los conjuntos son vivos. El archivo del BID cambia de tamaño entre descargas. Un
conteo fijo produce una falla falsa en cada actualización y esconde las reales.

## Estados de operación

**Decidido:** se excluyen las canceladas. El mapeo del catálogo de estados de cada institución a un
catálogo común es una decisión de criterio y se documenta acá cuando se implemente.

**Pendiente:** si entran las de preparación o pipeline. En el Banco Mundial son 292 desde 2014,
cerca del 4% del período. Está consultado al equipo.

## Unidades de monto: cada institución publica en la suya

**Decidido:** la normalización convierte todo a **unidades de dólar**, no a millones, y el programa
de cada institución es responsable de su propia conversión.

**Por qué hace falta decirlo.** El perfilado encontró tres convenciones distintas conviviendo
en el corpus. La IFC publica **en millones**: su campo de monto aprobado por el directorio dice 0,35
para una operación de 350.000 dólares. El AIIB publica **como texto**, del tipo "USD100 million".
CAF, MIGA, el BID y el Banco Mundial publican en unidades.

Sumar sin convertir da un resultado que parece plausible y está mal por seis órdenes de magnitud en
las filas de la IFC. Es el mismo error que se documentó para la base heredada de CAF.

**Control asociado:** el esquema declara que `monto_aprobado_usd` está en unidades de dólar. Conviene
un test que falle si el promedio de una institución cae por debajo de un umbral razonable, porque
eso es la señal de que quedó en millones.

## Sectores de CAF: vienen en código, no en texto

**Decidido:** los sectores de CAF requieren traducción desde el catálogo numérico del estándar IATI
antes de poder cruzarse con los del resto.

**Por qué:** CAF publica en IATI, y ese estándar codifica el sector como número. Las demás fuentes lo
publican como texto. Sin traducción, CAF queda fuera de cualquier comparación sectorial.

## Series sectoriales largas: verificar desde cuándo existe la categoría

**Decidido:** ninguna serie sectorial se publica sin antes verificar en qué año aparece cada
categoría en el dato.

**Por qué:** se verificó que los tres subsectores climáticos del BID nacen entre 2011 y
2012. Una serie que arranque antes muestra un crecimiento que es artefacto de la taxonomía, no del
fenómeno. El período del proyecto, 2014-2025, queda a salvo, pero el control tiene que existir.

## Unidad de análisis: no siempre es la operación

**Decidido:** cada institución declara su unidad de análisis en el catálogo de fuentes, y la
normalización la lleva a operación antes de consolidar.

**Por qué:** la IFC publica una fila por documento y varios documentos comparten operación, así que
sus 7.088 filas no son 7.088 operaciones. MIGA publica garantías emitidas, que no son préstamos.
Contar filas sin mirar la unidad produce comparaciones falsas entre bancos.
