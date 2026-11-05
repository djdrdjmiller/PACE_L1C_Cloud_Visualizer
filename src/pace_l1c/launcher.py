"""Local scene setup, bounded jobs and Earthdata login; never a public server."""
from concurrent.futures import ThreadPoolExecutor
import json
import logging
import os
from pathlib import Path
import re
import threading
import uuid
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
from .discovery import cache_directory, search, public_entry, make_manifest, scene_record, saved_scenes, incomplete_acquisitions
from .acquisition import DownloadCancelled, download
from .reader import sha256


class SearchRequest(BaseModel):
    identifier: str = Field(default='', max_length=180)
    start: str | None = None
    end: str | None = None
    bbox: list[float] | None = None
    limit: int = Field(default=12, ge=1, le=20)


class AcquireRequest(BaseModel):
    search_id: str
    candidate_id: str
    gpc_id: str | None = None
    budget_gib: float = Field(default=4, gt=0, le=100)
    rayleigh: bool = False
    ancillary_budget_mib: int = Field(default=768, ge=1, le=4096)


class LocalRequest(BaseModel):
    oci: str
    harp2: str
    gpc: str | None = None
    mie: str | None = None
    atmosphere: str | None = None


class RetryRequest(BaseModel):
    acquisition_id: str
    budget_gib: float = Field(default=4,gt=0,le=100)


class SavedRequest(BaseModel):
    scene_id: str


