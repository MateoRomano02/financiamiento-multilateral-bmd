"""Anexo "List of Projects Approved by NDB" del informe anual del NDB.

Por qué existe. El corpus del NDB sale del listado web y de la ficha de cada proyecto. La ficha
publica el monto vigente: en una operación cancelada queda sin monto, y en una cancelada en parte
muestra lo que quedó. El anexo del informe anual lista las 139 operaciones aprobadas 2016-2025
con el monto que aprobó el directorio, y con notas al pie que dicen qué se canceló y cuándo.
La investigación del 8/10/2026 midió la diferencia: 4.908 M de dólares (11,5% del total) entre lo
que suma el corpus y lo que declara el informe.

Extracción. Se usa pdfplumber, que es Python puro y corre en GitHub Actions sin instalar nada del
sistema. El texto plano de la página no alcanza: los nombres largos ocupan dos o tres líneas, una
arriba y otra abajo de la línea que lleva el número, y sin posición no se sabe a qué fila
pertenece cada una. Por eso se leen las palabras con sus coordenadas y cada línea de nombre se
asigna a la fila cuyo número está más cerca en vertical.

Emparejamiento con el corpus: por URL de la ficha cuando la tabla ALIAS_URL la tiene, y si no por
nombre normalizado y país.
"""

from __future__ import annotations

import difflib
import html
import re
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent

# Páginas del anexo en el PDF del informe 2025 (1 = primera). Se localizan igual por el encabezado,
# esto es solo el rango de búsqueda.
PAGINAS_ANEXO = range(180, 190)

# Límites horizontales de las columnas, en puntos del PDF (página A4 de 595 de ancho).
X_NOMBRE, X_TIPO, X_PAIS, X_MONEDA, X_MONTO = 85, 295, 365, 425, 475

URL_INFORME = "https://www.ndb.int/wp-content/uploads/2026/07/NDB_AnnualReport2025.pdf"

# Nombres de la web que el informe escribe distinto, o un proyecto que el informe parte en dos
# filas (5 y 6, 41 y 42). Clave: número de fila del anexo. Valor: URL de la ficha en el listado web.
# Armada a mano el 8/10/2026 contra el corpus; el emparejamiento por URL no depende de cómo se
# escriba el nombre. Las operaciones nuevas del informe no están acá: se emparejan por nombre.
ALIAS_URL = {
    1: "https://www.ndb.int/project/bndesbrazil/",
    4: (
        "https://www.ndb.int/project/"
        "eskom-renewable-energy-integration-and-transmission-augmentation-project/"
    ),
    5: "https://www.ndb.int/project/edbiibrussia/",
    6: "https://www.ndb.int/project/edbiibrussia/",
    28: "https://www.ndb.int/project/mumbai-metro-rail-project-india/",
    33: (
        "https://www.ndb.int/project/"
        "guangxi-chongzuo-urban-water-system-ecological-restoration-project/"
    ),
    41: "https://www.ndb.int/project/india-andhra-pradesh-road-sector-project/",
    42: "https://www.ndb.int/project/india-andhra-pradesh-road-sector-project/",
    44: (
        "https://www.ndb.int/project/"
        "bndes-clima-sustainable-financing-to-support-global-climate-change-mitigation-and-adaptation-in-brazil/"
    ),
    54: "https://www.ndb.int/project/china-ndb-emergency-assistance-program-combating-covid-19/",
    56: "https://www.ndb.int/project/india-ndb-emergency-assistance-program-combating-covid-19/",
    58: "https://www.ndb.int/project/south-africa-covid-19-emergency-program/",
    60: "https://www.ndb.int/project/brazil-emergency-assistance-program-combating-covid-19/",
    66: "https://www.ndb.int/project/brazil-brazil-emergency-assistance-program-economic-recovery/",
    67: (
        "https://www.ndb.int/project/"
        "india-covid-19-emergency-program-loan-supporting-indias-economic-recovery-covid-19/"
    ),
    73: (
        "https://www.ndb.int/project/"
        "china-emergency-assistance-program-supporting-chinas-economic-recovery-covid-19/"
    ),
    75: (
        "https://www.ndb.int/project/"
        "covid-19-emergency-program-loan-for-supporting-russias-healthcare-response/"
    ),
    77: (
        "https://www.ndb.int/project/"
        "covid-19-emergency-program-loan-for-supporting-south-africas-economic-recovery-from-covid-19/"
    ),
    116: "https://www.ndb.int/project/dhaka-water-supply-project/",
    126: "https://www.ndb.int/project/greener-shanghai-project/",
}


