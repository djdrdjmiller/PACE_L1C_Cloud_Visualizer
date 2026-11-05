"""Selected-bin, fixed-microphysics RFT comparison (not an RFT retrieval).

Published mode properties remain fixed. The explicitly chosen fraction semantics
determine normalized scattering weights; no phase-function peak scaling is used.
"""
import numpy as np
from .cloudbow import interpolate, forward
from .reader import ROW, COL, jsonable


def scattering_weights(fractions, optics, policy='literal'):
    """Convert stated fraction semantics to normalized scattering contributions.

    Number fractions multiply per-particle bulk Csca. Area fractions multiply
    area-weighted Qsca. Literal preserves the user-requested direct comparison.
    """
    fractions=np.asarray(fractions,dtype=float)
    if policy not in ('literal','number','area'):
        raise ValueError('RFT weighting must be literal, number or area')
    if not len(fractions) or not np.isfinite(fractions).all() or np.any(fractions<0) or not np.isclose(fractions.sum(),1,atol=1e-5,rtol=0):
        raise ValueError('Invalid published fraction sum; no repair applied')
    if policy=='literal':return fractions
    name='csca' if policy=='number' else 'qsca'
    factors=np.asarray([item.get(name,np.nan) for item in optics])
    if factors.shape!=fractions.shape or not np.isfinite(factors).all() or np.any(factors<=0):
        raise ValueError(f'Missing or invalid LUT {name}; no optical fallback applied')
    weighted=fractions*factors
    return weighted/weighted.sum()


def thick_cloud(theta_lut, phases, weights, samples, lower, upper, phase_units):
    """Single scattering, tau -> infinity, omega=1; no fitted coefficients.

    Unit-integral phase density p [sr^-1] gives rho_-Q=-pi*p/(mu0+mu).
    Dimensionless P with mean P11=1 gives rho_-Q=-P/(4*(mu0+mu)).
    Dense geometry interpolation is for display only; residuals use source views.
    """
    if phase_units == 'steradian^-1':
        scale=np.pi
    elif phase_units == 'dimensionless':
        scale=.25
    else:
        return {'status':'missing','reason':'LUT phase normalization units not established'}
    valid=[];excluded=[]
    for sample in samples:
        values=[sample.get(k) for k in ('scattering_angle','solar_zenith_angle','sensor_zenith_angle','q_scattering')]
        if any(v is None for v in values) or not np.isfinite(values).all():
            excluded.append({'view':sample['view'],'reason':'Missing geometry or TOA Q'});continue
        angle,sza,vza,_=values
        if not (lower<=angle<=upper and 0<=sza<90 and 0<=vza<90):
            excluded.append({'view':sample['view'],'reason':'Outside angular support or non-daylit/upward geometry'});continue
        valid.append(sample)
    if len(valid)<2:
        return {'status':'missing','reason':'Fewer than two supported source views with valid solar/view geometry','excluded_views':excluded}
    angles=np.array([v['scattering_angle'] for v in valid])
    denominator=np.array([np.cos(np.deg2rad(v['solar_zenith_angle']))+np.cos(np.deg2rad(v['sensor_zenith_angle'])) for v in valid])
    order=np.argsort(angles)
    if np.any(np.diff(angles[order])<=0):
        return {'status':'missing','reason':'Ambiguous repeated scattering angles within branch'}
    lo,hi=angles.min(),angles.max()
    theta=np.unique(np.r_[lo,np.asarray(theta_lut)[(theta_lut>lo)&(theta_lut<hi)],hi])
    factor=-scale/np.interp(theta,angles[order],denominator[order])
    mode_curves=np.array([np.interp(theta,theta_lut,p)*factor for p in phases])
    contributions=np.asarray(weights)[:,None]*mode_curves
    prediction=sum(w*np.interp(angles,theta_lut,p) for w,p in zip(weights,phases))*(-scale/denominator)
    observed=-np.array([v['q_scattering'] for v in valid])
    residual=prediction-observed
    return jsonable({'status':'experimental','theta':theta,'signed_q':contributions.sum(axis=0),
        'signed_full_contributions':contributions,'signed_full_modes':mode_curves,
        'observed_theta':angles,'observed_signed_q':observed,'predicted_signed_q':prediction,
        'source_views':[v['view'] for v in valid],'sample_count':len(valid),'residual_signed_q':residual,
        'rmse':float(np.sqrt(np.mean(residual**2))),'excluded_views':excluded,
        'model':'Optically thick single scattering; no A/B/C; omega=1',
        'phase_units':phase_units,'phase_scale':scale,'geometry_denominator':denominator,
        'geometry_policy':'Actual source solar/view zenith; denominator interpolated within each branch for dense display only; exact source geometry for predictions',
        'warnings':['Experimental thick homogeneous cloud; omega=1; no multiple scattering, cloud fraction, surface or overlying atmosphere',
                    'LUT phase normalization follows recorded convention/evidence; source LUT full P11 integral unavailable for independent verification']})


