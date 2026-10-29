"""Quién recibe el préstamo en CAF, FONPLATA y BCIE, y si es soberano.

Estos tres bancos no separan sus ventanillas en instituciones ni publican la garantía soberana en
ningún campo del archivo IATI (revisado el 8/10/2026 sobre las tres descargas). Por criterio de la
dirección del 8/10, lo que define la ventanilla es el sujeto del préstamo: un Estado nacional es
soberano; una empresa o un banco, no soberano; un gobierno subnacional depende del banco. La única
señal es el nombre del prestatario, así que la clasificación es por reglas sobre ese nombre, y los
casos que el nombre no resuelve quedan en categorías de revisión en lugar de forzarse:

- subnacional: provincias, estados federados, municipios. Pueden tener garantía de la Nación.
- banco_publico: bancos estatales de desarrollo, que toman deuda con o sin garantía soberana.
- empresa_publica: empresas del Estado sin forma societaria privada.

Dónde está el prestatario: en el BCIE, en el receptor de las transacciones (que además declara si
es sector privado, tipo 70); en FONPLATA, en la organización responsable (rol 2); en CAF solo está
el ejecutor (rol 4), que no siempre es el deudor. Evidencia y verificaciones: H33 en
docs/hallazgos.md.
"""

from __future__ import annotations

import collections
import re
import unicodedata
import xml.etree.ElementTree as ET

