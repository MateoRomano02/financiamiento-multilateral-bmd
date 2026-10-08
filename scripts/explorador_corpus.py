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

COLUMNAS = ["banco_grupo", "institucion", "tipo_ventanilla", "nombre", "pais", "anio_aprobacion",
            "estado", "monto_aprobado_usd", "monto_desembolsado_usd", "sector", "url_proyecto",
            "monto_constante_usd", "region"]

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
.anios-et{display:flex;gap:4px;font-size:11px;color:var(--s)}.anios-et span{flex:1;text-align:center}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{border-bottom:1px solid var(--l);padding:4px;text-align:left;vertical-align:top}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.tabla{overflow-x:auto}button{padding:6px 10px;border:1px solid var(--t);background:var(--b);border-radius:4px;cursor:pointer}
</style></head><body>
<h1>Explorador del corpus de financiamiento multilateral</h1>
<p class="nota">Proyecto CIAI Nº 34, UNSAM. Operaciones aprobadas 2014 a 2025, sin canceladas, armonizadas desde
las fuentes oficiales de cada banco. Descargas del __FECHA__. Montos aprobados en millones de dólares, corrientes o constantes de 2025 según el selector.
Sectores tal como los nombra cada banco. Ojo: la IFC anota el tope entero de algunas facilidades marco en cada banco participante, así que sus montos en mercados financieros están inflados. Borrador de trabajo, no para citar.</p>
<div class="filtros">
<div><label>Grupo</label><select id="f-grupo"></select></div>
<div><label>Institución</label><select id="f-inst"></select></div>
<div><label>Ventanilla</label><select id="f-vent"></select></div>
<div><label>Desde</label><select id="f-desde"></select></div>
<div><label>Hasta</label><select id="f-hasta"></select></div>
<div><label>País contiene</label><input id="f-pais" placeholder="Argentina"></div>
<div><label>Nombre o sector contiene</label><input id="f-texto" placeholder="solar, energy"></div>
<div><label>Dólares</label><select id="f-usd"><option value="c">Corrientes</option><option value="k">Constantes de 2025</option></select></div>
</div>
<div class="kpis">
<div class="kpi"><span class="nota">Operaciones</span><b id="k-ops"></b></div>
<div class="kpi"><span class="nota" id="k-monto-et">Aprobado, USD M</span><b id="k-monto"></b></div>
<div class="kpi"><span class="nota">Con desembolso publicado</span><b id="k-des"></b></div>
<div class="kpi"><span class="nota">Países</span><b id="k-pais"></b></div>
</div>
<h2>Monto aprobado por año</h2><div class="anios" id="g-anios"></div><div class="anios-et" id="g-anios-et"></div>
<h2>Comparación entre bancos</h2>
<p class="nota">Con los filtros elegidos. Cinco principales: porción del monto que se llevan los cinco países que más
reciben, sin contar los agregados sin país. A ALC: incluye los agregados regionales de la región.</p>
<div class="tabla"><table><thead><tr><th>Institución</th><th class="n">Operaciones</th><th class="n">USD M</th>
<th class="n">% del total</th><th class="n">Monto mediano</th><th class="n">A ALC</th><th class="n">Cinco principales</th>
<th>Principal receptor</th></tr></thead><tbody id="t-bancos"></tbody></table></div>
<h2>Ventanilla no soberana, por grupo</h2>
<p class="nota">Participación de la ventanilla no soberana sobre el total aprobado de cada grupo, con el criterio del
informe: MIGA y BID Lab fuera de las dos categorías y sin los topes de facilidad repetidos de la IFC. No cambia con
los filtros. En 2014 y 2015 la cartera privada del BID figura como soberana (ver informe v3, sección 2).</p>
<div class="tabla"><table><thead><tr><th>Año</th><th class="n">Grupo Banco Mundial</th><th class="n">Grupo BID</th></tr></thead><tbody id="t-vent"></tbody></table></div>
<h2>Diez principales países</h2><div class="barras" id="g-paises"></div>
<h2>Diez principales sectores</h2><div class="barras" id="g-sectores"></div>
<h2>Operaciones <span class="nota" id="t-nota"></span></h2>
<p><button id="b-csv">Descargar las filtradas como CSV</button></p>
<div class="tabla"><table><thead><tr><th>Año</th><th>Institución</th><th>Operación</th><th>País</th><th>Sector</th><th class="n">USD M</th></tr></thead><tbody id="t-cuerpo"></tbody></table></div>
<script>
const C=__COLUMNAS__, D=__DATOS__, V=__VENTANILLAS__;
const i=Object.fromEntries(C.map((c,k)=>[c,k]));
const fmt=n=>n.toLocaleString('es-AR',{maximumFractionDigits:0});
const $=id=>document.getElementById(id);
function opciones(sel,valores,todas){sel.innerHTML=(todas?'<option value="">'+todas+'</option>':'')+valores.map(v=>`<option>${v}</option>`).join('')}
const unicos=c=>[...new Set(D.map(r=>r[i[c]]).filter(v=>v!==null&&v!==''))].sort();
opciones($('f-grupo'),unicos('banco_grupo'),'Todos');opciones($('f-inst'),unicos('institucion'),'Todas');
opciones($('f-vent'),['soberana','no_soberana','sin asignar'],'Todas');
const anios=unicos('anio_aprobacion');opciones($('f-desde'),anios);opciones($('f-hasta'),anios);
$('f-hasta').value=anios[anios.length-1];
function filtradas(){
 const g=$('f-grupo').value,s=$('f-inst').value,v=$('f-vent').value,d=+$('f-desde').value,h=+$('f-hasta').value,
 p=$('f-pais').value.toLowerCase(),t=$('f-texto').value.toLowerCase();
 return D.filter(r=>(!g||r[i.banco_grupo]===g)&&(!s||r[i.institucion]===s)&&
  (!v||(v==='sin asignar'?!r[i.tipo_ventanilla]:r[i.tipo_ventanilla]===v))&&
  r[i.anio_aprobacion]>=d&&r[i.anio_aprobacion]<=h&&(!p||String(r[i.pais]||'').toLowerCase().includes(p))&&
  (!t||(String(r[i.nombre]||'')+' '+String(r[i.sector]||'')).toLowerCase().includes(t)));}
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
$('t-vent').innerHTML=[...new Set(V.map(x=>x.anio))].map(a=>{const v=g=>{const x=V.find(y=>y.anio===a&&y.grupo===g);return x?pct(x.pct_no_soberana):''};
 return `<tr><td>${a}</td><td class="n">${v('Grupo Banco Mundial')}</td><td class="n">${v('Grupo BID')}</td></tr>`}).join('');
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
 const top=o=>Object.entries(o).sort((a,b)=>b[1]-a[1]).slice(0,10);
 barras($('g-paises'),top(sumar(f,'pais')));barras($('g-sectores'),top(sumar(f,'sector')));
 const orden=[...f].sort((a,b)=>monto(b)-monto(a)).slice(0,300);
 $('t-nota').textContent=f.length>300?`(las 300 de mayor monto de ${fmt(f.length)})`:'';
 $('t-cuerpo').innerHTML=orden.map(r=>`<tr><td>${r[i.anio_aprobacion]}</td><td>${r[i.institucion]}</td><td>${r[i.url_proyecto]?`<a href="${r[i.url_proyecto]}" target="_blank" rel="noopener">${r[i.nombre]||'(sin nombre)'}</a>`:(r[i.nombre]||'')}</td><td>${r[i.pais]||''}</td><td>${r[i.sector]||''}</td><td class="n">${r[i.monto_aprobado_usd]===null?'sin dato':fmt(monto(r)/1e6)}</td></tr>`).join('');
}
$('b-csv').onclick=()=>{const q=v=>v===null?'':'"'+String(v).replace(/"/g,'""')+'"';
 const csv=[C.join(',')].concat(filtradas().map(r=>r.map(q).join(','))).join('\\n');
 const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));a.download='corpus-filtrado.csv';a.click();};
