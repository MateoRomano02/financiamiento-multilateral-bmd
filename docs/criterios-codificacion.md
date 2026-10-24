# Criterios de codificación

Las decisiones técnicas de codificación. Van acá porque condicionan el resultado y porque un valor derivado sin su
criterio escrito no es auditable: nadie puede saber después si un número salió de una regla o de
una casualidad.

Cada entrada dice qué se decidió, qué alternativas había y por qué esta.

**Documento en elaboración.** Se completa a medida que el pipeline normaliza cada institución.

Última actualización: 29 de septiembre de 2026.

---

## Identificación de BID Lab

**Decidido:** BID Lab se identifica por código de instrumento dentro del conjunto del BID, no por
una fuente propia, porque no la tiene.

**Alternativa descartada:** marcar las operaciones a mano, que es lo que hizo el relevamiento
anterior con 2.703 filas.

**Por qué:** la clasificación automática reproduce exactamente ese conjunto manual, sin una sola
discordancia, e identifica 591 operaciones adicionales. El criterio es auditable y el manual no.

## Deduplicación de la IFC

**Decidido:** pendiente de definir cuál documento prevalece cuando dos del mismo proyecto difieren.

**El problema:** el portal de la IFC publica una fila por documento, no por operación, y la fuente
actual devuelve 7.088 filas a nivel documento. La normalización tiene que colapsar a una fila por
proyecto, y eso obliga a elegir.

**Por qué queda abierto:** es una decisión de criterio, no una regla mecánica. El código heredado
concatenaba los valores distintos, que evita perder información pero produce campos que no se
pueden agregar.

## Monedas y montos

**Decidido:** cada operación conserva `moneda_original` y `monto_original`, y lleva además
`monto_aprobado_usd` en dólares corrientes.

**Alternativa descartada:** guardar solo el monto en dólares.

**Por qué:** perder la moneda original impide auditar la conversión y hace irreproducible
cualquier revisión del tipo de cambio. La conversión a dólares constantes queda fuera de esta etapa.

## Versión del punto de acceso

**Decidido:** cada descarga registra en su manifiesto qué versión del servicio usó, además del
origen, la fecha y la cantidad de registros.

**Por qué:** el Banco Mundial mantiene dos versiones de su interfaz operando en paralelo, que
devuelven 22.729 y 28.081 proyectos, y la más completa no figura en la documentación oficial. Dos
personas consultando "la API del Banco Mundial" pueden obtener corpus distintos sin enterarse.

## Control de completitud

**Decidido:** no se fija nunca un conteo esperado de filas como control de completitud. Se registra
el conteo obtenido con su fecha.

**Por qué:** los conjuntos son vivos. El archivo del BID cambia de tamaño entre descargas. Un
conteo fijo produce una falla falsa en cada actualización y esconde las reales.

## Estados de operación

**Decidido:** se excluyen las canceladas. El mapeo del catálogo de estados de cada institución a un
catálogo común es una decisión de criterio y se documenta acá cuando se implemente.

**Pendiente:** si entran las de preparación o pipeline. En el Banco Mundial son 292 desde 2014,
cerca del 4% del período.

## Unidades de monto: cada institución publica en la suya

**Decidido:** la normalización convierte todo a **unidades de dólar**, no a millones, y el programa
de cada institución es responsable de su propia conversión.

**Por qué hace falta decirlo.** El perfilado del 6/9 encontró tres convenciones distintas conviviendo
en el corpus. La IFC publica **en millones**: su campo de monto aprobado por el directorio dice 0,35
para una operación de 350.000 dólares. El AIIB publica **como texto**, del tipo "USD100 million".
CAF, MIGA, el BID y el Banco Mundial publican en unidades.

Sumar sin convertir da un resultado que parece plausible y está mal por seis órdenes de magnitud en
las filas de la IFC.

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

**Por qué:** los tres subsectores climáticos del BID nacen entre 2011 y
2012. Una serie que arranque antes muestra un crecimiento que es artefacto de la taxonomía, no del
fenómeno. El período del proyecto, 2014-2025, queda a salvo, pero el control tiene que existir.

## Unidad de análisis: no siempre es la operación

**Decidido:** cada institución declara su unidad de análisis en el catálogo de fuentes, y la
normalización la lleva a operación antes de consolidar.

