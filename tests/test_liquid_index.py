from dataclasses import asdict
import json
from types import SimpleNamespace
import numpy as np
import pytest
import xarray as xr
from fastapi.testclient import TestClient
from pace_l1c.liquid_index import calculate,diagnostics,map_layers,display_scale,adaptive_window,baseline_angle_scale
from pace_l1c.scene import Scene,Recipe
from pace_l1c.fixtures import create_pair
from pace_l1c.render import preview,colors,export
from pace_l1c.service import create_app
from pace_l1c.reader import ROW,COL


def samples():
    x=np.array([120,125,129,132,135,137,143,145,148,151,155,160.])
    baseline=.02+.0001*(x-140)
    y=baseline.copy();y[(x>=135)&(x<=145)]+=[.01,.04,.01,.02]
    return x,y


def test_independent_hand_calculation_discrete_and_trapezoid():
    x,y=samples();r=calculate(x,y,np.arange(len(x))+20)
    assert r['status']=='available'
    assert r['slope_per_degree']==pytest.approx(.0001)
    assert r['normalization_baseline']==pytest.approx(.0195)
    assert r['discrete']['value']==pytest.approx(.02/.0195)
    # Areas: 2*(.01+.04)/2 + 6*(.04+.01)/2 + 2*(.01+.02)/2.
    assert r['trapezoidal']['integral_reflectance_degrees']==pytest.approx(.23)
    assert r['trapezoidal']['value']==pytest.approx(.023/.0195)
    assert r['source_views'][4]==24
    # Reordering input cannot change either estimator/reference angle.
    reverse=calculate(x[::-1],y[::-1]);assert reverse['discrete']==r['discrete']
    assert reverse['trapezoidal']==r['trapezoidal']


def test_linear_interpolated_endpoints_no_extrapolation_and_negative_excess():
    x=np.array([120,125,129,134,136,140,144,146,151,155,160.])
    y=np.full(len(x),.02);y[(x>=134)&(x<=146)]=.01
    r=calculate(x,y)
    assert r['discrete']['value']==pytest.approx(-.5)
    assert r['trapezoidal']['value']==pytest.approx(-.5)
    assert r['trapezoidal']['theta']==[135,136,140,144,145]
    assert r['trapezoidal']['observed'][0]==pytest.approx(.01)
    assert calculate(x[x>=136],y[x>=136])['status']=='missing'  # absent left baseline
    dup=calculate(np.r_[x,140],np.r_[y,.01])
    assert dup['discrete']['status']=='available' and dup['trapezoidal']['status']=='missing'


def test_support_missing_zeros_and_scale_invariance():
    x,y=samples()
    for a,b in ((x[:6],y[:6]),(x,np.zeros_like(y)),(x,np.full_like(y,np.nan))):
        r=calculate(a,b);assert r['status']=='missing' and r['discrete']['value'] is None
        json.dumps(r,allow_nan=False)
    r=calculate(x,y);scaled=calculate(x,y*13)
    assert scaled['discrete']['value']==pytest.approx(r['discrete']['value'])
    assert scaled['trapezoidal']['value']==pytest.approx(r['trapezoidal']['value'])
    flat=calculate(x,np.full_like(x,.02));assert flat['discrete']['value']==pytest.approx(0,abs=1e-12)
    assert calculate(x,np.where(x==137,np.nan,y))['peak_count']==3
    with pytest.raises(ValueError):calculate([[1,2]],[[3,4]])


def test_quantity_branch_and_operational_separation():
    x,y=samples();s=[]
    for branch in (0,1):
        for i,(angle,value) in enumerate(zip(x,y)):
            s.append(dict(wavelength=664.6,branch=branch,view=branch*30+i,scattering_angle=angle,signed_q=value,polarized=value+(branch+1)*.01))
    # Other wavelengths must never enter the selected hyperangular calculation.
    s.extend([dict(sample,wavelength=440.,signed_q=1000.,polarized=2000.) for sample in s.copy()])
    r=diagnostics({'hyperangular_wavelength':664.6,'samples':s},2.5,{'name':'synthetic'})
    assert r['operational_value']==2.5
    assert [b['branch'] for b in r['branches']]==[0]
    with pytest.raises(ValueError):Recipe(liquid_index_branch='2').validate((2,2))
    for branch in r['branches']:
        q=branch['series']['signed_q'];mag=branch['series']['polarized']
        assert mag['discrete']['value']<q['discrete']['value']
        assert q['discrete']['difference_from_operational']==pytest.approx(q['discrete']['value']-2.5)
        assert q['discrete']['value']==pytest.approx(.02/.0195)


