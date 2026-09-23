"""Los cuatro análisis preliminares sobre el corpus consolidado.

Produce las tablas del primer informe de resultados. Cada análisis responde a algo concreto que
alguien pidió o que la bibliografía del proyecto usa como vocabulario común:

1. **Ventanillas soberanas contra no soberanas.** Es la hipótesis que planteó la dirección en la
   reunión de inicio: desde 2014 las ventanillas que prestan al sector privado deberían haber
   crecido frente a las soberanas, porque el paradigma vigente empuja el financiamiento privado.

2. **Concentración de los primeros cinco países.** Es la métrica que usan tres de los cinco textos
   de la bibliografía sin explicarla, porque la dan por conocida. Mide qué porción de la cartera
   de cada institución se lleva su primer decil de receptores.

3. **Composición de cartera por institución y año.** Es el insumo que el equipo que lee las
   memorias anuales necesita para contrastar lo que cada banco declara contra lo que aprobó.

4. **Velocidad de aprobación a firma.** Un proxy medible del costo no financiero de tomarle
   prestado a cada banco. Se calcula sobre las fuentes que publican las dos fechas.

Uso:
    uv run python scripts/analisis_preliminar.py            # tablas a pantalla
    uv run python scripts/analisis_preliminar.py --markdown # en markdown, para el informe
    uv run python scripts/analisis_preliminar.py --csv      # composición por banco, para el equipo
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.common.deflactor import ANIO_BASE, a_constantes  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
PROCESADO = RAIZ / "data" / "processed"
COMPOSICION = PROCESADO / "composicion-por-banco"

# Las ventanillas que prestan al sector privado dentro de cada grupo, y su par soberano.
# La comparación solo tiene sentido dentro del mismo grupo bancario: comparar la IFC contra el
# BID mezclaría el efecto del paradigma con el del tamaño de cada institución.
# MIGA emite garantías y BID Lab financia cooperación técnica, así que ninguna de las dos es
# inequívocamente una ventanilla no soberana. Por indicación de la dirección del proyecto quedan
# fuera de las dos categorías, sin sumar a ninguna, en lugar de forzarlas a una.
PARES = {
    "Grupo Banco Mundial": {"soberana": ["BIRF", "IDA"], "no_soberana": ["IFC"]},
    "Grupo BID": {"soberana": ["BID"], "no_soberana": ["BID Invest"]},
}
EXCLUIDAS_DE_VENTANILLA = ("MIGA", "BID Lab")


def a_markdown(tabla: pd.DataFrame) -> str:
    """Tabla en markdown sin depender de `tabulate`, que no vale una dependencia extra."""
    cols = list(tabla.columns)
    filas = [[("" if pd.isna(v) else str(v)) for v in fila] for fila in tabla.itertuples(index=False)]
    return "\n".join(
        ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
        + ["| " + " | ".join(f) + " |" for f in filas]
    )


def cargar(completo: bool = False) -> pd.DataFrame:
    """El corpus consolidado, con la columna en dólares constantes agregada."""
    nombre = "corpus_completo.csv" if completo else "corpus_2014_2025.csv"
    ruta = PROCESADO / nombre
    if not ruta.exists():
        raise SystemExit("falta el corpus. Correr antes: uv run python scripts/consolidar.py")
    df = pd.read_csv(ruta, low_memory=False)
    df["monto_constante_usd"] = [
        a_constantes(m, a) for m, a in zip(df["monto_aprobado_usd"], df["anio_aprobacion"])
    ]
    return df


# ---------------------------------------------------------------------------
# 1. Ventanillas
# ---------------------------------------------------------------------------


def ventanillas(df: pd.DataFrame, desde: int = 2014, constantes: bool = False) -> pd.DataFrame:
    """Participación anual de la ventanilla no soberana sobre el total de cada grupo.

    `constantes` expresa los montos en dólares del año base aplicando el deflactor del PBI de
    Estados Unidos. La participación porcentual no cambia al deflactar, porque numerador y
    denominador son del mismo año: lo que cambia son los niveles, y por eso conviene reportar
    las dos tablas.
    """
    columna = "monto_constante_usd" if constantes else "monto_aprobado_usd"
    df = df[~topes_de_facilidad_repetidos(df)]
    filas = []
    for grupo, lados in PARES.items():
        todas = lados["soberana"] + lados["no_soberana"]
        sub = df[df["institucion"].isin(todas) & df[columna].notna() & (df["anio_aprobacion"] >= desde)]
        for anio, tramo in sub.groupby("anio_aprobacion"):
            sob = tramo[tramo["institucion"].isin(lados["soberana"])][columna].sum()
            nos = tramo[tramo["institucion"].isin(lados["no_soberana"])][columna].sum()
            total = sob + nos
            if not total:
                continue
            filas.append(
                {
                    "grupo": grupo,
                    "anio": int(anio),
                    "soberana_mm": round(sob / 1e6),
                    "no_soberana_mm": round(nos / 1e6),
                    "pct_no_soberana": round(100 * nos / total, 1),
                }
            )
    return pd.DataFrame(filas)


def topes_de_facilidad_repetidos(df: pd.DataFrame, minimo: int = 10) -> pd.Series:
    """Marca las filas donde una misma institución repite el mismo monto muchas veces en un año.

    Es la firma de una facilidad marco cuyo tope se anota entero en cada línea participante, en
    lugar de la exposición individual. El caso que lo motivó es el programa de trade finance de la
    IFC: en 2004 hay 57 operaciones con USD 7.000 millones cada una, que es el tope del programa
    completo. Sumadas dan el 99% del total de la IFC de ese año y el 54% de toda su historia.

    No es un error de la normalización sino de cómo la fuente publica esas operaciones. Se detecta
    de forma mecánica, sin nombrar programas, para que sirva también en casos que no conocemos.
    """
    clave = df.groupby(["institucion", "anio_aprobacion", "monto_aprobado_usd"])["id_proyecto"].transform("size")
    return (clave >= minimo) & df["monto_aprobado_usd"].notna() & (df["monto_aprobado_usd"] > 0)


def sin_monto(df: pd.DataFrame) -> pd.DataFrame:
    """Las operaciones sin monto, una por fila, para poder rastrearlas a mano.

    La dirección del proyecto las pidió con banco, año y operación para facilitar el rastreo
    cualitativo: son los casos donde la fuente no publica la cifra y hay que ir al documento.
    """
    falta = df[df["monto_aprobado_usd"].isna()]
    return (
        falta[["institucion", "anio_aprobacion", "id_proyecto", "nombre", "pais", "url_proyecto"]]
        .assign(anio_aprobacion=lambda d: d["anio_aprobacion"].astype("Int64"))
        .sort_values(["institucion", "anio_aprobacion"])
    )


# ---------------------------------------------------------------------------
# 2. Concentración
# ---------------------------------------------------------------------------


# Etiquetas que no son un país receptor sino un agregado regional o global. Son 23 en el
# corpus y se llevan el 5% del monto. Se detectan por palabra completa, de modo que
# "South Africa", "Central African Republic" y "Dominican Republic" no caen por error.
RE_AGREGADO = re.compile(
    r"\b(Region|Regional|Regions|World|Multicountry|Multi-country|Multi-Regional|Subregion|Global)\b",
    re.I,
)


def es_pais_real(valor: object) -> bool:
    return bool(valor) and not RE_AGREGADO.search(str(valor))


def concentracion(df: pd.DataFrame, top: int = 5) -> pd.DataFrame:
    """Porción de la cartera de cada institución que se llevan sus `top` países receptores.

    Se excluyen las operaciones sin país y las asignadas a un agregado regional, porque no
    tienen un receptor único: contarlas mezclaría "se lo lleva Brasil" con "se lo lleva una
    facilidad para toda la región", que es exactamente lo contrario de concentración.
    """
    sub = df[df["monto_aprobado_usd"].notna() & df["pais"].apply(es_pais_real)]
    filas = []
    for institucion, tramo in sub.groupby("institucion"):
        por_pais = tramo.groupby("pais")["monto_aprobado_usd"].sum().sort_values(ascending=False)
        total = por_pais.sum()
        if not total:
            continue
        del_banco = df[df["institucion"] == institucion]
        regional = del_banco[~del_banco["pais"].apply(es_pais_real)]["monto_aprobado_usd"].sum()
        filas.append(
            {
                "institucion": institucion,
                "paises": len(por_pais),
                "pct_top5": round(100 * por_pais.head(top).sum() / total, 1),
                "pct_regional": round(100 * regional / (total + regional), 1) if total + regional else 0.0,
                "principales": ", ".join(por_pais.head(3).index.astype(str)),
            }
        )
    return pd.DataFrame(filas).sort_values("pct_top5", ascending=False)


# Países miembro de cada institución, verificados contra la documentación oficial de cada una el
# 17 de septiembre de 2026. Son la foto de hoy y no una serie: la membrecía cambia despacio pero
# cambia, y el AIIB en particular sumó miembros durante todo el período que analizamos.
#
# El BID es el único que quedó sin verificar: su sitio rechaza todo pedido automatizado con un 403,
# incluida la página institucional y el repositorio de publicaciones. Se usa 48 porque es la cifra
# que sí publica BID Invest para el grupo, y se marca como no verificada para que nadie la cite sin
# revisarla.
MIEMBROS = {
    "BIRF": (189, "https://www.worldbank.org/en/about/leadership/members", True),
    "IDA": (175, "https://www.worldbank.org/en/about/leadership/members", True),
    "IFC": (186, "https://www.ifc.org/en/about", True),
    "MIGA": (182, "https://www.miga.org/about-us", True),
    "BID": (48, "sin fuente accesible, el sitio rechaza pedidos automatizados", False),
    "BID Invest": (48, "https://www.idbinvest.org/en/about-us", True),
    "CAF": (23, "https://www.caf.com/media/4677283/2506-caf-presentacion-de-inversionistas.pdf", True),
    "AIIB": (105, "https://www.aiib.org/en/treasury/", True),  # miembros ratificados, no aprobados
    "NDB": (10, "https://www.ndb.int/about-ndb/members/", True),
}


def membrecia_y_concentracion(df: pd.DataFrame, top: int = 5) -> pd.DataFrame:
    """Cruza la concentración medida con la cantidad de países miembro de cada institución.

    Pone a prueba la lectura que propuso la dirección del proyecto el 17 de septiembre de 2026:
    "a menor membrecía, más concentración".

    El cruce directo la confirma, pero una parte del efecto es mecánica y conviene separarla. Un
    banco con diez socios no puede repartir su cartera entre ochenta países, así que su top cinco
    va a ser alto aunque reparta de la forma más pareja posible. Por eso se agrega el **piso**: si
    la institución llegó a `n` países y les hubiera dado exactamente lo mismo a cada uno, su top
    cinco seria 5/n. La diferencia entre lo observado y ese piso es la concentración que NO explica
    el tamaño del conjunto de receptores, y es la que vale la pena comparar entre bancos.

    BID Lab queda fuera porque no tiene membrecía propia: es un fondo dentro del Grupo BID.
    """
    base = concentracion(df, top=top).set_index("institucion")
    filas = []
    for institucion, (miembros, fuente, verificado) in MIEMBROS.items():
        if institucion not in base.index:
            continue
        fila = base.loc[institucion]
        piso = round(100 * min(top / fila["paises"], 1.0), 1)
        filas.append(
            {
                "institucion": institucion,
                "miembros": miembros,
                "verificado": "sí" if verificado else "NO",
                "paises_receptores": int(fila["paises"]),
                "pct_top5": fila["pct_top5"],
                "piso_si_repartiera_parejo": piso,
                "exceso_sobre_el_piso": round(fila["pct_top5"] - piso, 1),
                "fuente": fuente,
            }
        )
    return pd.DataFrame(filas).sort_values("miembros")


def spearman(a: pd.Series, b: pd.Series) -> float:
    """Correlación de rangos, que es Pearson sobre los rangos. Evita depender de scipy."""
    return a.rank().corr(b.rank())


# ---------------------------------------------------------------------------
# 2b. Analisis pedidos por la direccion el 18 y el 22 de septiembre de 2026
# ---------------------------------------------------------------------------

# Paises de America Latina y el Caribe. La direccion pidio el 22/09 separar ALC del resto en los
# bancos globales, porque un banco que presta en todo el mundo y uno regional no son comparables
# sin ese recorte.
#
# El mapeo es NUESTRO y se aplica igual a todas las fuentes, a proposito. Cada banco publica su
# propia agrupacion regional y usarlas mezcladas reproduciria en la geografia el mismo problema
# que ya tenemos con los sectores: categorias que se llaman parecido y no miden lo mismo.
PAISES_ALC = frozenset({
    "Antigua and Barbuda", "Argentina", "Bahamas", "Bahamas, The", "Barbados", "Belize",
    "Bolivia", "Brazil", "Chile", "Colombia", "Costa Rica", "Cuba", "Dominica",
    "Dominican Republic", "Ecuador", "El Salvador", "Grenada", "Guatemala", "Guyana", "Haiti",
    "Honduras", "Jamaica", "Mexico", "Nicaragua", "Panama", "Paraguay", "Peru",
    "St. Kitts and Nevis", "St. Lucia", "St. Vincent and the Grenadines", "Suriname",
    "Trinidad and Tobago", "Uruguay", "Venezuela", "Venezuela, RB",
})

RE_ALC_AGREGADO = re.compile(
    r"\b(Latin America|Caribbean|Central America|South America|LAC)\b", re.I)


def region_de(pais: object) -> str:
    """Clasifica el receptor en ALC, resto del mundo, o agregado sin pais.

    Los agregados regionales se separan en dos porque no son lo mismo: "Caribbean Subregion" si
    dice algo sobre ALC, "Africa Region" no.
    """
    texto = str(pais or "").strip()
    if not texto:
        return "sin dato"
    if texto in PAISES_ALC:
        return "ALC"
    if RE_ALC_AGREGADO.search(texto):
        return "ALC (agregado regional)"
    if not es_pais_real(texto):
        return "otro agregado regional"
    return "resto del mundo"


def por_region(df: pd.DataFrame) -> pd.DataFrame:
    """Cuanto de la cartera de cada institucion va a America Latina y el Caribe."""
    d = df[df["monto_aprobado_usd"].notna()].copy()
    d["region"] = d["pais"].apply(region_de)
    tabla = d.pivot_table(index="institucion", columns="region", values="monto_aprobado_usd",
                          aggfunc="sum", fill_value=0.0) / 1e6
    alc = tabla.get("ALC", 0) + tabla.get("ALC (agregado regional)", 0)
    tabla["pct_alc"] = (100 * alc / tabla.sum(axis=1)).round(1)
    return tabla.round(0).sort_values("pct_alc", ascending=False)


def moneda_local(df: pd.DataFrame) -> pd.DataFrame:
    """Proporcion de operaciones denominadas en moneda local, por institucion.

    Lo pidio la direccion del proyecto el 22/09, en cantidad y en monto. Solo se puede contestar para las cuatro
    fuentes que declaran la moneda de origen: BID Invest, CAF, AIIB y NDB. Las otras seis informan
    en dolares sin decir si hubo conversion, asi que para ellas la pregunta no tiene respuesta con
    estas fuentes y eso tambien es un dato.
    """
    filas = []
    for institucion, tramo in df[df["moneda_original"].notna()].groupby("institucion"):
        local = tramo[tramo["moneda_original"] != "USD"]
        monto_total = tramo["monto_aprobado_usd"].sum()
        filas.append({
            "institucion": institucion,
            "ops_con_moneda": len(tramo),
            "ops_en_moneda_local": len(local),
            "pct_ops": round(100 * len(local) / len(tramo), 1),
            "pct_monto": round(100 * local["monto_aprobado_usd"].sum() / monto_total, 1) if monto_total else 0.0,
            "monedas": ", ".join(sorted(local["moneda_original"].dropna().unique())[:8]),
        })
    return pd.DataFrame(filas).sort_values("pct_ops", ascending=False)


def aporte_del_banco(df: pd.DataFrame) -> pd.DataFrame:
    """Que proporcion del costo total del proyecto pone el banco.

    Pedido de la direccion el 18/09 para el NDB ("75 sobre 300 no es lo mismo que 75 sobre 100") y
    de la direccion el 22/09 para el costo de contraparte. Solo lo permiten el BID, que publica el
    costo total como campo, y el NDB, que lo trae en prosa en 37 de sus 170 fichas.
    """
    d = df[df["costo_total_proyecto_usd"].notna() & df["monto_aprobado_usd"].notna()]
    d = d[d["costo_total_proyecto_usd"] > 0]
    filas = []
    for institucion, tramo in d.groupby("institucion"):
        proporcion = tramo["monto_aprobado_usd"] / tramo["costo_total_proyecto_usd"]
        proporcion = proporcion[proporcion <= 1.5]  # descarta filas donde el costo esta mal cargado
        filas.append({
            "institucion": institucion,
            "operaciones": len(proporcion),
            "aporte_banco_mm": round(tramo["monto_aprobado_usd"].sum() / 1e6),
            "costo_total_mm": round(tramo["costo_total_proyecto_usd"].sum() / 1e6),
            "contraparte_mm": round((tramo["costo_total_proyecto_usd"] - tramo["monto_aprobado_usd"]).sum() / 1e6),
            "pct_mediana_del_banco": round(100 * proporcion.median(), 1),
            "pct_financia_todo": round(100 * (proporcion >= 0.99).mean(), 1),
        })
    return pd.DataFrame(filas)


def tamano_medio(df: pd.DataFrame, desde: int = 2014) -> pd.DataFrame:
    """Monto medio y mediano por operacion y anio, dentro de cada grupo y ventanilla.

    La direccion lo sugirio el 22/09 como control complementario del argumento de que la suba de la
    ventanilla privada es de base amplia: si el monto medio se dispara, la suba vendria de
    operaciones mas grandes y no de mas operaciones.
    """
    d = df[(df["anio_aprobacion"] >= desde) & df["monto_aprobado_usd"].notna()]
    d = d[d["institucion"].isin(["BID", "BID Invest"])]
    return (
        d.groupby(["institucion", "anio_aprobacion"])
        .agg(operaciones=("id_proyecto", "size"),
             monto_medio_mm=("monto_aprobado_usd", lambda s: round(s.mean() / 1e6, 1)),
             monto_mediano_mm=("monto_aprobado_usd", lambda s: round(s.median() / 1e6, 1)))
        .reset_index()
    )


# ---------------------------------------------------------------------------
# 3. Composición de cartera
# ---------------------------------------------------------------------------


def composicion(df: pd.DataFrame) -> pd.DataFrame:
    """Operaciones y monto por institución, año y sector, tal como lo clasifica cada banco."""
    sub = df[df["sector"].notna()]
    tabla = (
        sub.groupby(["institucion", "anio_aprobacion", "sector"])
        .agg(operaciones=("id_proyecto", "size"), usd_millones=("monto_aprobado_usd", "sum"))
        .reset_index()
    )
    tabla["usd_millones"] = (tabla["usd_millones"] / 1e6).round(1)
    tabla["anio_aprobacion"] = tabla["anio_aprobacion"].astype(int)
    return tabla.sort_values(["institucion", "anio_aprobacion", "usd_millones"], ascending=[True, True, False])


# ---------------------------------------------------------------------------
# 4. Velocidad
# ---------------------------------------------------------------------------


def velocidad() -> pd.DataFrame:
    """Días entre la aprobación y la firma, por institución.

    Se lee del crudo y no del corpus porque la fecha de firma no entra al esquema común: no la
    publican todas las fuentes y no es parte de la unidad de análisis. Es un proxy del costo no
    financiero de operar con cada banco, no la medida completa, que incluiría la preparación
    previa a la aprobación y esa no la publica ninguna.
    """
    import csv
    import json
    import xml.etree.ElementTree as ET
    from datetime import datetime

    from src.common.normalizar import CRUDO, ultima_descarga

    def dias(a: str, b: str, formato: str) -> int | None:
        """Dias entre dos fechas, o None si alguna no se puede interpretar.

        Se corta por la 'T' de la marca horaria y no por longitud fija: '13-Jul-2000' tiene
        once caracteres y un truncado a diez lo convertia en '13-Jul-200', que no parsea.
        """
        try:
            n = (
                datetime.strptime(str(b).split("T")[0].strip(), formato)
                - datetime.strptime(str(a).split("T")[0].strip(), formato)
            ).days
        except Exception:
            return None
        return n if 0 < n < 3000 else None

    medidas: dict[str, list[int]] = {}

    ifc = json.loads(ultima_descarga("gbm/ifc_inversiones_*.json").read_text(encoding="utf-8"))["data"]
    medidas["IFC"] = [d for d in (dias(str(r.get("ifc_approval_date", "")), str(r.get("ifc_signed_date", "")), "%d-%b-%Y") for r in ifc) if d]

    raiz = ET.parse(ultima_descarga("gbid/bid-invest_proyectos_*.xml")).getroot()
    bi = [{h.tag: (h.text or "").strip() for h in it} for it in raiz]
    medidas["BID Invest"] = [d for d in (dias(r.get("approval_date", ""), r.get("signed_date", ""), "%Y-%m-%d") for r in bi) if d]

    with ultima_descarga("gbid/bid_proyectos_*.csv").open(encoding="utf-8-sig") as f:
        bid = list(csv.DictReader(f))
    medidas["BID"] = [d for d in (dias(r.get("apprvl_dt", ""), r.get("sign_dt", ""), "%Y-%m-%d") for r in bid) if d]

    return pd.DataFrame(
        [
            {
                "institucion": k,
                "operaciones": len(v),
                "mediana_dias": int(pd.Series(v).median()),
                "media_dias": int(pd.Series(v).mean()),
            }
            for k, v in medidas.items()
            if v
        ]
    ).sort_values("mediana_dias")


# ---------------------------------------------------------------------------


def main() -> int:
    md = "--markdown" in sys.argv
    df = cargar()

    def imprimir(titulo: str, tabla: pd.DataFrame) -> None:
        print(f"\n## {titulo}\n" if md else f"\n=== {titulo} ===")
        print(a_markdown(tabla) if md else tabla.to_string(index=False))

    print(f"Corpus: {len(df):,} operaciones, 2014 a 2025, sin canceladas.")

    imprimir("Ventanilla no soberana, dólares corrientes (2014-2025)", ventanillas(df))
    imprimir(f"Ventanilla no soberana, dólares constantes de {ANIO_BASE} (2014-2025)",
             ventanillas(df, constantes=True))
    largo = cargar(completo=True)
    imprimir("Ventanilla no soberana, serie larga desde 1989 (corrientes)",
             ventanillas(largo, desde=1989))
    imprimir("Operaciones sin monto publicado", sin_monto(df).head(20))
    imprimir("Concentración de los primeros cinco países receptores", concentracion(df))

    memb = membrecia_y_concentracion(df)
    imprimir("Membrecía contra concentración", memb.drop(columns="fuente"))
    print(f"\n  Spearman entre miembros y concentración: {spearman(memb.miembros, memb.pct_top5):+.3f} "
          f"(n={len(memb)})")
    print(f"  Pearson contra el logaritmo de los miembros: {np.log(memb.miembros).corr(memb.pct_top5):+.3f}")
    print(f"  Spearman entre miembros y el exceso sobre el piso: "
          f"{spearman(memb.miembros, memb.exceso_sobre_el_piso):+.3f}")
    imprimir("Velocidad: días entre aprobación y firma", velocidad())
    imprimir("Préstamos en moneda local", moneda_local(df))
    imprimir("Aporte del banco sobre el costo total del proyecto", aporte_del_banco(df))
    imprimir("Destino: América Latina y el Caribe contra el resto", por_region(df).reset_index())
    imprimir("Tamaño medio de operación en el Grupo BID", tamano_medio(df))

    comp = composicion(df)
    imprimir("Composición de cartera (muestra)", comp.head(15))

    if "--csv" in sys.argv:
        COMPOSICION.mkdir(parents=True, exist_ok=True)
        for institucion, tramo in comp.groupby("institucion"):
            nombre = str(institucion).lower().replace(" ", "-")
            tramo.to_csv(COMPOSICION / f"{nombre}.csv", index=False)
        print(f"\nComposición por banco escrita en {COMPOSICION.relative_to(RAIZ)}/")

        # La tabla completa de operaciones sin monto va como archivo aparte: la dirección la pidió
        # para poder ir al documento de cada una, y eso no se hace mirando las primeras veinte.
        faltantes = COMPOSICION.parent / "operaciones-sin-monto.csv"
        sin_monto(df).to_csv(faltantes, index=False)
        print(f"Operaciones sin monto escritas en {faltantes.relative_to(RAIZ)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
