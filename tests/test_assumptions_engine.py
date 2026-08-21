from __future__ import annotations

from brok.assumptions.engine import ask, check_contradictions, explain, saturate
from brok.assumptions.entities import Channel, DataStore
from brok.assumptions.models import FactSource, Truth

# --- closed world: unknown is not false ------------------------------------------


def test_undeclared_predicate_is_unknown_not_false():
    store = DataStore(name="mystery")
    result = ask("strong_consistency", store)
    assert result.truth is Truth.UNKNOWN
    assert result.confidence is None


def test_asking_an_unknown_predicate_name_is_unknown_not_an_error():
    assert ask("not_a_real_predicate", DataStore(name="x")).truth is Truth.UNKNOWN


def test_declared_fact_is_returned_verbatim():
    store = DataStore(name="pg").declare("strong_consistency", True)
    result = ask("strong_consistency", store)
    assert result.truth is Truth.TRUE
    assert result.source is FactSource.DECLARED
    assert result.confidence == 1.0


# --- forward chaining ------------------------------------------------------------


def test_cap_derives_the_third_predicate_from_the_other_two():
    """Declaring AP behaviour should rule out strong consistency, unprompted."""
    store = (
        DataStore(name="cassandra")
        .declare("partition_tolerant", True)
        .declare("available_under_partition", True)
    )
    result = ask("strong_consistency", store)
    assert result.truth is Truth.FALSE
    assert result.source is FactSource.DERIVED
    assert any("CAP theorem" in c for c in result.citations)


def test_replication_implies_distribution_which_chains_into_cap():
    store = DataStore(name="s").declare("replicated", True)
    assert ask("distributed", store).truth is Truth.TRUE


def test_multi_step_chain_is_recorded_in_order():
    store = (
        DataStore(name="s")
        .declare("replicated", True)
        .with_quorum(n=3, w=1, r=1)
    )
    result = ask("stale_reads_possible", store)
    assert result.truth is Truth.TRUE
    rule_ids = [d.rule_id for d in result.derivation]
    assert "Q-D1" in rule_ids and "Q2" in rule_ids


def test_engine_does_not_mutate_the_entity_it_is_given():
    store = DataStore(name="s").declare("replicated", True)
    ask("distributed", store)
    assert "distributed" not in store.facts


# --- numeric derivation ----------------------------------------------------------


def test_quorum_numbers_derive_overlap_with_arithmetic_as_evidence():
    store = DataStore(name="c").with_quorum(n=3, w=2, r=2)
    result = ask("quorum_overlap", store)
    assert result.truth is Truth.TRUE
    assert result.source is FactSource.DERIVED
    assert "W(2) + R(2) = 4 vs N(3)" in (result.evidence or "")


def test_numeric_rule_is_skipped_when_attributes_are_missing():
    store = DataStore(name="c").with_quorum(n=3, w=2)  # no r
    assert ask("quorum_overlap", store).truth is Truth.UNKNOWN


def test_strict_quorum_with_overlap_gives_fresh_reads_but_not_strong_consistency():
    """Finding 1 end to end: the honest guarantee, and nothing stronger."""
    store = (
        DataStore(name="cassandra")
        .declare("replicated", True)
        .declare("sloppy_quorum", False)
        .with_quorum(n=3, w=2, r=2)
    )
    assert ask("read_sees_latest_acked_write", store).truth is Truth.TRUE
    assert ask("strong_consistency", store).truth is Truth.UNKNOWN


def test_sloppy_quorum_is_inferred_when_fresh_reads_are_known_absent():
    store = (
        DataStore(name="d")
        .declare("read_sees_latest_acked_write", False)
        .with_quorum(n=3, w=2, r=2)
    )
    assert ask("sloppy_quorum", store).truth is Truth.TRUE


# --- confidence propagation ------------------------------------------------------


def test_derived_fact_inherits_the_weakest_input_confidence():
    channel = (
        Channel(name="orders")
        .declare("at_least_once_delivery", True)
        .infer("idempotent_handler", False, confidence=0.6, evidence="db/writer.py:44")
        .infer("deduplication", False, confidence=0.9, evidence="no dedup table found")
    )
    result = ask("duplicate_side_effects_possible", channel)
    assert result.truth is Truth.TRUE
    assert result.confidence == 0.6


def test_declared_only_chain_keeps_full_confidence():
    channel = (
        Channel(name="orders")
        .declare("at_least_once_delivery", True)
        .declare("idempotent_handler", False)
        .declare("deduplication", False)
    )
    assert ask("duplicate_side_effects_possible", channel).confidence == 1.0


# --- contradictions --------------------------------------------------------------


