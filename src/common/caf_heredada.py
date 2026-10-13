"""CAF 2014-2022 desde la base heredada del relevamiento 2022, cruzada con el archivo IATI.

El archivo IATI de CAF trae el 27% de lo aprobado según los informes anuales (H37). La base
heredada (`data/raw/legacy/caf/caf_final.xlsx`, 1.087 filas) la reconstruyó el equipo de 2022 desde
esos informes y suma el 99,1% de su total para 2014-2022. Por eso, para esos años la base de
operaciones de CAF es la heredada, y el IATI aporta atributos (ficha, desembolsos, prestatario,
descripción, estado, fecha exacta) a las filas con las que cruza. Las decisiones técnicas están en
`docs/criterios-codificacion.md`, sección "CAF 2014-2022: base heredada como base de operaciones".
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

from .esquema import COLUMNAS

RAIZ = Path(__file__).resolve().parent.parent.parent
RUTA_HEREDADA = RAIZ / "data" / "raw" / "legacy" / "caf" / "caf_final.xlsx"
RUTA_INFORMES = sorted((RAIZ / "data" / "raw" / "referencia").glob("caf_aprobaciones_informes_*.csv"))

ANIO_DESDE, ANIO_HASTA = 2014, 2022

# Valores de la columna origen_fila.
ORIGEN_IATI = "iati"
ORIGEN_HEREDADA = "heredada"
ORIGEN_HEREDADA_IATI = "heredada_iati"

# Tolerancias del cruce IATI contra heredada. El monto del IATI y el del informe difieren hasta
# 2% por redondeos y por tipo de cambio; el año del informe puede estar corrido un año respecto de
# la fecha de compromiso del IATI.
TOLERANCIA_MONTO = 0.02
TOLERANCIA_ANIO = 1

# Nombres de país de la base heredada llevados al nombre que usa el resto del corpus.
PAISES = {
    "argentina": "Argentina", "barbados": "Barbados", "bolivia": "Bolivia", "brasil": "Brazil",
    "chile": "Chile", "colombia": "Colombia", "costa rica": "Costa Rica", "ecuador": "Ecuador",
    "el salvador": "El Salvador", "españa": "Spain", "mexico": "Mexico", "méxico": "Mexico",
    "multinacional": "Regional", "multinacionales": "Regional", "panama": "Panama",
    "panamá": "Panama", "paraguay": "Paraguay", "perú": "Peru", "peru": "Peru",
    "portugal": "Portugal", "rep. dominicana": "Dominican Republic",
    "república dominicana": "Dominican Republic", "trinidad y tobago": "Trinidad and Tobago",
    "uruguay": "Uruguay", "venezuela": "Venezuela",
}

# Tipo de inversión de la base heredada a la forma de financiamiento del esquema. La cooperación
# técnica va como donación igual que en el BID; la inversión patrimonial como "otro".
FORMAS = {
    "linea de credito": "prestamo", "prestamo": "prestamo", "pbl": "prestamo", "swap": "prestamo",
    "cooperacion tecnica": "donacion", "inversion patrimonial": "otro", "otros": "otro",
}

RIESGOS = {"soberano": "soberana", "no soberano": "no_soberana"}


def _sin_acentos(texto: object) -> str:
    base = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in base if not unicodedata.combining(c))


def _clave(texto: object) -> str:
    """Texto en minúsculas, sin acentos, sin puntuación y con espacios simples."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", _sin_acentos(texto).lower())).strip()


def _limpiar(texto: object) -> str | None:
    if texto is None or (isinstance(texto, float) and pd.isna(texto)):
        return None
    limpio = re.sub(r"\s+", " ", str(texto)).strip()
    return limpio or None


def pais_heredado(valor: object) -> str | None:
    limpio = _limpiar(valor)
    return PAISES.get(limpio.lower(), limpio) if limpio else None


def _urls_de_informes() -> dict[int, str]:
    if not RUTA_INFORMES:
        return {}
    inf = pd.read_csv(RUTA_INFORMES[-1])
    return {int(a): u for a, u in zip(inf["anio"], inf["fuente_url"])}


