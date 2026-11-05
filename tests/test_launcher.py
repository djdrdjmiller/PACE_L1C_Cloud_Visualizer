"""Local setup/auth/isolation tests with independent synthetic products."""
import json
import os
from pathlib import Path
import time
from types import SimpleNamespace
from fastapi.testclient import TestClient
import pytest
from pace_l1c.fixtures import create_pair
from pace_l1c.service import create_app


def finish(client):
    until=time.monotonic()+15
    while time.monotonic()<until:
        result=client.get('/api/setup/job').json()
        if result['status']!='running':return result
        time.sleep(.01)
    pytest.fail('Setup worker did not finish')


@pytest.fixture
def client(tmp_path):
    app=create_app(cache=tmp_path/'cache',output=tmp_path/'exports')
    with TestClient(app) as client:
        yield client
    app.state.launcher_executor.shutdown(wait=True)
    if app.state.scene:app.state.scene.close()


def test_empty_launch_demo_open_hash_checks_render_and_exports(client,tmp_path):
    assert not client.get('/api/setup').json()['scene_loaded']
    assert client.get('/api/scene').status_code==409
    assert client.post('/api/setup/demo',json={}).status_code==200
    job=finish(client);assert job['status']=='complete',job
    record=job['result']['scene'];assert record['synthetic']
    assert client.get('/api/setup/saved').json()[0]['available']
    assert client.post('/api/setup/open',json={'scene_id':record['id']}).status_code==200
    assert finish(client)['status']=='complete'
    info=client.get('/api/scene').json()
    assert info['model_capabilities']=={'cloudbow':False,'rft':False}
    recipe=info['default_recipe'];response=client.post('/api/render',json={'recipe':recipe,'width':160,'height':120})
    assert response.status_code==200,response.text
    result=client.post('/api/export',json={'recipe':recipe,'width_mm':90,'height_mm':90,'dpi':60,'layout':'maps'})
    assert result.status_code==200
    for url in result.json()['artifacts']:assert client.get(url).status_code==200
    # A changed cached source cannot silently reopen under the saved identity.
    with Path(record['paths']['oci']).open('ab') as f:f.write(b'changed')
    client.post('/api/setup/open',json={'scene_id':record['id']})
    assert finish(client)['status']=='failed'


def test_local_file_import_stays_local_and_rejects_path_traversal(client,tmp_path):
    pair=create_pair(tmp_path/'fixture')
    paths={}
    for role,p in zip(('oci','harp2'),pair):
        response=client.post('/api/setup/import',params={'name':role+'.nc'},content=Path(p).read_bytes(),headers={'Content-Type':'application/octet-stream'})
        assert response.status_code==200
        paths[role]=response.json()['path']
    assert client.post('/api/setup/local',json=paths).status_code==200
    assert finish(client)['status']=='complete'
    assert client.post('/api/setup/import',params={'name':'../outside.nc'},content=b'x').status_code==422
    assert client.post('/api/setup/open',json={'scene_id':'../../secret'}).status_code==422
    assert client.post('/api/setup/import',params={'name':'empty.nc'},content=b'').status_code==422


def test_same_origin_json_and_host_restrictions(client):
    assert client.get('/api/setup',headers={'Host':'evil.example'}).status_code==403
    assert client.post('/api/setup/demo',json={},headers={'Origin':'https://evil.example'}).status_code==403
    assert client.post('/api/setup/demo',json={},headers={'Sec-Fetch-Site':'cross-site'}).status_code==403
    assert client.post('/api/setup/demo',data={'anything':'x'}).status_code==415


