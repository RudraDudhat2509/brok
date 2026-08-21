"""Brok's assumptions engine: fact-based, contradiction-detecting inference over
system design trade-offs, with every conclusion traceable to a cited theorem.
"""

from brok.assumptions.engine import ask, check_contradictions, explain, saturate
from brok.assumptions.entities import Channel, DataStore, Entity, Service
from brok.assumptions.models import (
    AskResult,
    Clause,
    Contradiction,
    Derivation,
    Exclusion,
    Fact,
    FactSource,
    Implication,
    Literal,
    Truth,
)

__all__ = [
    "AskResult",
    "Channel",
    "Clause",
    "Contradiction",
    "DataStore",
    "Derivation",
    "Entity",
    "Exclusion",
    "Fact",
    "FactSource",
    "Implication",
    "Literal",
    "Service",
    "Truth",
    "ask",
    "check_contradictions",
    "explain",
    "saturate",
]
