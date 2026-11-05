import json
from dataclasses import asdict
import numpy as np
import pytest
import xarray as xr
from pace_l1c.atmosphere import TransmissionLUT,water_column,pressure_grid,cloud_fallback,sample,sample_times,Atmosphere
from pace_l1c.scene import Scene,Recipe
from pace_l1c.fixtures import create_pair
from pace_l1c.render import export,preview
from pace_l1c.reader import ROW,COL


def lut():
    t=TransmissionLUT.__new__(TransmissionLUT)
    t.d={'Cloud_Top_Pressure':np.arange(100,1001,100.),'View_Angle_Cosine':np.array([.05,.5,1.]),'Precipitable_Water':np.array([0.,.2,2.]),'Wavelengths':np.array([.64,.86,.94,1.2,1.38,1.6,2.1,2.23])}
    for key,value in [('Transmittance',.8),('counts',10),('Standard_Deviation',.02)]:
        t.d[key]=np.full((8,3,3,10),value)
    t.validate();return t


def test_effective_path_pressure_ties_and_invalid_corners():
    t=lut()
    # At nadir effective cosine is .5. Different pressure slices identify tie-up.
    t.d['Transmittance'][0,:,:,1]=.7
    assert t.evaluate(0,0,150,.1)==pytest.approx(.7)
    assert .4/t.evaluate(0,0,100,.1)==pytest.approx(.5)
    t.d['Transmittance'][0,0,0,0]=-1  # positive counts cannot rescue negative T
    assert np.isnan(t.evaluate(30,40,100,.1))
    assert np.isfinite(t.evaluate(0,0,100,.1))  # unused zero-weight corner irrelevant
    for p in [99,1001,np.nan]:assert np.isnan(t.evaluate(0,0,p,.1))
    assert np.isnan(t.evaluate(90,0,100,.1))
    assert np.isnan(t.evaluate(0,0,100,2.1))


def test_nonuniform_water_interpolation():
    t=lut();t.d['Transmittance'][:]=1-np.array([0,.2,2])[None,None,:,None]*.1
    assert t.evaluate(0,0,700,1.1)==pytest.approx(.89)


def test_cloud_and_surface_integration_and_missing_profile():
    p=np.array([.1,1,10,100,500,700,800,900,1000.])
    q=np.full((3,len(p)),.01)
    values=water_column(p,q,[700,950,990],[1010,950,995],[.01,.01,.01],[False,True,False])
    assert values[0]==pytest.approx(1000*.01/.99*(700-.1)/980.616,rel=2e-4)
    assert values[1]==pytest.approx(1000*.01/.99*(950-.1)/980.616,rel=2e-4)
    assert np.isnan(values[2])  # cloud rule requiring surface-level repair
    q[0,4]=np.nan
    assert np.isnan(water_column(p,q,[700,950,990],[1010,950,995],[.01,.01,.01],[False,True,False])[0])
    assert pressure_grid()[0]==pytest.approx(.005,rel=.03)


def test_bounded_cloud_vote_never_propagates_and_keeps_unknown():
    phase=np.full((13,13),2.);ctp=np.full((13,13),700.);ps=np.full((13,13),950.)
    ctp[6,6]=np.nan
    p,state=cloud_fallback(phase,ctp,ps,radius=1)
    assert p[6,6]==700 and state[6,6]==3
    phase[:]=np.nan;ctp[:]=np.nan
    phase[0,:]=1
    p,state=cloud_fallback(phase,ctp,ps,radius=1)
    assert state[1,6]==4 and p[1,6]==950
    assert state[2,6]==0 and np.isnan(p[2,6])  # no iterative fill
    phase[:]=1;phase[6,6]=2
    p,state=cloud_fallback(phase,ctp,ps,radius=1)
    assert state[6,6]==0  # known cloud cannot be made clear by clear neighbors


def test_periodic_sampling_and_time_brackets(tmp_path):
    paths=[]
    for hour in [0,1]:
        ds=xr.Dataset({'PS':(('lat','lon'),np.array([[100,200,300,400],[200,300,400,500]])+hour*100,{'units':'Pa'})},coords={'lat':[-1,1],'lon':[-180,-90,0,90]},attrs={'time_coverage_start':f'2025-10-02T0{hour}:00:00Z'})
        path=tmp_path/f'{hour}.nc';ds.to_netcdf(path,engine='h5netcdf');paths.append(path)
    lat=np.array([0.,0]);lon=np.array([179.,-181.]);seconds=float(np.datetime64('2025-10-02T00:30:00','ns').astype('int64'))/1e9
    value,_=sample_times(paths,'PS',lat,lon,np.full(2,seconds))
    assert value[0]==pytest.approx(value[1])
    first,_,_=sample(paths[0],'PS',lat,lon)
    np.testing.assert_allclose(value,first+50)
    value,_=sample_times(paths,'PS',lat,lon,np.full(2,seconds+7200))
    assert np.isnan(value).all()


