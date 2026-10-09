"""Genera un explorador del corpus en un solo archivo HTML, con los datos adentro.

Es el borrador más simple posible de un tablero: no elige herramienta (eso sigue abierto, P4), no
necesita servidor ni internet, se abre con doble clic y se puede mandar como archivo o subir a
cualquier hosting estático. Permite filtrar por grupo, institución, ventanilla, años, país y texto,
y muestra el monto por año, los principales países y sectores, y las operaciones con su enlace.

Uso:
    uv run python scripts/explorador_corpus.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analisis_preliminar as ap  # noqa: E402  mismas reglas que el informe

RAIZ = Path(__file__).resolve().parent.parent
CORPUS = RAIZ / "data" / "processed" / "corpus_2014_2025.csv"
SALIDA = RAIZ / "data" / "processed" / "explorador" / "explorador-corpus.html"
# Version publicada: la misma pagina sin los datos adentro. Los datos y los comentarios se leen de
# Firestore despues de que la persona entra con el link que le llega por mail (web/publicar.py).
SALIDA_WEB = RAIZ / "data" / "processed" / "explorador" / "publicado" / "index.html"
# La versión publicada solo se arma donde está la carpeta web/ (el repositorio privado); en el
# público se genera solo el archivo local, que se abre con doble clic.
WEB = RAIZ / "web"
PUBLICABLE = (WEB / "cargador.js").exists()
INGRESO = (WEB / "ingreso.html").read_text(encoding="utf-8") if PUBLICABLE else ""
CARGADOR = (WEB / "cargador.js").read_text(encoding="utf-8") if PUBLICABLE else ""

COLUMNAS = ["banco_grupo", "institucion", "tipo_ventanilla", "nombre", "pais", "anio_aprobacion",
            "estado", "monto_aprobado_usd", "monto_desembolsado_usd", "sector", "url_proyecto",
            "monto_constante_usd", "region", "forma_financiamiento", "moneda_original", "monto_original",
            "descripcion"]
# Una ficha por grupo bancario, en lenguaje para cualquier lector: es lo que convierte el
# explorador en el tablero por grupo que pide el plan de trabajo. Cada afirmación tiene su respaldo
# en docs/hallazgos.md.
FICHAS = {
    "GBM": "Grupo Banco Mundial. Cuatro ventanillas: el BIRF presta a Estados de ingreso medio, la IDA a "
           "Estados de ingreso bajo (con créditos y donaciones), la IFC a empresas y MIGA otorga garantías "
           "de inversión. Los montos son el aporte del banco; los fondos de donantes que administra van "
           "aparte. Publica desembolsos para el BIRF y la IDA. Sus informes anuales cierran el año en junio.",
    "GBID": "Grupo BID. El BID presta a Estados de América Latina y el Caribe, BID Invest a empresas y BID "
            "Lab financia innovación y cooperación técnica. Hasta 2015 el propio BID aprobaba la cartera "
            "privada, que en 2016 pasó a BID Invest: por eso la serie de la ventanilla privada se lee desde "
            "2016. No publica desembolsos.",
    "CAF": "CAF, Banco de Desarrollo de América Latina y el Caribe. Presta a Estados y a empresas sin "
           "separar ventanillas; la ventanilla se clasificó por el nombre del prestatario. Atención: su "
           "archivo oficial trae cerca del 27% de lo que CAF declara haber aprobado en sus informes anuales "
           "y casi nada de sus líneas de crédito a bancos. La tabla de abajo muestra el faltante por año.",
    "NDB": "Nuevo Banco de Desarrollo de los BRICS, opera desde 2016. Declara la ventanilla de cada "
           "operación y presta buena parte en monedas locales, convertidas a dólares con el promedio del "
           "año. Los montos se completaron con el anexo de su informe anual 2025. No publica la forma del "
           "financiamiento ni desembolsos.",
    "AIIB": "Banco Asiático de Inversión en Infraestructura, opera desde 2016. Declara la ventanilla de "
            "cada operación. Es de los más concentrados por país, con proyectos grandes. No publica la "
            "forma del financiamiento ni desembolsos.",
    "FONPLATA": "FONPLATA, banco de los cinco países de la Cuenca del Plata. Publica desembolsos de casi todas "
                "sus operaciones; no separa ventanillas y en una de cada tres falta el prestatario.",
    "BCIE": "Banco Centroamericano de Integración Económica. Publica desembolsos de tres de cada cuatro "
            "operaciones; declara cuando el prestatario es privado.",
}

# La descripción se recorta para que la página siga siendo liviana; la entera está en el corpus.
LARGO_DESCRIPCION = 300

# A: America Latina y el Caribe (con sus agregados), R: resto del mundo, G: agregado sin pais.
REGION = {"ALC": "A", "ALC (agregado regional)": "A", "resto del mundo": "R", "otro agregado regional": "G"}

PAGINA = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Explorador del corpus</title>
<style>
:root{--t:#111;--s:#666;--l:#ddd;--b:#fff;--a:#111}
body{font-family:system-ui,-apple-system,Segoe UI,Arial,sans-serif;color:var(--t);background:var(--b);margin:0 auto;max-width:1100px;padding:16px;line-height:1.4}
h1{font-size:22px;margin:4px 0}h2{font-size:16px;margin:24px 0 8px}
.nota{color:var(--s);font-size:13px}
.filtros{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:8px;margin:16px 0}
label{font-size:12px;color:var(--s);display:block}
select,input{width:100%;padding:6px;border:1px solid var(--l);border-radius:4px;font-size:14px;box-sizing:border-box}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px}
.kpi{border:1px solid var(--l);border-radius:6px;padding:10px}.kpi b{font-size:20px;display:block}
.barras div{display:grid;grid-template-columns:150px 1fr 90px;gap:8px;align-items:center;font-size:13px;margin:2px 0}
.barras span.b{background:var(--a);height:14px;display:block}
.barras .n{text-align:right;font-variant-numeric:tabular-nums}
.anios{display:flex;align-items:flex-end;gap:4px;height:160px;border-bottom:1px solid var(--l)}
.anios div{flex:1;background:var(--a);position:relative}
#g-forma div{background:none;display:flex;flex-direction:column-reverse}#g-forma span{display:block}
.leyenda{font-size:12px;color:var(--s);margin:4px 0}.leyenda i{display:inline-block;width:10px;height:10px;margin:0 4px 0 10px;vertical-align:middle}
.anios-et{display:flex;gap:4px;font-size:11px;color:var(--s)}.anios-et span{flex:1;text-align:center}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{border-bottom:1px solid var(--l);padding:4px;text-align:left;vertical-align:top}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.tabla{overflow-x:auto}.tableros button{margin:0 6px 6px 0}.tableros button.on{background:var(--t);color:var(--b)}th[data-o]{cursor:pointer;text-decoration:underline dotted}details summary{cursor:pointer;color:var(--s)}button{padding:6px 10px;border:1px solid var(--t);background:var(--b);border-radius:4px;cursor:pointer}
</style></head><body>
<h1>Explorador del corpus de financiamiento multilateral</h1>
__INGRESO__
<p class="nota">Proyecto CIAI Nº 34, UNSAM. Operaciones aprobadas 2014 a 2025, sin canceladas, armonizadas desde
las fuentes oficiales de cada banco. Descargas del __FECHA__. Montos aprobados en millones de dólares, corrientes o constantes de 2025 según el selector.
Sectores tal como los nombra cada banco. Ojo: la IFC anota el tope entero de algunas facilidades marco en cada banco participante, así que sus montos en mercados financieros están inflados. Borrador de trabajo, no para citar.</p>
<p id="tableros" class="tableros"></p>
<div class="kpi" id="ficha" style="display:none;margin:8px 0"></div>
<div id="caf-comp" style="display:none"><h2>CAF según sus informes anuales</h2>
<p class="nota">Millones de dólares. Lo que CAF declara haber aprobado en su informe de cada año, contra lo que trae su
archivo oficial (el corpus). El faltante se informa aparte y no se suma a las operaciones.</p>
<div class="tabla"><table><thead><tr><th>Año</th><th class="n">Informe</th><th class="n">En el corpus</th><th class="n">Falta soberano</th><th class="n">Falta no soberano</th><th class="n">Cobertura</th></tr></thead><tbody id="t-caf"></tbody></table></div></div>
<div class="filtros">
<div><label>Banco</label><select id="f-grupo"></select></div>
<div><label>Institución</label><select id="f-inst"></select></div>
<div><label>Ventanilla</label><select id="f-vent"></select></div>
<div><label>Desde</label><select id="f-desde"></select></div>
<div><label>Hasta</label><select id="f-hasta"></select></div>
<div><label>País contiene</label><input id="f-pais" placeholder="Argentina"></div>
<div><label>Nombre, sector o descripción contiene</label><input id="f-texto" placeholder="solar, energy"></div>
<div><label>Forma</label><select id="f-forma"></select></div>
<div><label>Dólares</label><select id="f-usd"><option value="c">Corrientes</option><option value="k">Constantes de 2025</option></select></div>
</div>
<div class="kpis">
<div class="kpi"><span class="nota">Operaciones</span><b id="k-ops"></b></div>
<div class="kpi"><span class="nota" id="k-monto-et">Aprobado, USD M</span><b id="k-monto"></b></div>
<div class="kpi"><span class="nota">Con desembolso publicado</span><b id="k-des"></b></div>
<div class="kpi"><span class="nota">Países</span><b id="k-pais"></b></div>
</div>
<h2>Monto aprobado por año</h2><div class="anios" id="g-anios"></div><div class="anios-et" id="g-anios-et"></div>
<h2>Por forma del financiamiento</h2>
<p class="nota">Con los filtros elegidos. Préstamo, donación, garantía u otro (capital, bonos, gestión de riesgo), según el
campo de cada fuente; mixta si la operación combina más de una. El AIIB y el NDB no publican la forma.</p>
<div class="leyenda" id="g-forma-ley"></div><div class="anios" id="g-forma"></div><div class="anios-et" id="g-forma-et"></div>
<h2>Comparación entre bancos</h2>
<p class="nota">Con los filtros elegidos. Cinco principales: porción del monto que se llevan los cinco países que más
reciben, sin contar los agregados sin país. A ALC: incluye los agregados regionales de la región.</p>
<div class="tabla"><table><thead><tr><th>Institución</th><th class="n">Operaciones</th><th class="n">USD M</th>
<th class="n">% del total</th><th class="n">Monto mediano</th><th class="n">A ALC</th><th class="n">Cinco principales</th>
<th>Principal receptor</th></tr></thead><tbody id="t-bancos"></tbody></table></div>
<h2>Ventanilla no soberana, por banco</h2>
<p class="nota">Participación de la ventanilla no soberana sobre el total aprobado de cada banco. En el Grupo Banco
Mundial y el Grupo BID la ventanilla es la institución (MIGA y BID Lab quedan fuera de las dos categorías, y se sacan
los topes de facilidad repetidos de la IFC); en el AIIB y el NDB la declara la fuente operación por operación. CAF,
BCIE y FONPLATA no la publican y se están clasificando por el prestatario. No cambia con los filtros. En 2014 y 2015
la cartera privada del BID figura como soberana (ver informe v3, sección 2).</p>
<div class="tabla"><table><thead id="t-vent-cab"></thead><tbody id="t-vent"></tbody></table></div>
<h2>Fuentes y fecha de descarga</h2>
<p class="nota">De dónde sale cada institución y cuándo se bajó por última vez. El corpus se actualiza solo una vez
por semana.</p>
<div class="tabla"><table><thead><tr><th>Institución</th><th class="n">Operaciones</th><th>Descargado</th><th>Fuente</th></tr></thead><tbody id="t-fuentes"></tbody></table></div>
<h2>Comentarios del equipo</h2>
<p class="nota">Análisis que les gustaría ver, dudas sobre una cifra, ideas de visualización. Se firman con el nombre
que escriban y los lee todo el equipo.</p>
<div class="filtros"><div><label>Sobre</label><select id="c-seccion">
<option>General</option><option>Explorador</option><option>Comparación entre bancos</option><option>Ventanillas</option>
<option>Países y sectores</option><option>Algo que me gustaría ver</option></select></div></div>
<textarea id="c-texto" rows="4" maxlength="4000" style="width:100%;box-sizing:border-box;padding:6px;border:1px solid var(--l);border-radius:4px;font:inherit"></textarea>
<p><button id="c-enviar">Enviar comentario</button> <span class="nota" id="c-estado"></span></p>
<div id="c-lista"></div>
<h2>Diez principales países</h2><div class="barras" id="g-paises"></div>
<h2>Diez principales sectores</h2>
<p class="nota" id="g-sectores-nota">Cada banco clasifica los sectores con su propio catálogo, así que no son comparables entre
bancos: elegí una institución para verlos. Al Banco Mundial se le saca el prefijo del año de su taxonomía (FY17).</p>
<div class="barras" id="g-sectores"></div>
<h2>Operaciones <span class="nota" id="t-nota"></span></h2>
<p><button id="b-csv">Descargar las filtradas como CSV</button> <span class="nota">El CSV trae todas las operaciones que
cumplen los filtros, no solo las 300 que se muestran abajo, con todas sus columnas.</span></p>
<p class="nota">Clic en el encabezado de una columna para ordenar; otro clic invierte el orden. Clic en la descripción para verla entera.</p>
<div class="tabla"><table><thead><tr><th data-o="anio_aprobacion">Año</th><th data-o="institucion">Institución</th><th data-o="nombre">Operación</th><th data-o="pais">País</th><th data-o="sector">Sector</th><th data-o="forma_financiamiento">Forma</th><th data-o="tipo_ventanilla">Ventanilla</th><th class="n" data-o="monto">USD M</th><th class="n" data-o="monto_desembolsado_usd">Desembolsado USD M</th><th>Moneda original</th><th>Descripción</th></tr></thead><tbody id="t-cuerpo"></tbody></table></div>
<script>__CARGADOR__
// P trae las columnas junto con los datos: así la página nunca interpreta datos nuevos con un orden
// de columnas viejo, aunque la página y los datos se publiquen en momentos distintos.
function iniciar(P,COM){
const C=P.columnas,D=P.datos,V=P.ventanillas,F=P.fuentes;
const i=Object.fromEntries(C.map((c,k)=>[c,k]));
const fmt=n=>n.toLocaleString('es-AR',{maximumFractionDigits:0});
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const $=id=>document.getElementById(id);
function opciones(sel,valores,todas){sel.innerHTML=(todas?'<option value="">'+todas+'</option>':'')+valores.map(v=>`<option>${v}</option>`).join('')}
const unicos=c=>[...new Set(D.map(r=>r[i[c]]).filter(v=>v!==null&&v!==''))].sort();
const NOMBRE={GBM:'Grupo Banco Mundial',GBID:'Grupo BID'};const nom=g=>NOMBRE[g]||g;
$('f-grupo').innerHTML='<option value="">Todos</option>'+unicos('banco_grupo').map(v=>`<option value="${v}">${nom(v)}</option>`).join('');
opciones($('f-forma'),unicos('forma_financiamiento'),'Todas');
// Los enlaces de MIGA no se muestran: el campo que publica lleva a otra página (H39).
// La institución depende del banco elegido, para que no se pueda pedir una combinación imposible.
function instituciones(){const g=$('f-grupo').value,actual=$('f-inst').value;
 const vs=[...new Set(D.filter(r=>!g||r[i.banco_grupo]===g).map(r=>r[i.institucion]))].sort();
 opciones($('f-inst'),vs,'Todas');$('f-inst').value=vs.includes(actual)?actual:'';}
instituciones();$('f-grupo').addEventListener('input',instituciones);
opciones($('f-vent'),['soberana','no_soberana','sin asignar'],'Todas');
const anios=unicos('anio_aprobacion');opciones($('f-desde'),anios);opciones($('f-hasta'),anios);
$('f-hasta').value=anios[anios.length-1];
function filtradas(){
 const g=$('f-grupo').value,s=$('f-inst').value,v=$('f-vent').value,d=+$('f-desde').value,h=+$('f-hasta').value,
 p=$('f-pais').value.toLowerCase(),t=$('f-texto').value.toLowerCase(),fo=$('f-forma').value;
 return D.filter(r=>(!g||r[i.banco_grupo]===g)&&(!s||r[i.institucion]===s)&&
  (!v||(v==='sin asignar'?!r[i.tipo_ventanilla]:r[i.tipo_ventanilla]===v))&&
  r[i.anio_aprobacion]>=d&&r[i.anio_aprobacion]<=h&&(!p||String(r[i.pais]||'').toLowerCase().includes(p))&&
  (!fo||r[i.forma_financiamiento]===fo)&&
  (!t||(String(r[i.nombre]||'')+' '+String(r[i.sector]||'')+' '+String(r[i.descripcion]||'')).toLowerCase().includes(t)));}
function barras(el,pares){const m=Math.max(1,...pares.map(x=>x[1]));
 el.innerHTML=pares.map(([k,v])=>`<div><span>${k}</span><span class="b" style="width:${100*v/m}%"></span><span class="n">${fmt(v)}</span></div>`).join('')||'<p class="nota">Sin datos</p>';}
const monto=r=>($('f-usd').value==='k'?r[i.monto_constante_usd]:r[i.monto_aprobado_usd])||0;
function sumar(f,c){const o={};f.forEach(r=>{const k=r[i[c]]||'sin dato';o[k]=(o[k]||0)+monto(r)/1e6});return o}
function mediana(xs){if(!xs.length)return 0;xs=[...xs].sort((a,b)=>a-b);const m=xs.length>>1;return xs.length%2?xs[m]:(xs[m-1]+xs[m])/2}
function porBanco(f,total){const g={};f.forEach(r=>{(g[r[i.institucion]]=g[r[i.institucion]]||[]).push(r)});
 return Object.entries(g).map(([k,rs])=>{const m=rs.reduce((a,r)=>a+monto(r),0)/1e6;
  const alc=rs.filter(r=>r[i.region]==='A').reduce((a,r)=>a+monto(r),0)/1e6;
  const pp={};rs.filter(r=>r[i.pais]&&r[i.region]&&r[i.region]!=='G').forEach(r=>{pp[r[i.pais]]=(pp[r[i.pais]]||0)+monto(r)});
  const orden=Object.entries(pp).sort((a,b)=>b[1]-a[1]),tp=orden.reduce((a,x)=>a+x[1],0);
  const top5=tp?100*orden.slice(0,5).reduce((a,x)=>a+x[1],0)/tp:0;
  return [k,rs.length,m,total?100*m/total:0,mediana(rs.filter(r=>r[i.monto_aprobado_usd]!==null).map(r=>monto(r)/1e6)),m?100*alc/m:0,top5,orden.length?orden[0][0]:'']})
  .sort((a,b)=>b[2]-a[2])}
const pct=n=>n.toLocaleString('es-AR',{maximumFractionDigits:1})+'%';
// Tablero integrado y uno por grupo bancario: cada botón fija el banco y muestra su ficha.
$('tableros').innerHTML='<span class="nota">Tablero: </span>'+['',...unicos('banco_grupo')].map(g=>`<button data-g="${g}">${g?nom(g):'Integrado'}</button>`).join('');
document.querySelectorAll('#tableros button').forEach(b=>b.onclick=()=>{$('f-grupo').value=b.dataset.g;$('f-grupo').dispatchEvent(new Event('input'))});
$('t-caf').innerHTML=(P.complemento_caf||[]).map(x=>`<tr><td>${x.anio}</td><td class="n">${fmt(x.informe_total_mm)}</td><td class="n">${fmt(x.corpus_soberano_mm+x.corpus_no_soberano_mm)}</td><td class="n">${fmt(x.complemento_soberano_mm)}</td><td class="n">${fmt(x.complemento_no_soberano_mm)}</td><td class="n">${pct(x.cobertura_pct)}</td></tr>`).join('');
function ficha(){const g=$('f-grupo').value;
 document.querySelectorAll('#tableros button').forEach(b=>b.classList.toggle('on',b.dataset.g===g));
 $('ficha').style.display=g&&P.fichas[g]?'block':'none';$('ficha').textContent=P.fichas[g]||'';
 $('caf-comp').style.display=g==='CAF'&&(P.complemento_caf||[]).length?'block':'none';}
$('f-grupo').addEventListener('input',ficha);ficha();
const VG=[...new Set(V.map(x=>x.grupo))];
$('t-vent-cab').innerHTML='<tr><th>Año</th>'+VG.map(g=>`<th class="n">${g}</th>`).join('')+'</tr>';
$('t-vent').innerHTML=[...new Set(V.map(x=>x.anio))].sort().map(a=>{const v=g=>{const x=V.find(y=>y.anio===a&&y.grupo===g);return x?pct(x.pct_no_soberana):''};
 return `<tr><td>${a}</td>${VG.map(g=>`<td class="n">${v(g)}</td>`).join('')}</tr>`}).join('');
let ORDEN={c:'monto',dir:-1};
const valor=(r,c)=>c==='monto'?monto(r):r[i[c]];
document.querySelectorAll('th[data-o]').forEach(th=>th.onclick=()=>{const c=th.dataset.o;
 ORDEN=ORDEN.c===c?{c,dir:-ORDEN.dir}:{c,dir:(c==='monto'||c==='anio_aprobacion'||c==='monto_desembolsado_usd')?-1:1};dibujar();});
function comparar(a,b){const x=valor(a,ORDEN.c),y=valor(b,ORDEN.c);
 if(x===null||x===undefined||x==='')return 1;if(y===null||y===undefined||y==='')return -1;
 return (typeof x==='number'&&typeof y==='number'?x-y:String(x).localeCompare(String(y),'es'))*ORDEN.dir;}
const FORMAS=[['prestamo','#111'],['donacion','#777'],['garantia','#aaa'],['otro','#ccc'],['mixto','#555'],['sin dato','#e6e6e6']];
$('g-forma-ley').innerHTML=FORMAS.map(([k,c])=>`<i style="background:${c}"></i>${k}`).join('');
$('t-fuentes').innerHTML=F.map(x=>`<tr><td>${x.institucion}</td><td class="n">${fmt(x.operaciones)}</td><td>${x.descargado}</td><td><a href="${x.fuente}" target="_blank" rel="noopener">${esc(x.fuente)}</a></td></tr>`).join('');
function dibujar(){
 const f=filtradas();const total=f.reduce((a,r)=>a+monto(r),0)/1e6;
 $('k-monto-et').textContent=$('f-usd').value==='k'?'Aprobado, USD M de 2025':'Aprobado, USD M';
 $('t-bancos').innerHTML=porBanco(f,total).map(b=>`<tr><td>${b[0]}</td><td class="n">${fmt(b[1])}</td><td class="n">${fmt(b[2])}</td><td class="n">${pct(b[3])}</td><td class="n">${b[4].toLocaleString('es-AR',{maximumFractionDigits:1})}</td><td class="n">${pct(b[5])}</td><td class="n">${pct(b[6])}</td><td>${b[7]}</td></tr>`).join('');
 $('k-ops').textContent=fmt(f.length);$('k-monto').textContent=fmt(total);
 $('k-des').textContent=fmt(f.filter(r=>r[i.monto_desembolsado_usd]!==null).length);
 $('k-pais').textContent=fmt(new Set(f.map(r=>r[i.pais]).filter(Boolean)).size);
 const pa=sumar(f,'anio_aprobacion'),ks=anios.filter(a=>a>=+$('f-desde').value&&a<=+$('f-hasta').value),m=Math.max(1,...ks.map(a=>pa[a]||0));
 $('g-anios').innerHTML=ks.map(a=>`<div title="${a}: ${fmt(pa[a]||0)}" style="height:${100*(pa[a]||0)/m}%"></div>`).join('');
 $('g-anios-et').innerHTML=ks.map(a=>`<span>${String(a).slice(2)}</span>`).join('');
 const pf={};f.forEach(r=>{const a=r[i.anio_aprobacion],k=r[i.forma_financiamiento]||'sin dato';(pf[a]=pf[a]||{})[k]=(pf[a][k]||0)+monto(r)});
 const mf=Math.max(1,...ks.map(a=>Object.values(pf[a]||{}).reduce((x,y)=>x+y,0)));
 $('g-forma').innerHTML=ks.map(a=>`<div style="height:100%">${FORMAS.map(([k,c])=>{const v=(pf[a]||{})[k]||0;return v?`<span title="${a}, ${k}: ${fmt(v/1e6)} M" style="height:${100*v/mf}%;background:${c}"></span>`:''}).join('')}</div>`).join('');
 $('g-forma-et').innerHTML=$('g-anios-et').innerHTML;
 const top=o=>Object.entries(o).sort((a,b)=>b[1]-a[1]).slice(0,10);
 barras($('g-paises'),top(sumar(f,'pais')));const unaInst=$('f-inst').value||new Set(f.map(r=>r[i.institucion])).size===1;
 const sinFY=o=>{const r={};Object.entries(o).forEach(([k,v])=>{const c=k.replace(/^FY\\d{2} - /,'');r[c]=(r[c]||0)+v});return r};
 if(unaInst)barras($('g-sectores'),top(sinFY(sumar(f,'sector'))));else $('g-sectores').innerHTML='';
 const orden=[...f].sort(comparar).slice(0,300);
 $('t-nota').textContent=f.length>300?`(las primeras 300 de ${fmt(f.length)} según el orden elegido)`:'';
 const mo=r=>r[i.moneda_original]&&r[i.moneda_original]!=='USD'?`${r[i.moneda_original]} ${fmt((r[i.monto_original]||0)/1e6)} M`:'';
 const de=r=>{const t=r[i.descripcion];if(!t)return '';const e=esc(t);return t.length>140?`<details><summary>${esc(t.slice(0,140))}...</summary>${e}</details>`:e};
 $('t-cuerpo').innerHTML=orden.map(r=>`<tr><td>${r[i.anio_aprobacion]}</td><td>${r[i.institucion]}</td><td>${r[i.url_proyecto]&&r[i.institucion]!=='MIGA'?`<a href="${r[i.url_proyecto]}" target="_blank" rel="noopener">${r[i.nombre]||'(sin nombre)'}</a>`:(r[i.nombre]||'')}</td><td>${r[i.pais]||''}</td><td>${r[i.sector]||''}</td><td>${r[i.forma_financiamiento]||''}</td><td>${(r[i.tipo_ventanilla]||'').replace('_',' ')}</td><td class="n">${r[i.monto_aprobado_usd]===null?'sin dato':fmt(monto(r)/1e6)}</td><td class="n">${r[i.monto_desembolsado_usd]===null?'':fmt(r[i.monto_desembolsado_usd]/1e6)}</td><td>${mo(r)}</td><td>${de(r)}</td></tr>`).join('');
}
$('b-csv').onclick=()=>{const q=v=>v===null?'':'"'+String(v).replace(/"/g,'""')+'"';
 const csv=[C.join(',')].concat(filtradas().map(r=>r.map(q).join(','))).join('\\n');
 const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));a.download='corpus-filtrado.csv';a.click();};
document.querySelectorAll('.filtros select,.filtros input').forEach(e=>{if(e.id!=='c-seccion')e.addEventListener('input',dibujar)});dibujar();
async function comentarios(){
 try{if(!COM)throw 0;const cs=await COM.listar();
  $('c-lista').innerHTML=cs.length?cs.map(c=>`<div class="kpi" style="margin:6px 0"><span class="nota">${esc(c.autor)} · ${esc(c.seccion)} · ${esc(c.creado)} UTC</span><p style="margin:4px 0 0;white-space:pre-wrap">${esc(c.texto)}</p></div>`).join(''):'<p class="nota">Todavía no hay comentarios.</p>';
 }catch(e){$('c-lista').innerHTML=COM?'<p class="nota">No se pudieron leer los comentarios.</p>':'<p class="nota">Los comentarios funcionan en la versión publicada, no en el archivo abierto desde la computadora.</p>';if(!COM)$('c-enviar').disabled=true}}
$('c-enviar').onclick=async()=>{const texto=$('c-texto').value.trim();if(!texto)return;$('c-estado').textContent='Enviando...';
 try{await COM.enviar($('c-seccion').value,texto);$('c-texto').value='';$('c-estado').textContent='Enviado.';comentarios();
 }catch(e){$('c-estado').textContent='No se pudo enviar: '+e.message}};
comentarios();
}
__ARRANQUE__
</script></body></html>
"""


