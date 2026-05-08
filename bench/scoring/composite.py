"""Composite Likeness Score: rewards accuracy AND calibration on E."""
from __future__ import annotations


def composite_likeness_score(summary: dict, scoring_cfg: dict) -> float:
    """Composite score that rewards both present/absent accuracy AND E-calibration.

    fp_E = P(predict E | E is wrong)         — false positive rate on E
    fn_E = P(predict not E | E is correct)   — false negative rate on E
    """
    w_p = scoring_cfg.get("w_present", 0.5)
    w_a = scoring_cfg.get("w_absent", 0.5)
    lam = scoring_cfg.get("lambda_e", 0.25)
    acc_p = summary.get("accuracy_when_present", 0.0)
    acc_a = summary.get("accuracy_when_absent", 0.0)
    nsr = summary.get("none_selection_rate", {})
    fp = nsr.get("when_incorrect", 0.0)
    fn = 1.0 - nsr.get("when_correct", 0.0)
    penalty = lam * (fp + fn) / 2.0
    return max(0.0, round(w_p * acc_p + w_a * acc_a - penalty, 4))