def write_cache(scene,path):
    t=lut();provenance={'inputs':[scene.oci.identity,scene.harp.identity],'state_codes':{'1':'cloud'}}
    ds=xr.Dataset({'boundary_pressure':((ROW,COL),np.full(scene.shape,700.)),'water_column':((ROW,COL),np.full(scene.shape,.1)),'surface_class':((ROW,COL),np.zeros(scene.shape,dtype=np.int8)),'boundary_state':((ROW,COL),np.ones(scene.shape,dtype=np.int8))},attrs={'provenance':json.dumps(provenance)})
    for name,a in t.d.items():
        dims={'Cloud_Top_Pressure':['pressure'],'View_Angle_Cosine':['cosine'],'Precipitable_Water':['water'],'Wavelengths':['band']}.get(name,['band','cosine','water','pressure'])
        ds[name]=(dims,a)
    ds.to_netcdf(path,engine='h5netcdf')


def test_map_correction_preserves_polarimetry_spectrum_and_replay(tmp_path):
    scene=Scene(*create_pair(tmp_path/'pair',permuted=True))
    try:
        cache=tmp_path/'atm.nc';write_cache(scene,cache)
        scene.atmosphere=Atmosphere(cache,scene)
        r=Recipe(selected=[5,6]);raw=scene.layers(r);diag=scene.diagnostics(r.selected)
        plain,ids=preview(scene,r,240,180)
        r.correction='transmission';corrected=scene.layers(r)
        np.testing.assert_allclose(corrected[0],raw[0]/.8,equal_nan=True)
        np.testing.assert_allclose(corrected[1],raw[1]/.8,equal_nan=True)
        np.testing.assert_array_equal(corrected[2],raw[2])
        assert diag==scene.diagnostics(r.selected)
        result,ids2=preview(scene,r,240,180);np.testing.assert_array_equal(ids,ids2)
        paths=export(scene,r,tmp_path/'corrected',dpi=100)
        saved=json.loads(paths[2].read_text());assert saved['atmosphere']['cache_sha256']==scene.atmosphere.provenance['cache_sha256']
        replay,_=preview(scene,Recipe(**saved['recipe']),240,180)
        assert replay['layers']==result['layers']
        scene.atmosphere.p[:]=1100;scene.atmosphere.cache.clear();scene._layers.clear()
        unavailable=scene.layers(r)
        assert np.isnan(unavailable[0]).all()  # never return zero for rejected correction
        np.testing.assert_array_equal(unavailable[2],raw[2])
    finally:scene.close()


