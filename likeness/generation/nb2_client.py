"""Nano Banana 2 client (via Fal AI).

Wraps fal-client with a simple sync API + cost ledger. Vendored utilities for
aspect-ratio snapping etc. would live here once we need them — v0 uses 1K
square outputs which side-step those concerns.
"""
from __future__ import annotations

import io
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import fal_client
import httpx
from PIL import Image

NB2_TEXT_TO_IMAGE = "fal-ai/nano-banana-2"
NB2_EDIT = "fal-ai/nano-banana-2/edit"

# Approximate price per image (1K resolution, March 2026 pricing).
PRICE_PER_IMAGE_1K = 0.045
PRICE_PER_IMAGE_2K = 0.10


@dataclass
class GenLedger:
    max_usd: float = 30.0
    total_usd: float = 0.0
    n_calls: int = 0
    failures: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, cost: float) -> None:
        with self._lock:
            self.total_usd += cost
            self.n_calls += 1

    def fail(self) -> None:
        with self._lock:
            self.failures += 1

    def check_budget(self) -> None:
        if self.total_usd >= self.max_usd:
            raise RuntimeError(
                f"Generation budget exceeded: ${self.total_usd:.2f} >= ${self.max_usd:.2f}"
            )


def _ensure_key() -> str:
    k = os.environ.get("FAL_KEY")
    if not k:
        raise RuntimeError("FAL_KEY not set in env")
    return k


def _download(url: str, timeout: float = 120.0) -> bytes:
    r = httpx.get(url, timeout=timeout)
    r.raise_for_status()
    return r.content


def _save_png(data: bytes, path: Path, max_edge: int = 1024) -> None:
    img = Image.open(io.BytesIO(data)).convert("RGB")
    if max(img.size) > max_edge:
        img.thumbnail((max_edge, max_edge), Image.LANCZOS)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG", optimize=True)


def text_to_image(
    *,
    prompt: str,
    out_path: Path,
    ledger: GenLedger,
    aspect_ratio: str = "1:1",
    resolution: str = "1K",
    seed: Optional[int] = None,
) -> dict:
    """Generate a face from a text prompt and save to disk. Returns meta dict."""
    _ensure_key()
    ledger.check_budget()
    args = {
        "prompt": prompt,
        "num_images": 1,
        "aspect_ratio": aspect_ratio,
        "output_format": "png",
        "resolution": resolution,
    }
    if seed is not None:
        args["seed"] = seed
    t0 = time.monotonic()
    try:
        result = fal_client.subscribe(NB2_TEXT_TO_IMAGE, arguments=args, with_logs=False)
    except Exception as e:
        ledger.fail()
        raise RuntimeError(f"NB2 text-to-image failed: {e}") from e

    images = result.get("images") or []
    if not images:
        ledger.fail()
        raise RuntimeError(f"NB2 returned no images. Result: {result}")
    url = images[0]["url"]
    data = _download(url)
    _save_png(data, out_path)
    cost = PRICE_PER_IMAGE_1K if resolution == "1K" else PRICE_PER_IMAGE_2K
    ledger.add(cost)
    return {
        "endpoint": NB2_TEXT_TO_IMAGE,
        "request_id": result.get("request_id"),
        "image_url": url,
        "cost_usd": cost,
        "elapsed_ms": int((time.monotonic() - t0) * 1000),
        "prompt": prompt,
    }


def edit_with_reference(
    *,
    prompt: str,
    reference_image_paths: list[Path],
    out_path: Path,
    ledger: GenLedger,
    aspect_ratio: str = "1:1",
    resolution: str = "1K",
) -> dict:
    """Use NB2 edit endpoint with reference image(s) to generate identity-preserved variant."""
    _ensure_key()
    ledger.check_budget()
    image_urls: list[str] = []
    for p in reference_image_paths:
        url = fal_client.upload_file(str(p))
        image_urls.append(url)
    args = {
        "prompt": prompt,
        "num_images": 1,
        "aspect_ratio": aspect_ratio,
        "output_format": "png",
        "resolution": resolution,
        "image_urls": image_urls,
    }
    t0 = time.monotonic()
    try:
        result = fal_client.subscribe(NB2_EDIT, arguments=args, with_logs=False)
    except Exception as e:
        ledger.fail()
        raise RuntimeError(f"NB2 edit failed: {e}") from e
    images = result.get("images") or []
    if not images:
        ledger.fail()
        raise RuntimeError(f"NB2 edit returned no images. Result: {result}")
    url = images[0]["url"]
    data = _download(url)
    _save_png(data, out_path)
    cost = PRICE_PER_IMAGE_1K if resolution == "1K" else PRICE_PER_IMAGE_2K
    ledger.add(cost)
    return {
        "endpoint": NB2_EDIT,
        "request_id": result.get("request_id"),
        "image_url": url,
        "input_image_urls": image_urls,
        "cost_usd": cost,
        "elapsed_ms": int((time.monotonic() - t0) * 1000),
        "prompt": prompt,
    }
