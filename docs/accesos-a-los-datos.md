# Accesos a los datos

Este documento responde una sola pregunta por fuente: dónde está el dato, cómo se baja, y si es
oficial. Es la referencia operativa del proyecto: entrás sabiendo qué banco necesitás y salís con
el link y el comando.

Toda la verificación se hizo el **21 de agosto de 2026**, con `curl` y `WebFetch` reales contra
las páginas y APIs vivas de cada institución (no de memoria), y con una segunda pasada adversarial
el mismo día dedicada específicamente a confirmar oficialidad y licencia. El razonamiento
completo, cada afirmación citada con el fragmento de respuesta real, y todo lo que quedó sin
verificar, vive en `research/relevamiento-de-fuentes.md`. Este documento es la respuesta destilada de ese
informe, no el razonamiento en sí. Ante cualquier duda sobre una cifra o una URL, la fuente
primaria está ahí.

---

## Tabla maestra de accesos

| Institución | Grupo | URL de acceso | Formato | Oficialidad | Licencia | Volumen ARG | Último dato |
|---|---|---|---|---|---|---|---|
| BIRF/IDA | Banco Mundial (soberano) | `search.worldbank.org/api/v2/projects?format=json&countrycode_exact=AR` | JSON | OFICIAL | CC-BY 4.0 | 255 proyectos | 31/07/2026 |
| IFC | Banco Mundial (privado) | `datacatalogapi.worldbank.org/dexapps/fone/api/apiservice?datasetId=DS00499&resourceId=RS00448&type=json` | JSON | OFICIAL | CC-BY 4.0 (asumida) | No verificado | No hay fecha propia confirmada |
| MIGA | Banco Mundial (garantías) | `datacatalogapi.worldbank.org/dexapps/fone/api/apiservice?datasetId=DS00988&resourceId=RS00918&type=json` | JSON | OFICIAL | CC-BY 4.0 | 11 registros | 31/07/2026 |
| BID | BID (soberano) | `data.iadb.org/file/download/791d475c-0f61-411c-ae92-2242c913e73a` | CSV | OFICIAL | CC-BY | Presente, sin conteo total | Declarado 01/01/2025; real 16/10/2025 |
| BID Invest | BID (privado) | `idbinvest.org/en/projects.xml` | XML | OFICIAL | No declarada (CC-BY en su canal IATI) | 263 proyectos | Aprobaciones hasta 07/08/2026 |
| BID Lab | BID | Mismo CSV de BID, filtrado por `lending_instrmnt_cd == "MIF"` | CSV filtrado | OFICIAL el dato; sin fuente propia | CC-BY (heredada del BID soberano) | No cuantificado | ~16/10/2025 (mismo dataset) |
| CAF | CAF | `iatiregistry.org/api/3/action/package_search?fq=organization:caf&rows=50` | XML (IATI) | OFICIAL_INDIRECTA | ODC-BY | 63 operaciones, USD 7.823-7.824 M | Generado 10/10/2025; actividad 08/09/2025 |
| NDB | NDB (BRICS) | `www.ndb.int/projects/all-projects/?project_status=approved` | HTML | OFICIAL | No documentada | 0 (no es país miembro) | No verificado |
| AIIB | AIIB | `www.aiib.org/en/projects/list/.content/all-projects-data.js` | JS/JSON | OFICIAL | Restrictiva, no CC (ver advertencias) | 1 proyecto (cancelado) | 2016-2026, sin fecha "as of" |

---

## Fichas por fuente

### BIRF/IDA

**Acceso.** Dos mecanismos complementarios, ninguno pide API key:

- API de proyectos: `https://search.worldbank.org/api/v2/projects?format=json&countrycode_exact=AR&rows=50`. Filtros que funcionan: `countrycode_exact`, `rows`, `os` (offset), `fl` (campos).
- WBG Finances One, para datos a nivel de préstamo individual:
  `curl "https://datacatalogapi.worldbank.org/dexapps/fone/api/apiservice?datasetId=DS00975&resourceId=RS00905&top=3&type=json"` (IBRD Statement of Loans, 1.566.442 filas históricas desde 1947). IDA tiene su propio dataset (`DS00976`/`RS00906`), con descarga bulk directa en CSV (548 MB) y JSON (1,56 GB).

