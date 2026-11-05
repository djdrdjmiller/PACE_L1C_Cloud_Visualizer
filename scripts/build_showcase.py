"""Build the original-scene showcase offline; supplied reference scripts are never run."""
import argparse,json
from pathlib import Path
from pace_l1c.scene import Scene
from pace_l1c.showcase import build_showcase

p=argparse.ArgumentParser()
p.add_argument('--manifest',required=True);p.add_argument('--case',default='science_scene')
p.add_argument('--atmosphere');p.add_argument('--output',required=True)
p.add_argument('--mie',help='Authorized local library; requires --include-cloudbow-curves to publish finite derived curves')
p.add_argument('--include-cloudbow-curves',action='store_true');p.add_argument('--include-left-maps',action='store_true')
a=p.parse_args()
m=json.loads(Path(a.manifest).read_text());case=next(c for c in m['cases'] if c['id']==a.case)
pair=case['pairs'][0];paths={role:m['files'][pair[role]] for role in ('oci','harp2','gpc') if role in pair}
if any(f['status']!='complete' for f in paths.values()):raise ValueError('Complete verified source files required')
s=Scene(paths['oci']['path'],paths['harp2']['path'],paths.get('gpc',{}).get('path'),mie_path=a.mie,atmosphere_path=a.atmosphere)
try:
    if [s.oci.identity['sha256'],s.harp.identity['sha256']]!=[paths[k]['sha256'] for k in ('oci','harp2')]:raise ValueError('Manifest source hashes changed')
    print(json.dumps(build_showcase(s,a.output,include_cloudbow_curves=a.include_cloudbow_curves,include_left_maps=a.include_left_maps)),flush=True)
finally:s.close()