**Por qué:** la IFC publica una fila por documento y varios documentos comparten operación, así que
sus 7.088 filas no son 7.088 operaciones. MIGA publica garantías emitidas, que no son préstamos.
Contar filas sin mirar la unidad produce comparaciones falsas entre bancos.

## Separación de BIRF e IDA

**Decidido:** se separan por el compromiso de cada ventanilla, `curr_ibrd_commitment` para BIRF e
`idacommamt` para IDA. Una operación con compromiso de las dos **genera dos filas**, una por
institución, cada una con su monto.

**Alternativa descartada:** asignar la operación entera a la ventanilla de mayor monto. Eso
distorsiona los totales por institución, que es justamente lo que el informe compara.

**Por qué importa el detalle:** el nombre `ibrdcommamt` que figuraba en nuestra lista no existe en
el servicio y volvía vacío en silencio.

## Deduplicación, una regla por fuente

Ninguna fuente publica exactamente una fila por operación, y cada una se desvía de forma distinta.

**BID Invest publica una fila por idioma.** Sus 4.757 filas son 2.084 operaciones en inglés, español
y portugués. Se conserva el inglés. Las 245 que aún se repiten dentro del inglés difieren solo en la
fecha de directorio y se toma la primera.

**MIGA publica una fila por garantía emitida, no por proyecto.** Un mismo proyecto puede tener
varias, incluso en el mismo año fiscal. El identificador se compone con el proyecto, el año y un
correlativo.

**La IFC publica a nivel documento.** En la práctica solo 17 operaciones traen más de uno, y en las
17 el monto y la fecha coinciden entre filas, así que quedarse con la primera no pierde información.

**AIIB y NDB no publican identificador.** Se usa la ruta de su ficha pública, que es única y además
permite auditar cada fila contra la fuente.

## Países: nombres, no códigos

**Decidido:** el campo país lleva el nombre, no el código.

**Por qué:** CAF publica el receptor como código ISO de dos letras y el resto del corpus usa el
nombre. Sin traducir, CAF queda fuera de cualquier agregación por país, que es media investigación.
La tabla de traducción cubre los 18 códigos que aparecen en su archivo; uno nuevo se vería como
código crudo y hay que sumarlo a mano.

## Agregados regionales: se separan, no se cuentan como país

**Decidido:** las operaciones asignadas a un agregado regional quedan fuera del cálculo de
concentración, y se reporta aparte qué porcentaje de la cartera representan.

**Por qué:** son 23 etiquetas del tipo "Regional", "World Region" o "Multicountry", que se llevan el
5% del monto del corpus. No tienen un receptor único: contarlas como si fueran un país mezclaría
"se lo lleva Brasil" con "se lo lleva una facilidad para toda la región", que es lo contrario de
concentración.

**Detalle de implementación:** se detectan por palabra completa, de modo que "South Africa",
"Central African Republic" y "Dominican Republic" no caen por error. La proporción resultante es
en sí un dato: BID Lab asigna el 41,7% de su cartera a destinos regionales y la IFC el 23,7%.

## Estados: catálogo por fuente, valor original preservado

**Decidido:** cada fuente tiene su tabla de traducción al catálogo común, y el valor tal cual lo
publica el banco se conserva siempre en `estado_original`.

**Los casos que no se fuerzan.** "Hold" en la IFC y en BID Invest, e "Inactive" en BID Invest, no
dicen si la operación sigue viva: se mapean a `desconocido` en lugar de suponer. MIGA no publica
estado en su servicio. El NDB sí lo trae en sus fichas, en 145 de 155 operaciones del período. En total son 782 operaciones en `desconocido` sobre 17.562.

**El caso que sí se interpreta.** "Dropped" en el Banco Mundial es un proyecto que no llegó a
aprobarse, y se trata como cancelado, que es lo que el criterio acordado excluye del análisis.

## Desembolsos del Banco Mundial: unión préstamo por préstamo

**Decidido.** El desembolsado del BIRF y la IDA sale del estado de préstamos de Finances
One, que publica por préstamo. Cada préstamo se asigna a la operación del corpus con el mismo
proyecto, la misma ventanilla y una fecha de aprobación a menos de 60 días, y solo si la suma del
monto original de sus préstamos está a menos de 20% del aprobado.

