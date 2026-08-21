"""Phase 1 rule tables: CAP, PACELC, quorum (NRW), and idempotency under retries.

Every rule here is backed by a theorem or a formal definition, never by taste. Soft
predicates ("needs microservices", "is maintainable") deliberately do not appear:
mixing them into this graph would make a heuristic hunch render with the same
authority as Gilbert & Lynch.

Two authoring forms, one internal form. `Implication` reads naturally for causal
rules and `Exclusion` for impossibility theorems, but both compile to `Clause`
("these literals cannot all hold") so the tables cannot drift apart and a single
inference step covers both.

PHASE 2 PLUG POINT: heuristic predicates would live in a separate module with their
own tables and their own clearly-labelled confidence floor. They must not be appended
to IMPLICATIONS or EXCLUSIONS below.
"""

from __future__ import annotations

from typing import Callable

from pydantic import BaseModel, ConfigDict

from brok.assumptions.models import Clause, Exclusion, Implication, Literal

DOMAINS = ("cap", "pacelc", "quorum", "idempotency")


def _p(name: str) -> Literal:
    return Literal(predicate=name)


def _not(name: str) -> Literal:
    return Literal(predicate=name, polarity=False)


# --- predicate vocabulary --------------------------------------------------------
# Declared explicitly so a typo in a rule table fails a test instead of silently
# creating a predicate nothing else ever references.

PREDICATES: dict[str, str] = {
    # cap
    "distributed": "Data or work is spread across more than one node.",
    "partition_tolerant": "Keeps operating when the network splits into parts that "
                          "cannot reach each other.",
    "strong_consistency": "Linearizable: every read observes the most recent "
                          "completed write, and operations have a single total order.",
    "available_under_partition": "Every non-failing node returns a non-error response "
                                 "while a partition is in effect.",
    # pacelc
    "replicated": "The same data is held on more than one replica.",
    "low_latency_under_normal_operation": "Reads and writes are served without "
                                          "cross-replica coordination on the hot path.",
    "stale_reads_possible": "A read can return a value older than the most recent "
                            "confirmed write.",
    # quorum
    "quorum_overlap": "W + R > N, so every read quorum intersects every write quorum.",
    "write_quorum_majority": "W > N/2, so any two write quorums intersect.",
    "sloppy_quorum": "Writes may be accepted by nodes outside the key's home replica "
                     "set (hinted handoff), so the counted quorum is not the real one.",
    "read_sees_latest_acked_write": "A read returns at least the most recent write "
                                    "that was fully acknowledged. Strictly weaker than "
                                    "strong_consistency.",
    # idempotency
    "at_least_once_delivery": "Messages are retried until acknowledged; never lost, "
                              "possibly duplicated.",
    "at_most_once_delivery": "Messages are sent without retry; never duplicated, "
                             "possibly lost.",
    "idempotent_handler": "Applying the same message twice has the same effect as "
                          "applying it once.",
    "deduplication": "Redeliveries are suppressed by an idempotency key or dedup store.",
    "duplicate_side_effects_possible": "A single logical request can apply its side "
                                       "effect more than once.",
    "exactly_once_processing": "Each logical request takes effect exactly once.",
    "message_loss_possible": "A message can be dropped without ever taking effect.",
}


# --- numeric derivation ----------------------------------------------------------
# Quorum consistency is arithmetic, not a boolean implication. These rules read
# numeric attributes off an entity and emit boolean facts tagged FactSource.DERIVED,
# which then enter the ordinary clause reasoning. Keeping the arithmetic here rather
# than upstream means the engine actually evaluates the theorem it cites.