@dataclass
class FilaAnexo:
    numero: int
    nombre: str
    tipo: str  # "soberana" o "no_soberana"
    pais: str
    moneda: str  # moneda en que el informe publica el monto
    monto_millones: float  # en `moneda_monto`
    moneda_monto: str  # igual a `moneda`, salvo "USD n equivalent" donde el monto es en USD
    anio_aprobacion: int
    pagina: int
    nota: str = ""
    cancelada_total: bool = False
    anio_cancelacion: int | None = None
    equivalente: bool = field(default=False)  # el informe da el monto como "USD n equivalent"


def _numero(texto: str) -> float:
    return float(texto.replace(",", ""))


def _lineas(palabras: list[dict]) -> list[list[dict]]:
    """Agrupa palabras en líneas por coordenada vertical, de arriba abajo."""
    lineas: list[list[dict]] = []
    for p in sorted(palabras, key=lambda w: (round(w["top"]), w["x0"])):
        if lineas and abs(lineas[-1][0]["top"] - p["top"]) < 2.5:
            lineas[-1].append(p)
        else:
            lineas.append([p])
    return [sorted(linea, key=lambda w: w["x0"]) for linea in lineas]


def _notas_al_pie(lineas: list[list[dict]], desde_top: float) -> dict[int, str]:
    """Notas al pie de la página: un número en la columna 1 y el texto en la columna de nombre."""
    notas: dict[int, str] = {}
    ultima = None
    for linea in lineas:
        if linea[0]["top"] <= desde_top:
            continue
        primero = linea[0]
        if primero["x0"] < X_NOMBRE and primero["text"].isdigit():
            ultima = int(primero["text"])
            notas[ultima] = " ".join(w["text"] for w in linea[1:])
        elif ultima is not None:
            notas[ultima] += " " + " ".join(w["text"] for w in linea)
    return notas


def _filas_de_pagina(pagina, indice: int) -> list[FilaAnexo]:
    palabras = pagina.extract_words()
    lineas = _lineas(palabras)

    # Encabezados de año: una página puede traer dos (por ejemplo 2016 y 2017). El bloque de
    # encabezado va desde "OPERATIONS APPROVED IN" hasta la línea "(million)", y no es dato.
    encabezados: list[tuple[float, int]] = []
    en_encabezado = False
    sin_encabezado = []
    for linea in lineas:
        texto = " ".join(w["text"] for w in linea)
        m = re.search(r"OPERATIONS APPROVED IN (\d{4})", texto)
        if m:
            encabezados.append((linea[0]["top"], int(m.group(1))))
            en_encabezado = True
        if en_encabezado:
            if "(million)" in texto:
                en_encabezado = False
            continue
        sin_encabezado.append(linea)
    if not encabezados:
        return []
    lineas = sin_encabezado

    # Una fila de datos es la línea que tiene número en la primera columna y tipo en la tercera.
    ancla = []
    for linea in lineas:
        tipo = [w for w in linea if X_TIPO <= w["x0"] < X_PAIS
                and w["text"].lower() in ("sovereign", "non-sovereign")]
        if linea[0]["x0"] < X_NOMBRE and linea[0]["text"].isdigit() and tipo:
            ancla.append(linea)
    if not ancla:
        return []

    # Cada palabra que no es de la línea ancla va a la fila más cercana en vertical.
    tops = [a[0]["top"] for a in ancla]
    asignadas: list[list[dict]] = [[] for _ in ancla]
    pie = max(tops) + 40  # el pie de nota empieza después de la última fila
    for linea in lineas:
        t = linea[0]["top"]
        if t < tops[0] - 40:
            continue
        if linea[0]["x0"] < X_NOMBRE and linea[0]["text"].isdigit() and linea not in ancla:
            pie = min(pie, t)  # primera nota al pie
            break
        j = min(range(len(ancla)), key=lambda i: abs(tops[i] - t))
        asignadas[j].extend(linea)

    notas = _notas_al_pie(lineas, pie - 1)
    filas = []
    for a, resto in zip(ancla, asignadas):
        top = a[0]["top"]
        numero = int(a[0]["text"])
        anio = [y for t, y in encabezados if t < top][-1]
        tipo_txt = " ".join(w["text"] for w in a if X_TIPO <= w["x0"] < X_PAIS)
        pais = " ".join(w["text"] for w in a if X_PAIS <= w["x0"] < X_MONEDA)
        moneda = next((w["text"] for w in a if X_MONEDA <= w["x0"] < X_MONTO), "")
        # Una llamada a nota al pie puede caer entre la moneda y el monto ("USD 55 300"): el monto
        # es siempre el último número de la fila.
        numeros = [w for w in a if w["x0"] >= X_MONEDA and re.fullmatch(r"[\d,.]+", w["text"])]
        monto_txt = numeros[-1]["text"] if numeros else None
        if len(numeros) > 1 and int(numeros[0]["text"]) in notas:
            nota_monto = notas[int(numeros[0]["text"])]
        else:
            nota_monto = ""
        equivalente = False
        moneda_monto = moneda
        if monto_txt is None:
            # "USD 50 equivalent": el monto está en dólares aunque la moneda de la operación sea otra
            # y viene en una línea aparte, encima o debajo de la fila.
            otras = [w for w in resto if w["x0"] >= X_MONEDA and abs(w["top"] - top) > 2.5]
            texto = " ".join(w["text"] for w in sorted(otras, key=lambda w: (w["top"], w["x0"])))
            m = re.search(r"USD\s+([\d,.]+)\s+equivalent", texto)
            if not m:
                raise ValueError(f"fila {numero}: sin monto en {texto!r}")
            monto_txt, moneda_monto, equivalente = m.group(1), "USD", True

        nombre_palabras = [w for w in resto if X_NOMBRE <= w["x0"] < X_TIPO]
        nombre_palabras.sort(key=lambda w: (round(w["top"]), w["x0"]))
        # Llamada a nota al pie: un número de dos cifras que es el de una nota de esta página,
        # pegado al final de alguna de las líneas del nombre.
        nota = ""
        partes = []
        for w in nombre_palabras:
            if re.fullmatch(r"\d{2}", w["text"]) and int(w["text"]) in notas:
                nota = notas[int(w["text"])]
            else:
                partes.append(w["text"])
        nombre = " ".join(partes)
        nota = f"{nota} {nota_monto}".strip()
        cancel = re.match(r"Cancelled in (\d{4})", nota)
        filas.append(FilaAnexo(
            numero=numero,
            nombre=re.sub(r"\s+", " ", nombre).strip(),
            tipo="soberana" if tipo_txt.lower() == "sovereign" else "no_soberana",
            pais=pais,
            moneda=moneda,
            monto_millones=_numero(monto_txt),
            moneda_monto=moneda_monto,
            anio_aprobacion=anio,
            pagina=indice + 1,
            nota=nota,
            cancelada_total=bool(cancel),
            anio_cancelacion=int(cancel.group(1)) if cancel else None,
            equivalente=equivalente,
        ))
    return filas


