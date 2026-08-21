"""The inference core: forward chaining, contradiction detection, explanation.

Deliberately knows nothing about where facts come from. It receives `Fact` objects and
never imports an extraction module, so extraction-layer uncertainty can only reach a
conclusion through a `Fact`'s own source and confidence.

Closed-world semantics are inverted from the usual database default: an undeclared
predicate is UNKNOWN, never False. Answering False for something merely unstated would
let a caller act on a guarantee that was never established.
"""

from __future__ import annotations

from brok.assumptions.entities import Entity
from brok.assumptions.models import (
    AskResult,
    Clause,
    Contradiction,
    Derivation,
    Fact,
    FactSource,
    Literal,
    Truth,
)
from brok.assumptions.rules import CLAUSES, NUMERIC_RULES

FactMap = dict[str, Fact]
OriginMap = dict[str, set[FactSource]]


def _numeric_pass(entity: Entity, facts: FactMap, origins: OriginMap) -> None:
    """Evaluate the arithmetic rules (quorum NRW) into boolean facts.

    A rule whose attributes are absent simply does not fire. That leaves the predicate
    UNKNOWN rather than substituting a default, which would then get reported with a
    citation it did not earn.
    """
    for rule in NUMERIC_RULES:
        if rule.produces in facts:
            continue
        if not all(attr in entity.attributes for attr in rule.requires):
            continue
        value, evidence = rule.compute(entity.attributes)
        facts[rule.produces] = Fact(
            value=value,
            source=FactSource.DERIVED,
            confidence=1.0,
            evidence=evidence,
            derivation=Derivation(
                rule_id=rule.rule_id,
                domain=rule.domain,
                citation=rule.citation,
                inputs=[f"{a}={entity.attributes[a]:g}" for a in rule.requires],
            ),
        )
        # Arithmetic over stated attributes introduces no uncertainty of its own, so
        # it contributes no root source. A contradiction reached through quorum
        # arithmetic is still a hard one.
        origins[rule.produces] = set()


def _evaluate(clause: Clause, facts: FactMap) -> tuple[list[Literal], list[Literal], bool]:
    """Split a clause's literals against current facts.

    Returns (satisfied, unknown, falsified). `falsified` short-circuits: one literal
    known to be false makes the clause unsatisfiable, so it can never fire.
    """
    satisfied: list[Literal] = []
    unknown: list[Literal] = []
    for lit in clause.literals:
        fact = facts.get(lit.predicate)
        if fact is None:
            unknown.append(lit)
        elif fact.value == lit.polarity:
            satisfied.append(lit)
        else:
            return satisfied, unknown, True
    return satisfied, unknown, False


def _support(literals: list[Literal], facts: FactMap, origins: OriginMap):
    """Weakest confidence across the supporting facts, plus their root provenance.

    Roots are transitive: a derived fact reports the sources its own inputs came from,
    not the bare fact that it was derived. That is what lets a contradiction three
    steps downstream still report whether a guess is holding it up.
    """
    confidence = min((facts[lit.predicate].confidence for lit in literals), default=1.0)
    roots: set[FactSource] = set()
    for lit in literals:
        roots |= origins.get(lit.predicate, {facts[lit.predicate].source})
    return confidence, roots


def saturate(entity: Entity) -> tuple[FactMap, list[Contradiction]]:
    """Run every rule to a fixpoint. Returns all known facts and any contradictions.

    One inference step covers both authoring forms, because both compiled to the same
    clause shape ("these literals cannot all hold"):

      * every literal satisfied      -> contradiction
      * all but one satisfied        -> derive the remaining literal's negation

    The second case is why no contrapositive ever has to be hand-written. Declaring
    strong consistency and partition tolerance derives unavailability under partition
    from the CAP exclusion alone.

    The entity is never mutated; facts are accumulated in a local copy.
    """
    facts: FactMap = dict(entity.facts)
    origins: OriginMap = {p: {f.source} for p, f in entity.facts.items()}
    contradictions: list[Contradiction] = []
    seen_rules: set[str] = set()

    _numeric_pass(entity, facts, origins)

    changed = True
    while changed:
        changed = False
        for clause in CLAUSES:
            satisfied, unknown, falsified = _evaluate(clause, facts)
            if falsified:
                continue

            if not unknown:
                if clause.rule_id in seen_rules:
                    continue
                seen_rules.add(clause.rule_id)
                confidence, roots = _support(satisfied, facts, origins)
                contradictions.append(
                    Contradiction(
                        rule_id=clause.rule_id,
                        domain=clause.domain,
                        citation=clause.citation,
                        conflicting=[lit.predicate for lit in satisfied],
                        sources=[facts[lit.predicate].source for lit in satisfied],
                        confidence=confidence,
                        all_declared=FactSource.INFERRED not in roots,
                        explanation=(
                            f"{' and '.join(str(lit) for lit in satisfied)} "
                            f"cannot all hold"
                        ),
                    )
                )
                continue

            if len(unknown) == 1:
                target = unknown[0]
                confidence, roots = _support(satisfied, facts, origins)
                facts[target.predicate] = Fact(
                    # The clause forbids this literal holding, so its negation follows.
                    value=not target.polarity,
                    source=FactSource.DERIVED,
                    confidence=confidence,
                    derivation=Derivation(
                        rule_id=clause.rule_id,
                        domain=clause.domain,
                        citation=clause.citation,
                        inputs=[str(lit) for lit in satisfied],
                        from_predicates=[lit.predicate for lit in satisfied],
                    ),
                )
                origins[target.predicate] = roots
                changed = True

    contradictions.sort(key=lambda c: (-c.confidence, c.rule_id))
    return facts, contradictions


