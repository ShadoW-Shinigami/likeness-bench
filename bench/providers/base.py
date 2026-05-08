"""VLMProvider ABC. Every provider implements this interface."""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Sequence

from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from ..models import ImageInput, ProviderResponse


class ProviderError(Exception):
    pass


class RateLimitError(ProviderError):
    pass


class AuthError(ProviderError):
    pass


class ContentPolicyRefusal(ProviderError):
    pass


class TransientError(ProviderError):
    pass


class VLMProvider(ABC):
    """Vision-language model provider abstraction."""

    name: str = ""
    model_id: str = ""
    family: str = ""
    display: str = ""
    supports_vision: bool = True
    max_concurrency: int = 4
    price_per_1m_input: float = 0.0
    price_per_1m_output: float = 0.0

    def __init__(
        self,
        *,
        model_id: str | None = None,
        display: str | None = None,
        family: str | None = None,
        price_per_1m_input: float = 0.0,
        price_per_1m_output: float = 0.0,
        max_concurrency: int = 4,
        api_key: str | None = None,
        base_url: str | None = None,
        extra: dict | None = None,
    ):
        if model_id:
            self.model_id = model_id
        if display:
            self.display = display
        if family:
            self.family = family
        self.price_per_1m_input = price_per_1m_input
        self.price_per_1m_output = price_per_1m_output
        self.max_concurrency = max_concurrency
        self.api_key = api_key
        self.base_url = base_url
        self.extra = extra or {}
        self._semaphore: asyncio.Semaphore | None = None

    def get_semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrency)
        return self._semaphore

    @abstractmethod
    async def _evaluate_impl(
        self,
        *,
        prompt: str,
        images: Sequence[ImageInput],
        max_output_tokens: int,
        temperature: float,
    ) -> ProviderResponse: ...

    async def evaluate(
        self,
        *,
        prompt: str,
        images: Sequence[ImageInput],
        max_output_tokens: int = 64,
        temperature: float = 0.0,
    ) -> ProviderResponse:
        """Public entry: applies retries + concurrency cap + cost calc."""
        async with self.get_semaphore():
            try:
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(5),
                    wait=wait_random_exponential(multiplier=1, max=30),
                    retry=retry_if_exception_type((RateLimitError, TransientError)),
                    reraise=True,
                ):
                    with attempt:
                        resp = await self._evaluate_impl(
                            prompt=prompt,
                            images=images,
                            max_output_tokens=max_output_tokens,
                            temperature=temperature,
                        )
                        if resp.input_tokens is not None and resp.output_tokens is not None:
                            resp.cost_usd = (
                                resp.input_tokens * self.price_per_1m_input / 1e6
                                + resp.output_tokens * self.price_per_1m_output / 1e6
                            )
                        return resp
            except ContentPolicyRefusal as e:
                return ProviderResponse(
                    raw_text="",
                    parsed_choice=None,
                    refusal=True,
                    refusal_reason=str(e),
                    finish_reason="content_filter",
                )
            except AuthError:
                raise
            except Exception as e:
                return ProviderResponse(
                    raw_text="",
                    parsed_choice=None,
                    error=f"{type(e).__name__}: {e}",
                    finish_reason="error",
                )
        # unreachable
        raise RuntimeError("retry loop fell through")

    async def health_check(self) -> bool:
        return self.api_key is not None or self.name == "mock"
