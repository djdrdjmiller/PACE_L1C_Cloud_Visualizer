"""Observed TOA cloudbow contrast; ATBD discrete and optional trapezoidal means.

No microphysical fitting, atmospheric correction or operational-value tuning.
The reference baseline is evaluated at 135 degrees, following the lower-window
reference illustrated in van Diedenhoven 2012 Figure 4. Operational parity is
not implied by this diagnostic reconstruction.
"""
import numpy as np
from .reader import jsonable

class MapCalculationCancelled(Exception):
    """Caller abandoned a bounded derived-map calculation."""


METHOD={
    'reference':'https://oceandata.sci.gsfc.nasa.gov/files/atbd/atbd-obdaac-cloud-GPC.pdf',
    'baseline_windows_degrees':[[120.,130.],[150.,160.]],
    'peak_window_degrees':[135.,145.],
    'wide_window_degrees':[130.,150.],
    'adaptive_policy':'nearest horizontal b(135) crossings enclosing largest measured peak in 135–145, bounded to 130–150; use window edge when crossing outside or absent, require endpoint bracketing; no extrapolation; subtract sloping baseline; fixed 10-degree denominator; trapezoidal only; no peak above reference uses fixed-wide trapezoidal fallback',
    'wide_policy':'experimental; unchanged inclusive baseline windows and baseline(135); fixed 10-degree denominator; discrete mean multiplied by 20/10; boundary samples at 130/150 may also constrain baseline; no clipping',
    'baseline_angle':'signed degrees(atan(a-0)); a=reflectance slope per degree of scattering angle; horizontal L(135) reference; numeric axes 1 reflectance unit per 1 scattering degree; no normalization by L(135); not a physical scattering angle or constituent retrieval',
    'baseline':'unweighted least-squares straight line through both off-bow windows',
    'discrete':'mean(observed_i-baseline_i)/baseline(theta_reference); equal weight per original peak view',
    'trapezoidal':'integral_135^145(observed-baseline)dtheta / (10*baseline(theta_reference)); piecewise linear between valid observations, interpolated endpoints, no extrapolation',
    'normalization':'baseline at 135 degrees, lower-window reference in van Diedenhoven 2012 Figure 4; operational implementation parity unverified',
    'normalization_reference':'https://www.giss.nasa.gov/pubs/docs/2012/2012_VanDiedenhoven_va04100j.pdf',
    'support':'at least 4 baseline samples, both baseline windows, 2 distinct peak angles; primary van Diedenhoven 2012 sampling checks with both-window coverage required here',
    'branch_policy':'branch 1 observations only; heuristic branch identity is not independently verified operational selection',
    'quantity':'signed -Q in scattering plane by default; polarized magnitude is an explicitly alternative diagnostic',
    'scope':'original red hyperangular TOA samples; no glint removal; no clipping negative excess or index; operational GPC retained independently',
}


def display_scale(field):
    """User-approved common display clipping only; scientific field untouched."""
    values=np.asarray(field,float);finite=values[np.isfinite(values)]
    return {'minimum':0.,'center':.3,'maximum':4.,'clipped_below':int((finite<0).sum()),'clipped_above':int((finite>4).sum()),
            'colormap':'blue-white-red','normalization':'piecewise linear either side of 0.3; display clipped to 0–4; science unchanged'}


def baseline_angle_scale(field,range_mode='percentile'):
    """User-facing contrast limits only; retain all scientific angles."""
    if range_mode not in ('percentile','full'):raise ValueError('Unsupported baseline-angle display range')
    finite=np.asarray(field,float);finite=finite[np.isfinite(finite)]
    if len(finite):
        lo,hi=np.percentile(finite,[1,99]) if range_mode=='percentile' else (finite.min(),finite.max())
        lo,hi=float(lo),float(hi)
    else:lo,hi=-.001,.001
    if lo==hi:
        pad=max(.001,abs(lo)*.05);lo-=pad;hi+=pad
    return {'minimum':lo,'center':(lo+hi)/2,'maximum':hi,'units':'degrees','colormap':'turbo',
            'range_mode':range_mode,'valid_bins':len(finite),
            'clipped_below':int((finite<lo).sum()),'clipped_above':int((finite>hi).sum()),
            'normalization':'linear 1st–99th percentiles, display only' if range_mode=='percentile' else 'linear full native-field extent'}


