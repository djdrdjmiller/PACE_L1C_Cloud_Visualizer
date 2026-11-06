import Plotly from 'plotly.js-dist-min';
import {liquidFigures,cloudbowFigures,colors} from './showcase-plots';
import './style.css';
import './showcase.css';
type Example={id:string;number:number;row:number;col:number;latitude:number;longitude:number;position:number[];diagnostics:string};
type Scenario={anchor:number;correction:string;images:string[];support:Record<string,boolean[]>};
type LeftMap={mode:string;quantity:string;label:string;image:string;scale:{minimum:number;center:number;maximum:number}|null;support:Record<string,boolean>};
type Manifest={title:string;examples:Example[];anchors:number[];scenarios:Scenario[];left_maps:LeftMap[];default_anchor:number;default_correction:string;aspect_ratio:number;model_preview:{enabled:boolean;provenance:unknown;policy:string}};
const root=document.querySelector<HTMLDivElement>('#showcase-app')!;
const repo='https://github.com/djdrdjmiller/PACE_L1C_Cloud_Visualizer';
const $=(id:string)=>document.getElementById(id)!;
const value=(id:string)=>($(id) as HTMLSelectElement).value;
const checked=(id:string)=>($(id) as HTMLInputElement).checked;
const fmt=(x:number|null|undefined)=>x==null?'Unavailable':Number(x).toPrecision(4);
async function json(path:string){const r=await fetch(path);if(!r.ok)throw Error(`Unable to load ${path} (${r.status})`);return r.json();}
let manifest:Manifest,selected:Example,diagnostic:any,revision=0;
const cache=new Map<string,any>();
function plot(id:string,traces:any[],x:string,y:string,range?:number[],extra:any={}){
  return Plotly.react(id,traces,{paper_bgcolor:'#fffefa',plot_bgcolor:'#fffefa',font:{family:'system-ui',size:11,color:'#253632'},margin:{l:60,r:20,t:15,b:145,autoexpand:false},xaxis:{title:{text:x},range,showline:true,mirror:true,gridcolor:'#e5e9e3'},yaxis:{title:{text:y},showline:true,mirror:true,gridcolor:'#e5e9e3'},legend:{orientation:'h',y:-.22,font:{size:10},entrywidth:.5,entrywidthmode:'fraction'},uirevision:selected.id,...extra},{responsive:true,displaylogo:false});
}
function maps(){
  const anchor=manifest.anchors[Number(value('anchor'))];
  const scenario=manifest.scenarios.find(s=>s.anchor===anchor&&s.correction===value('correction'))!;
  $('anchor-value').textContent=`${anchor.toFixed(1)}°`;
  $('anchor').setAttribute('aria-valuetext',`${anchor.toFixed(1)} degrees nominal angle`);
  const mode=value('left-mode'),quantity=value('li-quantity');
  const left=manifest.left_maps.find(m=>m.mode===mode&&(!mode.startsWith('liquid_index_')||m.quantity===quantity));
  const images=[...scenario.images],support=[...scenario.support[selected.id]];
  if(mode!=='oci_total'&&left){images[0]=left.image;support[0]=left.support[selected.id];}
  images.forEach((path,i)=>{($(`map-img-${i}`) as HTMLImageElement).src=path;$(`support-${i}`).textContent=support[i]?'Selected source bin has data.':'Selected source bin is missing in this map/preset.';});
  const title=mode==='oci_total'?'OCI total reflectance':left!.label;
  $('left-heading').textContent=title;($('map-img-0') as HTMLImageElement).alt=`${title} for the original scene`;
  $('left-note').textContent=mode==='oci_phase'?'Collocated native OCI cloud phase; original L1C-bin selection retained.':mode==='liquid_index'?'Reported GPC LI · independent of map correction and sector.':mode.startsWith('liquid_index_')?`Branch 1 TOA · ${quantity==='signed_q'?'−Q':'polarized magnitude'} · independent of map correction and sector.`:'';
  $('phase-key').hidden=mode!=='oci_phase';$('li-key').hidden=!mode.startsWith('liquid_index');
  if(left?.scale){$('li-min').textContent=fmt(left.scale.minimum);$('li-max').textContent=fmt(left.scale.maximum);}
  for(const i of [0,2]){const ring=$(`selected-ring-${i}`);ring.style.left=`${100*selected.position[0]}%`;ring.style.top=`${100*selected.position[1]}%`;ring.setAttribute('aria-label',`Selected example ${selected.number}, row ${selected.row}, column ${selected.col}`);}
}
function charts(){
  if(!diagnostic)return;
  const d=diagnostic,quantity=value('quantity'),branch=value('branch');
  const samples=d.harp2.samples.filter((s:any)=>s.wavelength===d.harp2.hyperangular_wavelength);
  const enabled=checked('cloudbow');
  const model=cloudbowFigures(d,enabled,quantity==='signed_q'&&branch!=='1');
  const observations=[0,1].filter(b=>branch==='both'||Number(branch)===b).map(b=>({x:samples.filter((s:any)=>s.branch===b).map((s:any)=>s.scattering_angle),y:samples.filter((s:any)=>s.branch===b).map((s:any)=>s[quantity]),mode:'markers',marker:{color:colors.observations[b],size:6,symbol:b?'diamond':'circle'},name:`Branch ${b+1} TOA`}));
  void plot('polar-chart',[...model.traces,...observations],'Scattering angle (°)',quantity==='dolp'?'DoLP':'TOA reflectance',[130,180]);
  $('model-note').textContent=model.notes.filter(Boolean).join(' ');
  const residualOn=enabled&&quantity==='signed_q'&&branch!=='1';
  $('residual-chart').hidden=!residualOn;
  if(residualOn)void plot('residual-chart',model.residuals,'Scattering angle (°)','Model − observed (−Q)',[130,180],{height:250,margin:{l:60,r:20,t:28,b:90,autoexpand:false},legend:{orientation:'h',y:-.42,font:{size:10},entrywidth:.5,entrywidthmode:'fraction'},title:{text:model.residuals.length?'Branch 1 · shared source-view residuals':'Residuals unavailable for selected bin',font:{size:11}}});
  const curve=d.liquid_index.branches[0].series[value('li-quantity')];
  const figures=liquidFigures(curve,checked('li-trapezoidal'));
  void plot('liquid-chart',figures.traces,'Scattering angle (°)','TOA reflectance',[115,165],{shapes:figures.shapes});
  void plot('liquid-integration-chart',figures.integration,'Scattering angle (°)','Cumulative LI',figures.range,{height:225,margin:{l:60,r:20,t:28,b:55},showlegend:false,title:{text:figures.method.status==='available'?`Normalized cumulative excess · LI ${fmt(figures.method.value)}`:'Integration unavailable · see support note',font:{size:11}}});
  $('li-values').textContent=`${checked('li-trapezoidal')?'Trapezoidal':'Discrete'} LI: ${fmt(figures.method.value)} · GPC: ${fmt(d.liquid_index.operational_value)} · Δ: ${fmt(figures.method.difference_from_operational)}`;
  $('li-note').textContent=figures.method.status==='available'?`Baseline n=${curve.baseline_counts.join('+')} · bow n=${curve.peak_count} · reference b(135°) · ${checked('li-trapezoidal')?'Linear interpolation; no extrapolation.':'Equal weight per measured bow view.'} Operational normalization/branch convention unverified.`:(curve.reason||figures.method.reason||'Integration unavailable');
  $('li-method').textContent=JSON.stringify({method:d.liquid_index.method,selected:curve},null,2);
  $('model-provenance').textContent=JSON.stringify({preview:manifest.model_preview,cloudbow:d.cloudbow},null,2);
  void plot('spectrum-chart',[{x:d.oci.wavelength,y:d.oci[value('spectrum')],mode:'lines',line:{color:'#356b61'},name:'Original OCI TOA'}],'Wavelength (nm)',value('spectrum')==='radiance'?'W m⁻² sr⁻¹ µm⁻¹':'TOA reflectance',undefined,{showlegend:false,margin:{l:60,r:20,t:15,b:55}});
  $('cloud-fields').replaceChildren();
  for(const [label,key] of [['Cloudbow radius (µm)','cloud_bow_droplet_effective_radius'],['Cloudbow variance','cloud_bow_droplet_effective_variance'],['Cloudbow fit correlation','cloud_bow_fit_correlation']]){const line=document.createElement('p');line.textContent=`${label}: ${fmt(d.cloud.fields?.[key]?.value)}`;$('cloud-fields').append(line);}
  $('cloud-quality').textContent=['cloud_bow_quality_retrieval_fail'].map(k=>`Cloudbow quality: ${d.cloud.fields?.[k]?.status??'unavailable'} · ${d.cloud.fields?.[k]?.flags?.join('; ')||''}`).join(' | ');
}
async function select(example:Example){
  selected=example;diagnostic=undefined;const request=++revision;
  document.querySelectorAll<HTMLButtonElement>('.example-marker').forEach(b=>{const active=b.dataset.bin===selected.id;b.setAttribute('aria-pressed',String(active));b.classList.toggle('active',active);});
  $('diagnostics').setAttribute('aria-busy','true');
  const label=`Example ${example.number} · Original row ${example.row}, column ${example.col} · ${example.latitude.toFixed(3)}°, ${example.longitude.toFixed(3)}°`;
  $('selection').textContent=`${label} · Loading diagnostics…`;maps();
  try{const d=cache.get(example.id)||await json(example.diagnostics);cache.set(example.id,d);if(request!==revision)return;diagnostic=d;$('selection').textContent=label;$('diagnostics').setAttribute('aria-busy','false');charts();}catch(e){if(request===revision)$('selection').textContent=String(e);}
}
async function start(){
  manifest=await json('data/manifest.json');
  root.innerHTML=`<header class="dashboard-header"><div class="dashboard-brand"><img class="mucloud-wordmark" src="branding/mucloud-wordmark-on-light.svg" alt="µCloud" width="150" height="36"><div class="dashboard-title"><h1>PACE L1C · Quicklook Dashboard</h1><small>${manifest.title}</small></div></div><div class="header-links"><span class="badge">Fixed-scene showcase</span><a class="dashboard-link" href="${repo}#installation-and-getting-started">Install the dashboard</a></div></header>
  <main class="showcase-main"><aside><label>Left map<select id="left-mode"><option value="oci_total">OCI total reflectance</option></select></label><label>Atmospheric Correction<select id="correction"></select></label><p class="quiet">Experimental molecular single scattering on classified land and water. LI, phase and diagnostic observations remain unchanged.</p><p class="quiet">Beauty · quicklook enhancement. Select a numbered bin in the middle map; open rings locate it in the other maps.</p><a href="data/manifest.json">Scene provenance</a><p class="quiet">Fixed original scene and marked bins. New scenes, arbitrary-bin inspection and unrestricted exports require the installed app. Cached cloudbow curves are a local-library preview; the phase library itself is excluded.</p></aside>
  <section><div class="maps">${['OCI total reflectance','HARP2 total reflectance','HARP2 polarized reflectance'].map((title,i)=>`<section class="panel"><h2 ${i===0?'id="left-heading"':''}>${title}</h2><div class="map showcase-map" id="map-${i}" style="aspect-ratio:${manifest.aspect_ratio}"><img id="map-img-${i}" alt="${title} for the original scene">${i!==1?`<span id="selected-ring-${i}" class="selected-ring" role="img"></span>`:''}</div><small id="support-${i}"></small>${i===0?'<p class="quiet" id="left-note"></p><div id="phase-key" class="phase-legend" hidden><span style="--phase:#a6aaa8">No mask</span><span style="--phase:#88c5eb">Clear</span><span style="--phase:#2da58a">Liquid</span><span style="--phase:#956bc2">Ice</span><span style="--phase:#e2a44c">Unknown cloud</span></div><div id="li-key" class="liquid-map-legend" hidden><span id="li-min">0</span><span class="liquid-colorbar"><span>0.3</span></span><span id="li-max">4</span><small>LI · white at 0.3</small></div>':''}</section>`).join('')}<section class="harp-slider"><div class="slider-head"><label for="anchor">HARP2 anchor nominal angle</label><output id="anchor-value" for="anchor"></output></div><input id="anchor" type="range" min="0" step="1" list="anchor-ticks" aria-label="Shared HARP2 nominal angle"><datalist id="anchor-ticks"></datalist><div class="slider-ends"><span id="anchor-min"></span><span id="anchor-state">Shared by both HARP2 panels</span><span id="anchor-max"></span></div></section></div>
  <div class="selection" id="selection" role="status" aria-live="polite"></div>
  <div class="diagnostics" id="diagnostics"><section class="panel showcase-diagnostic"><div class="showcase-tools"><h2>Liquid-index workspace · branch 1 · TOA</h2><label>TOA quantity<select id="li-quantity"><option value="signed_q">−Q scattering plane</option><option value="polarized">Polarized magnitude</option></select></label><label class="check"><input id="li-trapezoidal" type="checkbox">Trapezoidal integration</label><p id="li-values" class="liquid-values"></p></div><div id="liquid-chart" class="chart"></div><p id="li-note" class="quiet support-note"></p><div id="liquid-integration-chart"></div><details><summary>Liquid-index method & support</summary><pre id="li-method"></pre></details></section>
  <section class="panel showcase-diagnostic"><div class="showcase-tools"><h2>Cloud microphysics · HARP2 angular observations</h2><span class="badge">Cached local-library preview</span><div class="pair"><label>Quantity<select id="quantity"><option value="signed_q">−Q scattering plane</option><option value="polarized">Polarized magnitude</option><option value="dolp">DoLP</option></select></label><label>Branch<select id="branch"><option value="0">1 · comparison</option><option value="1">2 · sanity check</option><option value="both">Both</option></select></label></div><fieldset class="overlay-controls"><legend>Overlay · stored cloudbow</legend><label class="check"><input id="cloudbow" type="checkbox">Cloudbow</label></fieldset></div><div id="polar-chart" class="chart"></div><p class="quiet support-note" id="model-note"></p><div id="residual-chart" hidden></div><p class="quiet">Model code is in the repo; public phase-library access is not yet available. This preview caches only these original bins. Observations stay TOA. Branch 2 is a sanity check.</p><details><summary>Cached model provenance & support</summary><pre id="model-provenance"></pre></details></section>
  <section class="panel spectrum-panel"><h2>OCI spectrum · selected original bin</h2><label class="spectrum-control">Quantity<select id="spectrum"><option value="total">TOA reflectance</option><option value="radiance">Radiance</option></select></label><div id="spectrum-chart" class="chart"></div></section></div><section class="panel cloud-properties"><h2>Selected-bin reported cloud microphysics · GPC</h2><div id="cloud-fields"></div><p class="quiet" id="cloud-quality"></p></section></section></main>`;
  for(const mode of [...new Set(manifest.left_maps.map(m=>m.mode))]){const m=manifest.left_maps.find(m=>m.mode===mode)!;const option=document.createElement('option');option.value=mode;option.textContent=m.label;$('left-mode').append(option);}
  const corrections=[...new Set(manifest.scenarios.map(s=>s.correction))];$('correction').innerHTML=corrections.map(c=>`<option value="${c}">${c==='toa'?'Uncorrected TOA':'Experimental Rayleigh'}</option>`).join('');($('correction') as HTMLSelectElement).value=manifest.default_correction;
  const slider=$('anchor') as HTMLInputElement;
  slider.max=String(manifest.anchors.length-1);slider.value=String(manifest.anchors.indexOf(manifest.default_anchor));
  $('anchor-ticks').innerHTML=manifest.anchors.map((a,i)=>`<option value="${i}" label="${a.toFixed(1)}°"></option>`).join('');
  $('anchor-min').textContent=`${manifest.anchors[0].toFixed(1)}°`;
  $('anchor-max').textContent=`${manifest.anchors.at(-1)!.toFixed(1)}°`;
  slider.oninput=maps;

  for(const e of manifest.examples){const b=document.createElement('button');b.className='example-marker';b.textContent=String(e.number);b.dataset.bin=e.id;b.style.left=`${100*e.position[0]}%`;b.style.top=`${100*e.position[1]}%`;b.setAttribute('aria-label',`Select example ${e.number}, original row ${e.row}, column ${e.col}`);b.onclick=()=>void select(e);$('map-1').append(b);}
  for(const id of ['correction','left-mode'])$(id).onchange=maps;
  for(const id of ['quantity','branch','li-trapezoidal','spectrum'])$(id).onchange=charts;
  $('li-quantity').onchange=()=>{maps();charts();};
  for(const id of ['cloudbow']){
    const control=$(id) as HTMLInputElement;control.disabled=!manifest.model_preview.enabled;
    control.onchange=()=>{if(control.checked){($('quantity') as HTMLSelectElement).value='signed_q';($('branch') as HTMLSelectElement).value='0';}charts();};
  }
  await select(manifest.examples[6]||manifest.examples[0]);
}
start().catch(e=>{root.textContent=`Unable to open showcase: ${e}`;});
