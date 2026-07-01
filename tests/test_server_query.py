"""Integration tests for the query_tradeoffs MCP tool.

Tests the server layer directly (calls query_tradeoffs as a regular function,
same as the MCP runtime does). Verifies the tool is registered, returns the
correct shape, and that the two guard-critical cases the README advertises work.
"""
from __future__ import annotations

import brok.server as server


def test_tool_is_registered():
    tools = [t.name for t in server.mcp._tool_manager.list_tools()]
    assert "query_tradeoffs" in tools, (
        f"query_tradeoffs not registered. Tools: {tools}"
    )


def test_all_three_tools_registered():
    tools = {t.name for t in server.mcp._tool_manager.list_tools()}
    assert tools >= {"review_architecture", "review_components", "query_tradeoffs"}


def test_return_shape():
    result = server.query_tradeoffs("kafka vs pubsub")
    assert set(result.keys()) == {"matches", "comparison", "note"}
    assert isinstance(result["matches"], list)
    assert result["note"] == "Brok surfaces trade-offs. You decide."


def test_known_query_returns_entries():
    result = server.query_tradeoffs("redis vs memcached session cache")
    names = {m["name"] for m in result["matches"]}
    assert "Redis" in names
    assert "Memcached" in names


def test_comparison_block_fires_for_same_category():
    result = server.query_tradeoffs("kafka vs sqs")
    assert result["comparison"] is not None
    comp = result["comparison"].upper()
    assert "KAFKA" in comp or "SQS" in comp


def test_no_match_returns_empty_list_not_error():
    result = server.query_tradeoffs("xyzzy gobbledygook unknown 99999")
    assert isinstance(result["matches"], list)
    assert result["comparison"] is None or isinstance(result["comparison"], str)


def test_cassandra_guard_via_tool():
    result = server.query_tradeoffs("cassandra strong consistency")
    names = {m["name"] for m in result["matches"]}
    assert "Cassandra" in names
    cassandra = next(m for m in result["matches"] if m["name"] == "Cassandra")
    text = (cassandra["when_not_to_pick"] + " " + cassandra["extra"]).lower()
    assert any(w in text for w in ("eventual", "leaderless", "tunable"))


def test_cqrs_guard_via_tool():
    result = server.query_tradeoffs("use cqrs for simple crud app")
    names = {m["name"] for m in result["matches"]}
    assert "CQRS" in names
    cqrs = next(m for m in result["matches"] if m["name"] == "CQRS")
    text = (cqrs["when_not_to_pick"] + " " + cqrs["extra"]).lower()
    assert any(w in text for w in ("simple", "crud", "overhead"))


def test_each_match_has_citation_url():
    result = server.query_tradeoffs("postgres sharding strategy")
    for m in result["matches"]:
        assert m["citation"].startswith("http"), (
            f"{m['name']}: citation must be a URL"
        )


def test_existing_tools_unaffected():
    """review_architecture and review_components must still work."""
    result = server.review_components(
        [{"name": "api", "type": "app_server"}, {"name": "db", "type": "relational_db"}],
        expected_dau=100_000,
    )
    assert "bottleneck" in result
    assert "roast_text" in result