**Qué devuelve.** API de proyectos (JSON): `id`, `project_name`, `boardapprovaldate`, `totalamt`, `totalcommamt`, `ibrdcommamt`/`idacommamt`, `countryname`, `sector1`, `lendinginstr`, `status`. Finances One agrega, por préstamo: desembolsado, no desembolsado, cancelado, moneda, tasas, fechas de firma/efectividad/repago.

**Oficialidad.** OFICIAL. Ambos dominios son del Grupo Banco Mundial; `search.worldbank.org` respondió HTTP 200 el 21/08/2026 con `total: 22729` sin filtro.

**Licencia.** CC-BY 4.0, confirmada literal en el campo `license` de la metadata JSON de Finances One.

**Ojo con.** Es la fuente más limpia del relevamiento: sin bloqueo, sin auth, sin rate limit documentado (tampoco confirmado que no exista uno). No se identificaron campos faltantes.

### IFC

**Acceso.** El portal `disclosures.ifc.org` no tiene descarga masiva ni API propia. El mecanismo real, encontrado en la verificación adversarial, es Finances One con el `resourceId` correcto:

```
curl "https://datacatalogapi.worldbank.org/dexapps/fone/api/apiservice?datasetId=DS00499&resourceId=RS00448&type=json"
```

Esto pertenece al dataset padre `DS00499` ("IFC Investment Services Projects"), no al hijo `DS01670` ("IFC Active Investment Projects by Country") que se había buscado originalmente. `DS01670` sigue sin `resourceId` identificado: cualquier `resourceId` probado bajo ese dataset devuelve HTTP 417. No hace falta seguir buscándolo: `DS00499`/`RS00448` es un mecanismo verificado, funcionando hoy, con 7.088 filas a nivel de proyecto individual, más granular que la agregación "by Country".

**Qué devuelve.** JSON, 26 columnas reales: `project_number`, `ifc_approval_date`, `ifc_invested_date`, `ifc_signed_date`, `environmental_category`, `product_line`, montos por instrumento (equity, guarantee, loan, risk management), `project_url`.

**Oficialidad.** OFICIAL para `DS00499`/`RS00448` (pull real, HTTP 200, `count: 7088`). IFC también publica en IATI Registry (`ifcwbg`, 160 datasets), canal secundario no evaluado en detalle.

**Licencia.** CC-BY 4.0, confirmada en la metadata de `DS01670`; razonable asumir la misma para `DS00499` (comparten plataforma) pero no se verificó el campo `license` de `DS00499` de forma aislada.

**Ojo con.** No confundir `DS01670` con `DS00499`: son datasets distintos con la misma familia de resourceIds inválidos si se mezclan. No hay pull confirmado de volumen para Argentina.

### MIGA

**Acceso.** El portal oficial `miga.org/projects` está bloqueado (ver advertencias). El mecanismo verificado con pull real es Finances One:

```
curl "https://datacatalogapi.worldbank.org/dexapps/fone/api/apiservice?datasetId=DS00988&resourceId=RS00918&top=3&type=json"
```

Sin API key. Total: 715 garantías emitidas (histórico completo). Filtrando `host_country_code=="AR"`: 11 registros (ej. Banco Santander Río S.A., montos entre USD 247 M y USD 1.100 M, 2018-2021).

**Qué devuelve.** JSON, 12 campos: `business_sector`, `gross_issued_amount`, `host_country_code`, `issued_fy`, `product_line`, `project_id`, `project_links` (URL a la ficha en miga.org), `project_name`, `project_start_date`/`project_expiration_date`, entre otros.

