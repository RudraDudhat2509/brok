"""Entities that carry facts. They hold state and know nothing about inference.

Adding a new entity kind must never require touching the engine or the rule tables:
an entity is just a named bag of facts plus optional numeric attributes.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from brok.assumptions.models import Fact, FactSource


class Entity(BaseModel):
    """A named thing with predicates attached.

    The `declare` / `infer` builders return self so facts can be chained, which keeps
    worked examples readable. Both are ordinary mutation - the engine itself never
    writes back to an entity.
    """

    name: str
    kind: str = "entity"
    facts: dict[str, Fact] = Field(default_factory=dict)
    attributes: dict[str, float] = Field(default_factory=dict)

    def declare(self, predicate: str, value: bool) -> Entity:
        """State a fact directly. Full confidence, no evidence needed."""
        self.facts[predicate] = Fact(value=value, source=FactSource.DECLARED)
        return self

    def infer(
        self,
        predicate: str,
        value: bool,
        confidence: float,
        evidence: str | None = None,
    ) -> Entity:
        """Record a fact an extraction skill guessed. Confidence must be < 1.0 to stay
        honest about the difference between a reading and a statement."""
        self.facts[predicate] = Fact(
            value=value,
            source=FactSource.INFERRED,
            confidence=confidence,
            evidence=evidence,
        )
        return self


class DataStore(Entity):
    kind: str = "datastore"

    def with_quorum(
        self, n: float | None = None, w: float | None = None, r: float | None = None
    ) -> DataStore:
        """Set replica count and write/read quorum sizes.

        Partial input is allowed on purpose: a numeric rule missing an attribute simply
        does not fire, which leaves the predicate UNKNOWN rather than guessing a
        default that would then be cited as fact.
        """
        for key, value in (("n", n), ("w", w), ("r", r)):
            if value is not None:
                self.attributes[key] = float(value)
        return self


class Service(Entity):
    kind: str = "service"


class Channel(Entity):
    """A delivery path between components: a queue, a topic, an RPC call."""

    kind: str = "channel"