document.querySelectorAll('select,input').forEach(e=>e.addEventListener('input',dibujar));dibujar();
</script></body></html>
"""


def main() -> int:
    if not CORPUS.exists():
        raise SystemExit("falta el corpus. Correr antes: uv run python scripts/consolidar.py")
    df = ap.cargar()
    df["region"] = df["pais"].apply(ap.region_de).map(REGION)
    df.loc[~df["pais"].apply(ap.es_pais_real) & df["region"].isna(), "region"] = "G"
    ventanillas = ap.ventanillas(df).to_dict(orient="records")
    df = df[COLUMNAS].copy()
    df["anio_aprobacion"] = df["anio_aprobacion"].astype(int)
    df["monto_constante_usd"] = df["monto_constante_usd"].round(0)
    df = df.astype(object).where(df.notna(), None)
    fecha = date.fromtimestamp(CORPUS.stat().st_mtime).strftime("%d/%m/%Y")
    html = (PAGINA.replace("__FECHA__", fecha)
            .replace("__COLUMNAS__", json.dumps(COLUMNAS))
            .replace("__VENTANILLAS__", json.dumps(ventanillas, ensure_ascii=False))
            .replace("__DATOS__", json.dumps(df.values.tolist(), ensure_ascii=False)))
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(html, encoding="utf-8")
    print(f"Escrito {SALIDA.relative_to(RAIZ)}: {len(df):,} operaciones, {len(html) / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