**Oficialidad.** OFICIAL. Pull real HTTP 200 el 21/08/2026, metadata confirma `data_provided_by: "World Bank Group"` y `owner: financesone@worldbank.org`.

**Licencia.** CC-BY 4.0, en la metadata.

**Ojo con.** No hay monto desembolsado (una garantía no se desembolsa como un préstamo). Solo cubre garantías "emitidas", no el pipeline "Proposed" que sí muestra el portal público. `miga.org/projects` devuelve `cf-mitigated: challenge` y HTTP 403 (WAF de Cloudflare); usar siempre Finances One.

### BID (soberano)

**Acceso.** El sitio principal `www.iadb.org` está bloqueado (ver advertencias). El catálogo de datos abiertos, que corre sobre CKAN, no lo está:

```
curl "https://data.iadb.org/api/3/action/package_show?id=idb-projects-dataset"
```

Trae metadata completa y dos CSV descargables sin autenticación: inglés
(`https://data.iadb.org/file/download/791d475c-0f61-411c-ae92-2242c913e73a`) y español
(`https://data.iadb.org/file/download/fc342d1e-fdc9-4590-8d47-c4499a89d381`).

**Qué devuelve.** CSV, 27.329 filas, 28 columnas verificadas por header real: `oper_num`, `apprvl_dt`, `sign_dt`, `cntry_cd`, `sector_nm`, `orig_apprvd_useq_amnt` (monto aprobado), `totl_cost_orig`, `lending_typ_nm` (Sovereign/Non-Sovereign Guaranteed), `lending_instrmnt_cd` (incluye `"MIF"`, ver BID Lab).

**Oficialidad.** OFICIAL. `organization: "idb-datasets" / "Official list of IDB Datasets"`, `license_id: "cc-by"`, DOI de citación propio (`10.60966/ihisavwe`).

**Licencia.** CC-BY (`cc-by`), con `license_url` a creativecommons.org.

**Ojo con.** No trae monto desembolsado, solo aprobado y costo total. 314 filas con `apprvl_dt == "NULL"` sin explicación. El `robots.txt` de `data.iadb.org` bloquea explícitamente `/api/`, `/dataset/download/`, `/file/download/` y `/file/token-download/` ("Block direct download paths to force landing page traffic"); el link directo funciona igual, pero el BID señala preferencia por tráfico vía la página del dataset, no vía el link crudo (ver advertencias).

### BID Invest

**Acceso.** `idbinvest.org` no está detrás de un WAF agresivo, a diferencia de `www.iadb.org`. Descarga XML masiva, sin auth ni parámetros:

```
curl "https://idbinvest.org/en/projects.xml"
```

HTTP 200, ~9,9 MB. 4.757 proyectos totales, 263 de Argentina (conteo real de tags `<country>Argentina</country>`).

**Qué devuelve.** XML, 24 campos por `<item>`: `project_name`, `company`, `approval_date`, `country`, `status`, `signed_date`, `sector`, `currency`, `iic_financing_amount`, `funding_source`, `environment_social_category`, `project_url`.

**Oficialidad.** OFICIAL. Dominio institucional propio de IDB Invest. También publica en IATI (`idbinvest`, 2 datasets, canal mucho más pobre que el XML).

**Licencia.** No declarada en el archivo XML en sí. Sí hay CC-BY en su canal IATI.

**Ojo con.** No hay campo de monto desembolsado. Fechas de directorio (pipeline) llegan hasta 31/03/2027, mezcladas con aprobaciones reales; no confundir una cosa con la otra al filtrar.

### BID Lab

**Acceso.** No hay mecanismo dedicado. `bidlab.org` no tiene buscador de proyectos, portafolio ni catálogo de datos propio: se revisaron todos los `href` de la home y solo hay links a productos y notas de prensa. Las operaciones de BID Lab (antes FOMIN) están mezcladas en el mismo CSV del BID soberano, identificables por `lending_instrmnt_cd == "MIF"`. Se extraen del mismo endpoint de la sección BID, filtrando esa columna.

