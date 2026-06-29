from brok.pipeline import review_from_compose, review_from_components

COMPOSE = """
services:
  api: { build: . }
  db: { image: postgres:16 }
"""


def test_compose_entry_honors_provided_dau():
    res = review_from_compose(COMPOSE, {"dau": 50_000_000})
    assert res["bottleneck"] is not None
    assert all("daily active users" not in a for a in res["assumptions"])


def test_compose_entry_empty_is_friendly():
    res = review_from_compose("::: not yaml :::")
    assert res["bottleneck"] is None
    assert "couldn't find any components" in res["report_text"].lower()


def test_components_entry_builds_graph():
    res = review_from_components(
        [{"name": "api", "type": "app_server"}, {"name": "db", "type": "relational_db"}],
        {"dau": 2_000_000})
    assert res["bottleneck"] in ("api", "db")
    assert "report_text" in res


def test_components_entry_unknown_type_abstains():
    res = review_from_components([{"name": "mystery", "type": "cassandra"}])
    # unknown component is not scored => no bottleneck fabricated
    assert res["bottleneck"] is None


def test_components_entry_empty_list_is_friendly():
    res = review_from_components([])
    assert res["bottleneck"] is None
    assert "couldn't find any components" in res["report_text"].lower()
