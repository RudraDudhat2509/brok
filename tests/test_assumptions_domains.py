"""Every rule in the phase 1 tables, exercised individually.

A bug in a rule table corrupts every conclusion downstream of it, so each implication,
exclusion, and numeric rule gets its own scenario, plus a coverage guard that fails if
a rule is ever added without one.
"""

from __future__ import annotations

import pytest

from brok.assumptions.engine import ask, check_contradictions, saturate
from brok.assumptions.entities import Channel, DataStore
from brok.assumptions.models import Truth
from brok.assumptions.rules import EXCLUSIONS, IMPLICATIONS, NUMERIC_RULES


def fired_rules(entity) -> set[str]:
    """Rule ids that actually produced something for this entity."""
    facts, contradictions = saturate(entity)
    fired = {c.rule_id for c in contradictions}
    fired |= {f.derivation.rule_id for f in facts.values() if f.derivation}
    return fired


# --- CAP -------------------------------------------------------------------------


def test_c1_cap_theorem_forbids_all_three():
    store = (
        DataStore(name="impossible")
        .declare("strong_consistency", True)
        .declare("available_under_partition", True)
        .declare("partition_tolerant", True)
    )
    assert "C1" in {c.rule_id for c in check_contradictions(store)}


def test_c1_derives_the_missing_leg_rather_than_needing_a_written_contrapositive():
    cp = (
        DataStore(name="cp")
        .declare("strong_consistency", True)
        .declare("partition_tolerant", True)
    )
    assert ask("available_under_partition", cp).truth is Truth.FALSE


def test_c2_single_node_store_is_not_partition_tolerant():
    store = DataStore(name="sqlite").declare("distributed", False)
    assert ask("partition_tolerant", store).truth is Truth.FALSE
    assert "C2" in fired_rules(store)


# --- PACELC ----------------------------------------------------------------------


def test_p1_replicated_linearizable_store_cannot_also_be_low_latency():
    store = (
        DataStore(name="greedy")
        .declare("replicated", True)
        .declare("strong_consistency", True)
        .declare("low_latency_under_normal_operation", True)
    )
    found = [c for c in check_contradictions(store) if c.rule_id == "P1"]
    assert found and "Attiya" in found[0].citation


def test_p2_replica_without_fresh_read_guarantee_can_serve_stale_data():
    store = (
        DataStore(name="replica")
        .declare("replicated", True)
        .declare("read_sees_latest_acked_write", False)
    )
    assert ask("stale_reads_possible", store).truth is Truth.TRUE
    assert "P2" in fired_rules(store)


def test_p3_replication_entails_distribution():
    store = DataStore(name="r").declare("replicated", True)
    assert ask("distributed", store).truth is Truth.TRUE
    assert "P3" in fired_rules(store)


# --- Quorum ----------------------------------------------------------------------


def test_qd1_overlap_is_computed_from_the_numbers():
    store = DataStore(name="q").with_quorum(n=5, w=3, r=3)
    assert ask("quorum_overlap", store).truth is Truth.TRUE


def test_qd2_write_majority_is_computed_from_the_numbers():
    store = DataStore(name="q").with_quorum(n=3, w=2)
    assert ask("write_quorum_majority", store).truth is Truth.TRUE


def test_q1_overlap_plus_strict_quorum_gives_fresh_reads():
    store = DataStore(name="q").declare("sloppy_quorum", False).with_quorum(n=3, w=2, r=2)
    assert ask("read_sees_latest_acked_write", store).truth is Truth.TRUE
    assert "Q1" in fired_rules(store)


def test_q2_no_overlap_on_a_replicated_store_admits_stale_reads():
    store = DataStore(name="q").declare("replicated", True).with_quorum(n=3, w=1, r=1)
    assert ask("stale_reads_possible", store).truth is Truth.TRUE
    assert "Q2" in fired_rules(store)


def test_q3_strong_consistency_entails_fresh_reads():
    store = DataStore(name="q").declare("strong_consistency", True)
    assert ask("read_sees_latest_acked_write", store).truth is Truth.TRUE
    assert "Q3" in fired_rules(store)


def test_q4_fresh_reads_and_stale_reads_cannot_both_hold():
    store = (
        DataStore(name="q")
        .declare("read_sees_latest_acked_write", True)
        .declare("stale_reads_possible", True)
    )
    assert "Q4" in {c.rule_id for c in check_contradictions(store)}


def test_quorum_overlap_alone_does_not_yield_strong_consistency():
    """Finding 1, stated as an executable guarantee.

    A W=2 R=2 N=3 store is the textbook 'strongly consistent quorum' claim. The engine
    must refuse to make it: overlap gives fresh reads, and linearizability additionally
    requires an ordering for concurrent writes that a Dynamo-style quorum never
    establishes.
    """
    store = (
        DataStore(name="cassandra")
        .declare("replicated", True)
        .declare("sloppy_quorum", False)
        .with_quorum(n=3, w=2, r=2)
    )
    assert ask("read_sees_latest_acked_write", store).truth is Truth.TRUE
    assert ask("strong_consistency", store).truth is Truth.UNKNOWN


# --- Idempotency -----------------------------------------------------------------


def test_i1_at_least_once_without_idempotence_or_dedup_duplicates_side_effects():
    ch = (
        Channel(name="payments")
        .declare("at_least_once_delivery", True)
        .declare("idempotent_handler", False)
        .declare("deduplication", False)
    )
    assert ask("duplicate_side_effects_possible", ch).truth is Truth.TRUE
    assert "I1" in fired_rules(ch)