def test_auth_secrets_are_not_persisted_or_echoed_and_environment_is_restored(client,monkeypatch):
    import earthaccess
    seen=[]
    monkeypatch.setenv('EARTHDATA_USERNAME','prior')
    monkeypatch.setenv('EARTHDATA_TOKEN','prior-token')
    def login(**kwargs):
        seen.append((kwargs,os.environ.get('EARTHDATA_USERNAME'),os.environ.get('EARTHDATA_PASSWORD'),os.environ.get('EARTHDATA_TOKEN')))
        return SimpleNamespace(authenticated=True)
    monkeypatch.setattr(earthaccess,'login',login)
    monkeypatch.setattr(earthaccess,'get_requests_https_session',lambda:object())
    response=client.post('/api/setup/login',json={'username':'example-user','password':'example-secret','remember':False})
    assert response.status_code==200
    assert seen==[({'strategy':'environment','persist':False},'example-user','example-secret',None)]
    assert os.environ['EARTHDATA_USERNAME']=='prior' and os.environ['EARTHDATA_TOKEN']=='prior-token'
    assert os.environ.get('EARTHDATA_PASSWORD')!='example-secret'
    assert 'example-secret' not in client.get('/api/setup/job').text
    response=client.post('/api/setup/login',json={'username':{},'password':'example-secret'})
    assert response.status_code==400 and 'example-secret' not in response.text


def test_rejected_login_is_generic(client,monkeypatch):
    import earthaccess
    def failure(**kwargs):raise RuntimeError('credential and remote response must never be returned')
    monkeypatch.setattr(earthaccess,'login',failure)
    response=client.post('/api/setup/login',json={'username':'x','password':'secret'})
    assert response.status_code==401
    assert 'credential and remote response' not in response.text


def test_incomplete_download_is_visible_and_complete_staging_revalidates_without_network(client,tmp_path,monkeypatch):
    import hashlib,shutil
    import xarray as xr
    from pace_l1c.reader import sha256
    import earthaccess
    monkeypatch.setattr(earthaccess,'login',lambda **kw:pytest.fail('Complete staging recovery needs no login'))
    pair=create_pair(tmp_path/'row-tilt',oci_row_tilt=True)
    cache=tmp_path/'cache';raw=cache/'raw';records={};pair_ids={}
    stamp='20251002T182635'
    for n,(role,p) in enumerate(zip(('oci','harp2'),pair),1):
        name=f'PACE_{role.upper()}.{stamp}.L1C.V{3 if role=="oci" else 4}.5km.nc'
        xr.Dataset(attrs={'product_name':name}).to_netcdf(p,mode='a',engine='h5netcdf')
        id_=f'G{n}-TEST';directory=raw/hashlib.sha256((id_+':1').encode()).hexdigest()[:24]
        directory.mkdir(parents=True)
        if role=='oci':directory=directory/(id_+'.partial');directory.mkdir()
        target=directory/name;shutil.copyfile(p,target)
        size=target.stat().st_size
        records[id_]={'id':id_,'name':name,'role':role+'_l1c','revision_id':1,'size_bytes':size,'status':'validation_failed' if role=='oci' else 'complete',
                      'catalog':{'umm':{'DataGranule':{'ArchiveAndDistributionInformation':[{'Name':name,'SizeInBytes':size}]}}}}
        if role=='harp2':records[id_].update(path=str(target),sha256=sha256(target))
        else:records[id_]['reason']='Older reader could not interpret along-track tilt'
        pair_ids[role]=id_
    spent=sum(r['size_bytes'] for r in records.values());identifier='a'*20
    manifest={'schema_version':1,'attempted_bytes':spent,'files':records,'cases':[{'id':'selected_scene','status':'candidate','pairs':[pair_ids]}],
              'config':{'paths':{'raw':str(raw)},'limits':{'total_download_budget_gib':4,'max_candidate_pairs_to_download_per_case':1}}}
    path=cache/'acquisitions'/(identifier+'.json');path.parent.mkdir(parents=True);path.write_text(json.dumps(manifest))
    incomplete=client.get('/api/setup/acquisitions').json()
    assert len(incomplete)==1 and incomplete[0]['files'][0]['status']=='validation_failed'
    assert client.get('/api/setup/saved').json()==[]
    response=client.post('/api/setup/retry',json={'acquisition_id':identifier,'budget_gib':4})
    assert response.status_code==200,response.text
    job=finish(client);assert job['status']=='complete',job
    assert client.get('/api/setup/acquisitions').json()==[]
    assert len(client.get('/api/setup/saved').json())==1
    after=json.loads(path.read_text())
    assert after['attempted_bytes']==spent
    assert after['files']['G1-TEST']['recovered_staged']
