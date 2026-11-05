import Plotly from 'plotly.js-dist-min';

type Channel={view:number;band:number;wavelength:number;angle:number};
type OCIChannel=Omit<Channel,'angle'> & {angle:number|null;angle_source?:string};
type Sample=Channel & Record<string,number|null>;
type Recipe={left_mode:string;correction:string;polar_rayleigh:boolean;rayleigh_land:boolean;extrapolate_surface:boolean;projection:string;selected:number[];crop:number[]|null;oci_targets:number[];harp_targets:number[];manual_views:number[]|null;anchor_angle:number;third_quantity:string;diagnostic_quantity:string;diagnostic_axis:string;spectrum_quantity:string;stretch:Record<string,number[]>;preset:string;title:string;[key:string]:unknown};
type Fit={signed_rayleigh?:number[];rayleigh_status?:string;status:string;reason?:string;branch:number;theta:number[];signed_q:number[];signed_components:number[][];signed_full_modes:number[][];signed_full_contributions:number[][];signed_mixture:number[];observed_theta:number[];residual_signed_q:number[];mode_ids:number[];sample_count:number;rmse:number|null;warnings:string[]};
type CloudField={value:number|null;units:string;description:string;status:string;flags?:string[]};
type Residuals={branch:number;theta:number[];sample_count:number;series:Record<string,{status:string;reason?:string;residual_signed_q:number[];rmse:number|null}>};
type LiquidCurve={fallback_reason?:string;crossings?:{angle:number}[]|null;boundaries?:{angle:number;kind:string}[]|null;window_degrees:number[]|null;discrete_width_factor:number;status:string;reason:string|null;theta:number[];observed:number[];baseline:number[]|null;baseline_mask:boolean[];peak_mask:boolean[];peak_theta?:number[];peak_excess?:number[];reference_angle?:number;normalization_baseline?:number;baseline_counts:number[];peak_count:number;warnings:string[];discrete:{status:string;value:number|null;sum_excess?:number;mean_excess?:number;difference_from_operational?:number|null};trapezoidal:{status:string;reason?:string;value:number|null;theta?:number[];observed?:number[];baseline?:number[];excess?:number[];integral_reflectance_degrees?:number;difference_from_operational?:number|null}};
type LiquidIndex={wavelength_nm:number;operational_value:number|null;method:unknown;branches:{branch:number;series:Record<string,LiquidCurve>}[]};
type Diagnostics={liquid_index:LiquidIndex;residuals:Residuals;rft:{status:string;reason?:string;branches?:Fit[];thick_branches?:Fit[];modes?:{mode:number;fraction:number|null;scattering_weight?:number}[]};cloud:{status:string;reason?:string;source?:{product_name:string};fields?:Record<string,CloudField>};selected:number[];latitude:number;longitude:number;oci:{wavelength:number[];total:(number|null)[];radiance:(number|null)[]};harp2:{samples:Sample[];branch_policy:string;hyperangular_wavelength:number};cloudbow:{status:string;reason?:string;theta?:number[];signed_q?:number[];radius_um?:number;variance?:number}};
type Render={aspect_ratio:number;layers:string[];width:number;height:number;marker:number[];render_id:string;labels:string[];bounds:number[];native_evidence:unknown;provenance:{oci_channels:OCIChannel[];harp_channels:Channel[];maximum_angle_span:number;angle_warning:boolean;correction_coverage?:Record<string,{valid_bins:number;total_bins:number;estimated_boundary_bins:number;land_toa_bins:number;unknown_toa_bins:number;extended_surface_eligible_bins:number}>|null;liquid_index_scale?:{minimum:number;center:number;maximum:number}|null;scattering_contours?:{channel:Channel}|null}};
const $=<T extends HTMLElement=HTMLElement>(id:string)=>document.getElementById(id) as T;
const input=(id:string)=>$<HTMLInputElement>(id);
const plotColors={observations:['#0072B2','#E69F00'],rft:'#CC007A',modes:['#00A6A6','#7B4DFF'],cloudbow:'#303030'};
const app=$('app');
app.innerHTML=`<header class="dashboard-header"><div class="dashboard-brand"><img class="mucloud-wordmark" src="/branding/mucloud-wordmark-on-light.svg" alt="µCloud" width="150" height="36"><div class="dashboard-title"><h1>PACE L1C · Quicklook Dashboard</h1><small>OCI + HARP2 · Original L1C bins</small></div></div><div class="header-links"><a class="dashboard-link" href="/?setup=1">Choose scene</a><span class="badge">Uncorrected TOA</span><div id="status" role="status">Opening local pair…</div></div></header>
<main><aside><section><label class="first-control">Projection<select id="projection"><option value="plate_carree">Plate Carrée</option><option value="laea">Regional equal area</option><option value="native">Native source swath</option></select></label><label class="check" title="Actual HARP2 red-view scattering angle, shared across the two HARP2 maps"><input id="scattering-contours" type="checkbox">Scat contours · 10°</label><div id="contour-source" class="quiet"></div><label>Atmospheric Correction<select id="correction"><option value="toa">Uncorrected TOA</option><option value="rayleigh" disabled>Rayleigh · experimental</option></select></label><small id="correction-note"></small><div id="identity" class="quiet"></div><details><summary>Crop original bins</summary><label>Row start, stop<input id="rows" placeholder="0, 396"></label><label>Column start, stop<input id="cols" placeholder="0, 519"></label><button id="crop">Apply crop</button><button id="reset-crop">Full scene</button></details></section>
<section><h2>Shared HARP2 sectors</h2><label>RGB preset<select id="harp-preset"><option value="670,550,440">Visible · green anchors</option><option value="865,550,440">865 / 550 / 440</option><option value="865,670,440">865 / 670 / 440 · blue anchors</option></select></label><details><summary>Manual source sectors</summary><div id="manual"></div><button id="manual-apply">Apply source views</button><button id="manual-reset">Use anchors</button></details><label>Left map<select id="left-mode"><option value="oci_total">OCI total reflectance</option><option value="oci_phase" disabled>OCI cloud phase</option><option value="liquid_index" disabled>GPC liquid index</option><option value="liquid_index_discrete">Calculated LI · discrete</option><option value="liquid_index_trapezoidal">Calculated LI · trapezoidal</option></select></label><label>Total map<select id="harp-mode"><option value="rgb">RGB</option><option value="single">Single band · red source</option></select></label><label>Third map<select id="third"><option value="polarized">Polarized magnitude RGB</option><option value="dolp">DoLP RGB</option><option value="signed_q">−Q scattering-plane · red</option><option value="signed_u">−U scattering-plane · red</option></select></label><div id="angle-warning" class="warning"></div></section>
<section><h2>Display enhancement</h2><label>Preset<select id="enhance"><option value="comparison">Fixed comparison</option><option value="beauty">Beauty · quicklook</option></select></label><details><summary>Customize beauty</summary><p class="preset-note">Fixed quicklook stretch; adjusts display only.</p><label>Quantity<select id="stretch-quantity"><option value="total">Total</option><option value="polarized">Polarized</option><option value="dolp">DoLP</option><option value="signed_q">Signed Q</option><option value="signed_u">Signed U</option></select></label><label>Low, high, gamma<input id="stretch" value="0,1,1"></label><button id="stretch-apply">Save beauty</button><button id="beauty-reset">Reset quicklook</button></details></section></aside>
<section><div class="maps">${['OCI total reflectance','HARP2 total reflectance','HARP2 polarimetry'].map((s,i)=>`<article class="panel"><h2>${s}</h2><div id="channels-${i}" class="channels quiet"></div><div class="map" id="map-${i}" tabindex="0" aria-label="${s}; click selects an original bin"><img id="image-${i}" alt="${s} projected source cells"><span id="marker-${i}" class="marker">+</span></div><small id="map-note-${i}">No scene loaded</small>${i===0?'<div id="phase-legend" class="phase-legend" hidden><span style="--phase:#a6aaa8">No mask</span><span style="--phase:#88c5eb">Clear</span><span style="--phase:#2da58a">Liquid</span><span style="--phase:#956bc2">Ice</span><span style="--phase:#e2a44c">Unknown cloud</span></div><div id="liquid-map-legend" class="liquid-map-legend" hidden><span id="liquid-map-min">0</span><span class="liquid-colorbar"><span id="liquid-map-center">0.3</span></span><span id="liquid-map-max">1</span><small>LI · white at 0.3</small></div>':''}</article>`).join('')}<section class="oci-channels"><label>OCI RGB targets (nm)<input id="oci-targets" value="645,555,443" aria-label="OCI RGB targets in nanometers"></label><button id="oci-apply">Apply</button></section><section class="harp-slider"><div class="slider-head"><label for="anchor">HARP2 anchor nominal angle</label><output id="anchor-value"></output></div><input id="anchor" type="range" min="0" max="9" step="1" list="anchor-ticks" aria-label="HARP2 anchor nominal angle"><datalist id="anchor-ticks"></datalist><div class="slider-ends"><span id="anchor-min"></span><span id="anchor-state">Shared by both HARP2 panels</span><span id="anchor-max"></span></div></section></div>
<div class="selection" id="selected">Choose an original bin on any map.</div>
<div class="diagnostics"><article class="panel diagnostic-panel liquid-panel"><div class="diagnostic-header"><h2 id="liquid-heading">HARP2 · Liquid index · TOA</h2><div class="liquid-controls"><label>Quantity<select id="liquid-quantity"><option value="signed_q">−Q scat</option><option value="polarized">Pol mag</option><option value="dolp">DoLP</option></select></label><label>Branch<select id="liquid-branch" disabled><option value="1">1 · LI observations</option></select></label><label class="check"><input id="liquid-trapezoidal" type="checkbox">Trapezoidal integration</label></div><div id="liquid-values" class="liquid-values" aria-live="polite"></div></div><div class="chart" id="liquid-chart"></div><div class="diagnostic-footer"><div id="liquid-note" class="quiet"></div><div id="liquid-integration-chart"></div><details><summary>Liquid-index method & support</summary><pre id="liquid-method"></pre></details></div></article><article class="panel diagnostic-panel"><div class="diagnostic-header"><h2 id="polar-heading">HARP2 · Multiangular polarization</h2><div class="polar-controls"><label>Quantity<select id="quantity"><option value="polarized">Pol mag</option><option value="dolp">DoLP</option><option value="signed_q">−Q scat</option><option value="signed_u">−U scat</option></select></label><label>Axis<select id="axis"><option value="scattering_angle">Scat (°)</option><option value="angle">Sector (°)</option></select></label><label>Branch<select id="branch"><option value="both">Both</option><option value="1">1</option><option value="2">2</option></select></label><fieldset class="overlay-controls"><legend>Overlays · cloudbow A/B/C; RFT thick cloud</legend><label class="check"><input id="cloudbow" type="checkbox">Cloudbow</label><label class="check"><input id="rft" type="checkbox">RFT refl.</label><label class="check"><input id="rft-components" type="checkbox">RFT component</label><label class="check"><input id="rft-p12" type="checkbox">RFT P12</label></fieldset></div></div><div class="chart" id="polar-chart"></div><div class="diagnostic-footer"><small id="cloudbow-note">Discrete observations · exploratory branches.</small><small>Number fractions · Csca weighted</small><div id="rft-component-key" class="quiet" hidden>Magenta: RFT refl. · teal dashes: mode 0 · violet dash-dot: mode 1. Droplet contributions × 1.61 (1 + 0.5 + 0.1 + 0.01), plus Rayleigh, sum to RFT refl.; no A/B/C, ω=1. Amber: Rayleigh. Dotted: P12 with cloudbow A/B/C. Experimental; LUT normalization is recorded in provenance.</div><div id="rft-weights" class="quiet"></div><div id="rft-support" class="quiet"></div><div id="residual-chart" hidden></div><details><summary>RFT model, support & provenance</summary><pre id="rft-model"></pre></details><details><summary>Cloudbow model & provenance</summary><pre id="cloudbow-model"></pre></details></div></article><article class="panel diagnostic-panel spectrum-panel"><div class="diagnostic-header"><h2>OCI spectrum</h2><label class="spectrum-control">Quantity<select id="spectrum"><option value="total">TOA reflectance</option><option value="radiance">Radiance</option></select></label></div><div class="chart" id="spectrum-chart"></div><div class="diagnostic-footer quiet">All measured OCI wavelengths · selected original bin</div></article></div>
<section class="panel cloud-properties"><h2>Selected-bin cloud properties · GPC</h2><div id="cloud-summary" class="quiet"></div><div id="cloud-fields"></div><div id="cloud-quality"></div></section>
<details><summary>Selected-bin geometry, quality & canonical values</summary><pre id="raw"></pre></details>
<section class="panel exports"><label>Composition<select id="layout"><option value="diagnostics">Maps + diagnostics</option><option value="maps">Three maps</option><option value="one">Left map</option></select></label><label>Size preset<select id="size"><option value="paper">Paper · 180 mm</option><option value="presentation">Presentation · 16:9</option></select></label><label>Width (mm)<input id="width" type="number" value="180"></label><label>Height (mm)<input id="height" type="number" value="240"></label><label>DPI<input id="dpi" type="number" value="300"></label><label>Title<input id="title" value="PACE L1C · uncorrected TOA"></label><button id="export">Export PNG + PDF</button><button id="recipe">Save recipe</button><label>Restore recipe<input id="restore" type="file" accept=".json"></label><div id="export-links" class="export-links"></div></section><details><summary>Projection & matching evidence</summary><pre id="evidence"></pre></details></section></main>`;