def test_batched_map_has_known_finite_values_and_preserves_missing_bins():
    x,y=samples();x=np.r_[x,179,160,150,140];y=np.r_[y,.02,.02,.02,.04]
    class Product:
        shape=(3,2);distance=1.
        channels=[dict(view=i,wavelength=664.6,angle=60-i*4) for i in range(len(x))]
        def read(self,name,row=None):
            if name=='polarization_f0':return np.full(len(x),1000.)
            values={'number_of_observations':np.ones_like(x),'solar_zenith_angle':np.full_like(x,30.),
                'rotation_angle':np.zeros_like(x),'scattering_angle':x,
                'q':-y*1000*np.cos(np.deg2rad(30))/np.pi,'u':np.zeros_like(x)}[name]
            cube=np.broadcast_to(values,(*self.shape,len(x))).copy()
            if name=='number_of_observations':cube[0,0]=0
            return cube[row]
    maps=map_layers(Product(),batch_rows=1)
    assert np.isnan(maps['discrete'][0,0]) and np.isnan(maps['trapezoidal'][0,0])
    assert maps['discrete'][1,1]==pytest.approx(.02/.0195)
    assert maps['trapezoidal'][1,1]==pytest.approx(.023/.0195)


def test_native_computed_maps_equal_selected_diagnostics_and_export(tmp_path):
    scene=Scene(*create_pair(tmp_path/'pair',permuted=True))
    try:
        before=scene.diagnostics([5,6]);raw=scene.layers(Recipe())
        for quantity in ('signed_q','polarized'):
            for branch in (0,):
                maps=map_layers(scene.harp,quantity,branch,batch_rows=4,extended=False)
                for r,c in ((0,0),(5,6),(10,8)):
                    expected=scene.diagnostics([r,c])['liquid_index']['branches'][branch]['series'][quantity]
                    for method,array in maps.items():
                        value=expected[method]['value']
                        if value is None:assert np.isnan(array[r,c])
                        else:assert array[r,c]==pytest.approx(value)
        # Operational map is a reported, registered field, independent of own CLI.
        operational=np.full(scene.shape,.73);operational[5,6]=np.nan
        scene.cloudbow=SimpleNamespace(data=xr.Dataset({'cloud_liquid_index':((ROW,COL),operational)}),
            provenance={'gpc':{'product_name':'SYNTHETIC_GPC'}},close=lambda:None,
            diagnostics=lambda r,c:{'status':'available','fields':{}},solution=lambda r,c:{'status':'missing'},lower=134,upper=166,rft_lower=134,rft_upper=166)
        scene.gpc=scene.cloudbow  # Registered scalar adapter is now independent of the phase library.
        recipe=Recipe(selected=[5,6],left_mode='liquid_index')
        layers=scene.layers(recipe)
        np.testing.assert_array_equal(layers[0],operational)
        np.testing.assert_array_equal(layers[1],raw[1]);np.testing.assert_array_equal(layers[2],raw[2])
        _,ids=preview(scene,recipe,160,120)
        for mode in ('liquid_index_discrete','liquid_index_trapezoidal'):
            recipe.left_mode=mode;data,hit=preview(scene,recipe,160,120)
            np.testing.assert_array_equal(hit,ids)
            assert data['provenance']['liquid_index_map']['scope'].startswith('original TOA')
        assert scene.diagnostics([5,6])['harp2']==before['harp2']
        assert 'trapezoidal' in scene._liquid_maps[('signed_q','1')]
        assert set(scene._liquid_maps[('signed_q','1')])=={'discrete','trapezoidal'}
        client=TestClient(create_app(scene));assert client.get('/api/scene').json()['liquid_index_available']
        api=client.get('/api/bin/5/6').json()
        paths=export(scene,recipe,tmp_path/'li',width_mm=250,height_mm=260,dpi=80)
        saved=json.loads(paths[2].read_text());assert saved['liquid_index']==api['liquid_index']
        recipe.liquid_index_trapezoidal=True
        paths=export(scene,recipe,tmp_path/'trap',width_mm=250,height_mm=260,dpi=80)
        assert json.loads(paths[2].read_text())['recipe']['liquid_index_trapezoidal']
        recipe.liquid_plot_dolp=True
        paths=export(scene,recipe,tmp_path/'dolp',width_mm=250,height_mm=260,dpi=80)
        assert json.loads(paths[2].read_text())['recipe']['liquid_plot_dolp']
        assert scene.diagnostics([5,6])['liquid_index']==api['liquid_index']
        rgba=colors(np.array([[np.nan,-1.,0.,4.,8.]]),'liquid_index',recipe)
        assert rgba[0,0,3]==0 and np.all(rgba[0,1:,3]==1)
        np.testing.assert_array_equal(rgba[0,3],rgba[0,4]) # display clips; source values retained
        white=colors(np.array([[-2.,.3,8.]]),'liquid_index',recipe)
        np.testing.assert_allclose(white[0,1,:3],[1,1,1])
        assert white[0,0,2]>white[0,0,0] and white[0,2,0]>white[0,2,2]
        assert display_scale(np.array([[np.nan]]))['center']==.3
        assert Recipe.from_dict({}).liquid_index_trapezoidal is False
        recipe.liquid_index_quantity='dolp'
        assert client.post('/api/render',json={'recipe':asdict(recipe)}).status_code==422
    finally:scene.close()


