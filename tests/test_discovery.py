"""Independent synthetic catalog/transfer cases; no NASA credentials or network."""
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
import xarray as xr
from pace_l1c.acquisition import DownloadCancelled, download
from pace_l1c.discovery import search, make_manifest, scene_record, saved_scenes, role_and_stamp, COLLECTIONS
from pace_l1c.fixtures import create_pair
from pace_l1c.scene import Scene, Recipe
from pace_l1c.reader import ROW, COL

STAMP='20251002T182635'
class Granule(dict):
    def data_links(self):
        return ['https://oceandata.sci.gsfc.nasa.gov/ob/getfile/'+self['umm']['GranuleUR']]


def granule(role, id_, version=None):
    name={'oci_l1c':f'PACE_OCI.{STAMP}.L1C.V{version or 3}.5km.nc','harp2_l1c':f'PACE_HARP2.{STAMP}.L1C.V4.5km.nc','harp2_gpc':f'PACE_HARP2.{STAMP}.L2.CLOUD_GPC.V4_0.nc'}[role]
    return Granule(meta={'concept-id':id_,'revision-id':1},umm={'GranuleUR':name,'CollectionReference':{'ShortName':COLLECTIONS[role]['short_name'],'Version':COLLECTIONS[role]['version']},'DataGranule':{'ProducerGranuleId':name,'ArchiveAndDistributionInformation':[{'Name':name,'SizeInBytes':100}]}})


def catalog(*,gpc=True,revisions=False):
    entries=[granule('oci_l1c','G1-TEST'),granule('harp2_l1c','G2-TEST')]
    if gpc:entries.append(granule('harp2_gpc','G3-TEST'))
    if revisions:
        other=granule('oci_l1c','G4-TEST');other['meta']['revision-id']=2;entries.append(other)
    calls=[]
    def query(**kwargs):
        calls.append(kwargs)
        if 'concept_id' in kwargs:return [g for g in entries if g['meta']['concept-id']==kwargs['concept_id']]
        return [g for g in entries if g['umm']['CollectionReference']['ShortName']==kwargs['short_name'] and ('granule_name' not in kwargs or kwargs['granule_name']==g['umm']['GranuleUR'])]
    return entries,calls,query


@pytest.mark.parametrize('identifier',['20251002T182635','https://example.com/a.nc','../OCI.nc','$(whoami)','PACE_OCI.*.nc','G1-../x'])
def test_identifiers_are_not_paths_urls_or_expressions(identifier):
    with pytest.raises(ValueError):search(identifier=identifier,query=lambda **kw:pytest.fail('No query for unsafe input'))


def test_exact_id_resolves_companions_and_preserves_metadata():
    entries,calls,query=catalog(revisions=True)
    result=search(identifier='G1-TEST',query=query)
    assert len(result['candidates'])==1
    assert result['candidates'][0]['oci']=='G1-TEST'
    assert result['files']['G1-TEST']['producer_id']==entries[0]['umm']['GranuleUR']
    assert result['files']['G1-TEST']['revision_id']==1
    assert all(c['count']==13 for c in calls)
    assert not any('login' in str(c) for c in calls)


def test_date_region_revisions_dateline_and_missing_optional():
    _,calls,query=catalog(gpc=False,revisions=True)
    result=search(start='2025-10-02',end='2025-10-03',bbox=[170,-25,-170,25],query=query)
    assert len(result['candidates'])==2
    assert all(not c['gpc_candidates'] for c in result['candidates'])
    assert len(calls)==6
    assert len(result['files'])==3  # dedup across antimeridian halves
    with pytest.raises(ValueError):search(start='2025-01-01',end='2025-02-01',bbox=[0,0,1,1],query=query)
    with pytest.raises(ValueError):search(start='2025-01-01',end='2025-01-02',bbox=[0,float('nan'),1,1],query=query)


def test_missing_companions_and_query_failure_are_explicit():
    _,_,query=catalog()
    def fail(**kw):
        if kw['short_name']==COLLECTIONS['harp2_l1c']['short_name']:raise OSError('network')
        return query(**kw)
    result=search(start='2025-10-02',end='2025-10-03',bbox=[-85,-35,-65,-20],query=fail)
    assert not result['candidates'] and result['failures'][0]['role']=='harp2_l1c'
    assert result['warnings']


