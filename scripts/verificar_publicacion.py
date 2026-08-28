# -*- coding: utf-8 -*-
"""
Control previo a publicar: falla si el repositorio contiene informacion que no
corresponde hacer publica.

Como se usa:
  uv run python scripts/verificar_publicacion.py

Existe porque un repositorio publico conserva en su historial todo lo que alguna vez se
subio, aunque despues se borre. Este control se corre antes de cada publicacion.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
EXTENSIONES = {".md", ".py", ".toml", ".json", ".txt", ".yml", ".yaml"}
EXCLUIR_DIR = {".git", ".venv", "__pycache__", ".pytest_cache"}

# Cada patron con el motivo por el que no puede publicarse. Se buscan en contexto para
# evitar falsos positivos con fechas, tamanos de archivo y conteos de operaciones.
PROHIBIDO = [
    (r"(?i)\bDNI\b[\s:]*\d{7,8}", "documento de identidad"),
    (r"(?i)\blegajo\b[\s:]*[A-Z]*-?\d+", "numero de legajo"),
    (r"\+54\s?9?\s?11[\s\d-]{6,}", "telefono"),
    (r"[a-zA-Z0-9._%+-]+@estudiantes\.[a-zA-Z0-9.-]+", "correo personal de estudiante"),
    (r"(?i)rúbrica de evaluaci|nota sugerida|informe final \(anexo|plan de trabajo \(anexo",
     "material academico del estudiante"),
]

# Archivos de datos que no deben versionarse.
DATOS = {".xlsx", ".xls", ".csv", ".xml", ".js"}


def revisar() -> list[str]:
    problemas: list[str] = []

    for ruta in RAIZ.rglob("*"):
        if any(p in EXCLUIR_DIR for p in ruta.parts) or not ruta.is_file():
            continue
        if ruta.name == Path(__file__).name:
            continue

        if ruta.suffix in DATOS and "data" in ruta.parts:
            problemas.append(f"{ruta.relative_to(RAIZ)}: archivo de datos, no debe versionarse")
            continue

        if ruta.suffix not in EXTENSIONES:
            continue

        texto = ruta.read_text(encoding="utf-8", errors="replace")
        for patron, motivo in PROHIBIDO:
            for m in re.finditer(patron, texto):
                linea = texto[: m.start()].count("\n") + 1
                problemas.append(
                    f"{ruta.relative_to(RAIZ)}:{linea}: {motivo} ({m.group()[:40]!r})"
                )
    return problemas


def main() -> int:
    problemas = revisar()
    if not problemas:
        print("Sin hallazgos. El repositorio puede publicarse.")
        return 0
    print(f"{len(problemas)} hallazgo(s) que impiden publicar:\n")
    for p in problemas:
        print(f"  {p}")
    print("\nRevisar cada caso antes de publicar. Recordar que el historial de git conserva")
    print("todo lo que se subio alguna vez, aunque despues se elimine.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
