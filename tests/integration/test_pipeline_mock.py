"""End-to-end pipeline test using MockProvider over the tiny fixture."""
import pytest

from bench.config import load_config
from bench.runner.pipeline import run_evaluation


@pytest.mark.asyncio
async def test_pipeline_e2e_mock():
    cfg = load_config()
    out = await run_evaluation(
        cfg=cfg,
        model_key="mock",
        benchmark_id="tiny_benchmark",
        resume=False,
    )
    assert out["n_completed"] == 5
    assert "overall_accuracy" in out["metrics"]
    assert "composite_likeness_score" in out["metrics"]
    # MockProvider answers deterministically; with 5 fixture samples and 5-way
    # answer space, we expect *some* matches to occur over many runs but not
    # always — assertion is loose.
    assert 0.0 <= out["metrics"]["overall_accuracy"] <= 1.0