let recipe:Recipe, current:Render|undefined, diagnostics:Diagnostics|undefined;
const renderClientId=crypto.randomUUID();
let seq=0, selectionSeq=0, controller:AbortController|undefined;
let channels:Channel[]=[];
let anchorAngles:number[]=[];
let sliderTimer:ReturnType<typeof setTimeout>|undefined;
let identities:unknown;
let rayleighUnavailable='Rayleigh boundary cache not loaded. Select Prepare experimental Rayleigh / OCI phase in scene setup.';
function persist(){if(recipe&&identities)localStorage.setItem('pace-scene',JSON.stringify({inputs:identities,recipe}));}
const comparison={total:[0,1,1],polarized:[0,.15,1],dolp:[0,1,1],signed_q:[-.15,.15,1],signed_u:[-.15,.15,1]};
// Fixed quicklook recipe, visually checked on the benchmark; not a physical calibration.
const beautyDefaults={total:[0,.8,1.6],polarized:[0,.12,1.4],dolp:[0,1,1],signed_q:[-.15,.15,1],signed_u:[-.15,.15,1]};
function beautyPreset(){
  const saved=localStorage.getItem('pace-beauty-v1');
  if(saved)return JSON.parse(saved);
  const legacy=localStorage.getItem('pace-beauty');
  if(legacy&&JSON.stringify(JSON.parse(legacy))!==JSON.stringify(comparison)){
    localStorage.setItem('pace-beauty-v1',legacy);return JSON.parse(legacy);
  }
  return structuredClone(beautyDefaults);
}
function syncStretchEditor(){input('stretch').value=recipe.stretch[input('stretch-quantity').value].join(',');}