**Alternativas.** Sumar todos los préstamos del proyecto (le atribuía al proyecto original la plata
de sus financiamientos adicionales: 463 operaciones con más desembolsado que aprobado); unir solo
por fecha (dejaba pasar siete casos en que el préstamo vale de dos a diecisiete veces lo aprobado).

**Por qué esta.** Es la que cruza más operaciones sin atribuir plata a la operación equivocada. Lo
que no cruza queda vacío y se cuenta.

## Fuentes que dejan de publicar lo terminado: se unen las fotos

**Decidido.** Para CAF el corpus no toma la última descarga sino la unión de todas las
descargas fechadas, con la versión más nueva de cada operación. Una operación que solo está en una
foto vieja se conserva con la fecha de relevamiento de esa foto. Si una foto nueva trae el mismo
nombre y año bajo otro identificador, la versión vieja se descarta.

**Alternativas.** Usar solo la última descarga (CAF perdía la mitad de 2014-2025); fijar el
corpus a la primera descarga (perdía las 33 operaciones nuevas y las correcciones de monto y
estado de 23).

**Por qué esta.** Conserva lo que la fuente dejó de publicar sin congelar lo que actualizó. El
riesgo es contar dos veces una operación republicada con otro identificador y otro nombre; la regla
de nombre y año cubre el caso encontrado, y el comparador del pipeline avisa si CAF vuelve a cambiar
de golpe. Por ahora se aplica solo a CAF, que es donde se verificó; está en `ACUMULAN_FOTOS`.

## Forma de financiamiento, costo total y otros aportantes

**Criterios técnicos propios.** Distinguen, en el financiamiento aprobado, lo que aprueba el banco del monto total, e identifican
otros aportantes y cómo.

Forma en BIRF e IDA. Además de la unión por proyecto, un segundo cruce solo para la forma: mismo
país, misma ventanilla, aprobación a menos de 30 días y monto dentro del 5%. Se asigna únicamente si
todos los candidatos tienen la misma forma. No asigna desembolsos, porque sin el proyecto sería
adivinar. Recupera BIRF 180 de 193 e IDA 585 de 782 (la investigación estimó 593: la diferencia son
casos con candidatos de forma distinta, que se dejan vacíos). Quedan BIRF 13 e IDA 197.

Forma en BID Invest. Las operaciones sin instrumento que citan la ficha del BID
(`iadb.org/en/project/XX-L1234`) toman la forma de esa operación en el csv del BID, con la misma
lógica `_forma_bid` (incluidas las garantías dentro de Loan Operation). El enlace está en el HTML
escapado de la descripción y la limpieza de texto lo borra, por eso se busca en la descripción cruda.
El csv del BID se lee aparte (una vez, con caché) en lugar de depender del orden de normalización.
Si una descripción cita varias fichas con formas distintas, no se asigna. Quedan 145 sin forma.

Costo total del Banco Mundial. `lendprojectcost` va a `costo_total_proyecto_usd` en una sola fila por
proyecto (la primera, BIRF si el proyecto tiene las dos), igual que `aporte_terceros_usd`: es un dato
del proyecto y sumarlo en cada ventanilla lo duplicaría. Alternativa descartada: repetirlo en las dos
filas, que da proporciones por ventanilla pero duplica el costo en 384 proyectos mixtos. Consecuencia
para `aporte_del_banco`: el aporte del banco de una fila que lleva el costo es la suma de BIRF e IDA
del proyecto, y se atribuye a la institución de esa fila. Por eso los porcentajes por institución del
Banco Mundial mezclan las dos ventanillas en los proyectos mixtos. Salvedad: `lendprojectcost` es el
costo del proyecto o programa financiado, y en operaciones por resultados es el programa nacional
entero (por ejemplo, 200.000 M de dólares en P181649, probablemente un error de carga), así que los
porcentajes ponderados por monto se informan también sin los casos con costo mayor a 10 veces el
aporte del banco.

NDB. `monto_otras_fuentes` de la ficha va a `aporte_terceros_usd`, convertido con `a_dolares` al tipo
de cambio del año de aprobación. Son 9 de 10 fichas con el dato; no se infiere el costo total a
partir de la suma porque la tabla de aportantes puede no ser exhaustiva.

