"""Regression: superseded map requests must release the science/render lock."""
import asyncio
import threading
import time
from dataclasses import asdict
import numpy as np
import pytest
from fastapi.testclient import TestClient
from pace_l1c import service,liquid_index
from pace_l1c.fixtures import create_pair
from pace_l1c.scene import Scene,Recipe


def test_disconnected_render_stops_worker_and_next_map_can_render(tmp_path,monkeypatch):
    scene=Scene(*create_pair(tmp_path/'pair'))
    try:
        app=service.create_app(scene)
        endpoint=next(r.endpoint for r in app.routes if getattr(r,'path',None)=='/api/render')
        started=threading.Event();stopped=threading.Event()
        original=service.preview
        def slow_preview(*args,cancelled=None,**kwargs):
            started.set()
            deadline=time.monotonic()+3
            while not cancelled():
                if time.monotonic()>deadline:raise AssertionError('Obsolete render did not receive cancellation')
                time.sleep(.005)
            stopped.set()
            raise liquid_index.MapCalculationCancelled()
        monkeypatch.setattr(service,'preview',slow_preview)
        class Disconnected:
            async def is_disconnected(self):return True
        response=asyncio.run(endpoint(service.RenderRequest(recipe=asdict(Recipe())),Disconnected()))
        assert response.status_code==499 and started.is_set() and stopped.is_set()
        # The cancelled result must not enter cache, and its lock must be free.
        monkeypatch.setattr(service,'preview',original)
        response=TestClient(app).post('/api/render',json={'recipe':asdict(Recipe()),'width':80,'height':80})
        assert response.status_code==200 and len(response.json()['layers'])==3
    finally:scene.close()


def test_derived_map_row_cancellation_keeps_partial_values_out_of_scene_cache(tmp_path,monkeypatch):
    scene=Scene(*create_pair(tmp_path/'pair'))
    try:
        original=liquid_index.map_layers
        def cancel(*args,**kwargs):raise liquid_index.MapCalculationCancelled()
        monkeypatch.setattr(liquid_index,'map_layers',cancel)
        recipe=Recipe(left_mode='liquid_index_discrete')
        with pytest.raises(liquid_index.MapCalculationCancelled):scene.layers(recipe,cancelled=lambda:True)
        assert scene._liquid_maps[('signed_q','1')]=={}
        assert scene._layers=={}
        monkeypatch.setattr(liquid_index,'map_layers',original)
        # Exercise actual bounded-loop cancellation rather than only a stub.
        calls=0
        def cancelled():
            nonlocal calls
            calls+=1
            return calls>=2
        with pytest.raises(liquid_index.MapCalculationCancelled):
            original(scene.harp,baseline_only=True,cancelled=cancelled)
        assert calls==2
        recovered=scene.layers(recipe)[0]
        expected=original(scene.harp,extended=False)['discrete']
        np.testing.assert_array_equal(recovered,expected)
    finally:scene.close()


def test_newer_browser_generation_cancels_old_render_even_without_disconnect(tmp_path,monkeypatch):
    scene=Scene(*create_pair(tmp_path/'pair'))
    try:
        app=service.create_app(scene)
        endpoint=next(r.endpoint for r in app.routes if getattr(r,'path',None)=='/api/render')
        started=threading.Event();stopped=threading.Event();original=service.preview
        def slow_preview(scene,recipe,*args,cancelled=None,**kwargs):
            if recipe.title!='slow':return original(scene,recipe,*args,cancelled=cancelled,**kwargs)
            started.set();deadline=time.monotonic()+3
            while not cancelled():
                if time.monotonic()>deadline:raise AssertionError('New dropdown request did not cancel old generation')
                time.sleep(.005)
            stopped.set();raise liquid_index.MapCalculationCancelled()
        monkeypatch.setattr(service,'preview',slow_preview)
        class Connected:
            async def is_disconnected(self):return False
        async def run():
            first=service.RenderRequest(recipe=asdict(Recipe(title='slow')),client_id='browser',generation=1,width=80,height=80)
            old=asyncio.create_task(endpoint(first,Connected()))
            assert await asyncio.to_thread(started.wait,1)
            new=service.RenderRequest(recipe=asdict(Recipe()),client_id='browser',generation=2,width=80,height=80)
            result=await endpoint(new,Connected())
            assert len(result['layers'])==3
            assert (await old).status_code==499
            assert (await endpoint(first,Connected())).status_code==499 # late stale request
        asyncio.run(run());assert stopped.is_set()
    finally:scene.close()
