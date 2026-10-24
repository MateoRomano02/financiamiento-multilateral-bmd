# Financiamiento multilateral de bancos de desarrollo

Infraestructura reproducible para obtener, armonizar y auditar las bases de proyectos aprobados
por los bancos multilaterales, regionales y subregionales de desarrollo.

Proyecto Interdisciplinario CIAI-LCD-STD-UNSAM 2026 Nº 34, Escuela Interdisciplinaria de Altos
Estudios Sociales, Universidad Nacional de San Martín, en el marco de una línea de investigación
sobre financiamiento multilateral de la transición energética.

## Alcance

El repositorio contiene los programas que obtienen los datos desde las fuentes oficiales de cada
institución, los normalizan a un esquema común y validan su consistencia.

**No contiene datos.** Los conjuntos se reconstruyen ejecutando los programas contra las fuentes
originales. Esa decisión es deliberada: mantiene el repositorio liviano, evita redistribuir
material sujeto a condiciones de uso de terceros, y garantiza que lo obtenido corresponda al
estado actual de cada fuente. Los manifiestos en `data/raw/` documentan qué se descargó, desde
dónde y cuándo.

## Instituciones relevadas

| Grupo | Ventanillas |
|---|---|
| Grupo Banco Mundial | BIRF, IDA, IFC, MIGA |
| Grupo BID | BID, BID Invest, BID Lab |
| CAF, Banco de Desarrollo de América Latina y el Caribe | única |
| NDB, Nuevo Banco de Desarrollo | única |
| BAII, Banco Asiático de Inversión en Infraestructura | única |
| FONPLATA, Fondo Financiero para el Desarrollo de la Cuenca del Plata | única |
| BCIE, Banco Centroamericano de Integración Económica | única |

## Uso

Requiere [uv](https://docs.astral.sh/uv/). La versión de Python está fijada en `.python-version`.

```bash
uv sync --extra dev                                   # instala dependencias
uv run pytest                                         # valida el esquema
export CONTACTO="tu.correo@institucion.edu"
uv run python scripts/actualizar_corpus.py            # descarga y arma el corpus de punta a punta
uv run python scripts/actualizar_corpus.py --sin-descarga   # solo reprocesa lo ya descargado
uv run python scripts/descargar_fuentes.py caf bid    # descarga solo algunas fuentes
```

`actualizar_corpus.py` encadena la descarga, la normalización, la consolidación, los análisis y el
diccionario de variables. Frena en el primer error y al final muestra qué cambió respecto de la
corrida anterior, institución por institución.

Cada descarga queda registrada en el manifiesto de su directorio con la dirección de origen, la
fecha, la versión del punto de acceso y el número de registros obtenidos.

## Documentación

| Documento | Contenido |
|---|---|
| [docs/accesos-a-los-datos.md](docs/accesos-a-los-datos.md) | De dónde se obtiene el dato de cada institución, en qué formato y bajo qué licencia |
| [docs/notas-metodologicas.md](docs/notas-metodologicas.md) | Cómo se construye el corpus y por qué, sin terminología técnica |
| [docs/criterios-codificacion.md](docs/criterios-codificacion.md) | Cómo se decidió cada valor derivado |
| [docs/diccionario-de-variables.md](docs/diccionario-de-variables.md) | Definición de cada variable del esquema común, generado desde el código |
| [docs/resumen-de-variables.md](docs/resumen-de-variables.md) | Qué publica cada institución y qué campo alimenta cada columna |
| [docs/guia-composicion-de-cartera.md](docs/guia-composicion-de-cartera.md) | Cómo leer las tablas de composición de cartera |
| [docs/analisis-codigo-legacy.md](docs/analisis-codigo-legacy.md) | Qué hacía el código del relevamiento anterior y qué se rescató |

## Estructura

```
src/common/     esquema armonizado, normalizadores y validaciones
scripts/        descarga, consolidación, análisis y explorador
tests/          pruebas del esquema y de los normalizadores
data/raw/       manifiestos de descarga; los datos no se versionan
docs/           documentación técnica y metodológica
```

## Explorador

`uv run python scripts/explorador_corpus.py` genera, a partir del corpus consolidado, un único archivo
HTML con mapa, evolución por grupo, composición y tabla de operaciones. Se abre con doble clic.

## Licencia

Código bajo licencia MIT. Los datos obtenidos mediante estos programas se rigen por las
condiciones de uso de cada institución, documentadas en `docs/accesos-a-los-datos.md`.

## Nota sobre el acceso a las fuentes

Los programas se identifican ante cada institución mediante un user-agent que incluye una
dirección de contacto, tomada de la variable de entorno `CONTACTO`. Conviene definirla antes de
ejecutar cualquier descarga:

```bash
export CONTACTO="tu.correo@institucion.edu"
```

Es una práctica de acceso responsable: permite que una institución identifique y contacte a quien
consume sus datos si lo necesita.

## Fuentes que no se descargan solas

Algunos insumos no se pueden volver a bajar automáticamente y este repositorio no los incluye, porque
no publica datos. Sin ellos el corpus se arma igual, con estas diferencias:

- **CAF, operaciones completas.** Su archivo IATI trae cerca de un cuarto de lo que CAF declara haber
  aprobado en sus informes anuales. Las operaciones completas salen de una base reconstruida desde
  esos informes para 2014-2022 y de los listados de los informes 2023-2025, extraídos con
  `scripts/extraer_caf_informes.py`. Sin esos archivos, CAF queda solo con lo que publica su archivo.
- **CAF, descargas anteriores.** CAF republicó su archivo IATI sin las operaciones terminadas. El
  normalizador une todas las descargas fechadas de `data/raw/caf/`, así que quien descargue por primera
  vez obtiene solo lo que CAF publica hoy.
- **AIIB, desembolsos.** Salen de la lista oficial de proyectos desembolsados del banco, que su sitio
  no enlaza de forma estable. Sin ella, el AIIB queda sin desembolsos.
