"""Named model residuals on identical original branch-1 observations."""
import numpy as np
from .cloudbow import forward
from .reader import jsonable


def compare(observations,cloudbow,rft,interval):
    model=next((b for b in rft.get('thick_branches',rft.get('branches',[])) if b['branch']==0),
               {'status':'missing','reason':rft.get('reason','RFT comparison disabled')})
    models={'cloudbow':cloudbow,'rft':model}
    lower,upper=interval
    for curve in models.values():
        if curve['status']=='experimental':
            lower=max(lower,float(curve['theta'][0]));upper=min(upper,float(curve['theta'][-1]))
    wave=observations['hyperangular_wavelength']
    samples=[s for s in observations['samples'] if s['wavelength']==wave and s['branch']==0
             and s['scattering_angle'] is not None and s['q_scattering'] is not None
             and np.isfinite([s['scattering_angle'],s['q_scattering']]).all()
             and lower<=s['scattering_angle']<=upper]
    if 'phase_units' in model:
        samples=[s for s in samples if s['view'] in model['source_views']]
    theta=np.array([s['scattering_angle'] for s in samples],dtype=float)
    observed=-np.array([s['q_scattering'] for s in samples],dtype=float)
    result={'branch':0,'theta':theta,'observed_signed_q':observed,'sample_count':len(samples),
            'source_views':[s['view'] for s in samples],'angular_interval':[lower,upper],
            'policy':'Original TOA branch 1 only; full model minus observed in displayed -Q convention; identical samples for both models',
            'series':{}}
    for name,curve in models.items():
        if curve['status']!='experimental':
            result['series'][name]={'status':'missing','reason':curve.get('reason','Model unavailable')}
            continue
        if name=='rft' and 'phase_units' in curve:
            lookup=dict(zip(curve['source_views'],curve['predicted_signed_q']))
            predicted=np.array([lookup.get(s['view'],np.nan) for s in samples])
        else:
            phase=curve['phase'] if name=='cloudbow' else curve['phase_mixture']
            _,predicted=forward(theta,np.interp(theta,curve['theta'],phase),curve['coefficients_cba'])
        residual=predicted-observed
        result['series'][name]={'status':'available','predicted_signed_q':predicted,'residual_signed_q':residual,
                                'rmse':float(np.sqrt(np.mean(residual**2))) if len(samples) else None,
                                'coefficients_cba':curve.get('coefficients_cba'), 'model':curve.get('model','Stored A/B/C')}
    return jsonable(result)
