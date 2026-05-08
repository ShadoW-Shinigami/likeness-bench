"""V2 dataset build — every option in a sample shows the SAME action scenario.

Per-sample anatomy:
  - Pick one action scenario for the sample
  - Generate base portrait (NB2 t2i) and vision-describe it (Gemini 2.5 Flash via OR-on-Fal)
  - Type A (correct present, ~50%):
      * 1 correct option: GPT-Image-2 Edit on the base, putting the subject in the action scenario
      * 3 distractor options: NB2 t2i with description-derived prompts for similar-but-different
        people performing the SAME action
  - Type B (correct absent, ~50%):
      * 4 distractor options: NB2 t2i, four different but similar-vibe people, all doing the same action

All Fal calls share a single global semaphore (default cap = 5 in flight).
Build runs in PHASES (bases → lookalikes → actions → compose) so the asyncio
scheduler never has more than `fal_concurrency` per-sample chains alive at once.
"""
from __future__ import annotations

import asyncio
import json
import random
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import (
    BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeElapsedColumn,
)

from .composition.mcq_builder import bucket_tier
from .embeddings.phash_similarity import hamming_similarity, phash
from .generation.gpt_image2_edit import (
    ACTION_SCENARIOS, GptImageLedger, edit_action_shot,
)
from .generation.nb2_client import GenLedger, text_to_image
from .generation.openrouter_vision import (
    derive_lookalike_prompt, describe_face, verify_same_person,
)

console = Console()
_FILE_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _upload_image(local_path: Path, blob_name: str) -> str:
    from bench.utils.storage import upload_file_to_storage as upload_file_to_azure
    return upload_file_to_azure(local_path=local_path, blob_name=blob_name,
                                content_type="image/png")


def _atomic_write_json(path: Path, data: dict) -> None:
    with _FILE_LOCK:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str))
        tmp.replace(path)


def _scenario_for(seed: int, i: int) -> str:
    return ACTION_SCENARIOS[(seed * 31 + i) % len(ACTION_SCENARIOS)]


# --------------------------------------------------------------------------- #
# Stage 1: base portrait + vision-describe                                    #
# --------------------------------------------------------------------------- #

async def _do_base_describe(
    *, sid: str, i: int, seed: int, work_dir: Path, benchmark_id: str,
    upload: bool, bases: dict, pool_index_path: Path, nb2_ledger: GenLedger,
    fal_sem: asyncio.Semaphore, progress, task_id,
) -> None:
    info = bases.get(sid, {"sample_id": sid})
    info["action_scenario"] = _scenario_for(seed, i)
    if (info.get("base_path") and Path(info["base_path"]).exists()
            and info.get("description")):
        progress.update(task_id, advance=1)
        bases[sid] = info
        _atomic_write_json(pool_index_path, bases)
        return

    sd = work_dir / sid
    sd.mkdir(parents=True, exist_ok=True)
    base_path = sd / "base.png"
    from .generation.prompts import make_base_prompt
    bp = make_base_prompt(seed * 10000 + i)
    try:
        async with fal_sem:
            base_prov = await asyncio.to_thread(
                text_to_image, prompt=bp["prompt"], out_path=base_path,
                ledger=nb2_ledger, seed=seed * 10000 + i,
            )
    except Exception as e:
        console.log(f"[red]base gen failed[/red] {sid}: {e}")
        progress.update(task_id, advance=1)
        return

    base_url = ""
    if upload:
        try:
            base_url = await asyncio.to_thread(
                _upload_image, base_path,
                f"likeness/{benchmark_id}/work/{sid}/base.png",
            )
        except Exception as e:
            console.log(f"[yellow]base upload failed {sid}: {e}[/yellow]")
    try:
        async with fal_sem:
            desc = await asyncio.to_thread(describe_face, base_url or "")
    except Exception as e:
        console.log(f"[yellow]describe failed {sid}: {e}[/yellow]")
        desc = {"description": "", "anchor": "", "cost_usd": 0.0}

    info.update({
        "base_path": str(base_path), "base_url": base_url,
        "demographics": bp["demographics"], "base_provenance": base_prov,
        "description": desc.get("description", ""),
        "anchor": desc.get("anchor", ""),
        "describe_cost": desc.get("cost_usd", 0.0),
    })
    bases[sid] = info
    _atomic_write_json(pool_index_path, bases)
    progress.update(task_id, advance=1)
    console.log(
        f"[green]{sid}[/green] base+describe · NB2 ${nb2_ledger.total_usd:.2f} ({nb2_ledger.n_calls})"
    )


