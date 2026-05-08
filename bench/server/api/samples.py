"""Sample browsing + image serving API."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from ...config import load_config
from ...runner.dataset import load_manifest, resolve_samples_root

router = APIRouter(prefix="/api/samples", tags=["samples"])


@router.get("/{benchmark_id}")
async def list_samples(benchmark_id: str) -> dict:
    cfg = load_config()
    benchmarks_dir = cfg.benchmarks_dir()
    fixtures_dir = cfg.repo_root / "tests" / "fixtures"
    manifest_path = benchmarks_dir / benchmark_id / "manifest.json"
    if not manifest_path.exists():
        manifest_path = fixtures_dir / benchmark_id / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(404, "benchmark not found")
    manifest = json.loads(manifest_path.read_text())
    samples_root = resolve_samples_root(cfg.repo_root, benchmark_id)
    out = []
    for sid in manifest.get("sample_ids", []):
        meta_path = samples_root / sid / "meta.json"
        if not meta_path.exists():
            continue
        m = json.loads(meta_path.read_text())
        out.append({
            "id": m["id"],
            "task_type": m.get("task_type"),
            "tier": m.get("metadata", {}).get("tier") or m.get("metadata", {}).get("difficulty_split"),
            "presence": "correct_absent" if m.get("none_of_the_above_is_correct") else "correct_present",
            "source": (m.get("subject") or {}).get("real_or_synthetic", "unknown"),
        })
    return {"benchmark_id": benchmark_id, "samples": out}


@router.get("/{benchmark_id}/{sample_id}/meta")
async def get_sample_meta(benchmark_id: str, sample_id: str) -> dict:
    cfg = load_config()
    samples_root = resolve_samples_root(cfg.repo_root, benchmark_id)
    meta_path = samples_root / sample_id / "meta.json"
    if not meta_path.exists():
        raise HTTPException(404)
    return json.loads(meta_path.read_text())


@router.get("/{benchmark_id}/{sample_id}/image/{filename}")
async def get_sample_image(benchmark_id: str, sample_id: str, filename: str):
    """Serve a sample image. Redirects to Azure CDN when meta.json has cdn_url; falls
    back to the local file otherwise."""
    cfg = load_config()
    samples_root = resolve_samples_root(cfg.repo_root, benchmark_id)
    sample_dir = samples_root / sample_id
    if ".." in filename or "/" in filename:
        raise HTTPException(404)
    meta_path = sample_dir / "meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text())
            if filename == meta.get("base_image") and meta.get("base_cdn_url"):
                return RedirectResponse(meta["base_cdn_url"], status_code=302)
            for letter in ("A", "B", "C", "D"):
                opt = meta.get("options", {}).get(letter, {})
                if opt.get("image") == filename and opt.get("cdn_url"):
                    return RedirectResponse(opt["cdn_url"], status_code=302)
        except Exception:
            pass
    img_path = sample_dir / filename
    if not img_path.exists():
        raise HTTPException(404)
    return FileResponse(img_path)
