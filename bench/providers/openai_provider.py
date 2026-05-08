"""OpenAI vision-language provider."""
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
class OpenAIProvider(VLMProvider):
    name = "openai"
    family = "OpenAI"
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
            from openai import AsyncOpenAI, APIError, RateLimitError as OAIRate
            from openai import AuthenticationError as OAIAuth
            from openai import APIConnectionError, APIStatusError
        except ImportError:
            raise RuntimeError("openai SDK not installed. pip install openai")

        if not self.api_key:
            raise AuthError("OPENAI_API_KEY not set")

        client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        content: list[dict] = [{"type": "text", "text": prompt}]
        for img in images:
            content.append({
                "type": "image_url",
                "image_url": {"url": vu.to_data_url(Path(img.path))},
            })

        t0 = time.monotonic()
        try:
            resp = await client.chat.completions.create(
                model=self.model_id,
                messages=[{"role": "user", "content": content}],
                max_tokens=max_output_tokens,
                temperature=temperature,
            )
        except OAIAuth as e:
            raise AuthError(str(e)) from e
        except OAIRate as e:
            raise RateLimitError(str(e)) from e
        except (APIConnectionError, APIStatusError) as e:
            raise TransientError(str(e)) from e
        except APIError as e:
            msg = str(e).lower()
            if "policy" in msg or "safety" in msg or "refus" in msg:
                raise ContentPolicyRefusal(str(e)) from e
            raise TransientError(str(e)) from e

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        choice = resp.choices[0]
        text = choice.message.content or ""
        usage = resp.usage
        return ProviderResponse(
            raw_text=text,
            input_tokens=getattr(usage, "prompt_tokens", None),
            output_tokens=getattr(usage, "completion_tokens", None),
            latency_ms=elapsed_ms,
            provider_request_id=getattr(resp, "id", None),
            finish_reason=choice.finish_reason,
        )