def _chain(predicate: str, facts: FactMap) -> list[Derivation]:
    """Walk a fact's derivation backwards, dependencies first."""
    trail: list[Derivation] = []
    visited: set[str] = set()

    def walk(name: str) -> None:
        if name in visited:
            return
        visited.add(name)
        fact = facts.get(name)
        if fact is None or fact.derivation is None:
            return
        for parent in fact.derivation.from_predicates:
            walk(parent)
        trail.append(fact.derivation)

    walk(predicate)
    return trail


def ask(predicate: str, entity: Entity) -> AskResult:
    """Answer TRUE, FALSE, or UNKNOWN, with the derivation that produced it.

    A predicate caught up in a contradiction answers UNKNOWN rather than picking a
    side. The facts genuinely disagree; reporting either value would hide that.
    """
    facts, contradictions = saturate(entity)

    blocked = {p for c in contradictions for p in c.conflicting}
    if predicate in blocked:
        return AskResult(predicate=predicate, truth=Truth.UNKNOWN)

    fact = facts.get(predicate)
    if fact is None:
        return AskResult(predicate=predicate, truth=Truth.UNKNOWN)

    trail = _chain(predicate, facts)
    return AskResult(
        predicate=predicate,
        truth=Truth.TRUE if fact.value else Truth.FALSE,
        confidence=fact.confidence,
        source=fact.source,
        evidence=fact.evidence,
        derivation=trail,
        citations=list(dict.fromkeys(d.citation for d in trail)),
    )


def check_contradictions(entity: Entity) -> list[Contradiction]:
    """Forward chain and return every contradiction found, most certain first."""
    return saturate(entity)[1]


def explain(predicate: str, entity: Entity) -> str:
    """Human-readable derivation trail with citations, for MCP tool responses."""
    facts, contradictions = saturate(entity)
    relevant = [c for c in contradictions if predicate in c.conflicting]

    if relevant:
        lines = [
            f"{predicate} on '{entity.name}': UNKNOWN - blocked by a contradiction.",
            "",
        ]
        for c in relevant:
            lines.append(f"  contradiction [{c.rule_id}] {c.explanation}")
            lines.append(f"    cites: {c.citation}")
            lines.append(
                f"    confidence: {c.confidence:.2f}"
                f" ({'all facts declared' if c.all_declared else 'rests on an inferred fact'})"
            )
        return "\n".join(lines)

    fact = facts.get(predicate)
    if fact is None:
        return (
            f"{predicate} on '{entity.name}': UNKNOWN - insufficient facts. "
            f"Nothing declared or inferred entails it either way."
        )

    value = "true" if fact.value else "false"
    lines = [
        f"{predicate} on '{entity.name}': {value} "
        f"(confidence {fact.confidence:.2f}, source {fact.source.value})"
    ]
    if fact.evidence:
        lines.append(f"  evidence: {fact.evidence}")

    trail = _chain(predicate, facts)
    if not trail:
        lines.append("  declared directly; no derivation required.")
        return "\n".join(lines)

    lines.append("")
    lines.append("  derivation:")
    for step in trail:
        joined = " and ".join(step.inputs) if step.inputs else "given attributes"
        lines.append(f"    [{step.rule_id}] {joined}")
        lines.append(f"      cites: {step.citation}")
    return "\n".join(lines)
