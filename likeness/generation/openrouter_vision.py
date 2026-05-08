"""Vision tasks routed through Fal -> OpenRouter.

Used for two things in the dataset build pipeline:

  1. **Describe**: caption a base portrait verbosely so we can derive
     similar-but-different prompts for lookalike distractors.
  2. **Verify**: ask the model "are these the same person?" to gate
     GPT-Image-2 action shots (regenerate if identity drifts).
"""
from __future__ import annotations

import os
import time

import fal_client

OR_VISION_ENDPOINT = "openrouter/router/vision"
DEFAULT_MODEL = "google/gemini-2.5-flash"  # cheap and fast — "below Gemini 3"


def _ensure_fal_key() -> None:
    if not os.environ.get("FAL_KEY"):
        raise RuntimeError("FAL_KEY not set")


DESCRIBE_SYSTEM = (
    "You describe faces with maximum visual specificity for downstream "
    "image generation. Output is consumed by a t2i model. Do not name the "
    "person. Do not invent identifying claims. Only describe what is visible."
)

DESCRIBE_PROMPT = """Look at this portrait. Describe the person's face and head with maximum visual detail.

Cover, in this order, all of:
- estimated age range (10-year band) and apparent gender presentation
- skin tone (e.g. fair, olive, deep) and any visible texture detail
- face shape (e.g. oval, square, heart, round) and jawline
- hair: color, length, texture, style, hairline
- eyes: color, shape, set
- eyebrows: thickness, shape
- nose: shape, bridge, tip
- mouth: lip thickness, shape
- distinguishing features: facial hair, freckles, moles, scars, etc.
- general apparent ethnicity hints (without naming any specific group)
- expression and head angle

Write 4-6 sentences. Be specific and visual. No names, no judgments, no commentary. End with a single line: "ANCHOR: <one short clause that captures the most distinctive visual feature>"."""


def describe_face(image_url: str, model: str = DEFAULT_MODEL,
                  max_tokens: int = 512) -> dict:
    """Return {"description": str, "anchor": str, "cost_usd": float}."""
    _ensure_fal_key()
    t0 = time.monotonic()
    res = fal_client.subscribe(
        OR_VISION_ENDPOINT,
        arguments={
            "image_urls": [image_url],
            "prompt": DESCRIBE_PROMPT,
            "system_prompt": DESCRIBE_SYSTEM,
            "model": model,
            "temperature": 0.4,
            "reasoning": False,
            "max_tokens": max_tokens,
        },
        with_logs=False,
    )
    text = (res.get("output") or "").strip()
    anchor = ""
    description = text
    for line in text.splitlines():
        line = line.strip()
        if line.upper().startswith("ANCHOR:"):
            anchor = line.split(":", 1)[1].strip()
    if anchor:
        # remove the ANCHOR line from the body
        description = "\n".join(
            ln for ln in text.splitlines() if not ln.strip().upper().startswith("ANCHOR:")
        ).strip()
    return {
        "description": description,
        "anchor": anchor,
        "cost_usd": float((res.get("usage") or {}).get("cost", 0.0)),
        "elapsed_ms": int((time.monotonic() - t0) * 1000),
    }


VERIFY_SYSTEM = (
    "You compare faces. Output a single token: YES or NO. Then on the next "
    "line a short reason. Do not output anything else."
)

VERIFY_PROMPT = (
    "Are the two photos likely the same person? Look at face shape, eye spacing, "
    "nose shape, mouth, and hairline. Ignore differences in pose, lighting, "
    "expression, hair styling, clothing, and background. Be strict — if the "
    "facial geometry meaningfully differs, answer NO.\n\n"
    "Image 1 is the reference. Image 2 is the candidate. Answer:\nYES or NO\n"
    "<one-line reason>"
)


def verify_same_person(reference_url: str, candidate_url: str,
                       model: str = DEFAULT_MODEL,
                       max_tokens: int = 100) -> dict:
    """Return {"same": bool, "reason": str, "cost_usd": float}."""
    _ensure_fal_key()
    t0 = time.monotonic()
    res = fal_client.subscribe(
        OR_VISION_ENDPOINT,
        arguments={
            "image_urls": [reference_url, candidate_url],
            "prompt": VERIFY_PROMPT,
            "system_prompt": VERIFY_SYSTEM,
            "model": model,
            "temperature": 0.0,
            "reasoning": False,
            "max_tokens": max_tokens,
        },
        with_logs=False,
    )
    text = (res.get("output") or "").strip()
    first_line = (text.splitlines() or [""])[0].strip().upper()
    same = first_line.startswith("YES")
    return {
        "same": same,
        "reason": text,
        "cost_usd": float((res.get("usage") or {}).get("cost", 0.0)),
        "elapsed_ms": int((time.monotonic() - t0) * 1000),
    }


DERIVE_LOOKALIKE_SYSTEM = (
    "You write image-generation prompts for fictional faces. Output a single "
    "self-contained prompt for a text-to-image model. No names, no commentary."
)

DERIVE_LOOKALIKE_PROMPT_TEMPLATE = """Below is a description of a portrait. Generate a prompt for a NEW, DIFFERENT person who would plausibly be MISTAKEN for this person at a glance — same general age, ethnicity, gender presentation, and overall vibe — BUT with measurably different facial geometry (different jawline, different nose, different eye shape, different lip shape).

The new person must look DIFFERENT on close inspection. Same family of look, different individual. Vary {variation_hint}.

The image MUST show this person {action_scenario}. Full-body or three-quarter body shot. Face clearly visible. Photographic, realistic, sharp focus on the face.

Original face description:
{description}

Output ONLY the new image-generation prompt — a single self-contained string suitable for a t2i model. Do not output anything else. Mention all of: the new person's specific facial features (different from the reference), the action they are performing, and the framing. End with: "Photographic, sharp focus, realistic skin texture."""

VARIATION_HINTS = [
    "the nose shape, eye spacing, and jaw width",
    "the lip shape, brow height, and chin",
    "the cheekbone prominence and face length",
    "the eyebrow thickness, hairline, and forehead height",
    "the nose bridge, eye color, and lip fullness",
]


def derive_lookalike_prompt(description: str, action_scenario: str,
                            model: str = DEFAULT_MODEL, seed: int = 0,
                            max_tokens: int = 800) -> dict:
    """Use the description + action scenario to write a t2i prompt for a
    similar-but-different person performing the same action."""
    _ensure_fal_key()
    hint = VARIATION_HINTS[seed % len(VARIATION_HINTS)]
    user_prompt = DERIVE_LOOKALIKE_PROMPT_TEMPLATE.format(
        variation_hint=hint, description=description,
        action_scenario=action_scenario,
    )
    t0 = time.monotonic()
    res = fal_client.subscribe(
        OR_VISION_ENDPOINT,
        arguments={
            "image_urls": [],
            "prompt": user_prompt,
            "system_prompt": DERIVE_LOOKALIKE_SYSTEM,
            "model": model,
            "temperature": 0.85,
            "reasoning": False,
            "max_tokens": max_tokens,
        },
        with_logs=False,
    )
    text = (res.get("output") or "").strip()
    return {
        "prompt": text,
        "cost_usd": float((res.get("usage") or {}).get("cost", 0.0)),
        "variation_hint": hint,
        "elapsed_ms": int((time.monotonic() - t0) * 1000),
    }
