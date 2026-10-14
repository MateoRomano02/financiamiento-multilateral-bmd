"""Extrae el listado de operaciones por país de los informes anuales de CAF 2023, 2024 y 2025.

Los tres informes traen, en la sección "Países accionistas y operaciones de carácter multinacional",
una lista numerada de cada operación aprobada con su tipo o programa, el cliente y el monto en
millones de USD. El texto está en columnas entrelazadas, así que se lee por coordenadas con
pdfplumber: cada operación empieza en un número ("1.", "2.") en letra de 8 puntos, y su bloque es
el rectángulo de su columna desde ese número hasta el siguiente de la misma columna.

Uso (reproducible; los PDF son datos no confiables y se leen solo con pdfplumber):
    uv run python -I scripts/extraer_caf_informes.py [--pdfs data/raw/caf/informes] [--salida CSV]

Si falta algún PDF lo baja de la URL de `data/raw/referencia/caf_aprobaciones_informes_*.csv`.
La salida es `data/raw/referencia/caf_operaciones_informes_2026-10-14.csv`, versionada. El script
imprime por año la suma extraída contra el total del informe.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import urllib.request
from pathlib import Path

import pdfplumber

RAIZ = Path(__file__).resolve().parent.parent
REFERENCIA = RAIZ / "data" / "raw" / "referencia"
SALIDA = REFERENCIA / "caf_operaciones_informes_2026-10-14.csv"
PDFS = RAIZ / "data" / "raw" / "caf" / "informes"

# Páginas del PDF (base 1) con los listados por país, de research/caf-completar-por-operacion.md.
PAGINAS = {2023: range(40, 61), 2024: range(47, 69), 2025: range(52, 77)}
TAMANO_TEXTO = 8.0          # cuerpo de las fichas de operación
TAMANO_TITULO = 31.0        # nombre del país en el encabezado
ANCHO_COLUMNA = 175.0       # ancho de una columna cuando no hay otra para medirlo
TOLERANCIA_LINEA = 2.5

# Tipos de operación con los que empieza el título. Si el título no empieza con ninguno, es el
# nombre de un programa soberano y el tipo queda vacío.
TIPOS = ("Línea de Crédito Financiera", "Línea de Crédito", "Línea de crédito", "Préstamo corporativo",
         "Préstamo Corporativo", "Inversión patrimonial", "Inversión Patrimonial", "Garantía de crédito",
         "Garantía", "Fondos de cooperación", "Fondo de cooperación", "Cooperación técnica",
         "Préstamo sindicado", "Préstamo", "Bono", "Facilidad")

PAIS_ALIAS = {
    "antigua y barbuda": "Antigua y Barbuda", "salvador": "El Salvador", "el salvador": "El Salvador",
    "república dominicana": "República Dominicana", "operaciones multinacionales": "Multinacional",
    "otros aliados internacionales": "Multinacional", "trinidad y tobago": "Trinidad y Tobago",
}
CAMPOS = ["anio", "pais", "tipo", "programa", "cliente", "monto_musd", "titulo_crudo", "numero",
          "fuente_url", "pagina"]


def urls_de_informes() -> dict[int, str]:
    archivo = sorted(REFERENCIA.glob("caf_aprobaciones_informes_*.csv"))[-1]
    with open(archivo, encoding="utf-8") as f:
        return {int(r["anio"]): r["fuente_url"] for r in csv.DictReader(f)}


def asegurar_pdf(anio: int, carpeta: Path, urls: dict[int, str]) -> Path:
    ruta = carpeta / f"i{anio}.pdf"
    if not ruta.exists():
        carpeta.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(urls[anio], headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as r, open(ruta, "wb") as f:
            f.write(r.read())
    return ruta


def parsear_monto(texto: str) -> float | None:
    """'50' -> 50, '2.93' -> 2,93, '1.889' -> 1889 (grupo de tres cifras tras el punto = miles)."""
    m = re.search(r"USD\s*([\d.,]+)", texto)
    if not m:
        return None
    n = m.group(1).rstrip(".,")
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", n):
        return float(re.sub(r"[.,]", "", n))
    return float(n.replace(",", "."))


def _abre_linea(marca: dict, texto8: list[dict]) -> bool:
    """Un número es el inicio de una ficha solo si no hay texto pegado a su izquierda en la misma línea.

    Descarta los números dentro de una frase ("DFCD 13. ...") que, si no, abren una columna falsa.
    """
    return not any(abs(w["top"] - marca["top"]) <= TOLERANCIA_LINEA and marca["x0"] - 8 < w["x1"] and w["x0"] < marca["x0"] - 1
                   for w in texto8)


def paises_de_la_pagina(palabras: list[dict], ancho: float) -> list[tuple[float, str]]:
    """Encabezados de país de la página como (mitad, nombre); la mitad separa páginas enfrentadas."""
    grandes = [w for w in palabras if w["size"] >= TAMANO_TITULO]
    if not grandes:
        return []
    salida = []
    for mitad, sel in ((0, [w for w in grandes if w["x0"] < ancho / 2]),
                       (1, [w for w in grandes if w["x0"] >= ancho / 2])):
        if sel:
            sel.sort(key=lambda w: (round(w["top"] / 10), w["x0"]))
            nombre = " ".join(w["text"] for w in sel).title().replace(" De ", " de ").replace(" Y ", " y ")
            nombre = PAIS_ALIAS.get(nombre.lower(), nombre)
            salida.append((mitad, nombre))
    return salida


def columnas(marcadores: list[dict], ancho_pagina: float) -> list[tuple[float, float]]:
    xs = sorted({round(m["x0"]) for m in marcadores})
    grupos: list[float] = []
    for x in xs:
        if not grupos or x - grupos[-1] > 8:
            grupos.append(x)
    huecos = [b - a for a, b in zip(grupos, grupos[1:])]
    ancho = min(huecos) if huecos else ANCHO_COLUMNA
    return [(g - 4, grupos[i + 1] - 4 if i + 1 < len(grupos) else min(g + max(ancho, ANCHO_COLUMNA), ancho_pagina))
            for i, g in enumerate(grupos)]


def texto_de(palabras: list[dict]) -> str:
    palabras = sorted(palabras, key=lambda w: (w["top"], w["x0"]))
    lineas: list[list[dict]] = []
    for w in palabras:
        if lineas and abs(lineas[-1][0]["top"] - w["top"]) <= TOLERANCIA_LINEA:
            lineas[-1].append(w)
        else:
            lineas.append([w])
    return " ".join(w["text"] for l in lineas for w in sorted(l, key=lambda w: w["x0"]))


def tipo_y_programa(titulo: str) -> tuple[str, str]:
    for t in sorted(TIPOS, key=len, reverse=True):
        if titulo.lower().startswith(t.lower()):
            return t, titulo[len(t):].strip(" -:")
    return "", titulo


def extraer_pagina(pagina, numero_pagina: int, anio: int, url: str, pais_previo: str | None):
    palabras = pagina.extract_words(extra_attrs=["size"])
    texto8 = [w for w in palabras if abs(w["size"] - TAMANO_TEXTO) < 0.3]
    marcadores = [w for w in texto8 if re.fullmatch(r"\d{1,2}\.", w["text"]) and _abre_linea(w, texto8)]
    paises = paises_de_la_pagina(palabras, pagina.width)
    pais_actual = paises[-1][1] if paises else pais_previo
    if not marcadores:
        return [], pais_actual
    cols = columnas(marcadores, pagina.width)
    filas = []
    for x_ini, x_fin in cols:
        mias = sorted((m for m in marcadores if x_ini <= m["x0"] < x_fin), key=lambda m: m["top"])
        palabras_col = [w for w in texto8 if x_ini <= w["x0"] < x_fin]
        for k, m in enumerate(mias):
            fin = mias[k + 1]["top"] - 1 if k + 1 < len(mias) else pagina.height
            bloque = [w for w in palabras_col if m["top"] - 1 <= w["top"] < fin]
            texto = texto_de(bloque)
            monto = re.search(r"Monto:\s*USD\s*[\d.,]+\s*(millones|mil\b)?", texto)
            if not monto:
                continue
            # Lo que sigue al monto en el bloque es texto ajeno a la ficha (pie, nota).
            texto = texto[:monto.end()]
            valor = parsear_monto(monto.group(0))
            if monto.group(1) == "mil" and valor is not None:
                valor = valor / 1000
            cabeza = re.sub(r"^\d{1,2}\.\s*", "", texto[:monto.start()])
            cliente_m = re.search(r"Cliente:\s*", cabeza)
            titulo = cabeza[:cliente_m.start()].strip() if cliente_m else cabeza.strip()
            cliente = cabeza[cliente_m.end():].strip() if cliente_m else ""
            tipo, programa = tipo_y_programa(titulo)
            # El país es el del encabezado de la mitad de la página donde está la columna.
            mitad = 0 if m["x0"] < pagina.width / 2 else 1
            pais = next((p for h, p in paises if h == mitad), None) or pais_actual
            filas.append({"anio": anio, "pais": pais, "tipo": tipo, "programa": programa, "cliente": cliente,
                          "monto_musd": valor, "titulo_crudo": titulo, "numero": m["text"].rstrip("."),
                          "fuente_url": url, "pagina": numero_pagina})
    return filas, pais_actual


def extraer(carpeta_pdf: Path) -> list[dict]:
    urls = urls_de_informes()
    todas = []
    for anio, rango in PAGINAS.items():
        ruta = asegurar_pdf(anio, carpeta_pdf, urls)
        pais = None
        with pdfplumber.open(ruta) as pdf:
            for p in rango:
                filas, pais = extraer_pagina(pdf.pages[p - 1], p, anio, urls[anio], pais)
                todas.extend(filas)
    return todas


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdfs", type=Path, default=PDFS)
    ap.add_argument("--salida", type=Path, default=SALIDA)
    args = ap.parse_args()
    filas = extraer(args.pdfs)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    with open(args.salida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(filas)
    with open(sorted(REFERENCIA.glob("caf_aprobaciones_informes_*.csv"))[-1], encoding="utf-8") as f:
        totales = {int(r["anio"]): float(r["total_aprobado_musd"]) for r in csv.DictReader(f)}
    for anio in PAGINAS:
        suma = sum(r["monto_musd"] for r in filas if r["anio"] == anio)
        n = sum(1 for r in filas if r["anio"] == anio)
        print(f"{anio}: {n} operaciones, suma {suma:,.1f} contra informe {totales[anio]:,.0f} ({suma / totales[anio]:.1%})")
    print(f"escrito {args.salida} ({len(filas)} filas)", file=sys.stderr)


if __name__ == "__main__":
    main()
