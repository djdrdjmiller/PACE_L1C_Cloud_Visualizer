from types import SimpleNamespace
from dataclasses import asdict
import numpy as np
import xarray as xr
import pytest
from fastapi.testclient import TestClient
from pace_l1c.rft import comparison
from pace_l1c.cloudbow import Cloudbow, interpolate
from pace_l1c.reader import ROW, COL
from pace_l1c.fixtures import create_pair
from pace_l1c.scene import Scene, Recipe
from pace_l1c.service import create_app


def setup_comparison():
    theta=np.linspace(130,170,401)
    radii=np.array([3.,6.,12.]);variances=np.array([.01,.04,.16])
    table=np.empty((len(theta),3,3))
    for i,v in enumerate(variances):
        for j,r in enumerate(radii):
            table[:,i,j]=np.sin((theta-130)*r/15)*np.exp(-v*(theta-150)**2/100)
    fields={'cloud_rft_quality_retrieval_fail':0,'cloud_rft_mode_fraction_0':.7,'cloud_rft_mode_fraction_1':.3,
            'cloud_rft_droplet_effective_radius_mode_0':6.,'cloud_rft_droplet_effective_radius_mode_1':12.,
            'cloud_rft_droplet_effective_variance_mode_0':.04,'cloud_rft_droplet_effective_variance_mode_1':.16}
    data=xr.Dataset({k:((ROW,COL),[[float(v)]]) for k,v in fields.items()})
    data['cloud_bow_quality_retrieval_fail']=((ROW,COL),[[0.]])
    data['cloud_bow_auxiliary_fit']=((ROW,COL,'coeff'),[[[.003,.1,.5]]])
    cloud=SimpleNamespace(data=data,theta=theta,table=table,radii=radii,variances=variances,
                          lower=134.,upper=166.,rft_lower=134.,rft_upper=166.,rft_required=[136,150],provenance={'lut':{'units':'dimensionless'}})
    mixture=.7*table[:,1,1]+.3*table[:,2,2]
    samples=[]
    for branch,angles in enumerate([np.linspace(135,165,20)[::-1],np.linspace(136,164,18)]):
        for i,t in enumerate(angles):
            signal=.01+.03*(np.cos(np.deg2rad(t))**2-1)+.07*np.interp(t,theta,mixture)
            samples.append({'view':branch*30+i,'branch':branch,'angle':i-15.,'wavelength':664.6,'scattering_angle':t,'q_scattering':signal,'solar_zenith_angle':30.,'sensor_zenith_angle':40.})
    return cloud,{'hyperangular_wavelength':664.6,'samples':samples}


def test_fixed_weights_shared_coefficients_separate_branches_and_source_identity():
    cloud,obs=setup_comparison()
    result=comparison(cloud,0,0,obs,weighting='literal')
    assert result['status']=='experimental'
    for branch in result['branches']:
        assert branch['coefficients_cba']==[.003,.1,.5]
        assert branch['fitted_parameter_count']==0
        np.testing.assert_allclose(branch['signed_q'],-np.array(branch['canonical']))
        np.testing.assert_allclose(np.sum(branch['signed_components'],axis=0),branch['signed_mixture'])
        np.testing.assert_allclose(branch['signed_mixture']+np.array(branch['signed_background']),branch['signed_q'])
        np.testing.assert_allclose(branch['residual_signed_q'],np.array(branch['predicted_signed_q'])-branch['observed_signed_q'])
        assert branch['rmse']>0  # Observations came from different ABC: no refit is allowed.
        assert branch['source_views']==[s['view'] for s in obs['samples'] if s['branch']==branch['branch']]
    assert [m['fraction'] for m in result['modes']]==[.7,.3]


def test_reject_invalid_quality_weights_lut_and_allow_sparse_branch():
    cloud,obs=setup_comparison()
    cloud.data.cloud_rft_quality_retrieval_fail.values[:]=1024
    assert 'quality' in comparison(cloud,0,0,obs,weighting='literal')['reason']
    cloud.data.cloud_rft_quality_retrieval_fail.values[:]=0
    cloud.data.cloud_rft_mode_fraction_1.values[:]=.2
    assert 'sum to one' in comparison(cloud,0,0,obs,weighting='literal')['reason']
    cloud.data.cloud_rft_mode_fraction_1.values[:]=.3
    cloud.data.cloud_rft_droplet_effective_radius_mode_1.values[:]=75
    assert 'outside' in comparison(cloud,0,0,obs,weighting='literal')['reason']
    cloud.data.cloud_rft_droplet_effective_radius_mode_1.values[:]=12
    obs['samples']=[s for s in obs['samples'] if s['branch']==0 or s['view']<34]
    result=comparison(cloud,0,0,obs,weighting='literal')
    assert result['branches'][0]['status']=='experimental'
    assert result['branches'][1]['status']=='experimental'
    assert result['branches'][1]['sample_count']==4


