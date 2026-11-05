"""Static packaging preserves original selected science and rejects private overlays."""
import json
from pathlib import Path
import pytest
from pace_l1c.fixtures import create_pair
from pace_l1c.scene import Scene
from pace_l1c.showcase import build_showcase


def test_finite_original_bin_export(tmp_path):
    frontend=tmp_path/'web';frontend.mkdir();(frontend/'showcase.html').write_text('<html></html>')
    for name in ('assets','branding'):(frontend/name).mkdir()
    scene=Scene(*create_pair(tmp_path/'inputs',permuted=True))
    try:
        expected=scene.diagnostics([5,6])
        out=tmp_path/'site'
        result=build_showcase(scene,out,points=[(5,6),(8,12)],anchors=[scene.anchors()[0]],frontend=frontend)
        assert result['examples']==2 and result['scenarios']==1
        manifest=json.loads((out/'data/manifest.json').read_text())
        assert manifest['examples'][0]['id']=='5-6'
        d=json.loads((out/'data/bin-5-6.json').read_text())
        assert d['oci']==expected['oci'] and d['harp2']==expected['harp2']
        assert d['liquid_index']==expected['liquid_index']
        assert not {'rft','cloudbow','residuals'}&d.keys()
        assert manifest['scenarios'][0]['recipe']['rayleigh_land'] is True
        assert all(Path(name['name']).suffix not in ('.nc','.h5') for name in json.loads((out/'data/assets.json').read_text()))
        with pytest.raises(ValueError,match='existing artifacts'):build_showcase(scene,out,frontend=frontend)
        scene.cloudbow=object()
        with pytest.raises(ValueError,match='private Mie'):build_showcase(scene,tmp_path/'blocked',frontend=frontend)
        scene.cloudbow=None
    finally:scene.close()