def norm(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    return " " + re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', s)).strip() + " "

# Excepciones revisadas a mano (nombre normalizado, sin espacios extremos -> (categoria, motivo)).
# Son siglas sin palabra clave o casos donde las palabras clave engañan.
OVR = {
 'mti': ('soberana', 'sigla: Ministerio de Transporte e Infraestructura (Nicaragua)'),
 'sit': ('soberana', 'sigla: Secretaria de Infraestructura y Transporte (Honduras)'),
 'comision ejecutiva hidroelectrica del rio lempa cel': ('empresa_publica', 'CEL: generadora estatal de El Salvador'),
 'administracion nacional de correos': ('empresa_publica', 'Correo Uruguayo: empresa estatal'),
 'administracion de las obras sanitarias del estado': ('empresa_publica', 'OSE Uruguay: empresa estatal de agua'),
 'instituto nacional de aguas potables y alcantarillados inapa': ('empresa_publica', 'INAPA: entidad estatal de agua (Rep. Dominicana)'),
 'ose': ('empresa_publica', 'OSE Uruguay: empresa estatal de agua'),
 'the commonwealth of the bahamas': ('soberana', 'Estado nacional (Bahamas)'),
 'barbados water authority': ('empresa_publica', 'autoridad estatal de agua (Barbados)'),
 'bogota distrito capital': ('subnacional', 'distrito capital (gobierno local)'),
 'banecuador': ('banco_publico', 'BanEcuador: banco estatal'),
 'el credito hipotecario nacional': ('banco_publico', 'banco estatal de Guatemala'),
 'caja costarricense de seguro social': ('empresa_publica', 'entidad publica autonoma de seguridad social'),
 'caja de jubilaciones y pensiones bancarias': ('empresa_publica', 'entidad publica no estatal (Uruguay)'),
 'ugp aparecida de goiania': ('subnacional', 'unidad del municipio de Aparecida de Goiania'),
 'ministerio de gobernacion y desarrollo territorial mingobdt': ('soberana', 'ministerio nacional de El Salvador'),
 'compania espanola de financiacion del desarrollo cofides s a s m e': ('banco_publico', 'COFIDES: financiera de desarrollo estatal espanola'),
 'fondo ganadero': ('soberana', 'fondo publico (no verificado)'),
 'centros educativos primera infancia': ('sin_dato', 'vehiculo PPP, sin dato del titular'),
 'mop': ('soberana', 'sigla: Ministerio de Obras Publicas'),
 'minsa': ('soberana', 'sigla: Ministerio de Salud'),
 'conavi': ('soberana', 'sigla: Consejo Nacional de Vialidad (CR), organo del gobierno central'),
 'enatrel': ('empresa_publica', 'sigla: Empresa Nacional de Transmision Electrica (Nicaragua)'),
 'enee': ('empresa_publica', 'sigla: Empresa Nacional de Energia Electrica (Honduras)'),
 'enacal': ('empresa_publica', 'sigla: ENACAL'),
 'aya': ('empresa_publica', 'sigla: AyA'),
 'incofer': ('empresa_publica', 'sigla: Instituto Costarricense de Ferrocarriles'),
 'banhprovi': ('banco_publico', 'sigla: Banco Hondureno para la Produccion y la Vivienda'),
 'fovial': ('soberana', 'Fondo de Conservacion Vial (fondo publico central)'),
 'fondo de conservacion vial': ('soberana', 'Fondo de Conservacion Vial (fondo publico central)'),
 'organismos del sector justicia': ('soberana', 'organismos del sector justicia (gobierno central)'),
 'instituto conmemorativo gorgas de estudios de la salud': ('soberana', 'instituto publico de salud (Panama)'),
 'secretaria metro de panama': ('soberana', 'Secretaria del Metro: agencia del gobierno central (no es empresa)'),
 'administradora nacional de electricidad ande': ('empresa_publica', 'ANDE: empresa electrica estatal'),
 'administracion nacional de electricidad': ('empresa_publica', 'ANDE: empresa electrica estatal'),
 'agencia nacional de desarrollo ande': ('empresa_publica', 'ANDE: empresa electrica estatal (nombre mal escrito)'),
 'adm nal de navegacion y puertos annp': ('empresa_publica', 'ANNP: administracion portuaria estatal'),
 'corporacion vial del uruguay s a cvu': ('empresa_publica', 'CVU: S.A. propiedad de la Corporacion Nacional para el Desarrollo (Uruguay)'),
 'corporacion vial del uruguay': ('empresa_publica', 'CVU: S.A. estatal (Uruguay)'),
 'corporacion nacional para el desarrollo': ('banco_publico', 'CND Uruguay: holding financiero estatal'),
 'fondo nacional de inversion productiva y social': ('soberana', 'FNDR/FPS: fondo publico central'),
 'fondo fiduciario federal de infraestructura regional': ('soberana', 'fideicomiso del gobierno federal argentino'),
 'fondo fiduc fed de infraest regional ffir': ('soberana', 'fideicomiso del gobierno federal argentino'),
 'fondo financiero para el desarrollo de la cuenca del plata fonplata': ('multilateral', 'FONPLATA es banco multilateral'),
 'ministerio de educacion de jujuy': ('subnacional', 'ministerio de la provincia de Jujuy'),
 'republica administradora de fondos de inversion s a rafisa': ('no_soberana', 'gestora privada de fondos (no es una Republica)'),
 'agencia cordoba de inversion y financiamiento': ('subnacional', 'agencia de la provincia de Cordoba'),
 'instituto de vivienda de la ciudad': ('subnacional', 'instituto de la Ciudad de Buenos Aires'),
 'unidad de gestion provincia de santa fe': ('subnacional', 'unidad de la provincia de Santa Fe'),
 'unidad provincial de enlace y ejecucion de proyectos con financiamiento externo': ('subnacional', 'unidad provincial'),
 'dpomyfb del m econ pcia bs as': ('subnacional', 'ministerio de la provincia de Buenos Aires'),
 'min economia prov buenos aires': ('subnacional', 'ministerio de la provincia de Buenos Aires'),
 'direccion de vialidad pcia de bs as': ('subnacional', 'direccion provincial'),
 'direccion de vialidad provincial': ('subnacional', 'direccion provincial'),
 'casa civil do estado do para': ('subnacional', 'gobierno del estado de Para'),
 'estados unidos mexicanos': ('soberana', 'Estado nacional (Mexico)'),
 'mancomunidad de las bahamas commonwealth of the bahamas': ('soberana', 'Estado nacional (Bahamas)'),
 'departamento de valle del cauca': ('subnacional', 'departamento de Colombia'),
 'distrito de barranquilla': ('subnacional', 'distrito de Colombia (gobierno local)'),
 'instituto de credito oficial ico': ('banco_publico', 'ICO: agencia financiera del Estado espanol'),
 'caixa general de depositos': ('banco_publico', 'banco estatal portugues'),
 'enel': ('no_soberana', 'grupo electrico cotizado'),
 'v tal': ('no_soberana', 'empresa privada de fibra optica (Brasil)'),
 'infraestructura arazati': ('no_soberana', 'vehiculo del consorcio privado de la PPP Arazati (Uruguay)'),
 'caja de compensacion de asignacion familiar los andes': ('no_soberana', 'entidad privada sin fines de lucro (Chile)'),
 'asociacion civil club atletico river plate carp': ('no_soberana', 'asociacion civil'),
 'oenergy pv 72 mwp': ('no_soberana', 'proyecto solar privado'),
 'atacama solar': ('no_soberana', 'proyecto solar privado'),
 'corporacion interamericana para el financiamiento de infraestructura': ('no_soberana', 'CIFI: financiera privada'),
 'secretaria de turismo do estado do ceara': ('subnacional', 'secretaria del estado de Ceara'),
}
BANCO = r'\b(banco|bank|financiera|banhprovi|banesco|santander|scotiabank|davivienda|bbva|itau|citibank|hsbc|bladex|cofides)\b'
BANCO_PUB = (r'banco del estado|banco de la nacion|bndes|bancoldex|banco do nordeste|\bbnb\b|banco do brasil|caixa economica|'
  r'corporacion financiera nacional|financiera de desarrollo nacional|findeter|\bbice\b|banco de inversion y comercio exterior|'
  r'banco de desarrollo|banco de desenvolvimento|desenvolve sp|banco regional de desenvolvimento|brde|banadesa|bandex|banco nacional de comercio exterior|nafin|agencia financiera de desarrollo|finanzas populares|agencia de fomento|banco nacional|banco agricola|'
  r'banco de la republica|banco central|nacional financiera|cofide|banco de fomento|banco estado|banco para el fomento')
PRIVADO = r'\b(s a|s a s|s a m|c a|s l|sl|ltda|ltd|inc|llc|l p|lp|ltd|sas|s de r l|holding|group|grupo|partners|ventures|fund|fondo de capital privado|debt fund|investment)\b'
ESTADO_HINT = r'\b(nacional|estatal|del estado|publica|publico|vial del uruguay)\b'
EMPRESA = (r'\b(empresa|compania|ferrocarril\w*|hidrologica|servicio de agua|electric\w*|energia|acueducto\w*|puerto\w*|portuaria|'
  r'metropolitano|corporacion|petro\w*|telecom\w*|aeropuerto\w*)\b')
SUBNAC = (r'\b(gobernacion|gobierno (autonomo|provincial|departamental|de la provincia|del estado|municipal|regional|metropolitano)|provincia|provincial|prov|'
  r'pcia|municip\w*|prefeitura|prefectura|alcaldia|intendencia|ayuntamiento|gobierno autonomo|estado d[eo]s? (?!la republica)\w+|departamental|distrito metropolitano|ciudad de)\b')
SOBERANO = (r'\b(ministerio|ministerios|minist|min|ministry|republica|estado plurinacional|gobierno de (belice|argentina|cuba|\w+)|gobierno nacional|'
  r'secretaria|secretaria de estado|jefatura|presidencia|departamento nacional|hacienda|tesoreria|finanzas|casa civil|'
  r'instituto nacional|instituto|administradora|administracion|direccion|comision|consejo|fiscalia|fondo|agencia nacional|unidad|'
  r'subsecretaria|sub stria|biblioteca nacional|jefatura de gabinete)\b')

SOV_START = r'^ (ministerio|ministerios|ministry|republica de|republica del|republica dominicana|gobierno de|estado plurinacional|secretaria de estado|subsecretaria|departamento nacional de planeacion)'
def clasifica_nombre(nombre, pais=None):
    n = norm(nombre); k = n.strip()
    if not k: return ('sin_dato', 'sin nombre', 'n/a')
    if k in OVR: c, m = OVR[k]; return (c, 'excepcion manual: ' + m, 'media')
    if re.search(r'\bcon garantia soberana\b', n): return ('soberana', 'el nombre declara garantia soberana', 'alta')
    if re.search(BANCO_PUB, n): return ('banco_publico', 'banco/financiera estatal conocido, revisar garantia soberana', 'baja')
    if re.search(BANCO, n):
        if re.search(r'\b(del estado|nacional|desarrollo|fomento|estatal)\b', n):
            return ('banco_publico', 'banco con indicio de propiedad estatal, revisar', 'baja')
        return ('no_soberana', 'banco comercial', 'alta' if re.search(PRIVADO, n) else 'media')
    if re.search(r'\b(consorcio|concessionaria|concesionaria|fund|fondo de capital|fondo de deuda|fondo ashmore|fcp|fcr|f c r)\b', n): return ('no_soberana', 'consorcio / concesionaria / fondo privado', 'alta')
    if re.search(r'\b(empresa|compania|servicio de agua|ferrocarril\w*|hidrologica)\b', n) and not re.search(PRIVADO, n):
        return ('empresa_publica', 'empresa sin forma societaria privada, probable estatal/municipal, revisar', 'baja')
    if re.search(SUBNAC, n) and not re.search(r'^ ministerio de gobernacion', n):
        return ('subnacional', 'gobierno o entidad subnacional (provincia, municipio, estado federado)', 'media')
    if pais == 'Brazil' and re.search(r'\b(secretaria|sec|casa civil|ugp)\b', n):
        return ('subnacional', 'Brasil: secretaria sin "Ministerio" es estadual o municipal', 'baja')
    if re.search(SOV_START, n): return ('soberana', 'ministerio / Republica / Gobierno nacional', 'alta')
    if re.search(PRIVADO, n):
        if re.search(ESTADO_HINT, n): return ('empresa_publica', 'S.A. con indicio estatal, revisar', 'baja')
        return ('no_soberana', 'sociedad/fondo privado (S.A., Ltda, L.P., Grupo, Fund)', 'alta')
    if re.search(r'\b(ministerio|ministerios|republica|estado plurinacional|gobierno de \w+|departamento nacional de planeacion|dnp|hacienda|finanzas|jefatura|presidencia|tesoreria|secretaria|ministry|minist|min|subsecretaria|sub stria)\b', n):
        return ('soberana', 'ministerio / Republica / organismo central', 'alta')
    if re.search(EMPRESA, n): return ('empresa_publica', 'palabra de empresa/servicio publico sin forma privada, revisar', 'baja')
    if re.search(SOBERANO, n): return ('soberana', 'instituto/administradora/fondo/direccion de nivel central (no verificado)', 'media')
    return ('sin_dato', 'nombre no reconocido por la regla', 'n/a')


def _texto(e: ET.Element) -> str:
    return " ".join("".join(e.itertext()).split())


def prestatario_iati(act: ET.Element, institucion: str, pais: str | None) -> tuple[str, str, str]:
    """(prestatario, categoría, motivo) de una actividad IATI de CAF, FONPLATA o BCIE."""
    participantes = [(p.get("role"), _texto(p)) for p in act.findall("participating-org")]
    ejecutores = [n for r, n in participantes if r == "4" and n]
    responsables = [n for r, n in participantes if r == "2" and n]
    receptores = collections.Counter(
        (r.get("type"), _texto(r)) for t in act.findall("transaction") for r in t.findall("receiver-org") if _texto(r))
    receptor = receptores.most_common(1)[0][0] if receptores else None
    tipo_fin = act.find("default-finance-type")

    if institucion == "CAF":
        nombre = ejecutores[0] if ejecutores else ""
        categoria, motivo, _ = clasifica_nombre(nombre, pais)
        if tipo_fin is not None and tipo_fin.get("code") == "510" and categoria not in ("banco_publico", "multilateral"):
            return nombre, "no_soberana", "capital accionario (finance-type 510)"
        return nombre, categoria, "ejecutor: " + motivo
    if institucion == "BCIE" and receptor:
        tipo, nombre = receptor
        if tipo == "70":
            return nombre, "no_soberana", "receptor declarado sector privado (tipo 70)"
        categoria, motivo, _ = clasifica_nombre(nombre, pais)
        if categoria == "sin_dato" and ejecutores:
            nombre = ejecutores[0]
            categoria, motivo, _ = clasifica_nombre(nombre, pais)
        return nombre, categoria, "receptor: " + motivo
    nombre = (responsables or ejecutores or [receptor[1] if receptor else ""])[0]
    if not nombre:
        return "", "sin_dato", "sin prestatario ni ejecutor en la fuente"
    categoria, motivo, _ = clasifica_nombre(nombre, pais)
    return nombre, categoria, ("responsable: " if responsables else "ejecutor: ") + motivo
