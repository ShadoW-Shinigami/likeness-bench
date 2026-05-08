"""Build a 5-sample tiny benchmark fixture using procedurally-drawn faces.

Run:
    /opt/anaconda3/bin/conda run -n eval python scripts/build_fixture.py

This produces tests/fixtures/tiny_benchmark/{manifest.json, samples/0001..0005}
with 6 PNG images each (base + A/B/C/D options). The faces are stylized
geometric drawings — not realistic — but they exercise the full pipeline.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "tests" / "fixtures" / "tiny_benchmark"
SAMPLES = OUT / "samples"
SAMPLES.mkdir(parents=True, exist_ok=True)

W = H = 384
PALETTES = [
    {"skin": (252, 220, 196), "hair": (60, 40, 28), "eye": (90, 60, 30), "shirt": (52, 100, 162)},
    {"skin": (235, 190, 158), "hair": (28, 18, 14), "eye": (55, 36, 24), "shirt": (180, 60, 70)},
    {"skin": (200, 150, 120), "hair": (90, 50, 28), "eye": (70, 45, 25), "shirt": (60, 130, 90)},
    {"skin": (170, 120, 90), "hair": (35, 25, 18), "eye": (40, 25, 18), "shirt": (200, 160, 60)},
    {"skin": (130, 90, 65), "hair": (22, 14, 10), "eye": (35, 22, 14), "shirt": (110, 80, 160)},
]


def draw_face(seed: int, variant: float = 0.0) -> Image.Image:
    rng = random.Random(seed)
    palette = PALETTES[seed % len(PALETTES)]
    # Variant nudges shape/colors slightly to simulate "same person different photo".
    img = Image.new("RGB", (W, H), (245, 245, 248))
    d = ImageDraw.Draw(img)

    # Background gradient strip
    for y in range(H):
        c = 240 + int(8 * (y / H))
        d.line([(0, y), (W, y)], fill=(c, c, c + 4))

    cx, cy = W // 2 + int(rng.uniform(-12, 12) * (1 + variant)), H // 2 + 10
    fw = 150 + int(rng.uniform(-10, 10) * (1 + variant * 2))
    fh = 200 + int(rng.uniform(-10, 10) * (1 + variant * 2))

    # Hair backdrop
    hair = palette["hair"]
    d.ellipse([cx - fw - 18, cy - fh - 14, cx + fw + 18, cy + 16], fill=hair)

    # Face oval
    skin = palette["skin"]
    if variant:
        skin = tuple(max(0, min(255, c + int(rng.uniform(-25, 25) * variant))) for c in skin)
    d.ellipse([cx - fw, cy - fh, cx + fw, cy + fh], fill=skin)

    # Eyes
    eye_y = cy - 20
    eye_dx = 50 + int(rng.uniform(-6, 6) * (1 + variant))
    eye_color = palette["eye"]
    d.ellipse([cx - eye_dx - 22, eye_y - 12, cx - eye_dx + 22, eye_y + 12], fill=(255, 255, 255))
    d.ellipse([cx + eye_dx - 22, eye_y - 12, cx + eye_dx + 22, eye_y + 12], fill=(255, 255, 255))
    d.ellipse([cx - eye_dx - 9, eye_y - 9, cx - eye_dx + 9, eye_y + 9], fill=eye_color)
    d.ellipse([cx + eye_dx - 9, eye_y - 9, cx + eye_dx + 9, eye_y + 9], fill=eye_color)

    # Eyebrows
    bw = 30 + int(rng.uniform(-4, 4) * (1 + variant))
    by = eye_y - 26
    d.line([cx - eye_dx - bw, by, cx - eye_dx + bw, by - 4], fill=hair, width=6)
    d.line([cx + eye_dx - bw, by - 4, cx + eye_dx + bw, by], fill=hair, width=6)

    # Nose
    nose_h = 36 + int(rng.uniform(-6, 6) * (1 + variant))
    d.line([cx, eye_y + 8, cx - 8, eye_y + 8 + nose_h], fill=tuple(max(0, c - 35) for c in skin), width=3)
    d.line([cx - 8, eye_y + 8 + nose_h, cx + 6, eye_y + 8 + nose_h + 4], fill=tuple(max(0, c - 35) for c in skin), width=3)

    # Mouth
    mouth_y = cy + 70
    mw = 38 + int(rng.uniform(-6, 6) * (1 + variant))
    d.arc([cx - mw, mouth_y - 18, cx + mw, mouth_y + 18], 0, 180, fill=(140, 50, 60), width=6)

    # Shoulders / shirt
    shirt = palette["shirt"]
    d.polygon([(0, H), (W, H), (W, H - 60), (cx + 110, cy + fh - 8),
               (cx - 110, cy + fh - 8), (0, H - 60)], fill=shirt)

    return img


def make_distractor(seed: int, base_seed: int, similarity: str) -> Image.Image:
    """Distractor shares palette family for high tier, differs more for easy tier."""
    if similarity == "high":
        return draw_face(base_seed + seed * 1, variant=0.4)
    if similarity == "medium":
        return draw_face(base_seed + seed * 13, variant=0.7)
    return draw_face(base_seed + seed * 97, variant=1.5)


def build():
    sample_ids = []
    for i in range(1, 6):
        sid = f"{i:04d}"
        sample_ids.append(sid)
        sd = SAMPLES / sid
        sd.mkdir(parents=True, exist_ok=True)
        base_seed = i * 1000

        # Base
        draw_face(base_seed).save(sd / "base.png")

        # Decide: type A (correct present, sample 1,2,4) or type B (correct absent, 3,5)
        is_type_a = i in (1, 2, 4)

        if is_type_a:
            # One option is the same person (slight variant), others are distractors
            correct_letter = ["B", "C", "A", "D"][i % 4]
            for letter in ("A", "B", "C", "D"):
                if letter == correct_letter:
                    draw_face(base_seed, variant=0.15).save(sd / f"option_{letter.lower()}.png")
                else:
                    sim = "high" if letter == "A" else ("medium" if letter == "B" else "low")
                    make_distractor(ord(letter), base_seed, sim).save(sd / f"option_{letter.lower()}.png")
            options = {
                "A": {"image": "option_a.png", "kind": "true_match" if correct_letter == "A" else "distractor",
                      "similarity_tier": "self" if correct_letter == "A" else "hard",
                      "similarity_cosine": 0.78 if correct_letter == "A" else 0.61,
                      "source": "fixture", "person_id": f"p{i}_v" if correct_letter == "A" else f"p{i}_d_high"},
                "B": {"image": "option_b.png", "kind": "true_match" if correct_letter == "B" else "distractor",
                      "similarity_tier": "self" if correct_letter == "B" else "medium",
                      "similarity_cosine": 0.78 if correct_letter == "B" else 0.42,
                      "source": "fixture", "person_id": f"p{i}_v" if correct_letter == "B" else f"p{i}_d_med"},
                "C": {"image": "option_c.png", "kind": "true_match" if correct_letter == "C" else "distractor",
                      "similarity_tier": "self" if correct_letter == "C" else "medium",
                      "similarity_cosine": 0.78 if correct_letter == "C" else 0.42,
                      "source": "fixture", "person_id": f"p{i}_v" if correct_letter == "C" else f"p{i}_d_med2"},
                "D": {"image": "option_d.png", "kind": "true_match" if correct_letter == "D" else "distractor",
                      "similarity_tier": "self" if correct_letter == "D" else "easy",
                      "similarity_cosine": 0.78 if correct_letter == "D" else 0.21,
                      "source": "fixture", "person_id": f"p{i}_v" if correct_letter == "D" else f"p{i}_d_low"},
                "E": {"is_none_of_the_above": True},
            }
            meta = {
                "id": sid, "schema_version": "1.0.0", "task_type": "mcq_likeness",
                "subject": {"person_id": f"p{i}", "real_or_synthetic": "synthetic",
                            "license": "CC0", "source": "fixture"},
                "base_image": "base.png", "options": options,
                "correct_answer": correct_letter, "none_of_the_above_is_correct": False,
                "metadata": {"tier": "high", "difficulty_split": "medium", "type_b": False,
                             "synthid_present": False, "human_reviewed": True,
                             "preset": "medium_mix"},
            }
        else:
            # Type B: all 4 are distractors, E is correct
            for letter, sim in [("A", "high"), ("B", "medium"), ("C", "high"), ("D", "low")]:
                make_distractor(ord(letter), base_seed, sim).save(sd / f"option_{letter.lower()}.png")
            options = {
                "A": {"image": "option_a.png", "kind": "distractor", "similarity_tier": "hard",
                      "similarity_cosine": 0.61, "source": "fixture", "person_id": f"p{i}_d_a"},
                "B": {"image": "option_b.png", "kind": "distractor", "similarity_tier": "medium",
                      "similarity_cosine": 0.42, "source": "fixture", "person_id": f"p{i}_d_b"},
                "C": {"image": "option_c.png", "kind": "distractor", "similarity_tier": "hard",
                      "similarity_cosine": 0.59, "source": "fixture", "person_id": f"p{i}_d_c"},
                "D": {"image": "option_d.png", "kind": "distractor", "similarity_tier": "easy",
                      "similarity_cosine": 0.22, "source": "fixture", "person_id": f"p{i}_d_d"},
                "E": {"is_none_of_the_above": True},
            }
            meta = {
                "id": sid, "schema_version": "1.0.0", "task_type": "mcq_likeness",
                "subject": {"person_id": f"p{i}", "real_or_synthetic": "synthetic",
                            "license": "CC0", "source": "fixture"},
                "base_image": "base.png", "options": options,
                "correct_answer": "E", "none_of_the_above_is_correct": True,
                "metadata": {"tier": "high", "difficulty_split": "medium", "type_b": True,
                             "synthid_present": False, "human_reviewed": True,
                             "preset": "medium_mix"},
            }

        (sd / "meta.json").write_text(json.dumps(meta, indent=2))

    manifest = {
        "benchmark_id": "tiny_benchmark",
        "title": "Tiny Fixture Benchmark",
        "description": "5-sample fixture for self-check + UI smoke tests. Procedurally drawn faces.",
        "task_type": "mcq_likeness",
        "sample_ids": sample_ids,
        "schema_version": "1.0.0",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build()