def test_wide_window_fixed_denominator_independent_hand_calculation():
    # Flat baseline; irregular samples and nonzero shoulders. Inclusive boundary
    # samples constrain the unchanged baseline and integration, but have no excess.
    x=np.array([120,125,130,132,135,140,145,148,150,155,160.])
    excess=np.array([0,0,0,.01,.02,.04,.02,.01,0,0,0.])
    r=calculate(x,.02+excess,wide=True)
    assert r['window_degrees']==[130,150]
    assert r['reference_angle']==135
    assert r['normalization_baseline']==pytest.approx(.02)
    assert r['discrete']['value']==pytest.approx(2*excess[2:9].mean()/.02)
    # Independently sum piecewise-linear areas, including both shoulders.
    area=.01+ .045+ .15+ .15+ .045+ .01
    assert r['trapezoidal']['integral_reflectance_degrees']==pytest.approx(area)
    assert r['trapezoidal']['value']==pytest.approx(area/(10*.02))
    assert calculate(x,np.full_like(x,.02),wide=True)['discrete']['value']==pytest.approx(0,abs=1e-12)
    assert r['trapezoidal']['theta'][0]==130 and r['trapezoidal']['theta'][-1]==150
    assert Recipe.from_dict({'middle_mode':'liquid_index_wide_discrete'}).left_mode=='oci_total'
    with pytest.raises(ValueError):Recipe(left_mode='liquid_index_wide_trapezoidal').validate((2,2))


def test_adaptive_interpolated_crossings_and_signed_sloping_baseline_area():
    # Baseline is y=.02+.001*(theta-135). Reference is horizontal y=.02.
    # The main peak is bracketed by crossings at 132 and 147 degrees.
    x=np.array([120,125,130,134,140,146,148,150,155,160.])
    y=.02+.001*(x-135)
    y[3:7]=[.025,.04,.025,.015]
    c=calculate(x,y)
    r=adaptive_window(c)
    assert r['window_degrees']==pytest.approx([132,147])
    assert r['normalization_baseline']==pytest.approx(.02)
    assert r['crossings'][0]['bracket_source_views']==[2,3]
    t=r['trapezoidal']
    assert t['theta']==pytest.approx([132,134,140,146,147])
    # Horizontal-reference area .1575 minus integrated sloping background .0675.
    assert t['integral_reflectance_degrees']==pytest.approx(.09)
    assert t['value']==pytest.approx(.45)
    assert t['observed'][0]==pytest.approx(.02)
    assert t['observed'][-1]==pytest.approx(.02)
    assert t['excess'][-1]<0  # no clipping, despite horizontal boundary
    assert r['discrete']['value'] is None
    # Absolute radiometric scaling and input ordering cannot move crossings/LI.
    scaled=adaptive_window(calculate(x[::-1],(y*8)[::-1]))
    assert scaled['window_degrees']==pytest.approx([132,147])
    assert scaled['trapezoidal']['value']==pytest.approx(.45)