**Qué devuelve.** Los mismos 28 campos del CSV del BID soberano, en las filas con instrumento MIF. Ejemplo real: `AR-G1004`, "Zolvers: A FinTech Platform for Domestic Workers" (2018).

**Oficialidad.** El dato es OFICIAL (viene del CSV oficial del BID), pero BID Lab no tiene una fuente propia. Se confirmó activamente que no existe: `package_search?q=BID+Lab` no devuelve ningún dataset de BID Lab (205 resultados, todos ajenos); `package_search?q=MIF` devuelve `count: 0`. Su identidad legada en IATI, `fomin`, es publisher activo desde 2018 pero con `package_count: 0`: canal muerto.

**Licencia.** La misma CC-BY del CSV del BID soberano, por ser el mismo archivo.

**Ojo con.** No se sabe qué fracción del universo total de BID Lab (~3.000 operaciones desde 1993, cifra del propio sitio, no verificada de forma independiente) está cubierta por el filtro MIF. Podrían faltar donaciones chicas o instrumentos no reembolsables bajo otro código.

### CAF

**Acceso.** `caf.com` está bloqueado (ver advertencias). CAF es publisher en el IATI Registry desde el 14/08/2024. Mecanismo en dos pasos:

```
curl "https://iatiregistry.org/api/3/action/package_search?fq=organization:caf&rows=50"
```

Devuelve el dataset `caf-actfile-46008-2603` con un array `resources[].url` que apunta al XML real (al momento de la verificación, un blob de Azure con nombre fechado, por ejemplo `CAF-ActivityFile-2025-10-10.xml`). No hardcodear esa URL de blob: el nombre cambia si CAF regenera el feed. Siempre resolverla primero contra `package_search`, que es estable.

**Qué devuelve.** XML formato IATI Standard v2.03: id, nombre, estado (`<activity-status>`, solo Implementación/Cerrado), monto comprometido (100% de las actividades), monto desembolsado (98%), país (`<recipient-country>`), sector, link a la ficha en caf.com. 478 operaciones totales, 63 de Argentina, USD 7.823-7.824 millones comprometidos (el informe de origen trae ambas cifras, sin explicar la diferencia; probablemente redondeo).

**Oficialidad.** OFICIAL_INDIRECTA, con tres líneas de evidencia independientes: el `publisher_iati_id` (`XM-DAC-46008`) coincide con el codelist oficial OCDE-DAC ("Development Bank of Latin America"); la propia `caf.com` reconoce la publicación en IATI en al menos cinco páginas (leídas vía Wayback Machine porque el acceso directo sigue bloqueado); y el Registry asocia el archivo del blob a la organización `caf` de forma verificable. Queda sin confirmar quién opera técnicamente la cuenta de Azure, pero eso no cambia el veredicto.

**Licencia.** ODC-BY (Open Data Commons Attribution License), declarada en `license_id`.

**Ojo con.** El feed no se actualizó en los ~10-11 meses previos a esta verificación (generado 10/10/2025, actividad más reciente 08/09/2025). No está confirmado si cubre el 100% del portafolio histórico (CAF opera desde 1970, el feed arranca en 1995) o es un subconjunto. No hay campo de instrumento (préstamo/garantía) ni flag soberano/no soberano estructurado.


### Nota: CAF no tiene API propia, y hay un portal apagado

Se buscó una API o portal de datos abiertos propio de CAF, más allá de IATI. Resultado
(verificado el 21/08/2026):

- **`datos.caf.com` existe como registro DNS y apunta a `caf-ckan.eastus.cloudapp.azure.com`**, o
  sea a una instalación de CKAN, que es la plataforma estándar de portales de datos abiertos. Pero
  **no responde**: el nombre resuelve a `255.255.255.255`, que es una dirección de broadcast y no
  un servidor real, y los puertos 80 y 443 están cerrados.

  La lectura más razonable es que CAF montó o planeó un portal de datos abiertos propio que hoy no
  está operativo. Vale la pena reintentarlo cada tanto: si vuelve, sería una fuente mejor que IATI,
  porque un CKAN expone API de consulta y no solo un archivo para bajar entero.

  **Conviene preguntarle al equipo de investigación si esto es lo que escucharon** cuando
  mencionaron que CAF tenía "una base de datos nueva descargable". Puede que hayan visto ese
  portal cuando estaba en línea.

