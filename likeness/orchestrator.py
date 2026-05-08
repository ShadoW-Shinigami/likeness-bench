"""End-to-end dataset build:

  1. Generate a pool of N base faces (text-to-image via NB2).
  2. For each base, generate a "same person, different photo" variant (NB2 edit).
  3. Compose K MCQ samples from the pool — half Type A (correct present), half Type B.
  4. Upload every image to Azure; record CDN URLs in meta.json.
  5. Write per-sample provenance.json.
  6. Emit dataset.json + benchmarks/<id>/manifest.json.
"""
from __future__ import annotations

import json
import random
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import (
    BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeElapsedColumn,
)

from .composition.mcq_builder import PoolEntry, build_sample
from .generation.nb2_client import (
    GenLedger, edit_with_reference, text_to_image,
)
from .generation.prompts import make_base_prompt, make_identity_variant_prompt

console = Console()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _upload_image(local_path: Path, blob_name: str) -> str:
    from bench.utils.storage import upload_file_to_storage as upload_file_to_azure  # late import
    return upload_file_to_azure(local_path=local_path, blob_name=blob_name,
                                content_type="image/png")


def build_dataset(
    *,
    output_dir: Path,
    benchmark_id: str = "likeness_v1",
    n_pool: int = 30,
    n_samples: int = 20,
    type_a_ratio: float = 0.5,
    seed: int = 42,
    max_cost_usd: float = 25.0,
    upload_to_azure: bool = True,
    resume: bool = True,
) -> dict:
    """Build the dataset end-to-end.

    Args:
      output_dir: e.g. /repo/dataset/v1
      benchmark_id: identifier used by the eval engine
      n_pool: number of distinct identities to generate
      n_samples: number of MCQ items to compose
      type_a_ratio: fraction of items that are Type A
      seed: rng seed
      max_cost_usd: hard budget cap on Fal calls
      upload_to_azure: if True, also upload every image to Azure
      resume: skip any pool entry / sample that already exists on disk

    Returns:
      {"pool_size": int, "n_samples": int, "cost_usd": float, "manifest_path": Path}
    """
    rng = random.Random(seed)
    output_dir = Path(output_dir)
    pool_dir = output_dir / "pool"
    samples_dir = output_dir / "samples"
    pool_dir.mkdir(parents=True, exist_ok=True)
    samples_dir.mkdir(parents=True, exist_ok=True)

    ledger = GenLedger(max_usd=max_cost_usd)
    pool: list[PoolEntry] = []
    pool_index_path = output_dir / "pool" / "index.json"
    pool_index: dict[str, dict] = {}
    if resume and pool_index_path.exists():
        pool_index = json.loads(pool_index_path.read_text())

    # ---------- Step 1: generate pool ----------
    console.rule("[bold cyan]Step 1: Generating face pool")
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(), MofNCompleteColumn(), TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Pool", total=n_pool)
        for i in range(1, n_pool + 1):
            person_id = f"p_{i:04d}"
            entry_dir = pool_dir / person_id
            entry_dir.mkdir(parents=True, exist_ok=True)
            base_path = entry_dir / "base.png"
            variant_path = entry_dir / "variant.png"

            existing = pool_index.get(person_id)
            if (resume and base_path.exists() and existing
                    and existing.get("base_provenance")):
                base_prov = existing["base_provenance"]
                cdn_base = existing.get("cdn_base")
                demo = existing.get("demographics", {})
            else:
                bp = make_base_prompt(seed * 1000 + i)
                base_prov = text_to_image(
                    prompt=bp["prompt"], out_path=base_path, ledger=ledger,
                    seed=seed * 1000 + i,
                )
                base_prov["_kind"] = "base"
                demo = bp["demographics"]
                cdn_base = None
                if upload_to_azure:
                    cdn_base = _upload_image(base_path, f"likeness/{benchmark_id}/pool/{person_id}/base.png")

            # Variant for Type A. We generate one for every entry — cheap insurance.
            if (resume and variant_path.exists() and existing
                    and existing.get("variant_provenance")):
                variant_prov = existing["variant_provenance"]
                cdn_variant = existing.get("cdn_variant")
            else:
                try:
                    variant_prov = edit_with_reference(
                        prompt=make_identity_variant_prompt(i),
                        reference_image_paths=[base_path],
                        out_path=variant_path, ledger=ledger,
                    )
                    variant_prov["_kind"] = "variant"
                    cdn_variant = None
                    if upload_to_azure:
                        cdn_variant = _upload_image(
                            variant_path, f"likeness/{benchmark_id}/pool/{person_id}/variant.png"
                        )
                except Exception as e:
                    console.log(f"[yellow]Variant gen failed for {person_id}: {e}[/yellow]")
                    variant_prov = None
                    cdn_variant = None
                    if variant_path.exists():
                        variant_path.unlink()

            entry = PoolEntry(
                person_id=person_id,
                base_path=base_path,
                variant_path=variant_path if variant_path.exists() else None,
                cdn_base=cdn_base,
                cdn_variant=cdn_variant,
                demographics=demo,
                base_provenance=base_prov,
                variant_provenance=variant_prov,
            )
            pool.append(entry)
            pool_index[person_id] = {
                "base_provenance": base_prov,
                "variant_provenance": variant_prov,
                "cdn_base": cdn_base,
                "cdn_variant": cdn_variant,
                "demographics": demo,
            }
            pool_index_path.write_text(json.dumps(pool_index, indent=2))
            progress.update(task, advance=1)
            console.log(
                f"pool {person_id}: total spent ${ledger.total_usd:.2f} / "
                f"{ledger.n_calls} calls"
            )

    if not pool:
        raise RuntimeError("No pool entries generated.")

    # ---------- Step 2: compose samples ----------
    console.rule("[bold cyan]Step 2: Composing MCQ samples")
    sample_ids: list[str] = []
    n_type_a = int(round(n_samples * type_a_ratio))

    type_a_indices = [i for i, e in enumerate(pool) if e.variant_path is not None][:n_type_a]
    if len(type_a_indices) < n_type_a:
        console.log(f"[yellow]Only {len(type_a_indices)} Type A items possible (need {n_type_a})[/yellow]")
        n_type_a = len(type_a_indices)

    n_type_b = n_samples - n_type_a
    type_b_indices = list(range(len(pool)))
    rng.shuffle(type_b_indices)
    type_b_indices = type_b_indices[:n_type_b]

    schedule = (
        [(idx, True) for idx in type_a_indices] +
        [(idx, False) for idx in type_b_indices]
    )
    rng.shuffle(schedule)

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(), MofNCompleteColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Samples", total=len(schedule))
        for n, (target_idx, is_type_a) in enumerate(schedule, start=1):
            sid = f"lk_v1_{n:05d}"
            sample_dir = samples_dir / sid
            sample_dir.mkdir(parents=True, exist_ok=True)

            if resume and (sample_dir / "meta.json").exists() and (sample_dir / "base.png").exists():
                sample_ids.append(sid)
                progress.update(task, advance=1)
                continue

            meta = build_sample(
                sample_id=sid, pool=pool, target_index=target_idx,
                is_type_a=is_type_a, rng=rng,
            )
            if meta is None:
                console.log(f"[yellow]skip {sid}: pool too small[/yellow]")
                progress.update(task, advance=1)
                continue

            # Copy local image files into the sample dir
            base_local = Path(meta.pop("_local_base_image"))
            shutil.copy2(base_local, sample_dir / "base.png")
            for letter in ("A", "B", "C", "D"):
                opt = meta["options"][letter]
                local = Path(opt.pop("_local_image"))
                shutil.copy2(local, sample_dir / opt["image"])

            # Upload sample-level images (so the eval engine can serve via Azure too)
            if upload_to_azure:
                base_cdn = _upload_image(
                    sample_dir / "base.png",
                    f"likeness/{meta_benchmark_blob(sid)}/base.png",
                )
                meta["base_cdn_url"] = base_cdn
                for letter in ("A", "B", "C", "D"):
                    opt = meta["options"][letter]
                    cdn = _upload_image(
                        sample_dir / opt["image"],
                        f"likeness/{meta_benchmark_blob(sid)}/{opt['image']}",
                    )
                    opt["cdn_url"] = cdn

            (sample_dir / "meta.json").write_text(json.dumps(meta, indent=2))
            (sample_dir / "provenance.json").write_text(json.dumps({
                "built_at": _now(), "type_a": is_type_a,
                "target_person_id": pool[target_idx].person_id,
                "ledger_at_build": {"total_usd": ledger.total_usd, "n_calls": ledger.n_calls},
            }, indent=2))
            sample_ids.append(sid)
            progress.update(task, advance=1)

    # ---------- Step 3: emit manifests ----------
    console.rule("[bold cyan]Step 3: Writing manifests")
    dataset_json = {
        "version": "v1",
        "created_at": _now(),
        "n_samples": len(sample_ids),
        "license": "CC-BY-4.0",
        "license_notes": (
            "All faces are NB2-generated fictional persons. SynthID watermarked."
        ),
        "source_breakdown": {"nb2": {"samples": len(sample_ids), "license": "CC-BY-4.0"}},
        "generator_models": {
            "nano_banana_2": {"endpoint": "fal-ai/nano-banana-2", "snapshot": "2026"},
            "embedding": {"method": "phash16"},
        },
        "schema_version": "1.0.0",
    }
    (output_dir / "dataset.json").write_text(json.dumps(dataset_json, indent=2))

    bm_dir = output_dir.parent.parent / "benchmarks" / benchmark_id
    bm_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "benchmark_id": benchmark_id,
        "title": "Likeness v1",
        "description": (
            "MCQ likeness benchmark. 5-option MCQ with 4 face candidates + "
            "'none of the above'. ~50% items are Type A, ~50% Type B."
        ),
        "task_type": "mcq_likeness",
        "sample_ids": sample_ids,
        "schema_version": "1.0.0",
    }
    manifest_path = bm_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    console.print(
        f"\n[bold green]Dataset built[/bold green] — {len(sample_ids)} samples, "
        f"${ledger.total_usd:.2f} spent across {ledger.n_calls} Fal calls. "
        f"Manifest: [cyan]{manifest_path}[/cyan]"
    )
    return {
        "pool_size": len(pool),
        "n_samples": len(sample_ids),
        "cost_usd": ledger.total_usd,
        "n_calls": ledger.n_calls,
        "manifest_path": str(manifest_path),
    }


def meta_benchmark_blob(sample_id: str) -> str:
    """Azure blob path prefix for a sample. Keeps the URL hierarchy readable."""
    return f"likeness_v1/samples/{sample_id}"
