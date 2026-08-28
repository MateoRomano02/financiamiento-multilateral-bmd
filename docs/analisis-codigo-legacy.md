# Análisis del código heredado

Qué código del proyecto anterior sobrevivió, qué hacía, y qué se rescata de él.

La conclusión operativa está al final: **el valor del código viejo está en el conocimiento
del dominio que documenta, no en el código en sí.**

---

## Inventario

| Código | Estado | Ubicación |
|---|---|---|
| Lector de informes de CAF (R) | ✅ Recuperado | `reference/legacy-code/caf_lector-informes.Rmd` |
| Scraping de la IFC (Python) | ❌ Anunciado en el mail del 13/8, no llegó | |
| Relevamiento del BID | ❌ Nunca compartido | |
| Scraping de AIIB | ❌ Perdido (reseteo de equipo, backup incompleto) | |
| Scraping dinámico de NDB/AIIB | ❌ Perdido | |

De los cinco desarrollos del proyecto anterior, **sobrevivió uno**. Es exactamente el problema
que este repositorio existe para no repetir.

---

## Lector de informes de CAF (R)

Fecha: septiembre de 2023. Librerías: `pdftools`, `tidyverse`, `rvest`.

### Qué hace

CAF no publicaba sus operaciones en formato descargable, así que el script las reconstruye
leyendo los **informes anuales en PDF**. El PDF se convierte a filas de texto y el script
detecta dónde empieza cada proyecto con una heurística: *si los primeros seis caracteres de la
línea están en mayúscula, es el título de un proyecto nuevo*. Después parte ese bloque de texto
en campos buscando las palabras clave `Cliente`, `MONTO`, `PLAZO:` y `Objetivo:`.

Cubre **2014 a 2022**, con tres variantes de parseo porque el formato del informe cambió:
2014-2015 y 2017 en una sola columna, 2016/2018/2020-2022 en dos, y 2019 con su propio formato.

### Qué campos captura

`Nombre del proyecto`, `País`, `Prestatario`, `Fecha de aprobación`, `Monto Financiado`,
`Breve Descripción`.

Y tres campos que el script crea **vacíos** porque el informe no los trae: `Sector`,
`Tipo de inversión/financiamiento` y `Tipo de Préstamo`. Ahí está el origen concreto de los
"campos en blanco" que llevaron al equipo a excluir a CAF del corpus.

### Limitaciones que hereda la base de CAF

Son las que condicionan qué se puede analizar hoy con esos datos:

1. **La "fecha" de aprobación es solo el año.** El informe no publica el día, así que el script
   asigna el año del informe a todas las operaciones. No hay estacionalidad posible.
2. **No hay identificador de proyecto.** Sin ID del banco no se puede seguir un proyecto entre
   años ni detectar duplicados de forma confiable.
3. **No hay estado del proyecto** (aprobado, en implementación, cerrado) ni monto desembolsado:
   el informe anual solo reporta aprobaciones.
4. **Sector e instrumento vienen vacíos** y se completaron a mano después.
5. **El monto se multiplica por 1.000.000**: el informe publica en millones de dólares. Es un
   supuesto a verificar en cualquier fuente nueva de CAF, porque un error de unidad acá cambia
   el resultado por seis órdenes de magnitud.
6. **La detección de proyectos es frágil por diseño.** Depende de mayúsculas y de palabras clave
   en el PDF; cualquier cambio de maquetación del informe la rompe. El propio la dirección del proyecto lo describió
   como "bastante rústico", con ~85% de coincidencia contra lo publicado y completado manual
   posterior.

### Qué se rescata

El **mapa de campos** y las limitaciones de arriba: son la especificación de qué tiene que
producir la solución nueva y qué problemas tiene que resolver. El código en sí no se migra.

---

## Salidas de scraping de el equipo del relevamiento anterior

Sin código, pero los **resultados** sobrevivieron: `bid-invest_scrape-german-20230717.xlsx`
y `bid-lab_scrape-german-20230816.xlsx`.

Sirven para dos cosas: ver qué campos logró capturar del portal del BID en 2023 (o sea, qué es
razonable esperar del portal), y como control de calidad contra el cual comparar el pipeline
nuevo para ese período.

---

## Conclusión operativa

Se arranca de cero con herramientas actuales, decisión ya acordada con el equipo en la reunión
del 5 de agosto. El código viejo se lee, se documenta y se archiva en `reference/`; no se
mantiene ni se migra.

Lo que este repositorio agrega y el proyecto anterior no tuvo: el código versionado y público,
de modo que la próxima persona que retome el trabajo empiece desde donde este terminó.

---

## Script de la IFC en Python

Fecha: mayo de 2023. Única dependencia: `openpyxl`.
Ubicación: `reference/legacy-code/ifc_consolidar-documentos.py`.

### No es un scraper

Es el hallazgo importante de este archivo. Durante todo el proyecto se lo mencionó como "el
código de scraping de la IFC", el único que había sobrevivido. **No scrapea nada.** Lee un Excel
local llamado `SPI (1).xlsx`, hoja `Data`, que alguien descargó a mano.

O sea que la IFC nunca se relevó de forma automatizada: se bajó el Excel del portal y se lo
post-procesó. Conviene saberlo antes de buscar un scraper que no existe.

### Qué hace realmente

Colapsa varias filas en una sola por proyecto. Agrupa por la primera columna, que es el
identificador, y para cada una de las 35 columnas restantes concatena con el carácter `|` los
valores distintos que aparecen en las filas de ese mismo identificador.

Eso revela la forma del dato de origen: **el Excel de la IFC trae una fila por documento, no una
por proyecto.** Un mismo proyecto aparece repetido tantas veces como documentos publicados tenga,
y este script los junta.

### Por qué importa para el pipeline nuevo

El problema que resolvía sigue existiendo hoy. El dataset de IFC en Finances One
(`DS00499`/`RS00448`) devuelve 7.088 filas con un campo `document_type` cuyo primer valor
observado es "Summary of Proposed Investment", que es exactamente el `SPI` del nombre del archivo
que procesaba este script.

Conclusión operativa: **la normalización de IFC tiene que deduplicar a nivel de proyecto**, y esa
deduplicación es una decisión de criterio, no mecánica. Cuando dos documentos del mismo proyecto
difieren en un campo, hay que decidir cuál gana. El script viejo resolvía concatenando ambos con
`|`, lo cual preserva la información pero deja columnas que no se pueden sumar ni promediar.

Esa decisión hay que tomarla explícitamente y documentarla en `docs/criterios-codificacion.md`.

### Qué se rescata

El diagnóstico de la forma del dato de la IFC. El código no se migra: tiene rutas absolutas del
escritorio de su autor, usa una API de `openpyxl` que quedó deprecada (`get_sheet_by_name`), y
asume 36 columnas en un orden fijo.