def test_scalar_gpc_without_mie_supports_maps_diagnostics_and_registration(tmp_path):
    pair=create_pair(tmp_path/'pair');gpc=tmp_path/'gpc.nc'
    s=Scene(*pair)
    try:
        xr.Dataset(attrs=dict(s.harp.attrs,product_name='SYNTHETIC_GPC')).to_netcdf(gpc,engine='h5netcdf')
        xr.Dataset({'latitude':((ROW,COL),s.harp.lat),'longitude':((ROW,COL),s.harp.lon)}).to_netcdf(gpc,group='geolocation_data',mode='a',engine='h5netcdf')
        values=np.full(s.shape,.73);values[0,0]=np.nan
        xr.Dataset({'cloud_liquid_index':((ROW,COL),values,{'units':'1'})}).to_netcdf(gpc,group='geophysical_data',mode='a',engine='h5netcdf')
    finally:s.close()
    s=Scene(*pair,gpc_path=gpc)
    try:
        assert s.cloudbow is None
        np.testing.assert_allclose(s.layers(Recipe(left_mode='liquid_index'))[0],values,equal_nan=True)
        assert s.diagnostics([5,6])['cloud']['fields']['cloud_liquid_index']['value']==.73
        assert s.diagnostics([5,6],rft=True)['rft']['status']=='unavailable'
    finally:s.close()
    with xr.open_dataset(gpc,group='geolocation_data',engine='h5netcdf') as ds:bad=ds.load()
    bad['latitude']+=1
    bad.to_netcdf(gpc,group='geolocation_data',mode='a',engine='h5netcdf')
    with pytest.raises(ValueError,match='geolocation'):Scene(*pair,gpc_path=gpc)


def test_saved_scene_detects_missing_sources_and_keeps_hashes(tmp_path):
    pair=create_pair(tmp_path/'pair');directory=tmp_path/'cache'
    record=scene_record(directory,dict(oci=pair[0],harp2=pair[1]),synthetic=True)
    assert saved_scenes(directory)[0]['available']
    assert len(record['hashes']['oci'])==64
    Path(pair[1]).rename(tmp_path/'moved.nc')
    assert not saved_scenes(directory)[0]['available']


def test_stream_download_cancellation_budget_and_verified_offline_reuse(tmp_path):
    pair=create_pair(tmp_path/'fixture');_,_,query=catalog(gpc=False)
    result=search(identifier='G1-TEST',query=query)
    for i,role in enumerate(('oci_l1c','harp2_l1c')):
        xr.Dataset(attrs={'product_name':next(f['name'] for f in result['files'].values() if f['role']==role)}).to_netcdf(pair[i],mode='a',engine='h5netcdf')
    contents={role:Path(pair[i]).read_bytes() for i,role in enumerate(('oci_l1c','harp2_l1c'))}
    for f in result['files'].values():
        size=len(contents[f['role']]);f['size_bytes']=size
        f['catalog']['umm']['DataGranule']['ArchiveAndDistributionInformation'][0]['SizeInBytes']=size
    class Response:
        def __init__(self,data):self.data=data;self.headers={'Content-Length':str(len(data))}
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def raise_for_status(self):pass
        def iter_content(self,n):yield self.data
    calls=[]
    def get(url,**kwargs):
        calls.append(url);return Response(contents['oci_l1c' if 'PACE_OCI' in url else 'harp2_l1c'])
    path=make_manifest(result,result['candidates'][0]['id'],tmp_path/'cache',budget_gib=.1)
    session=SimpleNamespace(get=get)
    m=download(path,session=session)
    assert all(f['status']=='complete' for f in m['files'].values())
    count=len(calls);download(path,session=SimpleNamespace(get=lambda *a,**kw:pytest.fail('Cached files must not download')))
    assert len(calls)==count
    used=m['attempted_bytes'];path=make_manifest(result,result['candidates'][0]['id'],tmp_path/'cache',budget_gib=.1)
    assert json.loads(path.read_text())['attempted_bytes']==used
    with pytest.raises(DownloadCancelled):download(path,session=session,cancelled=lambda:True)


def test_processing_versions_are_explicit_not_silent_substitutions():
    with pytest.raises(ValueError,match='processing version'):
        role_and_stamp('PACE_OCI.20251002T182635.L1C.V9.5km.nc')


def test_failed_stream_attempts_keep_budget_and_cancellation_accounting(tmp_path):
    _,_,query=catalog(gpc=False)
    result=search(identifier='G1-TEST',query=query)
    path=make_manifest(result,result['candidates'][0]['id'],tmp_path/'cache',budget_gib=200/2**30)
    calls=[]
    class Response:
        headers={'Content-Length':'100'}
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def raise_for_status(self):pass
        def iter_content(self,n):
            yield b'incomplete'
            raise OSError('network interruption')
    session=SimpleNamespace(get=lambda *a,**kw:(calls.append(a),Response())[1])
    m=download(path,session=session)
    assert len(calls)==2 and m['attempted_bytes']==200
    assert all(f['status']=='failed' for f in m['files'].values())
    path=make_manifest(result,result['candidates'][0]['id'],tmp_path/'cache',budget_gib=200/2**30)
    download(path,session=session)
    assert len(calls)==2  # Retry cannot erase earlier failed bytes.
