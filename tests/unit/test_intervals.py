from bench.scoring.intervals import wilson_interval


def test_wilson_basic():
    lo, hi = wilson_interval(50, 100)
    assert 0.4 < lo < 0.5
    assert 0.5 < hi < 0.6


def test_wilson_zero():
    lo, hi = wilson_interval(0, 0)
    assert (lo, hi) == (0.0, 0.0)


def test_wilson_perfect():
    lo, hi = wilson_interval(10, 10)
    assert lo > 0.7
    assert hi == 1.0