AIIB. No se agrega columna. El `.js` trae `project_type` (Cofinanced 70, Stand-alone 76, vacío 336)
pero `committed_funding` está en 1 de 482 registros y `proposed_funding` es el monto propuesto del
propio AIIB: ningún campo da el monto total ni lo que ponen los cofinanciadores. Solo se puede marcar
qué operaciones son cofinanciadas, y no es un monto; queda sin codificar.

## CAF 2014-2022: base heredada como base de operaciones

Prioridad: universo completo y consistente. Código en `src/common/caf_heredada.py`, llamado desde `normalizar_todo`; tests en `tests/test_caf_heredada.py`.

Qué se decidió. Para 2014-2022 la base de operaciones de CAF es `data/raw/legacy/caf/caf_final.xlsx` (reconstruida por el relevamiento anterior desde los informes anuales, 99,1% del total del informe), porque el IATI trae solo el 27% de lo aprobado. El IATI pasa a ser capa de atributos. 2023-2025 sigue solo con IATI hasta que haya parser de los informes.

Cómo entra cada fila heredada. `id_proyecto` sintético `CAF-H-<año>-<8 caracteres de sha1 de año, país, nombre, prestatario, monto y descripción>`; `fuente_url` dice que viene de la base del relevamiento 2022 reconstruida desde los informes, con la ruta del archivo y el informe anual del año (la base no trae URL de scioteca por fila). País llevado al nombre en inglés del resto del corpus (Multinacional y Multinacionales a Regional). `instrumento` guarda el tipo de la base y `forma_financiamiento` sale de él (línea de crédito, préstamo, PBL y SWAp a prestamo; cooperación técnica a donacion, igual que el BID; inversión patrimonial y otros a otro). El riesgo soberano o no soberano de la base va a `tipo_ventanilla` y a `tipo_prestatario` (sin especificar queda vacío en la ventanilla y `sin_dato` en el prestatario). Estado `desconocido` y fecha anclada al 1 de enero porque la base trae solo el año, igual que el AIIB.

Repetidas. El informe previo hablaba de 90 filas repetidas. Verificado: solo 1 fila es idéntica en las nueve columnas (USD 70 M, 2022) y esa se elimina. Las demás repiten año, país, nombre y monto pero tienen otro prestatario: son líneas de crédito revolventes a bancos distintos. Quitarlas bajaría 2016 y 2022 a 87% y 84% del informe, así que se conservan. Criterio: se elimina lo idéntico en todas las columnas, no lo que comparte una clave parcial.

Cruce con IATI. Condiciones: año con tolerancia de uno, país igual (el IATI multipaís cruza si contiene el país), monto dentro de 2%. Entre candidatos: mismo año primero, después similitud del nombre, después cercanía del monto; asignación codiciosa 1 a 1. El nombre ordena pero no es condición, porque IATI y base heredada casi nunca coinciden en el nombre. La fila cruzada toma del IATI url_proyecto, desembolsado, prestatario, tipo de prestatario, descripción, estado y fecha exacta; se queda con monto, país, nombre y año de la heredada, que son los que suman al informe. La fecha del IATI solo se usa si cae en el mismo año que el de la heredada, para no mover una fila de año. El identificador IATI queda en `fuente_url`.

IATI sin cruce de 2014-2022. De 286 operaciones IATI de esos años, 177 cruzan y 109 (USD 9.878 M) no. No se agregan por defecto, porque son en su mayoría la misma operación con otro nombre o monto, y agregarlas pasa el informe entre 7% y 17%. Regla: se agregan solo en años donde la heredada queda bajo 97% del informe (hoy solo 2020, 93,8%), de mayor a menor monto, sin gemela por nombre (similitud 0,6 o más) en la heredada del mismo país y año más o menos uno, y sin pasar el total del informe. Entran 6 operaciones (USD 799 M, todas 2020). Quedan afuera 103 por no cumplir el piso del año, por tener gemela o por pasar el informe.

Columna `origen_fila` (nueva en `esquema.py`, grupo Trazabilidad): `iati`, `heredada` o `heredada_iati`. Solo CAF la completa. El diccionario se regenera con `scripts/diccionario_variables.py`.

