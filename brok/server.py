from __future__ import annotations

from mcp.server.fastmcp import FastMCP

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


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
