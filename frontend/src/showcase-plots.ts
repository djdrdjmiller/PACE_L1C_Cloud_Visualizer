/** Display the existing library's cached results; never fit or rescale a model. */
export const colors={observations:['#b13d35','#e69f00'],cloudbow:'#303030'};
export function liquidFigures(curve:any,trapezoidal:boolean){
  const traces:any[]=[];
  const [lo,hi]=curve.window_degrees??[135,145];
  const method=trapezoidal?curve.trapezoidal:curve.discrete;
  if(trapezoidal&&curve.trapezoidal.status==='available'){
    const t=curve.trapezoidal;
    traces.push({x:[...t.theta,...t.theta.slice().reverse()],y:[...t.observed,...t.baseline.slice().reverse()],fill:'toself',fillcolor:'rgba(0,166,166,.20)',line:{width:0},mode:'lines',name:'Trapezoidal excess',hoverinfo:'skip'});
  }else if(!trapezoidal&&curve.baseline){
    const mask=(values:number[])=>values.filter((_:number,i:number)=>curve.peak_mask[i]);
    traces.push({type:'bar',x:mask(curve.theta),y:mask(curve.observed).map((v,i)=>v-mask(curve.baseline)[i]),base:mask(curve.baseline),width:.22,marker:{color:'rgba(0,166,166,.45)'},name:'Discrete excess',hoverinfo:'skip'});
  }
  if(curve.baseline)traces.push({x:curve.theta,y:curve.baseline,mode:'lines',name:'Linear baseline',line:{color:'#303030',dash:'dash',width:1.8}});
  if(curve.normalization_baseline!=null)traces.push({x:[115,165],y:[curve.normalization_baseline,curve.normalization_baseline],mode:'lines',name:'Reference b(135°)',line:{color:'#98642d',dash:'dot',width:1.2}});
  traces.push({x:curve.theta,y:curve.observed,mode:'markers',name:'Branch 1 TOA',marker:{color:colors.observations[0],size:6}});
  traces.push({x:curve.theta.filter((_:number,i:number)=>curve.baseline_mask[i]),y:curve.observed.filter((_:number,i:number)=>curve.baseline_mask[i]),mode:'markers',name:'Baseline samples',marker:{color:'#00745c',size:9,symbol:'circle-open',line:{width:1.6}}});
  const shapes=[[120,130],[150,160],[lo,hi]].map(([a,b],i)=>({type:'rect',xref:'x',yref:'paper',x0:a,x1:b,y0:0,y1:1,fillcolor:i===2?'rgba(0,166,166,.06)':'rgba(0,116,92,.06)',line:{width:0},layer:'below'}));
  const integration:any[]=[];
  if(method.status==='available'){
    let x:number[],y:number[];
    if(trapezoidal){const t=curve.trapezoidal;x=t.theta;let sum=0;y=[0];for(let i=1;i<x.length;i++){sum+=(t.excess[i-1]+t.excess[i])*.5*(x[i]-x[i-1]);y.push(sum/(10*curve.normalization_baseline));}}
    else{x=curve.peak_theta;let sum=0;y=curve.peak_excess.map((v:number)=>{sum+=v;return curve.discrete_width_factor*sum/(curve.peak_count*curve.normalization_baseline);});}
    integration.push({x,y,mode:'lines+markers',name:trapezoidal?'Cumulative trapezoid':'Cumulative discrete sum',line:{color:'#00745c',width:1.5,shape:trapezoidal?'linear':'hv'},marker:{size:5},hovertemplate:'Scat %{x:.2f}°<br>Cumulative LI %{y:.4f}<extra></extra>'});
  }
  return {traces,shapes,integration,range:[lo-.5,hi+.5],method};
}
export function cloudbowFigures(d:any,enabled:boolean,compare:boolean){
  const traces:any[]=[],residuals:any[]=[],notes:string[]=[];
  if(!enabled)return {traces,residuals,notes};
  if(!compare){notes.push('Cloudbow overlays and residuals compare branch 1 −Q versus scattering angle. Branch 2 remains an observation sanity check.');return {traces,residuals,notes};}
  const fit=d.cloudbow;
  if(fit?.status==='experimental'){
    traces.push({x:fit.theta,y:fit.signed_q,mode:'lines',name:'Cloudbow · A/B/C',line:{color:colors.cloudbow,width:1.8}});
    notes.push(`Stored same-bin fit · radius ${fit.radius_um.toFixed(2)} µm · variance ${fit.variance.toFixed(3)} · experimental; no refit.`);
  }else notes.push(`Cloudbow unavailable: ${fit?.reason??'No cached local-library result'}`);
  const residual=d.residuals?.series.cloudbow;
  if(residual?.status==='available')residuals.push({x:d.residuals.theta,y:residual.residual_signed_q,mode:'markers',name:'Cloudbow − obs.',marker:{color:colors.cloudbow,size:6,symbol:'circle-open'}});
  return {traces,residuals,notes};
}