def test_fill_second_mode_only_valid_when_product_reports_single_mode():
    cloud,obs=setup_comparison()
    for key in ['cloud_rft_mode_fraction_1','cloud_rft_droplet_effective_radius_mode_1','cloud_rft_droplet_effective_variance_mode_1']:
        cloud.data[key].values[:]=np.nan
    assert 'invalid published fraction' in comparison(cloud,0,0,obs,weighting='literal')['reason']
    cloud.data.cloud_rft_mode_fraction_0.values[:]=1
    result=comparison(cloud,0,0,obs,weighting='literal')
    assert result['modes'][1]['status']=='absent (single-mode product)'
    assert all(b['mode_ids']==[0] for b in result['branches'])


def test_residual_sign_and_excluded_missing_samples():
    cloud,obs=setup_comparison()
    obs['samples'][0]['q_scattering']=None
    obs['samples'][1]['scattering_angle']=170
    obs['samples'][3]['q_scattering']+=.001
    fit=comparison(cloud,0,0,obs,weighting='literal')['branches'][0]
    assert len(fit['excluded_views'])==2
    np.testing.assert_allclose(fit['residual_signed_q'],np.array(fit['predicted_signed_q'])-fit['observed_signed_q'])


def test_cloud_metadata_flags_and_missing_values_without_substitution():
    cloud,_=setup_comparison()
    cloud.provenance={'gpc':{'product_name':'SYNTHETIC_GPC'},'alignment_max_error_m':0,'lut':{'units':'dimensionless'}}
    cloud.data['cloud_quality']=((ROW,COL),[[5.]],{'bit_0':'Cloud ambiguity','bit_2':'Size capped','units':'1'})
    cloud.data['cloud_top_pressure']=((ROW,COL),[[np.nan]],{'units':'Pa','long_name':'Cloud top pressure'})
    result=Cloudbow.diagnostics(cloud,0,0)
    assert result['fields']['cloud_quality']['flags']==['Cloud ambiguity','Size capped']
    assert result['fields']['cloud_quality']['status']=='flagged'
    assert result['fields']['cloud_top_pressure']['value'] is None
    assert result['fields']['cloud_top_pressure']['units']=='Pa'


def test_on_demand_api_missing_product_recipe_and_bounds(tmp_path):
    with_scene=Scene(*create_pair(tmp_path/'pair'))
    try:
        client=TestClient(create_app(with_scene))
        assert client.get('/api/bin/5/6').json()['rft']['status']=='disabled'
        assert client.get('/api/bin/5/6?rft=true').json()['rft']['status']=='unavailable'
        assert client.get('/api/bin/999/6?rft=true').status_code==422
        recipe=Recipe(rft_overlay=True,selected=[5,6])
        assert Recipe(**asdict(recipe)).validate(with_scene.shape).rft_overlay
        with pytest.raises(ValueError):Recipe(rft_overlay='yes').validate(with_scene.shape)
    finally:with_scene.close()


def test_utf8_gpc_attribute_surrogate_recovery():
    import json
    from pace_l1c.reader import jsonable
    cloud,_=setup_comparison()
    cloud.provenance={'gpc':{'product_name':'SYNTHETIC_GPC'},'alignment_max_error_m':0,'lut':{'units':'dimensionless'}}
    cloud.data['cloud_top_altitude']=((ROW,COL),[[2100.]],{'units':'m','long_name':'Angle 180\udcc2\udcb0; unknown byte \udcff'})
    result=Cloudbow.diagnostics(cloud,0,0)
    assert result['fields']['cloud_top_altitude']['description']=='Angle 180°; unknown byte \\xff'
    json.dumps(result,ensure_ascii=False,allow_nan=False).encode('utf8')
    assert jsonable('\ud800')=='\\ud800'