def leer_heredada(ruta: Path = RUTA_HEREDADA, relevamiento: str = "2026-10-09") -> pd.DataFrame:
    """Lee la base heredada y la lleva al esquema común, sin repetidas exactas.

    Se elimina solo la fila idéntica en las nueve columnas (1 fila, USD 70 millones, 2022). Las
    filas que repiten año, país, nombre y monto pero tienen otro prestatario no son duplicados:
    son líneas de crédito revolventes a bancos distintos, y quitarlas baja el total de 2016 y 2022
    a 87% y 84% del informe.
    """
    crudo = pd.read_excel(ruta)
    crudo.columns = ["nombre", "pais", "prestatario", "anio", "monto", "sector", "tipo", "riesgo", "descripcion"]
    crudo = crudo.drop_duplicates(keep="first").reset_index(drop=True)
    urls = _urls_de_informes()
    ruta_relativa = ruta.relative_to(RAIZ) if ruta.is_relative_to(RAIZ) else ruta
    filas, usados = [], set()
    for r in crudo.itertuples(index=False):
        anio = int(r.anio)
        nombre, prestatario = _limpiar(r.nombre), _limpiar(r.prestatario)
        pais = pais_heredado(r.pais)
        semilla = "|".join(map(str, (anio, pais, nombre, prestatario, int(r.monto), _limpiar(r.descripcion))))
        id_proyecto = f"CAF-H-{anio}-{hashlib.sha1(semilla.encode()).hexdigest()[:8]}"
        # Dos filas distintas con el mismo hash corto son imposibles hoy, pero el id debe ser único.
        n = 2
        base = id_proyecto
        while id_proyecto in usados:
            id_proyecto, n = f"{base}-{n}", n + 1
        usados.add(id_proyecto)
        tipo = _limpiar(r.tipo)
        riesgo = RIESGOS.get((_limpiar(r.riesgo) or "").lower())
        informe = urls.get(anio)
        fuente = (f"Base heredada del relevamiento 2022, reconstruida desde los informes anuales de CAF: "
                  f"{ruta_relativa}" + (f"; informe {anio}: {informe}" if informe else ""))
        filas.append({
            "banco_grupo": "CAF", "institucion": "CAF",
            "tipo_ventanilla": riesgo,
            "tipo_prestatario": riesgo or "sin_dato",
            "prestatario": prestatario,
            "id_proyecto": id_proyecto, "nombre": nombre, "descripcion": _limpiar(r.descripcion),
            "pais": pais, "url_proyecto": None,
            # La base trae solo el año: se ancla al 1 de enero, igual que el AIIB.
            "fecha_aprobacion": f"{anio}-01-01", "anio_aprobacion": anio,
            "estado": "desconocido", "estado_original": None,
            "monto_aprobado_usd": float(r.monto),
            "instrumento": tipo,
            "forma_financiamiento": FORMAS.get(_clave(tipo)) if tipo else None,
            "sector": _limpiar(r.sector),
            "fuente_url": fuente, "fecha_relevamiento": relevamiento,
            "origen_fila": ORIGEN_HEREDADA,
        })
    df = pd.DataFrame(filas)
    for col in COLUMNAS:
        if col not in df.columns:
            df[col] = None
    return df[list(COLUMNAS)]


def _similitud(a: object, b: object) -> float:
    return SequenceMatcher(None, _clave(a), _clave(b)).ratio()


def _paises_iati(valor: object) -> set[str]:
    return {p.strip() for p in str(valor or "").split(";") if p.strip()}


def cruzar(heredada: pd.DataFrame, iati: pd.DataFrame) -> list[tuple[int, int]]:
    """Empareja 1 a 1 filas heredadas con operaciones IATI. Devuelve pares (pos. heredada, pos. IATI).

    Condiciones: año con tolerancia de uno, país igual (el IATI multipaís cruza si contiene el
    país), monto dentro de 2%. Entre los candidatos manda primero el mismo año, después la
    similitud del nombre y por último la cercanía del monto. La asignación es codiciosa.
    """
    candidatos = []
    paises = [_paises_iati(p) for p in iati["pais"]]
    montos_i = iati["monto_aprobado_usd"].to_numpy()
    anios_i = iati["anio_aprobacion"].to_numpy()
    for h, fila in enumerate(heredada.itertuples(index=False)):
        for i in range(len(iati)):
            if pd.isna(montos_i[i]) or pd.isna(anios_i[i]):
                continue
            dif_anio = abs(int(anios_i[i]) - int(fila.anio_aprobacion))
            if dif_anio > TOLERANCIA_ANIO or fila.pais not in paises[i]:
                continue
            dif_monto = abs(montos_i[i] - fila.monto_aprobado_usd) / fila.monto_aprobado_usd
            if dif_monto > TOLERANCIA_MONTO:
                continue
            candidatos.append((dif_anio, -_similitud(fila.nombre, iati["nombre"].iloc[i]), dif_monto, h, i))
    candidatos.sort()
    usado_h, usado_i, pares = set(), set(), []
    for _, _, _, h, i in candidatos:
        if h not in usado_h and i not in usado_i:
            usado_h.add(h), usado_i.add(i)
            pares.append((h, i))
    return pares


# Atributos que el IATI le aporta a la fila heredada con la que cruza.
ATRIBUTOS_IATI = ("url_proyecto", "monto_desembolsado_usd", "prestatario", "descripcion", "estado",
                  "estado_original")