def test_adaptive_nearest_crossings_missing_support_and_exact_hits():
    x=np.array([120,125,130,134,140,146,150,155,160.])
    y=np.full(len(x),.02);y[3:6]=[.03,.04,.03]
    r=adaptive_window(calculate(x,y))
    assert r['window_degrees']==pytest.approx([130,150]) # exact hits
    assert r['trapezoidal']['value']==pytest.approx(1.1)
    # Separate positive lobe after an intervening zero must not be appended.
    x2=np.insert(x,7,[152,154]);y2=np.insert(y,7,[.05,.02])
    r2=adaptive_window(calculate(x2,y2))
    assert r2['window_degrees'][1]<152
    flat=adaptive_window(calculate(x,np.full(len(x),.02)))
    assert flat['status']=='available' and flat['window_degrees']==[130,150]
    assert flat['trapezoidal']['value']==pytest.approx(0,abs=1e-12)
    assert 'No main-bow peak' in flat['fallback_reason']
    assert adaptive_window(calculate(x,np.zeros(len(x))))['trapezoidal']['value'] is None
    assert adaptive_window(calculate(np.r_[x,140],np.r_[y,.04]))['status']=='missing'
    # An upward-sloping background may never cross the horizontal line again.
    rising=.02+.001*(x-135);rising[(x>=134)&(x<=146)]+=.02
    capped=adaptive_window(calculate(x,rising))
    assert capped['status']=='available' and capped['window_degrees'][1]==150
    assert capped['boundaries'][1]['kind']=='window_edge'
    json.dumps(capped,allow_nan=False)


def test_adaptive_native_map_known_finite_integral():
    x=np.array([120,125,130,134,140,146,150,155,160,179,160,150,140.])
    y=np.full(len(x),.02);y[3:6]=[.03,.04,.03]
    class Product:
        shape=(1,1);distance=1.
        channels=[dict(view=i,wavelength=664.6,angle=60-i*4) for i in range(len(x))]
        def read(self,name,row=None):
            if name=='polarization_f0':return np.full(len(x),1000.)
            a={'q':-y*1000/np.pi,'u':np.zeros_like(x),'number_of_observations':np.ones_like(x),
               'scattering_angle':x,'solar_zenith_angle':np.zeros_like(x),'rotation_angle':np.zeros_like(x)}[name]
            return np.broadcast_to(a,(1,1,len(x)))[row]
    maps=map_layers(Product(),batch_rows=1)
    assert maps['adaptive_trapezoidal'][0,0]==pytest.approx(1.1)
    assert 'wide_discrete' not in maps


def test_adaptive_caps_both_bounds_and_requires_observed_support():
    x=np.array([120,125,130,134,140,146,150,155,160.])
    y=np.array([.01,.01,.025,.03,.05,.03,.025,.01,.01])
    r=adaptive_window(calculate(x,y))
    # Both shoulders stay above fitted reference: stop at user window edges.
    assert r['window_degrees']==[130,150]
    assert [b['kind'] for b in r['boundaries']]==['window_edge','window_edge']
    assert r['crossings']==[]
    assert r['trapezoidal']['value']==pytest.approx(calculate(x,y,wide=True)['trapezoidal']['value'])
    # Even a reference curve with a valid fit cannot extrapolate missing edges.
    c=calculate(x,y);keep=np.array(c['theta'])>=134
    for key in ['theta','observed','source_views','baseline','baseline_mask','peak_mask']:
        c[key]=np.array(c[key])[keep].tolist()
    r=adaptive_window(c)
    assert r['status']=='missing' and 'no extrapolation' in r['reason']


def test_adaptive_no_peak_retains_signed_wide_fallback():
    x=np.array([120,125,130,134,140,146,150,155,160.])
    y=np.full(len(x),.02);y[3:6]=[.015,.01,.015]
    r=adaptive_window(calculate(x,y))
    wide=calculate(x,y,wide=True)
    assert r['window_degrees']==[130,150]
    assert r['trapezoidal']['value']==pytest.approx(wide['trapezoidal']['value'])
    assert r['trapezoidal']['value']<0
    assert r['fallback_reason']
    assert all(b['kind']=='window_edge' for b in r['boundaries'])


