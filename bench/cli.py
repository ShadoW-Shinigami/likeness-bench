"""bench CLI — Typer-based, single entry point."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import providers as _providers  # noqa: F401
from . import tasks as _tasks  # noqa: F401
from .config import load_config
from .logging import configure_logging
from .runner import control as run_control
from .runner import pipeline

app = typer.Typer(help="Likeness Detector benchmark CLI", no_args_is_help=True)
runs_app = typer.Typer(help="Manage running evaluations")
app.add_typer(runs_app, name="runs")
console = Console()


def _slice_arg(spec: str | None) -> tuple[int, int] | None:
    if not spec:
        return None
    if ":" not in spec:
        n = int(spec)
        return (0, n)
    lo, hi = spec.split(":", 1)
    return (int(lo or 0), int(hi or 10**9))


@app.command()
def list_models() -> None:
    """List models registered in bench.toml."""
    cfg = load_config()
    table = Table(title="Models")
    table.add_column("key")
    table.add_column("display")
    table.add_column("provider")
    table.add_column("model_id")
    table.add_column("$/1M in")
    table.add_column("$/1M out")
    for k, m in cfg.models.items():
        table.add_row(k, m.display, m.provider, m.model_id,
                      f"{m.price_per_1m_input:.2f}", f"{m.price_per_1m_output:.2f}")
    console.print(table)


@app.command()
def list_benchmarks() -> None:
    cfg = load_config()
    table = Table(title="Benchmarks")
    table.add_column("id")
    table.add_column("title")
    table.add_column("samples")
    table.add_column("location")
    for d in (cfg.benchmarks_dir(), cfg.repo_root / "tests" / "fixtures"):
        if not d.exists():
            continue
        for sub in sorted(d.iterdir()):
            mp = sub / "manifest.json"
            if mp.exists():
                m = json.loads(mp.read_text())
                table.add_row(
                    m.get("benchmark_id", sub.name),
                    m.get("title", ""),
                    str(len(m.get("sample_ids", []))),
                    str(sub.relative_to(cfg.repo_root)),
                )
    console.print(table)


@app.command()
def validate_dataset(path: Path) -> None:
    """Validate every sample's meta.json + image files exist."""
    cfg = load_config()
    manifest = json.loads((path / "manifest.json").read_text())
    samples_root = path / "samples"
    if not samples_root.exists():
        # Maybe path is benchmarks/<id>; samples may be in dataset/
        from .runner.dataset import resolve_samples_root
        samples_root = resolve_samples_root(cfg.repo_root, manifest["benchmark_id"])
    fails = 0
    from .models import SampleMeta
    for sid in manifest["sample_ids"]:
        sd = samples_root / sid
        meta_path = sd / "meta.json"
        if not meta_path.exists():
            console.print(f"[red]missing meta.json[/red]: {sid}")
            fails += 1
            continue
        try:
            meta = SampleMeta.model_validate_json(meta_path.read_text())
        except Exception as e:
            console.print(f"[red]bad schema[/red] {sid}: {e}")
            fails += 1
            continue
        if not (sd / meta.base_image).exists():
            console.print(f"[red]missing base[/red] {sid}")
            fails += 1
        for letter in ("A", "B", "C", "D"):
            opt = meta.options.get(letter)
            if opt and opt.image and not (sd / opt.image).exists():
                console.print(f"[red]missing option {letter}[/red] {sid}")
                fails += 1
    if fails:
        console.print(f"[red]{fails} validation errors[/red]")
        raise typer.Exit(1)
    console.print(f"[green]OK[/green] — {len(manifest['sample_ids'])} samples valid")


@app.command()
def eval(
    model: str = typer.Option(..., "--model", "-m", help="Model key from bench.toml"),
    benchmark: str | None = typer.Option(None, "--benchmark", "-b"),
    samples: str | None = typer.Option(None, "--samples", help="lo:hi slice"),
    concurrency: int | None = typer.Option(None),
    max_cost_usd: float | None = typer.Option(None, "--max-cost-usd"),
    resume: bool = typer.Option(False, "--resume"),
) -> None:
    """Run a model over a benchmark. Writes results/<benchmark>/<model>__<run>.json."""
    cfg = load_config()
    bench_id = benchmark or cfg.engine.default_benchmark
    configure_logging(cfg.engine.log_level)

    async def go() -> dict:
        return await pipeline.run_evaluation(
            cfg=cfg,
            model_key=model,
            benchmark_id=bench_id,
            sample_slice=_slice_arg(samples),
            concurrency=concurrency,
            max_cost_usd=max_cost_usd,
            resume=resume,
        )

    out = asyncio.run(go())
    console.print(f"[green]done[/green] — accuracy={out['metrics'].get('overall_accuracy', 0):.3f} "
                  f"composite={out['metrics'].get('composite_likeness_score', 0):.3f} "
                  f"cost=${out['cost'].get('total_usd', 0):.2f}")


