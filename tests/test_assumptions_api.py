from __future__ import annotations

from brok.assumptions.api import (
    ask_assumption,
    build_entity,
    check_design_assumptions,
    list_assumption_predicates,
)


def test_build_entity_accepts_declared_facts():
    entity = build_entity(name="pg", declared={"strong_consistency": True})
    assert entity.facts["strong_consistency"].value is True


def test_build_entity_accepts_inferred_facts_with_confidence_and_evidence():
    entity = build_entity(
        name="svc",
        inferred={
            "idempotent_handler": {
                "value": False,
                "confidence": 0.6,
                "evidence": "db/writer.py:44",
            }
        },
    )
    fact = entity.facts["idempotent_handler"]
    assert fact.value is False
    assert fact.confidence == 0.6
    assert fact.evidence == "db/writer.py:44"


def test_build_entity_defaults_inferred_confidence_below_certain():
    entity = build_entity(name="svc", inferred={"replicated": {"value": True}})
    assert entity.facts["replicated"].confidence < 1.0


def test_build_entity_kind_selects_the_entity_class():
    assert build_entity(name="q", kind="channel").kind == "channel"
    assert build_entity(name="d", kind="datastore").kind == "datastore"


def test_build_entity_carries_quorum_numbers():
    entity = build_entity(name="c", n=3, w=2, r=2)
    assert entity.attributes == {"n": 3.0, "w": 2.0, "r": 2.0}


def test_unknown_predicate_name_is_rejected_rather_than_silently_ignored():
    result = check_design_assumptions(name="x", declared={"definitely_not_real": True})
    assert result["unknown_predicates"] == ["definitely_not_real"]


def test_check_returns_contradictions_as_plain_dicts():
    result = check_design_assumptions(
        name="impossible",
        declared={
            "strong_consistency": True,
            "available_under_partition": True,
            "partition_tolerant": True,
        },
    )
    assert result["contradiction_count"] == 1
    first = result["contradictions"][0]
    assert first["rule_id"] == "C1"
    assert "Gilbert & Lynch" in first["citation"]
    assert first["all_declared"] is True


def test_check_reports_derived_facts_alongside_the_declared_ones():
    result = check_design_assumptions(name="c", declared={"replicated": True})
    derived = {f["predicate"]: f for f in result["facts"] if f["source"] == "derived"}
    assert "distributed" in derived


def test_check_on_a_coherent_design_reports_no_contradictions():
    result = check_design_assumptions(
        name="cassandra",
        declared={
            "replicated": True,
            "partition_tolerant": True,
            "available_under_partition": True,
            "sloppy_quorum": False,
        },
        n=3,
        w=2,
        r=2,
    )
    assert result["contradiction_count"] == 0


def test_ask_returns_truth_confidence_and_explanation():
    result = ask_assumption(
        predicate="strong_consistency",
        name="cassandra",
        declared={"partition_tolerant": True, "available_under_partition": True},
    )
    assert result["truth"] == "false"
    assert result["confidence"] == 1.0
    assert "CAP theorem" in result["explanation"]


def test_ask_an_undeclared_predicate_is_unknown_with_a_reason():
    result = ask_assumption(predicate="strong_consistency", name="mystery")
    assert result["truth"] == "unknown"
    assert "insufficient facts" in result["explanation"]


def test_list_predicates_groups_by_domain_with_descriptions():
    listing = list_assumption_predicates()
    assert "strong_consistency" in listing["predicates"]
    assert listing["predicates"]["strong_consistency"]
    assert set(listing["domains"]) == {"cap", "pacelc", "quorum", "idempotency"}


def test_list_predicates_documents_the_quorum_attributes():
    listing = list_assumption_predicates()
    assert set(listing["attributes"]) == {"n", "w", "r"}
