# Resumen de variables por institución

Qué variables publica realmente cada institución del corpus, con qué completitud, y qué campo de
cada fuente alimenta cada columna del esquema común.

Está generado con `scripts/perfilar_fuentes.py` sobre las descargas fechadas de `data/raw/`, así
que es reproducible y corresponde a un estado verificable del dato, no a una lectura de la
documentación de cada institución.

## Lo que conviene saber antes de leer las tablas

**Cuatro columnas del esquema no las publica casi nadie, y son las que más condicionan el
análisis.**

El **monto desembolsado** lo publica **una sola institución de ocho**: CAF, en la transacción IATI
de tipo 3, presente en el 98% de sus actividades. Es exactamente al revés de lo que se esperaba,
porque CAF era la fuente que se daba por más pobre. Para el resto, la distancia entre lo aprobado
y lo efectivamente desembolsado no es observable con estas fuentes.

El **monto aprobado** lo publican las ocho, aunque el NDB no en el mismo lugar que el resto.
**Corregido el 17 de septiembre de 2026:** este documento decía que el NDB no publicaba monto en
ninguna forma, y era cierto de su listado pero no de la fuente. **La ficha individual de cada
proyecto sí lo publica**, etiquetado como aporte del banco y como aporte de otras fuentes. Con las
170 fichas descargadas, 160 traen cifra. La lección es que un campo ausente en el listado no
significa ausente en la fuente.

La **moneda original** la publican tres de ocho, BID Invest, CAF y el NDB. En el NDB no es un dato
accesorio: **44 de sus 146 operaciones con monto están denominadas en moneda local**, sobre todo en
yuanes y rand, y hay que convertirlas antes de sumarlas. El resto informa en dólares sin decir si
hubo conversión ni con qué tipo de cambio.

El **monto en moneda original** lo publica solo el NDB, en sus fichas. BID Invest y CAF declaran la
moneda pero informan el monto ya convertido a dólares. El criterio acordado de conservar moneda y
monto originales **no es realizable con estas fuentes** para siete de las ocho instituciones, y para
el NDB es indispensable.

El **tipo de ventanilla**, soberana o no soberana, lo declaran fila por fila solo el AIIB y el NDB.
En el resto se deduce de la institución, que es correcto por diseño para BIRF, IDA, IFC, MIGA, BID,
BID Invest y BID Lab, pero no para CAF, que opera las dos sin separarlas.

**Tres trampas de unidades que hay que resolver antes de sumar nada.** Los montos de la IFC están
**en millones**, no en unidades. Los del AIIB vienen **como texto**, del tipo "USD100 million", y
hay que parsearlos. Los sectores de CAF vienen en **código numérico** del estándar IATI, no en
texto, y requieren traducción.

**Dos unidades de análisis no son la operación.** La IFC publica **una fila por documento**, no por
operación, así que sus 7.088 filas no son 7.088 operaciones y hay que deduplicar antes de agregar.
MIGA publica garantías emitidas, que no son préstamos y no se desembolsan.

---

## Panorama

| Institución | Grupo | Registros | Campos | Unidad de análisis |
|---|---|---|---|---|
| BIRF e IDA | GBM | 28,081 | 24 | una fila por proyecto aprobado |
| IFC | GBM | 7,088 | 26 | una fila por documento, NO por operación |
| MIGA | GBM | 715 | 14 | una fila por garantía emitida |
| BID y BID Lab | GBID | 27,329 | 28 | una fila por operación aprobada |
| BID Invest | GBID | 4,757 | 25 | una fila por operación |
| CAF | CAF | 478 | 15 | una actividad IATI por operación |
| AIIB | AIIB | 466 | 13 | una fila por proyecto |
| NDB | NDB | 170 | 6 | una fila por proyecto, extraída del listado web |

## Cobertura del esquema común

Cada celda dice qué campo de la fuente alimenta esa columna. Una celda vacía significa que **la institución no publica ese dato**, y es una decisión pendiente, no un descuido.