def install_launcher(app, replace_scene, current_scene, *, cache=None):
    directory = cache_directory(cache)
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='pace-acquisition')
    state_lock = threading.RLock()
    job = {'id': None, 'status': 'idle', 'message': 'Choose a scene'}
    cancellation = threading.Event()
    result_store = {}
    auth_lock = threading.RLock()
    session = None

    def update(**values):
        with state_lock:
            job.update(values)

    def progress(value):
        update(message=value.get('file', 'Working'), transfer=value)

    def check_cancelled():
        if cancellation.is_set():
            raise DownloadCancelled('Cancelled; completed files remain in your cache')

    def submit(message, work):
        with state_lock:
            if job['status'] == 'running':
                raise HTTPException(409, 'A setup operation is still running; wait or cancel it')
            cancellation.clear()
            job.clear()
            job.update(id=uuid.uuid4().hex, status='running', message=message, transfer=None)
            def run():
                try:
                    with app.state.scene_lock:
                        value = work()
                    check_cancelled()
                    update(status='complete', result=value, message='Ready')
                except DownloadCancelled:
                    update(status='cancelled', message='Cancelled; completed files retained')
                except Exception as error:
                    # Never return a URL, response body or credential-bearing network exception.
                    message = str(error) if isinstance(error, (ValueError, FileNotFoundError)) else f'{type(error).__name__}: operation failed. Check Earthdata authentication/network and retry.'
                    update(status='failed', message=message)
            executor.submit(run)
            return {'job_id': job['id']}

    def get_session():
        nonlocal session
        with auth_lock:
            if session is not None:
                return session
            import earthaccess
            for strategy in ('environment', 'netrc'):
                try:
                    auth = earthaccess.login(strategy=strategy, persist=False)
                    if auth.authenticated:
                        session = earthaccess.get_requests_https_session()
                        return session
                except Exception:
                    continue
            raise ValueError('Earthdata sign-in required. Connect your account in setup or run pace-l1c login.')

    def verify_and_open(record):
        check_cancelled()
        for role, path in record['paths'].items():
            if sha256(path) != record['hashes'][role]:
                raise ValueError('Saved source has changed: ' + role + '. Import/validate it as a new scene.')
        check_cancelled()
        replace_scene(record['paths'])
        return {'scene': record}

    def _ancillary(paths, budget_mib):
        from .ancillary import acquire_clouds, acquire
        from .atmosphere import prepare
        from .scene import Scene
        base = directory / 'ancillary' / sha256(paths['oci'])[:24]
        cloud_dir, met_dir = base / 'cloud', base / 'met'
        def spent(p):
            return json.loads(p.read_text()).get('attempted_bytes', 0) if p.exists() else 0
        # Shared upper bound across the existing independent ledgers, including failures.
        met_spent = spent(met_dir / 'acquisition.json')
        if met_spent >= budget_mib * 2**20:
            raise ValueError('Ancillary transfer budget exhausted by earlier MET attempts')
        with_scene = Scene(paths['oci'], paths['harp2'])
        try:
            update(message='Resolving OCI cloud coverage and declared MET pressure inputs')
            clouds = acquire_clouds(with_scene.oci, cloud_dir, budget_mib - met_spent / 2**20,
                                    session=get_session(), cancelled=cancellation.is_set, progress=progress)
            cloud_spent = spent(cloud_dir / 'cloud-acquisition.json')
            for cloud in clouds:
                check_cancelled()
                acquire(cloud, met_dir, budget_mib - cloud_spent / 2**20, session=get_session(),
                        kind='met', cancelled=cancellation.is_set, progress=progress)
            check_cancelled()
            update(message='Preparing existing experimental land + water Rayleigh boundaries')
            target = base / 'rayleigh-boundary.nc'
            prepare(with_scene, clouds, met_dir, None, target, mode='rayleigh')
            return str(target)
        finally:
            with_scene.close()

    @app.get('/api/setup')
    def setup():
        return {'scene_loaded': current_scene() is not None, 'cache_directory': str(directory),
                'earthdata_connected': session is not None,
                'collections': __import__('pace_l1c.discovery', fromlist=['COLLECTIONS']).COLLECTIONS,
                'remote_mie': False}

    @app.get('/api/setup/job')
    def status():
        with state_lock:
            return dict(job)

    @app.post('/api/setup/cancel')
    def cancel():
        cancellation.set()
        return {'status': 'cancelling', 'message': 'Stopping at the next transfer/preparation checkpoint'}

    @app.post('/api/setup/search')
    def find(req: SearchRequest):
        def work():
            result = search(**req.model_dump())
            check_cancelled()
            search_id = uuid.uuid4().hex
            result_store.clear()
            result_store[search_id] = result
            return {**result, 'search_id': search_id, 'files': {i: public_entry(f) for i, f in result['files'].items()}}
        return submit('Searching NASA catalog', work)

    @app.post('/api/setup/acquire')
    def acquire_scene(req: AcquireRequest):
        if req.search_id not in result_store:
            raise ValueError('Search expired; search again')
        result = result_store[req.search_id]
        def work():
            path = make_manifest(result, req.candidate_id, directory, gpc_id=req.gpc_id, budget_gib=req.budget_gib)
            # Verified cache reuse can be completely offline, without authentication.
            m = json.loads(path.read_text())
            needs_transfer = any(not f.get('path') or not Path(f['path']).is_file() or sha256(f['path']) != f.get('sha256') for f in m['files'].values())
            from .acquisition import save
            m['setup_options']={'rayleigh':req.rayleigh,'ancillary_budget_mib':req.ancillary_budget_mib}
            save(path,m)
            if needs_transfer:
                from types import SimpleNamespace
                lazy_session=SimpleNamespace(get=lambda *a,**kw:get_session().get(*a,**kw))
                m = download(path, session=lazy_session, cancelled=cancellation.is_set, progress=progress)
            check_cancelled()
            pair = m['cases'][0]['pairs'][0]
            warnings, paths = [], {}
            for role, key in pair.items():
                f = m['files'][key]
                if f['status'] == 'complete':
                    paths[role] = f['path']
                elif role == 'gpc':
                    warnings.append('GPC transfer failed or exceeded budget; core scene remains available')
                else:
                    raise ValueError('Required '+role.upper()+' is not ready ('+f['status']+'): '+f['name']+'. '+f.get('reason','Check transfer budget and authentication')+'. Complete staged files are retained for revalidation; earlier transfer attempts still count.')
            update(message='Validating full OCI/HARP2 geolocation')
            # Optional GPC incompatibility disables GPC, never invalidates an aligned core.
            try:
                record = scene_record(directory, paths, warnings=warnings)
            except ValueError:
                if 'gpc' not in paths:
                    raise
                paths.pop('gpc')
                warnings.append('GPC did not pass registration/metadata checks; omitted')
                record = scene_record(directory, paths, warnings=warnings)
            if req.rayleigh:
                try:
                    paths['atmosphere'] = _ancillary(paths, req.ancillary_budget_mib)
                    record = scene_record(directory, paths, warnings=warnings)
                except DownloadCancelled:
                    raise
                except Exception as error:
                    warnings.append('Rayleigh/OCI phase unavailable: ' + (str(error) if isinstance(error, ValueError) else type(error).__name__) + '. Core scene saved; no pressure fallback.')
                    paths.pop('atmosphere', None)
                    record = scene_record(directory, paths, warnings=warnings)
            check_cancelled()
            # Store validation evidence in the same acquisition manifest.
            m['cases'][0].update(status='aligned')
            m['cases'][0]['pairs'][0].update(status='aligned', evidence=record['alignment'])
            from .acquisition import save
            save(path, m)
            return {'scene': record}
        return submit('Preparing selected scene', work)

    @app.get('/api/setup/saved')
    def saved():
        return saved_scenes(directory)

    @app.get('/api/setup/acquisitions')
    def acquisitions():
        return incomplete_acquisitions(directory)

    @app.post('/api/setup/retry')
    def retry(req: RetryRequest):
        if not re.fullmatch('[a-f0-9]{20}',req.acquisition_id):raise ValueError('Unknown acquisition')
        path=directory/'acquisitions'/(req.acquisition_id+'.json')
        if not path.is_file():raise ValueError('Acquisition unavailable')
        m=json.loads(path.read_text());pair=m['cases'][0]['pairs'][0]
        search_id=uuid.uuid4().hex
        candidate={'id':req.acquisition_id,'oci':pair['oci'],'harp2':pair['harp2'],'gpc_candidates':[pair['gpc']] if pair.get('gpc') else []}
        result_store[search_id]={'files':m['files'],'candidates':[candidate],'search':m.get('search',{})}
        options=m.get('setup_options',{})
        return acquire_scene(AcquireRequest(search_id=search_id,candidate_id=req.acquisition_id,gpc_id=pair.get('gpc'),budget_gib=req.budget_gib,
                                           rayleigh=options.get('rayleigh',False),ancillary_budget_mib=options.get('ancillary_budget_mib',768)))

    @app.post('/api/setup/local')
    def local(req: LocalRequest):
        def work():
            record = scene_record(directory, req.model_dump(exclude_none=True))
            return {'scene': record}
        return submit('Validating your local pair', work)

    @app.post('/api/setup/import')
    async def import_file(request: Request, name: str):
        # Browser File inputs do not disclose absolute paths. Stream a local copy;
        # never buffer multi-GB files in memory or send them to an external service.
        if Path(name).name != name or not re.fullmatch(r'[A-Za-z0-9_.-]{1,180}\.nc', name):
            raise ValueError('Choose a NetCDF .nc file with a plain filename')
        dest = directory / 'imports' / uuid.uuid4().hex / name
        dest.parent.mkdir(parents=True)
        part = dest.with_suffix('.nc.partial')
        maximum = 3 * 2**30
        count = 0
        try:
            with part.open('wb') as stream:
                async for chunk in request.stream():
                    count += len(chunk)
                    if count > maximum:
                        raise ValueError('Local import exceeds the 3 GiB per-file limit; use an explicit local path instead')
                    stream.write(chunk)
            if count == 0:
                raise ValueError('Empty file')
            part.replace(dest)
        except BaseException:
            # Remove only this new incomplete import, never existing source data.
            part.unlink(missing_ok=True)
            raise
        return {'path': str(dest), 'bytes': count}

    @app.post('/api/setup/demo')
    def demo():
        def work():
            from .fixtures import create_pair
            files = create_pair(directory / 'synthetic' / uuid.uuid4().hex)
            record = scene_record(directory, dict(oci=files[0], harp2=files[1]), synthetic=True, label='Synthetic OCI + HARP2 demonstration')
            return {'scene': record}
        return submit('Creating independent synthetic scene', work)

    @app.post('/api/setup/open')
    def open_saved(req: SavedRequest):
        if not re.fullmatch('[a-f0-9]{24}', req.scene_id):
            raise ValueError('Unknown saved scene')
        path = directory / 'scenes' / (req.scene_id + '.json')
        if not path.is_file():
            raise ValueError('Saved scene unavailable')
        return submit('Rechecking saved sources and opening dashboard', lambda: verify_and_open(json.loads(path.read_text())))

    @app.post('/api/setup/login')
    async def login(request: Request):
        nonlocal session
        with state_lock:
            if job['status'] == 'running':
                raise HTTPException(409, 'Wait for the current operation before changing authentication')
        # Avoid Pydantic validation responses echoing password/token inputs.
        body = await request.json()
        if not isinstance(body, dict) or any(k not in ('username', 'password', 'remember', 'existing') for k in body):
            raise HTTPException(400, 'Malformed sign-in request')
        existing = body.get('existing', False)
        if existing:
            from starlette.concurrency import run_in_threadpool
            await run_in_threadpool(get_session)
            return {'connected': True}
        username, password = body.get('username'), body.get('password')
        remember = body.get('remember', False)
        if not isinstance(username, str) or not isinstance(password, str) or not username or not password or len(username) > 200 or len(password) > 1000 or type(remember) is not bool:
            raise HTTPException(400, 'Enter your Earthdata username and password')
        def connect():
            nonlocal session
            # Use earthaccess's public environment login strategy, restoring the
            # environment immediately. No credentials enter jobs/manifests/logs.
            import earthaccess
            with auth_lock:
                names = ('EARTHDATA_USERNAME', 'EARTHDATA_PASSWORD', 'EARTHDATA_TOKEN')
                previous = {k: os.environ.get(k) for k in names}
                old_level = logging.getLogger('earthaccess').level
                try:
                    logging.getLogger('earthaccess').setLevel(logging.CRITICAL)
                    os.environ['EARTHDATA_USERNAME'] = username
                    os.environ['EARTHDATA_PASSWORD'] = password
                    os.environ.pop('EARTHDATA_TOKEN', None)
                    auth = earthaccess.login(strategy='environment', persist=remember)
                    if not auth.authenticated:
                        raise RuntimeError('Authentication failed')
                    session = earthaccess.get_requests_https_session()
                except Exception:
                    session = None
                    raise HTTPException(401, 'Earthdata sign-in failed. Check your credentials, NASA application authorization and network connection.') from None
                finally:
                    logging.getLogger('earthaccess').setLevel(old_level)
                    for k, value in previous.items():
                        if value is None:
                            os.environ.pop(k, None)
                        else:
                            os.environ[k] = value
        from starlette.concurrency import run_in_threadpool
        await run_in_threadpool(connect)
        return {'connected': True}

    app.state.launcher_executor = executor
    return directory