def test_no_contradictions_on_a_coherent_design():
    store = (
        DataStore(name="cassandra")
        .declare("replicated", True)
        .declare("partition_tolerant", True)
        .declare("available_under_partition", True)
        .declare("sloppy_quorum", False)
        .with_quorum(n=3, w=2, r=2)
    )
    assert check_contradictions(store) == []


def test_contradiction_is_returned_not_raised():
    store = (
        DataStore(name="impossible")
        .declare("strong_consistency", True)
        .declare("available_under_partition", True)
        .declare("partition_tolerant", True)
    )
    found = check_contradictions(store)
    assert len(found) == 1
    assert found[0].rule_id == "C1"


def test_contradiction_between_declared_facts_is_marked_fully_certain():
    store = (
        DataStore(name="impossible")
        .declare("strong_consistency", True)
        .declare("available_under_partition", True)
        .declare("partition_tolerant", True)
    )
    c = check_contradictions(store)[0]
    assert c.all_declared is True
    assert c.confidence == 1.0


def test_contradiction_resting_on_a_guess_is_marked_less_certain():
    store = (
        DataStore(name="maybe")
        .declare("strong_consistency", True)
        .declare("available_under_partition", True)
        .infer("partition_tolerant", True, confidence=0.6, evidence="3 replicas in yaml")
    )
    c = check_contradictions(store)[0]
    assert c.all_declared is False
    assert c.confidence == 0.6


def test_arithmetic_derived_facts_do_not_taint_a_contradiction_as_a_guess():
    """Quorum arithmetic on stated numbers is certain, so a contradiction reached
    through it is still a hard one. Only an INFERRED fact should soften the report."""
    store = (
        DataStore(name="wishful")
        .declare("replicated", True)
        .declare("strong_consistency", True)
        .with_quorum(n=3, w=1, r=1)
    )
    c = check_contradictions(store)[0]
    assert c.confidence == 1.0
    assert c.all_declared is True


def test_an_inferred_fact_anywhere_in_the_chain_still_softens_the_contradiction():
    store = (
        DataStore(name="wishful")
        .infer("replicated", True, confidence=0.7, evidence="3 replicas in compose")
        .declare("strong_consistency", True)
        .with_quorum(n=3, w=1, r=1)
    )
    c = check_contradictions(store)[0]
    assert c.all_declared is False
    assert c.confidence == 0.7


def test_contradiction_names_the_conflicting_facts_and_cites_the_theorem():
    store = (
        DataStore(name="impossible")
        .declare("strong_consistency", True)
        .declare("available_under_partition", True)
        .declare("partition_tolerant", True)
    )
    c = check_contradictions(store)[0]
    assert set(c.conflicting) == {
        "strong_consistency",
        "available_under_partition",
        "partition_tolerant",
    }
    assert "Gilbert & Lynch" in c.citation


def test_contradictions_are_ordered_most_certain_first():
    store = (
        DataStore(name="two")
        .declare("strong_consistency", True)
        .declare("available_under_partition", True)
        .declare("partition_tolerant", True)
        .infer("low_latency_under_normal_operation", True, confidence=0.5)
        .infer("replicated", True, confidence=0.5)
    )
    found = check_contradictions(store)
    assert len(found) >= 2
    assert found[0].confidence >= found[-1].confidence


def test_a_contradicted_predicate_reports_unknown_rather_than_picking_a_side():
    store = (
        DataStore(name="impossible")
        .declare("strong_consistency", True)
        .declare("available_under_partition", True)
        .declare("partition_tolerant", True)
    )
    assert ask("strong_consistency", store).truth is Truth.UNKNOWN


# --- explain ---------------------------------------------------------------------


def test_explain_unknown_states_insufficient_facts():
    text = explain("strong_consistency", DataStore(name="mystery"))
    assert "insufficient facts" in text


def test_explain_renders_the_derivation_with_citations():
    store = (
        DataStore(name="cassandra")
        .declare("partition_tolerant", True)
        .declare("available_under_partition", True)
    )
    text = explain("strong_consistency", store)
    assert "strong_consistency" in text
    assert "false" in text.lower()
    assert "CAP theorem" in text
    assert "C1" in text


def test_explain_surfaces_a_contradiction_when_one_blocks_the_answer():
    store = (
        DataStore(name="impossible")
        .declare("strong_consistency", True)
        .declare("available_under_partition", True)
        .declare("partition_tolerant", True)
    )
    assert "contradiction" in explain("strong_consistency", store).lower()


def test_explain_reports_declared_facts_without_inventing_a_derivation():
    store = DataStore(name="pg").declare("strong_consistency", True)
    text = explain("strong_consistency", store)
    assert "declared" in text.lower()


# --- saturate is the shared primitive --------------------------------------------


def test_saturate_returns_both_facts_and_contradictions():
    store = DataStore(name="s").declare("replicated", True)
    facts, contradictions = saturate(store)
    assert "distributed" in facts
    assert contradictions == []
