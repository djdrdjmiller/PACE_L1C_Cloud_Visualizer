from dataclasses import asdict
import json
import numpy as np
import pytest
import h5py
from PIL import Image
from fastapi.testclient import TestClient
from pace_l1c.fixtures import create_pair
from pace_l1c.reader import Product
from pace_l1c.scene import Scene,Recipe
from pace_l1c.render import preview,export
from pace_l1c.service import create_app


@pytest.fixture
def scene(tmp_path):
    s=Scene(*create_pair(tmp_path/'inputs',permuted=True))
    yield s
    s.close()


def test_shuffled_metadata_fill_scale_and_dimension_permutation(scene):
    r=Recipe(selected=[5,6])
    oc,h=scene.channels(r)
    assert [c['wavelength'] for c in h]==[670,550,440]
    d=scene.diagnostics(r.selected)
    assert d['oci']['valid_source_views']==[0]
    assert scene.diagnostics([12,6])['oci']['valid_source_views']==[1]
    assert len(d['harp2']['samples'])==20
    assert all(s['dolp']==pytest.approx(.05,abs=.00001) for s in d['harp2']['samples'])
    assert all(s['total'] is None for s in scene.diagnostics([5,0])['harp2']['samples'])
    np.testing.assert_allclose(scene.harp.read('i',h[0])[5,6],126.5)


def test_strict_pair_rejection_and_one_absent_grid_attribute(tmp_path):
    paths=create_pair(tmp_path/'a')
    with h5py.File(paths[0],'a') as f:
        del f.attrs['l1cgrid_source']
    s=Scene(*paths); assert s.evidence['max_geolocation_error_m']==0; s.close()
    with h5py.File(paths[1],'a') as f:
        f['geolocation_data/latitude'][4,5]+=1
    with pytest.raises(ValueError,match='Geolocation mismatch'):
        Scene(*paths)


@pytest.mark.parametrize('projection',['plate_carree','laea','native'])
def test_cell_hits_survive_crop_downsampling_missing_and_mode(scene,projection):
    r=Recipe(projection=projection,selected=[5,6],crop=[2,16,2,22])
    p,ids=preview(scene,r,240,180)
    x,y=np.rint(p['marker']).astype(int)
    assert ids[y,x]==5*scene.shape[1]+6
    r.third_quantity='signed_q'
    q,ids2=preview(scene,r,240,180)
    np.testing.assert_array_equal(ids,ids2)
    assert q['marker']==p['marker']
    assert r.selected==[5,6]


@pytest.mark.parametrize('special',['dateline','high_latitude'])
def test_special_geography(tmp_path,special):
    s=Scene(*create_pair(tmp_path,**{special:True}))
    try:
        p,ids=preview(s,Recipe(selected=[8,12]),240,180)
        assert p['bounds'][1]-p['bounds'][0]<5
        x,y=np.rint(p['marker']).astype(int)
        assert ids[y,x]==8*24+12
    finally: s.close()


def test_singleton_spatial_preserved(tmp_path):
    paths=create_pair(tmp_path,shape=(1,5))
    p=Product(paths[1])
    try:
        assert p.values(p.channels[0])['total'].shape==(1,5)
    finally: p.close()


def test_exports_recipe_pixels_pages_and_scientific_values(scene,tmp_path):
    from pypdf import PdfReader
    r=Recipe(selected=[5,6],third_quantity='signed_q',projection='laea',crop=[2,16,2,22])
    paths=export(scene,r,tmp_path/'figure',width_mm=180,height_mm=150,dpi=100)
    with Image.open(paths[0]) as image:
        assert image.size==(int(180/25.4*100),int(150/25.4*100))
    pdf=PdfReader(paths[1]);page=pdf.pages[0]
    assert float(page.mediabox.width)==pytest.approx(180/25.4*72,abs=.001)
    saved=json.loads(paths[2].read_text());restored=Recipe(**saved['recipe'])
    assert asdict(restored)==asdict(r)
    assert saved['inputs'][0]['sha256']==scene.oci.identity['sha256']
    np.testing.assert_array_equal(scene.layers(r)[2],scene.layers(restored)[2])


