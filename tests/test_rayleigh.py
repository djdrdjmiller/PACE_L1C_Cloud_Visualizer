import numpy as np
import pytest
from scipy.integrate import quad
from pace_l1c.rayleigh import optical_depth,path_reflectance,subtract,king_factor,depolarization_ratio,phase_elements,scattering_cross_section,MODEL
from pace_l1c.science import rotate
from pace_l1c.scene import Scene,Recipe
from pace_l1c.fixtures import create_pair
from pace_l1c.atmosphere import Atmosphere
from test_atmosphere import lut,write_cache


def test_rayleigh_against_independent_depth_integral_and_known_tau():
    # Independent published cross-section fit: Bodhaine eq. 29, 360 ppm CO2.
    # Our fixed 300 ppm differs slightly; tolerance also covers the fit's 0.01%.
    for wave in (350,440,550,664.564,850):
        lam=wave/1000
        published=1e-32*(1.0455996-341.29061/lam**2-.90230850*lam**2)/(1+.0027059889/lam**2-85.968563*lam**2)
        assert scattering_cross_section(wave)==pytest.approx(published,rel=3e-4)
    # Standard-g column ~2.148e29 molecules/m², sigma(550) ~4.510e-31 m².
    assert optical_depth(550,1013.25)==pytest.approx(.09689,rel=1e-4)
    tau=optical_depth(440,700)
    mu0,mu=.6,.8;angle=90
    integral=quad(lambda depth:np.exp(-depth*(1/mu0+1/mu))/(4*mu0*mu),0,tau)[0]
    rho=depolarization_ratio(440)
    # At 90 degrees, the depolarization ratio independently fixes I/Q.
    expected_i=integral*3*(1+rho)/(2*(2+rho))
    expected_q=-expected_i*(1-rho)/(1+rho)
    i,q,u=path_reflectance(440,700,np.rad2deg(np.arccos(mu0)),np.rad2deg(np.arccos(mu)),angle)
    assert i==pytest.approx(expected_i) and q==pytest.approx(expected_q) and u==0
    assert optical_depth(550,500)==pytest.approx(optical_depth(550,1000)/2)
    assert path_reflectance(550,800,20,30,180)[1]==pytest.approx(0,abs=1e-15)
    assert np.isnan(path_reflectance(550,800,90,0,90)[0])


def test_molecular_phase_normalization_polarization_and_king_consistency():
    # Independent dry-air value in Trees et al. 2026, section 4.1 / Fig. 11.
    assert depolarization_ratio(550)==pytest.approx(.0283,abs=5e-5)
    assert depolarization_ratio(350)>depolarization_ratio(550)>depolarization_ratio(865)
    for wave in (350,440,550,664.564,865,1690,2260,2500):
        rho=depolarization_ratio(wave)
        assert king_factor(wave)==pytest.approx((6+3*rho)/(6-7*rho))
        assert quad(lambda mu:phase_elements(wave,np.rad2deg(np.arccos(mu)))[0]/2,-1,1)[0]==pytest.approx(1)
        p11,p21=phase_elements(wave,np.linspace(0,180,181))
        assert np.all(p11>0) and np.all(np.abs(p21)<=p11)
        assert -p21[90]/p11[90]==pytest.approx((1-rho)/(1+rho))
        assert np.isfinite(optical_depth(wave,1050))
    assert 'extrapolated' in MODEL['spectral_support']
    assert 'multiple scattering neglected' in MODEL['assumptions']


def test_rayleigh_domains_broadcasting_and_pressure_limits():
    for wave in (349,2501,np.nan):
        with pytest.raises(ValueError,match='350–2500'):optical_depth(wave,800)
    pressure=np.array([0.,-1.,np.nan,1050.,1050.1])
    assert np.array_equal(np.isfinite(optical_depth(550,pressure)),[False,False,False,True,False])
    i,q,u=path_reflectance(np.array([440,550,665])[:,None],800,30,20,np.array([90,140])[None,:])
    assert i.shape==q.shape==u.shape==(3,2)
    assert np.all(i>0) and np.all(q<0) and np.all(u==0)


