from sindri.benchmark.golden import GoldenCase
from sindri.benchmark.runner import run_case, run_benchmark, format_scorecard


def _consistency_db_case():
    return GoldenCase(
        name="db-wall", source_url="http://e.com", category="consistency",
        components=[("app", "app_server"), ("db", "relational_db")],
        nfrs={"dau": 500000, "requests_per_user_per_day": 50, "read_write_ratio": 10.0,
              "payload_kb": 50.0, "peak_factor": 3.0},
        expected_bottleneck_type="relational_db", expected_capacity_dau=576000,
        expect_overload=False, scored_for_accuracy=True, note="n")


def test_run_case_reproduces_cited_db_wall():
    r = run_case(_consistency_db_case())
    assert r.bottleneck_correct is True
    assert r.within_2x is True   # ~576000 reproduced end-to-end
    assert r.cited is True


def test_run_benchmark_aggregates():
    res = run_benchmark([_consistency_db_case()])
    assert res.bottleneck_accuracy == 1.0
    assert res.within_2x_rate == 1.0
    assert res.off_by_100x_count == 0
    assert res.citeability == 1.0


def test_format_scorecard_has_no_em_dash():
    res = run_benchmark([_consistency_db_case()])
    assert "—" not in format_scorecard(res)