class NumericRule(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    rule_id: str
    domain: str
    produces: str
    requires: tuple[str, ...]
    citation: str
    compute: Callable[[dict[str, float]], tuple[bool, str]]


def _overlap(a: dict[str, float]) -> tuple[bool, str]:
    n, w, r = a["n"], a["w"], a["r"]
    return w + r > n, f"W({w:g}) + R({r:g}) = {w + r:g} vs N({n:g})"


def _write_majority(a: dict[str, float]) -> tuple[bool, str]:
    n, w = a["n"], a["w"]
    return w > n / 2, f"W({w:g}) vs N/2 ({n / 2:g})"


NUMERIC_RULES: tuple[NumericRule, ...] = (
    NumericRule(
        rule_id="Q-D1",
        domain="quorum",
        produces="quorum_overlap",
        requires=("n", "w", "r"),
        citation="Quorum consistency, W+R>N (Gifford 1979, Weighted Voting for "
                 "Replicated Data): a read quorum then intersects every write quorum.",
        compute=_overlap,
    ),
    NumericRule(
        rule_id="Q-D2",
        domain="quorum",
        produces="write_quorum_majority",
        requires=("n", "w"),
        citation="Quorum consistency, W>N/2 (Gifford 1979): any two write quorums "
                 "intersect, so concurrent writes cannot proceed independently.",
        compute=_write_majority,
    ),
)


# --- CAP -------------------------------------------------------------------------

_CAP_EXCLUSIONS = (
    Exclusion(
        rule_id="C1",
        domain="cap",
        literals=(
            _p("strong_consistency"),
            _p("available_under_partition"),
            _p("partition_tolerant"),
        ),
        citation="CAP theorem (Brewer 2000; proved by Gilbert & Lynch 2002): a "
                 "distributed store cannot be consistent, available, and partition "
                 "tolerant at the same time. Partitions are not optional, so the real "
                 "choice is consistency or availability while one is in effect.",
    ),
)

_CAP_IMPLICATIONS = (
    Implication(
        rule_id="C2",
        domain="cap",
        when=(_not("distributed"),),
        implies=_not("partition_tolerant"),
        citation="CAP theorem: a single-node store has no internal network to split, "
                 "so it is CA and not partition tolerant.",
    ),
)


# --- PACELC ----------------------------------------------------------------------

_PACELC_EXCLUSIONS = (
    Exclusion(
        rule_id="P1",
        domain="pacelc",
        literals=(
            _p("replicated"),
            _p("strong_consistency"),
            _p("low_latency_under_normal_operation"),
        ),
        citation="PACELC else-branch (Abadi 2012): absent a partition, consistency "
                 "trades against latency. The bound is formal, not stylistic - Attiya "
                 "& Welch 1994 prove that in a linearizable replicated system read "
                 "latency plus write latency is at least the inter-replica delay.",
    ),
)

_PACELC_IMPLICATIONS = (
    Implication(
        rule_id="P2",
        domain="pacelc",
        when=(_p("replicated"), _not("read_sees_latest_acked_write")),
        implies=_p("stale_reads_possible"),
        citation="PACELC else-branch (Abadi 2012): if replicated data is not "
                 "guaranteed to return the latest acknowledged write, a replica can "
                 "serve an older value.",
    ),
    Implication(
        rule_id="P3",
        domain="pacelc",
        when=(_p("replicated"),),
        implies=_p("distributed"),
        citation="Definitional: replication places copies on distinct nodes, which is "
                 "what makes a store distributed.",
    ),
)


# --- Quorum (NRW) ----------------------------------------------------------------
# Finding 1, and the reason this domain is worth encoding carefully: W+R>N does NOT
# give linearizability. Dynamo-style quorums leave concurrent writes unordered, can
# leave a partially applied write readable, and sloppy quorums break the intersection
# argument outright (Kleppmann, DDIA ch.5, "Limitations of Quorum Consistency"). The
# provable guarantee is the weaker read_sees_latest_acked_write, so that is what the
# rules claim. strong_consistency implies it; it never implies strong_consistency.

_QUORUM_IMPLICATIONS = (
    Implication(
        rule_id="Q1",
        domain="quorum",
        when=(_p("quorum_overlap"), _not("sloppy_quorum")),
        implies=_p("read_sees_latest_acked_write"),
        citation="Quorum consistency, W+R>N with a strict quorum (Gifford 1979; "
                 "Kleppmann DDIA ch.5): the read quorum intersects the write quorum, "
                 "so a read observes the latest acknowledged write. This is NOT "
                 "linearizability - concurrent writes remain unordered.",
    ),
    Implication(
        rule_id="Q2",
        domain="quorum",
        when=(_not("quorum_overlap"), _p("replicated")),
        implies=_p("stale_reads_possible"),
        citation="Quorum consistency, W+R<=N (Gifford 1979): read and write quorums "
                 "need not intersect, so a read can miss the latest write entirely.",
    ),
    Implication(
        rule_id="Q3",
        domain="quorum",
        when=(_p("strong_consistency"),),
        implies=_p("read_sees_latest_acked_write"),
        citation="Linearizability is strictly stronger than reading the latest "
                 "acknowledged write, so it entails it. The converse does not hold "
                 "(Kleppmann DDIA ch.5).",
    ),
)

_QUORUM_EXCLUSIONS = (
    Exclusion(
        rule_id="Q4",
        domain="quorum",
        literals=(_p("read_sees_latest_acked_write"), _p("stale_reads_possible")),
        citation="Definitional: a read guaranteed to observe the latest acknowledged "
                 "write cannot also be allowed to return an older one.",
    ),
)


# --- Idempotency under retries ---------------------------------------------------

_IDEMPOTENCY_IMPLICATIONS = (
    Implication(
        rule_id="I1",
        domain="idempotency",
        when=(
            _p("at_least_once_delivery"),
            _not("idempotent_handler"),
            _not("deduplication"),
        ),
        implies=_p("duplicate_side_effects_possible"),
        citation="Idempotency under at-least-once delivery: a lost acknowledgement "
                 "causes redelivery, and a non-idempotent handler with no dedup "
                 "applies the side effect again.",
    ),
    Implication(
        rule_id="I2",
        domain="idempotency",
        when=(_p("at_least_once_delivery"), _p("idempotent_handler")),
        implies=_not("duplicate_side_effects_possible"),
        citation="Idempotence: applying the same message more than once has the same "
                 "effect as applying it once, so redelivery is harmless.",
    ),
    Implication(
        rule_id="I3",
        domain="idempotency",
        when=(_p("at_least_once_delivery"), _p("deduplication")),
        implies=_not("duplicate_side_effects_possible"),
        citation="Deduplication by idempotency key suppresses redeliveries - but only "
                 "within the dedup window and scope (Kafka's idempotent producer is "
                 "per-partition and per-session), so the guarantee expires when the "
                 "window does.",
    ),
    Implication(
        rule_id="I6",
        domain="idempotency",
        when=(_p("at_most_once_delivery"),),
        implies=_p("message_loss_possible"),
        citation="At-most-once delivery does not retry, so an unacknowledged message "
                 "is dropped rather than redelivered.",
    ),
)

_IDEMPOTENCY_EXCLUSIONS = (
    Exclusion(
        rule_id="I4",
        domain="idempotency",
        literals=(_p("exactly_once_processing"), _p("duplicate_side_effects_possible")),
        citation="Exactly-once delivery is impossible over an unreliable network (Two "
                 "Generals problem). Exactly-once processing is achievable only by "
                 "making duplicates harmless, so it cannot coexist with duplicate "
                 "side effects.",
    ),
    Exclusion(
        rule_id="I5",
        domain="idempotency",
        literals=(_p("at_least_once_delivery"), _p("at_most_once_delivery")),
        citation="Definitional: a channel either retries unacknowledged messages or "
                 "it does not. The two delivery guarantees are mutually exclusive.",
    ),
)


IMPLICATIONS: tuple[Implication, ...] = (
    *_CAP_IMPLICATIONS,
    *_PACELC_IMPLICATIONS,
    *_QUORUM_IMPLICATIONS,
    *_IDEMPOTENCY_IMPLICATIONS,
)

EXCLUSIONS: tuple[Exclusion, ...] = (
    *_CAP_EXCLUSIONS,
    *_PACELC_EXCLUSIONS,
    *_QUORUM_EXCLUSIONS,
    *_IDEMPOTENCY_EXCLUSIONS,
)

CLAUSES: tuple[Clause, ...] = tuple(
    rule.to_clause() for rule in (*IMPLICATIONS, *EXCLUSIONS)
)


def clauses_for_domain(domain: str) -> tuple[Clause, ...]:
    return tuple(c for c in CLAUSES if c.domain == domain)


def citation_for(rule_id: str) -> str | None:
    for rule in (*IMPLICATIONS, *EXCLUSIONS, *NUMERIC_RULES):
        if rule.rule_id == rule_id:
            return rule.citation
    return None