- `api.caf.com` resuelve a una IP real pero con los puertos cerrados. Parece infraestructura
  interna, no una API pública.

- No existen `data.caf.com`, `opendata.caf.com`, `transparencia.caf.com` ni
  `datosabiertos.caf.com`.

**Sobre IATI y su alcance como API.** El registro IATI sí tiene API, pero sirve para *localizar*
el archivo de CAF, no para consultar sus operaciones. Existe además el IATI Datastore
(`api.iatistandard.org/datastore/`), que sí es una API de consulta con filtros sobre las
actividades de todos los publicadores, pero **requiere una clave de suscripción** (devuelve 401 sin
ella). La clave se solicita gratis en el sitio de IATI. Si en algún momento hace falta consultar
en vez de bajar el archivo entero, ese es el camino, pero para el volumen de CAF (478
operaciones) bajar el archivo completo es más simple.

### NDB

**Acceso.** HTML servido por WordPress, sin necesidad de JS: el listado viene completo en el HTML crudo, con filtros por query string:

```
https://www.ndb.int/projects/all-projects/?project_status=approved
https://www.ndb.int/projects/all-projects/page/2/?project_status=approved
```

Parámetros: `country`, `key_area_focus`, `project_status`, `type_category`, `pyearval`. Pagina con `/page/N/`.

**Qué devuelve.** HTML: sector, país, título con link a la ficha, tipo (Sovereign/Non-Sovereign), fecha. No trae monto en el listado; la ficha individual sí trae monto financiado, prestatario y descripción.

**Oficialidad.** OFICIAL. Dominio propio, HTTP 200. No es publisher en IATI (`count: 0`).

**Licencia.** No documentada. Se buscó explícitamente una página de términos de reuso de datos; lo único enlazado desde la sección de transparencia es un PDF de procedimientos de admisión de nuevos países miembro, no una licencia de datos.

**Ojo con.** La API REST de WordPress (`wp-json`) está bloqueada por un WAF de Azure (403); usar siempre las páginas HTML. Argentina no es país miembro y no aparece en ningún proyecto (167 proyectos revisados, cero matches). No hay fecha "as of" en el sitio.

### AIIB

**Acceso.** El portal de proyectos es una SPA sin datos en el HTML servido. El archivo que alimenta el buscador es público y se descarga con una sola request:

```
curl "https://www.aiib.org/en/projects/list/.content/all-projects-data.js"
```

HTTP 200, 206 KB, array JS/JSON plano (`var data=[...]`). No hace falta headless browser: se parsea quitando `var data=` y las comas colgantes.

**Qué devuelve.** Por entrada: `date` (año), `economy` (país), `sector`, `financing_type` (Sovereign/Nonsovereign), `name`, `approved_funding`/`committed_funding`/`proposed_funding` (montos como string con moneda embebida, ej. `"USD100 million"`, no numéricos limpios), `status`, `path`.

**Oficialidad.** OFICIAL. Dominio propio, HTTP 200. No es publisher en IATI (`count: 0`).

**Licencia.** Restrictiva. Ver la sección de advertencias: no es CC ni ODC-BY.

**Ojo con.** No hay ID de proyecto propio, ni desembolso acumulado, ni fecha exacta de aprobación (solo año). Argentina es miembro pleno desde 2021 pero solo aparece un proyecto en todo el dataset (cancelado). Antes de redistribuir cualquier dato de AIIB, leer la advertencia de licencia abajo.

---

## Advertencias que afectan al proyecto entero

