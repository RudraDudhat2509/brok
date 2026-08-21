"""Dict-in, dict-out adapter for the MCP layer.

Keeps `server.py` declarative and keeps JSON shapes out of the inference core.
"""

from __future__ import annotations

from typing import Any

from brok.assumptions.engine import ask, check_contradictions, explain, saturate
from brok.assumptions.entities import Channel, DataStore, Entity, Service
from brok.assumptions.rules import DOMAINS, PREDICATES

_KINDS = {"datastore": DataStore, "service": Service, "channel": Channel}

# Inferred facts are guesses by definition, so an extraction skill that forgets to
# state its confidence gets a visibly non-certain default rather than silently
# borrowing the authority of a declared fact.
_DEFAULT_INFERRED_CONFIDENCE = 0.5


def build_entity(
    name: str,
    kind: str = "datastore",
    declared: dict[str, bool] | None = None,
    inferred: dict[str, dict[str, Any]] | None = None,
    n: float | None = None,
    w: float | None = None,
    r: float | None = None,
) -> Entity:
    entity = _KINDS.get(kind, DataStore)(name=name)

    for predicate, value in (declared or {}).items():
        entity.declare(predicate, bool(value))

    for predicate, spec in (inferred or {}).items():
        entity.infer(
            predicate,
            bool(spec.get("value")),
            confidence=float(spec.get("confidence", _DEFAULT_INFERRED_CONFIDENCE)),
            evidence=spec.get("evidence"),
        )

    for key, value in (("n", n), ("w", w), ("r", r)):
        if value is not None:
            entity.attributes[key] = float(value)

    return entity


def _unknown_predicates(entity: Entity) -> list[str]:
    return sorted(p for p in entity.facts if p not in PREDICATES)


def check_design_assumptions(**kwargs: Any) -> dict:
    """Forward chain over an entity and report contradictions plus everything known."""
    entity = build_entity(**kwargs)
    facts, contradictions = saturate(entity)

    return {
        "entity": entity.name,
        "kind": entity.kind,
        "contradiction_count": len(contradictions),
        "contradictions": [
            {
                "rule_id": c.rule_id,
                "domain": c.domain,
                "conflicting": c.conflicting,
                "citation": c.citation,
                "confidence": c.confidence,
                "all_declared": c.all_declared,
                "explanation": c.explanation,
            }
            for c in contradictions
        ],
        "facts": [
            {
                "predicate": predicate,
                "value": fact.value,
                "source": fact.source.value,
                "confidence": fact.confidence,
                "evidence": fact.evidence,
                "rule_id": fact.derivation.rule_id if fact.derivation else None,
                "citation": fact.derivation.citation if fact.derivation else None,
            }
            for predicate, fact in sorted(facts.items())
        ],
        "unknown_predicates": _unknown_predicates(entity),
        "note": "UNKNOWN means insufficient facts, never False. Brok cites the rule "
                "behind every derivation. You decide.",
    }


def ask_assumption(predicate: str, **kwargs: Any) -> dict:
    """Answer one predicate with its derivation trail and a rendered explanation."""
    entity = build_entity(**kwargs)
    result = ask(predicate, entity)

    return {
        "entity": entity.name,
        "predicate": predicate,
        "truth": result.truth.value,
        "confidence": result.confidence,
        "source": result.source.value if result.source else None,
        "evidence": result.evidence,
        "citations": result.citations,
        "derivation": [
            {"rule_id": d.rule_id, "inputs": d.inputs, "citation": d.citation}
            for d in result.derivation
        ],
        "explanation": explain(predicate, entity),
        "unknown_predicates": _unknown_predicates(entity),
    }


def list_assumption_predicates() -> dict:
    """The vocabulary a caller may use. Anything outside it is reported, not guessed."""
    return {
        "domains": list(DOMAINS),
        "predicates": dict(PREDICATES),
        "attributes": {
            "n": "replica count for quorum arithmetic",
            "w": "write quorum size",
            "r": "read quorum size",
        },
        "note": "Quorum overlap (W+R>N) yields read_sees_latest_acked_write, NOT "
                "strong_consistency. Dynamo-style quorums leave concurrent writes "
                "unordered (Kleppmann, DDIA ch.5).",
    }


__all__ = [
    "ask_assumption",
    "build_entity",
    "check_design_assumptions",
    "check_contradictions",
    "list_assumption_predicates",
]
