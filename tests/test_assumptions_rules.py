from __future__ import annotations

from brok.assumptions.models import Literal
from brok.assumptions.rules import (
    CLAUSES,
    DOMAINS,
    EXCLUSIONS,
    IMPLICATIONS,
    NUMERIC_RULES,
    PREDICATES,
    clauses_for_domain,
)


def test_every_rule_carries_a_non_empty_citation():
    for rule in (*IMPLICATIONS, *EXCLUSIONS, *NUMERIC_RULES):
        assert rule.citation.strip(), f"{rule.rule_id} has no citation"


def test_rule_ids_are_unique_across_all_tables():
    ids = [r.rule_id for r in (*IMPLICATIONS, *EXCLUSIONS, *NUMERIC_RULES)]
    assert len(ids) == len(set(ids)), f"duplicate rule ids: {ids}"


def test_every_predicate_used_by_a_rule_is_declared_in_the_vocabulary():
    used: set[str] = set()
    for imp in IMPLICATIONS:
        used.update(lit.predicate for lit in imp.when)
        used.add(imp.implies.predicate)
    for exc in EXCLUSIONS:
        used.update(lit.predicate for lit in exc.literals)
    for num in NUMERIC_RULES:
        used.add(num.produces)
    assert used <= set(PREDICATES), f"undeclared predicates: {used - set(PREDICATES)}"


def test_every_rule_belongs_to_a_known_domain():
    for rule in (*IMPLICATIONS, *EXCLUSIONS, *NUMERIC_RULES):
        assert rule.domain in DOMAINS, f"{rule.rule_id} has unknown domain {rule.domain}"


def test_all_four_phase_one_domains_have_rules():
    covered = {r.domain for r in (*IMPLICATIONS, *EXCLUSIONS, *NUMERIC_RULES)}
    assert {"cap", "pacelc", "quorum", "idempotency"} <= covered


def test_clauses_compile_from_both_authoring_tables():
    assert len(CLAUSES) == len(IMPLICATIONS) + len(EXCLUSIONS)


def test_no_clause_contains_a_predicate_twice():
    for clause in CLAUSES:
        names = [lit.predicate for lit in clause.literals]
        assert len(names) == len(set(names)), f"{clause.rule_id} repeats a predicate"


def test_no_clause_is_trivially_satisfiable_by_containing_a_literal_and_its_negation():
    for clause in CLAUSES:
        for lit in clause.literals:
            assert lit.negate() not in clause.literals, f"{clause.rule_id} is vacuous"


def test_clauses_for_domain_filters():
    assert {c.rule_id for c in clauses_for_domain("cap")} == {"C1", "C2"}


# --- the specific rules the design turns on -------------------------------------


def test_cap_theorem_is_a_three_way_exclusion():
    cap = next(e for e in EXCLUSIONS if e.rule_id == "C1")
    assert set(cap.literals) == {
        Literal(predicate="strong_consistency"),
        Literal(predicate="available_under_partition"),
        Literal(predicate="partition_tolerant"),
    }
    assert "CAP theorem" in cap.citation


def test_pacelc_else_branch_cites_the_latency_lower_bound_not_just_the_framework():
    p1 = next(e for e in EXCLUSIONS if e.rule_id == "P1")
    assert set(p1.literals) == {
        Literal(predicate="replicated"),
        Literal(predicate="strong_consistency"),
        Literal(predicate="low_latency_under_normal_operation"),
    }
    assert "Attiya" in p1.citation


def test_quorum_overlap_never_implies_strong_consistency():
    """Finding 1. W+R>N buys read-your-confirmed-writes, not linearizability.

    Dynamo-style quorums admit concurrent writes with no defined order, partially
    applied writes, and sloppy quorums. A rule claiming strong_consistency here
    would attach a real citation to a false guarantee.
    """
    for imp in IMPLICATIONS:
        if imp.implies == Literal(predicate="strong_consistency"):
            assert Literal(predicate="quorum_overlap") not in imp.when, (
                f"{imp.rule_id} claims strong consistency from quorum overlap"
            )


def test_strong_consistency_implies_reading_the_latest_confirmed_write_one_way_only():
    q3 = next(i for i in IMPLICATIONS if i.rule_id == "Q3")
    assert q3.when == (Literal(predicate="strong_consistency"),)
    assert q3.implies == Literal(predicate="read_sees_latest_acked_write")


def test_quorum_overlap_requires_a_strict_quorum_to_guarantee_fresh_reads():
    q1 = next(i for i in IMPLICATIONS if i.rule_id == "Q1")
    assert set(q1.when) == {
        Literal(predicate="quorum_overlap"),
        Literal(predicate="sloppy_quorum", polarity=False),
    }
    assert q1.implies == Literal(predicate="read_sees_latest_acked_write")


def test_dedup_citation_states_the_window_caveat():
    i3 = next(i for i in IMPLICATIONS if i.rule_id == "I3")
    assert "window" in i3.citation.lower()


def test_exactly_once_citation_names_two_generals():
    i4 = next(e for e in EXCLUSIONS if e.rule_id == "I4")
    assert "Two Generals" in i4.citation


# --- numeric derivation ----------------------------------------------------------


def test_quorum_overlap_rule_computes_w_plus_r_greater_than_n():
    rule = next(r for r in NUMERIC_RULES if r.rule_id == "Q-D1")
    value, evidence = rule.compute({"n": 3, "w": 2, "r": 2})
    assert value is True
    assert "2" in evidence and "3" in evidence


def test_quorum_overlap_rule_is_false_when_the_sets_can_miss_each_other():
    rule = next(r for r in NUMERIC_RULES if r.rule_id == "Q-D1")
    value, _ = rule.compute({"n": 3, "w": 1, "r": 1})
    assert value is False


def test_write_quorum_majority_rule_computes_w_greater_than_half_n():
    rule = next(r for r in NUMERIC_RULES if r.rule_id == "Q-D2")
    assert rule.compute({"n": 3, "w": 2, "r": 2})[0] is True
    assert rule.compute({"n": 3, "w": 1, "r": 3})[0] is False


def test_numeric_rules_declare_the_attributes_they_need():
    for rule in NUMERIC_RULES:
        assert rule.requires, f"{rule.rule_id} declares no required attributes"