@pytest.mark.parametrize('weighting',['literal','number','area'])
def test_api_and_export_share_fixed_comparison_and_component_recipe(tmp_path,weighting):
    import json
    from PIL import Image
    from pace_l1c.render import export
    cloud,obs=setup_comparison()
    for sample in obs['samples']:
        sample['signed_q']=-sample['q_scattering']
    s=Scene(*create_pair(tmp_path/'pair'))
    # This synthetic adapter isolates the API/export contract from reader tests.
    cloud.provenance={'gpc':{'product_name':'SYNTHETIC_GPC'},'alignment_max_error_m':0,'lut':{'units':'dimensionless'}}
    cloud.diagnostics=lambda row,col:Cloudbow.diagnostics(cloud,row,col)
    cloud.solution=lambda row,col:{'status':'missing','reason':'No stored fit in this fixture'}
    cloud.close=lambda:None
    cloud.optics={'csca':np.broadcast_to([100.,200.,800.],(3,3)),'qsca':np.full((3,3),2.)}
    s.cloudbow=cloud
    s.gpc=cloud
    s.harp.diagnostics=lambda row,col:obs
    try:
        client=TestClient(create_app(s))
        response=client.get(f'/api/bin/0/0?rft=true&rft_weighting={weighting}')
        assert response.status_code==200
        expected=response.json()['rft']
        recipe=Recipe(selected=[0,0],rft_overlay=True,rft_components=True,rft_p12=True,diagnostic_quantity='signed_q',rft_weighting=weighting)
        paths=export(s,recipe,tmp_path/'comparison',width_mm=180,height_mm=150,dpi=80)
        metadata=json.loads(paths[2].read_text())
        assert metadata['rft']==expected
        assert metadata['polarimetric_residuals']==response.json()['residuals']
        assert metadata['recipe']['rft_components'] is True
        assert metadata['recipe']['rft_p12'] is True
        assert metadata['selected_cloud_diagnostics']['fields']['cloud_rft_mode_fraction_0']['value']==.7
        with Image.open(paths[0]) as image:assert image.size==(566,472)
        from pypdf import PdfReader
        page=PdfReader(paths[1]).pages[0]
        text=page.extract_text()
        assert 'Mode 0 contribution' in text
        assert 'Mode 0 P12' in text
        assert float(page.mediabox.width)==pytest.approx(180/25.4*72,abs=.01)
    finally:s.close()


def test_stored_abc_linear_combination_no_refit_or_renormalization():
    from pace_l1c.cloudbow import forward
    cloud,obs=setup_comparison()
    result=comparison(cloud,0,0,obs,weighting='literal')
    for branch in result['branches']:
        stored=branch
        assert stored['coefficients_cba']==[.003,.1,.5]
        assert stored['fitted_parameter_count']==0
        np.testing.assert_allclose(np.sum(stored['signed_components'],axis=0)+stored['signed_background'],stored['signed_q'])
        theta=np.array(stored['theta'])
        phase0=np.interp(theta,cloud.theta,cloud.table[:,1,1])
        phase1=np.interp(theta,cloud.theta,cloud.table[:,2,2])
        # A unit-sum mixture retains the common LUT scale and background exactly once.
        model0,_=forward(theta,phase0,[.003,.1,.5])
        model1,_=forward(theta,phase1,[.003,.1,.5])
        np.testing.assert_allclose(stored['canonical'],.7*model0+.3*model1,atol=1e-14)
    np.testing.assert_allclose(result['branches'][0]['signed_q'],result['branches'][1]['signed_q'])
    obs['samples']=obs['samples'][:2]
    sparse=comparison(cloud,0,0,obs,weighting='literal')
    assert sparse['branches'][0]['status']=='experimental'
    assert sparse['branches'][1]['sample_count']==0
    cloud.data.cloud_bow_quality_retrieval_fail.values[:]=256
    assert 'quality' in comparison(cloud,0,0,obs,weighting='literal')['branches'][0]['reason']