def comparison(cloud, row, col, observations, weighting='number'):
    if weighting not in ('literal','number','area'):
        raise ValueError('RFT weighting must be literal, number or area')
    data = cloud.data
    index = {ROW: row, COL: col}
    def value(name):
        return float(data[name].isel(index).values) if name in data else np.nan
    qa = value('cloud_rft_quality_retrieval_fail')
    provenance = dict(cloud.provenance, model='A*(w0*P21_0+w1*P21_1)+B*(cos(theta)^2-1)+C',
        status='experimental RFT reflectance reconstruction with original cloudbow coefficients',
        weighting={'interpretation':weighting,'rule':{'literal':'Published fractions used directly',
                   'number':'f_number*Csca / sum(f_number*Csca)', 'area':'f_area*Qsca / sum(f_area*Qsca)'}[weighting],
                   'source':'Supplied Mie LUT at the same red wavelength and log-microphysics interpolation',
                   'optical_units':{'csca':'um^2','cext':'um^2','qsca':'dimensionless','qext':'dimensionless','omega':'dimensionless'},
                   'status':'Explicit experimental fraction interpretation; product fraction semantics not independently verified'},
        observations='Uncorrected canonical scattering-plane Q; negative display transform applied to every component',
        coefficient_policy='Original cloudbow C/B/A only; no coefficient fitting',
        angular_interval=[cloud.rft_lower, cloud.rft_upper])
    result = {'thick_branches': [], 'status': 'missing', 'quality': jsonable(qa), 'provenance': provenance, 'modes': [], 'branches': []}
    provenance['normalization']='Native LUT P21 unchanged; scattering weights normalized by their sum for number/area policies; no peak or P12-integral normalization'
    provenance['full_mode_policy']='Individual full responses use common A/B/C without fraction scaling; their scattering-weighted average is the full mixture (background counted once)'
    if not np.isfinite(qa) or qa != 0:
        return dict(result, reason='RFT retrieval missing or quality flags indicate failure')
    phases, weights, modes, optical_values = [], [], [], []
    for mode in (0, 1):
        radius = value(f'cloud_rft_droplet_effective_radius_mode_{mode}')
        variance = value(f'cloud_rft_droplet_effective_variance_mode_{mode}')
        weight = value(f'cloud_rft_mode_fraction_{mode}')
        description = jsonable({'mode': mode, 'radius_um': radius, 'variance': variance, 'fraction': weight})
        result['modes'].append(description)
        # Public product encodes absent second mode as three CF fills and mode-0 fraction=1.
        if mode == 1 and not any(np.isfinite([radius, variance, weight])) and weights == [1.]:
            description['status'] = 'absent (single-mode product)'
            continue
        if not np.isfinite(weight) or not 0 <= weight <= 1:
            return dict(result, reason=f'Mode {mode}: missing or invalid published fraction')
        if weight == 0:
            description['status'] = 'zero weight; not evaluated'
            continue
        try:
            phase = interpolate(cloud.table, cloud.radii, cloud.variances, radius, variance)
        except ValueError as error:
            return dict(result, reason=f'Mode {mode}: {error}')
        description['status'] = 'fixed'
        optical={}
        for name,table in getattr(cloud,'optics',{}).items():
            try:
                optical[name]=float(interpolate(table[None,:,:],cloud.radii,cloud.variances,radius,variance)[0])
            except ValueError:
                optical[name]=np.nan
        description['lut_optics']=jsonable(dict(optical,omega=optical['csca']/optical['cext'] if optical.get('cext',0)>0 and 'csca' in optical else None))
        optical_values.append(optical)
        phases.append(phase); weights.append(weight); modes.append(mode)
    if not phases or not np.isclose(sum(weights), 1, atol=1e-5, rtol=0):
        return dict(result, reason='Published active fractions do not sum to one; no renormalization applied')
    try:
        weights=scattering_weights(weights,optical_values,weighting).tolist()
    except ValueError as error:
        return dict(result,reason=str(error))
    for mode,weight in zip(modes,weights):
        next(item for item in result['modes'] if item['mode']==mode)['scattering_weight']=weight
    provenance['scattering_weights']=dict(zip(map(str,modes),weights))
    lower=max(cloud.rft_lower,float(cloud.theta[0]))
    upper=min(cloud.rft_upper,float(cloud.theta[-1]))
    use = (cloud.theta >= lower) & (cloud.theta <= upper)
    theta = np.unique(np.r_[lower,cloud.theta[use],upper]).astype(np.float64) if lower<upper else np.array([])
    if len(theta) < 2:
        return dict(result, reason='LUT has no supported RFT angular interval')
    wave = observations['hyperangular_wavelength']
    red = [s for s in observations['samples'] if s['wavelength'] == wave]
    stored_qa=value('cloud_bow_quality_retrieval_fail')
    coefficients=data['cloud_bow_auxiliary_fit'].isel(index).values.ravel() if 'cloud_bow_auxiliary_fit' in data else np.array([])
    stored_reason=None
    if not np.isfinite(stored_qa) or stored_qa!=0:
        stored_reason='Stored cloudbow retrieval missing or quality flags indicate failure'
    elif len(coefficients)!=3 or not np.isfinite(coefficients).all():
        stored_reason='Missing original cloudbow C/B/A coefficients'
    provenance['stored_coefficient_source']='GPC cloud_bow_auxiliary_fit, metadata order C/B/A, same bin; unchanged on both branches'
    for branch in (0, 1):
        candidates = [s for s in red if s['branch'] == branch]
        included, excluded = [], []
        for s in candidates:
            angle, signal = s['scattering_angle'], s['q_scattering']
            if angle is None or signal is None or not np.isfinite([angle, signal]).all():
                excluded.append({'view': s['view'], 'reason': 'Missing geometry or TOA Q'})
            elif not theta[0] <= angle <= theta[-1]:
                excluded.append({'view': s['view'], 'reason': 'Outside native LUT RFT interval'})
            else:
                included.append(s)
        obs_theta = np.array([s['scattering_angle'] for s in included])
        mixture = sum(w*p for w, p in zip(weights, phases))
        phase = np.interp(obs_theta, cloud.theta, mixture)
        stored={'status':'missing','reason':stored_reason,'branch':branch}
        if stored_reason is None:
            components=np.array([np.interp(theta,cloud.theta,p) for p in phases])*np.array(weights)[:,None]
            canonical,display=forward(theta,components.sum(axis=0),coefficients)
            prediction,_=forward(obs_theta,phase,coefficients)
            signal=np.array([s['q_scattering'] for s in included])
            residual=signal-prediction
            c,b,a=coefficients
            full_modes=np.array([forward(theta,np.interp(theta,cloud.theta,p),coefficients)[1] for p in phases])
            stored=jsonable({'status':'experimental','branch':branch,'coefficient_policy':'Original stored cloudbow C/B/A; no new fit or rescaling',
                'coefficients_cba':coefficients,'theta':theta,'canonical':canonical,'signed_q':display,
                'phase_mixture':components.sum(axis=0),'phase_components':components,
                'signed_components':-a*components,'signed_mixture':-a*components.sum(axis=0),
                'signed_full_modes':full_modes,
                'signed_full_contributions':full_modes*np.array(weights)[:,None],
                'signed_background':-(c+b*(np.cos(np.deg2rad(theta))**2-1)),
                'observed_theta':obs_theta,'observed_signed_q':-signal,'predicted_signed_q':-prediction,
                'residual_signed_q':residual,'source_views':[s['view'] for s in included],
                'nominal_angles':[s['angle'] for s in included],'mode_ids':modes,'sample_count':len(included),
                'rmse':float(np.sqrt(np.mean(residual**2))) if len(included) else None,
                'fitted_parameter_count':0,'warnings':['Stored coefficients retain unverified operational LUT/normalization convention'],
                'excluded_views':excluded})
        thick=thick_cloud(np.asarray(cloud.theta),phases,weights,candidates,lower,upper,
                          cloud.provenance.get('lut',{}).get('phase_normalization_units',cloud.provenance.get('lut',{}).get('units')))
        thick.update(branch=branch,mode_ids=modes)
        result['thick_branches'].append(thick)
        stored.update(mode_ids=modes,excluded_views=excluded)
        result['branches'].append(stored)
    provenance['dashboard_model']='thick_branches: optically thick single scattering, omega=1, audited/declared-normalized P21, actual per-view geometry, no A/B/C; branches retain stored A/B/C for RFT P12'
    result['status'] = 'experimental' if any(b['status']=='experimental' for b in result['branches']+result['thick_branches']) else 'missing'
    if result['status'] == 'missing': result['reason'] = stored_reason or 'Original cloudbow coefficients unavailable'
    return jsonable(result)


