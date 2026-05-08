"""GPT-Image-2 Edit endpoint wrapper (via Fal).

Used to generate the **correct-answer** option for Type A samples: take the
base portrait and put the same person in a full-body action scene. GPT-Image-2
is reasonably good at preserving facial identity through such edits; we still
verify with a vision pass.
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

GPT_IMAGE2_EDIT = "openai/gpt-image-2/edit"

# Approximate cost at high-quality 1024×1024 (per fal pricing).
PRICE_HIGH_QUALITY_PER_IMAGE = 0.30


@dataclass
class GptImageLedger:
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
                f"GPT-Image-2 budget exceeded: ${self.total_usd:.2f} >= ${self.max_usd:.2f}"
            )


# Full-body action scenarios. Identity preservation tends to be easier when
# the face is still visible — we bias toward situations where the camera can
# see the subject clearly.
ACTION_SCENARIOS = [
    "standing at a busy bar holding a glass, soft warm lighting, medium full-body shot, face clearly visible",
    "riding a bicycle on a sunlit city street, casual clothing, full-body shot, face turned slightly toward the camera",
    "walking through an autumn park with leaves on the ground, full-body candid photograph",
    "sitting on a wooden bench reading a paperback book, late afternoon light, full-body shot",
    "jogging along a beach at sunrise, athletic clothing, full-body shot, face clearly visible",
    "shopping at an outdoor farmer's market, holding a paper bag with vegetables, full-body shot",
    "hiking on a forest trail with a daypack, casual outdoor clothes, full-body shot, face turned toward camera",
    "working at a wooden desk with a laptop and coffee cup, looking up at the camera, three-quarter body",
    "waiting at a train platform with a small suitcase, urban setting, full-body shot",
    "cooking at a stovetop in a sunlit kitchen, wearing an apron, three-quarter body shot",
    "crossing a downtown crosswalk at golden hour, casual urban clothing, full-body candid",
    "sitting on the edge of a fountain in a public square, full-body shot, face visible",
    "leaning against a brick wall in a quiet alley, casual clothes, three-quarter body",
    "playing with a dog in a backyard with a ball, sunny daylight, full-body shot",
    "carrying a yoga mat through a city street, athletic clothes, full-body shot",
]


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


def edit_action_shot(
    *,
    reference_image_url: str,
    out_path: Path,
    ledger: GptImageLedger,
    scenario_seed: int = 0,
    quality: str = "high",
) -> dict:
    """Generate a full-body action shot of the same person. Returns provenance dict."""
    if not os.environ.get("FAL_KEY"):
        raise RuntimeError("FAL_KEY not set")
    ledger.check_budget()
    scenario = ACTION_SCENARIOS[scenario_seed % len(ACTION_SCENARIOS)]
    prompt = (
        f"The exact same person as in the reference image, now {scenario}. "
        "Preserve every facial feature exactly: same face shape, same eye color, "
        "same nose, same hair color and texture, same skin tone. Photographic, "
        "realistic, sharp focus on the face. No text, no watermark."
    )
    t0 = time.monotonic()
    try:
        result = fal_client.subscribe(
            GPT_IMAGE2_EDIT,
            arguments={
                "prompt": prompt,
                "image_urls": [reference_image_url],
                "image_size": "auto",
                "quality": quality,
                "num_images": 1,
                "output_format": "png",
            },
            with_logs=False,
        )
    except Exception as e:
        ledger.fail()
        raise RuntimeError(f"GPT-Image-2 edit failed: {e}") from e
    images = result.get("images") or []
    if not images:
        ledger.fail()
        raise RuntimeError(f"GPT-Image-2 returned no images: {result}")
    url = images[0]["url"]
    data = _download(url)
    _save_png(data, out_path)
    cost = PRICE_HIGH_QUALITY_PER_IMAGE  # rough estimate; refined per call below
    ledger.add(cost)
    return {
        "endpoint": GPT_IMAGE2_EDIT,
        "image_url": url,
        "input_image_url": reference_image_url,
        "scenario": scenario,
        "prompt": prompt,
        "cost_usd": cost,
        "elapsed_ms": int((time.monotonic() - t0) * 1000),
    }