def test_scattering_weight_conversion_number_area_and_literal():
    from pace_l1c.rft import scattering_weights
    fractions=[.6,.4]
    optics=[{'csca':100.,'qsca':2.},{'csca':400.,'qsca':2.}]
    np.testing.assert_allclose(scattering_weights(fractions,optics,'number'),[60/220,160/220])
    np.testing.assert_allclose(scattering_weights(fractions,optics,'area'),fractions)
    np.testing.assert_allclose(scattering_weights(fractions,optics,'literal'),fractions)
    # Equal number fractions of radii r and 2r: omega=1, Qext=2 gives a 1:4 scattering ratio.
    np.testing.assert_allclose(scattering_weights([.5,.5],optics,'number'),[.2,.8])
    with pytest.raises(ValueError,match='no optical fallback'):
        scattering_weights(fractions,[{},{}],'number')
    with pytest.raises(ValueError,match='Invalid published fraction'):
        scattering_weights([.6,.3],optics,'number')


def test_number_weighted_mixture_preserves_original_abc_and_reported_fractions():
    cloud,obs=setup_comparison()
    cloud.optics={'csca':np.broadcast_to([100.,200.,800.],(3,3)),
                  'cext':np.broadcast_to([100.,200.,800.],(3,3)),
                  'qsca':np.full((3,3),2.),'qext':np.full((3,3),2.)}
    direct=comparison(cloud,0,0,obs,weighting='literal')
    number=comparison(cloud,0,0,obs)  # User-confirmed default is number fractions.
    weights=np.array([.7*200,.3*800]);weights/=weights.sum()
    assert [m['fraction'] for m in number['modes']]==[.7,.3]
    np.testing.assert_allclose([m['scattering_weight'] for m in number['modes']],weights)
    stored=number['branches'][0]
    assert stored['coefficients_cba']==[.003,.1,.5]
    theta=np.array(stored['theta'])
    expected=weights[0]*np.interp(theta,cloud.theta,cloud.table[:,1,1])+weights[1]*np.interp(theta,cloud.theta,cloud.table[:,2,2])
    np.testing.assert_allclose(stored['phase_mixture'],expected)
    assert not np.allclose(stored['signed_q'],direct['branches'][0]['signed_q'])
    assert number['modes'][0]['lut_optics']['omega']==1
    cloud.optics['csca']=np.full((3,3),np.nan)
    assert 'csca' in comparison(cloud,0,0,obs)['reason']
    assert comparison(cloud,0,0,obs,weighting='literal')['status']=='experimental'


def test_saved_legacy_rft_recipe_preserves_literal_weights():
    assert Recipe().rft_weighting=='number'
    assert Recipe.from_dict({'rft_overlay':True}).rft_weighting=='literal'
    assert Recipe.from_dict({'rft_overlay':True,'rft_weighting':'number'}).rft_weighting=='number'


@pytest.mark.parametrize('dtype',[np.float32,np.float64])
def test_single_mode_equal_cloudbow_microphysics_has_identical_full_curve(dtype):
    cloud,obs=setup_comparison()
    cloud.theta=cloud.theta.astype(dtype)
    cloud.table=cloud.table.astype(dtype)
    cloud.radii=cloud.radii.astype(dtype)
    cloud.variances=cloud.variances.astype(dtype)
    cloud.lower=cloud.rft_lower;cloud.upper=cloud.rft_upper
    cloud.optics={'csca':np.full((3,3),123.)}
    cloud.data.cloud_rft_mode_fraction_0.values[:]=1.
    for name in ['cloud_rft_mode_fraction_1','cloud_rft_droplet_effective_radius_mode_1','cloud_rft_droplet_effective_variance_mode_1']:
        cloud.data[name].values[:]=np.nan
    cloud.data['cloud_bow_droplet_effective_radius']=((ROW,COL),[[6.]])
    cloud.data['cloud_bow_droplet_effective_variance']=((ROW,COL),[[.04]])
    cloudbow=Cloudbow.solution(cloud,0,0)
    result=comparison(cloud,0,0,obs)
    stored=result['branches'][0]
    assert result['modes'][0]['scattering_weight']==1.
    assert stored['coefficients_cba']==cloudbow['coefficients_cba']
    assert stored['theta']==cloudbow['theta']
    np.testing.assert_array_equal(stored['signed_q'],cloudbow['signed_q'])
    np.testing.assert_array_equal(stored['phase_mixture'],cloudbow['phase'])
    np.testing.assert_allclose(np.array(stored['signed_components'][0])+stored['signed_background'],stored['signed_q'],rtol=0,atol=2*np.finfo(float).eps)


