# Cómo contribuir

Pensado para el próximo estudiante que tome el proyecto y para el equipo de investigación.

## Antes de tocar nada

1. Leé `README.md` y `docs/notas-metodologicas.md`.
2. Instalá el entorno: `uv sync`.
3. Corré `uv run pytest`. Si algo está en rojo antes de tus cambios, arreglalo o documentalo primero.

## Las cuatro reglas

**1. Las bases heredadas no se tocan.** `data/raw/legacy/` se preserva byte a byte. Son la
evidencia de qué había antes y el control de calidad de todo pipeline nuevo.

**2. Ningún dato se edita a mano.** Si un valor está mal, el arreglo va en un script de `src/`,
con un comentario que explique por qué. Un Excel corregido a mano es un resultado que nadie
puede reproducir ni auditar.

**3. Toda descarga deja rastro.** Cada archivo nuevo en `data/raw/<banco>/` se registra en el
`manifest.json` de ese directorio: URL de origen, fecha ISO de descarga y método usado.

**4. Los criterios los define el equipo de investigación.** Si aparece una decisión de contenido
(cómo clasificar un proyecto, qué hacer con una discrepancia, cómo mapear un estado), no la
resuelvas por tu cuenta: anotala como pregunta abierta y consultá.

## Agregar un banco nuevo

Agregá su descarga en `scripts/descargar_fuentes.py` y su normalizador en `src/common/normalizar.py`, que lleva el crudo al esquema común de `src/common/esquema.py`. Después: agregá el banco a `tests/`, documentá la fuente en `docs/accesos-a-los-datos.md` y
cualquier decisión de mapeo en `docs/criterios-codificacion.md`.

## Scraping responsable

- Primero buscá API o descarga estructurada oficial. Scrapear es el último recurso.
- Revisá `robots.txt` y los términos de uso, y anotá lo que encontraste en `docs/accesos-a-los-datos.md`.
- Rate limiting siempre, user-agent identificable, y cacheá lo descargado para no repetir pedidos.
- El HTML cambia: documentá los selectores que usaste y por qué, para que el próximo entienda
  qué se rompió cuando se rompa.

## Commits

En español, chicos y descriptivos. Uno por cambio con sentido propio.

```
Agrega descarga de proyectos del BID via API de datos abiertos
Corrige parseo de montos con separador decimal en formato español
```

## Documentación

Un cambio sin su documentación está a medio hacer. Si tocaste el esquema, actualizá el
diccionario de variables. Si cambiaste cómo se obtiene un dato, actualizá las fuentes por banco.
Si el cambio afecta a cómo se lee la base, actualizá `docs/notas-metodologicas.md`,
ese documento lo leen investigadores sin formación técnica, escribilo sin jerga.

## Una advertencia sobre los conteos de filas

Los conjuntos de datos de los bancos son **vivos**: el CSV del BID cambia de tamaño entre
descargas, y la interfaz del Banco Mundial tiene dos versiones activas al mismo tiempo que
devuelven totales distintos.

Consecuencia práctica: **nunca fijes un número esperado de filas como control de completitud.**
Lo que corresponde es registrar el conteo y la fecha de cada descarga en el `manifest.json`, y
comparar contra la descarga anterior para detectar cambios bruscos.

## Verificá el archivo, no el índice

Tres veces en este proyecto una institución figuró como publicando datos y resultó que no.
BID Lab aparece registrado en el estándar internacional de transparencia con 27 archivos, uno por
país, y todos devuelven error. Climate Investment Funds tiene más de cincuenta conjuntos
registrados que apuntan a un dominio dado de baja. Y CAF tiene una dirección de portal de datos
abiertos que resuelve a un servidor apagado.

**Figurar en un registro no garantiza que el dato exista.** Antes de dar una fuente por
disponible, descargá el archivo. Es una verificación de segundos que evita construir un plan
sobre algo que no está.
