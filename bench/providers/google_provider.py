"""Google Gemini provider."""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Sequence

from ..models import ImageInput, ProviderResponse
from ..registry import register_provider
from . import _vision_utils as vu
from .base import AuthError, RateLimitError, TransientError, VLMProvider


@register_provider
class GoogleProvider(VLMProvider):
    name = "google"
    family = "Google"
    supports_vision = True

    async def _evaluate_impl(
        self,
        *,
        prompt: str,
        images: Sequence[ImageInput],
        max_output_tokens: int,
        temperature: float,
    ) -> ProviderResponse:
        try:
            import google.generativeai as genai
            from google.api_core import exceptions as gapi_exc
        except ImportError:
            raise RuntimeError(
                "google-generativeai not installed. pip install google-generativeai"
            )

        if not self.api_key:
            raise AuthError("GOOGLE_API_KEY not set")

        genai.configure(api_key=self.api_key)
        parts: list = [prompt]
        for img in images:
            raw, mt = vu.load_and_resize(Path(img.path))
            parts.append({"mime_type": mt, "data": raw})

        model = genai.GenerativeModel(self.model_id)
        t0 = time.monotonic()
        try:
            resp = await asyncio.to_thread(
                model.generate_content,
                parts,
                generation_config={
                    "max_output_tokens": max_output_tokens,
                    "temperature": temperature,
                },
            )
        except gapi_exc.Unauthenticated as e:
            raise AuthError(str(e)) from e
        except gapi_exc.ResourceExhausted as e:
            raise RateLimitError(str(e)) from e
        except gapi_exc.GoogleAPIError as e:
            raise TransientError(str(e)) from e

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        try:
            text = resp.text or ""
        except Exception:
            text = ""
        usage = getattr(resp, "usage_metadata", None)
        return ProviderResponse(
            raw_text=text,
            input_tokens=getattr(usage, "prompt_token_count", None),
            output_tokens=getattr(usage, "candidates_token_count", None),
            latency_ms=elapsed_ms,
            finish_reason=str(getattr(resp.candidates[0], "finish_reason", "")) if resp.candidates else None,
        )