| Columna del esquema | BIRF e IDA | IFC | MIGA | BID y BID Lab | BID Invest | CAF | AIIB | NDB |
|---|---|---|---|---|---|---|---|---|
| **tipo_ventanilla** | no publica | no publica | no publica | no publica | no publica | no publica | `financing_type` | `tipo` |
| **id_proyecto** | `id` | `project_number` | `project_id` | `oper_num` | `project_number` | `iati-identifier` | no publica | no publica |
| **nombre** | `project_name` | `project_name` | `project_name` | `oper_nm` | `project_name` | `title` | `name` | `titulo` |
| **pais** | `countryshortname` | `country` | `host_country` | `cntry_nm` | `country` | `recipient-country` | `economy` | `pais` |
| **url_proyecto** | `url` | `project_url` | `project_links` | no publica | `project_url` | no publica | `path` | `url` |
| **fecha_aprobacion** | `boardapprovaldate` | `ifc_approval_date` | `project_start_date` | `apprvl_dt` | `approval_date` | `activity-date@2` | `date` | `fecha` |
| **estado_original** | `projectstatusdisplay` | `status` | no publica | `publc_sts_nm` | `status` | `activity-status` | `status` | no publica |
| **monto_aprobado_usd** | `curr_total_commitment` | `total_ifc_investment_as_approved_by_boardmillion__usd` | `gross_issued_amount` | `orig_apprvd_useq_amnt` | `iic_financing_amount` | `transaction@2` | `approved_funding` | no publica |
| **monto_desembolsado_usd** | no publica | no publica | no publica | no publica | no publica | `transaction@3` | no publica | no publica |
| **moneda_original** | no publica | no publica | no publica | no publica | `currency` | `default-currency` | no publica | no publica |
| **monto_original** | no publica | no publica | no publica | no publica | no publica | no publica | no publica | no publica |
| **instrumento** | `lendinginstr` | `product_line` | `product_line` | `lending_instrmnt_nm` | `Investment_instrument` | no publica | no publica | no publica |
| **sector** | `sector1` | `industry` | `business_sector` | `sector_nm` | `sector` | `sector` | `sector` | `categoria` |

## Detalle por institución

### BIRF e IDA

Archivo `gbm/birf-ida_proyectos_2026-08-23.json`, 28,081 registros, 24 campos.

Unidad de análisis: **una fila por proyecto aprobado**.

Separa el compromiso de BIRF y de IDA en ibrdcommamt e idacommamt, lo que permite dividir las dos ventanillas dentro de la misma descarga.