def main() -> int:
    if not CORPUS.exists():
        raise SystemExit("falta el corpus. Correr antes: uv run python scripts/consolidar.py")
    df = ap.cargar()
    df["region"] = df["pais"].apply(ap.region_de).map(REGION)
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
    base = PAGINA.replace("__FECHA__", fecha)
    paquete = json.dumps({"columnas": COLUMNAS, "datos": df.values.tolist(), "ventanillas": ventanillas,
                          "fuentes": fuentes, "fichas": FICHAS,
                          "complemento_caf": ap.complemento_caf(ap.cargar()).drop(columns=["fuente_url"], errors="ignore")
                          .to_dict(orient="records")}, ensure_ascii=False, default=float)

    local = (base.replace("__INGRESO__", "").replace("__CARGADOR__", "")
             .replace("__ARRANQUE__", f"iniciar({paquete},null);"))
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(local, encoding="utf-8")
    print(f"Escrito {SALIDA.relative_to(RAIZ)}: {len(df):,} operaciones, {len(local) / 1e6:.1f} MB")

    if not PUBLICABLE:
        return 0
    web = (base.replace("__INGRESO__", INGRESO).replace("<script>__CARGADOR__", "</div><script type=\"module\">" + CARGADOR)
           .replace("__ARRANQUE__", ""))
    SALIDA_WEB.parent.mkdir(parents=True, exist_ok=True)
    SALIDA_WEB.write_text(web, encoding="utf-8")
    (SALIDA_WEB.parent / "datos.json").write_text(paquete, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
