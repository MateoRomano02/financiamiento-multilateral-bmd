"""Genera un explorador del corpus en un solo archivo HTML, con los datos adentro.

Es el borrador más simple posible de un tablero: no
necesita servidor ni internet, se abre con doble clic y se puede mandar como archivo o subir a
cualquier hosting estático. Permite filtrar por grupo, institución, ventanilla, años, país y texto,
y muestra un mapa del monto por país (con reproducción año por año), la evolución por grupo, la
composición por institución y sector, las tablas de comparación y las operaciones con su enlace, que
quedan en una pestaña aparte y de a 50. Las librerías de gráficos (d3, topojson, world-atlas) se bajan
de cdn.jsdelivr.net al abrir la página.

Uso:
    uv run python scripts/explorador_corpus.py
"""

from __future__ import annotations

import json
import random
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analisis_preliminar as ap  # noqa: E402  mismas reglas que el informe
from src.common.colores import COLORES_GRUPO  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
CORPUS = RAIZ / "data" / "processed" / "corpus_2014_2025.csv"
SALIDA = RAIZ / "data" / "processed" / "explorador" / "explorador-corpus.html"
# Version publicada: la misma pagina sin los datos adentro, que se leen aparte despues de ingresar.
SALIDA_WEB = RAIZ / "data" / "processed" / "explorador" / "publicado" / "index.html"
# La versión publicada solo se arma si existe la carpeta web/; sin ella se genera solo el archivo
# local, que se abre con doble clic.
WEB = RAIZ / "web"
PUBLICABLE = (WEB / "cargador.js").exists()
INGRESO = (WEB / "ingreso.html").read_text(encoding="utf-8") if PUBLICABLE else ""
CARGADOR = (WEB / "cargador.js").read_text(encoding="utf-8") if PUBLICABLE else ""

COLUMNAS = ["banco_grupo", "institucion", "tipo_ventanilla", "nombre", "pais", "anio_aprobacion",
            "estado", "monto_aprobado_usd", "monto_desembolsado_usd", "sector", "url_proyecto",
            "monto_constante_usd", "region", "forma_financiamiento", "moneda_original", "monto_original",
            "descripcion", "iso3", "zona"]
# Una ficha por grupo bancario, en lenguaje para cualquier lector: es lo que convierte el
# explorador en un tablero por grupo.
FICHAS = {
    "GBM": "Grupo Banco Mundial. El BIRF presta a Estados de ingreso medio, la IDA a Estados de ingreso bajo "
           "(créditos y donaciones), la IFC a empresas y MIGA da garantías de inversión. Los montos son el "
           "aporte del banco, sin los fondos de donantes que administra. Publica desembolsos del BIRF y la "
           "IDA. Su año fiscal cierra en junio.",
    "GBID": "Grupo BID. El BID presta a Estados de América Latina y el Caribe, BID Invest a empresas y BID "
            "Lab financia innovación y cooperación técnica. No publica desembolsos.",
    "CAF": "CAF, Banco de Desarrollo de América Latina y el Caribe. Presta a Estados y a empresas sin "
           "separar ventanillas; se clasificó por el prestatario. Las operaciones salen de sus informes anuales: "
           "2014-2022 de la base que el equipo reconstruyó en 2022 y 2023-2025 de los listados de cada "
           "informe. El riesgo soberano viene de la base heredada "
           "(2014-2022) y se infiere del cliente (2023-2025). Lo no soberano da 40% del monto, cerca del "
           "48% que declaran los informes.",
    "NDB": "Nuevo Banco de Desarrollo de los BRICS, opera desde 2016. Declara la ventanilla de cada "
           "operación y presta en monedas locales, convertidas a dólares con el promedio del año. Los "
           "montos se completaron con el anexo de su informe 2025. No publica forma de financiamiento ni "
           "desembolsos.",
    "AIIB": "Banco Asiático de Inversión en Infraestructura, opera desde 2016. Declara la ventanilla de "
            "cada operación. Proyectos grandes y muy concentrados por país. No publica forma de "
            "financiamiento ni desembolsos.",
    "FONPLATA": "FONPLATA, banco de los cinco países de la Cuenca del Plata. Publica desembolsos de casi todas "
                "sus operaciones; no separa ventanillas y en una de cada tres falta el prestatario.",
    "BCIE": "Banco Centroamericano de Integración Económica. Publica desembolsos de tres de cada cuatro "
            "operaciones; declara cuando el prestatario es privado.",
}

# La descripción se recorta para que la página siga siendo liviana; la entera está en el corpus.
LARGO_DESCRIPCION = 300

# A: America Latina y el Caribe (con sus agregados), R: resto del mundo, G: agregado sin pais.
REGION = {"ALC": "A", "ALC (agregado regional)": "A", "resto del mundo": "R", "otro agregado regional": "G"}

# Sede de cada grupo, de donde salen los arcos del globo: ciudad, latitud, longitud.
SEDES = {
    "GBM": ("Washington", 38.90, -77.04), "GBID": ("Washington", 38.90, -77.04),
    "CAF": ("Caracas", 10.49, -66.88), "NDB": ("Shanghái", 31.23, 121.47),
    "AIIB": ("Pekín", 39.90, 116.40), "FONPLATA": ("Santa Cruz de la Sierra", -17.78, -63.18),
    "BCIE": ("Tegucigalpa", 14.07, -87.20),
}
# Centroides (latitud, longitud) de los países que el mapa de 110 m no dibuja: islas y ciudades-Estado.
# El globo los muestra como puntos y apunta ahí los arcos.
CENTROIDES_EXTRA = {
    "BRB": (13.19, -59.54), "CPV": (16.0, -24.0), "STP": (0.19, 6.61), "COM": (-11.65, 43.33),
    "TON": (-21.18, -175.2), "MDV": (3.2, 73.22), "KIR": (1.45, 173.0), "WSM": (-13.76, -172.1),
    "TUV": (-8.52, 179.2), "MHL": (7.1, 171.38), "FSM": (6.92, 158.16), "SYC": (-4.68, 55.49),
    "DMA": (15.41, -61.37), "SGP": (1.35, 103.82), "LCA": (13.91, -60.98), "GRD": (12.12, -61.68),
    "VCT": (13.25, -61.2), "MUS": (-20.35, 57.55), "HKG": (22.3, 114.17), "ATG": (17.06, -61.8),
    "COK": (-21.24, -159.78), "KNA": (17.36, -62.78),
}
MEMBRECIA = RAIZ / "data" / "raw" / "referencia"


def membrecia_por_anio(anios: list[int]) -> dict[str, dict[str, int]]:
    """Miembros plenos de cada institución al 31 de diciembre de cada año, de la serie más reciente.

    Una fecha vacía es un ingreso anterior al período (cuenta en todos los años) y una fecha de solo
    año cuenta desde ese año. Los prospectivos no cuentan. Si la tabla no está (por ejemplo en el
    repositorio público, que no lleva datos), devuelve {}.
    """
    archivos = sorted(MEMBRECIA.glob("membrecia_*.csv"))
    if not archivos:
        return {}
    m = pd.read_csv(archivos[-1], dtype=str)
    m = m[m["tipo"] == "pleno"].copy()
    m["ingreso"] = pd.to_datetime(m["fecha_ingreso"], format="mixed", errors="coerce").fillna(pd.Timestamp.min)
    return {inst: {str(a): int((g["ingreso"] <= pd.Timestamp(f"{a}-12-31")).sum()) for a in anios}
            for inst, g in m.groupby("institucion")}


# Tabla de países para el mapa: ISO3, código numérico ISO 3166-1 (el que usa world-atlas), zona y los
# nombres con que los publican los bancos. Una línea por país; las variantes de nombre van separadas
# por "|". Kosovo no tiene código numérico y se une por nombre. La zona sigue las regiones del Banco
# Mundial: LAC América Latina y el Caribe, ECA Europa y Asia Central, EAP Asia oriental y Pacífico,
# SAS Asia meridional, MNA Medio Oriente y Norte de África, SSA África subsahariana. Lo que no está
# acá (agregados como "Regional" o "Pacific 1") no tiene país único y va al aviso "sin país".
ZONAS = {"LAC": "América Latina y el Caribe", "ECA": "Europa y Asia Central",
         "EAP": "Asia oriental y Pacífico", "SAS": "Asia meridional",
         "MNA": "Medio Oriente y Norte de África", "SSA": "África subsahariana"}
TABLA_PAISES = """
BRA 076 LAC Brazil
IND 356 SAS India
ARG 032 LAC Argentina
COL 170 LAC Colombia
MEX 484 LAC Mexico
PER 604 LAC Peru
TUR 792 ECA Turkiye|Türkiye
CHN 156 EAP China
UKR 804 ECA Ukraine
ECU 218 LAC Ecuador
BGD 050 SAS Bangladesh
IDN 360 EAP Indonesia
PAK 586 SAS Pakistan
NGA 566 SSA Nigeria
ETH 231 SSA Ethiopia
PHL 608 EAP Philippines
CHL 152 LAC Chile
ZAF 710 SSA South Africa
URY 858 LAC Uruguay
EGY 818 MNA Egypt, Arab Republic of|Egypt
PAN 591 LAC Panama
KEN 404 SSA Kenya
PRY 600 LAC Paraguay
UZB 860 ECA Uzbekistan
MAR 504 MNA Morocco
BOL 068 LAC Bolivia
DOM 214 LAC Dominican Republic
TZA 834 SSA Tanzania
CRI 188 LAC Costa Rica
SLV 222 LAC El Salvador
VNM 704 EAP Viet Nam
COD 180 SSA Congo, Democratic Republic of
JOR 400 MNA Jordan
ROU 642 ECA Romania
HND 340 LAC Honduras
CIV 384 SSA Cote d'Ivoire|Cote D'Ivoire|Côte d'Ivoire
MOZ 508 SSA Mozambique
SRB 688 ECA Serbia
AGO 024 SSA Angola
SEN 686 SSA Senegal
KAZ 398 ECA Kazakhstan
GTM 320 LAC Guatemala
GHA 288 SSA Ghana
NPL 524 SAS Nepal
TUN 788 MNA Tunisia
UGA 800 SSA Uganda
IRQ 368 MNA Iraq
YEM 887 MNA Yemen, Republic of
RWA 646 SSA Rwanda
MDG 450 SSA Madagascar
LKA 144 SAS Sri Lanka
CMR 120 SSA Cameroon
NIC 558 LAC Nicaragua
NER 562 SSA Niger
BFA 854 SSA Burkina Faso
ZMB 894 SSA Zambia
KHM 116 EAP Cambodia
BEN 204 SSA Benin
MWI 454 SSA Malawi
MMR 104 EAP Myanmar
POL 616 ECA Poland
HTI 332 LAC Haiti
RUS 643 ECA Russia|Russian Federation
MNG 496 EAP Mongolia
LBN 422 MNA Lebanon
GEO 268 ECA Georgia
SOM 706 SSA Somalia, Federal Republic of
THA 764 EAP Thailand
TTO 780 LAC Trinidad and Tobago
AFG 004 SAS Afghanistan
AZE 031 ECA Azerbaijan
JAM 388 LAC Jamaica
MLI 466 SSA Mali
GIN 324 SSA Guinea
TJK 762 ECA Tajikistan
HRV 191 ECA Croatia
OMN 512 MNA Oman
TCD 148 SSA Chad
BHS 044 LAC Bahamas|Bahamas, The
VEN 862 LAC Venezuela|Venezuela, RB
ALB 008 ECA Albania
BDI 108 SSA Burundi
BIH 070 ECA Bosnia and Herzegovina
TGO 768 SSA Togo
SDN 729 SSA Sudan
ESP 724 ECA Spain
KGZ 417 ECA Kyrgyz Republic|Kyrgyzstan
ARM 051 ECA Armenia
SSD 728 SSA South Sudan
SLE 694 SSA Sierra Leone
CAF 140 SSA Central African Republic
BLR 112 ECA Belarus
MRT 478 SSA Mauritania
MDA 498 ECA Moldova
LBR 430 SSA Liberia
SUR 740 LAC Suriname
GAB 266 SSA Gabon
COG 178 SSA Congo, Republic of
LAO 418 EAP Lao People's Democratic Republic|Lao PDR
SGP 702 EAP Singapore
PNG 598 EAP Papua New Guinea
MKD 807 ECA North Macedonia
XKX Kosovo ECA Kosovo
GRC 300 ECA Greece
HUN 348 ECA Hungary
GMB 270 SSA Gambia, The
BWA 072 SSA Botswana
FJI 242 EAP Fiji
BTN 064 SAS Bhutan
DJI 262 MNA Djibouti
CPV 132 SSA Cabo Verde
MUS 480 SSA Mauritius
BGR 100 ECA Bulgaria
MYS 458 EAP Malaysia
LSO 426 SSA Lesotho
SLB 090 EAP Solomon Islands
SWZ 748 SSA Eswatini
COM 174 SSA Comoros
MDV 462 SAS Maldives
FSM 583 EAP Micronesia, Federated States of
DMA 212 LAC Dominica
TON 776 EAP Tonga
GNB 624 SSA Guinea-Bissau
MHL 584 EAP Marshall Islands
WSM 882 EAP Samoa
MNE 499 ECA Montenegro
SAU 682 MNA Saudi Arabia
VUT 548 EAP Vanuatu
KIR 296 EAP Kiribati
STP 678 SSA Sao Tome and Principe
TUV 798 EAP Tuvalu
PRT 620 ECA Portugal
VCT 670 LAC St. Vincent and the Grenadines
HKG 344 EAP Hong Kong, China|Hong Kong SAR, China
TLS 626 EAP Timor-Leste
SYC 690 SSA Seychelles
LCA 662 LAC St. Lucia
IRL 372 ECA Ireland
GRD 308 LAC Grenada
PSE 275 MNA West Bank and Gaza
NAM 516 SSA Namibia
DZA 012 MNA Algeria
NLD 528 ECA Netherlands
SYR 760 MNA Syrian Arab Republic
IRN 364 MNA Iran, Islamic Republic of
ZWE 716 SSA Zimbabwe
ATG 028 LAC Antigua and Barbuda
CUB 192 LAC Cuba
ARE 784 MNA United Arab Emirates
FRA 250 ECA France
COK 184 EAP Cook Islands
TKM 795 ECA Turkmenistan
ISR 376 MNA Israel
BRB 052 LAC Barbados
GUY 328 LAC Guyana
BLZ 084 LAC Belize
KNA 659 LAC St. Kitts and Nevis
LBY 434 MNA Libya
ERI 232 SSA Eritrea
GNQ 226 SSA Equatorial Guinea
"""


def _leer_tabla() -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    nombre_a_iso: dict[str, str] = {}
    geo: dict[str, dict[str, str]] = {}
    for linea in TABLA_PAISES.strip().splitlines():
        iso, num, zona, nombres = linea.split(" ", 3)
        variantes = nombres.split("|")
        geo[iso] = {"n": num, "z": zona, "nombre": variantes[0]}
        for v in variantes:
            nombre_a_iso[v] = iso
    return nombre_a_iso, geo


NOMBRE_A_ISO, GEO = _leer_tabla()


def iso_de(pais: object) -> str | None:
    """ISO3 del receptor, o None si es un agregado regional o un nombre sin país único."""
    return NOMBRE_A_ISO.get(str(pais or "").strip())


# Orden único de los grupos: numera los colores (--g1 a --g7) y ordena botones, filtro, leyendas y tablas.
ORDEN_GRUPOS = ("GBM", "GBID", "CAF", "BCIE", "FONPLATA", "AIIB", "NDB")
CSS_COLORES_GRUPO = "".join(f"--g{k + 1}:{COLORES_GRUPO[g]};" for k, g in enumerate(ORDEN_GRUPOS))

# Ilustración del encabezado, grabado en línea: tres cordones de la cordillera, sombreados del lado
# opuesto al sol, y un Sol de Mayo. Las crestas se quiebran con una semilla fija: la imagen no cambia.
CORDONES = (  # (cumbres x, y), tinta, fondo; de atrás hacia adelante
    (((520, 200), (700, 120), (780, 140), (880, 46), (960, 104), (1040, 84), (1130, 28), (1216, 70)), .45, "#eaf2fa"),
    (((600, 200), (720, 150), (820, 112), (900, 140), (990, 92), (1080, 132), (1170, 100), (1216, 118)), .7, "#f2f7fc"),
    (((380, 205), (560, 186), (700, 176), (840, 168), (980, 150), (1100, 166), (1216, 150)), .9, "#fbfdfe"),
)


def _quebrar(rng: random.Random, cumbres) -> list[tuple[float, float]]:
    pts = list(cumbres)
    for vuelta in range(4):
        nuevos = [pts[0]]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            d = (x1 - x0) * .18 / (vuelta + 1)
            nuevos += [((x0 + x1) / 2, (y0 + y1) / 2 + rng.uniform(-d, d)), (x1, y1)]
        pts = nuevos
    return pts


def _ilustracion() -> str:
    rng = random.Random(34)
    capas = []
    for cumbres, tinta, fondo in CORDONES:
        p = _quebrar(rng, cumbres)
        cresta = "M" + "L".join(f"{x:.0f} {y:.1f}" for x, y in p)
        # Sombreado: cada 3,5 px de las laderas que bajan hacia la derecha, un trazo que sigue la caída y
        # se acorta hacia el valle, como un grabado.
        trazos = []
        for (x0, y0), (x1, y1) in zip(p, p[1:]):
            for x in range(int(x0), int(x1)):
                y = y0 + (y1 - y0) * (x - x0) / (x1 - x0)
                if y1 > y0 and x % 4 == 0:
                    largo = min(60, 200 - y) * .45 + 3
                    trazos.append(f"M{x} {y:.1f}l{-.35 * largo:.1f} {largo:.1f}")
        sombra = "".join(trazos)
        capas.append(f'<path d="{cresta}V240H{p[0][0]:.0f}Z" fill="{fondo}"/><g stroke-opacity="{tinta}">'
                     f'<path d="{sombra}" stroke-width=".55"/><path d="{cresta}" stroke-width="1.2"/></g>')
    rayos = "".join(f'<path d="{"M-2.2-21L0-42L2.2-21" if k % 2 else "M0-21c3-4-3-8 0-12s3-6 0-9"}" '
                    f'transform="rotate({k * 11.25})"/>' for k in range(32))
    sol = f'<g class="sol" transform="translate(985 62)" stroke="#d9a21b"><circle r="18" fill="#fbe9b0"/><circle r="11"/>{rayos}</g>'
    return (f'<svg viewBox="0 0 1216 200" preserveAspectRatio="xMaxYMax slice" aria-hidden="true">'
            f'<g fill="none" stroke="#1d3f72" stroke-linejoin="round" stroke-linecap="round">{sol}{"".join(capas)}</g></svg>')


ILUSTRACION = _ilustracion()

