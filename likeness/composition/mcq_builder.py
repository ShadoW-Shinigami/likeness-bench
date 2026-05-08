"""Compose MCQ samples from a pool of generated face images."""
from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..embeddings.phash_similarity import bucket_tier, hamming_similarity, phash


@dataclass
class PoolEntry:
    person_id: str             # e.g. "p_0001"
    base_path: Path            # primary photo
    variant_path: Optional[Path] = None  # "same person, different photo" (if generated)
    cdn_base: Optional[str] = None
    cdn_variant: Optional[str] = None
    demographics: dict = None
    base_provenance: dict = None
    variant_provenance: Optional[dict] = None


def _opt_block(*, image: str, kind: str, cosine: float, source: str,
               person_id: str, generated_by: Optional[str] = None,
               request_id: Optional[str] = None,
               cdn_url: Optional[str] = None) -> dict:
    block = {
        "image": image,
        "kind": kind,
        "similarity_tier": bucket_tier(cosine) if kind != "true_match" else "self",
        "similarity_cosine": round(cosine, 4),
        "source": source,
        "person_id": person_id,
    }
    if generated_by:
        block["generated_by"] = generated_by
    if request_id:
        block["fal_request_id"] = request_id
    if cdn_url:
        block["cdn_url"] = cdn_url
    return block


def build_sample(
    *,
    sample_id: str,
    pool: list[PoolEntry],
    target_index: int,
    is_type_a: bool,
    rng: random.Random,
) -> Optional[dict]:
    """Build one MCQ sample. Returns None if the pool is too small.

    Type A: target person's `variant_path` is the correct option; 3 distractors mined.
    Type B: 4 distractors mined; correct_answer = "E".
    """
    target = pool[target_index]
    if is_type_a and target.variant_path is None:
        return None  # cannot build Type A without a variant

    distractor_indices = [i for i in range(len(pool)) if i != target_index]
    rng.shuffle(distractor_indices)

    base_hash = phash(target.base_path)

    # Pick 4 distractors (Type A uses 3 + 1 variant; Type B uses 4)
    needed = 3 if is_type_a else 4
    chosen = distractor_indices[:needed]
    if len(chosen) < needed:
        return None

    # Assign letters; for Type A, drop the variant in a random A-D slot
    letters = ["A", "B", "C", "D"]
    rng.shuffle(letters)
    options: dict[str, dict] = {}

    if is_type_a:
        correct_letter = letters[0]
        options[correct_letter] = _opt_block(
            image=f"option_{correct_letter.lower()}.png",
            kind="true_match",
            cosine=hamming_similarity(base_hash, phash(target.variant_path)),
            source="nb2_identity_variant",
            person_id=target.person_id,
            generated_by="fal-ai/nano-banana-2/edit",
            request_id=(target.variant_provenance or {}).get("request_id"),
            cdn_url=target.cdn_variant,
        )
        options[correct_letter]["_local_image"] = str(target.variant_path)
        for letter, idx in zip(letters[1:], chosen):
            d = pool[idx]
            sim = hamming_similarity(base_hash, phash(d.base_path))
            options[letter] = _opt_block(
                image=f"option_{letter.lower()}.png",
                kind="distractor",
                cosine=sim,
                source="nb2_pool_mined",
                person_id=d.person_id,
                generated_by="fal-ai/nano-banana-2",
                request_id=(d.base_provenance or {}).get("request_id"),
                cdn_url=d.cdn_base,
            )
            options[letter]["_local_image"] = str(d.base_path)
    else:
        for letter, idx in zip(letters, chosen):
            d = pool[idx]
            sim = hamming_similarity(base_hash, phash(d.base_path))
            options[letter] = _opt_block(
                image=f"option_{letter.lower()}.png",
                kind="distractor",
                cosine=sim,
                source="nb2_pool_mined",
                person_id=d.person_id,
                generated_by="fal-ai/nano-banana-2",
                request_id=(d.base_provenance or {}).get("request_id"),
                cdn_url=d.cdn_base,
            )
            options[letter]["_local_image"] = str(d.base_path)

    options["E"] = {"is_none_of_the_above": True}

    correct_answer = (
        next(L for L, v in options.items() if v.get("kind") == "true_match")
        if is_type_a else "E"
    )

    meta = {
        "id": sample_id,
        "schema_version": "1.0.0",
        "task_type": "mcq_likeness",
        "subject": {
            "person_id": target.person_id,
            "real_or_synthetic": "synthetic",
            "license": "CC-BY-4.0 (NB2 generation, fictional persons)",
            "source": "nb2",
        },
        "base_image": "base.png",
        "_local_base_image": str(target.base_path),
        "_base_cdn_url": target.cdn_base,
        "options": options,
        "correct_answer": correct_answer,
        "none_of_the_above_is_correct": (correct_answer == "E"),
        "metadata": {
            "tier": "hard",
            "difficulty_split": "medium",
            "type_b": (correct_answer == "E"),
            "preset": "medium_mix",
            "synthid_present": True,
            "human_reviewed": False,
            "generator_model": "fal-ai/nano-banana-2",
            "embedding_model": "phash16",
            "demographic_hint": target.demographics or {},
        },
    }
    return meta
