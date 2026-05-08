"""The flagship MCQ likeness task."""
from __future__ import annotations

from typing import Sequence

from ..models import ImageInput, Letter, ProviderResponse, Sample
from ..registry import register_task
from ..runner import parsing
from .base import Task

PROMPT = """You are shown a reference photograph of a person and four candidate \
photographs labeled A, B, C, and D. Your task is purely visual: identify which \
candidate most closely depicts the same person as the reference, OR answer E if \
none of the candidates plausibly depict the same person.

Examine all five images. Compare facial structure, features, and proportions in \
the reference to each candidate. You are NOT being asked to identify, name, or \
recognize anyone — only to judge visual likeness.

Respond with exactly one letter (A, B, C, D, or E) wrapped in <answer> tags. \
Example: <answer>C</answer>

E means: none of A, B, C, or D plausibly depicts the same person as the reference.
"""


@register_task
class MCQLikenessTask(Task):
    type_id = "mcq_likeness"
    schema_version = "1.2"
    response_format = "letter"

    def render_prompt(self, sample: Sample) -> str:
        return PROMPT

    def images_for(self, sample: Sample) -> list[ImageInput]:
        # Pull CDN URLs out of the raw meta dict (they live in fields the
        # SampleMeta model doesn't enumerate but preserves via metadata blobs).
        meta_dump = sample.meta.model_dump()
        base_url = meta_dump.get("_base_cdn_url") or meta_dump.get("base_cdn_url")
        out: list[ImageInput] = [
            ImageInput(
                path=str(sample.image_path("base")),
                media_type="image/png",
                role="base",
                url=base_url,
            )
        ]
        for letter in ("A", "B", "C", "D"):
            opt = sample.meta.options[letter]
            if opt.image:
                # Per-option cdn_url is not in the Pydantic Option schema yet —
                # read from the dump.
                opt_dump = meta_dump.get("options", {}).get(letter, {})
                out.append(
                    ImageInput(
                        path=str(sample.image_path(letter)),
                        media_type="image/png",
                        role=f"option_{letter.lower()}",
                        url=opt_dump.get("cdn_url"),
                    )
                )
        return out

    def parse(self, raw: ProviderResponse) -> dict:
        if raw.error:
            return {"choice": None, "parse_failure": False, "error": raw.error}
        if raw.refusal:
            return {"choice": None, "parse_failure": False, "refusal": True}
        choice = parsing.parse_letter(raw.raw_text)
        return {"choice": choice, "parse_failure": choice is None and not raw.refusal}

    def score(self, parsed: dict, sample: Sample) -> tuple[bool, dict]:
        choice = parsed.get("choice")
        correct = choice == sample.meta.correct_answer
        return correct, {"predicted": choice}

    def expected_response_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {"choice": {"type": "string", "enum": ["A", "B", "C", "D", "E"]}},
            "required": ["choice"],
        }
