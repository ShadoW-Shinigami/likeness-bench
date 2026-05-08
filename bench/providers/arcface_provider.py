"""ArcFace baseline provider — no LLM.

For each MCQ sample, computes an ArcFace embedding for the base + each of the 4
candidate images, picks the option with the highest cosine similarity to the
base, and falls back to E ("none of the above") if max similarity is below a
configurable threshold.

Uses insightface's `buffalo_l` pack (512-d L2-normalized embeddings, the same
ones our dataset tier definitions are calibrated against). The face detector
crops the largest face per image automatically — works on both head-shots
(bases) and full-body action shots (options).
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Sequence

import numpy as np

from ..models import ImageInput, Letter, ProviderResponse
from ..registry import register_provider
from .base import VLMProvider

_APP = None  # process-global insightface FaceAnalysis app
_EMB_CACHE: dict[str, np.ndarray | None] = {}


def _get_app():
    global _APP
    if _APP is None:
        import insightface
        from insightface.app import FaceAnalysis
        app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        # ctx_id=-1 → CPU. det_size 640 is fine for our 1024px inputs.
        app.prepare(ctx_id=-1, det_size=(640, 640))
        _APP = app
    return _APP


def _embed_face(path: str) -> np.ndarray | None:
    if path in _EMB_CACHE:
        return _EMB_CACHE[path]
    try:
        import cv2
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            from PIL import Image
            arr = np.array(Image.open(path).convert("RGB"))
            img = arr[:, :, ::-1].copy()  # RGB → BGR
        faces = _get_app().get(img)
    except Exception:
        _EMB_CACHE[path] = None
        return None
    if not faces:
        _EMB_CACHE[path] = None
        return None
    # pick the largest detected face
    face = max(
        faces,
        key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
    )
    emb = face.embedding
    norm = np.linalg.norm(emb)
    if norm <= 0:
        _EMB_CACHE[path] = None
        return None
    out = (emb / norm).astype(np.float32)
    _EMB_CACHE[path] = out
    return out


@register_provider
class ArcFaceProvider(VLMProvider):
    """Pure face-recognition baseline. No LLM call, no prompt — just embeddings."""

    name = "arcface"
    family = "InsightFace"
    supports_vision = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Same-person threshold. Below this, predict E. 0.5 is a sane default
        # for buffalo_l L2-normalized cosines on photographic faces.
        try:
            self.threshold = float(self.extra.get("threshold", 0.5))
        except Exception:
            self.threshold = 0.5

    async def health_check(self) -> bool:
        return True

    async def _evaluate_impl(
        self,
        *,
        prompt: str,
        images: Sequence[ImageInput],
        max_output_tokens: int,
        temperature: float,
    ) -> ProviderResponse:
        t0 = time.monotonic()
        base = next((i for i in images if i.role == "base"), None)
        if base is None:
            return ProviderResponse(
                raw_text="", parsed_choice=None,
                error="no base image", finish_reason="error",
            )

        # Embed base + each option (in a thread; blocks the event loop otherwise)
        base_emb = await asyncio.to_thread(_embed_face, base.path)
        if base_emb is None:
            return ProviderResponse(
                raw_text="", parsed_choice=None,
                error="no face detected in base", finish_reason="error",
                latency_ms=int((time.monotonic() - t0) * 1000),
            )

        sims: dict[Letter, float] = {}
        for img in images:
            if img.role == "base":
                continue
            letter = img.role.split("_", 1)[1].upper()  # option_a → A
            emb = await asyncio.to_thread(_embed_face, img.path)
            if emb is None:
                sims[letter] = float("nan")
                continue
            sims[letter] = float(np.dot(base_emb, emb))

        finite = {k: v for k, v in sims.items() if v == v}  # drop NaN
        if not finite:
            return ProviderResponse(
                raw_text="<answer>E</answer>",
                parsed_choice="E",
                latency_ms=int((time.monotonic() - t0) * 1000),
                input_tokens=0, output_tokens=0,
                finish_reason="stop",
            )

        max_letter = max(finite, key=finite.get)
        max_sim = finite[max_letter]
        choice = max_letter if max_sim >= self.threshold else "E"
        sims_pretty = {k: round(v, 4) for k, v in sims.items()}
        raw = (
            f"<answer>{choice}</answer> "
            f"sims={sims_pretty} threshold={self.threshold} max={max_sim:.4f}"
        )
        return ProviderResponse(
            raw_text=raw,
            parsed_choice=choice,
            latency_ms=int((time.monotonic() - t0) * 1000),
            input_tokens=0, output_tokens=0,
            finish_reason="stop",
        )
