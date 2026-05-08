# likeness-bench

A vision-language-model benchmark for **face-likeness detection under shared context**.

Each item is a 5-option MCQ. One reference photograph plus four candidate full-body action shots — *all of the same activity*. ~50% of items have the actual person somewhere in the four; the rest are all lookalikes (E = "none of the above"). Distractors are vision-described and identity-verified through Gemini 2.5 Flash; the correct option is a GPT-Image-2 edit of the reference; an ArcFace baseline gives the empirical ceiling.

```
                              ┌───────────────────────────────────┐
                              │       reference portrait          │
                              └───────────────────────────────────┘
                                        │
        ┌───────┬─────────────┬─────────┴──────────┬──────────────┬─────────┐
        ▼       ▼             ▼                    ▼              ▼         ▼
      [ A ]   [ B ]         [ C ]                [ D ]          [ E ] none of the above
   distractor distractor true match (GPT-IM-2)  distractor

  All four candidates are full-body shots of the same action scenario
  (e.g. "riding a bicycle on a sunlit city street").
```

## Headline result

50 MCQs · seven systems · all under the trivial "always-pick-E" baseline except the ArcFace baseline:

| Rank | Model | Composite | Accuracy | Type A · present | Type B · absent |
|-----:|-------|----------:|---------:|-----------------:|----------------:|
|   1  | **ArcFace (buffalo_l)** | **90.0%** | **92.0%** | 100.0% | **84.0%** |
|   2  | Gemini 3 Flash | 52.5% | 62.0% | 100.0% | 24.0% |
|   3  | Seed 2.0 Lite | 50.0% | 60.0% | 100.0% | 20.0% |
|   4  | Seed 1.6 | 43.5% | 54.0% | 92.0% | 16.0% |
|   5  | Claude Opus 4.6 | 40.5% | 52.0% | 96.0% | 8.0% |
|   5  | Claude Opus 4.7 | 40.5% | 52.0% | 96.0% | 8.0% |
|   7  | GPT-5.5 | 29.5% | 42.0% | 84.0% | 0.0% |

Random baseline = 20% · always-pick-E = 50%.

The gap is entirely on **Type B (correct absent)**. LLMs over-pick a confident lookalike when the real subject isn't in the lineup. ArcFace's `max(cosine) < 0.5 ⇒ predict E` rule cleanly abstains.

---

## Quickstart

```bash
git clone https://github.com/<your-username>/likeness-bench.git
cd likeness-bench
make install        # conda env 'eval' + Python deps
make web-install
make build
make self-check     # mock provider over a 5-sample fixture (no API keys needed)
make serve          # http://127.0.0.1:8000
```

### Run a real model

```bash
cp .env.example .env
# fill in OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, FAL_KEY...

bench eval --model gemini-3-flash --benchmark likeness_v2 --max-cost-usd 4
```

### Run every configured model in one shot

```bash
make refresh        # evals any model that doesn't have a result yet,
                    # then rebuilds showcase.html
# or:
bench eval-all --benchmark likeness_v2
bench refresh-showcase
```

### Add a new model

Drop a `[models.<key>]` block into `bench.toml` (or `bench.local.toml` for personal overrides):

```toml
[models.gpt-6]
provider = "openrouter_fal"   # or openai / anthropic / google
model_id = "openai/gpt-6"
display = "GPT-6"
family = "OpenAI"
```

Then `make refresh` runs only the new model and regenerates the showcase.

### Add a new test type

1. Subclass `bench.tasks.base.Task` in `bench/tasks/my_task.py`, set `type_id`, decorate `@register_task`.
2. Import in `bench/tasks/__init__.py`.
3. Drop a renderer at `web/src/components/task-types/MyTask.jsx`, register in `web/src/utils/taskTypeRegistry.js`.
4. Build a benchmark whose samples have `task_type: "my_task"`.
5. `bench self-check --benchmark my_task_v1 --model mock` to verify wiring.

---

## How the dataset is built

```
                ┌──────────────────────┐
                │ pick action scenario │  e.g. "riding a bicycle on a sunlit city street"
                │  (per sample)        │
                └──────────┬───────────┘
                           │
                           ▼
            ┌──────────────────────────────┐
            │  base portrait (NB2 t2i)      │
            │  fictional person, head-shot  │
            └──────────────┬────────────────┘
                           │
              ┌────────────┴───────────────┐
              ▼                            ▼
   ┌─────────────────────────┐   ┌────────────────────────────┐
   │ Vision describe          │   │ GPT-Image-2 Edit            │
   │ (Gemini 2.5 Flash)       │   │ same person in the action   │
   │ 4–6 sentences,           │   │ → identity-verified by      │
   │ + ANCHOR feature         │   │   Gemini 2.5 Flash          │
   └────────────┬─────────────┘   └────────────────────────────┘
                │                            │
                ▼                            ▼
   ┌──────────────────────────────┐    [TYPE A correct option]
   │ Derive lookalike prompts      │
   │ (variation hints — different  │
   │  jaw / nose / eyes / lips)    │
   └────────────┬─────────────────┘
                │
                ▼
        ┌──────────────────────┐
        │ NB2 t2i × 3 (Type A)  │   different people, same action
        │ NB2 t2i × 4 (Type B)  │
        └──────────────────────┘
```

Build the full dataset:

```bash
bench grow-dataset --benchmark likeness_v2 --n-samples 50 \
    --max-nb2-usd 25 --max-gpt-image-usd 25
# resumable: stop with Ctrl-C, re-run to pick up
```

Total cost for 50 samples: ~$13 (NB2 ~$5–6 · GPT-Image-2 ~$7.50).

---

## Architecture