def calculate(theta,observed,source_views=None,*,wide=False,include_angle=True):
    """Return full baseline/excess evidence even when the index lacks support."""
    theta=np.asarray(theta,float);observed=np.asarray(observed,float)
    if theta.ndim!=1 or theta.shape!=observed.shape:raise ValueError('Liquid-index samples must be matching 1D arrays')
    views=np.arange(len(theta)) if source_views is None else np.asarray(source_views)
    if views.shape!=theta.shape:raise ValueError('Liquid-index view IDs must match samples')
    valid=np.isfinite(theta)&np.isfinite(observed)&(theta>=0)&(theta<=180)
    order=np.argsort(theta[valid],kind='stable')
    x=theta[valid][order];y=observed[valid][order];views=views[valid][order]
    lo,hi=(130.,150.) if wide else (135.,145.)
    width_factor=(hi-lo)/10.
    left=(x>=120)&(x<=130);right=(x>=150)&(x<=160);base=left|right;peak=(x>=lo)&(x<=hi)
    out={'status':'missing','reason':None,'theta':x,'observed':y,'source_views':views,
         'window_degrees':[lo,hi],'angular_denominator_degrees':10.,'discrete_width_factor':width_factor,
         'baseline_mask':base,'peak_mask':peak,'baseline_count':int(base.sum()),
         'baseline_counts':[int(left.sum()),int(right.sum())],'peak_count':int(peak.sum()),
         'baseline':None,**({'baseline_angle':{'status':'missing','value':None,'units':'degrees'}} if include_angle else {}),'discrete':{'status':'missing','value':None},
         'trapezoidal':{'status':'missing','value':None},'warnings':[]}
    if base.sum()<4 or not left.any() or not right.any() or np.ptp(x[base])==0:
        out['reason']='Need ≥4 valid baseline views spanning both 120–130° and 150–160° windows'
        return jsonable(out)
    # Centering provides numerical stability without changing unweighted OLS.
    slope,center=np.linalg.lstsq(np.column_stack([x[base]-140,np.ones(base.sum())]),y[base],rcond=None)[0]
    baseline=slope*(x-140)+center
    out.update(baseline=baseline,slope_per_degree=slope,intercept=center-140*slope,
               baseline_rms=float(np.sqrt(np.mean((y[base]-baseline[base])**2))))
    if include_angle:out['baseline_angle']={'status':'available','value':float(np.rad2deg(np.arctan(slope))),'units':'degrees','slope_reflectance_per_degree':float(slope),'reference_slope':0.,'definition':METHOD['baseline_angle']}
    if peak.sum()<2 or np.unique(x[peak]).size<2:
        out['reason']=f'Need ≥2 distinct valid peak angles in {lo:g}–{hi:g}°'
        return jsonable(out)
    reference=135.;denominator=float(slope*(reference-140)+center)
    out.update(reference_angle=reference,normalization_baseline=denominator,
               peak_theta=x[peak],peak_excess=y[peak]-baseline[peak])
    if abs(denominator)<=max(float(np.max(np.abs(y))),np.finfo(float).tiny)*1e-10:
        out['reason']='Baseline normalization is zero or numerically unstable'
        return jsonable(out)
    if denominator<0:out['warnings'].append('Normalization baseline is negative; signed result retained')
    out['discrete']={'status':'available','sum_excess':float(np.sum(y[peak]-baseline[peak])),
                     'mean_excess':float(np.mean(y[peak]-baseline[peak])),
                     'value':float(width_factor*np.mean(y[peak]-baseline[peak])/denominator)}
    out.update(status='available',reason=None)
    # Duplicate angles do not define a unique interpolation; retain discrete CLI.
    if np.unique(x).size!=len(x):
        out['trapezoidal']['reason']='Duplicate angles prevent unambiguous piecewise-linear integration'
    elif x.min()>lo or x.max()<hi:
        out['trapezoidal']['reason']=f'Observations do not bracket both {lo:g}° and {hi:g}°; no extrapolation'
    else:
        tx=np.r_[lo,x[(x>lo)&(x<hi)],hi]
        ty=np.interp(tx,x,y);tb=slope*(tx-140)+center
        area=float(np.trapezoid(ty-tb,tx))
        out['trapezoidal']={'status':'available','theta':tx,'observed':ty,'baseline':tb,
            'excess':ty-tb,'integral_reflectance_degrees':area,'mean_excess':area/10,
            'value':area/(10*denominator),'endpoint_policy':'linear interpolation between valid neighbors; no extrapolation',
            'largest_segment_degrees':float(np.max(np.diff(tx)))}
    return jsonable(out)