def add_rayleigh(result, product, observations, row, col, atmosphere):
    """Add existing molecular single-scattering path above the cached cloud top.

    Never modify observations, cloudbow, A/B/C arrays or map correction fields.
    Missing ancillary data retains explicitly labeled cloud-only diagnostics;
    conflicting/unsupported supplied cloud boundaries disable the total curve.
    """
    from .rayleigh import path_reflectance, MODEL
    samples={s['view']:s for s in observations['samples']}
    result['provenance']['rayleigh_addition']={'model':MODEL,'policy':'Add signed scattering-plane molecular Q above cached direct/estimated cloud top; no cloud attenuation/coupling; no atmospheric correction of observations',
        'boundary_source':atmosphere.provenance if atmosphere is not None else None}
    for curve in result.get('thick_branches',[]):
        if curve['status']!='experimental':continue
        curve['rayleigh_status']='unavailable'
        if atmosphere is None:
            curve['warnings'].append('Rayleigh unavailable: no boundary cache; displayed RFT is cloud only')
            continue
        pressure=float(atmosphere.p[row,col]);state=int(atmosphere.state[row,col])
        curve['rayleigh_boundary']={'pressure_hpa':pressure if np.isfinite(pressure) else None,'state':state}
        if state not in (1,3) or not np.isfinite(pressure) or not 0<pressure<=1050:
            curve.update(status='missing',reason='Above-cloud Rayleigh requires a supported direct/estimated cloud-top pressure; no clear-surface substitution')
            continue
        source=[samples[v] for v in curve['source_views']]
        angles=np.array([s['scattering_angle'] for s in source]);order=np.argsort(angles)
        sza=np.array([s['solar_zenith_angle'] for s in source]);vza=np.array([s['sensor_zenith_angle'] for s in source])
        intensity=np.asarray(product.read('intensity_f0'));polarization=np.asarray(product.read('polarization_f0'))
        views=np.array(curve['source_views'])
        f0=intensity[views];pf0=polarization[views]
        if not np.isfinite(f0).all() or not np.isfinite(pf0).all() or np.any(f0<=0) or np.any(pf0<=0):
            curve.update(status='missing',reason='Invalid intensity/polarization irradiance ratio for Rayleigh addition');continue
        ratio=f0/pf0;wave=observations['hyperangular_wavelength']
        _,qr,_=path_reflectance(wave,pressure,sza,vza,angles)
        molecular=-qr*ratio
        theta=np.array(curve['theta'])
        # Dense display geometry stays within measured branch support.
        mu0=np.interp(theta,angles[order],np.cos(np.deg2rad(sza[order])))
        mu=np.interp(theta,angles[order],np.cos(np.deg2rad(vza[order])))
        _,dense_q,_=path_reflectance(wave,pressure,np.rad2deg(np.arccos(mu0)),np.rad2deg(np.arccos(mu)),theta)
        dense=-dense_q*np.interp(theta,angles[order],ratio[order])
        curve['signed_cloud_only']=curve['signed_q']
        curve['predicted_cloud_only_signed_q']=curve['predicted_signed_q']
        curve['signed_rayleigh']=dense.tolist();curve['predicted_rayleigh_signed_q']=molecular.tolist()
        curve['signed_q']=(np.asarray(curve['signed_cloud_only'])+dense).tolist()
        curve['predicted_signed_q']=(np.asarray(curve['predicted_cloud_only_signed_q'])+molecular).tolist()
        residual=np.asarray(curve['predicted_signed_q'])-curve['observed_signed_q']
        curve['residual_signed_q']=residual.tolist();curve['rmse']=float(np.sqrt(np.mean(residual**2)))
        curve['warnings']=[w.replace('surface or overlying atmosphere','surface; molecular path handled separately') for w in curve['warnings']]
        curve['rayleigh_status']='included'
        curve['model']=('User-prescribed four-order droplet approximation' if 'scattering_order_weights' in curve else 'Optically thick droplet single scattering')+' + above-cloud Rayleigh; no A/B/C; omega=1'
        curve['warnings'].append('Above-cloud Rayleigh added; cloud attenuation, cloud/molecular coupling and resolved multiple scattering omitted')
    return jsonable(result)


