"""Anthropic Claude provider."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Sequence

from ..models import ImageInput, ProviderResponse
from ..registry import register_provider
from . import _vision_utils as vu
from .base import (
    AuthError,
    ContentPolicyRefusal,
    RateLimitError,
    TransientError,
    VLMProvider,
)


@register_provider
class AnthropicProvider(VLMProvider):
    name = "anthropic"
    family = "Anthropic"
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
            from anthropic import AsyncAnthropic, APIError
            from anthropic import RateLimitError as AntRate
            from anthropic import AuthenticationError as AntAuth
            from anthropic import APIConnectionError, APIStatusError
        except ImportError:
            raise RuntimeError("anthropic SDK not installed. pip install anthropic")

        if not self.api_key:
            raise AuthError("ANTHROPIC_API_KEY not set")

        client = AsyncAnthropic(api_key=self.api_key)
        blocks: list[dict] = []
        for img in images:
            b64, mt = vu.to_base64(Path(img.path))
            blocks.append({
                "type": "image",
                "source": {"type": "base64", "media_type": mt, "data": b64},
            })
        blocks.append({"type": "text", "text": prompt})

        t0 = time.monotonic()
        try:
            resp = await client.messages.create(
                model=self.model_id,
                max_tokens=max_output_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": blocks}],
            )
        except AntAuth as e:
            raise AuthError(str(e)) from e
        except AntRate as e:
            raise RateLimitError(str(e)) from e
        except (APIConnectionError, APIStatusError) as e:
            raise TransientError(str(e)) from e
        except APIError as e:
            msg = str(e).lower()
            if "policy" in msg or "safety" in msg:
                raise ContentPolicyRefusal(str(e)) from e
            raise TransientError(str(e)) from e

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        text = "".join(b.text for b in resp.content if hasattr(b, "text"))
        return ProviderResponse(
            raw_text=text,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            latency_ms=elapsed_ms,
            provider_request_id=resp.id,
            finish_reason=resp.stop_reason,
        )