def test_stokes_frame_f0_and_component_subtraction():
    # Different irradiances expose a normalization error that an equal-F0 test misses.
    ir,qr,ur=path_reflectance(550,800,30,20,100)
    ratio=2.;rotation=37.
    signal_q,signal_u=rotate(.04,.03,-rotation)
    molecular_q,molecular_u=rotate(qr*ratio,ur*ratio,-rotation)
    class Product:
        instrument='HARP2'
        def values(self,*args):return {'total':.5+ir,'q':signal_q+molecular_q,'u':signal_u+molecular_u}
        def read(self,name,*args):return {'solar_zenith_angle':30,'sensor_zenith_angle':20,'scattering_angle':100,'rotation_angle':rotation,'intensity_f0':2000.,'polarization_f0':1000.}[name]
    corrected=subtract(Product(),{'wavelength':550},800)
    assert corrected['total']==pytest.approx(.5)
    assert corrected['q_scattering']==pytest.approx(.04)
    assert corrected['u_scattering']==pytest.approx(.03)
    assert corrected['signed_q']==pytest.approx(-.04)
    assert corrected['polarized']==pytest.approx(.05)
    assert corrected['dolp']==pytest.approx(.05/ratio/.5)


def test_surface_log_transmission_extrapolation_bounds_and_unsupported_corners():
    t=lut()
    # Optical depth rises linearly with pressure, giving an independent extrapolation target.
    for j,p in enumerate(t.p):t.d['Transmittance'][:,:,:,j]=np.exp(-p*.0002)
    values=t.evaluate(0,0,np.array([999.,1000.,1025.,1050.,1051.]),.1,extend_surface=np.ones(5,bool))
    assert values[2]==pytest.approx(np.exp(-1025*.0002))
    assert values[3]==pytest.approx(np.exp(-1050*.0002))
    assert np.isnan(values[4])
    assert np.isnan(t.evaluate(0,0,1025,.1,extend_surface=False))
    t.d['counts'][:,:,:,8]=0
    assert np.isnan(t.evaluate(0,0,1025,.1,extend_surface=True))
    t=lut();t.d['Transmittance'][:,:,:,9]=.9  # attenuation decreases with pressure: reject extension
    assert np.isnan(t.evaluate(0,0,1025,.1,extend_surface=True))


@pytest.mark.parametrize('quantity',['polarized','signed_q','signed_u','dolp'])
def test_legacy_land_bypass_and_unclassified_bins_remain_toa_in_all_modes(tmp_path,quantity):
    s=Scene(*create_pair(tmp_path/'pair',permuted=True))
    try:
        cache=tmp_path/'cache.nc';write_cache(s,cache);s.atmosphere=Atmosphere(cache,s)
        s.atmosphere.surface_class[:,2:5]=1;s.atmosphere.surface_class[:,5]=-1
        # Land preservation must not depend on availability of atmospheric inputs.
        s.atmosphere.p[:,2:6]=np.nan;s.atmosphere.w[:,2:6]=np.nan
        r=Recipe(selected=[5,6],third_quantity=quantity,rayleigh_land=False)
        raw=s.layers(r);diag=s.diagnostics(r.selected)
        r.correction='rayleigh_transmission';r.polar_rayleigh=True
        corrected=s.layers(r)
        for a,b in zip(raw,corrected):np.testing.assert_array_equal(a[:,2:6],b[:,2:6])
        assert not np.allclose(raw[0][:,6:],corrected[0][:,6:],equal_nan=True)
        assert not np.allclose(raw[2][:,6:],corrected[2][:,6:],equal_nan=True) or quantity=='signed_u'
        assert diag==s.diagnostics(r.selected)  # diagnostics/fits remain source TOA
        assert r.selected==[5,6]
    finally:s.close()


def test_phase_map_colors_source_identity_and_linked_bin(tmp_path):
    from pace_l1c.render import preview,colors,export
    import json
    s=Scene(*create_pair(tmp_path/'pair',permuted=True))
    try:
        cache=tmp_path/'cache.nc';write_cache(s,cache);s.atmosphere=Atmosphere(cache,s)
        phase=np.tile(np.arange(s.shape[1])%5,(s.shape[0],1)).astype(float);phase[5,6]=np.nan
        s.atmosphere.phase=phase;s.atmosphere.provenance['phase_policy']='explicitly synthetic OCI phase'
        r=Recipe(selected=[5,6],scattering_contours=True)
        old,ids=preview(s,r,240,180);raw=s.layers(r);diag=s.diagnostics(r.selected)
        r.left_mode='oci_phase'
        new,ids2=preview(s,r,240,180);layers=s.layers(r)
        np.testing.assert_array_equal(ids,ids2)
        np.testing.assert_array_equal(layers[1],raw[1]);np.testing.assert_array_equal(layers[2],raw[2])
        np.testing.assert_array_equal(layers[0],phase)
        assert new['marker']==old['marker'] and diag==s.diagnostics(r.selected)
        rgba=colors(np.array([[0.,1.,2.,3.,4.,np.nan,9.]]),'phase',r)
        assert len(np.unique(rgba[0,:5,:3],axis=0))==5
        assert (rgba[0,5:,3]==0).all()
        assert new['provenance']['phase_source']=='explicitly synthetic OCI phase'
        paths=export(s,r,tmp_path/'phase',layout='maps',dpi=100)
        saved=json.loads(paths[2].read_text());assert saved['recipe']['left_mode']=='oci_phase' and saved['atmosphere']
        r.left_mode='oci_total';again,_=preview(s,r,240,180)
        assert again['layers']==old['layers']
    finally:s.close()


