"""Static packaging preserves original selected science and rejects private overlays."""
import json
from pathlib import Path
import pytest
from pace_l1c.fixtures import create_pair
from pace_l1c.scene import Scene
from pace_l1c.showcase import build_showcase


def test_finite_original_bin_export(tmp_path):
    frontend=tmp_path/'web';frontend.mkdir();(frontend/'showcase.html').write_text('<script type="module" src="./assets/showcase-test.js"></script>')
    for name in ('assets','branding'):(frontend/name).mkdir()
    (frontend/'assets/showcase-test.js').write_text('export {};')
    (frontend/'assets/dashboard-test.js').write_text('/* Installed app RFT controls must not enter the static demo */')
    scene=Scene(*create_pair(tmp_path/'inputs',permuted=True))
    try:
        expected=scene.diagnostics([5,6])
        out=tmp_path/'site'
        result=build_showcase(scene,out,points=[(5,6),(8,12)],anchors=[scene.anchors()[0]],frontend=frontend,include_left_maps=True)
        assert result['examples']==2 and result['scenarios']==1
        assert (out/'assets/showcase-test.js').is_file()
        assert not (out/'assets/dashboard-test.js').exists()
        manifest=json.loads((out/'data/manifest.json').read_text())
        assert manifest['examples'][0]['id']=='5-6'
        d=json.loads((out/'data/bin-5-6.json').read_text())
        assert d['oci']==expected['oci'] and d['harp2']==expected['harp2']
        assert d['liquid_index']==expected['liquid_index']
        assert not {'rft','cloudbow','residuals'}&d.keys()
        assert manifest['scenarios'][0]['recipe']['rayleigh_land'] is True
        assert {(m['mode'],m['quantity']) for m in manifest['left_maps']}=={(f'liquid_index_{method}',quantity) for method in ('discrete','trapezoidal') for quantity in ('signed_q','polarized')}
        for item in manifest['left_maps']:
            assert item['recipe']['liquid_index_branch']=='1'
            assert item['recipe']['correction']=='toa'
            assert (out/item['image']).is_file()
        assert all(Path(name['name']).suffix not in ('.nc','.h5') for name in json.loads((out/'data/assets.json').read_text()))
        with pytest.raises(ValueError,match='existing artifacts'):build_showcase(scene,out,frontend=frontend)
        scene.cloudbow=object()
        with pytest.raises(ValueError,match='private Mie'):build_showcase(scene,tmp_path/'blocked',frontend=frontend)
        scene.cloudbow=None
    finally:scene.close()


def test_cached_cloudbow_excludes_phase_arrays_optics_and_rft():
    from pace_l1c.showcase import cached_cloudbow
    diagnostic={'cloudbow':{'status':'experimental','theta':[135,140],'signed_q':[.1,.2],
                            'phase':['PRIVATE'],'canonical':['PRIVATE'],'coefficients_cba':['PRIVATE']},
                'rft':{'status':'experimental','modes':[{'lut_optics':'PRIVATE'}]},
                'residuals':{'branch':0,'sample_count':0,'theta':[],
                             'series':{'rft':{'status':'available','predicted_signed_q':['PRIVATE']},
                                       'cloudbow':{'status':'available','residual_signed_q':[.01,.02],'coefficients_cba':['PRIVATE']}}}}
    cached=cached_cloudbow(diagnostic)
    assert 'PRIVATE' not in json.dumps(cached)
    assert 'rft' not in json.dumps(cached).lower()
    assert cached['cloudbow']['signed_q']==[.1,.2]
    assert cached['residuals']['series']['cloudbow']['residual_signed_q']==[.01,.02]
