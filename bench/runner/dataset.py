"""Benchmark + sample loaders."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..models import BenchmarkManifest, Sample, SampleMeta


def load_manifest(benchmarks_dir: Path, benchmark_id: str) -> BenchmarkManifest:
    """Load benchmarks/<id>/manifest.json or tests/fixtures/<id>/manifest.json."""
    candidates = [
        benchmarks_dir / benchmark_id / "manifest.json",
        benchmarks_dir.parent / "tests" / "fixtures" / benchmark_id / "manifest.json",
        benchmarks_dir.parent / "dataset" / benchmark_id / "manifest.json",
    ]
    for p in candidates:
        if p.exists():
            return BenchmarkManifest.model_validate_json(p.read_text())
    raise FileNotFoundError(f"No manifest. Tried: {candidates}")


def load_sample(samples_root: Path, sample_id: str) -> Sample:
    sample_dir = samples_root / sample_id
    meta_path = sample_dir / "meta.json"
    meta = SampleMeta.model_validate_json(meta_path.read_text())
    return Sample(meta=meta, sample_dir=sample_dir)


def benchmark_hash(samples_root: Path, sample_ids: list[str]) -> str:
    h = hashlib.sha256()
    for sid in sorted(sample_ids):
        meta_path = samples_root / sid / "meta.json"
        if meta_path.exists():
            h.update(meta_path.read_bytes())
    return h.hexdigest()


def resolve_samples_root(repo_root: Path, benchmark_id: str) -> Path:
    """Where the actual sample directories live for this benchmark."""
    candidates = [
        repo_root / "dataset" / benchmark_id / "samples",
        repo_root / "benchmarks" / benchmark_id / "samples",
        repo_root / "tests" / "fixtures" / benchmark_id / "samples",
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        f"No samples dir for benchmark '{benchmark_id}'. Tried: {candidates}"
    )
