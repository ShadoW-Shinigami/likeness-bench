"""End-to-end dataset build (Phase 4 of the plan).

Usage:
    /opt/anaconda3/bin/conda run -n eval python scripts/build_dataset.py \
        --n-pool 30 --n-samples 20 --max-cost-usd 25 --upload

Generates faces with Nano Banana 2 (Fal AI), composes 5-option MCQs (Type A
correct-present + Type B correct-absent in 50/50 mix), uploads every image to
Azure (using the seedance-prompt-optimiser uploader), and writes:

    dataset/v1/dataset.json
    dataset/v1/samples/lk_v1_NNNNN/{base.png, option_a..d.png, meta.json, provenance.json}
    dataset/v1/pool/p_NNNN/{base.png, variant.png}
    benchmarks/likeness_v1/manifest.json

The build is idempotent — interrupt with Ctrl-C and re-run with --resume to
skip work already on disk.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

# Load .env BEFORE importing anything that touches Fal / Azure
load_dotenv(REPO / ".env", override=False)

from likeness.orchestrator import build_dataset  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark-id", default="likeness_v1")
    ap.add_argument("--output-dir", default=None,
                    help="Default: dataset/<benchmark-id>")
    ap.add_argument("--n-pool", type=int, default=30)
    ap.add_argument("--n-samples", type=int, default=20)
    ap.add_argument("--type-a-ratio", type=float, default=0.5)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--max-cost-usd", type=float, default=25.0)
    ap.add_argument("--upload", action="store_true",
                    help="Upload every image to Azure Blob Storage")
    ap.add_argument("--no-resume", dest="resume", action="store_false")
    args = ap.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else REPO / "dataset" / args.benchmark_id
    out = build_dataset(
        output_dir=output_dir,
        benchmark_id=args.benchmark_id,
        n_pool=args.n_pool,
        n_samples=args.n_samples,
        type_a_ratio=args.type_a_ratio,
        seed=args.seed,
        max_cost_usd=args.max_cost_usd,
        upload_to_azure=args.upload,
        resume=args.resume,
    )
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
