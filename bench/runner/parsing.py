"""Robust answer extraction from free-form model output."""
from __future__ import annotations

import re

from ..models import Letter

_ANSWER_TAG = re.compile(r"<answer>\s*([A-Ea-e])\s*</answer>", re.IGNORECASE)
_LETTER_FIRST = re.compile(r"^\s*(?:Option\s+|Answer\s*[:\-]?\s*)?\(?([A-Ea-e])\)?\b", re.IGNORECASE)
_LETTER_ANY = re.compile(r"\b([A-E])\b")
_NONE_PHRASE = re.compile(r"\bnone of (?:the )?(?:above|these)\b", re.IGNORECASE)
_FIRST_PHRASE = re.compile(r"\bthe (?:first|1st)\b", re.IGNORECASE)
_SECOND_PHRASE = re.compile(r"\bthe (?:second|2nd)\b", re.IGNORECASE)
_THIRD_PHRASE = re.compile(r"\bthe (?:third|3rd)\b", re.IGNORECASE)
_FOURTH_PHRASE = re.compile(r"\bthe (?:fourth|4th)\b", re.IGNORECASE)


def parse_letter(text: str) -> Letter | None:
    """Try several strategies to extract a single A/B/C/D/E choice."""
    if not text:
        return None

    m = _ANSWER_TAG.search(text)
    if m:
        return m.group(1).upper()  # type: ignore[return-value]

    m = _LETTER_FIRST.search(text)
    if m:
        return m.group(1).upper()  # type: ignore[return-value]

    if _NONE_PHRASE.search(text):
        return "E"

    if _FIRST_PHRASE.search(text):
        return "A"
    if _SECOND_PHRASE.search(text):
        return "B"
    if _THIRD_PHRASE.search(text):
        return "C"
    if _FOURTH_PHRASE.search(text):
        return "D"

    m = _LETTER_ANY.search(text)
    if m:
        return m.group(1).upper()  # type: ignore[return-value]

    return None
