"""Loopback-only analysis service. Loaded files are explicitly chosen at launch."""
from pathlib import Path
from hashlib import sha256
import json
import threading
import asyncio
from fastapi import FastAPI, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool
from .liquid_index import MapCalculationCancelled
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .scene import Scene, Recipe
from .render import preview, export


class RenderRequest(BaseModel):
    recipe: dict
    width: int = 560
    height: int = 420
    client_id: str | None = Field(default=None,max_length=100)
    generation: int = Field(default=0,ge=0)


class HitRequest(BaseModel):
    render_id: str
    x: int
    y: int


class ExportRequest(BaseModel):
    recipe: dict
    layout: str = "diagnostics"
    width_mm: float = 180
    height_mm: float = 150
    dpi: int = 300


def create_app(scene=None, output="outputs", frontend=None, *, cache=None):
    app=FastAPI(title="PACE L1C Analysis desk")
    lock=threading.RLock()  # HDF5 + Matplotlib are not thread safe.
    renders={}
    jobs={}  # Per-browser generations; never require the science lock to cancel.
    output=Path(output).resolve()
    app.state.scene=scene
    app.state.scene_lock=lock

    def replace_scene(paths):
        nonlocal scene
        with lock:
            replacement=Scene(paths['oci'],paths['harp2'],paths.get('gpc'),paths.get('mie'),paths.get('atmosphere'))
            old=scene
            for _,event in jobs.values():event.set()
            jobs.clear();renders.clear()
            scene=replacement
            app.state.scene=scene
            if old is not None:old.close()

    from .launcher import install_launcher
    install_launcher(app,replace_scene,lambda:scene,cache=cache)


    @app.middleware("http")
    async def local_origin(request, call_next):
        host=request.headers.get("host","").split(":")[0]
        origin=request.headers.get("origin")
        if host not in ("localhost","127.0.0.1","testserver") or (origin and origin not in ("http://"+request.headers.get("host",""), "https://"+request.headers.get("host",""))):
            return __import__("fastapi").responses.JSONResponse({"detail":"Local same-origin requests only"}, status_code=403)
        if request.headers.get('sec-fetch-site')=='cross-site' and request.url.path.startswith('/api/'):
            return __import__('fastapi').responses.JSONResponse({'detail':'Local same-origin requests only'},status_code=403)
        if request.method=='POST' and request.url.path.startswith('/api/setup') and request.url.path!='/api/setup/import' and 'application/json' not in request.headers.get('content-type',''):
            return __import__('fastapi').responses.JSONResponse({'detail':'JSON same-origin request required'},status_code=415)
        if scene is None and request.url.path.startswith('/api/') and not request.url.path.startswith('/api/setup'):
            return __import__('fastapi').responses.JSONResponse({'detail':'Choose a scene first'},status_code=409)
        return await call_next(request)

    @app.exception_handler(ValueError)
    async def invalid(request, error):
        return __import__("fastapi").responses.JSONResponse({"detail":str(error)},status_code=422)

    @app.exception_handler(TypeError)
    async def unsupported(request,error):
        return __import__("fastapi").responses.JSONResponse({"detail":"Malformed or unsupported recipe field"},status_code=422)

    @app.get("/api/scene")
    def info():
        with lock:
            return {"oci":scene.oci.inventory(),"harp2":scene.harp.inventory(),"alignment":scene.evidence,
                    "correction_capabilities":scene.atmosphere.capabilities if scene.atmosphere else {"rayleigh":False,"transmission":False},
                    "liquid_index_available":scene.gpc is not None and 'cloud_liquid_index' in scene.gpc.data,
                    "model_capabilities":{"cloudbow":scene.cloudbow is not None,"rft":scene.cloudbow is not None},
                    "phase_available":scene.atmosphere is not None and scene.atmosphere.phase is not None,"atmosphere":scene.atmosphere.provenance if scene.atmosphere else None,"anchors":scene.anchors(),"default_crop_policy":"bounding original bins of valid HARP2 default RGB footprint",
                    "default_recipe":__import__("dataclasses").asdict(scene.default_recipe())}

    @app.get("/api/scenes")
    def scenes():
        return [{"oci":scene.oci.identity,"harp2":scene.harp.identity,"alignment":scene.evidence}]

    @app.post("/api/render")
    async def render(req: RenderRequest, request: Request):
        # Aborting fetch must stop obsolete CPU work, not merely hide its reply.
        # Keep all HDF5/Matplotlib work under the original shared lock.
        abandoned=threading.Event()
        if req.client_id is not None:
            previous=jobs.get(req.client_id)
            if previous is not None:
                if req.generation<=previous[0]:return Response(status_code=499)
                previous[1].set()
            jobs[req.client_id]=(req.generation,abandoned)
            if len(jobs)>32:
                oldest=next(iter(jobs));jobs.pop(oldest)[1].set()
        def calculate():
            with lock:
                if abandoned.is_set():raise MapCalculationCancelled()
                key=sha256(json.dumps(req.model_dump(exclude={'client_id','generation'}),sort_keys=True).encode()).hexdigest()[:24]
                if key not in renders:
                    result, ids=preview(scene,Recipe.from_dict(req.recipe),req.width,req.height,cancelled=abandoned.is_set)
                    if abandoned.is_set():raise MapCalculationCancelled()
                    if len(renders)>=8:
                        renders.pop(next(iter(renders)))
                    renders[key]=(result,ids)
                return dict(renders[key][0],render_id=key)
        task=asyncio.create_task(run_in_threadpool(calculate))
        try:
            while not task.done():
                done,_=await asyncio.wait({task},timeout=.1)
                if not done and await request.is_disconnected():
                    abandoned.set()
                    try:await task
                    except MapCalculationCancelled:pass
                    return Response(status_code=499)
            return await task
        except MapCalculationCancelled:
            return Response(status_code=499)
        except asyncio.CancelledError:
            abandoned.set()
            # The worker will release its lock on its next row checkpoint.
            task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
            raise
        finally:
            abandoned.set()

    @app.post("/api/hit")
    def hit(req: HitRequest):
        with lock:
            if req.render_id not in renders:
                raise HTTPException(409,"Preview expired; render again")
            ids=renders[req.render_id][1]
            if not (0<=req.y<ids.shape[0] and 0<=req.x<ids.shape[1]):
                raise ValueError("Screen point outside preview")
            id_=int(ids[req.y,req.x])
            if id_<0:
                raise ValueError("No original source cell at screen point")
            return {"selected":[id_//scene.shape[1],id_%scene.shape[1]]}

    @app.get("/api/bin/{row}/{col}")
    def bin_(row:int,col:int,rft:bool=False,rft_weighting:str='number'):
        with lock:
            if not(0<=row<scene.shape[0] and 0<=col<scene.shape[1]):
                raise ValueError("Source bin outside granule")
            if rft_weighting not in ('literal','number','area'):raise ValueError('Unsupported RFT fraction interpretation')
            return scene.diagnostics([row,col],rft=rft,rft_weighting=rft_weighting)

    @app.post("/api/export")
    def export_(req: ExportRequest):
        with lock:
            key=sha256(json.dumps(req.model_dump(),sort_keys=True).encode()).hexdigest()[:24]
            paths=export(scene,Recipe.from_dict(req.recipe),output/key,req.layout,req.width_mm,req.height_mm,req.dpi)
            return {"artifacts":["/api/artifact/"+p.name for p in paths]}

    @app.get("/api/artifact/{name}")
    def artifact(name:str):
        if Path(name).name!=name or not (output/name).is_file():
            raise HTTPException(404,"Artifact unavailable")
        return FileResponse(output/name,filename=name)

    if frontend is None:
        packaged=Path(__file__).parent/'web'
        frontend=packaged if (packaged/'index.html').is_file() else Path(__file__).resolve().parents[2]/'frontend/dist'
    frontend=Path(frontend)
    if frontend.is_dir():
        app.mount("/",StaticFiles(directory=frontend,html=True),name="dashboard")
    return app
