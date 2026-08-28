# Notas metodológicas

Este documento explica **qué se hace con los datos del proyecto y por qué**, sin dar por supuesto
ningún conocimiento técnico. Está pensado para el equipo de investigación y para estudiantes de
otras disciplinas que se sumen al proyecto.

Si en algún momento algo acá está escrito en jerga, es un error de quien lo escribió. Avisá.

---

## 1. Qué problema resuelve este trabajo

El equipo de investigación construyó, entre 2022 y 2023, una serie de bases de datos con los
proyectos que los bancos multilaterales de desarrollo aprobaron desde 2014. Esas bases
permitieron responder preguntas sobre cuánto y cómo financian estas instituciones la transición
energética.

Tres años después hay tres problemas:

1. **Los datos están viejos.** La última foto es de 2022. Desde entonces se aprobaron proyectos
   nuevos, y los que ya existían cambiaron: uno que estaba "en implementación" hoy puede estar
   cerrado, y los montos efectivamente desembolsados son otros.
2. **Falta la CAF.** Se la excluyó porque su información tenía demasiados campos vacíos. Desde
   entonces la institución mejoró lo que publica.
3. **Se perdió casi todo el código.** De los cinco desarrollos que se hicieron para armar las
   bases, sobrevivió uno. Los demás desaparecieron con un reseteo de computadora, backups
   incompletos, o simplemente nunca se compartieron. Eso significa que actualizar las bases hoy
   implica empezar de nuevo casi desde cero.

El tercer problema es el que más condiciona el resto, y es el que explica por qué este proyecto
le da tanto lugar a la documentación y al repositorio: **no alcanza con producir la base nueva
si dentro de tres años vuelve a pasar lo mismo.**

---

## 2. Qué es un repositorio y por qué importa acá

Un repositorio es una carpeta compartida con memoria. Guarda no solo la versión actual de cada
archivo sino todas las versiones anteriores, quién hizo cada cambio y por qué. Nada se pierde y
todo se puede deshacer.

Para este proyecto resuelve tres cosas concretas:

- **El código no depende de una computadora.** Vive en un servidor y cualquiera con acceso lo
  descarga. Un reseteo de máquina deja de ser un evento catastrófico.
- **Se puede volver atrás.** Los sitios web de los bancos cambian de forma seguido, y a veces
  vuelven a una versión anterior. Tener registrado cómo se leía cada versión permite recuperar
  la solución vieja en vez de rehacerla.
- **La próxima persona empieza desde acá.** Ese es el punto. Un estudiante que tome el proyecto
  el año que viene encuentra el código, la documentación y las decisiones ya tomadas.

---

## 3. Cómo se organizan los datos

Hay tres tipos de datos y no se mezclan nunca.

**Datos crudos.** Es lo que se descarga de cada banco, tal cual viene, sin tocar. También entran
acá las bases que armó el equipo en 2022, que se guardan exactamente como llegaron. Esta parte es
**intocable**: nadie edita nada acá, ni para corregir un error evidente.

**Datos intermedios.** El resultado de los pasos de limpieza. Se pueden borrar y regenerar en
cualquier momento, porque son producto de aplicar los programas sobre los datos crudos.

**Datos finales.** Las bases limpias y unificadas, listas para analizar o para alimentar los
tableros.

La regla de que los datos crudos no se tocan tiene una razón práctica: son la única prueba de
qué publicaba efectivamente cada banco en cada momento. Si se corrigen a mano, esa prueba se
pierde y ya no hay forma de saber si un valor raro es un error del banco o un error nuestro.

---

## 4. Por qué nada se corrige a mano

Es la regla que más incomoda al principio: si un dato está mal, **no se arregla abriendo el
Excel**. Se arregla escribiendo una instrucción en un programa que dice "cuando aparezca este
caso, hacé esto".

Las razones:

- Un Excel corregido a mano no se puede repetir. Si tres meses después llegan datos nuevos, hay
  que volver a hacer las mismas correcciones a mano, y nadie se acuerda cuáles eran.
- No queda registro de qué se cambió ni por qué. Un revisor externo no puede auditar el
  resultado.
- Las correcciones a mano no escalan. Sobre cinco mil filas, arreglar a mano garantiza que algo
  se va a pasar por alto.

Escribir la corrección como instrucción cuesta un poco más la primera vez y sale gratis todas las
siguientes.

---

## 5. Cómo se obtiene la información de cada banco