def enriquecer(heredada: pd.DataFrame, iati: pd.DataFrame, pares: list[tuple[int, int]]) -> pd.DataFrame:
    """Copia a cada fila heredada cruzada los atributos de su operación IATI.

    El monto, el país, el nombre y el año quedan los de la base heredada: es la que suma al
    informe. El prestatario, la descripción y el tipo de prestatario del IATI reemplazan a los de
    la heredada porque son más finos. La fecha exacta del IATI se usa solo si cae en el mismo año
    que el de la base heredada; si no, manda el año del informe para no mover la fila de año.
    El identificador IATI queda en la fuente para poder volver a la operación.
    """
    out = heredada.copy()
    for h, i in pares:
        ia = iati.iloc[i]
        pos = out.index[h]
        for col in ATRIBUTOS_IATI:
            valor = ia[col]
            if pd.notna(valor) and str(valor).strip():
                out.at[pos, col] = valor
        if pd.notna(ia["tipo_prestatario"]):
            out.at[pos, "tipo_prestatario"] = ia["tipo_prestatario"]
        # La ventanilla declarada en la base heredada manda; si dice "sin especificar", la completa el IATI.
        if pd.isna(out.at[pos, "tipo_ventanilla"]):
            out.at[pos, "tipo_ventanilla"] = ia["tipo_ventanilla"]
        if pd.notna(ia["fecha_aprobacion"]) and int(str(ia["fecha_aprobacion"])[:4]) == int(out.at[pos, "anio_aprobacion"]):
            out.at[pos, "fecha_aprobacion"] = ia["fecha_aprobacion"]
        out.at[pos, "fuente_url"] = f"{out.at[pos, 'fuente_url']}; atributos del IATI {ia['id_proyecto']}"
        out.at[pos, "origen_fila"] = ORIGEN_HEREDADA_IATI
    return out


# Una IATI sin cruce solo se agrega si el año de la base heredada queda corto frente al informe
# por más de este margen. Sin ese piso, el IATI sin cruce son casi siempre las mismas operaciones
# que la heredada con otro nombre o monto, y agregarlas pasa el total del informe.
PISO_COBERTURA = 0.97
# Si la IATI sin cruce se parece a una fila heredada del mismo país y año (+-1) por nombre, se
# la trata como la misma operación con distinto monto y no se agrega.
UMBRAL_GEMELA = 0.6


def _totales_informe() -> dict[int, float]:
    if not RUTA_INFORMES:
        return {}
    inf = pd.read_csv(RUTA_INFORMES[-1])
    return {int(a): float(t) * 1e6 for a, t in zip(inf["anio"], inf["total_aprobado_musd"])}


def elegir_iati_sin_sumar(heredada: pd.DataFrame, iati_libres: pd.DataFrame,
                          informe: dict[int, float]) -> list[int]:
    """Posiciones de las IATI sin cruce que se agregan a la base heredada.

    Por año con cobertura heredada menor a 97% del informe: de mayor a menor monto, se agrega la
    IATI que no tiene gemela por nombre en la heredada y que no hace pasar el total del informe.
    """
    elegidas = []
    for anio, total_h in heredada.groupby("anio_aprobacion")["monto_aprobado_usd"].sum().items():
        meta = informe.get(int(anio))
        if not meta or total_h >= PISO_COBERTURA * meta:
            continue
        acumulado = total_h
        libres = iati_libres[iati_libres["anio_aprobacion"] == anio].sort_values(
            "monto_aprobado_usd", ascending=False)
        for i, fila in libres.iterrows():
            monto = fila["monto_aprobado_usd"]
            if pd.isna(monto) or acumulado + monto > meta:
                continue
            vecinas = heredada[(heredada["anio_aprobacion"].sub(anio).abs() <= TOLERANCIA_ANIO)
                               & (heredada["pais"].isin(_paises_iati(fila["pais"])))]
            if any(_similitud(n, fila["nombre"]) >= UMBRAL_GEMELA for n in vecinas["nombre"]):
                continue
            acumulado += monto
            elegidas.append(i)
    return elegidas


def construir_caf(iati: pd.DataFrame) -> pd.DataFrame:
    """Operaciones de CAF del corpus: heredada 2014-2022 (cruzada con el IATI) más el IATI restante.

    `iati` es la salida acumulada de normalizar_iati para CAF. Si no está la base heredada, se
    devuelve el IATI tal cual, con origen_fila = iati.
    """
    iati = iati.copy()
    iati["origen_fila"] = ORIGEN_IATI
    if not RUTA_HEREDADA.exists():
        return iati
    heredada = leer_heredada()
    en_rango = iati["anio_aprobacion"].between(ANIO_DESDE, ANIO_HASTA)
    iati_rango = iati[en_rango].reset_index(drop=True)
    resto = iati[~en_rango]
    pares = cruzar(heredada, iati_rango)
    base = enriquecer(heredada, iati_rango, pares)
    cruzadas = {i for _, i in pares}
    libres = iati_rango[~iati_rango.index.isin(cruzadas)]
    agregar = elegir_iati_sin_sumar(heredada, libres, _totales_informe())
    partes = [base, iati_rango.loc[agregar], resto]
    return pd.concat([p for p in partes if len(p)], ignore_index=True)[list(COLUMNAS)]