def test_baseline_raw_angle_independent_of_peak_and_reference_height():
    x=np.array([120,125,150,155.])
    y=.02+.001*(x-135)
    c=calculate(x,y)
    assert c['status']=='missing' # no measured bow points
    angle=c['baseline_angle']
    assert angle['status']=='available'
    assert angle['value']==pytest.approx(.0572957604145)
    assert angle['slope_reflectance_per_degree']==pytest.approx(.001)
    # Moving the horizontal reference up does not change angle; reflectance
    # scaling does change this user-selected raw numeric angle.
    assert calculate(x,y+2)['baseline_angle']['value']==pytest.approx(angle['value'])
    assert calculate(x,y*2)['baseline_angle']['value']==pytest.approx(np.rad2deg(np.arctan(.002)))
    assert calculate(x,-y)['baseline_angle']['value']==pytest.approx(-angle['value'])
    assert calculate(x,np.zeros_like(x))['baseline_angle']['value']==0
    assert calculate(x[:2],y[:2])['baseline_angle']['value'] is None
    scale=baseline_angle_scale(np.array([[-.02,.01,np.nan]]),'full')
    assert (scale['minimum'],scale['center'],scale['maximum'])==pytest.approx((-.02,-.005,.01))
    rgba=colors(np.array([[-.02,0.,.02,np.nan]]),'baseline_angle',Recipe())
    assert rgba[0,0,2]>rgba[0,0,0] and rgba[0,2,0]>rgba[0,2,2]
    assert rgba[0,1,1]>.8  # Turbo midpoint is green, not a white classification threshold
    assert rgba[0,3,3]==0


def test_baseline_only_native_map_without_any_bow_samples():
    x=np.array([120,125,150,155,179,155,140.]);y=.02+.001*(x-135)
    class Product:
        shape=(1,1);distance=1.
        channels=[dict(view=i,wavelength=664.6,angle=60-i*4) for i in range(len(x))]
        def read(self,name,row=None):
            if name=='polarization_f0':return np.full(len(x),1000.)
            a={'q':-y*1000/np.pi,'u':np.zeros_like(x),'number_of_observations':np.ones_like(x),
               'scattering_angle':x,'solar_zenith_angle':np.zeros_like(x),'rotation_angle':np.zeros_like(x)}[name]
            return np.broadcast_to(a,(1,1,len(x)))[row]
    only=map_layers(Product(),baseline_only=True)
    assert set(only)=={'baseline_angle'}
    assert only['baseline_angle'][0,0]==pytest.approx(.0572957604145)
    full=map_layers(Product())
    np.testing.assert_array_equal(only['baseline_angle'],full['baseline_angle'])


def test_baseline_turbo_percentiles_only_affect_display_and_recipe():
    field=np.arange(101,dtype=float).reshape(1,-1);before=field.copy()
    scale=baseline_angle_scale(field)
    assert (scale['minimum'],scale['maximum'])==(1,99)
    assert scale['clipped_below']==scale['clipped_above']==1
    assert scale['colormap']=='turbo' and scale['valid_bins']==101
    full=baseline_angle_scale(field,'full');assert (full['minimum'],full['maximum'])==(0,100)
    np.testing.assert_array_equal(field,before)
    assert Recipe.from_dict({'middle_mode':'liquid_index_baseline_angle','baseline_angle_range':'full'}).left_mode=='oci_total'


def test_quicklook_narrow_path_skips_retired_calculations(tmp_path,monkeypatch):
    import pace_l1c.liquid_index as li
    def retired(*args,**kwargs):
        raise AssertionError('Quicklook must not evaluate adaptive LI')
    monkeypatch.setattr(li,'adaptive_window',retired)
    scene=Scene(*create_pair(tmp_path/'pair'))
    try:
        diagnostics=scene.diagnostics([5,6])['liquid_index']
        for curve in diagnostics['branches'][0]['series'].values():
            assert not {'wide','adaptive','baseline_angle'} & curve.keys()
        for mode in ('liquid_index_discrete','liquid_index_trapezoidal'):
            recipe=Recipe(left_mode=mode,liquid_plot_dolp=True)
            layers=scene.layers(recipe)
            raw=scene.layers(Recipe())
            np.testing.assert_array_equal(layers[1],raw[1])
            np.testing.assert_array_equal(layers[2],raw[2])
        assert set(scene._liquid_maps[('signed_q','1')])=={'discrete','trapezoidal'}
    finally:scene.close()


def test_legacy_map_recipes_migrate_to_left_and_retired_modes_reset():
    assert Recipe.from_dict({'middle_mode':'harp_total'}).left_mode=='oci_total'
    assert Recipe.from_dict({'middle_mode':'oci_phase'}).left_mode=='oci_phase'
    assert Recipe.from_dict({'middle_mode':'liquid_index_discrete'}).left_mode=='liquid_index_discrete'
    for mode in ('liquid_index_wide_discrete','liquid_index_wide_trapezoidal','liquid_index_adaptive_trapezoidal','liquid_index_baseline_angle'):
        recipe=Recipe.from_dict({'middle_mode':mode,'liquid_index_wide':True,'liquid_index_adaptive':True,'baseline_angle_range':'full'})
        assert recipe.left_mode=='oci_total'
        recipe.validate((2,2))
