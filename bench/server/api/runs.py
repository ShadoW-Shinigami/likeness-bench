"""Run control + listing API."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ...config import load_config
from ...models import RunControlState
from ...runner import control, pipeline

router = APIRouter(prefix="/api/runs", tags=["runs"])

# In-process registry of running coroutines so we can also kill via os signal.
_RUN_TASKS: dict[str, asyncio.Task] = {}


class StartRunRequest(BaseModel):
    model: str
    benchmark: str | None = None
    samples: tuple[int, int] | None = None
    concurrency: int | None = None
    max_cost_usd: float | None = None
    resume: bool = False


@router.get("")
async def list_runs() -> dict:
    cfg = load_config()
    states = control.list_states(cfg.runs_dir_path())
    return {"runs": [s.model_dump() for s in states]}


@router.get("/{run_id}")
async def get_run(run_id: str) -> dict:
    cfg = load_config()
    s = control.read_state(cfg.runs_dir_path(), run_id)
    if not s:
        raise HTTPException(404, f"Run {run_id} not found")
    return s.model_dump()


@router.post("")
async def start_run(req: StartRunRequest) -> dict:
    cfg = load_config()
    bench_id = req.benchmark or cfg.engine.default_benchmark
    rid = pipeline.make_run_id(req.model, bench_id)

    async def _go() -> None:
        try:
            await pipeline.run_evaluation(
                cfg=cfg,
                model_key=req.model,
                benchmark_id=bench_id,
                sample_slice=req.samples,
                concurrency=req.concurrency,
                max_cost_usd=req.max_cost_usd,
                resume=req.resume,
                run_id=rid,
            )
        finally:
            _RUN_TASKS.pop(rid, None)

    task = asyncio.create_task(_go())
    _RUN_TASKS[rid] = task
    return {"run_id": rid, "status": "queued"}


@router.post("/{run_id}/pause")
async def pause_run(run_id: str) -> dict:
    cfg = load_config()
    s = control.request_action(cfg.runs_dir_path(), run_id, "pause")
    if not s:
        raise HTTPException(404)
    return s.model_dump()


@router.post("/{run_id}/resume")
async def resume_run(run_id: str) -> dict:
    cfg = load_config()
    s = control.request_action(cfg.runs_dir_path(), run_id, "resume")
    if not s:
        raise HTTPException(404)
    return s.model_dump()


@router.post("/{run_id}/kill")
async def kill_run(run_id: str) -> dict:
    cfg = load_config()
    s = control.request_action(cfg.runs_dir_path(), run_id, "kill")
    task = _RUN_TASKS.get(run_id)
    if task and not task.done():
        # Will exit at next sample boundary; we can't safely cancel mid-call
        # because that strands writes. The control flag is the canonical signal.
        pass
    if not s:
        raise HTTPException(404)
    return s.model_dump()


@router.get("/{run_id}/stream")
async def stream_run(run_id: str):
    """Server-sent events with periodic state snapshots."""
    cfg = load_config()

    async def event_gen():
        last_payload = None
        while True:
            s = control.read_state(cfg.runs_dir_path(), run_id)
            if s is None:
                yield {"event": "error", "data": json.dumps({"error": "not_found"})}
                break
            payload = s.model_dump_json()
            if payload != last_payload:
                yield {"event": "update", "data": payload}
                last_payload = payload
            if s.status in ("completed", "failed", "killed"):
                yield {"event": "end", "data": payload}
                break
            await asyncio.sleep(0.5)

    return EventSourceResponse(event_gen())
