"""Task ABC. Defines the test-type extension surface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from ..models import ImageInput, ProviderResponse, Sample


class Task(ABC):
    type_id: str = ""
    schema_version: str = "1.0"
    response_format: str = "letter"

    @abstractmethod
    def render_prompt(self, sample: Sample) -> str: ...

    @abstractmethod
    def images_for(self, sample: Sample) -> list[ImageInput]: ...

    @abstractmethod
    def parse(self, raw: ProviderResponse) -> dict: ...

    @abstractmethod
    def score(self, parsed: dict, sample: Sample) -> tuple[bool, dict]: ...

    def expected_response_schema(self) -> dict | None:
        return None
