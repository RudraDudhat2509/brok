from brok.models import Component, ComponentType, DesignGraph
from brok.pipeline import build_result, build_traffic, review

COMPOSE = """
services:
  api: { build: . }
  db: { image: postgres:16 }
"""


def _graph():
    return DesignGraph(components=[
        Component(name="api", type=ComponentType.APP_SERVER),
        Component(name="db", type=ComponentType.RELATIONAL_DB),
    ])


def test_build_result_returns_structured_plus_text():
    res = build_result(_graph(), {"dau": 5_000_000})
    assert "report_text" in res and isinstance(res["report_text"], str)
    assert "bottleneck" in res and "max_dau" in res and "confidence" in res
    # enums serialized to strings (json mode)
    assert all(isinstance(u["type"], str) for u in res["utilizations"])


def test_build_result_high_confidence_when_dau_provided_partial_still_low():
    # only dau provided: the other NFR fields are still assumed => low confidence,
    # but the dau assumption line must be gone and dau must be honored.
    res = build_result(_graph(), {"dau": 5_000_000})
    assert res["confidence"] == "low"
    assert all("daily active users" not in a for a in res["assumptions"])


def test_build_traffic_maps_and_drops_none():
    assert build_traffic(2_000_000, None, 4.0, None, None) == {"dau": 2_000_000, "read_write_ratio": 4.0}
    assert build_traffic(None, None, None, None, None) is None


def test_review_still_returns_text():
    out = review(COMPOSE)
    assert isinstance(out, str)
    assert "Brok capacity review" in out
