"""Aggregate metrics computed from per-sample SampleResult lists."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from ..models import SampleResult
from .intervals import wilson_interval

_LETTERS = ["A", "B", "C", "D", "E"]


def aggregate(results: list[SampleResult], samples_root: Path) -> dict:
    n = len(results)
    if n == 0:
        return {"overall_accuracy": 0.0, "overall_ci95": [0.0, 0.0]}
    correct = sum(1 for r in results if r.correct)
    overall = correct / n

    by_tier_correct: dict[str, int] = defaultdict(int)
    by_tier_total: dict[str, int] = defaultdict(int)
    by_presence_correct: dict[str, int] = defaultdict(int)
    by_presence_total: dict[str, int] = defaultdict(int)
    none_correct_when_correct = 0
    none_total_when_correct = 0
    none_when_incorrect = 0
    total_when_e_wrong = 0
    refusals = 0
    parse_failures = 0
    confusion = [[0] * 5 for _ in range(5)]

    for r in results:
        tier = r.tier or "unknown"
        by_tier_total[tier] += 1
        if r.correct:
            by_tier_correct[tier] += 1
        if r.presence:
            by_presence_total[r.presence] += 1
            if r.correct:
                by_presence_correct[r.presence] += 1
        if r.answer == "E":
            none_total_when_correct += 1
            if r.predicted == "E":
                none_correct_when_correct += 1
        else:
            total_when_e_wrong += 1
            if r.predicted == "E":
                none_when_incorrect += 1
        if r.refusal:
            refusals += 1
        if r.parse_failure:
            parse_failures += 1
        if r.predicted in _LETTERS and r.answer in _LETTERS:
            confusion[_LETTERS.index(r.answer)][_LETTERS.index(r.predicted)] += 1

    accuracy_by_tier = {
        t: by_tier_correct[t] / by_tier_total[t] for t in by_tier_total if by_tier_total[t]
    }
    return {
        "overall_accuracy": overall,
        "overall_ci95": list(wilson_interval(correct, n)),
        "accuracy_by_tier": accuracy_by_tier,
        "accuracy_when_present": (
            by_presence_correct["correct_present"] / by_presence_total["correct_present"]
            if by_presence_total.get("correct_present") else 0.0
        ),
        "accuracy_when_absent": (
            by_presence_correct["correct_absent"] / by_presence_total["correct_absent"]
            if by_presence_total.get("correct_absent") else 0.0
        ),
        "none_selection_rate": {
            "when_correct": (none_correct_when_correct / none_total_when_correct
                             if none_total_when_correct else 0.0),
            "when_incorrect": (none_when_incorrect / total_when_e_wrong
                               if total_when_e_wrong else 0.0),
        },
        "refusal_rate": refusals / n,
        "parse_failure_rate": parse_failures / n,
        "confusion_matrix": confusion,
        "n_samples": n,
        "n_correct": correct,
    }
