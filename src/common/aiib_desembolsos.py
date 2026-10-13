"""Desembolsos del AIIB: unión de su lista oficial de proyectos desembolsados con el corpus.

La fuente es `AIIB-List-of-Disbursed-Projects-Since-2016.xlsx`, con corte al 31/12/2025. El
archivo no se puede bajar solo (la página no expone el enlace), así que entra como carga manual
(ver data/raw/aiib/manifest.json). Se trata como dato no confiable: solo se lee con openpyxl.

El Project ID del archivo no sirve de clave (el corpus no lo tiene), así que se cruza por dos
claves fuertes y de a una fila por vez, en este orden:

1. La ficha: el último tramo de la URL de aiib.org que el archivo trae en "Target Results".
2. El nombre sin el prefijo "País:" ni siglas entre paréntesis, normalizado.

Un cruce solo vale si es uno a uno: si la clave se repite en el corpus o en el archivo, ninguna
de esas filas se une, porque sería adivinar. El cruce por solapamiento de palabras se descartó
(en la revisión dio pares con años invertidos y montos que no cierran).
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import openpyxl
import pandas as pd

HOJA = "All Projects Table 2016-2025"
CORTE = "2025-12-31"
FICHA = re.compile(r"aiib\.org/en/projects/details/[^\s]*?/([^/\s]+?)\.html", re.IGNORECASE)


def slug_de_url(texto) -> str | None:
    """El tramo final de la ficha del proyecto, en minúsculas. Ignora los PDF de documentos."""
    hallado = FICHA.search(str(texto or ""))
    return hallado.group(1).lower() if hallado else None


def nombre_clave(nombre) -> str:
    """Nombre sin prefijo de país ni siglas entre paréntesis, sin tildes ni puntuación."""
    texto = str(nombre or "")
    texto = re.sub(r"^[^:]{1,40}:\s*", "", texto)
    texto = re.sub(r"\([^)]*\)", " ", texto)
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def leer_lista(ruta: Path) -> pd.DataFrame:
    """Lee la hoja de proyectos. Montos en millones de USD, vacíos si el banco no los publica."""
    hoja = openpyxl.load_workbook(ruta, read_only=True, data_only=True)[HOJA]
    filas = []
    for r in list(hoja.iter_rows(values_only=True))[1:]:
        if not r[0]:
            continue
        def numero(v):
            return float(v) if isinstance(v, (int, float)) else None
        filas.append({"id": str(r[0]), "nombre": r[1], "anio": int(r[4]) if r[4] else None,
                      "slug": slug_de_url(r[6]), "compromiso_musd": numero(r[8]),
                      "desembolso_musd": numero(r[10])})
    return pd.DataFrame(filas)


def _unicos(serie: pd.Series) -> pd.Series:
    """Claves que aparecen una sola vez y no vacías."""
    return serie[serie.notna() & (serie != "") & ~serie.duplicated(keep=False)]


def cruzar(corpus: pd.DataFrame, lista: pd.DataFrame) -> pd.DataFrame:
    """Devuelve una fila por cruce seguro: indice del corpus, fila de la lista y paso usado."""
    claves = {
        "ficha": (corpus["url_proyecto"].map(slug_de_url), lista["slug"]),
        "nombre": (corpus["nombre"].map(nombre_clave), lista["nombre"].map(nombre_clave)),
    }
    pares, usado_c, usado_l = [], set(), set()
    for paso, (kc, kl) in claves.items():
        # Las claves únicas se calculan entre las filas que siguen libres, así un cruce ya hecho
        # no vuelve a competir por el mismo desembolso.
        libre_c = kc[~kc.index.isin(usado_c)]
        libre_l = kl[~kl.index.isin(usado_l)]
        uc, ul = _unicos(libre_c), _unicos(libre_l)
        comunes = set(uc) & set(ul)
        por_l = {v: i for i, v in ul.items()}
        for i, v in uc.items():
            if v in comunes:
                j = por_l[v]
                pares.append({"indice": i, "fila_lista": j, "paso": paso})
                usado_c.add(i)
                usado_l.add(j)
    return pd.DataFrame(pares, columns=["indice", "fila_lista", "paso"])


def unir_desembolsos(df: pd.DataFrame, ruta: Path) -> pd.DataFrame:
    """Carga monto_desembolsado_usd con el desembolso acumulado al 31/12/2025.

    No toca monto_aprobado_usd aunque el compromiso neto del archivo difiera. Las no soberanas
    sin dato en el archivo quedan vacías. Los cruces quedan en `df.attrs["aiib_cruces"]`.
    """
    lista = leer_lista(ruta)
    cruces = cruzar(df, lista)
    df = df.copy()
    df["monto_desembolsado_usd"] = df["monto_desembolsado_usd"].astype("float64")
    for _, c in cruces.iterrows():
        fila = lista.loc[c["fila_lista"]]
        if fila["desembolso_musd"] is not None and not pd.isna(fila["desembolso_musd"]):
            df.loc[c["indice"], "monto_desembolsado_usd"] = fila["desembolso_musd"] * 1e6
    df.attrs["aiib_cruces"] = cruces.merge(lista, left_on="fila_lista", right_index=True)
    return df