Pendiente de revisión. La clasificación soberano y no soberano de la base heredada no reproduce la del informe (soberano 88% del informe, 7% sin especificar), así que para esa tabla sigue valiendo el informe. El complemento de `analisis_preliminar.py` queda en cero en total para 2014-2022, pero su apertura soberano y no soberano muestra diferencias por esa clasificación.

## CAF 2023-2025: listados de los informes como base de operaciones

Continúa el criterio anterior. Código en `scripts/extraer_caf_informes.py` (extracción) y `src/common/caf_heredada.py` (`leer_informes`, `construir_caf`); tests en `tests/test_caf_heredada.py`.

Extracción. Los PDF de los informes 2023, 2024 y 2025 se bajan de las URL de `caf_aprobaciones_informes_<fecha>.csv` a `data/raw/caf/informes/` (ignorado por git) y se leen solo con pdfplumber. Cada ficha empieza en un número en letra de 8 puntos al inicio de línea; su bloque es la columna desde ese número hasta el siguiente de la misma columna. Un número dentro de una frase ("DFCD 13.") no abre ficha. El país sale del encabezado en letra grande de la mitad de la página donde está la columna (las del 2023 son páginas enfrentadas), y "Otros aliados internacionales" y "Operaciones multinacionales" van como Multinacional. El resultado se extrae una vez y se versiona en `data/raw/referencia/caf_operaciones_informes_<fecha>.csv` (474 filas, con `fuente_url` y `pagina` por fila, registrado en el manifest); el script lo regenera. Los montos con punto decimal ("2.93") son decimales y los de grupos de tres cifras ("1.889") miles.

Total usado para validar. El original de cada informe (`total_aprobado_musd`), no el reexpresado del informe 2025 (que quita renovaciones de líneas de crédito en 2021-2024): 16.261, 15.856 y 18.668 millones. Suma extraída: 15.842 (97,4%), 15.857 (100,0%) y 18.710 (100,2%).

Cómo entra cada fila. `origen_fila = informe`, `id_proyecto` sintético `CAF-I-<año>-<sha1 de año, país, título, cliente y monto>`; el nombre es el título de la ficha (para una línea de crédito, el tipo más el cliente); `instrumento` guarda el tipo del listado y `forma_financiamiento` sale de él (cooperación a donacion, inversión patrimonial a otro, garantía a garantia, el resto a prestamo). Fecha anclada al 1 de enero, estado `desconocido`, igual que la base heredada. `prestatario` es el cliente del listado; `tipo_prestatario` sale de `prestatario.clasifica_nombre` sobre el cliente y, si no reconoce el nombre, el tipo manda (línea de crédito, préstamo corporativo, inversión patrimonial y garantía son no soberanas). La ventanilla se llena solo si la categoría es soberana o no soberana, como en el IATI. Los "Fondos de cooperación" de cada país son una línea que agrupa varias cooperaciones técnicas; entran como una fila sin cliente.

Cruce con el IATI. Mismas reglas que 2014-2022 (año más o menos uno, país, monto dentro de 2%, nombre solo ordena), sobre el IATI de 2023 a 2025: 89 de 128 cruzan (`informe_iati`). Diferencia con la heredada: la fila cruzada conserva el cliente y su categoría del informe, porque el informe nombra al prestatario y el IATI solo al ejecutor (el IATI clasificaba como soberana una línea de crédito al BICE); el IATI completa la categoría solo si el informe dice `sin_dato`. El IATI sin cruce (39) no se agrega: los tres años quedan sobre el piso de 97% y la regla de 2014-2022 solo agrega bajo ese piso. El IATI de 2026 (11 filas) sigue como `iati`. Filas 2023-2025 por origen: 385 informe, 89 informe_iati.

Pendiente de revisión. (1) 2025 queda 0,2% sobre el total del informe, porque los montos del listado están redondeados; el test admite hasta 3%. (2) 2023 queda 2,6% bajo el total y Ecuador es el hueco: el listado suma 869 contra 1.252 en su caja "En cifras" (p. 47), las demás páginas de país coinciden con su caja en menos de 3% (verificado una por una), con Bolivia en 1.099 contra 1.112 y Colombia en 1.718 contra 1.743. (3) Tres fichas no tienen cliente fuera de las cooperaciones (2024 El Salvador, dos; 2025 Chile, una) y quedan `sin_dato`. (4) El cliente de una ficha de Ecuador 2023 (Pichincha) repite el de Manabí en el PDF; se conserva tal cual. (5) El riesgo por operación es una inferencia del cliente, no un dato del informe.