@pytest.mark.parametrize('mode',['transmission','rayleigh'])
def test_prepare_collocates_adjacent_clouds_and_time_offsets(tmp_path,monkeypatch,mode):
    import pace_l1c.atmosphere as atmosphere
    from pace_l1c.atmosphere import prepare,observation_times
    from pace_l1c.reader import VIEW
    shape=(6,8);paths=create_pair(tmp_path/'pair',shape=shape)
    base=float(np.datetime64('2025-10-02T00:00:00','ns').astype('int64'))/1e9
    # Nadir minus offset: nadir 610, native observation 600. The wrong sign fails.
    xr.Dataset({'nadir_view_time':((ROW,),np.arange(6)*10+610,{'units':'seconds since 2025-10-02'}),
                'view_time_offsets':((ROW,COL,VIEW),np.full((*shape,2),10.),{'units':'seconds'})}).to_netcdf(paths[0],group='bin_attributes',mode='a',engine='h5netcdf')
    scene=Scene(*paths)
    ancillary=tmp_path/'anc';ancillary.mkdir()
    p=np.array([.1,1,10,100,500,700,800,900,1000.]);pars={}
    for hour in [0,1]:
        tm=f'2025-10-02T0{hour}:00:00Z'
        profile=f'GMAO_MERRA2.20251002T0{hour}0000.PROFILE.nc';met=f'GMAO_MERRA2.20251002T0{hour}0000.MET.nc'
        pars[f'anc_profile{hour+1}']=profile;pars[f'met{hour+1}']=met
        coords={'lat':[-30,-20],'lon':[-80,-70]}
        xr.Dataset({'QV':(('lev','lat','lon'),np.full((len(p),2,2),.01),{'units':'kg kg-1'})},coords={**coords,'lev':('lev',p,{'units':'hPa'})},attrs={'time_coverage_start':tm}).to_netcdf(ancillary/profile,engine='h5netcdf')
        xr.Dataset({'PS':(('lat','lon'),np.full((2,2),95000.),{'units':'Pa'}),'QV10M':(('lat','lon'),np.full((2,2),.01),{'units':'kg kg-1'})},coords=coords,attrs={'time_coverage_start':tm}).to_netcdf(ancillary/met,engine='h5netcdf')
    clouds=[]
    for index in [0,1]:
        cloud=tmp_path/f'cloud{index}.nc';clouds.append(cloud)
        xr.Dataset().to_netcdf(cloud,engine='h5netcdf')
        xr.Dataset(attrs=pars).to_netcdf(cloud,group='processing_control/input_parameters',mode='a',engine='h5netcdf')
        lat=scene.oci.lat.copy();lon=scene.oci.lon.copy()
        lat[(slice(3,None) if index==0 else slice(None,3)),:]=np.nan
        xr.Dataset({'latitude':(('scan','pixel'),lat),'longitude':(('scan','pixel'),lon)}).to_netcdf(cloud,group='navigation_data',mode='a',engine='h5netcdf')
        xr.Dataset({'ctp':(('scan','pixel'),np.full(shape,700.),{'units':'mbar'}),
            'l2_flags':(('scan','pixel'),np.zeros(shape,dtype=np.uint32),{'flag_meanings':'LAND','flag_masks':np.array([2],dtype=np.uint32)}),'cld_phase_21':(('scan','pixel'),np.full(shape,2),{'long_name':'1 - clear, 2 - water cloud, 3 - ice cloud'})}).to_netcdf(cloud,group='geophysical_data',mode='a',engine='h5netcdf')
        xr.Dataset({'time':(('scan',),base+np.arange(6)*10+600,{'units':'seconds since 1970-1-1'})}).to_netcdf(cloud,group='scan_line_attributes',mode='a',engine='h5netcdf')
    class SyntheticLUT(TransmissionLUT):
        def __init__(self,path):self.d=lut().d;self.validate()
    if mode=='rayleigh':
        for path in ancillary.glob('*.PROFILE.nc'):path.unlink()
        for path in ancillary.glob('*.MET.nc'):
            with xr.open_dataset(path,engine='h5netcdf') as source:met_only=source.drop_vars('QV10M').load()
            met_only.to_netcdf(path,engine='h5netcdf')
        def no_table(*args):raise AssertionError('Rayleigh preparation must not open a transmission table')
        monkeypatch.setattr(atmosphere,'TransmissionLUT',no_table)
    else:monkeypatch.setattr(atmosphere,'TransmissionLUT',SyntheticLUT)
    table=tmp_path/'synthetic-lut';table.write_bytes(b'explicitly synthetic')
    try:
        result=prepare(scene,clouds,ancillary,table if mode=='transmission' else None,tmp_path/'prepared.nc',max_time_s=1,mode=mode)
        assert result['counts']['matched']==np.prod(shape)
        assert result['counts']['state_1']==np.prod(shape)
        with xr.open_dataset(tmp_path/'prepared.nc',engine='h5netcdf') as d:
            assert (d.cloud_source_product.values[:3]==0).all()
            assert (d.cloud_source_product.values[3:]==1).all()
            assert np.max(abs(d.match_time_s.values))<1e-5
            if mode=='transmission':assert np.isfinite(d.water_column.values).all()
            else:
                assert 'water_column' not in d and 'Transmittance' not in d
                assert 'lut' not in result and 'humidity' not in result
                assert all('.MET.' in a['name'] for a in result['ancillary'])
                assert np.all(d.boundary_pressure.values==700.)
                assert np.all(d.surface_class.values==0)
        loaded=Atmosphere(tmp_path/'prepared.nc',scene)
        assert loaded.capabilities=={'rayleigh':True,'transmission':mode=='transmission'}
    finally:scene.close()


def test_ancillary_budget_records_failed_bytes_without_login_or_partial_cache(tmp_path):
    from pace_l1c.ancillary import acquire
    cloud=tmp_path/'cloud.nc';xr.Dataset().to_netcdf(cloud,engine='h5netcdf')
    xr.Dataset(attrs={'met1':'GMAO_MERRA2.20251002T000000.MET.nc','anc_profile1':'GMAO_MERRA2.20251002T000000.PROFILE.nc'}).to_netcdf(cloud,group='processing_control/input_parameters',mode='a',engine='h5netcdf')
    class Response:
        headers={}
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def raise_for_status(self):pass
        def iter_content(self,*args):yield b'x'*200
    class Session:
        def get(self,*args,**kwargs):return Response()
    cache=tmp_path/'cache'
    with pytest.raises(ValueError,match='budget exceeded'):
        acquire(cloud,cache,budget_mib=.0001,session=Session())
    record=json.loads((cache/'acquisition.json').read_text())
    assert record['attempted_bytes']==200
    assert next(iter(record['files'].values()))['status']=='failed'
    assert not list(cache.glob('*.part')) and not list(cache.glob('*.nc'))


def test_met_only_acquisition_reuses_cache_without_profile_or_login(tmp_path):
    from pace_l1c.ancillary import acquire
    from pace_l1c.reader import sha256
    cloud=tmp_path/'cloud.nc';xr.Dataset().to_netcdf(cloud,engine='h5netcdf')
    met='GMAO_MERRA2.20251002T000000.MET.nc'
    xr.Dataset(attrs={'met1':met,'anc_profile1':'GMAO_MERRA2.20251002T000000.PROFILE.nc'}).to_netcdf(cloud,group='processing_control/input_parameters',mode='a',engine='h5netcdf')
    cache=tmp_path/'ancillary';cache.mkdir();(cache/met).write_bytes(b'verified synthetic cache')
    (cache/'acquisition.json').write_text(json.dumps({'attempted_bytes':10,'files':{met:{'status':'complete','sha256':sha256(cache/met)}}}))
    record=acquire(cloud,cache,kind='met')
    saved=json.loads(record.read_text())
    assert list(saved['files'])==[met] and saved['attempted_bytes']==10