function status(s:string,error=false){$('status').textContent=s;$('status').className=error?'error':'';}
async function api<T>(path:string,data?:unknown,signal?:AbortSignal):Promise<T>{const r=await fetch(path,{method:data?'POST':'GET',headers:data?{'Content-Type':'application/json'}:undefined,body:data?JSON.stringify(data):undefined,signal});if(r.status===499)throw new DOMException('Superseded render','AbortError');if(!r.ok){const e=await r.json();throw new Error(e.detail||r.statusText);}return r.json();}
function values(id:string){return input(id).value.split(',').map(Number);}
function run(fn:()=>Promise<void>){void fn().catch(e=>{if(e.name!=='AbortError')status(e.message,true)});}
async function render(){
  const generation=++seq;controller?.abort();controller=new AbortController();
  status(recipe.left_mode.startsWith('liquid_index_')?'Calculating/rendering liquid index from original views… first calculation is cached.':'Rendering original source cells…');
  const maps=document.querySelector('.maps')!;maps.setAttribute('aria-busy','true');$('map-0').classList.add('render-pending');
  $('map-note-0').textContent='Updating selected map… previous image shown until ready';
  let result:Render;
  try{result=await api<Render>('/api/render',{recipe:structuredClone(recipe),width:560,height:420,client_id:renderClientId,generation},controller.signal);}
  finally{if(generation===seq){maps.setAttribute('aria-busy','false');$('map-0').classList.remove('render-pending');}}
  if(generation!==seq)return;
  current=result;persist();
  result.layers.forEach((src,i)=>{
    const image=$<HTMLImageElement>(`image-${i}`);image.src=src;image.style.aspectRatio=String(result.aspect_ratio);
    const marker=$(`marker-${i}`);marker.style.left=`${result.marker[0]/(result.width-1)*100}%`;marker.style.top=`${result.marker[1]/(result.height-1)*100}%`;
    let cc=i===0?result.provenance.oci_channels:result.provenance.harp_channels;
    const scalar=(i===1&&recipe.harp_mode==='single')||(i===2&&recipe.third_quantity.startsWith('signed'));
    if(scalar)cc=cc.slice(0,1);
    $(`channels-${i}`).textContent=cc.map(c=>`${c.wavelength.toFixed(1)} nm${i&&c.angle!==null?` / ${c.angle.toFixed(1)}°`:''}`).join(' · ');
    const limits=recipe.stretch[i===2?recipe.third_quantity:'total'];
    $(`map-note-${i}`).textContent=scalar?`${i===2?`${recipe.polar_rayleigh?'Rayleigh approx · ':''}− scattering-plane reflectance`:recipe.correction!=='toa'?recipe.correction.replaceAll('_',' + ')+' approx':'TOA reflectance'} · scale ${limits[0]} to ${limits[1]}`:`${recipe.projection} · ${i<2&&recipe.correction!=='toa'?recipe.correction.replaceAll('_',' + ')+' approx':i===2&&recipe.polar_rayleigh?'Rayleigh approx':'TOA'} · missing cells transparent`;
  });
  const phase=recipe.left_mode==='oci_phase',liquid=recipe.left_mode.startsWith('liquid_index');
  const leftTitle=phase?'OCI cloud phase':liquid?(recipe.left_mode==='liquid_index'?'GPC liquid index':'Calculated liquid index'):'OCI total reflectance';
  $('map-0').closest('article')!.querySelector('h2')!.textContent=leftTitle;
  $('map-0').setAttribute('aria-label',`${leftTitle}; click selects an original bin`);
  $<HTMLImageElement>('image-0').alt=`${leftTitle} at original L1C bins`;
  updateAnchorState();
  $('phase-legend').hidden=!phase;input('harp-mode').disabled=false;
  $('liquid-map-legend').hidden=!liquid;
  document.querySelector<HTMLElement>('.oci-channels')!.hidden=phase||liquid;
  if(liquid){const operational=recipe.left_mode==='liquid_index';$('channels-0').textContent=operational?'cloud_liquid_index · operational GPC':`135–145° · ${recipe.left_mode.endsWith('trapezoidal')?'Trapezoidal':'Discrete'} · ${recipe.liquid_index_quantity==='signed_q'?'−Q':'Pol mag'} · branch 1 · TOA`;$('map-note-0').textContent='Original bins · display clipped to 0–4 · white at LI 0.3 · missing transparent';$('liquid-map-legend').querySelector('small')!.textContent=operational?'GPC LI · threshold 0.3':'Calculated LI · retained reflectance quantity';}
  if(phase){$('channels-0').textContent='cld_phase_21 · 2.1 µm retrieval · native L2 collocated';$('map-note-0').textContent='Nearest OCI L2 center · original L1C selection';}
  if(liquid&&result.provenance.liquid_index_scale){const scale=result.provenance.liquid_index_scale;$('liquid-map-min').textContent='≤'+scale.minimum.toPrecision(3);$('liquid-map-max').textContent='≥'+scale.maximum.toPrecision(3);}
  $('angle-warning').textContent=`RGB angle span ${result.provenance.maximum_angle_span.toFixed(2)}°${result.provenance.angle_warning?' · exceeds 5° display warning':''}`;
  $('evidence').textContent=JSON.stringify({projection:result.labels,bounds:result.bounds,native:result.native_evidence,channels:result.provenance},null,2);
  const source=result.provenance.scattering_contours?.channel;
  $('contour-source').textContent=source?`HARP2 ${source.wavelength.toFixed(1)} nm · sector ${source.angle.toFixed(1)}° · HARP2 maps`:'';
  $('correction-note').textContent=recipe.correction==='rayleigh'
    ?'Rayleigh on land and water. Unknown areas and plots stay TOA.'
    :input('correction').querySelector<HTMLOptionElement>('[value=rayleigh]')!.disabled?rayleighUnavailable:'Reflectance maps and plots show TOA.';
  document.querySelector<HTMLElement>('.badge')!.textContent=recipe.correction!=='toa'||recipe.polar_rayleigh?`Total: ${recipe.correction.replaceAll('_',' + ')} · Polar: ${recipe.polar_rayleigh?'Rayleigh':'TOA'} · Land: Rayleigh · Unknown: TOA`:'Uncorrected TOA';
  plots();
  status('Source-cell preview ready');
}
async function select(selected:number[]){const generation=++selectionSeq;const result=await api<Diagnostics>(`/api/bin/${selected[0]}/${selected[1]}?rft=${Boolean(recipe.rft_overlay)}&rft_weighting=${recipe.rft_weighting??'number'}`);if(generation!==selectionSeq)return;recipe.selected=selected;diagnostics=result;$('selected').textContent=`Original bin [${selected}] · ${result.latitude.toFixed(4)}°, ${result.longitude.toFixed(4)}° · selection persists through missing observations`;$('raw').textContent=JSON.stringify(result,null,2);plots();await render();}
function plots(){
  if(!diagnostics)return;
  const d=diagnostics;persist();cloudProperties(d);
  $('rft-model').textContent=JSON.stringify(d.rft,null,2);
  const common={height:310,autosize:true,paper_bgcolor:'#fffefa',plot_bgcolor:'#fffefa',font:{family:'system-ui',size:11,color:'#253632'},margin:{l:56,r:18,t:14,b:110,autoexpand:false}};
  const axisStyle={showline:true,mirror:true,linewidth:1,linecolor:'#52655b',ticks:'outside' as const,ticklen:5,tickwidth:1,tickcolor:'#52655b',showgrid:true,gridcolor:'#e3e9e3',gridwidth:1,zeroline:false,automargin:false,minor:{showgrid:true,gridcolor:'#f0f3ed',ticks:'outside' as const,ticklen:2}};
  void Plotly.react('spectrum-chart',[{x:d.oci.wavelength,y:d.oci[recipe.spectrum_quantity as 'total'|'radiance'],mode:'lines',connectgaps:false,line:{color:plotColors.observations[0],width:1.5}}],{...common,xaxis:{...axisStyle,title:{text:'Wavelength (nm)',standoff:12}},yaxis:{...axisStyle,title:{text:recipe.spectrum_quantity==='total'?'TOA reflectance':'W m⁻² sr⁻¹ µm⁻¹',standoff:10}},showlegend:false},{responsive:true,displaylogo:false});
  liquidPlot(d,common,axisStyle);
  const wave=d.harp2.hyperangular_wavelength;
  $('polar-heading').textContent=`HARP2 · ${wave.toFixed(1)} nm · Multiangular polarization · TOA`;
  $('cloudbow-model').textContent=JSON.stringify(d.cloudbow,null,2);
  const samples=d.harp2.samples.filter(s=>s.wavelength===wave);
  const traces:Partial<Plotly.PlotData>[]=[];
  [0,1].forEach(branch=>{
    if(recipe.diagnostic_branch!=='both'&&recipe.diagnostic_branch!==String(branch+1))return;
    const ss=samples.filter(s=>s.branch===branch);
    traces.push({x:ss.map(s=>s[recipe.diagnostic_axis]),y:ss.map(s=>s[recipe.diagnostic_quantity]),customdata:ss.map(s=>[s.angle,s.scattering_angle,s.view]),hovertemplate:'Scat %{customdata[1]:.1f}°<br>Sector %{customdata[0]:.1f}°<br>View %{customdata[2]}<br>Value %{y:.4f}<extra>%{fullData.name}</extra>',mode:'markers',name:`Branch ${branch+1}`,marker:{color:plotColors.observations[branch],size:6,symbol:branch?'diamond':'circle',line:{color:'#fffefa',width:.6}}});
  });
  const target=current?.provenance.harp_channels[0]?.angle??recipe.anchor_angle;
  const active=samples.reduce((a,s)=>Math.abs(s.angle-target)<Math.abs(a.angle-target)?s:a,samples[0]);
  const annotations:Partial<Plotly.Annotations>[]=[];
  if(active&&active[recipe.diagnostic_axis]!=null&&active[recipe.diagnostic_quantity]!=null&&(recipe.diagnostic_branch==='both'||recipe.diagnostic_branch===String(Number(active.branch)+1))){
    traces.push({x:[active[recipe.diagnostic_axis]],y:[active[recipe.diagnostic_quantity]],mode:'markers',showlegend:false,hoverinfo:'skip',marker:{symbol:'circle-open',size:12,color:'#253632',line:{width:2}}});
    annotations.push({x:active[recipe.diagnostic_axis] as number,y:active[recipe.diagnostic_quantity] as number,text:`Sector ${active.angle.toFixed(1)}°`,showarrow:true,arrowhead:0,ax:0,ay:-28,bgcolor:'rgba(255,254,250,.9)',font:{size:10},borderpad:2});
  }
  const observationTraces=traces.splice(0);
  let note='Hover points for sector angle · ring marks active red sector.';
  if(recipe.cloudbow_overlay){
    const fit=d.cloudbow;
    if(fit.status==='experimental'&&recipe.diagnostic_quantity==='signed_q'&&recipe.diagnostic_axis==='scattering_angle'){
      traces.push({x:fit.theta,y:fit.signed_q,mode:'lines',name:'Cloudbow',line:{color:plotColors.cloudbow,width:1.8,dash:'solid'}});
      note=`Experimental stored fit · re ${fit.radius_um?.toFixed(2)} µm · ve ${fit.variance?.toFixed(3)}. Both use −Q.`;
    }else note=fit.reason||'Cloudbow comparison requires −Q scattering-plane reflectance versus scattering angle.';
  }
  const fits=(d.rft.thick_branches??[]).filter(f=>recipe.diagnostic_branch==='both'||recipe.diagnostic_branch===String(f.branch+1));
  $('rft-weights').textContent=recipe.rft_overlay?(d.rft.modes??[]).filter(m=>m.scattering_weight!=null).map(m=>`Mode ${m.mode}: fraction ${m.fraction?.toFixed(4)} → scattering weight ${m.scattering_weight?.toFixed(4)}`).join(' · '):'';
  const canCompare=recipe.rft_overlay&&recipe.diagnostic_quantity==='signed_q'&&recipe.diagnostic_axis==='scattering_angle';
  if(canCompare){
    const curves=fits.filter(f=>f.status==='experimental');
    curves.slice(0,1).forEach(f=>{
      traces.push({x:f.theta,y:f.signed_q,mode:'lines',name:f.rayleigh_status==='included'?'RFT refl. · 4-order + Rayleigh':'RFT refl. · 4-order cloud only',line:{color:plotColors.rft,width:3}});
      if(recipe.rft_components&&f.signed_rayleigh)traces.push({x:f.theta,y:f.signed_rayleigh,mode:'lines',name:'Rayleigh contribution',line:{color:'#b56b00',width:2,dash:'dash'}});
      for(const [enabled,curves,kind] of [[recipe.rft_components,f.signed_full_contributions,'contribution']] as const){
        if(enabled)curves.forEach((values,i)=>{
          const mode=f.mode_ids[i],dash=mode?'dashdot':'longdash';
          // A white underlay separates coincident curves without moving the data.
          traces.push({x:f.theta,y:values,mode:'lines',showlegend:false,hoverinfo:'skip',line:{color:'#fffefa',width:5,dash}});
          traces.push({x:f.theta,y:values,mode:'lines',name:`Mode ${mode} ${kind}`,line:{color:plotColors.modes[mode],width:2.5,dash}});
        });
      }
    });
  }
    if(canCompare&&recipe.rft_p12){
      const full=(d.rft.branches??[]).find(f=>f.status==='experimental'&&(recipe.diagnostic_branch==='2'?f.branch===1:f.branch===0));
      if(full)full.signed_full_modes.forEach((values,i)=>{
        const mode=full.mode_ids[i];
        traces.push({x:full.theta,y:values,mode:'lines',name:`Mode ${mode} P12 · A/B/C`,line:{color:plotColors.modes[mode],width:2.5,dash:'dot'}});
      });
      else note+=' RFT P12 unavailable: original cloudbow coefficients missing or unsupported.';
    }
  const branchOneFits=fits.filter(f=>f.branch===0);
  $('rft-support').textContent=recipe.rft_overlay?(branchOneFits.length?branchOneFits.map(f=>f.status==='experimental'?`Branch ${f.branch+1}: ${f.sample_count} views · 4-order approx, ω=1 · ${f.rayleigh_status==='included'?'Rayleigh added':'cloud only'} · RMS ${(f.rmse?.toPrecision(3)??'missing')}${f.warnings.length?' · '+f.warnings.join('; '):''}`:`Branch ${f.branch+1}: ${f.reason}`).join(' | '):d.rft.reason??d.rft.status)+`. Experimental · ${recipe.rft_weighting??'number'} fraction interpretation.`:'';
  if(recipe.rft_overlay&&!canCompare)$('rft-support').textContent+=' Switch to −Q scat versus Scat to see the comparison.';
  const canResidual=(recipe.rft_overlay||recipe.cloudbow_overlay)&&recipe.diagnostic_quantity==='signed_q'&&recipe.diagnostic_axis==='scattering_angle'&&recipe.diagnostic_branch!=='2';
  $('residual-chart').hidden=!canResidual;
  $('rft-component-key').hidden=!(canCompare&&(recipe.rft_components||recipe.rft_p12));
  if(recipe.diagnostic_branch==='2'&&recipe.rft_overlay)$('rft-support').textContent='Branch 2 observations: sanity check only. Model residuals are shown for branch 1.';
  if(canResidual){
    const residualTraces:Partial<Plotly.PlotData>[]=[];
    for(const [key,label,color,enabled,symbol] of [['cloudbow','Cloudbow − observed',plotColors.cloudbow,recipe.cloudbow_overlay,'circle-open'],['rft','RFT refl. − observed',plotColors.rft,recipe.rft_overlay,'diamond']] as const){
      const series=d.residuals.series[key];
      if(enabled&&series?.status==='available')residualTraces.push({x:d.residuals.theta,y:series.residual_signed_q,mode:'markers',name:label,hovertemplate:'Scat %{x:.2f}°<br>Residual %{y:.5f}<extra>%{fullData.name} · branch 1</extra>',marker:{color,size:6,symbol}});
    }
    void Plotly.react('residual-chart',residualTraces,{...common,height:225,margin:{l:56,r:18,t:28,b:80},uirevision:JSON.stringify(recipe.selected),title:{text:`Branch 1 residuals · ${d.residuals.sample_count} shared observations`,font:{size:11}},xaxis:{...axisStyle,range:[130,180],autorange:false,title:{text:'Scattering angle (°)',standoff:8}},yaxis:{...axisStyle,title:{text:'Model − observed (−Q)',standoff:8},zeroline:true,zerolinecolor:'#8b9d93'},showlegend:true,legend:{orientation:'h',x:0,y:-.4,font:{size:10}}},{responsive:true,displaylogo:false});
  }
  $('cloudbow-note').textContent=note;
  traces.push(...observationTraces);
  void Plotly.react('polar-chart',traces,{...common,annotations,xaxis:{...axisStyle,...(recipe.diagnostic_axis==='scattering_angle'?{range:[130,180],autorange:false}:{autorange:true}),title:{text:recipe.diagnostic_axis==='angle'?'Nominal angle (°)':'Scattering angle (°)',standoff:12}},yaxis:{...axisStyle,title:{text:recipe.diagnostic_quantity==='signed_q'?'−Q reflectance':recipe.diagnostic_quantity,standoff:10}},showlegend:true,legend:{orientation:'h',x:0,y:-.30,xanchor:'left',yanchor:'top',font:{size:10},bgcolor:'rgba(255,254,250,0)',borderwidth:0},uirevision:JSON.stringify([recipe.selected,recipe.diagnostic_axis])},{responsive:true,displaylogo:false,doubleClick:'reset'});
}
function liquidPlot(d:Diagnostics,common:Partial<Plotly.Layout>,axisStyle:Partial<Plotly.LayoutAxis>){
  const li=d.liquid_index;
  const branch=Number(recipe.liquid_index_branch??'1')-1;
  const quantity=String(recipe.liquid_index_quantity??'signed_q');
  const original=li.branches.find(b=>b.branch===branch)!.series[quantity];
  if(recipe.liquid_plot_dolp){
    const samples=d.harp2.samples.filter(v=>v.branch===0&&v.wavelength===d.harp2.hyperangular_wavelength);
    $('liquid-heading').textContent=`HARP2 · ${li.wavelength_nm.toFixed(1)} nm · DoLP · TOA`;
    $('liquid-values').textContent='DoLP observations · branch 1';
    $('liquid-note').textContent='DoLP is not used to calculate liquid index. LI maps retain the last reflectance quantity.';
    $('liquid-method').textContent='Polarized magnitude / total reflectance, using original hyperangular TOA observations.';
    $('liquid-integration-chart').hidden=true;
    void Plotly.react('liquid-chart',[{x:samples.map(v=>v.scattering_angle),y:samples.map(v=>v.dolp),mode:'markers',name:'DoLP · branch 1',marker:{color:plotColors.observations[0],size:6}}],{...common,xaxis:{...axisStyle,range:[115,165],title:{text:'Scattering angle (°)',standoff:12}},yaxis:{...axisStyle,title:{text:'DoLP',standoff:10}},uirevision:JSON.stringify([recipe.selected,'liquid-dolp'])},{responsive:true,displaylogo:false});
    return;
  }
  $('liquid-integration-chart').hidden=false;
  const curve=original;
  const [lo,hi]=curve.window_degrees??[130,150];
  const trap=Boolean(recipe.liquid_index_trapezoidal),method=trap?curve.trapezoidal:curve.discrete;
  const label=quantity==='signed_q'?'−Q reflectance':'Polarized magnitude';
  const fmt=(v:number|null|undefined)=>v==null?'—':v.toPrecision(4);
  $('liquid-heading').textContent=`HARP2 · ${li.wavelength_nm.toFixed(1)} nm · Liquid index · TOA`;
  $('liquid-values').textContent=`135–145° ${trap?'trapezoidal':'discrete'} LI: ${fmt(method.value)} · GPC: ${fmt(li.operational_value)} · Δ: ${fmt(method.difference_from_operational)}`;
  $('liquid-method').textContent=JSON.stringify({method:li.method,selected:curve,operational:li.operational_value},null,2);
  $('liquid-note').textContent=method.status!=='available'?(curve.reason??('reason' in method?method.reason:null)??'Integration unavailable'):
    `Baseline n=${curve.baseline_counts.join('+')} · bow n=${curve.peak_count} · normalization at ${curve.reference_angle!.toFixed(2)}° · fixed 10° denominator${curve.fallback_reason?` · ${curve.fallback_reason}`:''}. ${trap?'Linear interpolation; no extrapolation.':'Equal weight per measured bow view.'} ${quantity==='polarized'?'Magnitude alternative; GPC uses Q. ':''}Operational normalization/branch convention unverified.`;
  const traces:(Partial<Plotly.PlotData>&{base?:number[]})[]=[];
  if(trap&&curve.trapezoidal.status==='available'){
    const t=curve.trapezoidal;
    traces.push({x:[...t.theta!,...t.theta!.slice().reverse()],y:[...t.observed!,...t.baseline!.slice().reverse()],fill:'toself',fillcolor:'rgba(0,166,166,.20)',line:{width:0},mode:'lines',name:'Trapezoidal excess',hoverinfo:'skip'});
  }else if(!trap&&curve.baseline){
    // Equal-width bars express equal per-view weights, not angular quadrature.
    traces.push({type:'bar',x:curve.theta.filter((_,i)=>curve.peak_mask[i]),y:curve.observed.filter((_,i)=>curve.peak_mask[i]).map((v,i)=>v-curve.baseline!.filter((_,j)=>curve.peak_mask[j])[i]),base:curve.baseline.filter((_,i)=>curve.peak_mask[i]),width:.22,marker:{color:'rgba(0,166,166,.45)'},name:'Discrete excess',hoverinfo:'skip'});
  }
  if(curve.baseline)traces.push({x:curve.theta,y:curve.baseline,mode:'lines',name:'Linear baseline',line:{color:'#303030',dash:'dash',width:1.8}});
  if(curve.normalization_baseline!=null)traces.push({x:[Math.min(115,lo),Math.max(165,hi)],y:[curve.normalization_baseline,curve.normalization_baseline],mode:'lines',name:'Reference b(135°)',line:{color:'#98642d',dash:'dot',width:1.2}});
  traces.push({x:curve.theta,y:curve.observed,mode:'markers',name:`Observed · branch ${branch+1}`,marker:{color:plotColors.observations[branch],size:6},hovertemplate:'Scat %{x:.2f}°<br>%{y:.5f}<extra>TOA observation</extra>'});
  traces.push({x:curve.theta.filter((_,i)=>curve.baseline_mask[i]),y:curve.observed.filter((_,i)=>curve.baseline_mask[i]),mode:'markers',name:'Baseline samples',marker:{color:'#00745c',size:9,symbol:'circle-open',line:{width:1.6}}});
  const shapes:Partial<Plotly.Shape>[]=[[120,130],[150,160],...(curve.window_degrees?[[lo,hi]]:[])].map(([a,b],i)=>({type:'rect',xref:'x',yref:'paper',x0:a,x1:b,y0:0,y1:1,fillcolor:i===2?'rgba(0,166,166,.06)':'rgba(0,116,92,.06)',line:{width:0},layer:'below'}));
  void Plotly.react('liquid-chart',traces,{...common,shapes,xaxis:{...axisStyle,range:[Math.min(115,lo-2),Math.max(165,hi+2)],autorange:false,title:{text:'Scattering angle (°)',standoff:12}},yaxis:{...axisStyle,title:{text:label,standoff:10}},showlegend:true,legend:{orientation:'h',x:0,y:-.30,font:{size:10}},uirevision:JSON.stringify([recipe.selected,branch,quantity])},{responsive:true,displaylogo:false});
  const integration:Partial<Plotly.PlotData>[]=[];
  if(method.status==='available'){
    let x:number[],y:number[];
    if(trap){
      const t=curve.trapezoidal;x=t.theta!;let sum=0;y=[0];
      for(let i=1;i<x.length;i++){sum+=(t.excess![i-1]+t.excess![i])*.5*(x[i]-x[i-1]);y.push(sum/(10*curve.normalization_baseline!));}
    }else{
      x=curve.peak_theta!;let sum=0;y=curve.peak_excess!.map(v=>{sum+=v;return curve.discrete_width_factor*sum/(curve.peak_count*curve.normalization_baseline!);});
    }
    integration.push({x,y,mode:'lines+markers',name:trap?'Cumulative trapezoid':'Cumulative discrete sum',line:{color:'#00745c',width:1.5,shape:trap?'linear':'hv'},marker:{size:5},hovertemplate:'Scat %{x:.2f}°<br>Cumulative LI %{y:.4f}<extra></extra>'});
  }
  void Plotly.react('liquid-integration-chart',integration,{...common,height:225,margin:{l:56,r:18,t:28,b:65},title:{text:method.status==='available'?`Normalized cumulative excess · LI ${fmt(method.value)}`:'Integration unavailable · see support note',font:{size:11}},xaxis:{...axisStyle,range:[lo-.5,hi+.5],title:{text:'Scattering angle (°)',standoff:8}},yaxis:{...axisStyle,title:{text:'Cumulative LI',standoff:8},zeroline:true,zerolinecolor:'#8b9d93'},showlegend:false,uirevision:JSON.stringify([recipe.selected,branch,quantity,trap])},{responsive:true,displaylogo:false});
}
function cloudProperties(d:Diagnostics){
  const fields=d.cloud.fields??{};
  $('cloud-summary').textContent=d.cloud.status==='available'?`${d.cloud.source?.product_name} · native bin [${d.selected}] · reported retrievals; flagged values are retained`:d.cloud.reason??'No registered GPC product';
  $('cloud-fields').replaceChildren();$('cloud-quality').replaceChildren();
  const groups:[string,[string,string][]][]=[['Cloud top / bulk',[['cloud_top_altitude','Top altitude'],['cloud_top_pressure','Top pressure'],['cloud_top_temperature','Top temperature'],['cloud_optical_thickness','Optical thickness'],['cloud_liquid_index','Liquid index']]],['Cloudbow',[['cloud_bow_droplet_effective_radius','Radius'],['cloud_bow_droplet_effective_variance','Variance'],['cloud_bow_droplet_effective_radius_stddev','Radius σ'],['cloud_bow_droplet_effective_variance_stddev','Variance σ'],['cloud_bow_fit_correlation','Fit correlation'],['cloud_bow_liquid_water_path','Liquid water path'],['cloud_bow_droplet_number_concentration_adiabatic','Adiabatic droplet count']]],['RFT modes',[...([0,1].flatMap(i=>[[`cloud_rft_droplet_effective_radius_mode_${i}`,`Mode ${i} radius`],[`cloud_rft_droplet_effective_variance_mode_${i}`,`Mode ${i} variance`],[`cloud_rft_mode_fraction_${i}`,`Mode ${i} fraction`]]) as [string,string][]),['cloud_rft_decomp_size_correlation','Decomp correlation']]]];
  for(const [title,items] of groups){const section=document.createElement('section');const heading=document.createElement('h3');heading.textContent=title;section.append(heading);const dl=document.createElement('dl');for(const [key,label] of items){const f=fields[key];const dt=document.createElement('dt');dt.textContent=label;const dd=document.createElement('dd');dd.textContent=f?.value!=null?`${Number(f.value.toPrecision(4))} ${f.units==='1'?'':f.units}`:'—';dd.title=f?.description??'Field unavailable';dl.append(dt,dd);}section.append(dl);$('cloud-fields').append(section);}
  for(const name of ['cloud_quality','cloud_bow_quality_retrieval_fail','cloud_rft_quality_retrieval_fail']){const f=fields[name];const line=document.createElement('p');line.textContent=`${name==='cloud_quality'?'Cloud':name.includes('rft')?'RFT':'Cloudbow'} quality: ${f?.status??'unavailable'}${f?.value!=null?' ('+f.value+')':''}${f?.flags?.length?' · '+f.flags.join('; '):''}`;line.className=f?.status==='flagged'?'warning':'quiet';$('cloud-quality').append(line);}
}
for(let i=0;i<3;i++)$(`map-${i}`).onclick=e=>run(async()=>{if(!current)return;const rect=$(`image-${i}`).getBoundingClientRect();const generation=seq;const hit=await api<{selected:number[]}>('/api/hit',{render_id:current.render_id,x:Math.round((e.clientX-rect.left)/rect.width*(current.width-1)),y:Math.round((e.clientY-rect.top)/rect.height*(current.height-1))});if(generation===seq)await select(hit.selected);});
function bind(id:string,fn:()=>void){$(id).onchange=()=>run(async()=>{fn();await render();});}
bind('scattering-contours',()=>recipe.scattering_contours=input('scattering-contours').checked);
bind('left-mode',()=>recipe.left_mode=input('left-mode').value);

