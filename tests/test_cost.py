# tests/test_cost.py
from brok.lenses.cost import estimate_cost
from brok.models import Component, ComponentType, DesignGraph, NFRs
from brok.pipeline import build_result, review_from_components


def _nfrs():
    return NFRs(dau=1_000_000, requests_per_user_per_day=100,
                read_write_ratio=10.0, payload_kb=10.0, peak_factor=3.0)


def _graph():
    return DesignGraph(components=[
        Component(name="api", type=ComponentType.APP_SERVER),
        Component(name="db", type=ComponentType.RELATIONAL_DB),
    ])


def test_compute_cost_sums_known_components():
    cost = estimate_cost(_graph(), _nfrs())
    assert cost["monthly_compute_usd"] == 180.0  # 60 app + 120 db


def test_egress_matches_formula():
    nfrs = _nfrs()
    cost = estimate_cost(_graph(), nfrs)
    avg_rps = nfrs.dau * nfrs.requests_per_user_per_day / 86400
    expected_gb = avg_rps * (nfrs.payload_kb * 1024) * 2_592_000 / (1024 ** 3)
    assert abs(cost["monthly_egress_usd"] - round(expected_gb * 0.09, 2)) < 0.01


def test_total_is_compute_plus_egress():
    cost = estimate_cost(_graph(), _nfrs())
    assert abs(cost["monthly_total_usd"]
               - (cost["monthly_compute_usd"] + cost["monthly_egress_usd"])) < 0.01


def test_cited_and_no_em_dash():
    cost = estimate_cost(_graph(), _nfrs())
    assert cost["source"]
    for a in cost["assumptions"]:
        assert "—" not in a
    assert "—" not in cost["source"]


def test_build_result_has_cost_and_roast_shows_it():
    res = build_result(_graph(), {"dau": 1_000_000})
    assert "cost" in res and res["cost"]["monthly_total_usd"] > 0
    assert "WHAT IT COSTS" in res["roast_text"]


def test_empty_result_cost_is_none():
    res = review_from_components([])
    assert res["cost"] is None