def test_full_mode_responses_share_abc_and_weighted_sum_reproduces_mixture():
    from pace_l1c.cloudbow import forward
    cloud,obs=setup_comparison()
    cloud.optics={'csca':np.broadcast_to([100.,200.,800.],(3,3))}
    result=comparison(cloud,0,0,obs)
    weights=np.array([m['scattering_weight'] for m in result['modes']])
    for curve in result['branches']:
        theta=np.array(curve['theta'])
        for index,(radius,variance) in enumerate([(6.,.04),(12.,.16)]):
            phase=interpolate(cloud.table,cloud.radii,cloud.variances,radius,variance)
            _,expected=forward(theta,np.interp(theta,cloud.theta,phase),curve['coefficients_cba'])
            np.testing.assert_allclose(curve['signed_full_modes'][index],expected,atol=1e-15)
        np.testing.assert_allclose(np.array(curve['signed_full_modes'])*weights[:,None],curve['signed_full_contributions'])
        np.testing.assert_allclose(np.sum(curve['signed_full_contributions'],axis=0),curve['signed_q'],atol=1e-15)

def test_removed_coefficient_refit_is_rejected():
    with pytest.raises(ValueError,match='refitting was removed'):
        Recipe(rft_scaling='refit').validate((10,10))


def test_thick_cloud_absolute_scale_units_geometry_and_additive_components():
    from pace_l1c.rft import thick_cloud
    # Independent analytic example: mu0=1, mu=.5, P21=-.6 / -.3.
    angles=np.array([140.,150.,160.])
    phases=np.array([[-.6]*3,[-.3]*3])
    samples=[dict(view=i,scattering_angle=t,solar_zenith_angle=0.,sensor_zenith_angle=60.,q_scattering=-.02)
             for i,t in enumerate(angles)]
    out=thick_cloud(angles,phases,[.75,.25],samples,135,165,'dimensionless')
    expected=(.75*.6+.25*.3)/(4*1.5)
    np.testing.assert_allclose(out['signed_q'],expected)
    np.testing.assert_allclose(np.sum(out['signed_full_contributions'],axis=0),out['signed_q'])
    np.testing.assert_allclose(out['residual_signed_q'],expected-.02)
    density=thick_cloud(angles,phases/(4*np.pi),[.75,.25],samples,135,165,'steradian^-1')
    np.testing.assert_allclose(density['signed_q'],out['signed_q'])
    # Angle-dependent geometry must affect amplitude at the source samples.
    samples[1]['solar_zenith_angle']=60.
    varied=thick_cloud(angles,phases,[.75,.25],samples,135,165,'dimensionless')
    assert varied['predicted_signed_q'][1]==pytest.approx((.75*.6+.25*.3)/4)
    assert thick_cloud(angles,phases,[.75,.25],samples,135,165,None)['status']=='missing'
    for sample in samples:sample['sensor_zenith_angle']=None
    assert thick_cloud(angles,phases,[.75,.25],samples,135,165,'dimensionless')['status']=='missing'


def test_thick_rft_is_independent_of_cloudbow_coefficients_and_quality():
    cloud,obs=setup_comparison()
    original=comparison(cloud,0,0,obs,weighting='literal')['thick_branches']
    cloud.data.cloud_bow_auxiliary_fit.values[:]=np.nan
    cloud.data.cloud_bow_quality_retrieval_fail.values[:]=1
    changed=comparison(cloud,0,0,obs,weighting='literal')
    assert changed['status']=='experimental'
    assert changed['thick_branches']==original
    assert all(b['status']=='missing' for b in changed['branches'])
    assert all(b['status']=='experimental' for b in original)
    from pace_l1c.residuals import compare
    residuals=compare(obs,{'status':'missing','reason':'No cloudbow'},changed,(134,166))
    curve=original[0]
    np.testing.assert_allclose(residuals['series']['rft']['predicted_signed_q'],curve['predicted_signed_q'])
    np.testing.assert_allclose(residuals['series']['rft']['residual_signed_q'],curve['residual_signed_q'])


