"""OpenRouter vision provider routed through Fal AI.

Calls `https://fal.run/openrouter/router/vision`. The model_id in bench.toml IS
the OpenRouter slug (e.g. `openai/gpt-5.5`, `anthropic/claude-opus-4.7`).
Per the user's instruction we always pass `temperature=1.0, reasoning=True`.

Image inputs may be either remote URLs (preferred — Azure CDN URLs from the
sample meta) or local file paths (uploaded transparently via fal_client).
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Sequence

from ..models import ImageInput, ProviderResponse
from ..registry import register_provider
from .base import (
    AuthError, ContentPolicyRefusal, RateLimitError, TransientError, VLMProvider,
)

OR_VISION_ENDPOINT = "openrouter/router/vision"


@register_provider
class OpenRouterFalProvider(VLMProvider):
    name = "openrouter_fal"
    family = "OpenRouter"
    supports_vision = True

    async def _evaluate_impl(
        self,
        *,
        prompt: str,
        images: Sequence[ImageInput],
        max_output_tokens: int,
        temperature: float,
    ) -> ProviderResponse:
        import os

        try:
            import fal_client
        except ImportError:
            raise RuntimeError("fal-client not installed. pip install fal-client")

        if not os.environ.get("FAL_KEY"):
            raise AuthError("FAL_KEY not set in env")

        image_urls: list[str] = []
        for img in images:
            if img.url:
                image_urls.append(img.url)
            else:
                p = Path(img.path)
                if not p.exists():
                    raise RuntimeError(f"image not found: {p}")
                url = await asyncio.to_thread(fal_client.upload_file, str(p))
                image_urls.append(url)

        # Reasoning models burn tokens internally before emitting the visible
        # answer; a 64-token cap silently truncates the answer. Floor at 2048.
        effective_max = max(int(max_output_tokens or 0), 2048)
        args = {
            "image_urls": image_urls,
            "prompt": prompt,
            "model": self.model_id,
            "temperature": 1.0,
            "reasoning": True,
            "max_tokens": effective_max,
        }

        t0 = time.monotonic()
        try:
            result = await asyncio.to_thread(
                fal_client.subscribe,
                OR_VISION_ENDPOINT,
                arguments=args,
                with_logs=False,
            )
        except Exception as e:
            msg = str(e).lower()
            if "rate limit" in msg or "429" in msg:
                raise RateLimitError(str(e)) from e
            if "policy" in msg or "safety" in msg or "moderation" in msg:
                raise ContentPolicyRefusal(str(e)) from e
            if "auth" in msg or "401" in msg:
                raise AuthError(str(e)) from e
            raise TransientError(str(e)) from e

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        text = result.get("output", "")
        usage = result.get("usage") or {}
        return ProviderResponse(
            raw_text=text,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            cost_usd=float(usage.get("cost", 0.0)),
            latency_ms=elapsed_ms,
            finish_reason="stop",
        )