def test_api_shared_selection_and_invalid_inputs(scene,tmp_path):
    client=TestClient(create_app(scene,tmp_path))
    recipe=asdict(Recipe(selected=[5,6]))
    rendered=client.post('/api/render',json={'recipe':recipe,'width':240,'height':180}).json()
    x,y=np.rint(rendered['marker']).astype(int)
    for panel in range(3):
        hit=client.post('/api/hit',json={'render_id':rendered['render_id'],'x':int(x),'y':int(y)})
        assert hit.json()['selected']==[5,6]
    assert client.get('/api/bin/5/6').json()['selected']==[5,6]
    assert client.get('/api/bin/-1/6').status_code==422
    recipe['crop']=[-1,3,0,3]
    assert client.post('/api/render',json={'recipe':recipe}).status_code==422
    assert client.post('/api/hit',json={'render_id':'stale','x':1,'y':1}).status_code==409
    assert client.get('/api/scene',headers={'Origin':'https://evil.example'}).status_code==403


def test_default_harp_crop_and_single_band_preserve_bin(scene):
    recipe=scene.default_recipe()
    assert recipe.crop==[0,18,1,24]
    selected=recipe.selected.copy()
    recipe.harp_mode='single'
    assert scene.layers(recipe)[1].ndim==2
    recipe.third_quantity='dolp'
    assert scene.layers(recipe)[2].ndim==3
    assert recipe.selected==selected


def test_unsupported_band_and_recipe_field(scene,tmp_path):
    client=TestClient(create_app(scene,tmp_path))
    recipe=asdict(Recipe())
    recipe['oci_targets']=[99999,555,443]
    assert client.post('/api/render',json={'recipe':recipe}).status_code==422
    recipe['unexpected']='bad'
    assert client.post('/api/render',json={'recipe':recipe}).status_code==422


@pytest.mark.parametrize('projection',['plate_carree','laea','native'])
def test_scattering_contours_preserve_geometry_and_record_source(tmp_path,projection):
    paths=create_pair(tmp_path/'contour-inputs',permuted=True)
    with h5py.File(paths[1],'a') as f:
        data=f['geolocation_data/scattering_angle']
        # Synthetic spatial gradient crosses several known 10-degree levels.
        values=data[:]
        values+=np.linspace(-20,20,18)[:,None,None]
        data[:]=values
    scene=Scene(*paths)
    r=Recipe(selected=[5,6],projection=projection,crop=[2,16,0,22])
    before=scene.diagnostics(r.selected)
    plain,ids=preview(scene,r,240,180)
    r.scattering_contours=True
    field,channel=scene.scattering_grid(r)
    assert channel['wavelength']==670
    np.testing.assert_array_equal(field[:,1:],scene.harp.read('scattering_angle',channel)[:,1:])
    assert np.isnan(field[:,0]).all()  # no geometry substitution through missing views
    overlaid,ids2=preview(scene,r,240,180)
    np.testing.assert_array_equal(ids,ids2)
    assert plain['marker']==overlaid['marker']
    assert plain['layers'][0]==overlaid['layers'][0]
    assert plain['layers'][1:]!=overlaid['layers'][1:]
    assert scene.diagnostics(r.selected)==before
    provenance=overlaid['provenance']['scattering_contours']
    assert provenance['interval_degrees']==10 and provenance['channel']==channel
    paths=export(scene,r,tmp_path/'contours',layout='maps',dpi=100)
    saved=json.loads(paths[2].read_text())
    restored=Recipe(**saved['recipe'])
    replay,_=preview(scene,restored,240,180)
    assert replay['layers']==overlaid['layers']
    scene.close()


def test_retired_surface_extension_defaults_off_and_rejects_old_enabled_recipe(scene,tmp_path):
    client=TestClient(create_app(scene,tmp_path))
    recipe=client.get('/api/scene').json()['default_recipe']
    assert recipe['extrapolate_surface'] is False
    recipe['extrapolate_surface']=True
    response=client.post('/api/render',json={'recipe':recipe,'width':240,'height':180})
    assert response.status_code==422
    assert 'extrapolation was retired' in response.json()['detail']