@app.command()
def self_check() -> None:
    """Run mock provider over the tiny fixture; exit nonzero on failure."""
    cfg = load_config()
    configure_logging("INFO")

    async def go() -> dict:
        return await pipeline.run_evaluation(
            cfg=cfg,
            model_key="mock",
            benchmark_id="tiny_benchmark",
            resume=False,
        )

    try:
        out = asyncio.run(go())
    except Exception as e:
        console.print(f"[red]self-check failed[/red]: {e}")
        raise typer.Exit(1)
    if out.get("n_completed", 0) == 0:
        console.print("[red]self-check: no samples completed[/red]")
        raise typer.Exit(1)
    console.print(f"[green]self-check OK[/green] — {out['n_completed']}/{out['n_samples']} "
                  f"accuracy={out['metrics'].get('overall_accuracy', 0):.3f}")


@app.command(name="refresh-showcase")
def refresh_showcase() -> None:
    """Rebuild showcase.html (re-uploads any new JPEGs, regenerates the page)."""
    cfg = load_config()
    script = cfg.repo_root / "scripts" / "build_showcase.py"
    if not script.exists():
        console.print(f"[red]missing {script}[/red]")
        raise typer.Exit(1)
    import subprocess
    r = subprocess.run([sys.executable, str(script)], cwd=cfg.repo_root)
    if r.returncode != 0:
        raise typer.Exit(r.returncode)


@app.command(name="eval-all")
def eval_all(
    benchmark: str | None = typer.Option(None, "--benchmark", "-b"),
    skip_done: bool = typer.Option(True, "--skip-done/--force",
                                   help="Skip models that already have a result for this benchmark"),
    only: list[str] | None = typer.Option(None, "--only",
                                          help="Only run these model keys (repeatable)"),
    concurrency: int = typer.Option(3),
    max_cost_usd: float = typer.Option(4.0, "--max-cost-usd"),
) -> None:
    """Run every configured model against a benchmark, sequentially."""
    cfg = load_config()
    bench_id = benchmark or cfg.engine.default_benchmark
    configure_logging("WARNING")

    # determine which models to run
    targets = list(only) if only else list(cfg.models.keys())
    targets = [m for m in targets if m in cfg.models]
    if skip_done:
        results_dir = cfg.results_dir_path() / bench_id
        if results_dir.exists():
            seen = {p.name.split("__", 1)[0] for p in results_dir.glob("*__*.json")}
            targets = [m for m in targets if m not in seen]
            if seen:
                console.print(f"[dim]skipping {sorted(seen)} — already have results[/dim]")
    if not targets:
        console.print("[yellow]nothing to run[/yellow]")
        return

    console.print(f"[bold]Will run {len(targets)} models against {bench_id}:[/bold] {', '.join(targets)}")
    rows = []
    for m in targets:
        console.rule(f"[bold cyan]{m}[/bold cyan]")
        try:
            out = asyncio.run(pipeline.run_evaluation(
                cfg=cfg, model_key=m, benchmark_id=bench_id,
                concurrency=concurrency, max_cost_usd=max_cost_usd, resume=False,
            ))
            metrics = out.get("metrics", {})
            rows.append({"model": m,
                         "accuracy": metrics.get("overall_accuracy", 0),
                         "composite": metrics.get("composite_likeness_score", 0),
                         "cost_usd": out.get("cost", {}).get("total_usd", 0)})
            console.print(
                f"[green]{m}[/green] acc={metrics.get('overall_accuracy', 0):.3f} "
                f"composite={metrics.get('composite_likeness_score', 0):.3f}"
            )
        except Exception as e:
            console.print(f"[red]{m} failed:[/red] {e}")

    table = Table(title=f"eval-all summary ({bench_id})")
    for col in ("model", "accuracy", "composite", "cost_usd"):
        table.add_column(col)
    for r in rows:
        table.add_row(r["model"], f"{r['accuracy']:.3f}",
                      f"{r['composite']:.3f}", f"${r['cost_usd']:.2f}")
    console.print(table)


@app.command()
def refresh(
    benchmark: str | None = typer.Option(None, "--benchmark", "-b"),
    only: list[str] | None = typer.Option(None, "--only"),
    skip_done: bool = typer.Option(True, "--skip-done/--force"),
    concurrency: int = typer.Option(3),
    max_cost_usd: float = typer.Option(4.0, "--max-cost-usd"),
    no_showcase: bool = typer.Option(False, "--no-showcase"),
) -> None:
    """One-shot: run any unevaluated models AND rebuild showcase.html."""
    eval_all(benchmark=benchmark, skip_done=skip_done, only=only,
             concurrency=concurrency, max_cost_usd=max_cost_usd)
    if not no_showcase:
        console.rule("[bold cyan]rebuilding showcase[/bold cyan]")
        refresh_showcase()


