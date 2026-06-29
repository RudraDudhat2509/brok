from brok.models import Component, ComponentType, DesignGraph
from brok.pipeline import build_result, review_from_components
from brok.voice import render_roast
from brok.models import CapacityReport, Utilization


def _graph():
    return DesignGraph(components=[
        Component(name="api", type=ComponentType.APP_SERVER),
        Component(name="db", type=ComponentType.RELATIONAL_DB),
    ])


def test_build_result_includes_tradeoffs():
    res = build_result(_graph(), {"dau": 2_000_000})
    assert "tradeoffs" in res
    types = [t["type"] for t in res["tradeoffs"]]
    assert "app_server" in types and "relational_db" in types


def test_empty_result_has_tradeoffs_key():
    res = review_from_components([])
    assert res["tradeoffs"] == []


def test_render_roast_has_tradeoff_section():
    utils = [Utilization(component="db", type=ComponentType.RELATIONAL_DB,
                         load_per_sec=8000.0, ceiling_per_sec=1000.0, utilization=8.0,
                         estimated=True)]
    report = CapacityReport(bottleneck="db", max_dau=12000, utilizations=utils,
                            assumptions=[], confidence="high", notes=[])
    card = render_roast(report)
    assert "TRADE-OFFS YOU ARE MAKING" in card
    assert "single point of failure" in card  # from the relational_db cost
    assert "—" not in card


def test_render_roast_no_tradeoff_section_when_none():
    report = CapacityReport(bottleneck=None, max_dau=None, utilizations=[],
                            assumptions=[], confidence="low", notes=[])
    assert "TRADE-OFFS YOU ARE MAKING" not in render_roast(report)
