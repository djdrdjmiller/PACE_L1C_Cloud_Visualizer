import argparse
import json
from pathlib import Path
from .reader import Product
from .scene import Scene, Recipe
from .render import export


def main():
    parser=argparse.ArgumentParser(description="PACE L1C local analysis and bounded acquisition")
    sub=parser.add_subparsers(dest="command",required=True)
    for name in ("serve","export","validate","atmosphere-prepare","atmosphere-clouds"):
        p=sub.add_parser(name)
        p.add_argument("--oci"); p.add_argument("--harp2")
        p.add_argument("--manifest");p.add_argument("--case",default="science_scene");p.add_argument("--pair-index",type=int,default=0)
        p.add_argument("--gpc");p.add_argument("--mie");p.add_argument("--atmosphere")
        if name=='atmosphere-clouds':
            p.add_argument('--cache',default='data/atmosphere/cloud');p.add_argument('--budget-mib',type=int,default=256);p.add_argument('--max-granules',type=int,default=3);p.add_argument('--local-cloud',action='append',default=[])
        if name=='atmosphere-prepare':
            p.add_argument('--cloud',required=True,nargs='+');p.add_argument('--lut')
            p.add_argument('--mode',choices=['rayleigh','transmission'],help='Default: Rayleigh without --lut; legacy transmission with --lut')
            p.add_argument('--ancillary',default='data/atmosphere/ancillary');p.add_argument('--output',default='data/atmosphere/scene.nc')
        if name=="serve":
            p.add_argument("--port",type=int,default=8000)
            p.add_argument("--cache-dir")
            p.add_argument("--no-browser",action="store_true")
        if name=="export":
            p.add_argument("--recipe"); p.add_argument("--output",default="outputs/figure")
            p.add_argument("--layout",choices=["one","maps","diagnostics"])
            p.add_argument("--width-mm",type=float); p.add_argument("--height-mm",type=float)
            p.add_argument("--dpi",type=int)
    p=sub.add_parser('atmosphere-extract-rayleigh');p.add_argument('--atmosphere',required=True);p.add_argument('--output',required=True)
    p=sub.add_parser('atmosphere-landmask');p.add_argument('--atmosphere',required=True);p.add_argument('--cloud',nargs='+',required=True);p.add_argument('--output',required=True)
    p=sub.add_parser('atmosphere-acquire');p.add_argument('--cloud',required=True);p.add_argument('--cache',default='data/atmosphere/ancillary');p.add_argument('--budget-mib',type=int,default=512);p.add_argument('--kind',choices=['all','met'],default='all')
    p=sub.add_parser("inspect"); p.add_argument("file")
    p=sub.add_parser("demo"); p.add_argument("--output",default="data/demo")
    p=sub.add_parser("coastlines");p.add_argument("--output",default="data/coastlines.json")
    for name in ("discover","download","qualify","cache"):
        p=sub.add_parser(name)
        p.add_argument("--manifest",default="data/manifests/development.json")
        if name=="discover":
            p.add_argument("--config",default="config/development-scenes.yaml")
    p=sub.add_parser('login',help='Authenticate with NASA Earthdata Login')
    p.add_argument('--remember',action='store_true',help='Save credentials in an unencrypted local netrc file')
    p=sub.add_parser('search-scenes',help='Bounded catalog search without login')
    p.add_argument('--identifier',default='');p.add_argument('--start');p.add_argument('--end')
    p.add_argument('--bbox',type=float,nargs=4);p.add_argument('--limit',type=int,default=12)
    p.add_argument('--output',required=True,help='User-local search JSON; never commit catalog/cache manifests')
    p=sub.add_parser('acquire-scene',help='Acquire an explicitly selected search candidate')
    p.add_argument('--search',required=True);p.add_argument('--candidate',required=True);p.add_argument('--gpc-id')
    p.add_argument('--budget-gib',type=float,default=4);p.add_argument('--cache-dir')
    a=parser.parse_args()
    if a.command=='login':
        import earthaccess
        auth=earthaccess.login(strategy='interactive',persist=a.remember)
        if not auth.authenticated:parser.error('Earthdata authentication failed')
        print('Earthdata connected'+('; local credentials saved' if a.remember else ' for this process; use --remember for later CLI processes, or sign in in the launcher'))
        return
    if a.command=='search-scenes':
        from .discovery import search
        from .acquisition import save
        result=search(identifier=a.identifier,start=a.start,end=a.end,bbox=a.bbox,limit=a.limit)
        save(a.output,result)
        from .discovery import public_entry
        print(json.dumps({'candidates':result['candidates'],'files':{i:public_entry(f) for i,f in result['files'].items()},'warnings':result['warnings']},indent=2))
        return
    if a.command=='acquire-scene':
        import earthaccess
        from .discovery import make_manifest,cache_directory,scene_record
        from .acquisition import download
        directory=cache_directory(a.cache_dir)
        path=make_manifest(json.loads(Path(a.search).read_text()),a.candidate,directory,gpc_id=a.gpc_id,budget_gib=a.budget_gib)
        m=json.loads(path.read_text())
        from .reader import sha256
        needs_transfer=any(not f.get('path') or not Path(f['path']).is_file() or sha256(f['path'])!=f.get('sha256') for f in m['files'].values())
        if needs_transfer:
            auth=None
            for strategy in ('environment','netrc'):
                try:
                    auth=earthaccess.login(strategy=strategy,persist=False)
                    if auth.authenticated:break
                except Exception:continue
            if not auth or not auth.authenticated:parser.error('Connect Earthdata with pace-l1c login --remember, or use the launcher')
            m=download(path,session=earthaccess.get_requests_https_session())
        pair=m['cases'][0]['pairs'][0]
        paths={role:m['files'][key]['path'] for role,key in pair.items() if m['files'][key]['status']=='complete'}
        if not all(k in paths for k in ('oci','harp2')):parser.error('Required pair incomplete; inspect acquisition manifest and budget')
        warnings=[]
        try:record=scene_record(directory,paths)
        except ValueError:
            if 'gpc' not in paths:raise
            paths.pop('gpc');warnings.append('GPC failed registration; core pair remains available')
            record=scene_record(directory,paths,warnings=warnings)
        print(json.dumps({'scene':record,'manifest':str(path),'launch':['pace-l1c','serve','--manifest',str(path),'--case','selected_scene']},indent=2))
        return
    if a.command=='serve' and not any((a.oci,a.harp2,a.manifest)):
        if a.gpc or a.mie or a.atmosphere:parser.error('Optional files require a selected OCI/HARP2 pair')
        from .discovery import cache_directory
        directory=cache_directory(a.cache_dir)
        from .service import create_app
        _serve(create_app(output=directory/'exports',cache=directory),a.port,a.no_browser)
        return
    if a.command=='atmosphere-extract-rayleigh':
        from .atmosphere import extract_rayleigh
        print(json.dumps(extract_rayleigh(a.atmosphere,a.output),indent=2))
    elif a.command=='atmosphere-landmask':
        from .atmosphere import add_surface_class
        print(add_surface_class(a.atmosphere,a.cloud,a.output))
    elif a.command=='atmosphere-acquire':
        from .ancillary import acquire
        print(acquire(a.cloud,a.cache,a.budget_mib,kind=a.kind))
    elif a.command in ("discover","download","qualify","cache"):
        from .acquisition import discover,download,inspect_manifest
        if a.command=="discover":
            m=discover(a.config,a.manifest)
        elif a.command=="download":
            m=download(a.manifest)
        elif a.command=="qualify":
            m=inspect_manifest(a.manifest)
        else:
            m=json.loads(Path(a.manifest).read_text())
        print(json.dumps({"cases":[{"id":c["id"],"status":c["status"],"pairs":c["pairs"]} for c in m["cases"]],
                          "candidate_bytes":sum(f["size_bytes"] for f in m["files"].values()),
                          "files":[{k:v for k,v in f.items() if k in ("name","status","size_bytes","reason")} for f in m["files"].values()]},indent=2))
    elif a.command=="inspect":
        p=Product(a.file)
        try: print(json.dumps(p.inventory(),indent=2))
        finally: p.close()
    elif a.command=="demo":
        from .fixtures import create_pair
        print(create_pair(a.output))
    elif a.command=="coastlines":
        from .coastline import acquire
        print(acquire(a.output))
    else:
        expected=None
        if a.manifest:
            m=json.loads(Path(a.manifest).read_text())
            case=next((c for c in m['cases'] if c['id']==a.case),None)
            if case is None or not 0<=a.pair_index<len(case['pairs']):
                parser.error('Requested manifest case/pair unavailable')
            pair=case['pairs'][a.pair_index]
            records=[m['files'][pair[k]] for k in ('oci','harp2')]
            if any(f['status']!='complete' for f in records):
                parser.error('Selected manifest pair has incomplete transfers; inspect cache status')
            a.oci,a.harp2=[f['path'] for f in records]
            expected=[f['sha256'] for f in records]
            if not a.gpc and 'gpc' in pair and m['files'][pair['gpc']]['status']=='complete':
                a.gpc=m['files'][pair['gpc']]['path']
        if not a.oci or not a.harp2:
            parser.error('Supply --oci and --harp2, or --manifest with a cached case')
        scene=Scene(a.oci,a.harp2,a.gpc,a.mie,a.atmosphere)
        try:
            if expected and expected!=[scene.oci.identity['sha256'],scene.harp.identity['sha256']]:
                raise ValueError('Manifest input hashes differ from cached products')
            if a.command=='atmosphere-clouds':
                from .ancillary import acquire_clouds
                print([str(p) for p in acquire_clouds(scene.oci,a.cache,a.budget_mib,a.max_granules,a.local_cloud)])
            elif a.command=='atmosphere-prepare':
                from .atmosphere import prepare
                print(json.dumps(prepare(scene,a.cloud,a.ancillary,a.lut,a.output,mode=a.mode),indent=2))
            elif a.command=="validate":
                print(json.dumps(scene.evidence,indent=2))
            elif a.command=="export":
                saved=json.loads(Path(a.recipe).read_text()) if a.recipe else {}
                recipe=Recipe.from_dict(saved.get("recipe",saved))
                if "inputs" in saved and saved["inputs"] != [scene.oci.identity,scene.harp.identity]:
                    raise ValueError("Recipe input identities/hashes differ from supplied products")
                if saved.get('atmosphere') and (not scene.atmosphere or saved['atmosphere']!=scene.atmosphere.provenance):
                    raise ValueError('Atmospheric cache provenance differs from saved recipe')
                if saved.get('gpc') and (not scene.gpc or saved['gpc']!=scene.gpc.provenance['gpc']):
                    raise ValueError('GPC provenance differs from saved recipe')
                if saved.get('cloudbow') and (not scene.cloudbow or saved['cloudbow']!=scene.cloudbow.provenance):
                    raise ValueError('Cloudbow GPC/LUT provenance differs from saved recipe')
                current_coast={k:v for k,v in scene.coastline.items() if k!='lines'} if scene.coastline else None
                if 'coastline' in saved and saved['coastline']!=current_coast:
                    raise ValueError('Coastline annotation provenance differs from saved figure')
                settings=saved.get('export',{})
                print(export(scene,recipe,a.output,a.layout or settings.get('layout','diagnostics'),
                    a.width_mm or settings.get('width_mm',180),a.height_mm or settings.get('height_mm',150),a.dpi or settings.get('dpi',300)))
            else:
                import uvicorn
                from .service import create_app
                from .discovery import cache_directory
                directory=cache_directory(a.cache_dir)
                _serve(create_app(scene,output=directory/'exports',cache=directory),a.port,a.no_browser)
        finally:
            scene.close()


def _serve(app,port,no_browser):
    import uvicorn
    if not no_browser:
        import asyncio,webbrowser
        async def open_browser():
            asyncio.get_running_loop().call_later(1,lambda:webbrowser.open(f'http://127.0.0.1:{port}/'))
        app.add_event_handler('startup',open_browser)
    uvicorn.run(app,host='127.0.0.1',port=port)


if __name__=="__main__":
    main()