def test_i2_idempotent_handler_makes_redelivery_harmless():
    ch = (
        Channel(name="payments")
        .declare("at_least_once_delivery", True)
        .declare("idempotent_handler", True)
    )
    assert ask("duplicate_side_effects_possible", ch).truth is Truth.FALSE
    assert "I2" in fired_rules(ch)


def test_i3_dedup_makes_redelivery_harmless_within_its_window():
    ch = (
        Channel(name="payments")
        .declare("at_least_once_delivery", True)
        .declare("deduplication", True)
    )
    result = ask("duplicate_side_effects_possible", ch)
    assert result.truth is Truth.FALSE
    assert any("window" in c.lower() for c in result.citations)


def test_i4_exactly_once_processing_cannot_coexist_with_duplicate_effects():
    ch = (
        Channel(name="payments")
        .declare("exactly_once_processing", True)
        .declare("duplicate_side_effects_possible", True)
    )
    found = [c for c in check_contradictions(ch) if c.rule_id == "I4"]
    assert found and "Two Generals" in found[0].citation


def test_i5_the_two_delivery_guarantees_are_mutually_exclusive():
    ch = (
        Channel(name="q")
        .declare("at_least_once_delivery", True)
        .declare("at_most_once_delivery", True)
    )
    assert "I5" in {c.rule_id for c in check_contradictions(ch)}


def test_i6_at_most_once_can_lose_messages():
    ch = Channel(name="fire_and_forget").declare("at_most_once_delivery", True)
    assert ask("message_loss_possible", ch).truth is Truth.TRUE
    assert "I6" in fired_rules(ch)


# --- one deliberately contradictory fact set per domain --------------------------


@pytest.mark.parametrize(
    "domain,entity,expected_rule",
    [
        (
            "cap",
            DataStore(name="cap_break")
            .declare("strong_consistency", True)
            .declare("available_under_partition", True)
            .declare("partition_tolerant", True),
            "C1",
        ),
        (
            "pacelc",
            DataStore(name="pacelc_break")
            .declare("replicated", True)
            .declare("strong_consistency", True)
            .declare("low_latency_under_normal_operation", True),
            "P1",
        ),
        (
            "quorum",
            DataStore(name="quorum_break")
            .declare("replicated", True)
            .declare("strong_consistency", True)
            .with_quorum(n=3, w=1, r=1),
            "Q4",
        ),
        (
            "idempotency",
            Channel(name="idem_break")
            .declare("at_least_once_delivery", True)
            .declare("idempotent_handler", False)
            .declare("deduplication", False)
            .declare("exactly_once_processing", True),
            "I4",
        ),
    ],
)
def test_each_domain_detects_its_own_contradiction(domain, entity, expected_rule):
    found = check_contradictions(entity)
    assert found, f"{domain} contradiction went undetected"
    assert expected_rule in {c.rule_id for c in found}
    assert all(c.citation.strip() for c in found)


def test_quorum_contradiction_crosses_domains_from_arithmetic_to_cap():
    """W=1 R=1 N=3 cannot support a strong_consistency claim, and the engine gets
    there from the numbers alone: overlap fails, so stale reads are possible, which
    collides with the freshness that linearizability entails."""
    store = (
        DataStore(name="wishful")
        .declare("replicated", True)
        .declare("strong_consistency", True)
        .with_quorum(n=3, w=1, r=1)
    )
    fired = fired_rules(store)
    assert {"Q-D1", "Q2", "Q3", "Q4"} <= fired


# --- coverage guard --------------------------------------------------------------


def test_every_rule_in_every_table_is_exercised_by_this_module():
    scenarios = [
        DataStore(name="a").declare("strong_consistency", True)
        .declare("available_under_partition", True).declare("partition_tolerant", True),
        DataStore(name="b").declare("distributed", False),
        DataStore(name="c").declare("replicated", True)
        .declare("strong_consistency", True)
        .declare("low_latency_under_normal_operation", True),
        DataStore(name="d").declare("replicated", True)
        .declare("read_sees_latest_acked_write", False),
        DataStore(name="e").declare("replicated", True),
        DataStore(name="f").with_quorum(n=5, w=3, r=3),
        DataStore(name="g").with_quorum(n=3, w=2),
        DataStore(name="h").declare("sloppy_quorum", False).with_quorum(n=3, w=2, r=2),
        DataStore(name="i").declare("replicated", True).with_quorum(n=3, w=1, r=1),
        DataStore(name="j").declare("strong_consistency", True),
        DataStore(name="k").declare("read_sees_latest_acked_write", True)
        .declare("stale_reads_possible", True),
        Channel(name="l").declare("at_least_once_delivery", True)
        .declare("idempotent_handler", False).declare("deduplication", False),
        Channel(name="m").declare("at_least_once_delivery", True)
        .declare("idempotent_handler", True),
        Channel(name="n").declare("at_least_once_delivery", True)
        .declare("deduplication", True),
        Channel(name="o").declare("exactly_once_processing", True)
        .declare("duplicate_side_effects_possible", True),
        Channel(name="p").declare("at_least_once_delivery", True)
        .declare("at_most_once_delivery", True),
        Channel(name="q").declare("at_most_once_delivery", True),
    ]
    fired: set[str] = set()
    for entity in scenarios:
        fired |= fired_rules(entity)

    declared = {r.rule_id for r in (*IMPLICATIONS, *EXCLUSIONS, *NUMERIC_RULES)}
    assert declared <= fired, f"rules never exercised: {sorted(declared - fired)}"
