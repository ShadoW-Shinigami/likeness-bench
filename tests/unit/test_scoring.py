from bench.models import SampleResult
from bench.scoring.composite import composite_likeness_score
from bench.scoring.metrics import aggregate


def _r(sid, ans, pred, presence="correct_present", tier="medium"):
    return SampleResult(
        sample_id=sid, tier=tier, presence=presence, answer=ans,
        predicted=pred, correct=(ans == pred),
        raw_output=pred or "",
    )


def test_aggregate_overall():
    results = [
        _r("1", "A", "A"),
        _r("2", "B", "B"),
        _r("3", "C", "D"),
        _r("4", "E", "E", presence="correct_absent"),
        _r("5", "E", "A", presence="correct_absent"),
    ]
    out = aggregate(results, samples_root=None)
    assert out["overall_accuracy"] == 0.6
    assert out["accuracy_when_present"] == 2 / 3
    assert out["accuracy_when_absent"] == 0.5


def test_composite_penalises_e_bias():
    summary = {
        "accuracy_when_present": 0.5,
        "accuracy_when_absent": 0.5,
        "none_selection_rate": {"when_correct": 0.0, "when_incorrect": 1.0},
    }
    score = composite_likeness_score(summary, {"w_present": 0.5, "w_absent": 0.5, "lambda_e": 0.25})
    assert score < 0.5  # symmetric E-bias punished

    summary2 = {
        "accuracy_when_present": 0.5,
        "accuracy_when_absent": 0.5,
        # perfectly calibrated on E: always picks E when E is correct, never otherwise
        "none_selection_rate": {"when_correct": 1.0, "when_incorrect": 0.0},
    }
    score2 = composite_likeness_score(summary2, {"w_present": 0.5, "w_absent": 0.5, "lambda_e": 0.25})
    assert score2 == 0.5  # no penalty when E-calibrated
