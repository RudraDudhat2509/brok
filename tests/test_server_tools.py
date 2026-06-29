import sindri.server as server


def test_review_architecture_passthrough_dau_drops_assumption():
    res = server.review_architecture(
        "services:\n  api: { build: . }\n  db: { image: postgres:16 }\n",
        expected_dau=50_000_000)
    assert isinstance(res, dict)
    assert res["bottleneck"] is not None
    assert all("daily active users" not in a for a in res["assumptions"])
    assert "report_text" in res


def test_review_components_tool_builds_and_scores():
    res = server.review_components(
        [{"name": "api", "type": "app_server"}, {"name": "db", "type": "relational_db"}],
        expected_dau=2_000_000)
    assert res["bottleneck"] in ("api", "db")


def test_server_imports_clean():
    assert hasattr(server, "mcp")