**AIIB tiene una licencia restrictiva, distinta a la del resto de las fuentes.** La página
`https://www.aiib.org/en/general/copyright/index.html` (verificada en su texto real, no en un
resumen, el 21/08/2026) dice que el uso está limitado a fines personales y no comerciales, y que
está prohibido crear obra derivada o hacer uso comercial, incluyendo reventa o redistribución,
"sin el consentimiento previo por escrito de AIIB". Esto es sustancialmente distinto a la CC-BY
4.0 del Banco Mundial y del BID, o a la ODC-BY de CAF, que permiten reuso y obra derivada con
solo atribución. Un análisis académico que cita y analiza el dato con atribución probablemente
cae dentro del uso permitido, pero publicar el dataset crudo de AIIB en un repositorio abierto (o
cualquier redistribución del dato en sí, más allá del análisis propio) sí podría chocar con estos
términos. Esta es una decisión que le corresponde al equipo de investigación, no algo para
resolver de forma unilateral acá. Las salidas posibles, sin que ninguna esté descartada de
antemano:

- Escribirle a AIIB pidiendo consentimiento explícito para redistribuir el dato derivado.
- Publicar en el repositorio del proyecto solo el código que baja y procesa el dato de AIIB, sin
  redistribuir el dataset de AIIB en sí (cada quien lo vuelve a descargar con ese código).
- Excluir a AIIB del conjunto de datos que se redistribuye públicamente, y tratarlo aparte (dado
  además que el corte Argentina de AIIB es prácticamente vacío: un solo proyecto, cancelado).

**El `robots.txt` de `data.iadb.org` ahora bloquea rutas de descarga directa, aunque el acceso
sigue funcionando.** Además del ya conocido `Disallow: /api/`, hoy también bloquea explícitamente
`/dataset/download/`, `/file/download/` y `/file/token-download/`, con el comentario "Block direct
download paths to force landing page traffic". La descarga directa del CSV sigue devolviendo HTTP
200 (se probó de nuevo el 21/08/2026), así que técnicamente no hay nada roto. Pero el `robots.txt`
es una señal explícita de que el BID prefiere que el tráfico pase por la página del dataset en
`data.iadb.org/dataset/idb-projects-dataset`, no por el link crudo. Un uso respetuoso del acceso
es: automatizar la descarga vía el link directo (es lo que documenta este proyecto), pero no
scrapear en bucle ni a alta frecuencia esa ruta, y linkear a la página del dataset como fuente
citable en cualquier entrega, en vez del link crudo del archivo.

**Estos conjuntos de datos están vivos, no son una foto fija.** Cada institución actualiza con su
propia cadencia (MIGA e IFC casi a diario según su metadata, BID soberano y CAF con meses de
retraso entre lo declarado y lo real). No hay que fijar un conteo esperado de filas ni una fecha
de corte única para todo el relevamiento: cualquier número de este documento (255 proyectos de
BIRF/IDA, 715 garantías de MIGA, 27.329 filas del BID, etc.) es válido a la fecha de verificación
indicada junto a cada cifra, y puede cambiar la próxima vez que alguien vuelva a bajar el dato.

---

## Qué falta

- **Las bases heredadas del equipo de 2022 no incluyen BIRF/IBRD ni IFC/CFI.** De los tres brazos
  del Grupo Banco Mundial que el proyecto original esperaba (BIRF, IFC, MIGA), esas bases legadas
  solo trajeron MIGA, el brazo más chico. BIRF aparece únicamente como un listado de países
  elegibles dentro de una hoja de lookup de `MIGA - TE.xlsx`, no como datos de préstamos. Esto no
  afecta el acceso a la fuente viva (BIRF/IDA e IFC sí tienen mecanismo verificado y funcionando
  hoy, ver fichas arriba), pero sí implica que no hay un dataset histórico ya trabajado por el
  equipo anterior para esos dos brazos: el trabajo de bajar y curar esos datos queda entero para
  este proyecto.
