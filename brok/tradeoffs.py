from __future__ import annotations

from pydantic import BaseModel

from brok.models import CapacityReport, ComponentType


class Tradeoff(BaseModel):
    when_fine: str
    gain: str
    cost: str
    move: str  # the move when you outgrow it
    source: str


TRADEOFFS: dict[ComponentType, Tradeoff] = {
    ComponentType.RELATIONAL_DB: Tradeoff(
        when_fine="under about 500 writes/sec and a dataset one machine can hold",
        gain="simple, transactional, strong consistency",
        cost="a single point of failure, writes cap near 1k/sec, scales only by a bigger box",
        move="read-heavy: add read replicas (accept replication lag). write-bound: shard by a "
             "high cardinality key (lose cross-shard joins, gain ops work). spiky writes: put a "
             "queue in front (adds latency).",
        source="Hello Interview (sharding); Postgres write benchmarks",
    ),
    ComponentType.CACHE: Tradeoff(
        when_fine="read-heavy traffic where slightly stale data is acceptable",
        gain="cuts read latency and offloads the database",
        cost="adds a cache invalidation problem and a staleness window; long TTL means stale, "
             "short TTL means more database hits",
        move="if the hit rate is low the cache is not earning its keep; if you need fresh data, "
             "shorten the TTL or invalidate on write",
        source="Azure caching guidance",
    ),
    ComponentType.QUEUE: Tradeoff(
        when_fine="spiky or write-heavy workloads that tolerate async processing",
        gain="smooths spikes, decouples producers from consumers, turns sync writes async",
        cost="adds end to end latency, plus at-least-once delivery and ordering concerns",
        move="size the consumers to drain faster than the arrival rate, or the queue grows "
             "unbounded",
        source="System Design Primer (message queues)",
    ),
    ComponentType.CDN: Tradeoff(
        when_fine="static or cacheable read content served to many users",
        gain="massive read fan-out, served close to the user",
        cost="useless for writes or per-user dynamic data; cache purge complexity",
        move="never route writes through it; for dynamic data use a cache or an edge function",
        source="CDN: massive read fan-out; writes do not belong on a CDN (System Design Primer, CDN)",
    ),
    ComponentType.APP_SERVER: Tradeoff(
        when_fine="almost always, as a stateless app tier",
        gain="scales out horizontally behind a load balancer, cheaply",
        cost="a single instance caps at low thousands of req/sec; state must live elsewhere",
        move="add instances behind the load balancer; keep the handlers stateless",
        source="Single app instance: low thousands RPS typical (order-of-magnitude); horizontal scaling pattern",
    ),
    ComponentType.OBJECT_STORE: Tradeoff(
        when_fine="large blobs (images, video, files) and high-throughput reads",
        gain="cheap, durable, effectively unlimited capacity",
        cost="higher per-request latency than memory or a database; some stores list "
             "eventually consistently; per-prefix throughput is bounded (about 3.5k writes/sec, "
             "5.5k reads/sec on S3-class), so hot keys throttle",
        move="spread the keys across more prefixes, and put a CDN in front of the hot read paths",
        source="Object store (S3-class) per-prefix: ~3.5k w/s, ~5.5k r/s (order-of-magnitude)",
    ),
    ComponentType.LOAD_BALANCER: Tradeoff(
        when_fine="any multi-instance tier",
        gain="distributes load, enables horizontal scale and failover",
        cost="itself a single point of failure if not redundant; adds a network hop",
        move="run it redundant, or use a managed balancer",
        source="L7 load balancer: tens of thousands RPS per node (order-of-magnitude)",
    ),
}


def get_tradeoff(t: ComponentType) -> Tradeoff | None:
    return TRADEOFFS.get(t)


def tradeoffs_for(report: CapacityReport) -> list[dict]:
    rows: list[dict] = []
    seen: set[ComponentType] = set()
    for u in report.utilizations:
        if u.type in seen:
            continue
        to = get_tradeoff(u.type)
        if to is None:
            continue
        seen.add(u.type)
        rows.append({"type": u.type.value, **to.model_dump()})
    return rows