def test_boundary_only_cache_has_no_lut_and_matches_legacy_stokes_maps_and_export(tmp_path,monkeypatch):
    import json
    import xarray as xr
    import pace_l1c.atmosphere as atmosphere
    from pace_l1c.atmosphere import extract_rayleigh,TRANSMISSION_VARIABLES
    from pace_l1c.render import export,preview
    from pace_l1c.service import create_app
    from fastapi.testclient import TestClient
    from dataclasses import asdict
    s=Scene(*create_pair(tmp_path/'pair',permuted=True))
    try:
        legacy=tmp_path/'legacy.nc';write_cache(s,legacy)
        # Include water, land, unknown and missing water pressure in the preserved fields.
        with xr.open_dataset(legacy,engine='h5netcdf') as source:ds=source.load()
        ds.surface_class.values[:,2:4]=1;ds.surface_class.values[:,4]=-1
        ds.boundary_pressure.values[5,7]=np.nan
        ds['oci_phase']=(ds.boundary_pressure.dims,np.full(s.shape,2.))
        ds.to_netcdf(legacy,engine='h5netcdf');original=Atmosphere(legacy,s)
        target=tmp_path/'rayleigh.nc';extract_rayleigh(legacy,target)
        with xr.open_dataset(target,engine='h5netcdf') as ds:
            assert not any(n in ds for n in TRANSMISSION_VARIABLES)
            assert 'water_column' not in ds
            assert set(ds.dims)=={'bins_along_track','bins_across_track'}
        with pytest.raises(ValueError,match='preserved'):extract_rayleigh(legacy,legacy)
        with pytest.raises(ValueError,match='preserved'):extract_rayleigh(legacy,target)
        def no_lut(*args):raise AssertionError('Boundary-only loading must not touch TransmissionLUT')
        monkeypatch.setattr(atmosphere.TransmissionLUT,'validate',no_lut)
        boundary=Atmosphere(target,s);s.atmosphere=boundary
        assert boundary.w is None and boundary.lut is None
        assert boundary.capabilities=={'rayleigh':True,'transmission':False}
        r=Recipe(selected=[5,6],correction='rayleigh',polar_rayleigh=True)
        for product in (s.oci,s.harp):
            for channel in s.channels(r)[0 if product.instrument=='OCI' else 1]:
                before=original.corrected_values(product,channel,r)
                after=boundary.corrected_values(product,channel,r)
                for field in before:np.testing.assert_array_equal(before[field],after[field])
        assert s.diagnostics([5,6])['atmosphere']['water_g_cm2'] is None
        client=TestClient(create_app(s,tmp_path/'artifacts'))
        assert client.get('/api/scene').json()['correction_capabilities']==boundary.capabilities
        bad=asdict(r);bad['correction']='transmission'
        response=client.post('/api/render',json={'recipe':bad,'width':240,'height':180})
        assert response.status_code==422 and 'Rayleigh only' in response.json()['detail']
        shown,ids=preview(s,r,240,180)
        assert shown['provenance']['transmission_mapping'] is None
        paths=export(s,r,tmp_path/'rayleigh-figure',dpi=80)
        saved=json.loads(paths[2].read_text())
        assert saved['atmosphere']['cache_kind']=='rayleigh_boundary'
        assert saved['recipe']['polar_rayleigh'] is True
        replay,_=preview(s,Recipe.from_dict(saved['recipe']),240,180)
        assert replay['layers']==shown['layers']
    finally:s.close()