def test_rayleigh_addition_has_correct_sign_irradiance_and_component_closure():
    import copy
    from pace_l1c.rft import add_rayleigh
    from pace_l1c.rayleigh import path_reflectance
    cloud,obs=setup_comparison()
    original=comparison(cloud,0,0,obs,weighting='literal')
    untouched=copy.deepcopy(original)
    observations_before=copy.deepcopy(obs)
    product=SimpleNamespace(read=lambda name:np.full(60,2. if name=='intensity_f0' else 1.))
    atmosphere=SimpleNamespace(p=np.array([[500.]]),state=np.array([[1]]),provenance={'test':'synthetic cloud top'})
    updated=add_rayleigh(copy.deepcopy(original),product,obs,0,0,atmosphere)
    assert updated['branches']==original['branches']  # A/B/C comparison unchanged.
    assert obs==observations_before and original==untouched
    for curve,baseline in zip(updated['thick_branches'],original['thick_branches']):
        assert curve['rayleigh_status']=='included'
        assert np.all(np.asarray(curve['signed_rayleigh'])>=0)
        np.testing.assert_allclose(np.sum(curve['signed_full_contributions'],axis=0)+curve['signed_rayleigh'],curve['signed_q'])
        np.testing.assert_allclose(np.array(baseline['predicted_signed_q'])+curve['predicted_rayleigh_signed_q'],curve['predicted_signed_q'])
        np.testing.assert_allclose(np.array(curve['predicted_signed_q'])-curve['observed_signed_q'],curve['residual_signed_q'])
        sample=next(s for s in obs['samples'] if s['view']==curve['source_views'][0])
        _,canonical_q,_=path_reflectance(664.6,500.,sample['solar_zenith_angle'],sample['sensor_zenith_angle'],sample['scattering_angle'])
        assert curve['predicted_rayleigh_signed_q'][0]==pytest.approx(-2*canonical_q)
    # No assumed pressure on missing ancillary; no surface-boundary substitution.
    unavailable=add_rayleigh(copy.deepcopy(original),product,obs,0,0,None)
    assert unavailable['thick_branches'][0]['signed_q']==original['thick_branches'][0]['signed_q']
    assert unavailable['thick_branches'][0]['rayleigh_status']=='unavailable'
    atmosphere.state[:]=2
    rejected=add_rayleigh(copy.deepcopy(original),product,obs,0,0,atmosphere)
    assert rejected['thick_branches'][0]['status']=='missing'
    assert 'surface substitution' in rejected['thick_branches'][0]['reason']


def test_prescribed_four_orders_scale_droplets_only_and_preserve_abc():
    import copy
    from pace_l1c.rft import approximate_scattering_orders, add_rayleigh
    cloud,obs=setup_comparison()
    original=comparison(cloud,0,0,obs,weighting='literal')
    orders=approximate_scattering_orders(copy.deepcopy(original))
    assert orders['branches']==original['branches']
    assert orders['provenance']['scattering_order_approximation']['relative_weights']==[1.,.5,.1,.01]
    for curve,base in zip(orders['thick_branches'],original['thick_branches']):
        np.testing.assert_allclose(curve['signed_q'],1.61*np.array(base['signed_q']))
        for i,weight in enumerate([1.,.5,.1,.01]):
            np.testing.assert_allclose(curve['signed_order_contributions'][i],weight*np.array(base['signed_q']))
        np.testing.assert_allclose(np.sum(curve['signed_order_contributions'],axis=0),curve['signed_q'])
        np.testing.assert_allclose(np.sum(curve['signed_full_contributions'],axis=0),curve['signed_q'])
        assert curve['predicted_single_scattering_signed_q']==base['predicted_signed_q']
    with pytest.raises(ValueError,match='already applied'):approximate_scattering_orders(orders)
    product=SimpleNamespace(read=lambda name:np.ones(60))
    atmosphere=SimpleNamespace(p=np.array([[600.]]),state=np.array([[1]]),provenance={})
    base_ray=add_rayleigh(copy.deepcopy(original),product,obs,0,0,atmosphere)
    combined=add_rayleigh(orders,product,obs,0,0,atmosphere)
    for curve,base in zip(combined['thick_branches'],base_ray['thick_branches']):
        np.testing.assert_array_equal(curve['signed_rayleigh'],base['signed_rayleigh'])
        np.testing.assert_allclose(curve['predicted_signed_q'],1.61*np.array(base['predicted_cloud_only_signed_q'])+base['predicted_rayleigh_signed_q'])
        np.testing.assert_allclose(np.sum(curve['signed_full_contributions'],axis=0)+curve['signed_rayleigh'],curve['signed_q'])