```
bench/                      # eval engine
  cli.py                    # typer entry point: `bench`
  providers/                # VLMProvider implementations
    base.py
    mock_provider.py
    openai_provider.py
    anthropic_provider.py
    google_provider.py
    openrouter_fal_provider.py
    arcface_provider.py     # baseline — no LLM
  tasks/                    # Task abstraction
    base.py
    mcq_likeness.py
  runner/
    pipeline.py             # async orchestration, atomic checkpoints, --resume
    control.py              # pause / resume / kill via on-disk JSON
    parsing.py              # robust answer extraction
  scoring/
    metrics.py              # accuracy, by-tier, presence-conditioned
    intervals.py            # Wilson score CI
    composite.py            # composite Likeness Score
  server/                   # FastAPI — single port for /api/* + React bundle
    api/{runs,results,samples,models,showcase}.py
  utils/
    storage.py              # pluggable image-host backend (default: local)

likeness/                   # dataset build pipeline
  orchestrator_v2.py        # 4-stage build: bases → lookalikes → action → compose
  generation/
    nb2_client.py           # Nano Banana 2 t2i
    gpt_image2_edit.py      # GPT-Image-2 Edit (action shot)
    openrouter_vision.py    # describe / verify / derive prompts
    prompts.py
  embeddings/
    phash_similarity.py     # placeholder; ArcFace via insightface for tier calibration
  composition/
    mcq_builder.py

dataset/likeness_v2/        # 50-sample MCQ benchmark
  samples/lk_v2_NNNNN/
    base.jpg
    option_a..d.jpg
    meta.json
    provenance.json
  dataset.json

benchmarks/likeness_v2/manifest.json
results/likeness_v2/        # per-model run aggregates + index.json
runs/                       # in-flight run state (gitignored)

web/                        # React + Vite + Tailwind frontend
  src/routes/{Leaderboard, Practice, Runs, Models, Samples, About}Page.jsx
```

---

## Run control

The runner reads `runs/<run_id>/control.json` between every sample. Both the CLI and the FastAPI server write the same file, so a run started from the web UI can be paused from the terminal (or vice versa).

```bash
bench runs list
bench runs pause   <run_id>
bench runs resume  <run_id>
bench runs kill    <run_id>
bench runs continue <run_id>      # restart skipping completed samples
```

The Runs page in the web UI exposes the same controls plus a **Rebuild showcase** button.

---

## Image hosting

By default the FastAPI server serves images directly from `dataset/likeness_v2/samples/<sid>/*.jpg`. No external host needed.

If you want a CDN, implement the `Storage` protocol in `bench/utils/storage.py` and point at it via env:

```python
# mypkg/r2.py
from bench.utils.storage import Storage

class R2Storage(Storage):
    def upload_file(self, *, local_path, blob_name=None, content_type=None) -> str:
        # ... upload to Cloudflare R2 / S3-compatible, return public URL
        ...
    def upload_bytes(self, *, data, blob_name, content_type=None) -> str: ...
```

```bash
BENCH_STORAGE_BACKEND=mypkg.r2.R2Storage bench refresh-showcase
```

The `meta.json` schema reserves an optional `cdn_url` per option, used by the FastAPI image route to 302-redirect to the CDN when present. Recommended free hosts:

- **Cloudflare R2** — 10 GB free, S3-compatible
- **Hugging Face Hub Datasets** — perpetual free, designed for ML
- **GitHub LFS** — within bandwidth quota for small datasets
- **Bunny CDN** — pay-as-you-go ~$0.01/GB

---

## Composite Likeness Score

Punishes both halves of E-error so a model can't game the metric by always (or never) picking E:

```
                  acc(present) + acc(absent)         fp_E + fn_E
   Composite =   ──────────────────────────  −  λ ·  ───────────
                            2                             2

   fp_E = P(predict E  |  E is the wrong answer)
   fn_E = P(predict ¬E |  E is the right answer)
   λ = 0.25  (configurable per-benchmark in bench.toml)
```

Wilson 95% intervals + per-tier breakdowns are written into `results/<benchmark>/<model>__<run>.json` for every run.

---

## Adding more samples

Datasets are versioned and additive:

```bash
bench grow-dataset --benchmark likeness_v2 --n-samples 100   # 50 → 100
# Existing pool entries + lookalikes + action shots are preserved.
# Only the new samples are generated.
```

Then re-evaluate every model on the bigger set:

```bash
bench eval-all --benchmark likeness_v2 --force
bench refresh-showcase
```

---

## Self-check

A 5-sample procedurally-generated fixture lives in `tests/fixtures/tiny_benchmark/`. Use it to verify the whole pipeline (no API keys needed):

```bash
make self-check
# → mock provider, all 5 samples, ~1 second
```

The same fixture is exposed at `/practice` in the web UI for human play.

---

## Limitations

- **Synthetic faces only** — every subject is a fictional person generated by Nano Banana 2. No real identities. We don't claim this transfers cleanly to real-world face recognition.
- **Identity-verify is imperfect** — Gemini 2.5 Flash sometimes accepts GPT-Image-2 outputs that subtly drift the face. It's a soft gate (with up to 2 retries), not a hard guarantee. The verifier's verdict is recorded in `meta.json.metadata.type_a_action_verify`.
- **The "perceptual-hash similarity tier" is a placeholder.** The intended tier definition uses ArcFace cosine; we ship a pHash16 stand-in for portability. ArcFace embeddings are only consumed by the baseline scorer.
- **OR-on-Fal latency is high with reasoning=on.** A full 50-sample run takes 5–10 minutes per model.

---

## License

MIT (see `LICENSE`).

Generated faces are derivatives of Nano Banana 2 (Google, via Fal AI) and GPT-Image-2 (OpenAI). Verify your provider's terms before redistributing the dataset.
