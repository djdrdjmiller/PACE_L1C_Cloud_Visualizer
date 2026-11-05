"""Finite static showcase assets from verified original bins, without private LUTs.

This exports only pre-rendered maps and a declared set of TOA diagnostics. It is
not a substitute for the local arbitrary-bin scientific application.
"""
import base64
from dataclasses import asdict,replace
from hashlib import sha256
import json
import re
from pathlib import Path
import shutil
import numpy as np
from .reader import jsonable
from .render import preview
from .geometry import Grid
from . import __version__

DEFAULT_POINTS=[(60,300),(100,200),(120,380),(175,250),(190,370),(225,170),(254,261),(260,303),(280,385),(320,220),(335,340),(365,280)]


def _write_json(path,value):
    path.write_text(json.dumps(jsonable(value),allow_nan=False,separators=(',',':')),encoding='utf-8')


def build_showcase(scene,output,*,points=DEFAULT_POINTS,anchors=None,frontend='frontend/dist'):
    """All plotted science comes from the current shared library, not a new model."""
    output=Path(output)
    if output.exists():raise ValueError('Choose a new output directory; existing artifacts/data are never cleaned automatically')
    if not (Path(frontend)/'showcase.html').is_file():raise ValueError('Build the frontend/showcase entry first')
    if scene.cloudbow:raise ValueError('Static export must use the GPC-only scene, without a private Mie library')
    recipe=scene.default_recipe()
    recipe.projection='plate_carree';recipe.scattering_contours=True
    if anchors is None:
        anchors=list(dict.fromkeys(min(scene.anchors(),key=lambda a:abs(a-target)) for target in (-30,0,30)))
    if len(anchors)>5 or not anchors:raise ValueError('Choose one to five existing sparse-band anchors')
    if any(a not in scene.anchors() for a in anchors):raise ValueError('Showcase sectors must be actual metadata-derived anchors')
    if not 1<=len(points)<=20:raise ValueError('Choose one to twenty marked original bins')
    points=[tuple(map(int,p)) for p in points]
    if len(set(points))!=len(points):raise ValueError('Duplicate example bin')
    grid=Grid(scene.oci,recipe)
    width,height=720,560
    examples=[]
    for index,(r,c) in enumerate(points,1):
        if not(0<=r<scene.shape[0] and 0<=c<scene.shape[1]):raise ValueError('Example bin outside source')
        x,y=grid.screen(grid.centers[r,c],width,height)
        if not(np.isfinite([x,y]).all() and 12<x<width-12 and 12<y<height-12):raise ValueError('Example marker falls outside the retained map crop')
        examples.append({'id':f'{r}-{c}','number':index,'row':r,'col':c,'latitude':float(scene.oci.lat[r,c]),'longitude':float(scene.oci.lon[r,c]),
                         'position':[float(x/width),float(y/height)],'diagnostics':f'data/bin-{r}-{c}.json'})
    output.mkdir(parents=True);(output/'data').mkdir();(output/'maps').mkdir()
    shutil.copyfile(Path(frontend)/'showcase.html',output/'index.html')
    shutil.copytree(Path(frontend)/'assets',output/'assets')
    shutil.copytree(Path(frontend)/'branding',output/'branding')
    for item in examples:
        d=scene.diagnostics([item['row'],item['col']])
        public={key:d[key] for key in ('selected','latitude','longitude','oci','harp2','cloud','liquid_index','atmosphere')}
        _write_json(output/item['diagnostics'],public)
    scenarios=[]
    corrections=['toa','rayleigh'] if scene.atmosphere and scene.atmosphere.capabilities['rayleigh'] else ['toa']
    for n,angle in enumerate(anchors):
        for correction in corrections:
            choice=replace(recipe,anchor_angle=angle,correction=correction,polar_rayleigh=correction=='rayleigh',rayleigh_land=True)
            print(f'Preparing static maps: anchor {angle:.1f}, {correction}',flush=True)
            result,_=preview(scene,choice,width,height)
            paths=[]
            for layer,encoded in enumerate(result['layers']):
                path=f'maps/anchor-{n}-{correction}-{layer}.png'
                (output/path).write_bytes(base64.b64decode(encoded.split(',',1)[1]));paths.append(path)
            fields=scene.layers(choice)
            p=result['provenance']
            scenarios.append({'id':f'{n}-{correction}','anchor':angle,'correction':correction,'images':paths,
                              'channels':{'oci':p['oci_channels'],'harp2':p['harp_channels']},
                              'support':{e['id']:[bool(np.isfinite(a[e['row'],e['col']]).all()) for a in fields] for e in examples},
                              'recipe':asdict(choice),'coverage':p.get('correction_coverage'),'rayleigh_land_policy':p['rayleigh_land_policy']})
    default_anchor=min(anchors,key=abs)
    identities={'oci':scene.oci.identity,'harp2':scene.harp.identity,'gpc':scene.gpc.provenance['gpc'] if scene.gpc else None}
    manifest={'schema_version':1,'software_version':__version__,'scene_time':scene.oci.attrs['time_coverage_start'],
              'title':'Original PACE scene · 2 October 2025','shape':scene.shape,'alignment':scene.evidence,'inputs':identities,
              'aspect_ratio':result['aspect_ratio'],'image_size':[width,height],'crop':recipe.crop,'projection':recipe.projection,
              'examples':examples,'scenarios':scenarios,'anchors':anchors,'default_anchor':default_anchor,
              'default_correction':'rayleigh' if 'rayleigh' in corrections else 'toa','display_recipe':asdict(replace(recipe,anchor_angle=default_anchor,correction='rayleigh' if 'rayleigh' in corrections else 'toa',polar_rayleigh='rayleigh' in corrections)),
              'phase_library':'Not included; no Mie data or Mie-derived cloudbow/RFT curves are distributed',
              'scope':{'selection':'Only the declared marked original bins','diagnostics':'Original TOA samples; branch 1 LI',
                       'maps':'Pre-rendered original-bin OCI and shared-source HARP2 images; supported classified land+water Rayleigh, unclassified TOA, unsupported classified missing',
                       'not_included':['New scene discovery','Arbitrary-bin inspection','Unrestricted rendering/exports','Cloudbow/RFT model overlays']}}
    _write_json(output/'data/manifest.json',manifest)
    (output/'.nojekyll').write_text('')
    for name in ('LICENSE','NOTICE','THIRD_PARTY.md'):
        if Path(name).exists():shutil.copyfile(name,output/name)
    if Path('licenses').is_dir():shutil.copytree('licenses',output/'licenses')
    files=[]
    for path in output.rglob('*'):
        if path.is_file():
            assert path.suffix not in ('.nc','.nc4','.hdf','.h5','.ipynb')
            if path.suffix in ('.json','.html','.js','.css'):
                data=path.read_bytes()
                if re.search(rb'/'+b'Users/'+rb'[^/]+/',data):raise ValueError('Private author path in static asset')
            files.append({'name':path.relative_to(output).as_posix(),'bytes':path.stat().st_size,'sha256':sha256(path.read_bytes()).hexdigest()})
    _write_json(output/'data/assets.json',files)
    return {'directory':str(output),'examples':len(examples),'scenarios':len(scenarios),'bytes':sum(f['bytes'] for f in files)}
