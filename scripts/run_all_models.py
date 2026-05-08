"""Sequentially run a benchmark against multiple models.

Usage:
    python scripts/run_all_models.py --benchmark likeness_v2 \\
        --models gpt-5_5 gemini-3-flash seed-2-lite seed-1-6 claude-opus-4-7 claude-opus-4-6 \\
        --concurrency 4 --max-cost-usd 5
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
load_dotenv(REPO / ".env", override=False)

from rich.console import Console  # noqa: E402

from bench import providers as _providers  # noqa: F401, E402
from bench import tasks as _tasks  # noqa: F401, E402
from bench.config import load_config  # noqa: E402
from bench.logging import configure_logging  # noqa: E402
from bench.runner import pipeline  # noqa: E402

console = Console()


async def run_one(cfg, model: str, benchmark: str, concurrency: int, max_cost: float) -> dict:
    return await pipeline.run_evaluation(
        cfg=cfg, model_key=model, benchmark_id=benchmark,
        concurrency=concurrency, max_cost_usd=max_cost, resume=False,
    )


async def main_async(args) -> int:
    cfg = load_config()
    configure_logging("WARNING")  # quiet the per-call HTTP logs
    rows = []
    for m in args.models:
        if m not in cfg.models:
            console.print(f"[red]model {m} not in bench.toml[/red]")
            continue
        console.rule(f"[bold cyan]{m}[/bold cyan]")
        try:
            out = await run_one(cfg, m, args.benchmark, args.concurrency, args.max_cost_usd)
            rows.append({
                "model": m,
                "n": out["n_completed"],
                "accuracy": out["metrics"]["overall_accuracy"],
                "composite": out["metrics"]["composite_likeness_score"],
                "cost_usd": out["cost"]["total_usd"],
                "p95_ms": out["latency"]["p95_ms"],
            })
            console.print(
                f"[green]{m}[/green] "
                f"acc={out['metrics']['overall_accuracy']:.3f} "
                f"composite={out['metrics']['composite_likeness_score']:.3f} "
                f"cost=${out['cost']['total_usd']:.2f}"
            )
        except Exception as e:
            console.print(f"[red]{m} failed:[/red] {e}")

    console.rule("[bold]Summary[/bold]")
    console.print(rows)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark", default="likeness_v2")
    ap.add_argument("--models", nargs="+", default=[
        "gemini-3-flash", "claude-opus-4-7", "claude-opus-4-6",
        "gpt-5_5", "seed-2-lite", "seed-1-6",
    ])
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--max-cost-usd", type=float, default=10.0)
    args = ap.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
