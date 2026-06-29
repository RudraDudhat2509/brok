from brok.models import CapacityReport, ComponentType, Utilization
from brok.benchmark.golden import GoldenCase
from brok.benchmark.scorer import score_case


def _case(**kw):
    base = dict(name="x", source_url="http://e.com", category="consistency",
                components=[("db", "relational_db")],
                nfrs={"dau": 1, "requests_per_user_per_day": 1, "read_write_ratio": 1.0,
                      "payload_kb": 1.0, "peak_factor": 1.0},
                expected_bottleneck_type="relational_db", expected_capacity_dau=576000,
                expect_overload=False, scored_for_accuracy=True, note="n")
    base.update(kw)
    return GoldenCase(**base)


def _report(bottleneck, max_dau, util):
    u = Utilization(component="db", type=ComponentType.RELATIONAL_DB,
                    load_per_sec=1.0, ceiling_per_sec=1000.0, utilization=util,
                    estimated=True)
    return CapacityReport(bottleneck=bottleneck, max_dau=max_dau, utilizations=[u],
                          assumptions=[], confidence="high", notes=[])


def test_correct_bottleneck_and_capacity():
    r = score_case(_case(), _report("db", 600000, 0.5))
    assert r.bottleneck_correct is True
    assert r.within_2x is True
    assert r.off_by_100x is False
    assert r.cited is True


def test_wrong_capacity_outside_2x():
    r = score_case(_case(), _report("db", 50000, 0.5))  # exp 576k, far under
    assert r.within_2x is False


def test_off_by_100x_flagged():
    r = score_case(_case(), _report("db", 100, 0.5))  # 5760x under
    assert r.off_by_100x is True


def test_abstain_case_correct_when_no_bottleneck():
    c = _case(expected_bottleneck_type=None, expected_capacity_dau=None)
    r = score_case(c, _report(None, None, None))
    assert r.bottleneck_correct is True


def test_overload_correct():
    c = _case(expect_overload=True)
    r = score_case(c, _report("db", 600000, 8.0))  # util > 1 => overloaded
    assert r.overload_correct is True