# --------------------------------------------------------------------------- #
# Stage 2: lookalike action shots                                             #
# --------------------------------------------------------------------------- #

async def _do_lookalikes(
    *, sid: str, n_needed: int, seed: int, work_dir: Path, benchmark_id: str,
    upload: bool, bases: dict, pool_index_path: Path, nb2_ledger: GenLedger,
    fal_sem: asyncio.Semaphore, progress, task_id,
) -> None:
    info = bases.get(sid)
    if info is None or not info.get("description"):
        progress.update(task_id, advance=1)
        return
    looks: list[dict] = info.get("lookalikes", [])
    sd = work_dir / sid
    action_scenario = info.get("action_scenario", "")
    if not action_scenario:
        action_scenario = _scenario_for(seed, 0)
        info["action_scenario"] = action_scenario

    while len(looks) < n_needed:
        k = len(looks)
        lookalike_path = sd / f"lookalike_{k}.png"
        try:
            async with fal_sem:
                derived = await asyncio.to_thread(
                    derive_lookalike_prompt, info["description"],
                    action_scenario, seed=seed * 100 + k * 13 + (hash(sid) % 1000),
                )
        except Exception as e:
            console.log(f"[yellow]derive {sid}.{k} failed: {e}[/yellow]")
            break
        try:
            async with fal_sem:
                nb2_prov = await asyncio.to_thread(
                    text_to_image, prompt=derived["prompt"], out_path=lookalike_path,
                    ledger=nb2_ledger,
                    seed=seed * 100 + k * 17 + (hash(sid) % 1000),
                )
        except Exception as e:
            console.log(f"[yellow]lookalike {sid}.{k} t2i failed: {e}[/yellow]")
            break
        cdn = ""
        if upload:
            try:
                cdn = await asyncio.to_thread(
                    _upload_image, lookalike_path,
                    f"likeness/{benchmark_id}/work/{sid}/lookalike_{k}.png",
                )
            except Exception as e:
                console.log(f"[yellow]lookalike upload {sid}.{k} failed: {e}[/yellow]")
        looks.append({
            "path": str(lookalike_path), "url": cdn,
            "prompt": derived["prompt"],
            "variation_hint": derived.get("variation_hint"),
            "action_scenario": action_scenario,
            "nb2_provenance": nb2_prov,
        })
        info["lookalikes"] = looks
        bases[sid] = info
        _atomic_write_json(pool_index_path, bases)

    progress.update(task_id, advance=1)
    console.log(f"[green]{sid}[/green] {len(looks)} lookalikes done")


# --------------------------------------------------------------------------- #
# Stage 3: GPT-Image-2 action shot (Type A only)                              #
# --------------------------------------------------------------------------- #

