import brok.server as server
from brok.pipeline import build_result, review_from_components
from brok.models import Component, ComponentType, DesignGraph


def _graph():
    return DesignGraph(components=[
        Component(name="api", type=ComponentType.APP_SERVER),
        Component(name="db", type=ComponentType.RELATIONAL_DB),
    ])


def test_build_result_includes_roast_text():
    res = build_result(_graph(), {"dau": 5_000_000})
    assert "roast_text" in res
    assert res["roast_text"].startswith("BROK:")


def test_tool_returns_roast_text():
    res = server.review_architecture(
        "services:\n  api: { build: . }\n  db: { image: postgres:16 }\n",
        expected_dau=50_000_000)
    assert "roast_text" in res and res["roast_text"].startswith("BROK:")


def test_empty_result_has_roast_text_key():
    res = review_from_components([])
    assert "roast_text" in res