PAGINA = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Explorador del corpus</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,500;6..72,600&display=swap">
<script src="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js" integrity="sha384-CjloA8y00+1SDAUkjs099PVfnY2KmDC2BZnws9kh8D/lX1s46w6EPhpXdqMfjK6i" crossorigin="anonymous"></script>
<script src="https://cdn.jsdelivr.net/npm/topojson-client@3.1.0/dist/topojson-client.min.js" integrity="sha384-Ukv1p/xTma6P4/2bY5KzWBw+ydSpXmhCMtyciIQVDJ1RmOxtCYNMF1uXT9T63H67" crossorigin="anonymous"></script>
<style>
:root{color-scheme:light;--t:#1d1d1b;--s:#5f5e5a;--m:#8b8982;--l:#e6e4de;--l2:#d2cfc7;--b:#fff;--panel:#f8f7f4;--a:#2a78d6;
--seq0:#cfe2f8;--seq1:#0b3a80;--nodata:#eceae5;--sel:#111;
__COLORES_GRUPO__--gx:#8a8984;
--f1:#4a3aa7;--f2:#008300;--f3:#e87ba4;--f4:#eda100;--f5:#e34948;--f6:#9a9892;
--sky0:#cfe3f6;--sky1:#f6faff;--ink:#1d3f72;--sol:#d9a21b;--serif:Newsreader,Georgia,"Times New Roman",serif;
--ease:cubic-bezier(.2,.7,.2,1)}
*{box-sizing:border-box}
html{scrollbar-gutter:stable;scroll-padding-top:150px;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
body{position:relative;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Helvetica,Arial,sans-serif;font-size:14px;color:var(--t);background:var(--b);margin:0 auto;max-width:1280px;padding:28px 32px 64px;line-height:1.5;font-feature-settings:"tnum" 1,"lnum" 1}
html.tr-lock{overflow:hidden}
h1,h2{font-family:var(--serif);font-weight:600}
h1{font-size:36px;letter-spacing:-.015em;margin:12px 0 8px;line-height:1.15}
h2{font-size:22px;letter-spacing:-.01em;margin:32px 0 6px}
h3{font-size:11px;font-weight:650;letter-spacing:.07em;text-transform:uppercase;color:var(--s);margin:20px 0 8px}
.nota{color:var(--s);font-size:12.5px;line-height:1.5}
p{margin:6px 0}
section{animation:entra .38s var(--ease)}
@keyframes entra{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){section,#hero{animation:none}*{transition:none!important}}
label{font-size:11px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:var(--s);display:block;margin-bottom:3px}
select,input,textarea{width:100%;padding:6px 8px;border:1px solid var(--l2);border-radius:3px;font:inherit;font-size:13px;background:var(--b);color:var(--t);transition:border-color .15s,box-shadow .15s}
select:hover,input:hover{border-color:var(--m)}select:focus,input:focus,textarea:focus{outline:0;border-color:var(--a);box-shadow:0 0 0 3px rgba(42,120,214,.16)}
input[type=range]{padding:0;border:0;accent-color:var(--a);box-shadow:none}input[type=radio],input[type=checkbox]{width:auto;accent-color:var(--a)}
button,.btn{padding:6px 12px;border:1px solid var(--l2);background:var(--b);color:var(--t);border-radius:3px;cursor:pointer;font:inherit;font-size:13px;text-decoration:none;display:inline-flex;align-items:center;gap:6px;transition:background .15s,border-color .15s,color .15s}
button:hover,.btn:hover{border-color:var(--t);background:var(--panel)}
a{color:var(--a)}
.fecha{display:inline-block;margin:0;padding:3px 10px;border:1px solid rgba(29,63,114,.2);border-radius:99px;font-size:12px;color:var(--s);background:rgba(255,255,255,.7)}
#hero{position:relative;overflow:hidden;border-radius:14px;padding:22px 28px 30px;min-height:200px;background:linear-gradient(180deg,var(--sky0),var(--sky1));animation:entra .5s var(--ease)}
#hero>svg{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
#hero .texto{position:relative;max-width:620px}
.marca{display:flex;align-items:center;gap:12px;margin:0;color:var(--ink);font-size:12px;line-height:1.35}.marca b{display:flex;align-items:center;gap:9px;font:600 21px/1 Helvetica,Arial,sans-serif;letter-spacing:.07em;color:#111;padding-right:12px;border-right:1px solid rgba(29,63,114,.3)}.marca b svg{width:30px;height:27px}

.prosa{max-width:720px}.prosa h3{margin-top:24px}.prosa p{font-size:14.5px;line-height:1.6}.cita{border-left:2px solid var(--l2);padding-left:14px;color:var(--s)}
.guia{border:1px solid var(--l);border-radius:4px;padding:10px 18px;margin:10px 0;background:var(--panel)}.guia summary{font-size:14px;cursor:pointer}
.guia p,.guia dd{margin:6px 0;font-size:13.5px}.guia dt{font-weight:650;font-size:13.5px;margin-top:10px}.guia dd{margin-left:0;color:var(--s)}
.guia .aviso{border-left:2px solid var(--t);padding-left:12px}
.tableros{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:16px 0 8px}.tableros .nota{margin-right:4px;text-transform:uppercase;letter-spacing:.07em;font-size:11px;font-weight:650}
.tableros button{border-radius:99px;padding:5px 12px}.tableros button.on{background:var(--t);border-color:var(--t);color:var(--b)}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block}
kbd{font:600 11px/1 system-ui,sans-serif;border:1px solid var(--l2);border-bottom-width:2px;border-radius:3px;padding:2px 5px;background:var(--b)}
.slider{position:relative;display:inline-block;width:min(360px,100%);padding-bottom:48px}.slider input{width:100%;display:block}
.hitos{position:absolute;left:0;right:0;top:22px;height:0}.hitos i{position:absolute;font-style:normal;transform:translateX(-50%);font-size:10.5px;line-height:12px;color:var(--s);white-space:nowrap;cursor:default}
.hitos u{position:absolute;left:50%;top:-6px;height:5px;width:1px;background:var(--m)}
#p-mapa[data-vista=plano] .solo-globo,#p-mapa[data-vista=globo] .solo-plano{display:none}
.vista{display:inline-flex;align-items:center;gap:8px}.vista button{padding:5px 14px}.vista button:first-of-type{border-radius:99px 0 0 99px;margin-right:-9px}.vista button:last-of-type{border-radius:0 99px 99px 0}.vista button.on{background:var(--t);border-color:var(--t);color:var(--b)}
.mapa-ctrl .grupo{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center}
#g-caja{position:relative}#globo{position:relative;height:560px;width:100%}
#g-estado{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);text-align:center;padding:12px;max-width:80%}
.float-tooltip-kap{background:none!important;padding:0!important}
.tt{background:#fff;color:var(--t);border:1px solid var(--l2);border-radius:4px;padding:8px 11px;font-size:12.5px;line-height:1.4;max-width:260px;box-shadow:0 6px 20px rgba(0,0,0,.14);text-align:left}.tt b{display:block;font-size:13px;margin-bottom:2px}.tt .n{font-weight:650;font-size:15px}
.historias{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:10px 0}
.historias button{display:block;text-align:left;padding:8px 12px;border-radius:4px;background:var(--b);min-width:0}
.historias .etq{display:block;font-size:11px;letter-spacing:.07em;text-transform:uppercase;color:var(--s)}.historias .tit{display:block;font-size:16px;font-weight:650;line-height:1.25}.historias .det{display:block;font-size:12px;line-height:1.35;color:var(--s);margin-top:2px;white-space:normal}
#g-panel .pt{font-size:18px;font-weight:650;letter-spacing:-.01em}#g-panel .gran{font-size:26px;font-weight:650;letter-spacing:-.02em;margin:4px 0;line-height:1.2}#g-panel .op{margin:7px 0;font-size:13px;line-height:1.35}
#mb svg{display:block}#mb g{cursor:default}
.ficha{margin:8px 0;font-size:13.5px;line-height:1.55;background:var(--panel);border:1px solid var(--l);border-radius:4px;padding:12px 16px}
#barra{position:sticky;top:0;z-index:20;background:rgba(255,255,255,.96);backdrop-filter:blur(6px);margin:12px -32px 0;padding:10px 32px 8px;border-bottom:1px solid var(--l);box-shadow:0 6px 12px -10px rgba(0,0,0,.25)}
.filtros{display:grid;grid-template-columns:1.1fr 1.2fr .9fr .75fr .75fr 1fr 1fr .9fr 1.1fr;gap:8px}
.filtros>div,.kpis>div{min-width:0}
.fila-chips{display:flex;align-items:center;gap:10px;margin-top:8px;min-height:28px}.fila-chips .chips{flex:1}
.chips{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.chip{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--l2);background:var(--panel);border-radius:99px;padding:2px 4px 2px 10px;font-size:12.5px;animation:entra .25s var(--ease)}
.chip .nota{font-size:11px;text-transform:uppercase;letter-spacing:.05em}
.chip button{border:0;background:none;padding:0 7px;font-size:16px;line-height:18px;border-radius:99px;color:var(--s)}.chip button:hover{background:var(--l);color:var(--t)}
.kpis{display:flex;gap:28px;margin:8px 0 0;padding-top:6px;border-top:1px solid var(--l)}
.kpi{display:flex;align-items:baseline;gap:8px}
.kpi .nota{font-size:11px;text-transform:uppercase;letter-spacing:.06em}
.kpi b{font-size:18px;font-weight:650;letter-spacing:-.01em;font-variant-numeric:tabular-nums;line-height:1.3}
#tabs{display:flex;flex-wrap:wrap;gap:2px;margin:26px 0 0;border-bottom:1px solid var(--l)}
#tabs button{border:0;border-bottom:2px solid transparent;border-radius:0;padding:9px 16px;margin-bottom:-1px;color:var(--s);font-size:14px;background:none}
#tabs button:hover{color:var(--t);background:var(--panel)}#tabs button.on{color:var(--t);border-bottom-color:var(--t);font-weight:650;background:none}
.barras div{display:grid;grid-template-columns:150px 1fr 90px;gap:10px;align-items:center;font-size:13px;margin:3px 0}
.barras div>span:first-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.barras .pista{display:block;height:12px;background:var(--panel);border-radius:2px;overflow:hidden}
.barras .b{display:block;height:100%;background:var(--a);border-radius:2px;transition:width .65s var(--ease)}
.barras .n{text-align:right;font-variant-numeric:tabular-nums}
.barras.lado div{grid-template-columns:minmax(120px,1.7fr) 1fr 60px}.barras.lado div>span:first-child{white-space:normal;line-height:1.25}
.barras div[data-iso],.barras div[data-zona]{cursor:pointer;border-radius:3px;transition:background .15s}.barras div[data-iso]:hover,.barras div[data-zona]:hover{background:var(--panel)}
.barras div.sel>span:first-child{font-weight:700}.barras div.sel .b{background:var(--seq1)}
#tip{position:fixed;z-index:50;background:#fff;color:var(--t);font-size:12px;line-height:1.45;padding:8px 11px;border:1px solid var(--l2);border-radius:4px;box-shadow:0 6px 20px rgba(0,0,0,.14);pointer-events:none;display:none;max-width:320px;font-variant-numeric:tabular-nums}
#tip b{display:block;font-size:12.5px;margin-bottom:2px}#tip i{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:6px}
.leyenda{font-size:12px;color:var(--s);margin:10px 0 0;display:flex;flex-wrap:wrap;gap:4px 16px}
.leyenda span{display:inline-flex;align-items:center;cursor:default;padding:1px 4px;border-radius:3px}.leyenda i{width:10px;height:10px;margin-right:6px;border-radius:2px}
[data-grp]{transition:opacity .2s}.dim{opacity:.16!important}
table{width:100%;border-collapse:collapse;font-size:13px}th{font-size:11px;font-weight:650;letter-spacing:.05em;text-transform:uppercase;color:var(--s);border-bottom:1px solid var(--l2)}
th,td{border-bottom:1px solid var(--l);padding:6px 8px;text-align:left;vertical-align:top}tbody tr:hover td{background:var(--panel)}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.tabla{overflow-x:auto}th[data-o]{cursor:pointer}th[data-o]:hover{color:var(--t)}details summary{cursor:pointer;color:var(--s)}
.mapa-grid{display:grid;grid-template-columns:minmax(0,3fr) minmax(0,1.1fr);gap:28px;align-items:start}
.mapa-ctrl{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center;margin:10px 0}
.mapa-ctrl label{display:inline-flex;gap:6px;align-items:center;font-size:13px;text-transform:none;letter-spacing:0;font-weight:400;color:var(--t);margin:0}
#m-anio,#mb-anio{font-weight:650;font-size:22px;letter-spacing:-.01em;font-variant-numeric:tabular-nums;min-width:4.4em}
#mapa svg{display:block;width:100%;height:auto}
#mapa path[data-k]{stroke:#fff;stroke-width:.45;cursor:pointer}#mapa path[data-k]:hover{stroke:var(--sel);stroke-width:1.1}#mapa path.sel{stroke:var(--sel);stroke-width:1.8}
.grad{height:8px;border-radius:2px;margin-top:8px;max-width:340px}.grad-et{display:flex;justify-content:space-between;max-width:340px;font-size:11px;color:var(--s);margin-top:3px;font-variant-numeric:tabular-nums}
.nd{font-size:11px;color:var(--s);margin-top:6px;display:flex;align-items:center;gap:6px}.nd i{width:14px;height:8px;background:var(--nodata);border-radius:1px;display:inline-block}
.mini{display:grid;grid-template-columns:repeat(auto-fill,minmax(168px,1fr));gap:18px 20px}.mini>div{min-width:0}.mini svg{display:block;max-width:100%}.mini .nota b{color:var(--t)}
#tm{position:relative;margin-top:8px}
#tm div{position:absolute;overflow:hidden;font-size:11px;line-height:1.2;cursor:pointer;padding:3px 4px;transition:left .6s var(--ease),top .6s var(--ease),width .6s var(--ease),height .6s var(--ease),background-color .4s,opacity .4s}
#tm div.l{border-radius:2px}.heat td{text-align:right}.heat td:first-child{text-align:left}.heat td.v{font-variant-numeric:tabular-nums}
svg text{font-family:inherit;font-variant-numeric:tabular-nums}
.dos{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:16px}
.ref>summary{display:flex;align-items:baseline;gap:10px;cursor:pointer;list-style:none;color:var(--t)}.ref>summary::-webkit-details-marker{display:none}
.ref>summary::before{content:"\25B8";color:var(--s);font-size:14px}.ref[open]>summary::before{content:"\25BE"}
.ref>summary .ver{font-size:12px;color:var(--a)}.ref[open]>summary .ver{display:none}
.recorrido{position:absolute;top:18px;right:20px;z-index:1}
#p-sobre{max-width:880px}
.sobre-ir{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0 0}.sobre-ir button{border-radius:99px;padding:5px 14px}
.faq details{border-bottom:1px solid var(--l);padding:9px 0}.faq summary{font-weight:600;font-size:14.5px;color:var(--t)}
.faq details p{margin:6px 0 2px;color:var(--s);font-size:14px}
.ruta{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px;margin-top:12px}
.ruta>div{border-top:2px solid var(--ink);padding-top:8px}.ruta>div:nth-child(2){border-color:var(--sol)}.ruta>div:nth-child(3){border-color:var(--l2)}
.ruta h3{margin:0 0 6px}.ruta ul{margin:0;padding-left:16px}.ruta li{font-size:13.5px;margin:5px 0;color:var(--s)}
.decisiones dt{font-weight:650;font-size:14px;margin-top:14px}.decisiones dd{margin:2px 0 0;color:var(--s);font-size:13.5px}
#tr-capa{position:fixed;inset:0;z-index:1100;display:none}#tr-capa.dim{background:rgba(29,29,27,.4)}
#tr-foco{position:fixed;z-index:1101;border-radius:6px;pointer-events:none;box-shadow:0 0 0 9999px rgba(29,29,27,.4),0 0 0 2px var(--a);opacity:0;transition:left .3s var(--ease),top .3s var(--ease),width .3s var(--ease),height .3s var(--ease),opacity .2s}
#tr-foco.v{opacity:1}
#tr-caja{position:fixed;z-index:1102;width:360px;max-width:calc(100vw - 28px);background:var(--b);border:1px solid var(--l2);border-radius:10px;box-shadow:0 14px 40px rgba(0,0,0,.24);padding:16px 18px;opacity:0;transform:translateY(6px);display:none;transition:opacity .2s var(--ease),transform .2s var(--ease),left .3s var(--ease),top .3s var(--ease)}
#tr-caja.v{opacity:1;transform:none}#tr-caja.modal{width:460px}
.tr-prog{display:flex;align-items:center;gap:10px;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--s);font-weight:650}
.tr-barra{flex:1;height:3px;background:var(--l);border-radius:2px;overflow:hidden}.tr-barra i{display:block;height:100%;background:var(--a);transition:width .3s var(--ease)}
.tr-t{font:600 19px/1.25 var(--serif);letter-spacing:-.01em;text-transform:none;color:var(--t);margin:10px 0 4px;line-height:1.25}#tr-caja [hidden]{display:none!important}#tr-caja p{margin:4px 0;font-size:13.5px}#tr-caja label{margin-top:12px}#tr-caja input[hidden]{display:none}#tr-caja textarea{resize:none}#tr-caja #tr-ins-otra{margin-top:6px}
.tr-pie{display:flex;align-items:center;gap:8px;margin-top:14px}.tr-sp{flex:1}
#tr-caja .tr-pri{background:var(--t);border-color:var(--t);color:var(--b)}#tr-caja .tr-pri:hover{background:#000}
#tr-caja button:disabled{opacity:.4;cursor:default}#tr-caja .tr-sec{border-color:transparent;color:var(--s)}#tr-caja .tr-sec:hover{color:var(--t);background:none}
.fb-flot{opacity:0;transition:opacity .18s var(--ease),transform .18s var(--ease)}.fb-flot.v{opacity:1}
#fb-btn{position:fixed;right:24px;bottom:24px;z-index:1000;padding:9px 16px 9px 13px;border-radius:99px;font-weight:600;gap:8px;box-shadow:0 6px 20px rgba(0,0,0,.14)}
#fb-btn svg{width:15px;height:15px;flex:none}
#fb-btn.on{background:var(--t);border-color:var(--t);color:var(--b)}
#fb-panel,#fb-burbuja{position:fixed;z-index:1001;background:var(--b);border:1px solid var(--l2);border-radius:8px;box-shadow:0 12px 36px rgba(0,0,0,.18);font-size:13px;padding:14px;overflow:auto;transform:translateY(6px)}
#fb-panel.v,#fb-burbuja.v{transform:none}
#fb-panel{right:24px;bottom:72px;width:340px;max-height:calc(100vh - 110px)}#fb-panel.ancho{width:440px}
#fb-burbuja{width:340px;max-height:min(72vh,580px,calc(100vh - 100px))}
#fb-aviso{position:fixed;top:14px;left:50%;margin-left:-170px;width:340px;text-align:center;z-index:1002;background:var(--t);color:var(--b);padding:8px 16px;border-radius:99px;font-size:13px;box-shadow:0 6px 20px rgba(0,0,0,.2)}
#fb-contorno{position:fixed;z-index:999;pointer-events:none;border:2px solid var(--a);border-radius:4px;background:rgba(42,120,214,.07);opacity:0;transition:left .12s var(--ease),top .12s var(--ease),width .12s var(--ease),height .12s var(--ease),opacity .12s}
#fb-contorno.v{opacity:1}
#fb-contorno span{position:absolute;left:-2px;bottom:100%;margin-bottom:2px;background:var(--a);color:#fff;font-size:11px;line-height:1.3;padding:2px 7px;border-radius:3px;white-space:nowrap}
#fb-contorno.dentro span{bottom:auto;top:2px;left:2px}
.fb-marca{position:fixed;z-index:999;pointer-events:none;min-width:20px;height:20px;border-radius:99px;background:var(--a);color:#fff;font-size:11px;font-weight:650;display:flex;align-items:center;justify-content:center;padding:0 6px;box-shadow:0 2px 6px rgba(0,0,0,.2)}
body.fb-on,body.fb-on *{cursor:crosshair}body.fb-on #fb-ui,body.fb-on #fb-ui *{cursor:auto}body.fb-on #fb-ui button,body.fb-on #fb-ui select{cursor:pointer}body.fb-on #tip{display:none!important}
.fb-h{font-size:14px;font-weight:650;margin:0}.fb-cab{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;margin-bottom:8px}
.fb-x{border:0;background:none;font-size:20px;line-height:1;padding:0 4px;color:var(--s)}.fb-x:hover{background:none;color:var(--t)}
.fb-menu{display:grid;gap:6px;margin-top:10px}.fb-menu button{justify-content:flex-start;padding:8px 12px}
.fb-c{border-top:1px solid var(--l);padding:8px 0}.fb-c .fb-t{margin:3px 0 0;white-space:pre-wrap;overflow-wrap:anywhere}.fb-pr{margin:6px 0 0;white-space:pre-wrap}
.fb-c b{white-space:nowrap}.fb-resp{margin-left:14px;padding-left:10px;border-left:2px solid var(--l)}
.fb-link{border:0;background:none;padding:2px 0;color:var(--a);font-size:12px}.fb-link:hover{background:none;text-decoration:underline}
.fb-chip{display:inline-block;font-size:11px;color:var(--s);border:1px solid var(--l);border-radius:99px;padding:1px 8px;margin-top:8px;background:var(--panel)}
.fb-form{margin-top:10px;border-top:1px solid var(--l);padding-top:10px}.fb-form label{margin-top:8px}.fb-form textarea{resize:vertical}
.fb-pie{display:flex;align-items:center;gap:10px;margin-top:10px}.fb-pie button{background:var(--t);border-color:var(--t);color:var(--b)}.fb-pie button:disabled{opacity:.5;cursor:default}
.fb-rf .fb-form{margin-top:4px}
</style></head><body>
<header id="hero">__ILUSTRACION__
<div class="texto"><p class="marca"><b><svg viewBox="-10 -10 219 198" aria-hidden="true"><path d="M0 0H58L100 13L142 0H199V165H142L100 178L58 165H0Z" fill="none" stroke="#7fa1c8" stroke-width="18" stroke-linejoin="round"/></svg>UNSAM</b><span>Universidad Nacional de San Martín<br>Proyecto CIAI Nº 34</span></p>
<h1>Explorador del corpus de financiamiento multilateral</h1>
<p class="fecha">Datos actualizados al __FECHA__</p></div>
<button type="button" id="b-recorrido" class="recorrido" data-fb="recorrido" data-fb-label="Botón Recorrido">Recorrido</button>
</header>
__INGRESO__
<details class="guia" id="guia" open data-fb="guia" data-fb-label="Guía de lectura"><summary><b>Guía de lectura</b></summary>
<p><b>Qué muestra.</b> Los compromisos que cada banco multilateral de desarrollo aprobó entre 2014 y 2025. Un monto
aprobado es lo que el banco se comprometió a prestar o donar, no lo desembolsado.</p>
<p><b>Cómo se usa.</b> Los botones de Tablero eligen un grupo con su ficha. Los filtros acotan la vista y todo se
recalcula. Copiar link guarda filtros y pestaña.</p>
<dl>
<dt>Resumen</dt><dd>Totales, rankings y la lista de operaciones.</dd>
<dt>Mapa</dt><dd>Monto por país, en plano o en globo (botones Plano y Globo). Un clic en un país lo filtra y otro clic lo saca.</dd>
<dt>Composición</dt><dd>Monto por grupo, institución y sector o zona.</dd>
<dt>Membrecía y concentración</dt><dd>Miembros de cada institución y porción que reciben sus cinco mayores
receptores. Solo cuenta países con código ISO3.</dd>
<dt>Soberana y no soberana</dt><dd>Soberana: financia a Estados o con su garantía. No soberana: financia a empresas
sin garantía estatal.</dd>
<dt>Forma del financiamiento</dt><dd>Préstamo, donación, garantía u otro. Mixta combina más de uno. Algunos bancos
no la publican.</dd>
<dt>Dólares</dt><dd>Corrientes, del año de aprobación, o constantes de 2025, ajustados por la inflación de Estados
Unidos.</dd>
<dt>Sin país</dt><dd>Operaciones de una región o de varios países. No entran en mapas ni en rankings de países.</dd>
<dt>Zonas</dt><dd>Las seis regiones del Banco Mundial.</dd>
<dt>Desembolsado</dt><dd>Lo que el banco entregó. Pocos lo publican.</dd>
<dt>Colores</dt><dd>Cada grupo mantiene su color. En los mapas, un color que se oscurece mide el monto y el gris es
"sin dato".</dd>
<dt>Hitos</dt><dd>Líneas verticales: Acuerdo de París (diciembre de 2015), AIIB y NDB (2016) y COVID-19 (2020).
Son contexto, no causas.</dd>
</dl>
<p class="aviso"><b>Tres advertencias.</b> Las operaciones de CAF salen de sus informes anuales, porque su archivo
oficial trae cerca de un cuarto de lo aprobado. La IFC anota el tope entero de algunas facilidades marco en cada banco
participante, así que sus montos en mercados financieros pueden estar inflados. En 2014 y 2015 la cartera privada del BID
figura como soberana, porque pasó a BID Invest en 2016.</p>
</details>
<p class="nota">Operaciones aprobadas 2014 a 2025, sin canceladas, armonizadas desde las fuentes oficiales. Millones de dólares.</p>
<p id="tableros" class="tableros" data-fb="tableros" data-fb-label="Tableros por banco"></p>
<div class="ficha" id="ficha" style="display:none" data-fb="ficha" data-fb-label="Ficha del banco"></div>
<div id="caf-comp" style="display:none" data-fb="caf-comp" data-fb-label="CAF según sus informes anuales"><details class="ref"><summary><h2>CAF según sus informes anuales</h2><span class="ver">Ver tabla</span></summary>
<p class="nota">Millones de dólares. Informe anual de CAF contra su archivo oficial (el corpus); el faltante no se suma.</p>
<div class="tabla"><table><thead><tr><th>Año</th><th class="n">Informe</th><th class="n">En el corpus</th><th class="n">Falta soberano</th><th class="n">Falta no soberano</th><th class="n">Cobertura</th></tr></thead><tbody id="t-caf"></tbody></table></div></details></div>
<div id="barra">
<div class="filtros">
<div data-fb="filtro-grupo" data-fb-label="Filtro: Banco"><label>Banco</label><select id="f-grupo"></select></div>
<div data-fb="filtro-inst" data-fb-label="Filtro: Institución"><label>Institución</label><select id="f-inst"></select></div>
<div data-fb="filtro-vent" data-fb-label="Filtro: Ventanilla"><label>Ventanilla</label><select id="f-vent"></select></div>
<div data-fb="filtro-desde" data-fb-label="Filtro: Desde"><label>Desde</label><select id="f-desde"></select></div>
<div data-fb="filtro-hasta" data-fb-label="Filtro: Hasta"><label>Hasta</label><select id="f-hasta"></select></div>
<div data-fb="filtro-pais" data-fb-label="Filtro: País contiene"><label>País contiene</label><input id="f-pais" placeholder="Argentina"></div>
<div data-fb="filtro-texto" data-fb-label="Filtro: Texto contiene"><label title="Nombre, sector o descripción contiene">Texto contiene</label><input id="f-texto" placeholder="solar, energy" title="Nombre, sector o descripción contiene"></div>
<div data-fb="filtro-forma" data-fb-label="Filtro: Forma"><label>Forma</label><select id="f-forma"></select></div>
<div data-fb="filtro-usd" data-fb-label="Filtro: Dólares"><label>Dólares</label><select id="f-usd"><option value="c">Corrientes</option><option value="k">Constantes de 2025</option></select></div>
</div>
<div style="display:none"><input id="f-iso"><input id="f-zona"></div>
<div class="fila-chips" data-fb="filtros-activos" data-fb-label="Filtros activos y copiar link"><div class="chips" id="chips"></div><span class="nota" id="b-link-estado"></span><button id="b-link">Copiar link de esta vista</button></div>
<input id="b-link-url" readonly style="display:none;margin-top:6px" aria-label="Link de esta vista">
<div class="kpis">
<div class="kpi" data-fb="kpi-ops" data-fb-label="Total: operaciones"><span class="nota">Operaciones</span><b id="k-ops">0</b></div>
<div class="kpi" data-fb="kpi-monto" data-fb-label="Total: monto aprobado"><span class="nota" id="k-monto-et">Aprobado, USD M</span><b id="k-monto">0</b></div>
<div class="kpi" data-fb="kpi-des" data-fb-label="Total: con desembolso publicado"><span class="nota">Con desembolso publicado</span><b id="k-des">0</b></div>
<div class="kpi" data-fb="kpi-pais" data-fb-label="Total: países"><span class="nota">Países</span><b id="k-pais">0</b></div>
</div>
</div>
<div id="tabs" role="tablist"></div>

<section id="p-resumen">
<div data-fb="resumen-evolucion" data-fb-label="Resumen: monto por año y grupo">
<h2>Monto aprobado por año y grupo bancario</h2>
<p class="nota" id="e-eje"></p>
<div class="mapa-ctrl"><label><input type="checkbox" id="e-pct"> Ver como participación (100%)</label></div>
<div id="e-area"></div><div class="leyenda" id="e-ley"></div>
</div>
<div data-fb="resumen-forma" data-fb-label="Resumen: por forma del financiamiento">
<h2>Por forma del financiamiento</h2>
<p class="nota">El AIIB y el NDB no publican la forma.</p>
<div id="e-forma"></div><div class="leyenda" id="e-forma-ley"></div>
</div>
<div data-fb="resumen-comparacion" data-fb-label="Resumen: comparación entre bancos">
<h2>Comparación entre bancos</h2>
<p class="nota">Cinco principales: porción del monto con país que reciben sus cinco mayores receptores. A ALC: porción que va a
América Latina y el Caribe, con sus agregados regionales.</p>
<div class="tabla"><table><thead><tr><th>Institución</th><th class="n">Operaciones</th><th class="n">USD M</th>
<th class="n">% del total</th><th class="n">Monto mediano</th><th class="n">A ALC</th><th class="n">Cinco principales</th>
<th>Principal receptor</th></tr></thead><tbody id="t-bancos"></tbody></table></div>
</div>
<div data-fb="resumen-ventanilla" data-fb-label="Resumen: ventanilla no soberana">
<details class="ref"><summary><h2>Ventanilla no soberana, por banco</h2><span class="ver">Ver tabla</span></summary>
<p class="nota">Porción no soberana del total aprobado de cada banco. En el Grupo Banco Mundial y el Grupo BID la ventanilla es la
institución (MIGA y BID Lab quedan fuera y se sacan los topes repetidos de la IFC). El AIIB y el NDB la declaran. CAF, BCIE
y FONPLATA se clasifican por el prestatario.</p>
<div class="tabla"><table><thead id="t-vent-cab"></thead><tbody id="t-vent"></tbody></table></div>
</details>
</div>
<div data-fb="resumen-fuentes" data-fb-label="Resumen: fuentes y fecha de descarga">
<details class="ref"><summary><h2>Fuentes y fecha de descarga</h2><span class="ver">Ver tabla</span></summary>
<p class="nota">Origen de cada institución y última descarga. El corpus se actualiza cada semana.</p>
<div class="tabla"><table><thead><tr><th>Institución</th><th class="n">Operaciones</th><th>Descargado</th><th>Fuente</th></tr></thead><tbody id="t-fuentes"></tbody></table></div>
</details>
</div>
<div data-fb="resumen-paises" data-fb-label="Resumen: diez principales países">
<h2>Diez principales países</h2><div class="barras" id="g-paises"></div>
</div>
<div data-fb="resumen-sectores" data-fb-label="Resumen: diez principales sectores">
<h2>Diez principales sectores</h2>
<p class="nota" id="g-sectores-nota">Cada banco usa su propio catálogo de sectores: elegí una institución. Al Banco Mundial se le quita el
prefijo del año (FY17).</p>
<div class="barras" id="g-sectores"></div>
</div>
<div data-fb="resumen-operaciones" data-fb-label="Resumen: tabla de operaciones">
<h2>Operaciones <span class="nota" id="t-nota"></span></h2>
<p><button id="b-csv">Descargar las filtradas como CSV</button> <span class="nota">El CSV trae todas las columnas. Clic en un encabezado
ordena y otro clic invierte el orden; clic en una descripción larga la abre.</span></p>
<div class="tabla"><table><thead><tr><th data-o="anio_aprobacion">Año</th><th data-o="institucion">Institución</th><th data-o="nombre">Operación</th><th data-o="pais">País</th><th data-o="sector">Sector</th><th data-o="forma_financiamiento">Forma</th><th data-o="tipo_ventanilla">Ventanilla</th><th class="n" data-o="monto">USD M</th><th class="n" data-o="monto_desembolsado_usd">Desembolsado USD M</th><th>Moneda original</th><th>Descripción</th></tr></thead><tbody id="t-cuerpo"></tbody></table></div>
<p><button id="b-mas">Mostrar más</button></p>
</div>
</section>

<section id="p-mapa" data-vista="plano" hidden>
<h2>Dónde fue el financiamiento</h2>
<p class="nota solo-plano">Con los filtros menos país y zona. Escala de raíz cuadrada, para que se vean los países chicos.</p>
<p class="nota solo-globo">Con los filtros menos país y zona. Arrastrar gira el globo. Atajos: <kbd>Espacio</kbd>
reproduce, <kbd>Esc</kbd> saca el país.</p>
<div class="historias solo-globo" id="g-hist"></div>
<div class="mapa-ctrl">
<span class="vista" id="m-vista" role="group" aria-label="Vista del mapa" data-fb="mapa-vista" data-fb-label="Mapa: vista plana o globo"><span class="nota">Vista</span><button type="button" data-v="plano" data-fb-nav>Plano</button><button type="button" data-v="globo" data-fb-nav>Globo</button></span>
<span class="grupo" data-fb="mapa-anios" data-fb-label="Mapa: reproductor de años"><button id="m-play">Reproducir</button><span id="m-anio"></span>
<span class="slider"><input type="range" id="m-slider" aria-label="Año del mapa"><span class="hitos" id="m-hitos"></span></span>
<button id="m-todo">Todo el período</button>
<label><input type="checkbox" id="m-acum"> Acumulado hasta el año</label></span>
<label class="solo-globo"><input type="checkbox" id="g-arcos" checked> Arcos desde la sede de cada banco</label></div>
<div class="mapa-grid"><div data-fb="mapa-monto-pais" data-fb-label="Mapa: monto por país"><div id="mapa" class="solo-plano"></div>
<div id="g-caja" class="solo-globo"><div id="globo"></div><div id="g-estado" class="nota"></div></div>
<div class="grad" id="m-grad"></div><div class="grad-et" id="m-grad-et"></div><div class="nd"><i></i>Sin monto en el período</div>
<p class="nota" id="m-sinpais"></p></div>
<div><div class="solo-plano"><div data-fb="mapa-top-paises" data-fb-label="Mapa: países con más monto"><h3>Países con más monto</h3><div class="barras lado" id="m-top"></div></div>
<div data-fb="mapa-zonas" data-fb-label="Mapa: por zona del mundo"><h3>Por zona del mundo</h3><div class="barras lado" id="m-zonas"></div></div></div>
<div class="solo-globo" id="g-panel" data-fb="mapa-panel-globo" data-fb-label="Globo: panel del país"></div></div></div>
</section>

<section id="p-comp" hidden>
<div data-fb="comp-treemap" data-fb-label="Composición: quién financia qué">
<h2>Quién financia qué</h2>
<p class="nota">El área es el monto. Los sectores se nombran como los publica cada banco. Un clic en un grupo o una institución lo filtra.</p>
<div class="mapa-ctrl"><label><input type="radio" name="tm-modo" value="sector" checked> Sector</label>
<label><input type="radio" name="tm-modo" value="zona"> Zona del mundo</label></div>
<div id="tm"></div>
</div>
<div data-fb="comp-zonas" data-fb-label="Composición: adónde va cada grupo">
<h2>Adónde va cada grupo</h2>
<p class="nota">Porción del monto de cada grupo que va a cada zona. Cada fila suma 100% con Sin país.</p>
<div class="tabla"><table class="heat"><thead id="h-cab"></thead><tbody id="h-cuerpo"></tbody></table></div>
</div>
<div data-fb="comp-mini" data-fb-label="Composición: porción no soberana">
<h2>Porción no soberana de cada grupo, año por año</h2>
<p class="nota">Sobre el total aprobado de cada grupo. No cambia con los filtros.</p>
<div class="mini" id="e-mini"></div>
</div>
</section>

<section id="p-membre" hidden>
<div data-fb="membre-grafico" data-fb-label="Membrecía: países miembros y concentración">
<h2>Membrecía y concentración</h2>
<p class="nota">Una burbuja por institución. Horizontal: países miembros al 31 de diciembre. Vertical: porción del monto del
año que reciben sus cinco mayores receptores. Tamaño: monto aprobado. Con pocos receptores esa
porción es alta por construcción. Filtros menos país y zona.</p>
<div class="mapa-ctrl"><button id="b-mb-play">Reproducir</button><span id="mb-anio"></span>
<span class="slider"><input type="range" id="mb-slider" aria-label="Año de la membrecía"><span class="hitos" id="mb-hitos"></span></span></div>
<div id="mb"></div><div class="leyenda" id="mb-ley"></div>
<p class="nota" id="mb-nota"></p>
</div>
</section>
<section id="p-sobre" class="prosa" hidden>
<div data-fb="sobre-proyecto" data-fb-label="Sobre el proyecto">
<h2>Sobre el proyecto</h2>
<p class="sobre-ir"><button data-ir="sobre-faq">Preguntas frecuentes</button><button data-ir="sobre-ruta">Hoja de ruta</button><button data-ir="sobre-decisiones">Decisiones y por qué</button></p>
<h3>Qué es</h3>
<p>El Proyecto Interdisciplinario CIAI Nº 34, UNSAM, "Financiamiento multilateral de iniciativas de transición energética", estudia
cuánto y cómo financian los bancos multilaterales de desarrollo la transición energética. Este explorador es su base de datos para
consultar: reúne <b data-v="ops"></b> operaciones con su monto, su país y el enlace a la fuente oficial.</p>
<h3>La pregunta</h3>
<p>Para saber cuánto fue a la transición energética hace falta antes una base comparable de todo lo que aprobaron los bancos. Esta etapa
la construye y la etapa 2 separa, dentro de ella, lo que corresponde a la transición.</p>
<h3>Bancos y período</h3>
<p>Operaciones aprobadas entre <b data-v="anios"></b>, sin las canceladas. Son <b data-v="inst"></b> instituciones de <b data-v="ngrupos"></b> grupos: <b data-v="grupos"></b>.</p>
<h3>Aprobado y desembolsado</h3>
<p>El monto aprobado es lo que el banco se comprometió a prestar o donar. El desembolsado es lo que entregó. Pocos bancos publican
desembolsos, por eso los totales y rankings de la página usan el monto aprobado.</p>
<h3>Criterio soberano</h3>
<p>Una operación es soberana cuando el prestatario es un Estado y no soberana cuando es una empresa u otra entidad. Los bancos que no
separan ventanillas se clasifican por el prestatario.</p>
<h3>Fuentes y actualización</h3>
<p>Los datos son los que cada banco publica oficialmente. Se actualizan cada semana. La dirección de cada fuente y la fecha de su última
descarga están en la tabla Fuentes y fecha de descarga, en la pestaña Resumen.</p>
<h3>Límites conocidos</h3>
<p>CAF publica solo una parte menor de lo aprobado: el resto sale de sus informes anuales. Los sectores no son comparables entre bancos,
porque cada uno usa su propio catálogo. En 2014 y 2015 hay operaciones privadas del BID dentro de la ventanilla soberana, porque su
cartera privada pasó a BID Invest recién en 2016.</p>
<h3>Etapa 2</h3>
<p>Operación por operación, se le asignará una etiqueta de crédito que diga si es verde. Antes hace falta una definición escrita de qué
cuenta como verde, porque sin ella ningún método automático da un resultado defendible. Está prevista para el año próximo.</p>
</div>
<div id="sobre-faq" class="faq" data-fb="sobre-faq" data-fb-label="Preguntas frecuentes">
<h2>Preguntas frecuentes</h2>
<details><summary>¿Qué es un monto aprobado?</summary><p>Lo que el banco se comprometió a prestar o donar cuando aprobó la operación. No es lo desembolsado, que es lo que entregó.
Pocos bancos publican desembolsos.</p></details>
<details><summary>¿Por qué no coincide con lo que declara un banco?</summary><p>El explorador suma el aporte de cada banco por operación aprobada, sin las canceladas, convertido a dólares con el tipo de cambio
promedio del año de aprobación. Los bancos suelen informar con otro corte: el Grupo Banco Mundial usa año fiscal, y algunos informes incluyen
lo cancelado, el costo total del proyecto o el aporte de terceros.</p></details>
<details><summary>¿Qué es soberano?</summary><p>Una operación es soberana cuando el prestatario es un Estado o cuenta con su garantía, y no soberana cuando es una empresa u otra entidad.</p></details>
<details><summary>¿Por qué hay operaciones sin país?</summary><p>Son operaciones de una región o de varios países. No entran en los mapas ni en los rankings de países, pero sí en los totales.</p></details>
<details><summary>¿Cada cuánto se actualiza?</summary><p>Cada lunes, de forma automática, desde las fuentes oficiales. El encabezado muestra la fecha de los datos.</p></details>
<details><summary>¿Cómo se cita?</summary><p class="cita">Proyecto CIAI Nº 34, UNSAM (2026). Explorador del corpus de financiamiento multilateral. Datos al __FECHA__.</p></details>
<details><summary>¿Cómo se descargan los datos?</summary><p>En la pestaña Resumen, al final de la lista de operaciones, el botón Descargar las filtradas como CSV baja lo que muestran los filtros, con todas las columnas.</p></details>
<details><summary>¿Cómo se comenta?</summary><p>Con el botón Feedback, abajo a la derecha: elegí un elemento de la página y dejá una pregunta, una mejora o algo nuevo. Los comentarios se responden en la misma página.</p></details>
</div>
<div id="sobre-ruta" data-fb="sobre-ruta" data-fb-label="Hoja de ruta">
<h2>Hoja de ruta</h2>
<div class="ruta">
<div><h3>Hecho, de agosto a octubre</h3><ul>
<li>Corpus de operaciones aprobadas de los siete grupos de bancos</li>
<li>Informes de acceso a los datos y de calidad de las bases</li>
<li>Actualización semanal automática</li>
<li>Explorador con mapa, composición, membrecía y recorrido guiado</li></ul></div>
<div><h3>Ahora, noviembre</h3><ul>
<li>Revisión de los tableros por banco con la dirección</li>
<li>Contraste de CAF con sus informes anuales</li>
<li>Exposición del proyecto</li></ul></div>
<div><h3>Después</h3><ul>
<li>Informe final, a fines de noviembre</li>
<li>Etapa 2, en 2027: etiqueta de crédito verde, operación por operación</li></ul></div>
</div>
</div>
<div id="sobre-decisiones" class="decisiones" data-fb="sobre-decisiones" data-fb-label="Decisiones y por qué">
<h2>Decisiones y por qué</h2>
<dl>
<dt>La unidad son los compromisos de cada banco (la dirección del proyecto)</dt><dd>Lo aprobado está en todas las fuentes; los desembolsos casi no se publican.</dd>
<dt>Cartera completa, sin recorte por país (la referente de los datos)</dt><dd>El recorte se hace al analizar, para no tener que rehacer el corpus.</dd>
<dt>Las canceladas quedan fuera y las operaciones en preparación entran marcadas (la dirección del proyecto)</dt><dd>Lo cancelado no es financiamiento; lo que está en preparación es un compromiso en marcha.</dd>
<dt>El monto es el aporte del banco (la dirección del proyecto)</dt><dd>Importa cuánto se compromete cada banco; el aporte de terceros va en una columna aparte.</dd>
<dt>Moneda original y dólares corrientes, con constantes de 2025 al lado (la dirección del proyecto)</dt><dd>Conservar la moneda permite auditar la conversión, y el dólar permite sumar.</dd>
<dt>Soberano o no soberano según el prestatario (la referente de los datos)</dt><dd>Es el único criterio que se aplica igual en todos los bancos.</dd>
<dt>MIGA y BID Lab no cuentan como soberanos ni como no soberanos (la dirección del proyecto)</dt><dd>Garantías y cooperación técnica no son inequívocamente no soberanas.</dd>
<dt>Cada banco con sus propios sectores (la dirección del proyecto)</dt><dd>Los catálogos no son comparables; reclasificar exige leer los textos de los proyectos y queda para otra etapa.</dd>
<dt>Base completa y consistente antes que más bancos (la dirección del proyecto)</dt><dd>Un universo parcial hace falsas las comparaciones.</dd>
<dt>2020 se lee aparte (la referente de los datos)</dt><dd>Los bancos reprogramaron préstamos ya aprobados y la carga fue desordenada.</dd>
<dt>Se unen las descargas de CAF (el equipo técnico)</dt><dd>CAF dejó de publicar operaciones terminadas; tomar solo la última descarga las perdería.</dd>
</dl>
</div>
</section>
<div id="fb-ui">
<button type="button" id="fb-btn" aria-expanded="false" aria-controls="fb-panel"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" aria-hidden="true"><path d="M2.5 3.5h11v7h-6l-3 2.5v-2.5h-2z"/></svg>Feedback</button>
<div id="fb-panel" class="fb-flot" hidden role="dialog" aria-label="Feedback"></div>
<div id="fb-aviso" class="fb-flot" hidden role="status">Elegí un elemento para comentar · Esc para salir</div>
<div id="fb-burbuja" class="fb-flot" hidden role="dialog" aria-label="Comentarios del elemento"></div>
<div id="fb-contorno"><span></span></div>
<div id="fb-marcas"></div>
</div>
<div id="tr-ui"><div id="tr-capa"></div><div id="tr-foco"></div><div id="tr-caja" role="dialog" aria-modal="true" aria-labelledby="tr-tit"></div></div>
<div id="tip"></div>
<script>__CARGADOR__
// P trae las columnas junto con los datos: así la página nunca interpreta datos nuevos con un orden
// de columnas viejo, aunque la página y los datos se publiquen en momentos distintos.
function iniciar(P,COM){
const C=P.columnas,D=P.datos,V=P.ventanillas,F=P.fuentes,GEO=P.geo||{},ZON=P.zonas||{},MEMB=P.membrecia||{},SEDE=P.sedes||{},CEXTRA=P.centroides||{};
const i=Object.fromEntries(C.map((c,k)=>[c,k]));
const D3=typeof d3!=='undefined'&&typeof topojson!=='undefined';
const U_ATLAS='https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-110m.json';
const U_GEOJSON='https://cdn.jsdelivr.net/gh/vasturiano/globe.gl@2.45.0/example/datasets/ne_110m_admin_0_countries.geojson';
const U_GLOBE=['https://cdn.jsdelivr.net/npm/globe.gl@2.46.2/dist/globe.gl.min.js','sha384-1uolMBZ25k3zJcNwCLEv49+L+m2dZudqAzsoSAJfQTzDCSBxJzrMuZ2dkp/5JKiT'];
const fmt=n=>n.toLocaleString('es-AR',{maximumFractionDigits:0});
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const urlSegura=u=>/^https?:\/\//i.test(String(u||''))?esc(u):'';
const $=id=>document.getElementById(id);
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
function opciones(sel,valores,todas){sel.innerHTML=(todas?'<option value="">'+todas+'</option>':'')+valores.map(v=>`<option>${esc(v)}</option>`).join('')}
const unicos=c=>[...new Set(D.map(r=>r[i[c]]).filter(v=>v!==null&&v!==''))].sort();
const NOMBRE={GBM:'Grupo Banco Mundial',GBID:'Grupo BID'};const nom=g=>NOMBRE[g]||g;
// Un color por grupo, siempre el mismo, en el orden fijo de la paleta.
const GR=__GRUPOS__;
const enOrden=gs=>GR.filter(g=>gs.includes(g));
const cod=g=>({'Grupo Banco Mundial':'GBM','Grupo BID':'GBID'})[g]||g;
const colG=g=>css(GR.indexOf(cod(g))<0?'--gx':'--g'+(GR.indexOf(cod(g))+1));
const FORMAS=['prestamo','donacion','garantia','otro','mixto','sin dato'];
const colF=k=>css('--f'+(FORMAS.indexOf(k)+1));
const tinta=c=>d3.lab(c).l>62?'#111':'#fff';
const nombreIso=iso=>(GEO[iso]||{}).nombre||iso;
const REDUCE=!!(window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches);
// Anima fn(t), t de 0 a 1, atada a un elemento. Una animación nueva con el mismo nombre corta la anterior.
function animar(el,nombre,dur,fn,ease){if(!D3||REDUCE||!dur){fn(1);return}
 d3.select(el).transition(nombre).duration(dur).ease(ease||d3.easeCubicOut).tween(nombre,()=>fn);}
// Los totales de arriba cuentan hasta su valor nuevo.
function numero(el,a){const de=+el.dataset.v||0;el.dataset.v=a;animar(el,'n',550,t=>{el.textContent=fmt(de+(a-de)*t)})}
// Resaltado cruzado: pasar el mouse por un grupo lo destaca en todos los gráficos y baja el resto.
let HL=null;
function resaltar(g){if(g===HL)return;HL=g;document.querySelectorAll('[data-grp]').forEach(e=>e.classList.toggle('dim',!!g&&e.dataset.grp!==g))}
$('f-grupo').innerHTML='<option value="">Todos</option>'+enOrden(unicos('banco_grupo')).map(v=>`<option value="${esc(v)}">${esc(nom(v))}</option>`).join('');
opciones($('f-forma'),unicos('forma_financiamiento'),'Todas');
// La institución depende del banco elegido, para que no se pueda pedir una combinación imposible.
function instituciones(){const g=$('f-grupo').value,actual=$('f-inst').value;
 const vs=[...new Set(D.filter(r=>!g||r[i.banco_grupo]===g).map(r=>r[i.institucion]))].sort();
 opciones($('f-inst'),vs,'Todas');$('f-inst').value=vs.includes(actual)?actual:'';}
instituciones();$('f-grupo').addEventListener('input',instituciones);
opciones($('f-vent'),['soberana','no_soberana','sin asignar'],'Todas');
const anios=unicos('anio_aprobacion');opciones($('f-desde'),anios);opciones($('f-hasta'),anios);
$('f-hasta').value=anios[anios.length-1];
// omitir: filtros que el mapa, el globo y la membrecía no aplican a sí mismos (c: país, r: zona).
function filtradas(omitir){
 omitir=omitir||[];
 const g=$('f-grupo').value,s=$('f-inst').value,v=$('f-vent').value,d=+$('f-desde').value,h=+$('f-hasta').value,
 p=$('f-pais').value.toLowerCase(),t=$('f-texto').value.toLowerCase(),fo=$('f-forma').value,
 iso=omitir.includes('c')?'':$('f-iso').value,zo=omitir.includes('r')?'':$('f-zona').value;
 return D.filter(r=>(!g||r[i.banco_grupo]===g)&&(!s||r[i.institucion]===s)&&
  (!v||(v==='sin asignar'?!r[i.tipo_ventanilla]:r[i.tipo_ventanilla]===v))&&
  r[i.anio_aprobacion]>=d&&r[i.anio_aprobacion]<=h&&(!p||String(r[i.pais]||'').toLowerCase().includes(p))&&
  (!iso||r[i.iso3]===iso)&&(!zo||r[i.zona]===zo)&&
  (!fo||r[i.forma_financiamiento]===fo)&&
  (!t||(String(r[i.nombre]||'')+' '+String(r[i.sector]||'')+' '+String(r[i.descripcion]||'')).toLowerCase().includes(t)));}
// Barras con ancho animado. Cada par: [nombre, valor, atributos, seleccionada, color].
function barras(el,pares){const m=Math.max(1,...pares.map(x=>x[1])),prev=el._p||{},nuevo={};
 el.innerHTML=pares.map(([k,v,at,sel,col])=>{nuevo[k]=100*v/m;return `<div ${at||''} class="${sel?'sel':''}"><span title="${esc(k)}">${esc(k)}</span><span class="pista"><span class="b" style="width:${prev[k]||0}%${col?';background:'+col:''}"></span></span><span class="n">${fmt(v)}</span></div>`}).join('')||'<p class="nota">Sin datos</p>';
 el._p=nuevo;
 requestAnimationFrame(()=>requestAnimationFrame(()=>{el.querySelectorAll('.b').forEach((b,j)=>{if(pares[j])b.style.width=100*pares[j][1]/m+'%'})}));}
const monto=r=>($('f-usd').value==='k'?r[i.monto_constante_usd]:r[i.monto_aprobado_usd])||0;
const unidad=()=>$('f-usd').value==='k'?'USD M de 2025':'USD M';
function sumar(f,c){const o={};f.forEach(r=>{const k=r[i[c]]||'sin dato';o[k]=(o[k]||0)+monto(r)/1e6});return o}
function mediana(xs){if(!xs.length)return 0;xs=[...xs].sort((a,b)=>a-b);const m=xs.length>>1;return xs.length%2?xs[m]:(xs[m-1]+xs[m])/2}
// Porción del monto con país (ISO3) que reciben los cinco países más grandes. Es la misma cuenta en la tabla de bancos y en la membrecía.
function top5(rs){const pp={};rs.forEach(r=>{const k=r[i.iso3];if(k)pp[k]=(pp[k]||0)+monto(r)});
 const orden=Object.entries(pp).sort((a,b)=>b[1]-a[1]),tp=orden.reduce((a,x)=>a+x[1],0);
 return {p:tp?100*orden.slice(0,5).reduce((a,x)=>a+x[1],0)/tp:null,primero:orden.length?orden[0][0]:''}}
function porBanco(f,total){const g={};f.forEach(r=>{(g[r[i.institucion]]=g[r[i.institucion]]||[]).push(r)});
 return Object.entries(g).map(([k,rs])=>{const m=rs.reduce((a,r)=>a+monto(r),0)/1e6;
  const alc=rs.filter(r=>r[i.region]==='A').reduce((a,r)=>a+monto(r),0)/1e6,t=top5(rs);
  return [k,rs.length,m,total?100*m/total:0,mediana(rs.filter(r=>r[i.monto_aprobado_usd]!==null).map(r=>monto(r)/1e6)),m?100*alc/m:0,t.p||0,t.primero?nombreIso(t.primero):'']})
  .sort((a,b)=>b[2]-a[2])}
const pct=n=>n.toLocaleString('es-AR',{maximumFractionDigits:1})+'%';
// USD M a una forma legible. "Billón" se evita porque significa cosas distintas según el país.
const grande=v=>v>=1e6?'USD '+(v/1e6).toLocaleString('es-AR',{maximumFractionDigits:1})+' millones de millones':v>=1e3?'USD '+(v/1e3).toLocaleString('es-AR',{maximumFractionDigits:1})+' mil millones':'USD '+fmt(v)+' millones';
// Tablero integrado y uno por grupo bancario: cada botón fija el banco y muestra su ficha.
$('tableros').innerHTML='<span class="nota">Tablero: </span>'+['',...enOrden(unicos('banco_grupo'))].map(g=>`<button data-g="${g}"${g?` data-grp="${g}"`:''}>${g?`<i class="dot" style="background:${colG(g)}"></i>`:''}${g?nom(g):'Integrado'}</button>`).join('');
document.querySelectorAll('#tableros button').forEach(b=>b.onclick=()=>{$('f-grupo').value=b.dataset.g;$('f-grupo').dispatchEvent(new Event('input'))});
$('t-caf').innerHTML=(P.complemento_caf||[]).map(x=>`<tr><td>${x.anio}</td><td class="n">${fmt(x.informe_total_mm)}</td><td class="n">${fmt(x.corpus_soberano_mm+x.corpus_no_soberano_mm+(x.corpus_sin_clasificar_mm||0))}</td><td class="n">${fmt(x.complemento_soberano_mm)}</td><td class="n">${fmt(x.complemento_no_soberano_mm)}</td><td class="n">${pct(x.cobertura_pct)}</td></tr>`).join('');
function ficha(){const g=$('f-grupo').value;
 document.querySelectorAll('#tableros button').forEach(b=>b.classList.toggle('on',b.dataset.g===g));
 $('ficha').style.display=g&&P.fichas[g]?'block':'none';$('ficha').textContent=P.fichas[g]||'';
 $('caf-comp').style.display=g==='CAF'&&(P.complemento_caf||[]).length?'block':'none';}
$('f-grupo').addEventListener('input',ficha);ficha();
const VG=[...new Set(V.map(x=>x.grupo))].sort((a,b)=>GR.indexOf(cod(a))-GR.indexOf(cod(b)));
$('t-vent-cab').innerHTML='<tr><th>Año</th>'+VG.map(g=>`<th class="n">${esc(g)}</th>`).join('')+'</tr>';
$('t-vent').innerHTML=[...new Set(V.map(x=>x.anio))].sort().map(a=>{const v=g=>{const x=V.find(y=>y.anio===a&&y.grupo===g);return x?pct(x.pct_no_soberana):''};
 return `<tr><td>${a}</td>${VG.map(g=>`<td class="n">${v(g)}</td>`).join('')}</tr>`}).join('');
$('t-fuentes').innerHTML=F.map(x=>`<tr><td>${esc(x.institucion)}</td><td class="n">${fmt(x.operaciones)}</td><td>${esc(x.descargado)}</td><td><a href="${urlSegura(x.fuente)}" target="_blank" rel="noopener">${esc(x.fuente)}</a></td></tr>`).join('');

// ---- Hitos: líneas de contexto en los gráficos de tiempo y marcas en los controles de año.
const HITOS=[{a:2015,c:'París',t:'Acuerdo de París',f:'Diciembre de 2015'},
 {a:2016,c:'AIIB y NDB',t:'Comienzo de operaciones del AIIB y el NDB',f:'AIIB: enero de 2016. NDB: primeros préstamos en 2016'},
 {a:2020,c:'COVID-19',t:'COVID-19',f:'Pandemia declarada en marzo de 2020'}];
function hitosSvg(xf,ks,m,h){return HITOS.filter(o=>o.a>=ks[0]&&o.a<=ks[ks.length-1]).map(o=>{const x=xf(o.a),fin=o.a===2015;
 return `<line x1="${x}" x2="${x}" y1="${m.t-6}" y2="${h-m.b}" stroke="${css('--m')}" stroke-dasharray="3 3" style="pointer-events:none"/><text x="${x+(fin?-4:4)}" y="${m.t-10}" text-anchor="${fin?'end':'start'}" font-size="10.5" fill="${css('--s')}" data-tip="${o.t}\n${o.f}">${o.c}</text>`}).join('')}
function hitosSlider(id,d,h){const el=$(id);if(!(h>d)){el.innerHTML='';return}
 el.innerHTML=HITOS.filter(o=>o.a>=d&&o.a<=h).map((o,n)=>`<i style="left:calc(8px + (100% - 16px) * ${(o.a-d)/(h-d)});top:${(n%2)*13}px" data-tip="${o.t}\n${o.f}"><u></u>${o.c}</i>`).join('')}

// ---- Reproductores: el mapa (plano y globo) y la membrecía comparten la misma lógica de años.
const MAPA={anio:null,acum:false,timer:null,svgW:0},MB={anio:null,timer:null};
function parar(S){if(S.timer){clearInterval(S.timer);S.timer=null}if(S.btn)S.btn.textContent='Reproducir'}
function pararTodo(){[MAPA,MB].forEach(parar)}
function jugar(S,btn,dibuja,ms){if(S.timer){parar(S);return}
 const d=+$('f-desde').value,h=+$('f-hasta').value;if(d>=h)return;
 if(S.anio===null||S.anio>=h)S.anio=d;S.btn=btn;btn.textContent='Pausa';dibuja();
 S.timer=setInterval(()=>{if(S.anio>=h){parar(S);dibuja();return}S.anio++;dibuja()},ms)}

// ---- Pestañas: solo se dibuja la que está a la vista.
const TABS=[['resumen','Resumen'],['mapa','Mapa'],['comp','Composición'],['membre','Membrecía y concentración'],['sobre','Sobre el proyecto']];
let TAB='resumen',FILT=[],VISTA='plano';
const enGlobo=()=>TAB==='mapa'&&VISTA==='globo';
$('tabs').innerHTML=TABS.map(([k,n])=>`<button role="tab" data-t="${k}" data-fb-nav>${n}</button>`).join('');
document.querySelectorAll('#tabs button').forEach(b=>b.onclick=()=>{pestania(b.dataset.t);escribirHash()});
function pestania(t,dib){if(!TABS.some(x=>x[0]===t))t='resumen';pararTodo();TAB=t;
 document.querySelectorAll('#tabs button').forEach(b=>{b.classList.toggle('on',b.dataset.t===t);b.setAttribute('aria-selected',b.dataset.t===t)});
 TABS.forEach(([k])=>{$('p-'+k).hidden=k!==t});marcarVista();if(!enGlobo())pausarGlobo();if(dib!==false)dibujarTab();fbCambio();}
function marcarVista(){$('p-mapa').dataset.vista=VISTA;document.querySelectorAll('#m-vista button').forEach(b=>{const on=b.dataset.v===VISTA;b.classList.toggle('on',on);b.setAttribute('aria-pressed',on)})}
document.querySelectorAll('#m-vista button').forEach(b=>b.onclick=()=>{if(b.dataset.v===VISTA)return;parar(MAPA);VISTA=b.dataset.v;marcarVista();if(VISTA!=='globo')pausarGlobo();escribirHash();dMapa()});
function dibujarTab(){ocultarTip();({resumen:dResumen,mapa:dMapa,comp:dComp,membre:dMembre,sobre:dSobre})[TAB](FILT);}
document.querySelectorAll('[data-ir]').forEach(b=>b.onclick=()=>$(b.dataset.ir).scrollIntoView({behavior:REDUCE?'auto':'smooth'}));
function dSobre(){const g=enOrden(unicos('banco_grupo')).map(nom),
 v={ops:fmt(D.length),anios:`${anios[0]} y ${anios[anios.length-1]}`,inst:unicos('institucion').length,ngrupos:g.length,grupos:g.slice(0,-1).join(', ')+' y '+g[g.length-1]};
 document.querySelectorAll('#p-sobre [data-v]').forEach(e=>{e.textContent=v[e.dataset.v]})}
const ancho=el=>Math.max(260,el.clientWidth||260);
const sinD3=el=>{el.innerHTML='<p class="nota">No se pudieron cargar las librerías de gráficos (hace falta conexión). Los filtros, los totales y las tablas funcionan igual.</p>'};

// ---- Resumen: monto por año y por forma.
function ejes(w,h,m,x,y,ks,fy){const ny=Math.max(2,Math.floor((h-m.t-m.b)/46));
 const yt=y.ticks(ny).map(t=>`<line x1="${m.l}" x2="${w-m.r}" y1="${y(t)}" y2="${y(t)}" stroke="${css('--l')}"/><text x="${m.l-6}" y="${y(t)+4}" text-anchor="end" font-size="11" fill="${css('--s')}">${fy(t)}</text>`).join('');
 const paso=w<520?2:1,xt=ks.filter((a,k)=>k%paso===0).map(a=>`<text x="${x(a)}" y="${h-6}" text-anchor="middle" font-size="11" fill="${css('--s')}">${w<520?String(a).slice(2):a}</text>`).join('');
 return yt+xt;}
const EV={area:null,forma:null,modo:null};
function dEvol(f){
 if(!D3){sinD3($('e-area'));return}
 const ks=anios.filter(a=>a>=+$('f-desde').value&&a<=+$('f-hasta').value),un=unidad();
 const gs=GR.filter(g=>f.some(r=>r[i.banco_grupo]===g)).concat([...new Set(f.map(r=>r[i.banco_grupo]))].filter(g=>!GR.includes(g)));
 const pa={};f.forEach(r=>{const a=r[i.anio_aprobacion],g=r[i.banco_grupo];(pa[a]=pa[a]||{})[g]=(pa[a][g]||0)+monto(r)/1e6});
 const pctModo=$('e-pct').checked;
 $('e-eje').textContent=ks.length>1?`Apilado por grupo, en ${un}${pctModo?', como participación del total de cada año':''}. La escala empieza en 0. El mouse sobre un año muestra cada grupo y sobre la leyenda resalta un grupo.`:'Elegí al menos dos años para ver la evolución.';
 const el=$('e-area');
 if(ks.length<2||!gs.length){el.innerHTML='';$('e-ley').innerHTML='';EV.area=null}
 else{
  const prev=EV.area,mismo=EV.modo===pctModo;EV.modo=pctModo;
  const todos=GR.filter(g=>gs.includes(g)||(prev&&prev.gs.includes(g))).concat(gs.filter(g=>!GR.includes(g)));
  const nuevo={};ks.forEach(a=>gs.forEach(g=>nuevo[a+'|'+g]=(pa[a]||{})[g]||0));
  const w=ancho(el),h=330,m={l:60,r:70,t:26,b:28};
  const x=d3.scaleLinear([ks[0],ks[ks.length-1]],[m.l,w-m.r]),paso=(w-m.l-m.r)/(ks.length-1);
  const pintar=t=>{
   // Cada cuadro mezcla los valores anteriores con los nuevos; sin anteriores, el área crece desde cero.
   const rows=ks.map(a=>{const o={anio:a};todos.forEach(g=>{const k=a+'|'+g,n=nuevo[k]||0,p=prev&&mismo?(prev.v[k]||0):(prev?n:0);o[g]=p+(n-p)*t});return o});
   const st=d3.stack().keys(todos).offset(pctModo?d3.stackOffsetExpand:d3.stackOffsetNone)(rows);
   const y=d3.scaleLinear([0,pctModo?1:(d3.max(st[st.length-1],d=>d[1])||1)],[h-m.b,m.t]).nice();
   const ar=d3.area().x(d=>x(d.data.anio)).y0(d=>y(d[0])).y1(d=>y(d[1]));
   const dir=st.map(s=>{if(!gs.includes(s.key))return '';const u=s[s.length-1],mid=(y(u[0])+y(u[1]))/2;return y(u[0])-y(u[1])>13?`<text x="${w-m.r+8}" y="${mid+4}" font-size="12" font-weight="600" fill="${css('--t')}">${s.key}</text>`:''}).join('');
   el._ctx={m,paso,ks,y,st,x};
   el.innerHTML=`<svg viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" role="img" aria-label="Monto aprobado por año y grupo">${ejes(w,h,m,x,y,ks,v=>pctModo?Math.round(v*100)+'%':fmt(v))}`+
    st.map(s=>`<path data-grp="${cod(s.key)}" d="${ar(s)}" fill="${colG(s.key)}" stroke="#fff" stroke-width="1.2"/>`).join('')+dir+
    `<line id="e-cur" y1="${m.t}" y2="${h-m.b}" stroke="${css('--t')}" stroke-width="1" style="display:none;pointer-events:none"/>`+
    ks.map(a=>{const tot=gs.reduce((q,g)=>q+((pa[a]||{})[g]||0),0);
     return `<rect x="${x(a)-paso/2}" y="${m.t}" width="${paso}" height="${h-m.t-m.b}" fill="transparent" data-tip="${a} · total ${fmt(tot)} ${un}\n${gs.filter(g=>(pa[a]||{})[g]).map(g=>colG(g)+'|'+g+'  '+fmt(pa[a][g])+(tot?' ('+pct(100*pa[a][g]/tot)+')':'')).join('\n')}"/>`}).join('')+hitosSvg(x,ks,m,h)+'</svg>';
  };
  EV.area={v:nuevo,gs};
  animar(el,'area',prev&&!mismo?0:700,pintar);
  $('e-ley').innerHTML=gs.map(g=>`<span data-grp="${cod(g)}"><i style="background:${colG(g)}"></i>${nom(g)}</span>`).join('');
 }
 // Forma del financiamiento: barras apiladas con 2 px de separación entre segmentos.
 const pf={};f.forEach(r=>{const a=r[i.anio_aprobacion],k=r[i.forma_financiamiento]||'sin dato';(pf[a]=pf[a]||{})[k]=(pf[a][k]||0)+monto(r)/1e6});
 const el2=$('e-forma');
 if(!ks.length){el2.innerHTML='';$('e-forma-ley').innerHTML='';EV.forma=null}
 else{
  const prevF=EV.forma,nf={};ks.forEach(a=>FORMAS.forEach(k=>nf[a+'|'+k]=(pf[a]||{})[k]||0));EV.forma=nf;
  const w=ancho(el2),h=290,m={l:60,r:8,t:26,b:28};
  const x=d3.scaleBand(ks,[m.l,w-m.r]).paddingInner(.25);
  const pintarF=t=>{
   const v=(a,k)=>{const q=a+'|'+k,n=nf[q],p=prevF?(prevF[q]||0):0;return p+(n-p)*t};
   const tot=a=>FORMAS.reduce((s,k)=>s+v(a,k),0),mx=Math.max(1,...ks.map(tot));
   const y=d3.scaleLinear([0,mx],[h-m.b,m.t]).nice(),xc=a=>x(a)+x.bandwidth()/2;
   el2.innerHTML=`<svg viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" role="img" aria-label="Monto aprobado por año y forma">${ejes(w,h,m,xc,y,ks,fmt)}`+
    ks.map(a=>{let acc=0;return FORMAS.map(k=>{const q=v(a,k);if(q<=0)return '';const y1=y(acc),y0=y(acc+q);acc+=q;
     return `<rect x="${x(a)}" width="${x.bandwidth()}" y="${y0}" height="${Math.max(0,y1-y0-1.5)}" fill="${colF(k)}" data-tip="${a} · ${k}\n${fmt(nf[a+'|'+k])} ${un}"/>`}).join('')}).join('')+hitosSvg(xc,ks,m,h)+'</svg>';
  };
  animar(el2,'forma',650,pintarF);
  $('e-forma-ley').innerHTML=FORMAS.filter(k=>f.some(r=>(r[i.forma_financiamiento]||'sin dato')===k)).map(k=>`<span><i style="background:${colF(k)}"></i>${esc(k)}</span>`).join('');
 }
}
// Seguir con el mouse el año y el grupo que se están mirando en el área apilada.
$('e-area').addEventListener('mousemove',ev=>{const el=$('e-area'),c=el._ctx,svg=el.querySelector('svg');if(!c||!svg)return;
 const r=svg.getBoundingClientRect(),px=ev.clientX-r.left,py=ev.clientY-r.top;
 const k=Math.max(0,Math.min(c.ks.length-1,Math.round((px-c.m.l)/c.paso))),cur=el.querySelector('#e-cur');
 if(cur){cur.setAttribute('x1',c.x(c.ks[k]));cur.setAttribute('x2',c.x(c.ks[k]));cur.style.display=''}
 const yv=c.y.invert(py),s=c.st.find(s=>yv>=s[k][0]&&yv<=s[k][1]);resaltar(s?cod(s.key):null)});
$('e-area').addEventListener('mouseleave',()=>{resaltar(null);const cur=$('e-area').querySelector('#e-cur');if(cur)cur.style.display='none'});
$('e-pct').addEventListener('input',()=>dEvol(FILT));

// ---- Resumen: comparación entre bancos, rankings y operaciones.
function dComparar(f){const total=f.reduce((a,r)=>a+monto(r),0)/1e6;
 $('t-bancos').innerHTML=porBanco(f,total).map(b=>`<tr><td>${esc(b[0])}</td><td class="n">${fmt(b[1])}</td><td class="n">${fmt(b[2])}</td><td class="n">${pct(b[3])}</td><td class="n">${b[4].toLocaleString('es-AR',{maximumFractionDigits:1})}</td><td class="n">${pct(b[5])}</td><td class="n">${pct(b[6])}</td><td>${esc(b[7])}</td></tr>`).join('');}
function dPais(f){const top=o=>Object.entries(o).sort((a,b)=>b[1]-a[1]).slice(0,10);
 const sel=$('f-iso').value,po={};f.forEach(r=>{const k=r[i.iso3];if(k)po[k]=(po[k]||0)+monto(r)/1e6});
 barras($('g-paises'),top(po).map(([k,v])=>[nombreIso(k),v,`data-iso="${k}"`,k===sel]));
 $('g-paises').querySelectorAll('[data-iso]').forEach(e=>e.onclick=()=>filtro('f-iso',e.dataset.iso));
 const unaInst=$('f-inst').value||new Set(f.map(r=>r[i.institucion])).size===1;
 const sinFY=o=>{const r={};Object.entries(o).forEach(([k,v])=>{const c=k.replace(/^FY\d{2} - /,'');r[c]=(r[c]||0)+v});return r};
 $('g-sectores-nota').style.display=unaInst?'none':'';
 if(unaInst)barras($('g-sectores'),top(sinFY(sumar(f,'sector'))));else $('g-sectores').innerHTML='';}
const PAG=50;let ORDEN={c:'monto',dir:-1},VISTAS=PAG;
const valor=(r,c)=>c==='monto'?monto(r):r[i[c]];
document.querySelectorAll('th[data-o]').forEach(th=>th.onclick=()=>{const c=th.dataset.o;
 ORDEN=ORDEN.c===c?{c,dir:-ORDEN.dir}:{c,dir:(c==='monto'||c==='anio_aprobacion'||c==='monto_desembolsado_usd')?-1:1};VISTAS=PAG;dOps(FILT);});
function comparar(a,b){const x=valor(a,ORDEN.c),y=valor(b,ORDEN.c);
 if(x===null||x===undefined||x==='')return 1;if(y===null||y===undefined||y==='')return -1;
 return (typeof x==='number'&&typeof y==='number'?x-y:String(x).localeCompare(String(y),'es'))*ORDEN.dir;}
function dOps(f){
 const orden=[...f].sort(comparar).slice(0,VISTAS);
 $('t-nota').textContent=`(${fmt(Math.min(VISTAS,f.length))} de ${fmt(f.length)})`;
 $('b-mas').style.display=f.length>VISTAS?'':'none';
 const mo=r=>r[i.moneda_original]&&r[i.moneda_original]!=='USD'?`${esc(r[i.moneda_original])} ${fmt((r[i.monto_original]||0)/1e6)} M`:'';
 const de=r=>{const t=r[i.descripcion];if(!t)return '';const e=esc(t);return t.length>140?`<details><summary>${esc(t.slice(0,140))}...</summary>${e}</details>`:e};
 const nombreOp=r=>{const n=esc(r[i.nombre]||'(sin nombre)'),u=urlSegura(r[i.url_proyecto]);return u?`<a href="${u}" target="_blank" rel="noopener">${n}</a>`:(r[i.nombre]?n:'')};
 $('t-cuerpo').innerHTML=orden.map(r=>`<tr><td>${r[i.anio_aprobacion]}</td><td>${esc(r[i.institucion])}</td><td>${nombreOp(r)}</td><td>${esc(r[i.pais]||'')}</td><td>${esc(r[i.sector]||'')}</td><td>${esc(r[i.forma_financiamiento]||'')}</td><td>${esc((r[i.tipo_ventanilla]||'').replace('_',' '))}</td><td class="n">${r[i.monto_aprobado_usd]===null?'sin dato':fmt(monto(r)/1e6)}</td><td class="n">${r[i.monto_desembolsado_usd]===null?'':fmt(r[i.monto_desembolsado_usd]/1e6)}</td><td>${mo(r)}</td><td>${de(r)}</td></tr>`).join('');}
$('b-mas').onclick=()=>{VISTAS+=PAG;dOps(FILT)};
$('b-csv').onclick=()=>{const q=v=>v===null?'':'"'+String(v).replace(/"/g,'""')+'"';
 const csv=[C.join(',')].concat(filtradas().map(r=>r.map(q).join(','))).join('\n');
 const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));a.download='corpus-filtrado.csv';a.click();};
function dResumen(f){dEvol(f);dComparar(f);dPais(f);dOps(f)}

// ---- Mapa
let ATLAS=null,ATLAS_ERR=!D3;
if(D3)d3.json(U_ATLAS).then(w=>{ATLAS=topojson.feature(w,w.objects.countries).features;if(TAB==='mapa'&&VISTA==='plano')dMapa()}).catch(()=>{ATLAS_ERR=true;if(TAB==='mapa'&&VISTA==='plano')dMapa()});
const enVent=(a,S)=>S.anio===null||(S.acum?a<=S.anio:a===S.anio);
function datosMapa(f){
 f=f||filtradas(['c','r']);const anual={},sin={};let sinTot=0,sinN=0;
 f.forEach(r=>{const m=monto(r)/1e6,a=r[i.anio_aprobacion],k=r[i.iso3];
  if(!k){sinTot+=m;sinN++;const n=r[i.pais]||'(vacío)';sin[n]=(sin[n]||0)+m;return}
  const o=anual[k]=anual[k]||{};o[a]=(o[a]||0)+m;});
 return {anual,sin,sinTot,sinN};}
function valoresDe(dm,S){const v={};
 Object.entries(dm.anual).forEach(([k,o])=>{let s=0;Object.entries(o).forEach(([a,m])=>{if(enVent(+a,S))s+=m});v[k]=s});return v;}
function maximoDe(dm,S){let mx=0;Object.values(dm.anual).forEach(o=>{
 if(S.anio===null||S.acum){mx=Math.max(mx,Object.values(o).reduce((x,y)=>x+y,0))}else mx=Math.max(mx,...Object.values(o))});return mx||1;}
const rampa=()=>D3?d3.interpolateLab(css('--seq0'),css('--seq1')):()=>'#888';
// Controles de año del mapa, iguales en la vista plana y en el globo.
function controlesAnio(S,p,txt){const d=+$('f-desde').value,h=+$('f-hasta').value,sl=$(p+'-slider');
 sl.min=d;sl.max=h;if(S.anio!==null)S.anio=Math.min(h,Math.max(d,S.anio));sl.value=S.anio===null?h:S.anio;
 $(p+'-anio').textContent=S.anio===null?(d===h?String(d):d+'-'+h):(S.acum?d+'-'+S.anio:S.anio);
 $(p+'-play').textContent=S.timer?'Pausa':'Reproducir';hitosSlider(p+'-hitos',d,h);}
function leyendaEscala(p,mx,un){const r=rampa();
 $(p+'-grad').style.background=`linear-gradient(90deg,${[0,.25,.5,.75,1].map(t=>r(.12+.88*t)).join(',')})`;
 $(p+'-grad-et').innerHTML=`<span>0</span><span>${fmt(mx/4)}</span><span>${fmt(mx)} ${un}</span>`;}
function topLados(val,sel,id){const top=Object.entries(val).filter(x=>x[1]>0).sort((a,b)=>b[1]-a[1]).slice(0,8);
 barras($(id),top.map(([k,v])=>[nombreIso(k),v,`data-iso="${k}"`,k===sel]));
 $(id).querySelectorAll('[data-iso]').forEach(e=>e.onclick=()=>filtro('f-iso',e.dataset.iso));}
function dMapa(){
 const fm=filtradas(['c','r']),dm=datosMapa(fm),val=valoresDe(dm,MAPA),mx=maximoDe(dm,MAPA),un=unidad();
 controlesAnio(MAPA,'m');leyendaEscala('m',mx,un);
 const sinN=Object.entries(dm.sin).sort((a,b)=>b[1]-a[1]);
 $('m-sinpais').textContent=dm.sinTot>0?`Sin país: ${fmt(dm.sinTot)} ${un} en ${fmt(dm.sinN)} operaciones asignadas a una región, a varios países o a un nombre que no es un país único (principales: ${sinN.slice(0,4).map(x=>x[0]).join(', ')}). En un año o acumulado, este monto no se divide por año.`:'';
 if(VISTA==='globo')dGlobo(fm,val,mx);else dPlano(val,mx,un);
}
function dPlano(val,mx,un){
 const el=$('mapa'),r=rampa();
 const sq=v=>Math.sqrt(Math.max(0,v)/mx);
 // Los países con monto empiezan en 12% de la rampa para no confundirse con "sin dato".
 const color=k=>val[k]>0?r(0.12+0.88*sq(val[k])):css('--nodata');
 const sel=$('f-iso').value;
 const tip=k=>`${nombreIso(k)} · ${(GEO[k]||{}).z?ZON[GEO[k].z]:''}\n${val[k]>0?fmt(val[k])+' '+un:'Sin monto en este período'}`;
 if(ATLAS_ERR||!D3){if(!el.firstChild)sinD3(el)}
 else if(!ATLAS){el.innerHTML='<p class="nota">Cargando el mapa...</p>'}
 else{
  const w=ancho(el);
  if(!el.querySelector('svg')||MAPA.svgW!==w){
   const proj=d3.geoNaturalEarth1().fitWidth(w,{type:'Sphere'}),path=d3.geoPath(proj),hh=Math.ceil(path.bounds({type:'Sphere'})[1][1]);
   const gk=f=>f.id!==undefined?String(f.id).padStart(3,'0'):f.properties.name;
   el.innerHTML=`<svg viewBox="0 0 ${w} ${hh}" role="img" aria-label="Mapa del monto aprobado por país"><path d="${path({type:'Sphere'})}" fill="#f4f7fb" stroke="#d3dce6" stroke-width=".8" style="pointer-events:none"/><path d="${path(d3.geoGraticule10())}" fill="none" stroke="#e3e9f0" stroke-width=".5" style="pointer-events:none"/>`+
    ATLAS.filter(f=>f.properties.name!=='Antarctica').map(f=>{const k=NUM[gk(f)];return `<path d="${path(f)}" data-k="${k||''}" fill="${css('--nodata')}"/>`}).join('')+'</svg>';
   MAPA.svgW=w;
   el.querySelectorAll('path[data-k]').forEach(p=>{const k=p.dataset.k;if(k){p.onclick=()=>filtro('f-iso',k);p.onmouseenter=()=>{if(!p.classList.contains('sel'))d3.select(p).raise();const s=el.querySelector('path.sel');if(s)d3.select(s).raise()}}});
   MAPA.primera=true;
  }
  const dur=MAPA.primera?0:(MAPA.timer?1000:550);MAPA.primera=false;
  el.querySelectorAll('path[data-k]').forEach(p=>{const k=p.dataset.k;if(!k)return;
   p.setAttribute('data-tip',tip(k));p.classList.toggle('sel',k===sel);
   if(dur)d3.select(p).transition().duration(dur).ease(MAPA.timer?d3.easeLinear:d3.easeCubicOut).attr('fill',color(k));else p.setAttribute('fill',color(k));});
  const s=el.querySelector('path.sel');if(s)d3.select(s).raise();
 }
 topLados(val,sel,'m-top');
 const zs={};Object.entries(val).forEach(([k,v])=>{const z=(GEO[k]||{}).z;if(z)zs[z]=(zs[z]||0)+v});
 const tz=Object.values(zs).reduce((a,b)=>a+b,0)||1;
 barras($('m-zonas'),Object.entries(zs).sort((a,b)=>b[1]-a[1]).map(([z,v])=>[ZON[z]+' ('+pct(100*v/tz)+')',v,`data-zona="${z}"`,z===$('f-zona').value]));
 $('m-zonas').querySelectorAll('[data-zona]').forEach(e=>e.onclick=()=>filtro('f-zona',e.dataset.zona));
}
const NUM={};Object.entries(GEO).forEach(([k,g])=>{NUM[g.n]=k});
$('m-slider').addEventListener('input',()=>{parar(MAPA);MAPA.anio=+$('m-slider').value;dMapa()});
$('m-todo').onclick=()=>{parar(MAPA);MAPA.anio=null;dMapa()};
$('m-acum').addEventListener('input',()=>{MAPA.acum=$('m-acum').checked;dMapa()});
$('m-play').onclick=()=>jugar(MAPA,$('m-play'),dMapa,VISTA==='globo'?1500:1100);

// ---- Globo: globe.gl se baja recién al elegir la vista Globo. Solo se recolorea y se reescala; la geometría no se rearma.
const GL={globo:null,feats:null,cent:{},amp:{},polis:{},po:null,pt:null,cur:{},ext:{},extT:{},hover:null,pausado:false,visible:true,ult:Date.now(),
 selPrev:'',zonaPrev:'',cargando:false,fallo:false,claveHist:'',arcT:0,rafR:0,idle:0};
const ALT_MAX=.06,OCEANO='#dbe5ee',INICIO={lat:15,lng:-30,alt:1.95};
const ZVIEW={LAC:[-15,-65,2.6],ECA:[48,40,2.3],EAP:[10,115,2.5],SAS:[22,80,2.2],MNA:[28,30,2.3],SSA:[0,20,2.4]};
const gr=v=>grande(v)+($('f-usd').value==='k'?' de 2025':'');
const idDe=f=>{const p=f.properties,k=p.ISO_A3!=='-99'?p.ISO_A3:p.ISO_A3_EH!=='-99'?p.ISO_A3_EH:p.ADM0_A3;return k==='KOS'?'XKX':k};
const hayWebGL=()=>{try{const c=document.createElement('canvas');return !!(c.getContext('webgl2')||c.getContext('webgl'))}catch(e){return false}};
const cargarScript=([src,sri])=>new Promise((ok,ko)=>{const s=document.createElement('script');s.src=src;s.integrity=sri;s.crossOrigin='anonymous';
 s.onload=ok;s.onerror=()=>ko(new Error('No se pudo cargar '+src));document.head.appendChild(s)});
let LUT=null;
function colorW(w){if(!LUT){const r=rampa(),nd=d3.rgb(css('--nodata'));LUT={n:[nd.r/255,nd.g/255,nd.b/255],r:Array.from({length:65},(_,k)=>{const c=d3.rgb(r(k/64));return [c.r/255,c.g/255,c.b/255]})}}
 if(w<=0)return LUT.n;const a=LUT.r[Math.round(Math.min(1,w)*64)];if(w>=.12)return a;const t=w/.12;return LUT.n.map((x,k)=>x+(a[k]-x)*t)}
// Centroide ponderado por área del anillo más grande; si cae fuera del país (islas, medialunas), el punto interior más cercano de una grilla.
function dentro(x,y,a){let c=false;for(let k=0,j=a.length-1;k<a.length;j=k++){const [xi,yi]=a[k],[xj,yj]=a[j];if((yi>y)!==(yj>y)&&x<(xj-xi)*(y-yi)/(yj-yi)+xi)c=!c}return c}
function centroides(){
 for(const f of GL.feats){const iso=idDe(f),g=f.geometry;GL.polis[iso]=true;
  const anillos=g.type==='Polygon'?[g.coordinates[0]]:g.coordinates.map(p=>p[0]);
  let mejor=null,area=-1,bx0=0,bx1=0,by0=0,by1=0;
  for(const a of anillos){let x0=181,x1=-181,y0=91,y1=-91;
   for(const [x,y] of a){if(x<x0)x0=x;if(x>x1)x1=x;if(y<y0)y0=y;if(y>y1)y1=y}
   const ar=(x1-x0)*(y1-y0);if(ar>area){area=ar;mejor=a;bx0=x0;bx1=x1;by0=y0;by1=y1}}
  let A=0,cx=0,cy=0;
  for(let k=0,j=mejor.length-1;k<mejor.length;j=k++){const [xi,yi]=mejor[k],[xj,yj]=mejor[j],q=xj*yi-xi*yj;A+=q;cx+=(xj+xi)*q;cy+=(yj+yi)*q}
  let x=cx/(3*A),y=cy/(3*A);
  if(!A||!dentro(x,y,mejor)){let md=Infinity,bx=(bx0+bx1)/2,by=(by0+by1)/2;
   for(let a=1;a<24;a++)for(let b=1;b<24;b++){const gx=bx0+(bx1-bx0)*a/24,gy=by0+(by1-by0)*b/24;if(!dentro(gx,gy,mejor))continue;
    const d=(gx-(bx0+bx1)/2)**2+(gy-(by0+by1)/2)**2;if(d<md){md=d;bx=gx;by=gy}}
   x=bx;y=by}
  GL.cent[iso]=[y,x];GL.amp[iso]=Math.max(bx1-bx0,by1-by0)}
 for(const k in CEXTRA)GL.cent[k]=CEXTRA[k];}
const chicos=()=>Object.keys(GEO).filter(k=>!(k in GL.polis)&&GL.cent[k]);
const esSel=iso=>$('f-iso').value===iso;
function etiqueta(iso){const v=GL.val&&GL.val[iso],nom=esc(nombreIso(iso));
 if(!(v>0))return `<div class="tt"><b>${nom}</b>Sin monto en este período</div>`;
 return `<div class="tt"><b>${nom}</b><span class="n">${fmt(v)} ${unidad()}</span><br><span class="nota">Un clic lo usa como filtro</span></div>`}
// Objetos de three-globe: un grupo por polígono; se clonan los materiales para colorear cada país por separado.
function indexarObjetos(){GL.po={};GL.pt={};const vistos=new Set();
 GL.globo.scene().traverse(o=>{if(vistos.has(o))return;
  if(o.__globeObjType==='polygon'&&o.__data){vistos.add(o);
   const malla=o.children.find(c=>c.isMesh),lin=o.children.find(c=>c.isLineSegments);if(!malla)return;
   const mats=(Array.isArray(malla.material)?malla.material:[malla.material]).map(m=>m.clone());
   malla.material=Array.isArray(malla.material)?mats:mats[0];
   const cap=mats.find(m=>m.color.getHexString()==='eceff1')||mats[mats.length-1];
   let linea={color:{set(){}}};if(lin){lin.material=lin.material.clone();linea=lin.material}
   (GL.po[idDe(o.__data.data)]||=[]).push({g:o,cap,linea})}
  else if(o.__globeObjType==='point'&&o.__data){vistos.add(o);o.material=o.material.clone();GL.pt[o.__data.iso]=o.material}})}
function aplicarEscena(contornos){if(!GL.po)return;
 for(const iso in GL.po){const w=GL.cur[iso]||0,c=colorW(w),e=GL.ext[iso]||0,s=(1+.004+.05*w+e)/(1+ALT_MAX);
  for(const o of GL.po[iso]){o.g.scale.setScalar(s);o.cap.color.setRGB(c[0],c[1],c[2],'srgb');
   if(contornos)o.linea.color.set(esSel(iso)?'#111c26':GL.hover===iso?'#0e5aa7':'#ffffff')}}
 for(const iso in GL.pt){const c=colorW(GL.cur[iso]||0);GL.pt[iso].color.setRGB(c[0],c[1],c[2],'srgb')}}
function relieve(iso,v){if(!iso)return;GL.extT[iso]=v;if(!GL.rafR)GL.rafR=requestAnimationFrame(pasoRelieve)}
function pasoRelieve(){GL.rafR=0;let mas=false;
 for(const k in GL.extT){const a=GL.ext[k]||0,b=GL.extT[k],n=REDUCE||Math.abs(b-a)<.0004?b:a+(b-a)*.28;GL.ext[k]=n;if(n!==b)mas=true;else if(b===0)delete GL.extT[k]}
 aplicarEscena(false);if(mas)GL.rafR=requestAnimationFrame(pasoRelieve)}
function tweenEscena(dur,ease){const el=$('globo'),ini={};for(const iso in GL.tgt)ini[iso]=GL.cur[iso]||0;
 animar(el,'esc',dur,t=>{for(const iso in GL.tgt)GL.cur[iso]=ini[iso]+(GL.tgt[iso]-ini[iso])*t;aplicarEscena(false)},ease)}
function volarA(lat,lng,alt){const g=GL.globo;if(!g)return;g.controls().autoRotate=false;
 const p0=g.pointOfView(),dl=((lng-p0.lng+540)%360)-180,dist=Math.hypot(lat-p0.lat,dl),hump=Math.min(1.1,dist/120),
 dur=REDUCE?0:Math.round(1000*Math.min(2.3,Math.max(.9,.7+dist/90)));
 animar($('globo'),'cam',dur,t=>{g.pointOfView({lat:p0.lat+(lat-p0.lat)*t,lng:p0.lng+dl*t,altitude:p0.altitude+(alt-p0.altitude)*t+hump*Math.sin(Math.PI*t)},0)},d3.easeCubicInOut);
 actividad()}
function volverInicio(){volarA(INICIO.lat,INICIO.lng,INICIO.alt)}
function hoverIso(iso){if(iso===GL.hover)return;const antes=GL.hover;GL.hover=iso;
 if(antes&&!esSel(antes))relieve(antes,0);if(iso)relieve(iso,.008);aplicarEscena(true)}
function arcosDatos(f){if(!$('g-arcos').checked)return [];
 const por={};f.forEach(r=>{const k=r[i.iso3];if(!k||!GL.cent[k]||!enVent(r[i.anio_aprobacion],MAPA))return;const g=cod(r[i.banco_grupo]);(por[g]=por[g]||{})[k]=(por[g][k]||0)+monto(r)});
 const un=Object.keys(por).length===1,out=[];
 Object.entries(por).forEach(([g,o])=>{const s=SEDE[g];if(!s)return;const l=Object.entries(o).sort((a,b)=>b[1]-a[1]),mx=l.length?l[0][1]:1;
  l.slice(0,un?24:7).forEach(([k,v])=>out.push({g,iso:k,sl:s[0],sg:s[1],el:GL.cent[k][0],eg:GL.cent[k][1],w:.12+.5*Math.sqrt(v/mx)}))});
 return out}
function actualizarArcos(f){clearTimeout(GL.arcT);
 GL.arcT=setTimeout(()=>{if(!GL.globo)return;const arcos=arcosDatos(f),vistos={};GL.globo.arcsData(arcos);
  // Un anillo marca dónde termina cada arco, en los destinos más grandes de cada grupo.
  GL.globo.ringsData(arcos.filter(a=>(vistos[a.g]=(vistos[a.g]||0)+1)<=(Object.keys(vistos).length===1?8:2)));actividad()},120)}
function pausarGlobo(){if(GL.globo&&!GL.pausado){GL.globo.pauseAnimation();GL.pausado=true}}
function reanudarGlobo(){if(GL.globo&&GL.pausado&&!document.hidden&&enGlobo()&&GL.visible){GL.globo.resumeAnimation();GL.pausado=false}}
function actividad(){GL.ult=Date.now();reanudarGlobo()}
document.addEventListener('visibilitychange',()=>{if(document.hidden)pausarGlobo();else actividad()});
async function montarGlobo(){
 const el=$('globo'),est=$('g-estado');GL.cargando=true;est.textContent='Cargando el globo...';est.style.display='block';
 try{
  if(!hayWebGL())throw new Error('webgl');
  await cargarScript(U_GLOBE);
  const r=await fetch(U_GEOJSON);if(!r.ok)throw new Error('geo');
  GL.feats=(await r.json()).features.filter(f=>f.properties.ADM0_A3!=='ATA');centroides();
  const g=GL.globo=Globe({rendererConfig:{antialias:true,powerPreference:'high-performance'}})(el)
   .width(el.clientWidth).height(el.clientHeight).backgroundColor('rgba(255,255,255,0)').globeImageUrl(null)
   .showGraticules(true).showAtmosphere(true).atmosphereColor('#b9c8d8').atmosphereAltitude(.07)
   .polygonsData(GL.feats).polygonsTransitionDuration(0).polygonAltitude(ALT_MAX)
   .polygonCapColor(()=>'#eceff1').polygonSideColor(()=>'rgba(120,140,165,.45)').polygonStrokeColor(()=>'#ffffff')
   .polygonLabel(f=>etiqueta(idDe(f))).onPolygonHover(f=>hoverIso(f?idDe(f):null))
   .onPolygonClick(f=>{const k=idDe(f);if(GEO[k])filtro('f-iso',k)})
   .pointsData(chicos().map(k=>({iso:k}))).pointRadius(.5).pointResolution(8).pointAltitude(.012).pointColor(()=>'#eceff1')
   .pointLat(d=>GL.cent[d.iso][0]).pointLng(d=>GL.cent[d.iso][1]).pointLabel(d=>etiqueta(d.iso)).onPointClick(d=>filtro('f-iso',d.iso))
   .arcStartLat('sl').arcStartLng('sg').arcEndLat('el').arcEndLng('eg').arcStroke('w')
   .arcColor(d=>[colG(d.g)+'d0',colG(d.g)+'50']).arcAltitudeAutoScale(.3)
   .ringLat('el').ringLng('eg').ringMaxRadius(2.2).ringPropagationSpeed(REDUCE?0:1.1).ringRepeatPeriod(2200)
   .ringColor(d=>{const c=[1,3,5].map(k=>parseInt(colG(d.g).slice(k,k+2),16));return t=>`rgba(${c[0]},${c[1]},${c[2]},${(1-t)*.8})`})
   .arcDashLength(.45).arcDashGap(.3).arcDashInitialGap(()=>Math.random()).arcDashAnimateTime(REDUCE?0:3600).arcsTransitionDuration(0);
  g.renderer().setPixelRatio(Math.min(window.devicePixelRatio||1,2));
  // Esfera plana y luz pareja: el color se lee igual en todo el globo.
  const mat=g.globeMaterial();mat.color.set('#000000');mat.emissive.set(OCEANO);mat.specular.set('#000000');mat.shininess=0;
  const luces=g.lights().filter(l=>l.isAmbientLight||l.isDirectionalLight);luces.forEach(l=>{l.intensity=l.isAmbientLight?Math.PI:0});g.lights(luces);
  const c=g.controls();c.autoRotate=!REDUCE;c.autoRotateSpeed=.4;c.enableDamping=true;c.dampingFactor=.08;c.minDistance=130;c.maxDistance=450;
  g.pointOfView({lat:INICIO.lat,lng:INICIO.lng,altitude:3.6},0);
  for(const ev of ['pointerdown','wheel','keydown','touchstart'])el.addEventListener(ev,()=>{c.autoRotate=false;actividad()},{passive:true});
  new ResizeObserver(()=>{if(GL.globo&&el.clientWidth)GL.globo.width(el.clientWidth).height(el.clientHeight)}).observe(el);
  new IntersectionObserver(es=>{GL.visible=es[0].isIntersecting;if(GL.visible)actividad();else pausarGlobo()}).observe($('g-caja'));
  await new Promise(ok=>{let n=0;const t=()=>{indexarObjetos();(Object.keys(GL.po).length>100||n++>120)?ok():requestAnimationFrame(t)};t()});
  clearInterval(GL.idle);GL.idle=setInterval(()=>{if(!GL.globo||!enGlobo())return;if(document.hidden)return pausarGlobo();
   if(!MAPA.timer&&Date.now()-GL.ult>20000){g.controls().autoRotate=false;setTimeout(pausarGlobo,600)}},2000);
  est.style.display='none';GL.cargando=false;GL.selPrev='';GL.zonaPrev='';
  if(!$('f-iso').value&&!$('f-zona').value)volverInicio();
  dMapa();
 }catch(e){GL.cargando=false;GL.fallo=true;GL.globo=null;
  est.textContent=e.message==='webgl'?'Este navegador no puede dibujar el globo. Usá la vista plana.':'No se pudo cargar el globo (hace falta conexión). Usá la vista plana.';est.style.display='block'}}
// Historias: hechos calculados con los filtros, cada una lleva a una vista.
function historias(f){const cp=f.filter(r=>r[i.iso3]);if(!cp.length)return [];
 const out=[],por={},tot=f.reduce((a,r)=>a+monto(r),0)/1e6,d=+$('f-desde').value,h=+$('f-hasta').value;
 cp.forEach(r=>{por[r[i.iso3]]=(por[r[i.iso3]]||0)+monto(r)/1e6});
 const t1=Object.entries(por).sort((a,b)=>b[1]-a[1])[0];
 out.push({etq:'Mayor destino',tit:nombreIso(t1[0]),det:`${gr(t1[1])}, ${pct(100*t1[1]/tot)} del monto aprobado.`,ir:()=>{MAPA.anio=null;fijar('f-iso',t1[0])}});
 if(h-d>=5){let mej=null;GR.forEach(g=>{const rs=f.filter(r=>cod(r[i.banco_grupo])===g),s=(a,b)=>rs.filter(r=>r[i.anio_aprobacion]>=a&&r[i.anio_aprobacion]<=b).reduce((q,r)=>q+monto(r),0)/1e6;
   const a=s(d,d+2),b=s(h-2,h);if(a>=300&&b/a>1&&(!mej||b/a>mej.r))mej={g,r:b/a}});
  if(mej)out.push({etq:'Mayor crecimiento',tit:mej.g,det:`${nom(mej.g)} aprobó ${mej.r.toLocaleString('es-AR',{maximumFractionDigits:1})} veces más en ${h-2}-${h} que en ${d}-${d+2}.`,
   ir:()=>{$('f-grupo').value=mej.g;$('f-grupo').dispatchEvent(new Event('input'))}})}
 const lac=cp.filter(r=>r[i.zona]==='LAC').reduce((a,r)=>a+monto(r),0)/1e6,tc=cp.reduce((a,r)=>a+monto(r),0)/1e6;
 if(lac>0)out.push({etq:'América Latina y el Caribe',tit:pct(100*lac/tc),det:`${gr(lac)} del monto con país.`,ir:()=>fijar('f-zona','LAC')});
 const pa={};f.forEach(r=>{pa[r[i.anio_aprobacion]]=(pa[r[i.anio_aprobacion]]||0)+monto(r)/1e6});
 const y=Object.entries(pa).sort((a,b)=>b[1]-a[1])[0];
 if(h>d)out.push({etq:'Año con más monto',tit:y[0],det:`${gr(y[1])} aprobados en un año.`,ir:()=>{parar(MAPA);MAPA.anio=+y[0];MAPA.acum=false;dMapa()}});
 return out}
function pintarHistorias(f){const hs=historias(f),clave=hs.map(x=>x.tit+x.det).join('|');if(clave===GL.claveHist)return;GL.claveHist=clave;
 const c=$('g-hist');c.innerHTML=hs.map((x,k)=>`<button type="button" data-h="${k}"><span class="etq">${esc(x.etq)}</span><span class="tit">${esc(x.tit)}</span><span class="det">${esc(x.det)}</span></button>`).join('');
 c.onclick=e=>{const b=e.target.closest('button');if(b){parar(MAPA);actividad();hs[+b.dataset.h].ir()}}}
function sparkline(porAnio,ks,actual){const W=300,H=64,m=Math.max(1,...ks.map(a=>porAnio[a]||0)),bw=W/ks.length;
 const pico=ks.find(a=>(porAnio[a]||0)===m);
 return `<svg viewBox="0 0 ${W} ${H+14}" width="100%" role="img" aria-label="Monto aprobado por año">`+ks.map((a,k)=>{const v=porAnio[a]||0,hh=Math.max(v>0?2:0,(H-6)*v/m);
  return `<rect x="${k*bw+2}" y="${H-hh}" width="${Math.max(1,bw-4)}" height="${hh}" fill="${actual(a)?css('--seq1'):'#c3cad2'}" data-tip="${a}\n${fmt(v)} ${unidad()}"/>`}).join('')+
  `<text x="2" y="${H+12}" fill="${css('--s')}" font-size="10">${ks[0]}</text><text x="${W-2}" y="${H+12}" fill="${css('--s')}" font-size="10" text-anchor="end">${ks[ks.length-1]}</text></svg>`+
  (m>0?`<p class="nota">Año más alto: ${pico}, ${fmt(m)} ${unidad()}.</p>`:'')}
function panelGlobo(f){
 const sel=$('f-iso').value,zona=$('f-zona').value,cp=f.filter(r=>r[i.iso3]),d=+$('f-desde').value,h=+$('f-hasta').value,ks=anios.filter(a=>a>=d&&a<=h);
 if(!$('gp-cab')){$('g-panel').innerHTML='<div id="gp-cab"></div><h3>Por grupo</h3><div class="barras lado" id="gp-grupos"></div><h3>Año por año</h3><div id="gp-spark"></div><h3>Operaciones más grandes</h3><div id="gp-ops"></div><div id="gp-lista"></div>'}
 const filas=sel?cp.filter(r=>r[i.iso3]===sel):zona?cp.filter(r=>r[i.zona]===zona):cp;
 const tit=sel?nombreIso(sel):zona?ZON[zona]:'Todos los países',sub=sel?(ZON[(GEO[sel]||{}).z]||''):zona?'Zona del mundo':'Operaciones con país',
 w=filas.filter(r=>enVent(r[i.anio_aprobacion],MAPA)),tot=w.reduce((a,r)=>a+monto(r),0)/1e6,
 mundo=cp.filter(r=>enVent(r[i.anio_aprobacion],MAPA)).reduce((a,r)=>a+monto(r),0)/1e6,
 ven=MAPA.anio===null?(d===h?String(d):d+' a '+h):MAPA.acum?d+' a '+MAPA.anio:String(MAPA.anio);
 $('gp-cab').innerHTML=`<div class="pt">${esc(tit)}</div><p class="nota">${esc(sub)}${sel||zona?' · <a href="#" id="gp-volver">Quitar</a>':''}</p>`+
  (tot>0?`<p class="gran">${gr(tot)}</p><p class="nota">${esc(ven)}: ${fmt(w.length)} operaciones${sel||zona?', '+pct(100*tot/(mundo||1))+' del monto con país':''}.</p>`:`<p class="nota">Sin operaciones en ${esc(ven)} con estos filtros.</p>`);
 const v=$('gp-volver');if(v)v.onclick=e=>{e.preventDefault();$('f-iso').value='';$('f-zona').value='';dibujar()};
 const gs={};w.forEach(r=>{const g=cod(r[i.banco_grupo]);gs[g]=(gs[g]||0)+monto(r)/1e6});
 barras($('gp-grupos'),Object.entries(gs).sort((a,b)=>b[1]-a[1]).map(([g,x])=>[nom(g),x,`data-grp="${g}"`,false,colG(g)]));
 const pa={};filas.forEach(r=>{pa[r[i.anio_aprobacion]]=(pa[r[i.anio_aprobacion]]||0)+monto(r)/1e6});
 $('gp-spark').innerHTML=ks.length?sparkline(pa,ks,a=>enVent(a,MAPA)&&MAPA.anio!==null):'';
 const top=[...w].sort((a,b)=>monto(b)-monto(a)).slice(0,5);
 $('gp-ops').innerHTML=top.map(r=>{const u=urlSegura(r[i.url_proyecto]),n=esc(r[i.nombre]||'(sin nombre)');
  return `<div class="op"><b>${u?`<a href="${u}" target="_blank" rel="noopener">${n}</a>`:n}</b><br><span class="nota"><i class="dot" style="background:${colG(r[i.banco_grupo])}"></i> ${esc(r[i.institucion])} · ${r[i.anio_aprobacion]} · ${fmt(monto(r)/1e6)} ${unidad()}</span></div>`}).join('')||'<p class="nota">Sin operaciones.</p>';
 const lista=$('gp-lista');
 if(sel){lista.innerHTML=''}
 else{const pc={};w.forEach(r=>{pc[r[i.iso3]]=(pc[r[i.iso3]]||0)+monto(r)/1e6});
  lista.innerHTML='<h3>Países con más monto</h3><div class="barras lado" id="gp-paises"></div>'+(zona?'':'<h3>Zonas</h3><div class="barras lado" id="gp-zonas"></div>');
  barras($('gp-paises'),Object.entries(pc).sort((a,b)=>b[1]-a[1]).slice(0,8).map(([k,x])=>[nombreIso(k),x,`data-iso="${k}"`,false]));
  $('gp-paises').querySelectorAll('[data-iso]').forEach(e=>e.onclick=()=>filtro('f-iso',e.dataset.iso));
  if(!zona){const zs={};w.forEach(r=>{const z=r[i.zona];if(z)zs[z]=(zs[z]||0)+monto(r)/1e6});
   barras($('gp-zonas'),Object.entries(zs).sort((a,b)=>b[1]-a[1]).map(([z,x])=>[ZON[z],x,`data-zona="${z}"`,false]));
   $('gp-zonas').querySelectorAll('[data-zona]').forEach(e=>e.onclick=()=>filtro('f-zona',e.dataset.zona))}}}
function dGlobo(fm,val,mx){
 GL.val=val;panelGlobo(fm);pintarHistorias(fm);
 if(!GL.globo){if(!GL.cargando&&!GL.fallo)montarGlobo();return}
 actividad();
 GL.tgt={};Object.keys(GEO).forEach(k=>{GL.tgt[k]=val[k]>0?.12+.88*Math.sqrt(val[k]/mx):0});
 const primera=!GL.listo;GL.listo=true;
 tweenEscena(primera?0:MAPA.timer?1000:650,MAPA.timer?d3.easeLinear:d3.easeCubicInOut);
 actualizarArcos(fm);
 const sel=$('f-iso').value,zona=$('f-zona').value;
 if(sel!==GL.selPrev){if(GL.selPrev)relieve(GL.selPrev,GL.hover===GL.selPrev?.008:0);if(sel)relieve(sel,.014);
  const c=GL.cent[sel];if(sel&&c)volarA(c[0],c[1],Math.min(2,Math.max(.7,.45+(GL.amp[sel]||8)/28)));else if(!sel&&!zona)volverInicio();
  GL.selPrev=sel;aplicarEscena(true)}
 if(zona!==GL.zonaPrev){GL.zonaPrev=zona;if(zona&&!sel){const v=ZVIEW[zona];volarA(v[0],v[1],v[2])}else if(!zona&&!sel)volverInicio()}}
$('g-arcos').addEventListener('input',()=>dMapa());
// Atajos solo en la vista Globo: Espacio reproduce, Esc saca el país o la zona.
document.addEventListener('keydown',e=>{if(!enGlobo()||FB.on||TOUR.on)return;const t=e.target&&e.target.tagName;if(t==='INPUT'||t==='SELECT'||t==='TEXTAREA'||t==='BUTTON'||t==='A')return;
 if(e.key==='Escape'){if($('f-iso').value||$('f-zona').value){$('f-iso').value='';$('f-zona').value='';dibujar()}}
 else if(e.key===' '||e.code==='Space'){e.preventDefault();jugar(MAPA,$('m-play'),dMapa,1500)}});

// ---- Composición: treemap grupo > institución > sector o zona, matriz grupo por zona y porción no soberana.
function dComp(f){
 const el=$('tm'),modo=document.querySelector('input[name=tm-modo]:checked').value;
 if(!D3){sinD3(el);return}
 const w=ancho(el),h=600,un=unidad();el.style.height=h+'px';
 const agg={},etq=r=>modo==='sector'?(r[i.sector]||'sin dato').replace(/^FY\d{2} - /,''):(ZON[r[i.zona]]||'Sin país (agregado regional)');
 f.forEach(r=>{const v=monto(r)/1e6;if(!(v>0))return;const g=r[i.banco_grupo],s=r[i.institucion],k=etq(r);
  const a=((agg[g]=agg[g]||{})[s]=agg[g][s]||{});a[k]=(a[k]||0)+v;});
 const kids=Object.entries(agg).map(([g,ins])=>({name:g,children:Object.entries(ins).map(([s,ls])=>{
  let es=Object.entries(ls).sort((a,b)=>b[1]-a[1]);
  if(modo==='sector'&&es.length>12){const r=es.slice(12).reduce((q,x)=>q+x[1],0);es=es.slice(0,12).concat([['Otros sectores',r]])}
  return {name:s,children:es.map(([n,v])=>({name:n,v}))}})}));
 if(!kids.length){el.innerHTML='<p class="nota">Sin datos</p>';}
 else{
  if(!el.querySelector('div'))el.innerHTML='';
  const root=d3.hierarchy({name:'',children:kids}).sum(d=>d.v||0).sort((a,b)=>b.value-a.value);
  d3.treemap().size([w,h]).paddingInner(2).paddingOuter(2).paddingTop(d=>d.depth===1?22:d.depth===2?16:2).round(true)(root);
  const tot=root.value,viejos=new Map([...el.children].filter(c=>c.dataset.key&&!c.dataset.out).map(c=>[c.dataset.key,c])),vistos=new Set(),nuevos=[];
  // Los rectángulos se reusan por su ruta: al cambiar un filtro se desplazan y cambian de tamaño en vez de reaparecer.
  root.descendants().filter(d=>d.depth>0).forEach(d=>{
   const ruta=d.ancestors().reverse().slice(1).map(a=>a.data.name),key=ruta.join('\u0001');
   const g=ruta[0],c=colG(g),w0=d.x1-d.x0,h0=d.y1-d.y0;
   let e=viejos.get(key);if(!e){e=document.createElement('div');e.dataset.key=key;e.style.opacity=0;nuevos.push(e);el.appendChild(e)}
   vistos.add(key);
   e.className=d.depth===3?'l':'';e.dataset.d=d.depth;e.dataset.g=g;e.dataset.s=d.depth===2?d.data.name:'';e.dataset.grp=cod(g);
   e.dataset.tip=ruta.map((n,j)=>j===0?nom(n):n).join(' > ')+'\n'+fmt(d.value)+' '+un+' · '+pct(100*d.value/tot)+' del total';
   const txt=d.depth===1?`${esc(nom(g))} · ${pct(100*d.value/tot)}`:d.depth===2?esc(d.data.name):`${esc(d.data.name)}${h0>32?'<br>'+fmt(d.value):''}`;
   const ver=d.depth===3?(w0>46&&h0>24):w0>34&&h0>(d.depth===1?20:15);
   const st=e.style;st.left=d.x0+'px';st.top=d.y0+'px';st.width=w0+'px';st.height=h0+'px';
   st.background=d.depth===1?c:d.depth===2?`color-mix(in srgb,${c} 55%,#fff)`:`color-mix(in srgb,${c} 26%,#fff)`;
   st.color=d.depth===1?tinta(c):'var(--t)';st.fontWeight=d.depth<3?'650':'400';
   e.innerHTML=ver?txt:'';});
  viejos.forEach((e,k)=>{if(!vistos.has(k)){e.dataset.out=1;e.style.opacity=0;e.style.pointerEvents='none';setTimeout(()=>e.remove(),450)}});
  requestAnimationFrame(()=>requestAnimationFrame(()=>nuevos.forEach(e=>{e.style.opacity=1})));
 }
 // Matriz grupo por zona: la porción del monto de cada grupo que va a cada zona.
 const zs=Object.keys(ZON),m={};
 f.forEach(r=>{const v=monto(r)/1e6;if(!(v>0))return;const g=r[i.banco_grupo],z=r[i.zona]||'-';(m[g]=m[g]||{})[z]=((m[g]||{})[z]||0)+v});
 $('h-cab').innerHTML='<tr><th>Grupo</th>'+zs.map(z=>`<th class="n">${ZON[z]}</th>`).join('')+'<th class="n">Sin país</th><th class="n">Total, '+un+'</th></tr>';
 const ramp=d3.interpolateLab(css('--seq0'),css('--seq1'));
 $('h-cuerpo').innerHTML=GR.concat(Object.keys(m).filter(g=>!GR.includes(g))).filter(g=>m[g]).map(g=>{const t=Object.values(m[g]).reduce((a,b)=>a+b,0);
  const cel=z=>{const v=(m[g][z]||0)/t,c=ramp(Math.sqrt(v)*.95);return `<td class="v" style="background:${c};color:${v>.35?(d3.lab(c).l>60?'#111':'#fff'):'var(--t)'}" data-tip="${nom(g)} > ${z==='-'?'sin país':ZON[z]}\n${fmt(m[g][z]||0)} ${un} · ${pct(100*v)} del grupo">${v>=.0005?pct(100*v):''}</td>`};
  return `<tr data-grp="${cod(g)}"><td><i class="dot" style="background:${colG(g)};margin-right:7px"></i>${nom(g)}</td>${zs.map(cel).join('')}${cel('-')}<td class="n">${fmt(t)}</td></tr>`}).join('');
 // Una miniatura por grupo con su porción no soberana. No depende de los filtros: se arma una vez por ancho.
 const mini=$('e-mini'),clave=ancho(mini)+'|'+V.length;
 if(mini.dataset.c===clave)return;mini.dataset.c=clave;
 mini.innerHTML=VG.map(g=>{const rows=V.filter(x=>x.grupo===g).sort((a,b)=>a.anio-b.anio);const u=rows[rows.length-1];
  return `<div data-grp="${cod(g)}"><div class="nota"><i class="dot" style="background:${colG(g)};margin-right:6px"></i><b>${cod(g)}</b> ${u?pct(u.pct_no_soberana)+' en '+u.anio:''}</div><div data-g="${g}"></div></div>`}).join('');
 mini.querySelectorAll('[data-g]').forEach(c=>{const g=c.dataset.g,rows=V.filter(x=>x.grupo===g).sort((a,b)=>a.anio-b.anio);if(rows.length<1)return;
  const w=Math.max(120,c.clientWidth),h=100,m={l:28,r:8,t:6,b:18};const x=d3.scaleLinear(d3.extent(rows,r=>r.anio),[m.l,w-m.r]),y=d3.scaleLinear([0,100],[h-m.b,m.t]);
  const ln=d3.line().x(r=>x(r.anio)).y(r=>y(r.pct_no_soberana)),ar=d3.area().x(r=>x(r.anio)).y0(y(0)).y1(r=>y(r.pct_no_soberana));
  const col=colG(g);
  c.innerHTML=`<svg viewBox="0 0 ${w} ${h}" width="${w}" height="${h}">`+[0,50,100].map(t=>`<line x1="${m.l}" x2="${w-m.r}" y1="${y(t)}" y2="${y(t)}" stroke="${css('--l')}"/><text x="${m.l-5}" y="${y(t)+3.5}" text-anchor="end" font-size="10" fill="${css('--m')}">${t}</text>`).join('')+
   `<path d="${ar(rows)}" fill="${col}" opacity=".14"/><path d="${ln(rows)}" fill="none" stroke="${col}" stroke-width="2" stroke-linejoin="round"/>`+
   `<text x="${m.l}" y="${h-4}" font-size="10" fill="${css('--m')}">${rows[0].anio}</text><text x="${w-m.r}" y="${h-4}" text-anchor="end" font-size="10" fill="${css('--m')}">${rows[rows.length-1].anio}</text>`+
   rows.map(r=>`<circle cx="${x(r.anio)}" cy="${y(r.pct_no_soberana)}" r="4.5" fill="${col}" stroke="#fff" stroke-width="2" data-tip="${cod(g)} · ${r.anio}\n${pct(r.pct_no_soberana)} no soberana\n${fmt(r.no_soberana_mm)} de ${fmt(r.soberana_mm+r.no_soberana_mm)} USD M"/>`).join('')+'</svg>';});
}
$('tm').addEventListener('click',ev=>{const e=ev.target.closest('div[data-d]');if(!e||e.dataset.d==='3')return;
 $('f-grupo').value=e.dataset.g;$('f-grupo').dispatchEvent(new Event('input'));
 if(e.dataset.s){$('f-inst').value=e.dataset.s;$('f-inst').dispatchEvent(new Event('input'))}});
document.querySelectorAll('input[name=tm-modo]').forEach(e=>e.addEventListener('input',()=>dComp(FILT)));

// ---- Membrecía y concentración: una burbuja por institución, un año a la vez.
// Acomoda las etiquetas de las burbujas: a la derecha o a la izquierda, subiendo o bajando de a una línea hasta que no choquen con otra etiqueta ni con otra burbuja.
function ubicarEtiquetas(it,minX){const ocup=[],out={};
 const caja=(c,w)=>{const x0=c[2]==='start'?c[0]:c[0]-w;return [x0,c[1]-11,x0+w,c[1]+3]};
 const choca=(b,q)=>b[0]<q[2]&&b[2]>q[0]&&b[1]<q[3]&&b[3]>q[1];
 const tocaBurbuja=(b,o)=>{const nx=Math.max(b[0],Math.min(o.cx,b[2])),ny=Math.max(b[1],Math.min(o.cy,b[3]));return (nx-o.cx)**2+(ny-o.cy)**2<o.r*o.r};
 [...it].sort((a,b)=>b.r-a.r).forEach(o=>{const w=o.n.length*6.4+6,cand=[];
  for(let k=0;k<14;k++){const dy=k===0?0:(k%2?1:-1)*Math.ceil(k/2)*13;cand.push([o.cx+o.r+4,o.cy+4+dy,'start'],[o.cx-o.r-4,o.cy+4+dy,'end'])}
  const libre=c=>{const b=caja(c,w);return b[0]>=minX&&!ocup.some(q=>choca(b,q))};
  const ok=cand.find(c=>libre(c)&&!it.some(z=>z!==o&&tocaBurbuja(caja(c,w),z)))||cand.find(libre)||cand[0];
  ocup.push(caja(ok,w));out[o.n]=ok});
 return out}
function dMembre(){
 const el=$('mb');if(!D3){sinD3(el);return}
 const f=filtradas(['c','r']),d=+$('f-desde').value,h=+$('f-hasta').value,sl=$('mb-slider'),un=unidad();
 sl.min=d;sl.max=h;MB.anio=Math.min(h,Math.max(d,MB.anio===null?h:MB.anio));sl.value=MB.anio;
 $('mb-anio').textContent=MB.anio;$('b-mb-play').textContent=MB.timer?'Pausa':'Reproducir';hitosSlider('mb-hitos',d,h);
 const por={},grupo={};f.forEach(r=>{const n=r[i.institucion],a=r[i.anio_aprobacion];grupo[n]=r[i.banco_grupo];((por[n]=por[n]||{})[a]=por[n][a]||[]).push(r)});
 const insts=Object.keys(por).sort(),sinMemb=insts.filter(n=>!MEMB[n]);
 const dato=(n,a)=>{const rs=(por[n]||{})[a]||[],tot=rs.reduce((q,r)=>q+monto(r),0)/1e6,t=top5(rs),x=(MEMB[n]||{})[String(a)];
  return {tot,y:t.p,x,ok:tot>0&&t.p!==null&&x!==undefined}};
 let mx=10,mt=1;insts.forEach(n=>{for(let a=d;a<=h;a++){const q=dato(n,a);if(q.x!==undefined)mx=Math.max(mx,q.x);mt=Math.max(mt,q.tot)}});
 const w=ancho(el),hh=520,m={l:64,r:36,t:24,b:52},x=d3.scaleLinear([0,Math.ceil(mx*1.06/10)*10],[m.l,w-m.r]),y=d3.scaleLinear([0,100],[hh-m.b,m.t]);
 const rad=t=>t>0?5+40*Math.sqrt(t/mt):0,clave=w+'|'+insts.join(',')+'|'+x.domain()[1];
 if(el.dataset.c!==clave){el.dataset.c=clave;
  el.innerHTML=`<svg viewBox="0 0 ${w} ${hh}" width="${w}" height="${hh}" role="img" aria-label="Países miembros contra concentración en los cinco principales receptores">`+
   y.ticks(5).map(t=>`<line x1="${m.l}" x2="${w-m.r}" y1="${y(t)}" y2="${y(t)}" stroke="${css('--l')}"/><text x="${m.l-8}" y="${y(t)+4}" text-anchor="end" font-size="11" fill="${css('--s')}">${t}%</text>`).join('')+
   x.ticks(8).map(t=>`<line x1="${x(t)}" x2="${x(t)}" y1="${m.t}" y2="${hh-m.b}" stroke="${css('--l')}" stroke-dasharray="2 4"/><text x="${x(t)}" y="${hh-m.b+16}" text-anchor="middle" font-size="11" fill="${css('--s')}">${t}</text>`).join('')+
   `<text x="${(m.l+w-m.r)/2}" y="${hh-8}" text-anchor="middle" font-size="12" fill="${css('--s')}">Países miembros al 31 de diciembre</text>`+
   `<text transform="translate(14 ${(m.t+hh-m.b)/2}) rotate(-90)" text-anchor="middle" font-size="12" fill="${css('--s')}">Cinco principales receptores, % del monto con país</text>`+
   insts.map(n=>`<g data-n="${esc(n)}" data-grp="${cod(grupo[n])}" style="opacity:0"><line stroke="${css('--m')}" stroke-width=".8" style="opacity:0;pointer-events:none"/><circle fill="${colG(grupo[n])}" fill-opacity=".72" stroke="${colG(grupo[n])}" stroke-width="1.5" r="0"/><text font-size="11" font-weight="600" fill="${css('--t')}" style="pointer-events:none">${esc(n)}</text></g>`).join('')+'</svg>';
  el._ini=false}
 const dur=!el._ini?0:MB.timer?900:500;el._ini=true;
 const items=insts.map(n=>{const q=dato(n,MB.anio);return {n,q,cx:q.ok?x(q.x):0,cy:q.ok?y(q.y):0,r:q.ok?rad(q.tot):0}}),pos=ubicarEtiquetas(items.filter(o=>o.q.ok),m.l+2);
 const tr=s=>dur?s.transition().duration(dur).ease(MB.timer?d3.easeLinear:d3.easeCubicInOut):s;
 el.querySelectorAll('g[data-n]').forEach(g=>{const o=items.find(z=>z.n===g.dataset.n),q=o.q,c=g.querySelector('circle'),t=g.querySelector('text'),l=g.querySelector('line'),e=pos[o.n]||[o.cx+o.r+4,o.cy+4,'start'];
  g.dataset.tip=q.ok?`${o.n} · ${MB.anio}\n${fmt(q.x)} países miembros\n${pct(q.y)} en los cinco principales receptores\n${fmt(q.tot)} ${un} aprobados`:'';
  tr(d3.select(g)).style('opacity',q.ok?1:0);
  tr(d3.select(c)).attr('cx',o.cx).attr('cy',o.cy).attr('r',o.r);
  t.setAttribute('text-anchor',e[2]);tr(d3.select(t)).attr('x',e[0]).attr('y',e[1]);
  const lejos=q.ok&&Math.abs(e[1]-4-o.cy)>6;
  tr(d3.select(l)).attr('x1',o.cx).attr('y1',o.cy).attr('x2',e[0]+(e[2]==='start'?-2:2)).attr('y2',e[1]-4).style('opacity',lejos?1:0);
  g.style.pointerEvents=q.ok?'':'none'});
 $('mb-ley').innerHTML=GR.filter(g=>insts.some(n=>cod(grupo[n])===g)).map(g=>`<span data-grp="${g}"><i style="background:${colG(g)}"></i>${nom(g)}</span>`).join('');
 const sinAnio=insts.filter(n=>MEMB[n]&&!dato(n,MB.anio).ok);
 $('mb-nota').textContent=(!Object.keys(MEMB).length?'No está la tabla de membrecía en esta versión. ':'')+(sinMemb.length?`Sin dato en la tabla de membrecía: ${sinMemb.join(', ')}. `:'')+(sinAnio.length?`Sin operaciones con país en ${MB.anio}: ${sinAnio.join(', ')}.`:'');
}
$('mb-slider').addEventListener('input',()=>{parar(MB);MB.anio=+$('mb-slider').value;dMembre()});
$('b-mb-play').onclick=()=>jugar(MB,$('b-mb-play'),dMembre,1400);

// ---- Núcleo: totales, chips y hash; luego dibuja la pestaña a la vista.
function filtro(id,v){$(id).value=$(id).value===v?'':v;dibujar();}
function fijar(id,v){$(id).value=v;dibujar();}
function dibujar(){
 const f=FILT=filtradas();const total=f.reduce((a,r)=>a+monto(r),0)/1e6;
 $('k-monto-et').textContent=$('f-usd').value==='k'?'Aprobado, USD M de 2025':'Aprobado, USD M';
 numero($('k-ops'),f.length);numero($('k-monto'),total);
 numero($('k-des'),f.filter(r=>r[i.monto_desembolsado_usd]!==null).length);
 numero($('k-pais'),new Set(f.map(r=>r[i.iso3]).filter(Boolean)).size);
 chips();VISTAS=PAG;escribirHash();dibujarTab();fbRefrescar();
}
// Una ficha por cada filtro activo, con su cruz para sacarlo de un clic.
function chips(){const v=k=>$(S[k]).value,act=k=>v(k)!==DEF[k],it=[];
 if(act('g'))it.push(['Banco',nom(v('g')),['g','i']]);
 if(act('i'))it.push(['Institución',v('i'),['i']]);
 if(act('v'))it.push(['Ventanilla',v('v').replace('_',' '),['v']]);
 if(act('d')||act('h'))it.push(['Período',v('d')+' a '+v('h'),['d','h']]);
 if(act('p'))it.push(['País contiene',v('p'),['p']]);
 if(act('c'))it.push(['País',nombreIso(v('c')),['c']]);
 if(act('r'))it.push(['Zona',ZON[v('r')]||v('r'),['r']]);
 if(act('t'))it.push(['Texto',v('t'),['t']]);
 if(act('f'))it.push(['Forma',v('f'),['f']]);
 if(act('usd'))it.push(['Dólares','constantes de 2025',['usd']]);
 const el=$('chips');
 el.innerHTML=it.map(([k,t],n)=>`<span class="chip"><span class="nota">${k}</span>${esc(t)}<button data-n="${n}" aria-label="Quitar el filtro ${k}">&times;</button></span>`).join('')||'<span class="nota">Sin filtros: se muestra todo el corpus.</span>';
 el.querySelectorAll('button').forEach(b=>b.onclick=()=>{it[+b.dataset.n][2].forEach(k=>{$(S[k]).value=DEF[k]});instituciones();ficha();pararTodo();dibujar()});}
// Vista compartible: los filtros y la pestaña viajan en el hash junto a la clave k, que no se toca.
const S={g:'f-grupo',i:'f-inst',v:'f-vent',d:'f-desde',h:'f-hasta',p:'f-pais',t:'f-texto',f:'f-forma',usd:'f-usd',c:'f-iso',r:'f-zona'};
const DEF={g:'',i:'',v:'',d:String(anios[0]),h:String(anios[anios.length-1]),p:'',t:'',f:'',usd:'c',c:'',r:''};
// Un link viejo con tab=globo abre el Mapa en vista Globo; la vista viaja aparte en vista=globo.
function estadoDeHash(q){let t=q.get('tab'),v=q.get('vista')==='globo'?'globo':'plano';
 if(t==='globo'){t='mapa';v='globo'}
 return {tab:TABS.some(x=>x[0]===t)?t:'resumen',vista:v}}
function aplicarHash(){const q=new URLSearchParams(location.hash.slice(1));
 Object.entries(S).forEach(([k,id])=>{if(k==='i')instituciones();const e=$(id);let v=q.has(k)?q.get(k):DEF[k];
  if(e.tagName==='SELECT'&&![...e.options].some(o=>o.value===v))v=DEF[k];e.value=v;});
 const e=estadoDeHash(q);VISTA=e.vista;return e.tab;}
function escribirHash(){const q=new URLSearchParams(location.hash.slice(1));
 Object.entries(S).forEach(([k,id])=>{const v=$(id).value;if(v===DEF[k])q.delete(k);else q.set(k,v)});
 if(TAB==='resumen')q.delete('tab');else q.set('tab',TAB);
 if(VISTA==='globo')q.set('vista','globo');else q.delete('vista');
 const h=q.toString();try{history.replaceState(null,'',h?'#'+h:location.href.split('#')[0])}catch(e){}}
$('b-link').onclick=async()=>{escribirHash();const u=location.href,c=$('b-link-url');
 try{await navigator.clipboard.writeText(u);$('b-link-estado').textContent='Link copiado.';c.style.display='none'}
 catch(e){c.style.display='block';c.value=u;c.focus();c.select();let ok=false;try{ok=document.execCommand('copy')}catch(x){}
  $('b-link-estado').textContent=ok?'Link copiado.':'Copiá el link seleccionado (Ctrl+C o Cmd+C).'}};
window.addEventListener('hashchange',()=>{const t=aplicarHash();ficha();pestania(t,false);dibujar()});
// Cuadro con el valor de cada marca: al pasar el mouse y al tocar en el celular.
const tip=$('tip');
function ocultarTip(){tip.style.display='none';tip._k=null}
// Cuadro junto al cursor: primera línea en negrita; una línea que empieza con #color| lleva su cuadradito.
function mostrarTip(t){const L=t.dataset.tip.split('\n');tip._k=t.dataset.tip;
 tip.innerHTML='<b>'+esc(L[0])+'</b>'+L.slice(1).map(l=>{const m=/^(#[0-9a-fA-F]{6})\|(.*)$/.exec(l);return m?`<div><i style="background:${m[1]}"></i>${esc(m[2])}</div>`:`<div>${esc(l)}</div>`}).join('');
 tip.style.display='block';}
function posTip(ev){const w=tip.offsetWidth,h=tip.offsetHeight;let x=ev.clientX+16,y=ev.clientY+16;
 if(x+w>innerWidth-8)x=ev.clientX-w-16;if(y+h>innerHeight-8)y=ev.clientY-h-16;tip.style.left=Math.max(4,x)+'px';tip.style.top=Math.max(4,y)+'px'}
document.addEventListener('mousemove',e=>{const t=e.target.closest&&e.target.closest('[data-tip]');
 if(t&&t.dataset.tip){if(tip._k!==t.dataset.tip)mostrarTip(t);posTip(e)}else if(tip._k)ocultarTip()});
document.addEventListener('mouseover',e=>{if(e.target.closest&&e.target.closest('#e-area'))return;const t=e.target.closest&&e.target.closest('[data-grp]');resaltar(t?t.dataset.grp:null)});
window.addEventListener('scroll',ocultarTip,{passive:true});
// La guía queda abierta la primera vez y se recuerda cerrada.
const guia=$('guia');try{if(localStorage.getItem('explorador-guia')==='cerrada')guia.open=false}catch(e){}
guia.addEventListener('toggle',()=>{try{localStorage.setItem('explorador-guia',guia.open?'abierta':'cerrada')}catch(e){}});
// Los selectores recalculan al instante; los campos de texto esperan a que termine de teclear.
let dt;document.querySelectorAll('#barra select,#barra input').forEach(e=>{e.addEventListener('input',()=>{pararTodo();clearTimeout(dt);if(e.tagName==='INPUT')dt=setTimeout(dibujar,160);else dibujar()});});
let rz;window.addEventListener('resize',()=>{clearTimeout(rz);rz=setTimeout(()=>{if(!enGlobo())dibujarTab()},150)});
// ---- Feedback: botón flotante, modo selección y comentarios por elemento.
// Los comentarios viejos no tienen elemento: su sección se lleva al elemento más parecido al leerlos.
const SECCION_VIEJA={'General':'general','Explorador':'general','Mapa':'mapa-monto-pais','Comparación entre bancos':'resumen-comparacion','Ventanillas':'resumen-ventanilla','Países y sectores':'resumen-paises','Algo que me gustaría ver':'general'};
const ETQ_ESTADO={recibido:'Recibido',revision:'En revisión',resuelto:'✓ Resuelto',descartado:'No se aplica'};
const TIPOS=[['pregunta','Pregunta'],['mejora','Mejora'],['nuevo','Algo nuevo']];
const UI_PROPIA='#fb-ui,#tr-ui';
const TOUR={on:false,n:0,previo:null};
const FB={on:false,sel:null,hov:null,cs:[],fallo:false,vista:'menu',raf:0,pt:null};
const elemFb=t=>t&&t.closest&&!t.closest(UI_PROPIA)?t.closest('[data-fb]'):null;
const etiquetaFb=id=>{if(id==='general')return 'General';const e=document.querySelector(`[data-fb="${id}"]`);return e?e.dataset.fbLabel:''};
const elementoDe=c=>c.elemento||SECCION_VIEJA[c.seccion]||'general';
// El estado de la vista que se guarda con cada comentario: los parámetros del hash, nunca la clave k del link.
function vistaSinClave(hash){const q=new URLSearchParams(String(hash).replace(/^#/,''));q.delete('k');return q.toString().slice(0,1000)}
function estadoVistaActual(){escribirHash();return vistaSinClave(location.hash)}
function nombreGuardado(){try{return localStorage.getItem('explorador-nombre')||''}catch(e){return ''}}
function guardarNombre(n){try{localStorage.setItem('explorador-nombre',n)}catch(e){}}
function institucionGuardada(){try{return localStorage.getItem('explorador-institucion')||''}catch(e){return ''}}
function guardarInstitucion(n){try{localStorage.setItem('explorador-institucion',n)}catch(e){}}
async function cargarFb(){if(!COM)return;try{FB.cs=await COM.listar();FB.fallo=false}catch(e){FB.cs=[];FB.fallo=true}}
function hilos(){const porId={},raices=[],resp={};FB.cs.forEach(c=>{porId[c.id]=c});
 FB.cs.forEach(c=>{if(c.padre&&porId[c.padre])(resp[c.padre]=resp[c.padre]||[]).push(c);else raices.push(c)});
 Object.values(resp).forEach(l=>l.reverse());return {raices,resp}}
function cuenta(){const {raices,resp}=hilos(),n={};raices.forEach(c=>{const e=elementoDe(c);n[e]=(n[e]||0)+1+(resp[c.id]||[]).length});return n}
function comentarioHtml(c,esResp){
 const est=c.estado?`<b>${ETQ_ESTADO[c.estado]||esc(c.estado)}</b>${c.resuelto?' el '+esc(c.resuelto):''}`:'Pendiente',tipo=(TIPOS.find(t=>t[0]===c.tipo)||[])[1];
 return `<div class="fb-c${esResp?' fb-resp':''}"><span class="nota">${esc(c.autor)}${tipo?' · '+tipo:''} · ${esc(c.creado)} UTC · ${est}</span><p class="fb-t">${esc(c.texto)}</p>${c.respuesta?`<p class="nota fb-pr"><b>Respuesta:</b> ${esc(c.respuesta)}</p>`:''}${esResp?'':`<button type="button" class="fb-link" data-act="resp" data-id="${esc(c.id)}">Responder</button><div class="fb-rf" data-for="${esc(c.id)}"></div>`}</div>`}
const hiloHtml=(c,resp)=>comentarioHtml(c,false)+(resp[c.id]||[]).map(r=>comentarioHtml(r,true)).join('');
function formHtml(o){
 return `<form class="fb-form" data-padre="${esc(o.padre||'')}" autocomplete="off">${o.padre?'':`<label>Tipo</label><select class="fb-tipo">${TIPOS.map(([v,n])=>`<option value="${v}"${v===o.tipo?' selected':''}>${n}</option>`).join('')}</select>`}<label>${o.padre?'Tu respuesta':'Comentario'}</label><textarea class="fb-texto" rows="${o.padre?2:3}" maxlength="4000"></textarea><label>Tu nombre</label><input class="fb-nombre" maxlength="80" value="${esc(nombreGuardado())}" placeholder="Nombre y apellido"><div class="fb-pie"><button type="submit" class="fb-enviar">Enviar</button><span class="nota fb-estado"></span></div></form>`}
// Hilo de un elemento (o de "general") dentro de cont: comentarios más viejos primero, respuestas anidadas y el formulario.
function montarHilo(cont,o){cont.dataset.modo='hilo';cont.dataset.elem=o.elem;cont.dataset.tipo=o.tipo||'pregunta';
 const {raices,resp}=hilos(),mios=raices.filter(c=>elementoDe(c)===o.elem).reverse();
 cont.innerHTML=(FB.fallo?'<p class="nota">No se pudieron leer los comentarios.</p>':mios.length?mios.map(c=>hiloHtml(c,resp)).join(''):'<p class="nota">Todavía no hay comentarios sobre esto.</p>')+formHtml({tipo:cont.dataset.tipo});
 if(o.msg)cont.querySelector('.fb-estado').textContent=o.msg;enlazar(cont)}
// Todos los comentarios, el más nuevo primero, con el elemento al que pertenece cada uno.
function montarTodos(cont,msg){cont.dataset.modo='todos';
 const {raices,resp}=hilos();
 cont.innerHTML=FB.fallo?'<p class="nota">No se pudieron leer los comentarios.</p>':raices.length?raices.map(c=>`<span class="fb-chip">${esc(etiquetaFb(elementoDe(c))||c.seccion)}</span>`+hiloHtml(c,resp)).join(''):'<p class="nota">Todavía no hay comentarios.</p>';
 enlazar(cont)}
const rerender=(cont,msg)=>cont.dataset.modo==='todos'?montarTodos(cont,msg):montarHilo(cont,{elem:cont.dataset.elem,tipo:cont.dataset.tipo,msg});
function enlazar(cont){
 cont.onclick=e=>{const b=e.target.closest('[data-act=resp]');if(!b)return;
  const rf=cont.querySelector(`.fb-rf[data-for="${b.dataset.id}"]`);
  if(rf.firstChild){rf.innerHTML='';return}
  cont.querySelectorAll('.fb-rf').forEach(x=>{x.innerHTML=''});rf.innerHTML=formHtml({padre:b.dataset.id});rf.querySelector('textarea').focus()};
 cont.onsubmit=e=>{e.preventDefault();enviarFb(cont,e.target.closest('.fb-form'))}}
async function enviarFb(cont,form){
 const texto=form.querySelector('.fb-texto').value.trim(),autor=form.querySelector('.fb-nombre').value.trim().slice(0,80),
 est=form.querySelector('.fb-estado'),btn=form.querySelector('.fb-enviar');
 if(!texto){est.textContent='Escribí el comentario.';return}
 if(!autor){est.textContent='Falta tu nombre.';return}
 guardarNombre(autor);
 const padre=form.dataset.padre,raiz=padre?FB.cs.find(x=>x.id===padre):null,elem=raiz?elementoDe(raiz):cont.dataset.elem;
 // Una respuesta hereda la sección y el elemento de su comentario raíz y apunta siempre a la raíz.
 const c={autor,texto,seccion:(raiz?raiz.seccion:etiquetaFb(elem)||'General').slice(0,60),pestana:TAB,estado_vista:estadoVistaActual()};
 const el=raiz?raiz.elemento:elem==='general'?'':elem;if(el)c.elemento=el;
 if(padre)c.padre=padre;else c.tipo=form.querySelector('.fb-tipo').value;
 btn.disabled=true;est.textContent='Enviando...';
 try{await COM.enviar(c);await cargarFb();rerender(cont,'Enviado.');fbRefrescar()}
 catch(err){est.textContent='No se pudo enviar: '+(err.code||err.message);btn.disabled=false}}
function mostrar(el,on){clearTimeout(el._t);
 if(on){el.hidden=false;requestAnimationFrame(()=>requestAnimationFrame(()=>el.classList.add('v')))}
 else{el.classList.remove('v');el._t=setTimeout(()=>{el.hidden=true},200)}}
// Panel del botón: menú, "algo nuevo / general" y la lista de todos los comentarios.
function panelVista(v){FB.vista=v;const p=$('fb-panel');p.classList.toggle('ancho',v==='todos');
 const atras='<div class="fb-cab"><span class="fb-h">';
 if(v==='menu'){const n=cuenta(),total=FB.cs.length,gen=n.general||0;
  p.innerHTML=COM?`<p class="fb-h">Feedback</p><p class="nota">Elegí un elemento de la página para comentarlo, o usá estas opciones.</p><div class="fb-menu"><button type="button" data-act="general">Algo nuevo / general${gen?' ('+gen+')':''}</button><button type="button" data-act="todos">Ver todos los comentarios${total?' ('+total+')':''}</button><button type="button" data-act="salir">Salir</button></div>`
   :`<p class="fb-h">Feedback</p><p class="nota">Los comentarios funcionan en la versión publicada, no en el archivo abierto desde la computadora.</p><div class="fb-menu"><button type="button" data-act="salir">Cerrar</button></div>`}
 else{p.innerHTML=atras+(v==='general'?'Algo nuevo / general':'Todos los comentarios')+'</span><button type="button" class="fb-link" data-act="menu">Volver</button></div><div id="fb-sub"></div>';
  if(v==='general')montarHilo($('fb-sub'),{elem:'general',tipo:'nuevo'});else montarTodos($('fb-sub'))}}
$('fb-panel').addEventListener('click',e=>{const b=e.target.closest('[data-act]');if(!b||b.dataset.act==='resp')return;
 const a=b.dataset.act;if(a==='general'||a==='todos')panelVista(a);else if(a==='menu')panelVista('menu');else if(a==='salir')fbModo(false)});
function contorno(el){const c=$('fb-contorno');if(!el){c.classList.remove('v');return}
 const r=el.getBoundingClientRect();Object.assign(c.style,{left:r.left-3+'px',top:r.top-3+'px',width:r.width+6+'px',height:r.height+6+'px'});
 c.firstChild.textContent=el.dataset.fbLabel;c.classList.toggle('dentro',r.top<30);c.classList.add('v')}
function marcas(){const cont=$('fb-marcas');if(!FB.on){cont.innerHTML='';return}
 cont.innerHTML=Object.entries(cuenta()).map(([id,k])=>{const e=document.querySelector(`[data-fb="${id}"]`);if(!e)return '';
  const r=e.getBoundingClientRect();if(!r.width||!r.height||r.bottom<0||r.top>innerHeight)return '';
  return `<span class="fb-marca" style="left:${Math.min(r.right,innerWidth-30)-12}px;top:${Math.max(r.top,6)-9}px">${k}</span>`}).join('')}
function posBurbuja(){const b=$('fb-burbuja');if(!FB.sel||b.hidden)return;
 const r=FB.sel.getBoundingClientRect(),w=b.offsetWidth,h=b.offsetHeight,m=12,W=innerWidth,H=innerHeight;const mb=76;let x,y=Math.max(m,Math.min(r.top,H-h-mb));
 if(r.right+m+w<=W-m)x=r.right+m;
 else if(r.left-m-w>=m)x=r.left-m-w;
 else{const p=FB.pt||{x:r.left,y:r.top};x=Math.min(Math.max(m,p.x+14),W-w-m);y=Math.min(Math.max(m,p.y+14),H-h-mb)}
 b.style.left=x+'px';b.style.top=y+'px'}
function abrirBurbuja(el){FB.sel=el;const id=el.dataset.fb,b=$('fb-burbuja');
 b.innerHTML=`<div class="fb-cab"><span class="fb-h">${esc(el.dataset.fbLabel)}</span><button type="button" class="fb-x" data-act="cerrar" aria-label="Cerrar">&times;</button></div><div id="fb-hilo"></div>`;
 montarHilo($('fb-hilo'),{elem:id,tipo:'pregunta'});
 b.onclick=e=>{if(e.target.closest('[data-act=cerrar]'))cerrarBurbuja()};
 contorno(el);mostrar($('fb-panel'),false);mostrar(b,true);posBurbuja()}
function cerrarBurbuja(){FB.sel=null;FB.hov=null;contorno(null);mostrar($('fb-burbuja'),false);if(FB.on){panelVista('menu');mostrar($('fb-panel'),true)}}
function fbModo(on){if(on===FB.on&&!(on===false&&!$('fb-panel').hidden))return;FB.on=on;
 document.body.classList.toggle('fb-on',on);$('fb-btn').classList.toggle('on',on);$('fb-btn').setAttribute('aria-expanded',on);
 mostrar($('fb-aviso'),on);mostrar($('fb-panel'),on);
 if(on){panelVista('menu');cargarFb().then(()=>{if(FB.vista==='menu')panelVista('menu');marcas()})}
 else{cerrarBurbuja();$('fb-marcas').innerHTML=''}}
function fbRefrescar(){if(FB.raf)return;FB.raf=requestAnimationFrame(()=>{FB.raf=0;if(!FB.on)return;marcas();contorno(FB.sel||FB.hov);posBurbuja()})}
function fbCambio(){if(FB.on){cerrarBurbuja();fbRefrescar()}}
$('fb-btn').onclick=()=>{if(!COM){const p=$('fb-panel');if(p.hidden){panelVista('menu');mostrar(p,true)}else mostrar(p,false);return}fbModo(!FB.on)};
document.addEventListener('mousemove',e=>{if(!FB.on||FB.sel)return;const el=elemFb(e.target);if(el!==FB.hov){FB.hov=el;contorno(el)}});
// En modo selección el clic elige un elemento y no hace lo que haría la página; los botones de pestaña y de vista siguen andando.
['pointerdown','mousedown','click'].forEach(ev=>document.addEventListener(ev,e=>{
 if(!FB.on)return;const t=e.target;if(!t.closest||t.closest(UI_PROPIA)||t.closest('[data-fb-nav]'))return;
 e.preventDefault();e.stopPropagation();
 if(ev==='click'){const el=elemFb(t);FB.pt={x:e.clientX,y:e.clientY};if(el)abrirBurbuja(el);else cerrarBurbuja()}},true));
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&FB.on&&!TOUR.on)fbModo(false)});
window.addEventListener('scroll',fbRefrescar,{passive:true});window.addEventListener('resize',fbRefrescar);
cargarFb().then(fbRefrescar);
// ---- Recorrido guiado: resalta elementos reales de la página, paso a paso. Las cifras salen de los datos cargados.
const TOUR_VERSION='1';
const FILTROS_FB=['filtro-grupo','filtro-inst','filtro-vent','filtro-desde','filtro-hasta','filtro-pais','filtro-texto','filtro-forma','filtro-usd'];
const PASOS=[
 {modal:true,tit:'Explorador del corpus de financiamiento multilateral',form:true,
  texto:()=>`${nombreGuardado()?'Hola, '+nombreGuardado()+'. ':''}Reúne las operaciones que los bancos multilaterales de desarrollo aprobaron entre ${anios[0]} y ${anios[anios.length-1]}: ${fmt(D.length)} en total, con su monto en millones de dólares y el enlace a la fuente oficial. Este recorrido muestra cómo leerlo.`},
 {fb:['kpi-ops','kpi-monto','kpi-des','kpi-pais'],tit:'Los totales',
  texto:()=>`Cuatro números que se recalculan con cada filtro: operaciones, monto aprobado, operaciones con desembolso publicado y países. Con la vista actual: ${fmt(FILT.length)} operaciones y ${fmt(FILT.reduce((a,r)=>a+monto(r),0)/1e6)} ${unidad()}.`},
 {fb:[...FILTROS_FB,'filtros-activos'],tit:'Los filtros',
  texto:()=>'Acotan todo lo que ves: totales, gráficos, mapa y tabla. Cada filtro activo aparece como una ficha que se saca con la cruz, y Copiar link guarda la vista para compartirla.'},
 {tab:'resumen',fb:['resumen-evolucion'],tit:'Monto por año',
  texto:()=>`Cada color es un grupo bancario. Las líneas punteadas marcan hitos: ${HITOS.map(o=>o.c+' ('+o.a+')').join(', ')}. Son contexto, no causas.`},
 {tab:'resumen',fb:['resumen-ventanilla'],tit:'Soberana y no soberana',
  texto:()=>'Soberana: el banco financia a un Estado o con su garantía. No soberana: financia a una empresa sin garantía estatal. La tabla, plegada, da la porción no soberana de cada banco año por año.'},
 {tab:'resumen',fb:['resumen-operaciones'],tit:'Las operaciones',
  texto:()=>'Cada fila es una operación aprobada, con el enlace a su fuente. Un clic en un encabezado ordena y otro clic invierte el orden. El botón descarga las filtradas en CSV.'},
 {tab:'mapa',fb:['mapa-monto-pais'],tit:'Mapa',
  texto:()=>'Cuanto más oscuro el país, más monto aprobado. Un clic en un país lo filtra y otro clic lo saca. El gris es sin monto en el período.'},
 {tab:'mapa',fb:['mapa-vista','mapa-anios'],tit:'Años y vistas',
  texto:()=>'Reproducir recorre los años de a uno; el control deslizante elige uno y Acumulado suma hasta ese año. Plano y Globo muestran lo mismo: el globo se descarga recién cuando lo elegís.'},
 {tab:'comp',fb:['comp-treemap'],tit:'Composición',
  texto:()=>'El área de cada rectángulo es el monto: primero el grupo, después la institución y el sector, o la zona. Un clic en un grupo o una institución lo filtra.'},
 {tab:'membre',fb:['membre-grafico'],tit:'Membrecía y concentración',
  texto:()=>'Una burbuja por institución. Horizontal: países miembros. Vertical: porción del monto que reciben sus cinco mayores receptores. Sirve para ver si las instituciones con más miembros concentran menos su monto.'},
 {sel:'#fb-btn',tit:'Feedback',
  texto:()=>'Con este botón elegís cualquier elemento de la página y dejás una pregunta, una mejora o algo nuevo. También ves los comentarios de todos y podés responderlos. Se firman con tu nombre.'},
 {modal:true,tit:'Listo',texto:()=>'La pestaña Sobre el proyecto explica el alcance, los criterios, los límites y cómo citar. Podés repetir el recorrido cuando quieras con el botón Recorrido, arriba a la derecha.'}];
const INSTITUCIONES=['UNSAM','CONICET','Otra universidad','Organismo público','Organismo internacional','Otra'];
const ROLES=['Investigación','Docencia','Estudiante','Gestión pública','Otro'];
const opciones0=lista=>'<option value="">Elegí una</option>'+lista.map(v=>`<option>${v}</option>`).join('');
// Solo la primera vez: con el nombre ya guardado el recorrido no vuelve a pedir nada.
const formularioHtml=()=>`<label for="tr-nombre">Nombre</label><input id="tr-nombre" maxlength="80" placeholder="Nombre y apellido" autocomplete="name">
<label for="tr-ins">Institución</label><select id="tr-ins">${opciones0(INSTITUCIONES)}</select><input id="tr-ins-otra" maxlength="80" placeholder="¿Cuál?" hidden>
<label for="tr-rol">Rol</label><select id="tr-rol">${opciones0(ROLES)}</select>
<label for="tr-uso">¿Para qué lo vas a usar? (opcional)</label><textarea id="tr-uso" rows="2" maxlength="200"></textarea>
<p class="nota">Sin correo ni contraseña. El nombre firma tus comentarios; lo demás nos ayuda a saber quién usa el explorador y a explicarlo mejor.</p>`;
function tourPerfil(){const v=id=>$(id).value.trim(),ins=v('tr-ins')==='Otra'?v('tr-ins-otra'):v('tr-ins');
 return {nombre:v('tr-nombre').slice(0,80),institucion:ins.slice(0,80),rol:v('tr-rol'),uso:v('tr-uso').slice(0,200)}}
// El perfil viaja solo con el inicio; las visitas siguientes llevan nombre, evento y paso.
function tourVisita(evento,paso){const nombre=nombreGuardado();if(!COM||!COM.visita||!nombre)return;
 COM.visita({nombre,evento,paso,...(evento==='inicio'?TOUR.perfil||{institucion:institucionGuardada()}:{})}).catch(()=>{})}
function tourElementos(p){return (p.fb||[]).map(id=>document.querySelector(`[data-fb="${id}"]`)).concat(p.sel?[document.querySelector(p.sel)]:[]).filter(Boolean)}
function tourUnion(els){let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
 els.forEach(e=>{const r=e.getBoundingClientRect();if(!r.width&&!r.height)return;x0=Math.min(x0,r.left);y0=Math.min(y0,r.top);x1=Math.max(x1,r.right);y1=Math.max(y1,r.bottom)});
 return x0>x1?null:{x0,y0,x1,y1}}
function tourRect(els){const u=tourUnion(els);if(!u)return null;
 const y0=Math.max(u.y0,10),y1=Math.min(u.y1,innerHeight-10);return {l:u.x0-6,t:y0-6,w:u.x1-u.x0+12,h:Math.max(24,y1-y0+12)}}
// Antes de medir, lleva el objetivo a la franja visible: centrado debajo de la barra fija, o la barra misma
// pegada arriba si el objetivo vive en ella. El botón fijo y los pasos modales no se desplazan.
function tourEncuadrar(){const p=PASOS[TOUR.n],els=p.modal||p.sel?[]:tourElementos(p),barra=els.length&&els[0].closest('#barra'),u=tourUnion(els);
 if(barra)scrollBy({top:Math.round(barra.getBoundingClientRect().top),behavior:'instant'});
 else if(u){const top=$('barra').offsetHeight+12,alto=innerHeight-top-12,h=u.y1-u.y0;
  scrollBy({top:Math.round(u.y0-top-Math.max(0,alto-h)/2),behavior:'instant'})}
 tourPos()}
function tourPos(){const p=PASOS[TOUR.n],caja=$('tr-caja'),foco=$('tr-foco'),capa=$('tr-capa'),m=14,W=innerWidth,H=innerHeight;
 const r=p.modal?null:tourRect(tourElementos(p)),cw=caja.offsetWidth,ch=caja.offsetHeight,cl=(v,a,b)=>Math.max(a,Math.min(v,b));
 capa.classList.toggle('dim',!r);foco.classList.toggle('v',!!r);
 if(!r){caja.style.left=(W-cw)/2+'px';caja.style.top=Math.max(m,(H-ch)/2)+'px';return}
 Object.assign(foco.style,{left:r.l+'px',top:r.t+'px',width:r.w+'px',height:r.h+'px'});
 let x,y;
 if(r.t+r.h+m+ch<=H-m){y=r.t+r.h+m;x=cl(r.l,m,W-cw-m)}
 else if(r.t-m-ch>=m){y=r.t-m-ch;x=cl(r.l,m,W-cw-m)}
 else if(r.l+r.w+m+cw<=W-m){x=r.l+r.w+m;y=cl(r.t,m,H-ch-m)}
 else if(r.l-m-cw>=m){x=r.l-m-cw;y=cl(r.t,m,H-ch-m)}
 else{x=W-cw-m;y=H-ch-m}
 caja.style.left=x+'px';caja.style.top=y+'px'}
function tourPaso(n){const p=PASOS[n],caja=$('tr-caja'),ult=n===PASOS.length-1,pide=p.form&&!nombreGuardado();TOUR.n=n;
 if(p.tab&&p.tab!==TAB)pestania(p.tab);
 caja.classList.toggle('modal',!!p.modal);
 caja.innerHTML=`<div class="tr-prog"><span>${n+1} de ${PASOS.length}</span><span class="tr-barra"><i style="width:${100*(n+1)/PASOS.length}%"></i></span></div><h3 class="tr-t" id="tr-tit">${esc(p.tit)}</h3><p>${esc(p.texto())}</p>`+
  (pide?formularioHtml():'')+
  `<div class="tr-pie"><button type="button" class="tr-sec" data-tr="salir">${n===0?'Ahora no':ult?'':'Salir'}</button><span class="tr-sp"></span><button type="button" data-tr="ant"${n===0?' hidden':''}>Anterior</button><button type="button" class="tr-pri" data-tr="sig"${pide?' disabled':''}>${n===0?'Empezar':ult?'Terminar':'Siguiente'}</button></div>`;
 if(ult)caja.querySelector('[data-tr=salir]').hidden=true;
 caja.style.display='block';requestAnimationFrame(()=>{tourEncuadrar();caja.classList.add('v');const f=caja.querySelector('#tr-nombre')||caja.querySelector('.tr-pri');f.focus()});
 setTimeout(()=>{if(TOUR.on&&TOUR.n===n)tourEncuadrar()},450)}
function tourIniciar(){if(TOUR.on)return;fbModo(false);TOUR.on=true;TOUR.perfil=null;TOUR.previo={tab:TAB,vista:VISTA,y:window.scrollY};pararTodo();document.documentElement.classList.add('tr-lock');
 $('tr-capa').style.display='block';tourPaso(0)}
function tourFin(completo){if(!TOUR.on)return;
 tourVisita(completo?'recorrido_completo':'recorrido_salteado',TOUR.n);
 TOUR.on=false;document.documentElement.classList.remove('tr-lock');try{localStorage.setItem('explorador-recorrido',TOUR_VERSION)}catch(e){}
 const caja=$('tr-caja');caja.classList.remove('v');$('tr-foco').classList.remove('v');
 setTimeout(()=>{if(!TOUR.on){caja.style.display='none';$('tr-capa').style.display='none'}},220);
 if(TOUR.previo){pestania(TOUR.previo.tab);escribirHash();window.scrollTo(0,TOUR.previo.y)}}
function tourSiguiente(){if(TOUR.n===0){
  if($('tr-nombre')){const pf=tourPerfil();if(!pf.nombre)return;guardarNombre(pf.nombre);guardarInstitucion(pf.institucion);TOUR.perfil=pf}
  tourVisita('inicio')}
 if(TOUR.n>=PASOS.length-1)tourFin(true);else tourPaso(TOUR.n+1)}
$('tr-caja').addEventListener('click',e=>{const b=e.target.closest('[data-tr]');if(!b)return;
 if(b.dataset.tr==='sig')tourSiguiente();else if(b.dataset.tr==='ant'&&TOUR.n>0)tourPaso(TOUR.n-1);else if(b.dataset.tr==='salir')tourFin(false)});
$('tr-caja').addEventListener('input',e=>{
 if(e.target.id==='tr-nombre')$('tr-caja').querySelector('.tr-pri').disabled=!e.target.value.trim();
 if(e.target.id==='tr-ins')$('tr-ins-otra').hidden=e.target.value!=='Otra'});
// Mientras el recorrido está abierto la página no se desplaza: el foco y la caja siempre coinciden con su elemento.
['wheel','touchmove'].forEach(ev=>addEventListener(ev,e=>{if(TOUR.on&&e.target.tagName!=='TEXTAREA')e.preventDefault()},{passive:false}));
document.addEventListener('keydown',e=>{if(!TOUR.on)return;const tag=e.target&&e.target.tagName,campo=/^(INPUT|TEXTAREA|SELECT)$/.test(tag);
 if(e.key==='Escape'){e.preventDefault();e.stopPropagation();tourFin(false)}
 else if(e.key==='ArrowRight'&&!campo){e.preventDefault();e.stopPropagation();tourSiguiente()}
 else if(e.key==='ArrowLeft'&&!campo){e.preventDefault();e.stopPropagation();if(TOUR.n>0)tourPaso(TOUR.n-1)}
 else if(e.key==='Enter'&&tag==='INPUT'){e.preventDefault();tourSiguiente()}
 else if(!campo&&(['ArrowUp','ArrowDown','PageUp','PageDown','Home','End'].includes(e.key)||(e.key===' '&&tag!=='BUTTON')))e.preventDefault()},true);
window.addEventListener('resize',()=>{if(TOUR.on)tourEncuadrar()});
$('b-recorrido').onclick=tourIniciar;
const tab0=aplicarHash();ficha();pestania(tab0,false);dibujar();
// Primera visita: el recorrido arranca solo y no vuelve hasta que cambie su versión.
try{if(localStorage.getItem('explorador-recorrido')!==TOUR_VERSION)setTimeout(tourIniciar,700)}catch(e){}
}
__ARRANQUE__
</script></body></html>
"""


def main() -> int:
    if not CORPUS.exists():
        raise SystemExit("falta el corpus. Correr antes: uv run python scripts/consolidar.py")
    df = ap.cargar()
    df["region"] = df["pais"].apply(ap.region_de).map(REGION)
    df["iso3"] = df["pais"].apply(iso_de)
    df["zona"] = df["iso3"].map(lambda k: GEO[k]["z"] if isinstance(k, str) else None)
    df.loc[~df["pais"].apply(ap.es_pais_real) & df["region"].isna(), "region"] = "G"
    ventanillas = ap.ventanillas(df).to_dict(orient="records")
    fuentes = [{"institucion": inst, "operaciones": int(len(g)), "descargado": str(g["fecha_relevamiento"].max()),
                "fuente": str(g["fuente_url"].mode().iloc[0])} for inst, g in df.groupby("institucion")]
    df = df[COLUMNAS].copy()
    df["descripcion"] = df["descripcion"].str.slice(0, LARGO_DESCRIPCION)
    df["anio_aprobacion"] = df["anio_aprobacion"].astype(int)
    df["monto_constante_usd"] = df["monto_constante_usd"].round(0)
    df = df.astype(object).where(df.notna(), None)
    fecha = date.fromtimestamp(CORPUS.stat().st_mtime).strftime("%d/%m/%Y")
    base = (PAGINA.replace("__COLORES_GRUPO__", CSS_COLORES_GRUPO).replace("__FECHA__", fecha)
            .replace("__GRUPOS__", json.dumps(ORDEN_GRUPOS)).replace("__ILUSTRACION__", ILUSTRACION))
    anios = sorted(df["anio_aprobacion"].unique().tolist())
    paquete = json.dumps({"columnas": COLUMNAS, "datos": df.values.tolist(), "ventanillas": ventanillas,
                          "fuentes": fuentes, "fichas": FICHAS, "geo": GEO, "zonas": ZONAS,
                          "membrecia": membrecia_por_anio(anios), "centroides": CENTROIDES_EXTRA,
                          "sedes": {g: [s[1], s[2], s[0]] for g, s in SEDES.items()},
                          "complemento_caf": ap.complemento_caf(ap.cargar()).drop(columns=["fuente_url"], errors="ignore")
                          .to_dict(orient="records")}, ensure_ascii=False, default=float)

    local = (base.replace("__INGRESO__", "").replace("__CARGADOR__", "")
             .replace("__ARRANQUE__", f"iniciar({paquete},null);"))
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(local, encoding="utf-8")
    print(f"Escrito {SALIDA.relative_to(RAIZ)}: {len(df):,} operaciones, {len(local) / 1e6:.1f} MB")

    if not PUBLICABLE:
        return 0
    web = (base.replace("__INGRESO__", INGRESO).replace("<script>__CARGADOR__", "</div></div><script type=\"module\">" + CARGADOR)
           .replace("__ARRANQUE__", ""))
    SALIDA_WEB.parent.mkdir(parents=True, exist_ok=True)
    SALIDA_WEB.write_text(web, encoding="utf-8")
    (SALIDA_WEB.parent / "datos.json").write_text(paquete, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