async def _do_action_shot(
    *, sid: str, i: int, seed: int, work_dir: Path, benchmark_id: str,
    upload: bool, bases: dict, pool_index_path: Path,
    gpt_ledger: GptImageLedger, fal_sem: asyncio.Semaphore,
    identity_verify_attempts: int, progress, task_id,
) -> None:
    info = bases.get(sid)
    if info is None:
        progress.update(task_id, advance=1)
        return
    if info.get("action_shot") and Path(info["action_shot"].get("path", "")).exists():
        progress.update(task_id, advance=1)
        return
    base_url = info.get("base_url") or ""
    if not base_url:
        console.log(f"[yellow]skip action {sid}: no base_url[/yellow]")
        progress.update(task_id, advance=1)
        return

    sd = work_dir / sid
    action_scenario = info.get("action_scenario", "")
    action_idx = ACTION_SCENARIOS.index(action_scenario) if action_scenario in ACTION_SCENARIOS else 0
    best: Optional[dict] = None
    last: Optional[dict] = None

    for attempt in range(max(1, identity_verify_attempts)):
        action_path = sd / f"action_attempt_{attempt}.png"
        try:
            async with fal_sem:
                prov = await asyncio.to_thread(
                    edit_action_shot,
                    reference_image_url=base_url,
                    out_path=action_path,
                    ledger=gpt_ledger,
                    scenario_seed=action_idx,
                )
        except Exception as e:
            console.log(f"[red]action gen failed[/red] {sid} attempt {attempt}: {e}")
            continue
        action_url = ""
        if upload:
            try:
                action_url = await asyncio.to_thread(
                    _upload_image, action_path,
                    f"likeness/{benchmark_id}/work/{sid}/action_attempt_{attempt}.png",
                )
            except Exception as e:
                console.log(f"[yellow]action upload failed {sid}: {e}[/yellow]")
        try:
            async with fal_sem:
                verdict = (
                    await asyncio.to_thread(verify_same_person, base_url, action_url)
                    if action_url else
                    {"same": True, "reason": "verify_skipped_no_url"}
                )
        except Exception as e:
            console.log(f"[yellow]verify failed {sid}: {e}[/yellow]")
            verdict = {"same": True, "reason": f"verify_failed: {e}"}
        console.log(
            f"  {sid} action attempt {attempt}: same={verdict.get('same')} — "
            f"{str(verdict.get('reason', ''))[:80]}"
        )
        last = {
            "path": str(action_path), "url": action_url,
            "provenance": prov, "verify": verdict, "attempt": attempt,
            "action_scenario": action_scenario,
        }
        if verdict.get("same"):
            best = last
            break

    if best is None and last is not None:
        last["verify"] = {**last.get("verify", {}), "fallback_after_retries": True}
        best = last
    if best is not None:
        info["action_shot"] = best
        bases[sid] = info
        _atomic_write_json(pool_index_path, bases)
    progress.update(task_id, advance=1)
    console.log(f"[green]{sid}[/green] action shot done · GPT-Image-2 ${gpt_ledger.total_usd:.2f}")


# --------------------------------------------------------------------------- #
# Stage 4: compose                                                            #
# --------------------------------------------------------------------------- #