## Desembolsos del AIIB: lista oficial cargada a mano

El corpus del AIIB no traía desembolsos. Se carga `monto_desembolsado_usd` desde `AIIB-List-of-Disbursed-Projects-Since-2016.xlsx` (copia en `data/raw/aiib/aiib_desembolsos_<fecha>.xlsx`, registrada en el manifest como carga manual). Código en `src/common/aiib_desembolsos.py`; lo llama `normalizar_aiib` si el archivo está.

- **Fecha del dato.** El desembolso es el acumulado **al 31/12/2025**, el corte del archivo. `fecha_relevamiento` de esas filas sigue siendo la de la descarga del listado web, porque esa columna dice cuándo se bajó la fila y pisarla con el corte falsearía la trazabilidad. Las operaciones aprobadas en 2026 no pueden tener desembolso en esta fuente.
- **Claves del cruce, de a una fila por vez.** Primero la ficha (último tramo de la URL de aiib.org que el archivo trae en "Target Results"), después el nombre sin prefijo "País:" ni siglas entre paréntesis. Una clave repetida en el corpus o en el archivo no cruza: es preferible un hueco a repartir un desembolso entre dos operaciones.
- **Descartado: solapamiento de palabras con país y año.** Los 22 casos que sumaba dieron años invertidos (Antalya Airport) y montos que no cierran (Bukhara Phase II), y no se verificaron a mano. No entran.
- **Monto aprobado intacto.** El compromiso neto del archivo se usa solo para comparar; no reemplaza `monto_aprobado_usd`. Para ratios de desembolso conviene el compromiso neto como denominador (cancelaciones y conversión de moneda al 31/12/2025).
- **No soberanas.** El banco oculta por confidencialidad el desembolso de 106 proyectos no soberanos: quedan vacíos, no en cero.
- **Un año raro de origen.** CONAFIPS (Ecuador) figura en el corpus con año 2022 y en la ficha y el archivo con 2020; es la misma operación (misma ficha, 50 millones). No se corrigió el año.

## Enlace a la ficha de MIGA: se deja vacío

**Decidido:** `url_proyecto` de MIGA queda vacío en las 472 filas. El campo `project_links` de la
fuente (`node/<n>`) no se publica: (de 12 al azar, 8 dieron 404 y 4 llevaron a otra página).

**Alternativa descartada:** cruzar cada garantía con su ficha `miga.org/project/<slug>` usando el
sitemap. Se bajaron robots.txt (permite `/project/`, `Crawl-delay: 2`) y el sitemap (1.889 URL
`/project/`) y 15 fichas reales. Evidencia:

- La ficha no muestra el id de proyecto: solo nombre, país, monto, sector, fecha de directorio y
  estado. No hay cruce por id.
- Los slugs no coinciden con los nombres del corpus (Oyu Tolgoi Project vs `oyu-tolgoi-llc`;
  Nafith Logistics FZ vs `nafith-logistics-iraq-branch`; Myingyan IPP vs
  `sembcorp-myingyan-power-company-limited`; Gaziantep BLT vs `gaziantep-hospital-ppp-project`).
- Por nombre normalizado exacto cruzan 32 de 472 filas (6,8%) y solo 5 (1,1%) con una única ficha.
- Cada proyecto tiene fichas duplicadas (`-0`, `-1`: la versión propuesta y la emitida, con montos
  distintos, p. ej. Azura USD 600 M vs 492 M) y una ficha agrupa varias garantías del corpus (Oyu
  Tolgoi tiene filas de 1.000 M y 900 M, una sola ficha de 1.000 M).
- Cruzar por país + monto + fecha exigiría bajar cientos de fichas (1.889 para indexar) y los montos
  no coinciden (USD 491,8 M vs 492 M; USD 360,8 M vs 361 M).

**Por qué:** el máximo alcanzable queda muy por debajo del 80 % exigido y un enlace equivocado es
peor que ninguno. Vacío no es un dato faltante de la fuente sino una decisión nuestra.
