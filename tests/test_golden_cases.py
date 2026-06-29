from brok.benchmark.golden import GOLDEN_CASES


def test_has_all_three_categories():
    cats = {c.category for c in GOLDEN_CASES}
    assert {"consistency", "behavior", "out_of_model"} <= cats


def test_every_case_is_cited():
    assert all(c.source_url.startswith("http") for c in GOLDEN_CASES)
    assert all(c.note for c in GOLDEN_CASES)


def test_consistency_cases_have_expected_outcomes():
    cons = [c for c in GOLDEN_CASES if c.category == "consistency"]
    assert len(cons) >= 3
    assert all(c.scored_for_accuracy and c.expected_capacity_dau for c in cons)


def test_out_of_model_cases_not_scored_for_accuracy():
    oom = [c for c in GOLDEN_CASES if c.category == "out_of_model"]
    assert len(oom) >= 2
    assert all(not c.scored_for_accuracy for c in oom)