def _compose_one_sample(
    *, sid: str, is_type_a: bool, seed: int, i: int,
    bases: dict, samples_dir: Path, benchmark_id: str, upload: bool,
) -> bool:
    info = bases.get(sid)
    if not info:
        return False
    sample_dir = samples_dir / sid
    sample_dir.mkdir(parents=True, exist_ok=True)
    if (sample_dir / "meta.json").exists() and (sample_dir / "base.png").exists():
        return True

    looks = info.get("lookalikes", [])
    n_needed = 3 if is_type_a else 4
    if len(looks) < n_needed:
        console.log(f"[red]skip {sid}: only {len(looks)}/{n_needed} lookalikes[/red]")
        return False
    if is_type_a and not (info.get("action_shot")
                          and Path(info["action_shot"].get("path", "")).exists()):
        console.log(f"[red]skip Type A {sid}: no action shot[/red]")
        return False

    shutil.copy2(info["base_path"], sample_dir / "base.png")
    base_hash = phash(sample_dir / "base.png")
    rng = random.Random(seed * 777 + i)
    letters = ["A", "B", "C", "D"]
    rng.shuffle(letters)

    slots: list[dict] = []
    if is_type_a:
        action = info["action_shot"]
        slots.append({
            "kind": "true_match",
            "src_path": Path(action["path"]),
            "src_url": action.get("url"),
            "source": "gpt_image_2_edit",
            "person_id": sid + "_self",
            "generated_by": "openai/gpt-image-2/edit",
            "scenario": info.get("action_scenario"),
        })
    for li, look in enumerate(looks[:n_needed]):
        if not Path(look["path"]).exists():
            continue
        slots.append({
            "kind": "distractor",
            "src_path": Path(look["path"]),
            "src_url": look.get("url"),
            "source": "nb2_action_lookalike",
            "person_id": f"{sid}_look_{li}",
            "generated_by": "fal-ai/nano-banana-2",
            "variation_hint": look.get("variation_hint"),
            "scenario": info.get("action_scenario"),
        })
    if len(slots) < 4:
        console.log(f"[red]skip {sid}: only {len(slots)} slots[/red]")
        return False

    rng.shuffle(slots)
    options: dict[str, dict] = {}
    for letter, slot in zip(letters, slots[:4]):
        opt_filename = f"option_{letter.lower()}.png"
        shutil.copy2(slot["src_path"], sample_dir / opt_filename)
        opt_url = ""
        if upload:
            try:
                opt_url = _upload_image(
                    sample_dir / opt_filename,
                    f"likeness/{benchmark_id}/samples/{sid}/{opt_filename}",
                )
            except Exception as e:
                console.log(f"[yellow]opt upload failed {sid}.{letter}: {e}[/yellow]")
        sim = hamming_similarity(base_hash, phash(sample_dir / opt_filename))
        options[letter] = {
            "image": opt_filename,
            "kind": slot["kind"],
            "similarity_tier": (
                bucket_tier(sim) if slot["kind"] != "true_match" else "self"
            ),
            "similarity_cosine": round(sim, 4),
            "source": slot["source"],
            "person_id": slot["person_id"],
            "generated_by": slot.get("generated_by"),
            "scenario": slot.get("scenario"),
            "variation_hint": slot.get("variation_hint"),
            "cdn_url": opt_url,
        }
    options["E"] = {"is_none_of_the_above": True}
    correct_letter = (
        next(L for L, v in options.items() if v.get("kind") == "true_match")
        if is_type_a else "E"
    )

    base_cdn = ""
    if upload:
        try:
            base_cdn = _upload_image(
                sample_dir / "base.png",
                f"likeness/{benchmark_id}/samples/{sid}/base.png",
            )
        except Exception as e:
            console.log(f"[yellow]base upload failed {sid}: {e}[/yellow]")

    meta = {
        "id": sid, "schema_version": "1.0.0", "task_type": "mcq_likeness",
        "subject": {
            "person_id": sid, "real_or_synthetic": "synthetic",
            "license": "CC-BY-4.0 (NB2 + GPT-Image-2 fictional persons)",
            "source": "nb2+gpt-image-2",
        },
        "base_image": "base.png",
        "base_cdn_url": base_cdn,
        "options": options,
        "correct_answer": correct_letter,
        "none_of_the_above_is_correct": (correct_letter == "E"),
        "metadata": {
            "tier": "mixed", "difficulty_split": "medium",
            "type_b": (correct_letter == "E"),
            "preset": "v2_action_scenario",
            "synthid_present": True, "human_reviewed": False,
            "generator_models": ["fal-ai/nano-banana-2", "openai/gpt-image-2/edit"],
            "embedding_model": "phash16",
            "demographic_hint": info.get("demographics", {}),
            "description": info.get("description"),
            "anchor": info.get("anchor"),
            "action_scenario": info.get("action_scenario"),
            "type_a_action_verify": (
                info["action_shot"].get("verify", {}) if is_type_a else None
            ),
        },
    }
    (sample_dir / "meta.json").write_text(json.dumps(meta, indent=2, default=str))
    (sample_dir / "provenance.json").write_text(json.dumps({
        "built_at": _now(), "type_a": is_type_a,
        "action_scenario": info.get("action_scenario"),
        "base": info.get("base_provenance"),
        "action": (info.get("action_shot") or {}).get("provenance"),
        "lookalikes": [l.get("nb2_provenance") for l in looks],
    }, indent=2, default=str))
    return True


# --------------------------------------------------------------------------- #
# Top-level driver                                                            #
# --------------------------------------------------------------------------- #

async def _stage_run(
    name: str, items: list, fn, total: int,
) -> None:
    """Run an iterable of coroutines with rich progress bar."""
    if not items:
        return
    with Progress(
        TextColumn("{task.description}"), BarColumn(),
        MofNCompleteColumn(), TimeElapsedColumn(), console=console,
    ) as progress:
        tid = progress.add_task(name, total=total)
        await asyncio.gather(*[fn(item, progress, tid) for item in items])