Los bancos publican sus proyectos de formas muy distintas, y para cada uno se elige el camino
más simple que funcione. En orden de preferencia:

1. **Una vía de acceso directa a los datos.** Algunos bancos ofrecen una dirección donde un
   programa puede pedir los datos y recibirlos ya ordenados. Es lo mejor: rápido, estable y sin
   ambigüedad.
2. **Un archivo descargable.** Un Excel o un CSV publicado por el propio banco. Casi tan bueno.
3. **Leer la página web.** Si no hay ninguna de las anteriores, se escribe un programa que
   recorre el sitio y extrae los datos de las páginas, como lo haría una persona copiando a mano
   pero mucho más rápido. Esto es lo que se llama *scraping*.
4. **Leer documentos en PDF.** El último recurso, y el caso de CAF en el proyecto anterior. Es el
   más frágil, porque un PDF está diseñado para que lo lea una persona, no un programa.

Cuanto más abajo en esta lista, más trabajo cuesta y más fácil se rompe. Por eso la primera tarea
con cada banco es averiguar qué opción está disponible hoy, y no asumir que sigue siendo la misma
que en 2022.

### Sobre el scraping y por qué se rompe

Un programa que lee una página web depende de cómo está construida esa página. Si el banco
rediseña su sitio, el programa deja de encontrar lo que buscaba. No es un defecto del programa:
es una característica inevitable del método.

Por eso importa documentar no solo *qué* hace cada programa sino *dónde* buscaba cada dato. Con
eso, arreglarlo después de un rediseño es cuestión de horas y no de rehacerlo entero.

---

## 6. Qué significa "armonizar" las bases

Cada banco nombra las cosas a su manera. Uno dice "Approved", otro "Aprobado", otro "Active".
Uno publica montos en dólares y otro en millones de dólares. Uno tiene una columna "país" y otro
la llama "country".

Armonizar es traducir todo a un vocabulario único, para que las cinco bases se puedan comparar y
sumar. Dos decisiones sobre cómo se hace:

- **Se guarda siempre el valor original además del traducido.** Si el BID dice "Closed" y nosotros
  lo traducimos a "cerrado", las dos versiones quedan en la base. Así, si más adelante alguien
  discute la traducción, el dato original sigue ahí.
- **Las traducciones dudosas no las decide el pipeline.** Cuando no está claro a qué categoría
  corresponde un valor, la pregunta va al equipo de investigación, porque es una decisión de
  contenido, no técnica. Esas preguntas se anotan en
  [preguntas-para-el-equipo.md](preguntas-para-el-equipo.md).

---

## 7. Los controles automáticos

El proyecto tiene una serie de verificaciones que se corren solas cada vez que se procesa una
base. Buscan cosas como:

- que no haya dos proyectos con el mismo identificador dentro del mismo banco;
- que ningún monto sea negativo;
- que lo desembolsado no supere lo aprobado, porque cuando eso pasa casi siempre es un error de
  unidad (millones mezclados con unidades) y no un desembolso real;
- que las fechas caigan dentro del período del relevamiento;
- que la ventanilla de cada institución sea la que le corresponde: la IFC solo presta al sector
  privado, así que una operación de la IFC marcada como soberana delata un error de mapeo.

La idea no es que estas verificaciones garanticen que los datos son correctos, eso ningún
programa lo puede garantizarsino que **un problema conocido no vuelva a pasar en silencio**.
Cada vez que aparece un error nuevo, se agrega la verificación que lo detecta.

---

## 8. Qué se puede y qué no se puede pedirle a estos datos

Una advertencia que conviene tener presente antes de sacar conclusiones:

- **No todos los bancos publican lo mismo.** Algunos informan montos desembolsados y otros solo
  aprobaciones. Comparar el volumen "financiado" entre bancos que miden cosas distintas produce
  resultados engañosos.
- **La base de CAF es estructuralmente más pobre.** Proviene de informes anuales que solo publican
  el año de aprobación y el monto: no hay día exacto, ni estado del proyecto, ni identificador.
  El detalle está en [analisis-codigo-legacy.md](analisis-codigo-legacy.md).
- **Los montos cambian con el tiempo.** Un proyecto aprobado por cien millones puede terminar
  desembolsando sesenta. Qué número se usa depende de la pregunta que se quiera responder, y
  conviene decidirlo explícitamente antes de armar un gráfico.

---

*Este documento se actualiza a medida que avanza el proyecto. Si algo quedó desactualizado o
poco claro, es un problema del documento y hay que arreglarlo.*
