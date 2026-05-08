"""Build the v2 dataset (vision-described distractors + GPT-Image-2 action shots).

Usage:
    python scripts/build_dataset_v2.py \\
        --n-samples 50 --max-nb2-usd 25 --max-gpt-image-usd 15 --upload
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
load_dotenv(REPO / ".env", override=False)

from likeness.orchestrator_v2 import build_dataset_v2  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark-id", default="likeness_v2")
    ap.add_argument("--output-dir", default=None)
    ap.add_argument("--n-samples", type=int, default=50)
    ap.add_argument("--type-a-ratio", type=float, default=0.5)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--max-nb2-usd", type=float, default=25.0)
    ap.add_argument("--max-gpt-image-usd", type=float, default=15.0)
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--no-resume", dest="resume", action="store_false")
    ap.add_argument("--identity-verify-attempts", type=int, default=3)
    ap.add_argument("--fal-concurrency", type=int, default=5,
                    help="Global cap on concurrent Fal requests (NB2 + GPT-Image-2)")
    args = ap.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else REPO / "dataset" / args.benchmark_id
    out = build_dataset_v2(
        output_dir=output_dir,
        benchmark_id=args.benchmark_id,
        n_samples=args.n_samples,
        type_a_ratio=args.type_a_ratio,
        seed=args.seed,
        max_nb2_usd=args.max_nb2_usd,
        max_gpt_image_usd=args.max_gpt_image_usd,
        upload_to_azure=args.upload,
        resume=args.resume,
        identity_verify_attempts=args.identity_verify_attempts,
        fal_concurrency=args.fal_concurrency,
    )
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
