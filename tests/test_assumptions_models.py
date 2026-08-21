from __future__ import annotations

import pytest
from pydantic import ValidationError

from brok.assumptions.models import (
    Clause,
    Exclusion,
    Fact,
    FactSource,
    Implication,
    Literal,
    Truth,
)


def test_literal_negate_flips_polarity_and_keeps_predicate():
    lit = Literal(predicate="strong_consistency")
    assert lit.polarity is True
    assert lit.negate() == Literal(predicate="strong_consistency", polarity=False)


def test_literal_is_hashable_so_clauses_can_be_deduped():
    a = Literal(predicate="replicated")
    b = Literal(predicate="replicated")
    assert len({a, b}) == 1


def test_literal_str_reads_as_english():
    assert str(Literal(predicate="replicated")) == "replicated"
    assert str(Literal(predicate="replicated", polarity=False)) == "not replicated"


def test_declared_fact_defaults_to_full_confidence():
    fact = Fact(value=True, source=FactSource.DECLARED)
    assert fact.confidence == 1.0


def test_confidence_outside_zero_to_one_is_rejected_at_construction():
    with pytest.raises(ValidationError):
        Fact(value=True, source=FactSource.INFERRED, confidence=1.5)


def test_derived_is_a_distinct_third_source():
    assert FactSource.DERIVED.value == "derived"
    assert len(set(FactSource)) == 3


def test_implication_compiles_to_a_clause_with_the_consequent_negated():
    imp = Implication(
        rule_id="T1",
        domain="test",
        when=(Literal(predicate="a"), Literal(predicate="b")),
        implies=Literal(predicate="c"),
        citation="test citation",
    )
    clause = imp.to_clause()
    assert isinstance(clause, Clause)
    assert clause.literals == (
        Literal(predicate="a"),
        Literal(predicate="b"),
        Literal(predicate="c", polarity=False),
    )
    assert clause.citation == "test citation"
    assert clause.rule_id == "T1"


def test_implication_with_negated_consequent_compiles_to_positive_literal():
    imp = Implication(
        rule_id="T2",
        domain="test",
        when=(Literal(predicate="a"),),
        implies=Literal(predicate="c", polarity=False),
        citation="c",
    )
    assert imp.to_clause().literals == (Literal(predicate="a"), Literal(predicate="c"))


def test_exclusion_compiles_to_a_clause_verbatim():
    exc = Exclusion(
        rule_id="T3",
        domain="test",
        literals=(Literal(predicate="a"), Literal(predicate="b")),
        citation="cannot both hold",
    )
    assert exc.to_clause().literals == (Literal(predicate="a"), Literal(predicate="b"))


def test_truth_has_three_values_unknown_is_not_false():
    assert Truth.UNKNOWN != Truth.FALSE
    assert {t.value for t in Truth} == {"true", "false", "unknown"}
