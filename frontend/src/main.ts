import './style.css';

async function start(){
  document.getElementById('app')!.innerHTML=`<header class="dashboard-header"><div class="dashboard-brand"><img class="mucloud-wordmark" src="/branding/mucloud-wordmark-on-light.svg" alt="µCloud" width="150" height="36"><div class="dashboard-title"><h1>PACE L1C · Quicklook Dashboard</h1><small>OCI + HARP2 · Original L1C bins</small></div></div></header><div class="selection" role="status">Opening your local workspace…</div>`;
  const response=await fetch('/api/setup');
  if(!response.ok)throw new Error('Local setup service unavailable');
  const info=await response.json();
  if(info.scene_loaded&&!new URLSearchParams(location.search).has('setup'))await import('./dashboard');
  else {const {startSetup}=await import('./setup');await startSetup(info);}
}
start().catch(error=>{const app=document.getElementById('app')!;app.textContent=String(error);app.setAttribute('role','alert');});