def adaptive_window(curve,wide_curve=None):
    """Main-bow b(135) crossings, capped at user-approved 130–150 edges.

    Reuse the existing off-bow fit. No smoothing, extrapolation, positivity
    clipping. Window bounds are explicit; no angular extrapolation. Crossings select bounds only; excess
    remains relative to the sloping fitted baseline.
    """
    out={k:v for k,v in curve.items() if k not in ('wide','adaptive')}
    out.update(status='missing',reason=None,window_degrees=None,peak_count=0,
               peak_mask=[False]*len(curve['theta']),peak_theta=[],peak_excess=[],
               discrete={'status':'missing','value':None,'reason':'Adaptive window supports trapezoidal integration only'},
               trapezoidal={'status':'missing','value':None},crossings=None,boundaries=None)
    def missing(reason):
        out['reason']=reason;out['trapezoidal']['reason']=reason
        return jsonable(out)
    if curve['baseline'] is None:return missing(curve['reason'] or 'Baseline unavailable')
    x=np.asarray(curve['theta']);y=np.asarray(curve['observed']);baseline=np.asarray(curve['baseline'])
    b=float(curve['slope_per_degree']*135+curve['intercept'])
    out.update(reference_angle=135.,normalization_baseline=b)
    if abs(b)<=max(float(np.max(np.abs(y))),np.finfo(float).tiny)*1e-10:
        return missing('Baseline normalization is zero or numerically unstable')
    if len(np.unique(x))!=len(x):return missing('Duplicate angles prevent unambiguous crossing interpolation')
    candidates=np.flatnonzero((x>=135)&(x<=145))
    h=y-b
    tolerance=max(float(np.max(np.abs(y))),np.finfo(float).tiny)*1e-10
    h[np.abs(h)<=tolerance]=0.
    if not len(candidates):return missing('No valid measured main-bow sample in 135–145°')
    seed=int(candidates[np.argmax(h[candidates])])
    if h[seed]<=tolerance:
        wide_curve=wide_curve if wide_curve is not None else calculate(x,y,curve['source_views'],wide=True)
        if wide_curve['trapezoidal']['status']!='available':
            return missing(wide_curve['reason'] or wide_curve['trapezoidal'].get('reason','Wide fallback unavailable'))
        bounds=[]
        for angle in (130.,150.):
            j=int(np.clip(np.searchsorted(x,angle,side='right'),1,len(x)-1));i=j-1
            bounds.append({'angle':angle,'kind':'window_edge','bracket_angles':[float(x[i]),float(x[j])],
                'bracket_source_views':[curve['source_views'][i],curve['source_views'][j]]})
        out.update(status='available',reason=None,window_degrees=[130.,150.],boundaries=bounds,crossings=[],
            seed_angle=float(x[seed]),fallback_reason='No main-bow peak above horizontal reference; wide-window fallback',
            peak_mask=wide_curve['peak_mask'],peak_count=wide_curve['peak_count'],
            peak_theta=wide_curve['peak_theta'],peak_excess=wide_curve['peak_excess'],
            trapezoidal=dict(wide_curve['trapezoidal']))
        out['trapezoidal']['endpoint_policy']='No peak above reference: fixed 130–150° trapezoidal fallback; no extrapolation'
        return jsonable(out)
    left=seed
    while left>0 and h[left-1]>0:left-=1
    right=seed
    while right<len(x)-1 and h[right+1]>0:right+=1
    def crossing(i,j):
        angle=float(x[i]-h[i]*(x[j]-x[i])/(h[j]-h[i]))
        return {'angle':angle,'bracket_angles':[float(x[i]),float(x[j])],
                'bracket_source_views':[curve['source_views'][i],curve['source_views'][j]]}
    lc=crossing(left-1,left) if left>0 else None
    rc=crossing(right,right+1) if right<len(x)-1 else None
    lo=max(130.,lc['angle']) if lc else 130.
    hi=min(150.,rc['angle']) if rc else 150.
    if x[0]>lo or x[-1]<hi:
        return missing('Observations do not bracket required adaptive crossing/window edges; no extrapolation')
    def boundary(angle,candidate):
        if candidate and 130<=candidate['angle']<=150:
            return dict(candidate,kind='crossing')
        j=int(np.clip(np.searchsorted(x,angle,side='right'),1,len(x)-1));i=j-1
        return {'angle':angle,'kind':'window_edge','unbounded_crossing_angle':candidate['angle'] if candidate else None,
                'bracket_angles':[float(x[i]),float(x[j])],
                'bracket_source_views':[curve['source_views'][i],curve['source_views'][j]]}
    bounds=[boundary(lo,lc),boundary(hi,rc)]
    tx=np.r_[lo,x[(x>lo)&(x<hi)],hi];ty=np.interp(tx,x,y)
    tb=curve['slope_per_degree']*tx+curve['intercept'];excess=ty-tb
    area=float(np.trapezoid(excess,tx));peak=(x>=lo)&(x<=hi)
    out.update(status='available',reason=None,window_degrees=[lo,hi],boundaries=bounds,crossings=[b for b in bounds if b['kind']=='crossing'],
               seed_angle=float(x[seed]),peak_mask=peak,peak_count=int(peak.sum()),
               peak_theta=x[peak],peak_excess=y[peak]-baseline[peak])
    out['trapezoidal']={'status':'available','value':area/(10*b),'theta':tx,
        'observed':ty,'baseline':tb,'excess':excess,'integral_reflectance_degrees':area,
        'mean_excess':area/10,'largest_segment_degrees':float(np.max(np.diff(tx))),
        'endpoint_policy':'nearest b(135) crossings enclosing strongest measured peak in 135–145; cap to 130–150 window edges; interpolate endpoints; no extrapolation'}
    return jsonable(out)


