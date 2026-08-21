from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from brok.assumptions import api as assumptions_api
from brok.pipeline import build_traffic, review_from_components, review_from_compose
from brok.query import search

mcp = FastMCP("brok")


@mcp.tool()
def review_architecture(
    compose_yaml: str,
    expected_dau: int | None = None,
    requests_per_user_per_day: int | None = None,
    read_write_ratio: float | None = None,
    payload_kb: float | None = None,
    peak_factor: float | None = None,
) -> dict:
    """Estimate a system's capacity, find its bottleneck, and surface the trade-offs of its
    design choices. Use this when designing, scaling, or reviewing a system, or when choosing
    or changing a datastore, cache, or queue, so you decide with grounded numbers and known
    trade-offs instead of guessing.

    How to use this (for the calling assistant):
    1. If the project has a docker-compose.yml, read it and pass its full contents as compose_yaml.
    2. Ask the user for their expected scale and pass expected_dau (and read_write_ratio if known).
       Without expected_dau the result assumes 100k users and is reported as low confidence.
    3. Prefer report["roast_text"] as the headline to show the user (Brok's voice); use the
       structured fields and report["tradeoffs"] to reason about the design.

    Returns a dict: bottleneck, max_dau, confidence, assumptions, utilizations, notes,
    tradeoffs (the grounded pros, cons, and next move for each component), cost (a rough
    monthly compute plus egress estimate), report_text, roast_text.
    """
    traffic = build_traffic(expected_dau, requests_per_user_per_day,
                            read_write_ratio, payload_kb, peak_factor)
    return review_from_compose(compose_yaml, traffic)


@mcp.tool()
def review_components(
    components: list[dict],
    expected_dau: int | None = None,
    requests_per_user_per_day: int | None = None,
    read_write_ratio: float | None = None,
    payload_kb: float | None = None,
    peak_factor: float | None = None,
) -> dict:
    """Estimate capacity and surface design trade-offs from a structured component list. Use this
    when designing or scaling a system and there is no docker-compose: infer the components
    yourself from the user's description or code and pass them.

    Pass components as a list of {"name", "type"} dicts. Valid types: relational_db, cache, queue,
    cdn, app_server, object_store, load_balancer. Any other type is reported as not estimated
    (Brok will not guess). Pass expected_dau for a high-confidence result. Prefer roast_text as the
    headline; use the structured fields, tradeoffs, and cost to reason. Returns the same dict
    shape as review_architecture.
    """
    traffic = build_traffic(expected_dau, requests_per_user_per_day,
                            read_write_ratio, payload_kb, peak_factor)
    return review_from_components(components, traffic)


@mcp.tool()
def query_tradeoffs(question: str) -> dict:
    """Call this BEFORE choosing between technologies or architectural patterns.

    Works for: datastores, queues, caches, CDNs, load balancers, sharding strategies,
    cache eviction policies, delivery guarantees, and architectural patterns
    (CQRS, Saga, Circuit Breaker, Event Sourcing, etc.).

    Ask in natural language:
      "kafka vs pubsub for spiky writes"
      "should I use consistent hashing or range sharding"
      "when does CQRS make sense"
      "redis or memcached for session data"
      "how to avoid hot partitions in Kafka"
      "is Cassandra good for strong consistency"   <- returns: no, here is why

    Returns matched KB entries with cited trade-offs, a head-to-head comparison
    when two technologies from the same category match, and a note that Brok
    surfaces the trade-offs but you decide.

    Return shape:
      matches    — list of {name, type, category, when_to_pick, when_not_to_pick,
                             key_tradeoff, extra, citation}
      comparison — head-to-head string when two same-category tech entries match,
                   None otherwise
      note       — "Brok surfaces trade-offs. You decide."
    """
    return search(question)


@mcp.tool()
def check_assumptions(
    name: str,
    kind: str = "datastore",
    declared: dict | None = None,
    inferred: dict | None = None,
    n: float | None = None,
    w: float | None = None,
    r: float | None = None,
) -> dict:
    """Call this when a design makes consistency, availability, or delivery claims,
    to check whether those claims can all be true at once.

    Catches things like: claiming strong consistency AND staying available during a
    network partition (CAP theorem); claiming strong consistency on replicas AND low
    latency (PACELC); claiming exactly-once processing over an at-least-once queue with
    a non-idempotent handler; claiming fresh reads with a quorum config that cannot
    deliver them.

    Pass what you know and nothing else. An undeclared predicate stays UNKNOWN and is
    never assumed False, so a partial fact set gives a partial answer rather than a
    wrong one.

      name      — what you are checking, e.g. "orders_db"
      kind      — "datastore", "service", or "channel"
      declared  — {predicate: bool} for facts the user stated outright
      inferred  — {predicate: {"value": bool, "confidence": 0.0-1.0, "evidence": str}}
                  for facts you guessed from code. Confidence propagates: a conclusion
                  is never more certain than its weakest input.
      n, w, r   — replica count and write/read quorum sizes, for quorum arithmetic

    Call list_assumption_predicates first if you are unsure of the vocabulary; any
    predicate outside it comes back in "unknown_predicates" rather than being guessed at.

    Returns: contradiction_count, contradictions (each with the rule, the citation, the
    conflicting facts, a confidence, and all_declared so you can tell a hard conflict
    from one resting on a guess), every known fact with its provenance, and
    unknown_predicates.
    """
    return assumptions_api.check_design_assumptions(
        name=name, kind=kind, declared=declared, inferred=inferred, n=n, w=w, r=r
    )


@mcp.tool()
def ask_assumption(
    predicate: str,
    name: str,
    kind: str = "datastore",
    declared: dict | None = None,
    inferred: dict | None = None,
    n: float | None = None,
    w: float | None = None,
    r: float | None = None,
) -> dict:
    """Ask whether one specific property holds for a design, with the reasoning shown.

    Returns "true", "false", or "unknown" — where unknown genuinely means the facts do
    not settle it, not that the answer is no. A predicate caught in a contradiction also
    answers unknown rather than picking a side.

    Same entity arguments as check_assumptions. Use this when you need one answer and
    the derivation behind it; use check_assumptions when you want every problem found.

    Returns: truth, confidence, source (declared / inferred / derived), the citation
    chain, the step-by-step derivation, and a rendered explanation suitable for showing
    the user directly.
    """
    return assumptions_api.ask_assumption(
        predicate=predicate,
        name=name,
        kind=kind,
        declared=declared,
        inferred=inferred,
        n=n,
        w=w,
        r=r,
    )


@mcp.tool()
def list_assumption_predicates() -> dict:
    """The predicate vocabulary check_assumptions and ask_assumption understand.

    Call this before the other two if you are unsure what to pass. Returns every
    predicate with a plain description, the four domains covered (CAP, PACELC, quorum,
    idempotency), and the numeric attributes used for quorum arithmetic.
    """
    return assumptions_api.list_assumption_predicates()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
