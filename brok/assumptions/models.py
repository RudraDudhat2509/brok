"""Data model for the assumptions engine.

Everything here is inert: facts, literals, and the two authoring forms for rules.
No inference lives in this module, and nothing here imports an extraction layer.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Truth(str, Enum):
    """Three-valued answer. UNKNOWN means "insufficient facts", never False.

    Claiming FALSE for something merely undeclared would let callers act on a
    guarantee the engine never established, which is the failure this engine exists
    to prevent.
    """

    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


class FactSource(str, Enum):
    """Where a fact came from. Provenance never collapses into a bare bool.

    DECLARED — stated directly by a user or agent.
    INFERRED — produced by an extraction skill reading a codebase; confidence < 1.0.
    DERIVED  — computed by this engine, either by a numeric rule or forward chaining.
               Distinct from INFERRED because nothing was guessed: the value follows
               from a cited formula or clause.
    """

    DECLARED = "declared"
    INFERRED = "inferred"
    DERIVED = "derived"


class Literal(BaseModel):
    """A predicate together with the polarity being asserted.

    Polarity is a field rather than a "not " string prefix so that a typo becomes a
    predicate-name mismatch the rule-table tests catch, not a silently non-matching
    rule.
    """

    model_config = ConfigDict(frozen=True)

    predicate: str
    polarity: bool = True

    def negate(self) -> Literal:
        return Literal(predicate=self.predicate, polarity=not self.polarity)

    def __str__(self) -> str:
        return self.predicate if self.polarity else f"not {self.predicate}"


class Derivation(BaseModel):
    """How one derived fact was produced: the rule, its citation, and its inputs.

    `inputs` renders the supporting literals for humans; `from_predicates` carries the
    bare predicate names so the engine can walk a chain backwards without parsing
    display strings.
    """

    rule_id: str
    citation: str
    domain: str
    inputs: list[str] = Field(default_factory=list)
    from_predicates: list[str] = Field(default_factory=list)

    def __str__(self) -> str:
        joined = " and ".join(self.inputs) if self.inputs else "no prior facts"
        return f"[{self.rule_id}] {joined} -> ({self.citation})"


class Fact(BaseModel):
    """One predicate's value on one entity, with its provenance."""

    value: bool
    source: FactSource
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence: str | None = None
    derivation: Derivation | None = None

    def as_literal(self, predicate: str) -> Literal:
        return Literal(predicate=predicate, polarity=self.value)


class Clause(BaseModel):
    """The single internal rule form: these literals cannot all hold at once.

    Both authoring forms compile to this. One representation means the implication
    table and the exclusion table cannot drift apart, and one inference step covers
    both: if every literal but one is satisfied, the remaining literal's negation is
    derived; if every literal is satisfied, that is a contradiction.
    """

    model_config = ConfigDict(frozen=True)

    rule_id: str
    domain: str
    literals: tuple[Literal, ...]
    citation: str


class Implication(BaseModel):
    """`when` (a conjunction) implies `implies`. Reads naturally for causal rules."""

    rule_id: str
    domain: str
    when: tuple[Literal, ...]
    implies: Literal
    citation: str

    def to_clause(self) -> Clause:
        # A -> C is exactly "A and not-C cannot both hold".
        return Clause(
            rule_id=self.rule_id,
            domain=self.domain,
            literals=(*self.when, self.implies.negate()),
            citation=self.citation,
        )


class Exclusion(BaseModel):
    """These literals cannot all hold. Reads naturally for impossibility theorems."""

    rule_id: str
    domain: str
    literals: tuple[Literal, ...]
    citation: str

    def to_clause(self) -> Clause:
        return Clause(
            rule_id=self.rule_id,
            domain=self.domain,
            literals=self.literals,
            citation=self.citation,
        )


class Contradiction(BaseModel):
    """A clause whose literals all hold, reported rather than raised.

    `confidence` is the weakest link across every fact involved, and `all_declared`
    separates a hard conflict between two stated facts from a soft one resting on a
    heuristic guess.
    """

    rule_id: str
    domain: str
    citation: str
    conflicting: list[str]
    sources: list[FactSource]
    confidence: float
    all_declared: bool
    explanation: str


class AskResult(BaseModel):
    """Answer to `ask()`: a Truth, plus how the engine got there."""

    predicate: str
    truth: Truth
    confidence: float | None = None
    source: FactSource | None = None
    evidence: str | None = None
    derivation: list[Derivation] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