def leer_anexo(ruta_pdf: Path) -> list[FilaAnexo]:
    """Las operaciones del anexo, en el orden del informe (numeradas desde 1)."""
    import pdfplumber

    filas: list[FilaAnexo] = []
    with pdfplumber.open(ruta_pdf) as pdf:
        for i in PAGINAS_ANEXO:
            if i < len(pdf.pages):
                filas.extend(_filas_de_pagina(pdf.pages[i], i))
    return sorted(filas, key=lambda f: f.numero)


def normalizar_nombre(nombre: str) -> str:
    """Minúsculas, sin entidades HTML, sin puntuación: para comparar nombres de web e informe."""
    n = html.unescape(nombre).lower().replace("-", " ")
    n = n.replace("’", "'")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", n)).strip()


def _pais_comparable(pais: str) -> str:
    p = normalizar_nombre(pais)
    return {"russian federation": "russia"}.get(p, p)


def emparejar(fila: FilaAnexo, candidatos: list[dict]) -> int | None:
    """Índice del candidato (con claves url_proyecto, nombre, pais) que es esta fila, o None.

    Primero la URL de la ficha, si ALIAS_URL la tiene. Si no, el nombre normalizado igual y, en
    último caso, el más parecido del mismo país con similitud de al menos 0,75. Un nombre que
    se parece pero es de otro país pierde 0,15, así no se confunde una repetición en dos países.
    """
    url = ALIAS_URL.get(fila.numero)
    if url:
        for i, c in enumerate(candidatos):
            if (c.get("url_proyecto") or "").rstrip("/") == url.rstrip("/"):
                return i
        return None
    objetivo = normalizar_nombre(fila.nombre)
    mejor, mejor_i = 0.0, None
    for i, c in enumerate(candidatos):
        n = normalizar_nombre(c["nombre"])
        puntaje = 1.0 if n == objetivo else difflib.SequenceMatcher(None, objetivo, n).ratio()
        if _pais_comparable(c.get("pais") or "") != _pais_comparable(fila.pais):
            puntaje -= 0.15
        if puntaje > mejor:
            mejor, mejor_i = puntaje, i
    return mejor_i if mejor >= 0.75 else None
