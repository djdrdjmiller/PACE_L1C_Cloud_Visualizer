"""Audit a release wheel and exercise it outside the source checkout."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile
import venv
import zipfile


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('directory')
    parser.add_argument('--smoke',action='store_true')
    args=parser.parse_args()
    wheels=list(Path(args.directory).glob('*.whl'))
    if len(wheels)!=1:raise SystemExit('Expected exactly one wheel')
    wheel=wheels[0].resolve()
    with zipfile.ZipFile(wheel) as archive:
        names=archive.namelist()
        assert 'pace_l1c/web/index.html' in names
        assert any(n.startswith('pace_l1c/web/assets/setup-') and n.endswith('.js') for n in names)
        assert any(n.startswith('pace_l1c/web/assets/dashboard-') and n.endswith('.js') for n in names)
        assert any(n.endswith('LICENSE') for n in names)
        assert not any(n.endswith(('.nc','.hdf','.h5','.ipynb','.netrc')) or '/data/' in n or 'granule-statistics' in n for n in names)
        for name in names:
            if name.endswith(('.py','.js','.css','.html','.json')):
                contents=archive.read(name)
                assert not re.search(rb'/Users/[^/]+/',contents),name
    print(json.dumps({'wheel':wheel.name,'bytes':wheel.stat().st_size,'sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),'bundled_frontend':True}))
    if not args.smoke:return
    with tempfile.TemporaryDirectory(prefix='pace-wheel-') as temporary:
        base=Path(temporary);environment=base/'environment'
        # Dependencies come from the verified runtime; the project must come only
        # from the installed wheel, proven by __file__ below. CI tests dependencies
        # from the lock on each fresh hosted runner before reaching this stage.
        venv.EnvBuilder(with_pip=True,system_site_packages=True).create(environment)
        python=environment/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        subprocess.run([str(python),'-I','-m','pip','install','--no-deps',str(wheel)],check=True,cwd=base)
        code='''
import json,time,sys
from pathlib import Path
import pace_l1c
from fastapi.testclient import TestClient
from pace_l1c.service import create_app
module_path=Path(pace_l1c.__file__).resolve()
environment_path=Path(sys.prefix).resolve()
assert module_path.is_relative_to(environment_path),(str(module_path),str(environment_path))
app=create_app(cache=Path('cache'),output=Path('exports'))
with TestClient(app) as client:
    page=client.get('/')
    assert page.status_code==200 and 'src/main.ts' not in page.text
    assert not client.get('/api/setup').json()['scene_loaded']
    assert client.post('/api/setup/demo',json={}).status_code==200
    for attempt in range(1000):
        job=client.get('/api/setup/job').json()
        if job['status']!='running':break
        time.sleep(.01)
    assert job['status']=='complete',job
    scene=job['result']['scene']
    client.post('/api/setup/open',json={'scene_id':scene['id']})
    for attempt in range(1000):
        job=client.get('/api/setup/job').json()
        if job['status']!='running':break
        time.sleep(.01)
    assert job['status']=='complete',job
    recipe=client.get('/api/scene').json()['default_recipe']
    preview=client.post('/api/render',json={'recipe':recipe,'width':160,'height':120})
    assert preview.status_code==200,preview.text
    artifacts=client.post('/api/export',json={'recipe':recipe,'layout':'maps','dpi':60,'width_mm':90,'height_mm':90})
    assert artifacts.status_code==200,artifacts.text
    for url in artifacts.json()['artifacts']:assert client.get(url).status_code==200
app.state.launcher_executor.shutdown(wait=True)
app.state.scene.close()
print(json.dumps({'outside_checkout':True,'installed_wheel':str(pace_l1c.__file__),'setup_demo_open_render_export':'passed'}))
'''
        subprocess.run([str(python),'-I','-c',code],cwd=base,check=True)


if __name__=='__main__':main()
