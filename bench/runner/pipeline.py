"""Async evaluation pipeline with run control."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from ..config import BenchConfig, ModelConfig, get_api_key, load_config
from ..logging import get_logger
from ..models import (
    BenchmarkManifest,
    Letter,
    ProviderResponse,
    RunControlState,
    RunResult,
    Sample,
    SampleResult,
)
from ..registry import get_provider_class, get_task_class
from ..scoring.composite import composite_likeness_score
from ..scoring.intervals import wilson_interval
from ..scoring.metrics import aggregate
from . import checkpoint, control
from .cost import BudgetExceeded, CostLedger
from .dataset import benchmark_hash, load_manifest, load_sample, resolve_samples_root

log = get_logger("runner")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_run_id(model_id: str, benchmark_id: str) -> str:
    raw = f"{model_id}-{benchmark_id}-{time.time()}".encode()
    digest = hashlib.sha256(raw).hexdigest()[:8]
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    return f"{stamp}_{model_id}_{benchmark_id}_{digest}"


def build_provider(cfg: BenchConfig, model_key: str):
    mc: ModelConfig = cfg.model_config_for(model_key)
    pcfg = cfg.providers.get(mc.provider)
    cls = get_provider_class(mc.provider)
    api_key = get_api_key(pcfg.api_key_env if pcfg else None) if pcfg else None
    return cls(
        model_id=mc.model_id,
        display=mc.display,
        family=mc.family,
        price_per_1m_input=mc.price_per_1m_input,
        price_per_1m_output=mc.price_per_1m_output,
        max_concurrency=(pcfg.max_concurrency if pcfg else 4),
        api_key=api_key,
        base_url=(pcfg.base_url if pcfg else None),
        extra=mc.extra,
    )


async def _process_sample(
    *,
    sample: Sample,
    task,
    provider,
    runs_dir: Path,
    run_id: str,
    ledger: CostLedger,
) -> SampleResult:
    prompt = task.render_prompt(sample)
    images = task.images_for(sample)
    presence = (
        "correct_absent"
        if sample.meta.none_of_the_above_is_correct
        else "correct_present"
    )
    tier = sample.meta.metadata.get("difficulty_split") or sample.meta.metadata.get("tier")

    resp: ProviderResponse = await provider.evaluate(prompt=prompt, images=images)
    parsed = task.parse(resp)
    correct, extras = task.score(parsed, sample)

    ledger.add(cost=resp.cost_usd, in_tok=resp.input_tokens, out_tok=resp.output_tokens)

    sr = SampleResult(
        sample_id=sample.meta.id,
        tier=tier,
        presence=presence,
        answer=sample.meta.correct_answer,
        predicted=extras.get("predicted"),
        correct=correct,
        raw_output=resp.raw_text,
        refusal=resp.refusal,
        parse_failure=bool(parsed.get("parse_failure")),
        latency_ms=resp.latency_ms,
        cost_usd=resp.cost_usd,
        input_tokens=resp.input_tokens,
        output_tokens=resp.output_tokens,
        error=resp.error,
        completed_at=_now(),
    )
    checkpoint.write_sample(runs_dir, run_id, sr)
    return sr


async def run_evaluation(
    *,
    cfg: BenchConfig,
    model_key: str,
    benchmark_id: str,
    sample_slice: tuple[int, int] | None = None,
    concurrency: int | None = None,
    max_cost_usd: float | None = None,
    resume: bool = False,
    run_id: str | None = None,
) -> dict:
    """Run a model over a benchmark. Returns the aggregated results dict."""
    runs_dir = cfg.runs_dir_path()
    benchmarks_dir = cfg.benchmarks_dir()

    manifest = load_manifest(benchmarks_dir, benchmark_id)
    samples_root = resolve_samples_root(cfg.repo_root, benchmark_id)
    sample_ids = manifest.sample_ids
    if sample_slice:
        lo, hi = sample_slice
        sample_ids = sample_ids[lo:hi]
    bench_hash = benchmark_hash(samples_root, sample_ids)

    rid = run_id or make_run_id(model_key, benchmark_id)
    state = control.init_state(
        runs_dir,
        rid,
        n_samples=len(sample_ids),
        model_id=model_key,
        benchmark_id=benchmark_id,
    )

    mc = cfg.model_config_for(model_key)
    provider = build_provider(cfg, model_key)
    task_cls = get_task_class(manifest.task_type)
    task = task_cls()

    ledger = CostLedger(max_usd=max_cost_usd or cfg.engine.max_cost_usd_default)

    completed = checkpoint.completed_sample_ids(runs_dir, rid) if resume else set()
    pending = [sid for sid in sample_ids if sid not in completed]
    log.info(
        "run.start",
        run_id=rid,
        model=model_key,
        benchmark=benchmark_id,
        total=len(sample_ids),
        pending=len(pending),
        resumed=len(completed),
    )

    control.update_state(runs_dir, rid, status="running", completed=len(completed))

    sem = asyncio.Semaphore(concurrency or cfg.engine.default_concurrency)
    killed = False

    async def _one(sample_id: str) -> SampleResult | None:
        nonlocal killed
        if killed:
            return None
        action = control.wait_if_paused(runs_dir, rid)
        if action == "kill":
            killed = True
            return None
        try:
            ledger.check_budget()
        except BudgetExceeded as e:
            log.warning("budget.exceeded", run_id=rid, error=str(e))
            killed = True
            return None
        async with sem:
            sample = load_sample(samples_root, sample_id)
            try:
                return await _process_sample(
                    sample=sample,
                    task=task,
                    provider=provider,
                    runs_dir=runs_dir,
                    run_id=rid,
                    ledger=ledger,
                )
            except Exception as e:
                log.error("sample.error", run_id=rid, sample=sample_id, error=str(e))
                sr = SampleResult(
                    sample_id=sample_id,
                    answer=sample.meta.correct_answer,
                    predicted=None,
                    correct=False,
                    raw_output="",
                    parse_failure=False,
                    error=f"{type(e).__name__}: {e}",
                    completed_at=_now(),
                )
                checkpoint.write_sample(runs_dir, rid, sr)
                return sr
            finally:
                done = len(checkpoint.completed_sample_ids(runs_dir, rid))
                control.update_state(runs_dir, rid, completed=done)

    tasks = [asyncio.create_task(_one(sid)) for sid in pending]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=False)

    final_status = "killed" if killed else "completed"
    control.update_state(runs_dir, rid, status=final_status)

    return aggregate_run(cfg, run_id=rid, manifest=manifest, sample_ids=sample_ids,
                         model_key=model_key, samples_root=samples_root,
                         bench_hash=bench_hash, killed=killed)


def aggregate_run(
    cfg: BenchConfig,
    *,
    run_id: str,
    manifest: BenchmarkManifest,
    sample_ids: list[str],
    model_key: str,
    samples_root: Path,
    bench_hash: str,
    killed: bool = False,
) -> dict:
    """Aggregate per-sample JSON into a single results file + update index.json."""
    runs_dir = cfg.runs_dir_path()
    sample_results = []
    for sid in sample_ids:
        sr = checkpoint.load_sample(runs_dir, run_id, sid)
        if sr is not None:
            sample_results.append(sr)

    summary = aggregate(sample_results, samples_root)
    composite = composite_likeness_score(
        summary,
        scoring_cfg=cfg.scoring.get(manifest.benchmark_id, {
            "w_present": 0.5, "w_absent": 0.5, "lambda_e": 0.25,
        }),
    )
    summary["composite_likeness_score"] = composite
    if "overall_accuracy" in summary and "overall_ci95" not in summary:
        n = len(sample_results) or 1
        k = sum(1 for r in sample_results if r.correct)
        summary["overall_ci95"] = list(wilson_interval(k, n))

    mc = cfg.model_config_for(model_key)
    cost_total = sum(r.cost_usd for r in sample_results)
    in_tok = sum(r.input_tokens or 0 for r in sample_results)
    out_tok = sum(r.output_tokens or 0 for r in sample_results)
    lats = [r.latency_ms for r in sample_results if r.latency_ms]
    mean_lat = sum(lats) / len(lats) if lats else 0
    p95 = sorted(lats)[int(len(lats) * 0.95) - 1] if len(lats) >= 20 else (max(lats) if lats else 0)

    started = control.read_state(runs_dir, run_id)
    out = {
        "schema_version": "1.0",
        "run_id": run_id,
        "benchmark_id": manifest.benchmark_id,
        "benchmark_hash": bench_hash,
        "n_samples": len(sample_ids),
        "n_completed": len(sample_results),
        "killed": killed,
        "model": {"id": model_key, "model_id": mc.model_id, "display": mc.display, "family": mc.family},
        "engine": {"prompt_template_version": "mcq:1.2"},
        "started_at": started.started_at if started else _now(),
        "completed_at": _now(),
        "metrics": summary,
        "cost": {"total_usd": round(cost_total, 4), "input_tokens": in_tok, "output_tokens": out_tok},
        "latency": {"mean_ms": int(mean_lat), "p95_ms": int(p95)},
    }

    results_dir = cfg.results_dir_path() / manifest.benchmark_id
    results_dir.mkdir(parents=True, exist_ok=True)
    out_path = results_dir / f"{model_key}__{run_id}.json"
    out_path.write_text(json.dumps(out, indent=2))

    update_index(cfg, manifest.benchmark_id)
    log.info("run.aggregate", run_id=run_id, accuracy=summary.get("overall_accuracy"),
             composite=composite, file=str(out_path))
    return out


def update_index(cfg: BenchConfig, benchmark_id: str) -> None:
    """Regenerate results/<benchmark>/index.json from the per-run files."""
    results_dir = cfg.results_dir_path() / benchmark_id
    if not results_dir.exists():
        return
    rows = []
    for p in sorted(results_dir.glob("*.json")):
        if p.name == "index.json":
            continue
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        rows.append({
            "model_id": d["model"]["id"],
            "model_name": d["model"]["display"],
            "company": d["model"]["family"],
            "run_id": d["run_id"],
            "accuracy": d["metrics"].get("overall_accuracy", 0.0),
            "composite": d["metrics"].get("composite_likeness_score", 0.0),
            "file": p.name,
            "n_samples": d.get("n_completed", d.get("n_samples", 0)),
            "evaluated_at": d.get("completed_at"),
            "cost_usd": d.get("cost", {}).get("total_usd", 0.0),
            "killed": d.get("killed", False),
        })
    rows.sort(key=lambda r: r["composite"], reverse=True)
    index = {
        "benchmark_id": benchmark_id,
        "generated_at": _now(),
        "rows": rows,
        "baselines": [
            {"label": "Random Guess (5-way)", "composite": 0.20},
            {"label": "Always pick E", "composite": 0.50},
        ],
    }
    (results_dir / "index.json").write_text(json.dumps(index, indent=2))
