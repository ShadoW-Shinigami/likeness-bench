"""Prompt bank for Nano Banana 2 face generation."""
from __future__ import annotations

import random

# Diverse demographic prompts for base face generation. Crafted so the base set
# isn't dominated by a single look. We DO NOT name real people — every face is a
# fictional character described by demographics + non-distinctive features.

GENDER_HINTS = ["man", "woman"]
AGE_BUCKETS = [
    ("20-30", "in their mid-twenties"),
    ("30-40", "in their early thirties"),
    ("40-50", "in their forties"),
    ("50-60", "in their fifties"),
    ("60-70", "in their sixties"),
]
ETHNIC_HINTS = [
    "of East Asian descent",
    "of South Asian descent",
    "of Sub-Saharan African descent",
    "of Northern European descent",
    "of Mediterranean descent",
    "of Latin American descent",
    "of Middle Eastern descent",
    "of mixed heritage",
]
HAIR_HINTS = [
    "short black hair", "shoulder-length brown hair", "long curly hair",
    "wavy auburn hair", "straight blonde hair", "salt-and-pepper hair",
    "tight coily hair", "buzzed hair", "a neat bun", "a tied-back ponytail",
]
EYE_HINTS = [
    "warm brown eyes", "sharp hazel eyes", "soft green eyes",
    "light blue eyes", "deep dark eyes", "amber eyes",
]
EXPRESSION_HINTS = [
    "a calm, neutral expression", "a soft smile", "a thoughtful look",
    "a relaxed expression",
]
LIGHTING = [
    "soft daylight from a north-facing window",
    "warm afternoon sunlight",
    "even studio lighting with a soft box",
    "diffuse cloudy-day lighting",
    "natural light from a side window",
]
BACKGROUND = [
    "a plain off-white wall",
    "a softly blurred neutral indoor background",
    "a textured beige wall",
    "a softly lit gray studio backdrop",
    "a blurred bookshelf in the background",
]

BASE_TEMPLATE = (
    "A photographic, candid, head-and-shoulders portrait of a fictional "
    "{gender} {age_phrase}, {ethnic}, with {hair} and {eyes}, {expression}. "
    "{lighting}. {background}. Realistic skin texture, natural pores, no makeup, "
    "no glasses, no jewelry, no text, no watermark, sharp focus on the face. "
    "This is a fictional character — do not generate a real or named person."
)


def make_base_prompt(seed: int) -> dict:
    rng = random.Random(seed)
    gender = rng.choice(GENDER_HINTS)
    age_band, age_phrase = rng.choice(AGE_BUCKETS)
    ethnic = rng.choice(ETHNIC_HINTS)
    hair = rng.choice(HAIR_HINTS)
    eyes = rng.choice(EYE_HINTS)
    expression = rng.choice(EXPRESSION_HINTS)
    lighting = rng.choice(LIGHTING)
    background = rng.choice(BACKGROUND)
    prompt = BASE_TEMPLATE.format(
        gender=gender, age_phrase=age_phrase, ethnic=ethnic,
        hair=hair, eyes=eyes, expression=expression,
        lighting=lighting, background=background,
    )
    return {
        "prompt": prompt,
        "demographics": {
            "perceived_gender": "f" if gender == "woman" else "m",
            "age_band": age_band,
            "ethnic_hint": ethnic,
            "hair": hair,
            "eyes": eyes,
        },
    }


VARIATION_AXES = [
    "a slightly different angle, three-quarter profile",
    "softer side lighting from the left",
    "a different but still neutral expression",
    "a slightly different background, still plainly lit",
    "wearing a different plain top, but the same face",
    "in different ambient lighting (golden hour)",
]


def make_identity_variant_prompt(axis_seed: int) -> str:
    """Prompt that asks NB2 to render the SAME person in a different photo."""
    axis = VARIATION_AXES[axis_seed % len(VARIATION_AXES)]
    return (
        f"The exact same person as in the reference image — same face shape, "
        f"same eye color, same nose, same hair color and texture, same skin tone "
        f"— rendered in {axis}. Photographic, sharp, head-and-shoulders portrait. "
        f"Preserve every facial feature exactly. Only change the framing/lighting. "
        f"No glasses, no jewelry, no text."
    )


# (Reserved for future tier-targeted distractor synthesis; v0 uses pool mining.)
DISTRACTOR_PROMPT_TIERS = {
    "easy": (
        "A different fictional person — clearly a different individual from the reference. "
        "Distinctly different age, build, and ethnic features. Different hair, different eyes, "
        "different bone structure. Photographic head-and-shoulders portrait. Plain background, "
        "even lighting. Realistic skin texture. No glasses, no jewelry, no text."
    ),
    "medium": (
        "A different person who looks somewhat similar to the reference — same general age range "
        "and ethnicity, but a different individual. Different bone structure, different nose, "
        "different mouth. Photographic head-and-shoulders portrait. Plain background. No glasses."
    ),
    "hard": (
        "A different person who could plausibly be confused with the reference at a glance — "
        "same age range, same ethnicity, similar hair color and length, similar skin tone, "
        "but a clearly different individual upon close inspection. Different facial geometry. "
        "Photographic portrait. Plain background, even lighting. No glasses, no jewelry."
    ),
}