| Campo | Completitud | Ejemplo |
|---|---|---|
| `boardapprovaldate` | 98 % | 2027-10-26T00:00:00Z |
| `borrower` | 29 % | The Republic of Burundi |
| `closingdate` | 56 % | 2034-05-31 |
| `cons_serv_reqd_ind` | 21 % | Yes |
| `countrycode` | 100 % | ['BI'] |
| `countryname` | 100 % | Republic of Burundi |
| `countryshortname` | 100 % | Burundi |
| `curr_total_commitment` | 64 % | 85000000 |
| `envassesmentcategorycode` | 56 % | A |
| `esrc_ovrl_risk_rate` | 11 % | H |
| `grantamt` | 64 % | 0 |
| `id` | 100 % | P518248 |
| `idacommamt` | 49 % | 85000000 |
| `impagency` | 30 % | Ministry of the Environment, Agriculture and Liv |
| `lendprojectcost` | 98 % | 86500000 |
| `major_sectors` | 83 % | [{'major_sector': {'major_sector_code': 'HHX', ' |
| `mjsector` | 83 % | Early Childhood Education,Health,Public Administ |
| `proj_id` | 100 % | P518248 |
| `project_abstract` | 53 % | Rehabilitation of the Kajeke dam and the associa |
| `project_name` | 100 % | Kajeke-Gihanga III hydro-agricultural developmen |
| `regionname` | 100 % | Eastern and Southern Africa |
| `status` | 100 % | Pipeline |
| `teamleadname` | 64 % | ['Shelley Mcmillan '] |
| `totalamt` | 49 % | 85000000 |

### IFC

Archivo `gbm/ifc_inversiones_2026-08-21.json`, 7,088 registros, 26 campos.

Unidad de análisis: **una fila por documento, NO por operación**.

Requiere deduplicar a nivel proyecto antes de poder agregarse: el portal publica una fila por documento. **Sus montos están en millones**, no en unidades, y vienen además desagregados por instrumento (préstamo, capital, garantía, gestión de riesgo), lo que permite separar la cartera sin recurrir a otra fuente.

| Campo | Completitud | Ejemplo |
|---|---|---|
| `as_of_date` | 100 % | 20-Aug-2026 |
| `board_approval___calendar_year` | 96 % | 2000 |
| `board_approval___fiscal_year` | 96 % | 2001 |
| `company_name` | 100 % | Kabojja Junior School |
| `country` | 100 % | Uganda |
| `date_disclosed` | 100 % | 05-Feb-2010 |
| `department` | 100 % | Regional Industry - MAS Africa |
| `document_type` | 100 % | Summary of Proposed Investment (Disclosure Polic |
| `environmental_category` | 100 % | B - Limited |
| `ifc_approval_date` | 96 % | 13-Jul-2000 |
| `ifc_country_code` | 88 % | UAN |
| `ifc_invested_date` | 88 % | 02-Feb-2001 |
| `ifc_investment_for_equitymillion__usd` | 34 % | 32.6 |
| `ifc_investment_for_guaranteemillion__usd` | 6 % | 25 |
| `ifc_investment_for_loanmillion__usd` | 70 % | 0.35 |
| `ifc_investment_for_risk_managementmillion__usd` | 3 % | 20 |
| `ifc_signed_date` | 93 % | 03-Oct-2000 |
| `industry` | 100 % | Health, Education and Life Sciences |
| `product_line` | 95 % | Loan |
| `project_name` | 100 % | AEF Kabojja |
| `project_number` | 100 % | 10006 |
| `project_url` | 100 % | https://disclosures.ifc.org/project-detail/SPI/1 |
| `projected_board_date` | 87 % | 15-Jul-2000 |
| `status` | 100 % | Completed |
| `total_ifc_investment_as_approved_by_boardmillion__usd` | 96 % | 0.35 |
| `wb_country_code` | 95 % | UG |

### MIGA

Archivo `gbm/miga_garantias_2026-08-21.json`, 715 registros, 14 campos.

Unidad de análisis: **una fila por garantía emitida**.

Emite garantías, no préstamos: no hay monto desembolsado y no lo va a haber. Solo cubre las emitidas, no el pipeline propuesto que sí muestra su portal. Ojo: `project_start_date` es el inicio de la garantía, no la fecha de aprobación; para series anuales conviene `issued_fy`, que es año fiscal y está al 100%.

| Campo | Completitud | Ejemplo |
|---|---|---|
| `business_sector` | 100 % | Financial |
| `gross_issued_amount` | 99 % | 12451577.2 |
| `host_country` | 100 % | South Africa |
| `host_country_code` | 100 % | ZA |
| `host_region` | 100 % | Sub-Saharan Africa |
| `host_region_code` | 100 % | SSA |
| `issued_fy` | 100 % | 2012 |
| `issued_proj_count` | 100 % | 1 |
| `product_line` | 100 % | PRI |
| `project_expiration_date` | 100 % | 29-Mar-2027 |
| `project_id` | 100 % | 1258 |
| `project_links` | 70 % | https://www.miga.org/node/2195 |
| `project_name` | 100 % | HBZ Bank Limited |
| `project_start_date` | 100 % | 09-Apr-1996 |

### BID y BID Lab

Archivo `gbid/bid_proyectos_2026-08-21.csv`, 27,329 registros, 28 campos.

Unidad de análisis: **una fila por operación aprobada**.

BID Lab sale de este mismo archivo por código de instrumento MIF. Trae además subsector, modalidad y clasificación ambiental.

| Campo | Completitud | Ejemplo |
|---|---|---|
| `apprvl_dt` | 99 % | 2015-07-29T00:00 |
| `cntry_cd` | 100 % | AR |
| `cntry_nm` | 100 % | Argentina |
| `envmntl_clssfctn_cd` | 34 % | C |
| `envmntl_clssfctn_nm` | 33 % | Likely to cause minimal or no negative environme |
| `facility_typ_cd` | 1 % | TFF |
| `facility_typ_nm` | 1 % | Trade Financing Facility |
| `lending_instrmnt_cd` | 39 % | MIF |
| `lending_instrmnt_nm` | 39 % | Multilateral Investment Fund Instrument |
| `lending_typ_cd` | 100 % | SG |
| `lending_typ_nm` | 100 % | Sovereign Guaranteed |
| `loc_cntrprt` | 95 % | 70780224.00 |
| `modality_cd` | 21 % | SEF |
| `modality_nm` | 21 % | SEF (Sector Facility) |
| `objtv` | 100 % | This project is to establish regulatory and tech |
| `oper_nm` | 100 % | Energy Efficiency and Renewable Energy in Low-in |
| `oper_num` | 100 % | AR-G1002 |
| `oper_typ_cd` | 100 % | IGR |
| `opertyp_nm` | 100 % | Investment Grants |
| `orig_apprvd_useq_amnt` | 100 % | 14630855.000 |
| `publc_sts_nm` | 100 % | Implementation |
| `sector_cd` | 93 % | DU |
| `sector_nm` | 92 % | URBAN DEVELOPMENT AND HOUSING |
| `sign_dt` | 84 % | 2017-03-15T00:00 |
| `sts_cd` | 100 % | ACTIVE |
| `subsector_cd` | 100 % | DU-VIV |
| `subsector_nm` | 92 % | HOUSING |
| `totl_cost_orig` | 100 % | 85411079.00 |

### BID Invest

Archivo `gbid/bid-invest_proyectos_2026-08-21.xml`, 4,757 registros, 25 campos.

Unidad de análisis: **una fila por operación**.

Descarga completa sin consulta selectiva. Trae además `project_idb_fin_amount`, que es el aporte del BID en operaciones conjuntas, y `mobilization`, que mide el capital privado movilizado: los dos son directamente pertinentes a la hipótesis sobre el crecimiento de las ventanillas no soberanas. Contiene datos de contacto de clientes que **no deben publicarse**.

| Campo | Completitud | Ejemplo |
|---|---|---|
| `Investment_instrument` | 79 % | Guarantee |
| `Language` | 100 % | English |
| `approval_date` | 94 % | 2018-11-07 |
| `client_email` | 39 % | jfcarbel@peasapem.com |
| `client_phone` | 39 % | +54 3804 431439 |
| `client_post_office_address` | 13 % | Dean Valdivia 111, oficina 901, San Isidro, Perú |
| `company` | 71 % | Vientos de Arauco Renovables SAU and Arauco Reno |
| `country` | 97 % | Argentina |
| `currency` | 86 % | USD |
| `description` | 83 % | IDB Invest is considering providing a loan to su |
| `disclosed_date` | 72 % | 2018-07-03 |
| `domicile` | 13 % | Dean Valdivia 111, oficina 901, San Isidro, Perú |
| `environment_social_category` | 63 % | B |
| `funding_source` | 98 % | Own Resources |
| `iic_financing_amount` | 87 % | 12000000.00 |
| `investment_operations_department_contact` | 100 % | Portfolio Management Division |
| `mobilization` | 100 % | 0 |
| `project_board_date` | 70 % | 2018-06-26 |
| `project_idb_fin_amount` | 24 % | 22000000.00 |
| `project_name` | 100 % | Parque Arauco Wind Projects |
| `project_number` | 100 % | 12133-01 |
| `project_url` | 100 % | https://idbinvest.org/en/projects/parque-arauco- |
| `sector` | 94 % | Energy |
| `signed_date` | 61 % | 2018-08-24 |
| `status` | 100 % | Inactive |

### CAF

Archivo `caf/caf_actividades_2026-08-21.xml`, 478 registros, 15 campos.

Unidad de análisis: **una actividad IATI por operación**.

Fuente incompleta: cubre entre el 13% y el 48% del volumen que la propia CAF reporta en sus informes anuales. Se usa junto con la base heredada, no en lugar de ella. **Es la única fuente del corpus con monto desembolsado explícito**, en la transacción IATI de tipo 3, presente en el 98% de las actividades. Sus sectores vienen en código numérico del estándar, no en texto, así que requieren traducción.

| Campo | Completitud | Ejemplo |
|---|---|---|
| `activity-date@2` | 100 % | 2024-10-07 |
| `activity-status` | 100 % | 2 |
| `budget/value` | 0 % |  |
| `default-currency` | 100 % | USD |
| `description` | 100 % | Apoyar a la República de El Salvador en el despl |
| `iati-identifier` | 100 % | XM-DAC-46008-cfa012402 |
| `recipient-country` | 97 % | SV |
| `sector` | 100 % | 10 |
| `title` | 100 % | Programa de Fortalecimiento de la Soberanía de c |
| `transaction@2` | 100 % | 145000000 |
| `transaction@2/currency` | 100 % | USD |
| `transaction@2/date` | 100 % | 2024-10-07 |
| `transaction@3` | 98 % | 0 |
| `transaction@3/currency` | 98 % | USD |
| `transaction@3/date` | 98 % | 2024-10-07 |

### AIIB

Archivo `aiib/aiib_proyectos_2026-08-21.js`, 466 registros, 13 campos.

Unidad de análisis: **una fila por proyecto**.

Declara la ventanilla fila por fila en `financing_type`, igual que el NDB. **Su monto viene como texto**, del tipo "USD100 million", y hay que parsearlo. Su campo de fecha es solo el año. `project_type` está al 31% y no sirve como estado: el estado real está en `status`, al 100%. Ojo con la licencia: restringe la redistribución.

| Campo | Completitud | Ejemplo |
|---|---|---|
| `approved_funding` | 81 % | USD100 million |
| `committed_funding` | 0 % | TBD |
| `date` | 82 % | 2025 |
| `economy` | 100 % | Indonesia |
| `financing_type` | 100 % | Sovereign |
| `name` | 100 % | Indonesia : Development of the Center of Excelle |
| `path` | 100 % | /en/projects/details/2026/proposed/indonesia-dev |
| `pos` | 100 % | 0.956533 |
| `project_type` | 31 % | Stand-alone |
| `proposed_funding` | 18 % | USD47.71 million |
| `sector` | 100 % | Health Infrastructure |
| `special_funding` | 0 % |  |
| `status` | 100 % | Proposed |

### NDB

Archivo `ndb/ndb_proyectos_2026-09-06.html`, 170 registros, 6 campos.

Unidad de análisis: **una fila por proyecto, extraída del listado web**.

Única institución sin archivo ni servicio: hay que leer el sitio, y el listado pagina de a doce sin declararlo. **No publica monto**, que es el campo que más falta hace. Declara la ventanilla fila por fila, igual que el AIIB.

| Campo | Completitud | Ejemplo |
|---|---|---|
| `categoria` | 100 % | Clean Energy and Energy Efficiency |
| `fecha` | 100 % | 24 August 2026 |
| `pais` | 100 % | India |
| `tipo` | 100 % | Non-Sovereign |
| `titulo` | 100 % | REC Energy Infrastructure Project |
| `url` | 100 % | https://www.ndb.int/project/rec-energy-infrastru |