async def _build_async(
    *,
    output_dir: Path,
    benchmark_id: str,
    n_samples: int,
    type_a_ratio: float,
    seed: int,
    max_nb2_usd: float,
    max_gpt_image_usd: float,
    upload_to_azure: bool,
    resume: bool,
    identity_verify_attempts: int,
    fal_concurrency: int = 5,
) -> dict:
    rng = random.Random(seed)
    samples_dir = output_dir / "samples"
    work_dir = output_dir / "work"
    samples_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    nb2_ledger = GenLedger(max_usd=max_nb2_usd)
    gpt_ledger = GptImageLedger(max_usd=max_gpt_image_usd)

    n_type_a = int(round(n_samples * type_a_ratio))
    n_type_b = n_samples - n_type_a
    type_assignments = [True] * n_type_a + [False] * n_type_b
    rng.shuffle(type_assignments)
    sample_ids = [f"lk_v2_{i:05d}" for i in range(1, n_samples + 1)]

    bases: dict[str, dict] = {}
    pool_index_path = output_dir / "pool_index.json"
    if resume and pool_index_path.exists():
        bases = json.loads(pool_index_path.read_text())

    fal_sem = asyncio.Semaphore(fal_concurrency)

    console.rule(f"[bold cyan]Building {benchmark_id}: {n_samples} samples "
                 f"(Type A {n_type_a}, Type B {n_type_b}); Fal cap = {fal_concurrency}")

    # ---- Stage 1: bases + descriptions ----
    console.print("[bold]Stage 1[/bold]: base portraits + descriptions")
    indexed = list(zip(range(n_samples), sample_ids, type_assignments))
    todo_base = [(i, sid, is_a) for (i, sid, is_a) in indexed
                 if not (bases.get(sid, {}).get("base_path")
                         and bases.get(sid, {}).get("description"))]
    if todo_base:
        async def _wrap_base(item, prog, tid):
            i, sid, _ = item
            return await _do_base_describe(
                sid=sid, i=i, seed=seed, work_dir=work_dir,
                benchmark_id=benchmark_id, upload=upload_to_azure,
                bases=bases, pool_index_path=pool_index_path,
                nb2_ledger=nb2_ledger, fal_sem=fal_sem,
                progress=prog, task_id=tid,
            )
        await _stage_run("Bases", todo_base, _wrap_base, total=len(todo_base))
    else:
        console.print(f"  [dim]all {n_samples} bases already cached[/dim]")

    # ---- Stage 2: lookalikes ----
    console.print("[bold]Stage 2[/bold]: lookalike action shots (NB2 t2i)")
    todo_looks = [(i, sid, is_a) for (i, sid, is_a) in indexed
                  if len(bases.get(sid, {}).get("lookalikes", [])) < (3 if is_a else 4)]
    if todo_looks:
        async def _wrap_looks(item, prog, tid):
            i, sid, is_a = item
            n_needed = 3 if is_a else 4
            return await _do_lookalikes(
                sid=sid, n_needed=n_needed, seed=seed, work_dir=work_dir,
                benchmark_id=benchmark_id, upload=upload_to_azure,
                bases=bases, pool_index_path=pool_index_path,
                nb2_ledger=nb2_ledger, fal_sem=fal_sem,
                progress=prog, task_id=tid,
            )
        await _stage_run("Lookalikes", todo_looks, _wrap_looks, total=len(todo_looks))
    else:
        console.print(f"  [dim]all lookalikes already cached[/dim]")

    # ---- Stage 3: action shots (Type A only) ----
    console.print("[bold]Stage 3[/bold]: GPT-Image-2 action shots (Type A only)")
    todo_action = [(i, sid, is_a) for (i, sid, is_a) in indexed
                   if is_a and not (bases.get(sid, {}).get("action_shot")
                                    and Path(bases[sid].get("action_shot", {}).get("path", "")).exists())]
    if todo_action:
        async def _wrap_action(item, prog, tid):
            i, sid, _ = item
            return await _do_action_shot(
                sid=sid, i=i, seed=seed, work_dir=work_dir,
                benchmark_id=benchmark_id, upload=upload_to_azure,
                bases=bases, pool_index_path=pool_index_path,
                gpt_ledger=gpt_ledger, fal_sem=fal_sem,
                identity_verify_attempts=identity_verify_attempts,
                progress=prog, task_id=tid,
            )
        await _stage_run("Actions", todo_action, _wrap_action, total=len(todo_action))
    else:
        console.print(f"  [dim]all action shots already cached[/dim]")

    # ---- Stage 4: compose ----
    console.print("[bold]Stage 4[/bold]: composing MCQ samples")
    composed: list[str] = []
    for (i, sid, is_a) in indexed:
        ok = _compose_one_sample(
            sid=sid, is_type_a=is_a, seed=seed, i=i,
            bases=bases, samples_dir=samples_dir,
            benchmark_id=benchmark_id, upload=upload_to_azure,
        )
        if ok:
            composed.append(sid)

    # ---- Stage 5: emit manifests ----
    console.print("[bold]Stage 5[/bold]: writing manifests")
    dataset_json = {
        "version": benchmark_id,
        "created_at": _now(),
        "n_samples": len(composed),
        "license": "CC-BY-4.0",
        "license_notes": (
            "Fictional persons. NB2 t2i for distractors, GPT-Image-2 Edit for "
            "Type A correct answers. All four options share one action scenario."
        ),
        "source_breakdown": {
            "nb2": {"endpoint": "fal-ai/nano-banana-2"},
            "gpt_image_2": {"endpoint": "openai/gpt-image-2/edit"},
            "vision_describe": {"endpoint": "openrouter/router/vision",
                                 "model": "google/gemini-2.5-flash"},
        },
        "ledgers": {
            "nb2": {"total_usd": nb2_ledger.total_usd,
                    "n_calls": nb2_ledger.n_calls,
                    "failures": nb2_ledger.failures},
            "gpt_image_2": {"total_usd": gpt_ledger.total_usd,
                            "n_calls": gpt_ledger.n_calls,
                            "failures": gpt_ledger.failures},
        },
        "schema_version": "1.0.0",
    }
    (output_dir / "dataset.json").write_text(json.dumps(dataset_json, indent=2, default=str))

    bm_dir = output_dir.parent.parent / "benchmarks" / benchmark_id
    bm_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "benchmark_id": benchmark_id,
        "title": f"Likeness {benchmark_id.split('_')[-1].upper()}",
        "description": (
            "MCQ identity-likeness with shared action scenarios per sample. "
            "Type A correct option is a GPT-Image-2 edit; distractors are "
            "NB2 t2i lookalikes performing the same action."
        ),
        "task_type": "mcq_likeness",
        "sample_ids": composed,
        "schema_version": "1.0.0",
    }
    (bm_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    sibling = output_dir.parent / benchmark_id
    if not sibling.exists() and sibling.resolve() != output_dir.resolve():
        try:
            sibling.symlink_to(output_dir.name)
        except FileExistsError:
            pass

    console.print(
        f"\n[bold green]{benchmark_id} built[/bold green] — {len(composed)} samples · "
        f"NB2 ${nb2_ledger.total_usd:.2f} ({nb2_ledger.n_calls} calls) · "
        f"GPT-Image-2 ${gpt_ledger.total_usd:.2f} ({gpt_ledger.n_calls} calls)"
    )
    return {
        "n_samples": len(composed),
        "nb2_cost_usd": nb2_ledger.total_usd,
        "gpt_image_cost_usd": gpt_ledger.total_usd,
        "manifest_path": str(bm_dir / "manifest.json"),
    }


def build_dataset_v2(
    *,
    output_dir: Path,
    benchmark_id: str = "likeness_v2",
    n_samples: int = 50,
    type_a_ratio: float = 0.5,
    seed: int = 42,
    max_nb2_usd: float = 25.0,
    max_gpt_image_usd: float = 15.0,
    upload_to_azure: bool = True,
    resume: bool = True,
    identity_verify_attempts: int = 2,
    fal_concurrency: int = 5,
) -> dict:
    return asyncio.run(_build_async(
        output_dir=Path(output_dir),
        benchmark_id=benchmark_id,
        n_samples=n_samples,
        type_a_ratio=type_a_ratio,
        seed=seed,
        max_nb2_usd=max_nb2_usd,
        max_gpt_image_usd=max_gpt_image_usd,
        upload_to_azure=upload_to_azure,
        resume=resume,
        identity_verify_attempts=identity_verify_attempts,
        fal_concurrency=fal_concurrency,
    ))
