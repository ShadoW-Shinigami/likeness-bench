"""Leaderboard + per-run results API."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ...config import load_config

router = APIRouter(prefix="/api/results", tags=["results"])


@router.get("/benchmarks")
async def list_benchmarks() -> dict:
    cfg = load_config()
    benchmarks_dir = cfg.benchmarks_dir()
    out = []
    if benchmarks_dir.exists():
        for d in sorted(benchmarks_dir.iterdir()):
            mp = d / "manifest.json"
            if mp.exists():
                m = json.loads(mp.read_text())
                out.append({
                    "id": m.get("benchmark_id"),
                    "title": m.get("title", m.get("benchmark_id")),
                    "description": m.get("description", ""),
                    "task_type": m.get("task_type", "mcq_likeness"),
                    "n_samples": len(m.get("sample_ids", [])),
                })
    fixtures_dir = cfg.repo_root / "tests" / "fixtures"
    if fixtures_dir.exists():
        for d in sorted(fixtures_dir.iterdir()):
            mp = d / "manifest.json"
            if mp.exists():
                m = json.loads(mp.read_text())
                out.append({
                    "id": m.get("benchmark_id"),
                    "title": m.get("title", m.get("benchmark_id")) + " (fixture)",
                    "description": m.get("description", ""),
                    "task_type": m.get("task_type", "mcq_likeness"),
                    "n_samples": len(m.get("sample_ids", [])),
                    "fixture": True,
                })
    return {"benchmarks": out, "default": cfg.engine.default_benchmark}


@router.get("/{benchmark_id}/index")
async def benchmark_index(benchmark_id: str) -> dict:
    cfg = load_config()
    path = cfg.results_dir_path() / benchmark_id / "index.json"
    if not path.exists():
        return {"benchmark_id": benchmark_id, "rows": [], "baselines": []}
    return json.loads(path.read_text())


@router.get("/{benchmark_id}/runs/{file}")
async def get_run_file(benchmark_id: str, file: str) -> dict:
    cfg = load_config()
    path = cfg.results_dir_path() / benchmark_id / file
    if not path.exists() or path.suffix != ".json":
        raise HTTPException(404)
    return json.loads(path.read_text())