@pytest.mark.parametrize('broken',['schema','units','surface','table','shape'])
def test_rayleigh_cache_rejects_malformed_fields(tmp_path,broken):
    import json
    import xarray as xr
    from pace_l1c.atmosphere import extract_rayleigh
    s=Scene(*create_pair(tmp_path/'pair'))
    try:
        legacy=tmp_path/'legacy.nc';write_cache(s,legacy)
        target=tmp_path/'rayleigh.nc';extract_rayleigh(legacy,target)
        with xr.open_dataset(target,engine='h5netcdf') as source:ds=source.load()
        if broken=='schema':
            metadata=json.loads(ds.attrs['provenance']);metadata['cache_schema_version']=999;ds.attrs['provenance']=json.dumps(metadata)
        elif broken=='units':ds.boundary_pressure.attrs['units']='Pa'
        elif broken=='surface':ds.surface_class.values[0,0]=2
        elif broken=='table':ds['water_column']=(ds.boundary_pressure.dims,np.zeros(s.shape))
        else:ds=ds.isel(bins_along_track=slice(0,2))
        ds.to_netcdf(target,engine='h5netcdf')
        with pytest.raises(ValueError):Atmosphere(target,s)
    finally:s.close()


@pytest.mark.parametrize('mode',['rayleigh','rayleigh_transmission'])
def test_land_enabled_production_matches_trial_and_keeps_unknown_diagnostics_and_policy(tmp_path,mode):
    import json
    from dataclasses import replace
    from pace_l1c.land_trial import apply_land_trial
    from pace_l1c.render import export
    s=Scene(*create_pair(tmp_path/'pair',permuted=True))
    try:
        cache=tmp_path/'cache.nc';write_cache(s,cache);s.atmosphere=Atmosphere(cache,s)
        atm=s.atmosphere;atm.surface_class[:,2:5]=1;atm.surface_class[:,5]=-1
        atm.p[5,3]=np.nan
        r=Recipe(selected=[5,6],correction=mode,polar_rayleigh=True)
        legacy=replace(r,rayleigh_land=False)
        before=s.diagnostics(r.selected)
        for channel in s.channels(r)[1]:
            raw=s.harp.values(channel)
            old=atm.corrected_values(s.harp,channel,legacy)
            expected=apply_land_trial(old,subtract(s.harp,channel,atm.p,raw=raw),atm.surface_class)
            actual=atm.corrected_values(s.harp,channel,r)
            for field in actual:np.testing.assert_array_equal(actual[field],expected[field])
            assert np.isnan(actual['total'][5,3]) and np.isnan(actual['polarized'][5,3])
            np.testing.assert_array_equal(actual['total'][:,5],raw['total'][:,5])
        # A per-recipe policy change must not reuse a cached water-only layer.
        old_layers=s.layers(legacy);land_layers=s.layers(r)
        assert not np.allclose(old_layers[0][:,2:5],land_layers[0][:,2:5],equal_nan=True)
        assert s.diagnostics(r.selected)==before
        provenance=s.provenance(r)
        assert provenance['rayleigh_land_policy']['total']=='Rayleigh only'
        assert provenance['correction_coverage']['oci']['land_corrected_bins']>0
        assert provenance['correction_coverage']['oci']['land_toa_bins']==0
        assert provenance['correction_coverage']['oci']['unknown_toa_bins']>0
        saved=json.loads(export(s,r,tmp_path/'land-corrected',layout='maps',dpi=70)[2].read_text())
        assert saved['recipe']['rayleigh_land'] is True
        np.testing.assert_array_equal(s.layers(Recipe.from_dict(saved['recipe']))[0],land_layers[0])
    finally:s.close()


def test_old_rayleigh_recipes_keep_water_only_but_new_defaults_and_explicit_recipes_enable_land():
    assert Recipe().rayleigh_land is True
    assert Recipe.from_dict({'correction':'rayleigh','polar_rayleigh':True}).rayleigh_land is False
    assert Recipe.from_dict({'correction':'toa','polar_rayleigh':True}).rayleigh_land is False
    assert Recipe.from_dict({'correction':'rayleigh','rayleigh_land':True}).rayleigh_land is True
    assert Recipe.from_dict({'correction':'toa'}).rayleigh_land is True
    assert not Recipe(correction='transmission').corrects_land_total
    assert Recipe(correction='toa',polar_rayleigh=True).corrects_land_polarization
    with pytest.raises(ValueError):Recipe(rayleigh_land='yes').validate((2,2))