- **BID Lab no tiene fuente propia.** Se confirmó de forma activa que no existe ni un dataset CKAN
  dedicado, ni una sección de portafolio en `bidlab.org`, ni un canal IATI vivo (la identidad
  legada FOMIN tiene cero datasets publicados). El dato disponible es un subconjunto del CSV del
  BID soberano, de cobertura no cuantificada frente al universo real de operaciones de BID Lab.
- **El `resourceId` de IFC `DS01670`** (el dataset "by Country" que se había buscado
  originalmente, más agregado que `DS00499`) sigue sin identificarse. No es bloqueante: `DS00499`
  ya da un mecanismo oficial y funcionando, más granular.
- **Volumen Argentina de IFC** no se cuantificó todavía sobre el pull real de `DS00499`/`RS00448`.
- **Licencia de reuso de NDB** no existe documentada en ningún lado del sitio institucional
  (se buscó explícitamente y lo único encontrado fue un procedimiento de admisión de miembros, no
  una licencia de datos).
- **Quién opera técnicamente el blob de Azure que aloja el feed de CAF** no se pudo determinar. No
  cambia el veredicto de oficialidad (el IATI Registry asocia el archivo a CAF de forma
  verificable), pero es un detalle de infraestructura sin confirmar.

---

## Qué es IATI y qué sirve de ahí

**IATI** es la International Aid Transparency Initiative, un estándar internacional por el cual
los organismos de financiamiento publican sus operaciones en un formato XML común. Hoy tiene
**2.087 organizaciones publicadoras** (verificado el 21/08/2026 contra el registro).

Importa para este proyecto por una razón concreta: cuando una institución publica ahí, sus datos
quedan en el mismo formato que los de las demás, con los mismos nombres de campo. Es la única
fuente del relevamiento que ofrece eso.

### Quién de nuestro corpus publica

| Institución | ¿Publica en IATI? | ¿Sirve? |
|---|---|---|
| CAF | Sí | **Sí, es la única fuente disponible** |
| Banco Mundial | Sí, 148 datasets | Secundaria: su API propia es mejor |
| BID | Sí, 28 datasets, uno por país | Secundaria, pero ver la nota de abajo |
| BID Invest | Sí, 2 datasets | Secundaria: el XML de su sitio es más directo |
| BID Lab (como "fomin") | Figura registrado, 27 datasets | **No: los archivos dan 404** |
| IFC | No | |
| NDB | No | |
| AIIB | No | |

### Dos cosas que salieron de verificarlo

**BID Lab sigue sin fuente propia usable.** Aparece en el registro de IATI con 27 datasets, uno
por país, lo cual parecía resolver el problema de completitud. Pero los archivos no existen: se
probaron cinco, incluido el de Argentina, y los cinco devuelven 404. Es un registro huérfano.
Sigue habiendo que extraer BID Lab del conjunto del BID filtrando por instrumento.

**El BID publica un archivo por país que sí funciona.** `webimages.iadb.org/iati/iadb-Argentina.xml`
responde, pesa 8,7 MB y trae 165 actividades entre 2004 y 2035. Tiene más campos que el CSV:
tipo de ayuda, tipo de financiamiento, alcance, y un campo de condiciones.

Sobre ese último, con cuidado: el proyecto estudia **condicionalidades**, así que el campo parece
directamente relevante. Pero las 165 actividades declaran `conditions attached="1"`, es decir que
sí existen condiciones, y **ninguna publica cuáles son.** Es una bandera sin contenido. Sirve para
saber que hay condiciones asociadas, no para analizarlas.

### El límite de IATI como API

El registro (`iatiregistry.org/api/3`) sirve para **localizar** archivos, no para consultar datos.
Existe el IATI Datastore (`api.iatistandard.org/datastore/`), que sí permite consultar actividades
con filtros, pero **requiere una clave de suscripción** que se pide gratis en el sitio de IATI.
Para los volúmenes de este proyecto, bajar el archivo completo es más simple.