@app.command(name="grow-dataset")
def grow_dataset(
    benchmark: str = typer.Option("likeness_v2", "--benchmark", "-b"),
    n_samples: int = typer.Option(..., "--n-samples", "-n",
                                  help="TARGET sample count (existing samples are kept)"),
    seed: int = typer.Option(42),
    max_nb2_usd: float = typer.Option(25.0, "--max-nb2-usd"),
    max_gpt_image_usd: float = typer.Option(25.0, "--max-gpt-image-usd"),
    fal_concurrency: int = typer.Option(5, "--fal-concurrency"),
    no_upload: bool = typer.Option(False, "--no-upload"),
) -> None:
    """Extend an existing dataset to a new total sample count.

    Resumable: existing pool entries + lookalikes + action shots are kept.
    """
    cfg = load_config()
    out_dir = cfg.repo_root / "dataset" / benchmark
    from likeness.orchestrator_v2 import build_dataset_v2
    out = build_dataset_v2(
        output_dir=out_dir,
        benchmark_id=benchmark,
        n_samples=n_samples,
        seed=seed,
        max_nb2_usd=max_nb2_usd,
        max_gpt_image_usd=max_gpt_image_usd,
        upload_to_azure=not no_upload,
        resume=True,
        fal_concurrency=fal_concurrency,
    )
    console.print(f"[green]grew {benchmark} → {out['n_samples']} samples[/green]")


@app.command()
def serve(
    host: str | None = typer.Option(None),
    port: int | None = typer.Option(None),
    reload: bool = typer.Option(False, "--reload"),
) -> None:
    """Start the FastAPI server (serves /api/* AND the built React frontend)."""
    import uvicorn
    cfg = load_config()
    h = host or cfg.server.host
    p = port or cfg.server.port
    web_dist = cfg.web_dist_path()
    if not web_dist.exists():
        console.print(
            f"[yellow]Note:[/yellow] {web_dist} does not exist yet. "
            "Run `make build` (or `cd web && npm run build`) to populate it."
        )
    console.print(f"[bold green]bench server[/bold green] on http://{h}:{p}")
    uvicorn.run("bench.server.app:app", host=h, port=p, reload=reload)


# --- run management subcommands ---

@runs_app.command("list")
def runs_list() -> None:
    cfg = load_config()
    states = run_control.list_states(cfg.runs_dir_path())
    table = Table(title="Runs")
    table.add_column("run_id"); table.add_column("status"); table.add_column("model")
    table.add_column("benchmark"); table.add_column("progress"); table.add_column("started")
    for s in states:
        table.add_row(s.run_id, s.status, s.model_id, s.benchmark_id,
                      f"{s.completed}/{s.n_samples}", s.started_at)
    console.print(table)


@runs_app.command("show")
def runs_show(run_id: str) -> None:
    cfg = load_config()
    s = run_control.read_state(cfg.runs_dir_path(), run_id)
    if not s:
        raise typer.Exit(1)
    console.print_json(s.model_dump_json())


@runs_app.command("pause")
def runs_pause(run_id: str) -> None:
    cfg = load_config()
    if run_control.request_action(cfg.runs_dir_path(), run_id, "pause"):
        console.print(f"[yellow]pause requested[/yellow] {run_id}")
    else:
        console.print(f"[red]no such run[/red] {run_id}")
        raise typer.Exit(1)


@runs_app.command("resume")
def runs_resume(run_id: str) -> None:
    cfg = load_config()
    if run_control.request_action(cfg.runs_dir_path(), run_id, "resume"):
        console.print(f"[green]resume requested[/green] {run_id}")
    else:
        console.print(f"[red]no such run[/red] {run_id}")
        raise typer.Exit(1)


@runs_app.command("kill")
def runs_kill(run_id: str) -> None:
    cfg = load_config()
    if run_control.request_action(cfg.runs_dir_path(), run_id, "kill"):
        console.print(f"[red]kill requested[/red] {run_id}")
    else:
        console.print(f"[red]no such run[/red] {run_id}")
        raise typer.Exit(1)


@runs_app.command("continue")
def runs_continue(run_id: str) -> None:
    """Restart an interrupted run (skips completed samples)."""
    cfg = load_config()
    s = run_control.read_state(cfg.runs_dir_path(), run_id)
    if not s:
        raise typer.Exit(1)
    configure_logging(cfg.engine.log_level)

    async def go() -> dict:
        return await pipeline.run_evaluation(
            cfg=cfg,
            model_key=s.model_id,
            benchmark_id=s.benchmark_id,
            resume=True,
            run_id=run_id,
        )
    out = asyncio.run(go())
    console.print(f"[green]continued[/green] accuracy={out['metrics'].get('overall_accuracy', 0):.3f}")


if __name__ == "__main__":
    app()
