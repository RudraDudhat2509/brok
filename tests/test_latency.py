from brok.lenses.latency import KNEE, latency_multiplier


def test_knee_is_point_seven():
    assert KNEE == 0.7


def test_multiplier_matches_queueing_formula():
    assert latency_multiplier(0.5) == 2.0
    assert round(latency_multiplier(0.8), 1) == 5.0
    assert round(latency_multiplier(0.9), 1) == 10.0


def test_multiplier_none_when_unknown_or_saturated():
    assert latency_multiplier(None) is None
    assert latency_multiplier(1.0) is None
    assert latency_multiplier(3.0) is None
    assert latency_multiplier(-0.1) is None
