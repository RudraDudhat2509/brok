import brok.server as server


def test_check_assumptions_tool_catches_the_cap_contradiction():
    res = server.check_assumptions(
        name="impossible",
        declared={
            "strong_consistency": True,
            "available_under_partition": True,
            "partition_tolerant": True,
        },
    )
    assert res["contradiction_count"] == 1
    assert res["contradictions"][0]["rule_id"] == "C1"


def test_check_assumptions_tool_passes_quorum_numbers_through():
    res = server.check_assumptions(name="c", declared={"replicated": True}, n=3, w=1, r=1)
    stale = next(f for f in res["facts"] if f["predicate"] == "stale_reads_possible")
    assert stale["value"] is True
    assert stale["rule_id"] == "Q2"


def test_ask_assumption_tool_returns_three_valued_truth():
    res = server.ask_assumption(predicate="strong_consistency", name="mystery")
    assert res["truth"] == "unknown"


def test_list_assumption_predicates_tool_exposes_the_vocabulary():
    res = server.list_assumption_predicates()
    assert "quorum_overlap" in res["predicates"]


def test_assumption_tools_are_registered_with_the_mcp_server():
    for name in ("check_assumptions", "ask_assumption", "list_assumption_predicates"):
        assert callable(getattr(server, name))