ORDER_WEIGHTS=(1.,.5,.1,.01)


def approximate_scattering_orders(result):
    """User-prescribed phase-preserving order proxy, not vector RT or a fit.

    Each order repeats the same signed droplet shape; Rayleigh is added later
    and is never multiplied. Retain the first-order arrays for exact audits.
    """
    if 'scattering_order_approximation' in result['provenance']:
        raise ValueError('Scattering-order approximation already applied')
    gain=sum(ORDER_WEIGHTS)
    result['provenance']['dashboard_model']='Four-order phase-preserving droplet approximation with fixed gain 1.61; above-cloud Rayleigh added separately when supported; RFT P12 retains original A/B/C'
    result['provenance']['scattering_order_approximation']={
        'orders':[1,2,3,4],'relative_weights':list(ORDER_WEIGHTS),'droplet_gain':gain,
        'source':'User-prescribed experiment; Cornet Fig. 9 motivates low-order convergence but does not establish these coefficients',
        'assumptions':'Same signed angular shape, scattering plane and geometry factor for all four orders; same multiplier for both droplet modes; Rayleigh excluded; no fit'}
    for curve in result.get('thick_branches',[]):
        if curve['status']!='experimental':continue
        curve['signed_single_scattering']=curve['signed_q']
        curve['predicted_single_scattering_signed_q']=curve['predicted_signed_q']
        curve['single_scattering_contributions']=curve['signed_full_contributions']
        curve['signed_order_contributions']=(np.array(ORDER_WEIGHTS)[:,None]*np.array(curve['signed_q'])).tolist()
        for key in ('signed_q','signed_full_contributions','signed_full_modes','predicted_signed_q'):
            curve[key]=(gain*np.asarray(curve[key])).tolist()
        residual=np.array(curve['predicted_signed_q'])-curve['observed_signed_q']
        curve['residual_signed_q']=residual.tolist();curve['rmse']=float(np.sqrt(np.mean(residual**2)))
        curve['scattering_order_weights']=list(ORDER_WEIGHTS)
        curve['model']='User-prescribed four-order phase-preserving approximation; droplet gain 1.61; no A/B/C; omega=1'
        curve['warnings']=[w.replace('no multiple scattering','no resolved multiple scattering') for w in curve['warnings']]
        curve['warnings'].append('Orders 1–4 repeat the same droplet shape with weights 1, 0.5, 0.1, 0.01; heuristic, not resolved scattering orders')
    return jsonable(result)