def diagnostics(observations,operational=None,source=None,*,extended=True):
    wave=observations['hyperangular_wavelength']
    result={'wavelength_nm':wave,'operational_value':operational,'operational_source':source,
            'method':METHOD if extended else {k:v for k,v in METHOD.items() if k not in ('wide_window_degrees','wide_policy','adaptive_policy','baseline_angle')},'branches':[]}
    for branch in (0,):
        samples=[s for s in observations['samples'] if s['wavelength']==wave and s['branch']==branch]
        series={}
        for quantity in ('signed_q','polarized'):
            curve=calculate([s['scattering_angle'] for s in samples],[s.get(quantity) for s in samples],[s['view'] for s in samples],include_angle=extended)
            for name in ('discrete','trapezoidal'):
                value=curve[name]['value']
                curve[name]['difference_from_operational']=value-operational if value is not None and operational is not None else None
            if extended:
                wide_curve=calculate([s['scattering_angle'] for s in samples],[s.get(quantity) for s in samples],[s['view'] for s in samples],wide=True)
                for name in ('discrete','trapezoidal'):
                    value=wide_curve[name]['value']
                    wide_curve[name]['difference_from_operational']=value-operational if value is not None and operational is not None else None
                curve['wide']=wide_curve
                adaptive=adaptive_window(curve,wide_curve)
                value=adaptive['trapezoidal']['value']
                adaptive['trapezoidal']['difference_from_operational']=value-operational if value is not None and operational is not None else None
                curve['adaptive']=adaptive
            series[quantity]=curve
        result['branches'].append({'branch':branch,'series':series})
    return jsonable(result)


