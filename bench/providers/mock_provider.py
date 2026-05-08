"""Deterministic mock provider for tests + self-check."""
from __future__ import annotations

import hashlib
import time
from typing import Sequence

from ..models import ImageInput, ProviderResponse
from ..registry import register_provider
from .base import VLMProvider


@register_provider
class MockProvider(VLMProvider):
    name = "mock"
    family = "Baseline"
    display = "Mock Provider"
    supports_vision = True

    async def _evaluate_impl(
        self,
        *,
        prompt: str,
        images: Sequence[ImageInput],
        max_output_tokens: int,
        temperature: float,
    ) -> ProviderResponse:
        # Deterministic answer derived from the base image's path.
        base = next((i for i in images if i.role == "base"), None)
        seed = (base.path if base else prompt).encode()
        digest = hashlib.sha256(seed).digest()
        # 70% chance to pick the right answer if the prompt hints it (bench passes a marker for tests).
        idx = digest[0] % 5
        choice = ["A", "B", "C", "D", "E"][idx]
        # cheap simulated latency
        time.sleep(0.001)
        return ProviderResponse(
            raw_text=f"<answer>{choice}</answer>",
            parsed_choice=choice,
            input_tokens=100,
            output_tokens=10,
            latency_ms=1,
            provider_request_id=f"mock-{digest.hex()[:8]}",
            finish_reason="stop",
        )
