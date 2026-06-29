from sindri.benchmark.runner import run_benchmark


def test_meets_section_3_1_thresholds_on_golden_set():
    res = run_benchmark()  # the real GOLDEN_CASES
    # §3.1 acceptance bar, measured on the cases Sindri can faithfully score:
    assert res.bottleneck_accuracy >= 0.8
    assert res.within_2x_rate >= 0.8
    assert res.off_by_100x_count == 0
    assert res.citeability == 1.0


def test_does_not_cry_wolf_or_overclaim():
    res = run_benchmark()
    # behavior + out-of-model honesty: every case's overload verdict matches expectation
    # (tiny app fits; Instagram app flagged but throughput ok; Discord store documented/excluded).
    assert res.overload_accuracy == 1.0
