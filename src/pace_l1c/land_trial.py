"""Offline evaluation of the existing Rayleigh calculation over classified land.

No model/pressure changes, fallback filling, or dashboard policy changes.
"""
import numpy as np

FIELDS=('total','q','u','q_scattering','u_scattering','signed_q','signed_u','polarized','dolp')


def apply_land_trial(current,molecular,surface_class):
    """Replace land fields by the existing component-corrected model result.

    Water/unknown fields remain exactly the production result. Unsupported land
    becomes missing, rather than silently falling back to TOA in a mixed image.
    """
    land=np.asarray(surface_class)==1
    result=dict(current)
    for name in FIELDS:
        if name in molecular:
            value=np.asarray(molecular[name])
            if value.shape!=land.shape or np.shape(current[name])!=land.shape:
                raise ValueError('Land trial requires matching original-bin fields')
            result[name]=np.where(land,value,current[name])
    return result


def distribution(values):
    values=np.asarray(values);finite=values[np.isfinite(values)]
    if not finite.size:return None
    return dict(zip(('min','p05','median','p95','max'),map(float,np.percentile(finite,[0,5,50,95,100]))))


def field_summary(raw,trial,mask):
    """Counts use observed land as denominator; deltas use paired finite values."""
    raw,trial=np.asarray(raw),np.asarray(trial)
    observed=np.asarray(mask)&np.isfinite(raw)
    paired=observed&np.isfinite(trial)
    return {'observed_bins':int(observed.sum()),'corrected_bins':int(paired.sum()),
            'lost_bins':int((observed&~np.isfinite(trial)).sum()),
            'negative_before':int((paired&(raw<0)).sum()),
            'negative_after':int((paired&(trial<0)).sum()),
            'newly_negative':int((paired&(raw>=0)&(trial<0)).sum()),
            'above_one_after':int((paired&(trial>1)).sum()),
            'raw':distribution(raw[paired]),'trial':distribution(trial[paired]),
            'trial_minus_toa':distribution((trial-raw)[paired])}
