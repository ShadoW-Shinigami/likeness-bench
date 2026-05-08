"""Atomic per-sample result writes for resume support."""
from __future__ import annotations

import json
from pathlib import Path

from ..models import SampleResult


def sample_path(runs_dir: Path, run_id: str, sample_id: str) -> Path:
    return runs_dir / run_id / "samples" / f"{sample_id}.json"


def write_sample(runs_dir: Path, run_id: str, result: SampleResult) -> None:
    path = sample_path(runs_dir, run_id, result.sample_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(result.model_dump_json(indent=2))
    tmp.replace(path)


def load_sample(runs_dir: Path, run_id: str, sample_id: str) -> SampleResult | None:
    path = sample_path(runs_dir, run_id, sample_id)
    if not path.exists():
        return None
    return SampleResult.model_validate_json(path.read_text())


def completed_sample_ids(runs_dir: Path, run_id: str) -> set[str]:
    folder = runs_dir / run_id / "samples"
    if not folder.exists():
        return set()
    return {p.stem for p in folder.glob("*.json")}