def map_layers(product,quantity='signed_q',branch=0,batch_rows=16,*,baseline_only=False,cancelled=None,extended=True):
    """Bounded native-bin calculation. Cache both methods, never regrid a cube."""
    from .science import reflectance,rotate,branches
    if quantity not in ('signed_q','polarized') or branch != 0:raise ValueError('Unsupported liquid-index map quantity/branch')
    if not isinstance(batch_rows,int) or not 1<=batch_rows<=64:raise ValueError('Liquid-index batch_rows must be 1–64')
    wave=max({c['wavelength'] for c in product.channels},key=lambda w:(sum(c['wavelength']==w for c in product.channels),-abs(w-665)))
    channels=[c for c in product.channels if c['wavelength']==wave]
    views=[c['view'] for c in channels];nominal=[c['angle'] for c in channels]
    outputs={name:np.full(product.shape,np.nan) for name in (('baseline_angle',) if baseline_only else ('discrete','trapezoidal','wide_trapezoidal','adaptive_trapezoidal','baseline_angle') if extended else ('discrete','trapezoidal'))}
    pf0=product.read('polarization_f0')[views]
    for start in range(0,product.shape[0],batch_rows):
        if cancelled is not None and cancelled():raise MapCalculationCancelled()
        sl=slice(start,min(start+batch_rows,product.shape[0]))
        field=lambda name:np.asarray(product.read(name,row=sl))[...,views]
        count=field('number_of_observations');sza=field('solar_zenith_angle')
        q=reflectance(np.where(count>0,field('q'),np.nan),pf0,sza,product.distance)
        u=reflectance(np.where(count>0,field('u'),np.nan),pf0,sza,product.distance)
        y=-rotate(q,u,field('rotation_angle'))[0] if quantity=='signed_q' else np.hypot(q,u)
        theta=field('scattering_angle')
        for offset in range(len(theta)):
            if cancelled is not None and cancelled():raise MapCalculationCancelled()
            for col in range(product.shape[1]):
                x=theta[offset,col];values=y[offset,col]
                if not np.any(np.isfinite(values)&(x>=120)&(x<=160)):continue
                use=branches(x,nominal)==branch
                result=calculate(x[use],values[use],include_angle=extended or baseline_only)
                if baseline_only:
                    value=result['baseline_angle']['value']
                    if value is not None:outputs['baseline_angle'][start+offset,col]=value
                    continue
                if not extended:
                    for name in outputs:
                        value=result[name]['value']
                        if value is not None:outputs[name][start+offset,col]=value
                    continue
                wide_result=calculate(x[use],values[use],wide=True)
                adaptive=adaptive_window(result,wide_result)
                for name in outputs:
                    value=result['baseline_angle']['value'] if name=='baseline_angle' else adaptive['trapezoidal']['value'] if name=='adaptive_trapezoidal' else (wide_result[name.removeprefix('wide_')] if name.startswith('wide_') else result[name])['value']
                    if value is not None:outputs[name][start+offset,col]=value
    return outputs