bind('correction',()=>{recipe.correction=input('correction').value;recipe.polar_rayleigh=recipe.correction==='rayleigh';});
bind('projection',()=>recipe.projection=input('projection').value);
bind('third',()=>recipe.third_quantity=input('third').value);
bind('harp-mode',()=>recipe.harp_mode=input('harp-mode').value);
$('anchor').oninput=()=>{
  if(recipe.manual_views)return;
  recipe.anchor_angle=anchorAngles[Number(input('anchor').value)];updateAnchorState();
  clearTimeout(sliderTimer);sliderTimer=setTimeout(()=>run(render),100);
};
bind('harp-preset',()=>{recipe.harp_targets=values('harp-preset');recipe.manual_views=null;fillAnchors();fillManualControls();});
function fillAnchors(){
  const target=recipe.harp_targets.includes(550)?550:440;
  const wave=channels.reduce((a,c)=>Math.abs(c.wavelength-target)<Math.abs(a-target)?c.wavelength:a,channels[0].wavelength);
  anchorAngles=channels.filter(c=>c.wavelength===wave).map(c=>c.angle).sort((a,b)=>a-b);
  const nearest=anchorAngles.reduce((a,v)=>Math.abs(v-recipe.anchor_angle)<Math.abs(a-recipe.anchor_angle)?v:a,anchorAngles[0]);
  input('anchor').min='0';input('anchor').max=String(anchorAngles.length-1);input('anchor').value=String(anchorAngles.indexOf(nearest));
  recipe.anchor_angle=nearest;
  $('anchor-ticks').innerHTML=anchorAngles.map((a,i)=>`<option value="${i}" label="${a.toFixed(1)}°"></option>`).join('');
  $('anchor-min').textContent=`${anchorAngles[0].toFixed(1)}°`;
  $('anchor-max').textContent=`${anchorAngles.at(-1)?.toFixed(1)}°`;
  updateAnchorState();
}
function fillManualControls(){
  const defaults=recipe.harp_targets.map((target,i)=>{
    if(recipe.manual_views)return channels.find(c=>c.view===recipe.manual_views?.[i])!;
    const wave=channels.reduce((a,c)=>Math.abs(c.wavelength-target)<Math.abs(a-target)?c.wavelength:a,channels[0].wavelength);
    return channels.filter(c=>c.wavelength===wave).reduce((a,c)=>Math.abs(c.angle-recipe.anchor_angle)<Math.abs(a.angle-recipe.anchor_angle)?c:a);
  });
  $('manual').innerHTML=defaults.map((chosen,i)=>`<label>${['Red','Green','Blue'][i]}<select id="manual-${i}">${channels.filter(c=>c.wavelength===chosen.wavelength).map(c=>`<option value="${c.view}">${c.wavelength.toFixed(1)} nm · ${c.angle.toFixed(1)}° · #${c.view}</option>`).join('')}</select></label>`).join('');
  defaults.forEach((c,i)=>input(`manual-${i}`).value=String(c.view));
}
function updateAnchorState(){
  input('anchor').disabled=recipe.manual_views!==null;
  $('anchor-value').textContent=`${recipe.anchor_angle.toFixed(2)}°`;
  $('anchor-state').textContent=recipe.manual_views?'Manual sectors active · use “Use anchors” to enable slider':'Shared by both HARP2 panels';
}
for(const [id,key] of [['quantity','diagnostic_quantity'],['axis','diagnostic_axis'],['spectrum','spectrum_quantity'],['branch','diagnostic_branch']])$(id).onchange=()=>{recipe[key]=input(id).value;plots();};
for(const [id,key] of [['rft-components','rft_components'],['rft-p12','rft_p12']] as const)$(id).onchange=()=>run(async()=>{
  recipe[key]=input(id).checked;
  if(recipe[key]){recipe.rft_overlay=true;input('rft').checked=true;recipe.diagnostic_quantity='signed_q';recipe.diagnostic_axis='scattering_angle';input('quantity').value='signed_q';input('axis').value='scattering_angle';await select(recipe.selected);}else plots();
});

$('liquid-quantity').onchange=()=>run(async()=>{const value=input('liquid-quantity').value;recipe.liquid_plot_dolp=value==='dolp';if(!recipe.liquid_plot_dolp)recipe.liquid_index_quantity=value;syncLiquidIntegration();plots();if(!recipe.liquid_plot_dolp&&recipe.left_mode.startsWith('liquid_index_'))await render();});
function syncLiquidIntegration(){input('liquid-trapezoidal').disabled=Boolean(recipe.liquid_plot_dolp);input('liquid-trapezoidal').checked=Boolean(recipe.liquid_index_trapezoidal);}
$('liquid-trapezoidal').onchange=()=>{recipe.liquid_index_trapezoidal=input('liquid-trapezoidal').checked;plots();};
$('rft').onchange=()=>run(async()=>{recipe.rft_overlay=input('rft').checked;if(recipe.rft_overlay){recipe.diagnostic_quantity='signed_q';recipe.diagnostic_axis='scattering_angle';input('quantity').value='signed_q';input('axis').value='scattering_angle';}await select(recipe.selected);});
$('cloudbow').onchange=()=>{recipe.cloudbow_overlay=input('cloudbow').checked;if(recipe.cloudbow_overlay){recipe.diagnostic_quantity='signed_q';recipe.diagnostic_axis='scattering_angle';input('quantity').value='signed_q';input('axis').value='scattering_angle';}plots();};
$('oci-apply').onclick=()=>run(async()=>{recipe.oci_targets=values('oci-targets');await render();});
$('crop').onclick=()=>run(async()=>{recipe.crop=[...values('rows'),...values('cols')];await render();});
$('reset-crop').onclick=()=>run(async()=>{recipe.crop=null;await render();});
$('manual-apply').onclick=()=>run(async()=>{recipe.manual_views=[0,1,2].map(i=>Number(input(`manual-${i}`).value));updateAnchorState();await render();});
$('manual-reset').onclick=()=>run(async()=>{recipe.manual_views=null;updateAnchorState();await render();});
bind('enhance',()=>{recipe.preset=input('enhance').value;recipe.stretch=recipe.preset==='comparison'?structuredClone(comparison):beautyPreset();syncStretchEditor();});
$('stretch-quantity').onchange=syncStretchEditor;
$('stretch-apply').onclick=()=>run(async()=>{recipe.stretch[input('stretch-quantity').value]=values('stretch');recipe.preset='beauty';input('enhance').value='beauty';await render();localStorage.setItem('pace-beauty-v1',JSON.stringify(recipe.stretch));});
$('beauty-reset').onclick=()=>run(async()=>{localStorage.removeItem('pace-beauty-v1');localStorage.removeItem('pace-beauty');recipe.preset='beauty';recipe.stretch=structuredClone(beautyDefaults);input('enhance').value='beauty';syncStretchEditor();await render();});
$('size').onchange=()=>{input('width').value=input('size').value==='paper'?'180':'320';input('height').value=input('size').value==='paper'?'240':'180';};
$('title').onchange=()=>recipe.title=input('title').value;
$('export').onclick=()=>run(async()=>{const button=$<HTMLButtonElement>('export');button.disabled=true;status('Composing scientific PNG/PDF…');try{const result=await api<{artifacts:string[]}>('/api/export',{recipe,layout:input('layout').value,width_mm:Number(input('width').value),height_mm:Number(input('height').value),dpi:Number(input('dpi').value)});$('export-links').innerHTML=result.artifacts.map(p=>`<a href="${p}" download>${p.split('.').pop()?.toUpperCase()}</a>`).join('');status('Figure and reproduction recipe saved');}finally{button.disabled=false;}});
$('recipe').onclick=()=>{const a=document.createElement('a');const url=URL.createObjectURL(new Blob([JSON.stringify({schema_version:1,recipe,inputs:identities},null,2)],{type:'application/json'}));a.href=url;a.download='pace-recipe.json';a.click();URL.revokeObjectURL(url);};
$('restore').onchange=()=>run(async()=>{const f=$<HTMLInputElement>('restore').files?.[0];if(!f)return;const saved=JSON.parse(await f.text());if(saved.inputs&&JSON.stringify(saved.inputs)!==JSON.stringify(identities))throw new Error('Recipe belongs to different source products');recipe=saved.recipe||saved;recipe.rft_weighting='number';syncControls();await select(recipe.selected);});
function syncControls(){
  // Older independent map settings become a single dashboard choice on restore.
  const rayleigh=(recipe.correction.includes('rayleigh')||recipe.polar_rayleigh)&&!input('correction').querySelector<HTMLOptionElement>('[value=rayleigh]')!.disabled;
  recipe.correction=rayleigh?'rayleigh':'toa';recipe.polar_rayleigh=rayleigh;recipe.rayleigh_land=true;
  if(recipe.title==='PACE L1C • uncorrected TOA')recipe.title='PACE L1C';
  const legacy=recipe.middle_mode as string|undefined;recipe.left_mode??=legacy==='harp_total'?'oci_total':legacy??'oci_total';if(!['oci_total','oci_phase','liquid_index','liquid_index_discrete','liquid_index_trapezoidal'].includes(recipe.left_mode))recipe.left_mode='oci_total';for(const key of ['middle_mode','liquid_index_wide','liquid_index_adaptive','baseline_angle_range'])delete recipe[key];recipe.liquid_plot_dolp??=false;recipe.liquid_index_quantity??='signed_q';recipe.liquid_index_branch='1';recipe.liquid_index_trapezoidal??=false;syncLiquidIntegration();recipe.rft_weighting='number';recipe.rft_scaling='stored';recipe.extrapolate_surface=false;for(const [id,key] of [['left-mode','left_mode'],['correction','correction'],['projection','projection'],['third','third_quantity'],['quantity','diagnostic_quantity'],['axis','diagnostic_axis'],['spectrum','spectrum_quantity'],['enhance','preset'],['harp-mode','harp_mode'],['branch','diagnostic_branch'],['title','title'],['liquid-branch','liquid_index_branch']])input(id).value=String(recipe[key]);input('liquid-quantity').value=recipe.liquid_plot_dolp?'dolp':String(recipe.liquid_index_quantity);fillAnchors();fillManualControls();syncStretchEditor();input('cloudbow').checked=Boolean(recipe.cloudbow_overlay);input('rft').checked=Boolean(recipe.rft_overlay);input('rft-components').checked=Boolean(recipe.rft_components);input('rft-p12').checked=Boolean(recipe.rft_p12);input('scattering-contours').checked=Boolean(recipe.scattering_contours);input('oci-targets').value=recipe.oci_targets.join(',');if(recipe.crop){input('rows').value=recipe.crop.slice(0,2).join(',');input('cols').value=recipe.crop.slice(2).join(',');}}
run(async()=>{const info=await api<{oci:{identity:unknown;shape:number[]};harp2:{identity:unknown;channels:Channel[]};default_recipe:Recipe;alignment:unknown;atmosphere:unknown;phase_available:boolean;liquid_index_available:boolean;correction_unavailable_reason?:string|null;model_capabilities:{cloudbow:boolean;rft:boolean};correction_capabilities:{rayleigh:boolean;transmission:boolean}}>('/api/scene');recipe={...info.default_recipe,preset:'beauty',stretch:beautyPreset()};for(const id of ['cloudbow','rft','rft-components','rft-p12']){input(id).disabled=!info.model_capabilities.cloudbow;input(id).title=info.model_capabilities.cloudbow?'':'Requires matching GPC and an optional local phase library';}input('left-mode').querySelector<HTMLOptionElement>('[value=oci_phase]')!.disabled=!info.phase_available;input('left-mode').querySelector<HTMLOptionElement>('[value=liquid_index]')!.disabled=!info.liquid_index_available;rayleighUnavailable=info.correction_unavailable_reason??rayleighUnavailable;const caps=info.correction_capabilities;input('correction').querySelector<HTMLOptionElement>('[value=rayleigh]')!.disabled=!caps.rayleigh;$('correction-note').textContent=caps.rayleigh?'':'Rayleigh correction unavailable for this scene.';channels=info.harp2.channels;identities=[info.oci.identity,info.harp2.identity];const saved=JSON.parse(localStorage.getItem('pace-scene')||'null');if(saved&&JSON.stringify(saved.inputs)===JSON.stringify(identities))recipe={...recipe,...saved.recipe,left_mode:saved.recipe.left_mode??(saved.recipe.middle_mode==='harp_total'?'oci_total':saved.recipe.middle_mode)??'oci_total'};if(recipe.preset==='beauty'&&JSON.stringify(recipe.stretch)===JSON.stringify(comparison))recipe.stretch=beautyPreset();$('identity').textContent=`${info.oci.shape.join(' × ')} original bins`;fillManualControls();fillAnchors();syncControls();await select(recipe.selected);});
