"""Operational strategy knowledge base — 18 entries across 5 domains.

Domains: sharding (4), cache eviction (6), queue delivery (3),
         DB replication (3), partitioning (2).

Every entry has a `citation` URL that backs its claims.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyEntry:
    name: str
    aliases: list[str]
    applies_to: list[str]       # component category strings this strategy applies to
    when_to_use: str
    when_not_to_use: str
    key_tradeoff: str
    citation: str


# ---------------------------------------------------------------------------
# Sharding (4)
# ---------------------------------------------------------------------------

STRATEGY_KB: list[StrategyEntry] = [
    StrategyEntry(
        name="consistent hashing",
        aliases=["ketama", "ring hashing", "consistent hash ring", "virtual nodes"],
        applies_to=["cache", "relational_db", "queue"],
        when_to_use=(
            "distribute data across nodes where node count changes frequently; "
            "minimizes key remapping when a node is added or removed — "
            "only 1/N keys need to move vs a full reshuffle with modulo hashing"
        ),
        when_not_to_use=(
            "small, fixed-size cluster where simple modulo hashing is sufficient; "
            "adds virtual-node complexity for no gain when topology is stable"
        ),
        key_tradeoff=(
            "only 1/N keys remap on node change (vs full reshuffle); "
            "virtual nodes (vnodes) are required for even distribution — "
            "without them, physical nodes with different capacities get uneven load"
        ),
        citation="https://en.wikipedia.org/wiki/Consistent_hashing",
    ),
    StrategyEntry(
        name="range-based sharding",
        aliases=["range sharding", "range partitioning", "range partition"],
        applies_to=["relational_db", "queue"],
        when_to_use=(
            "time-series data, sequential range scans across contiguous key ranges "
            "(e.g., user_id 1-1000 on shard A, 1001-2000 on shard B); "
            "enables partition pruning so range queries only hit one shard"
        ),
        when_not_to_use=(
            "monotonically increasing keys (timestamps, auto-increment IDs) — "
            "all writes go to the last shard, creating a permanent hot shard; "
            "random-access patterns where range locality is irrelevant"
        ),
        key_tradeoff=(
            "enables efficient range queries and partition pruning; "
            "monotonic keys create hot shards and must be actively avoided — "
            "use composite keys or hash prefix for write-heavy time-series"
        ),
        citation="https://www.citusdata.com/blog/2017/08/28/five-sharding-data-models/",
    ),
    StrategyEntry(
        name="hash-based sharding",
        aliases=["hash sharding", "hash partitioning", "modulo sharding", "key-based sharding"],
        applies_to=["relational_db", "cache"],
        when_to_use=(
            "even data distribution across shards, random-access patterns, "
            "no range queries needed — spread writes uniformly to prevent hot shards"
        ),
        when_not_to_use=(
            "range queries spanning multiple shards — must scatter-gather all shards "
            "and merge results; adding or removing shards requires a full key reshuffle"
        ),
        key_tradeoff=(
            "uniform distribution prevents hot shards; "
            "range queries become expensive scatter-gather operations across all shards; "
            "resharding is painful — use consistent hashing to mitigate remapping cost"
        ),
        citation="https://www.citusdata.com/blog/2017/08/28/five-sharding-data-models/",
    ),
    StrategyEntry(
        name="directory-based sharding",
        aliases=["directory sharding", "lookup table sharding", "shard map"],
        applies_to=["relational_db"],
        when_to_use=(
            "heterogeneous shard sizes, fine-grained resharding without a full rebalance, "
            "multi-tenant systems where different tenants have different data volumes"
        ),
        when_not_to_use=(
            "the lookup table itself becomes a single point of failure or throughput bottleneck; "
            "overhead is unjustified when data is uniform and hash/range sharding suffices"
        ),
        key_tradeoff=(
            "lookup table adds one extra network hop per query and is a SPOF — "
            "must be replicated and highly available; "
            "enables fine-grained shard control unavailable with hash or range strategies"
        ),
        citation="https://en.wikipedia.org/wiki/Shard_(database_architecture)",
    ),

    # ---------------------------------------------------------------------------
    # Cache eviction (6)
    # ---------------------------------------------------------------------------

    StrategyEntry(
        name="LRU",
        aliases=["least recently used", "lru eviction", "lru cache policy"],
        applies_to=["cache"],
        when_to_use=(
            "temporal locality: recently accessed items are likely to be accessed again; "
            "session caches, hot page caches, browser caches"
        ),
        when_not_to_use=(
            "sequential scan workloads that access every item once — "
            "a single scan thrashes the cache and evicts the entire hot working set; "
            "use LFU or ARC when frequency matters more than recency"
        ),
        key_tradeoff=(
            "O(1) with doubly linked list + hashmap; "
            "does not account for access frequency — one large scan evicts all hot keys; "
            "Redis default eviction policy"
        ),
        citation="https://redis.io/docs/latest/develop/reference/eviction/",
    ),
    StrategyEntry(
        name="LFU",
        aliases=["least frequently used", "lfu eviction", "lfu cache policy"],
        applies_to=["cache"],
        when_to_use=(
            "frequency-dominated access patterns: popular items should stay in cache "
            "regardless of recency; content delivery caches, recommendation result caches"
        ),
        when_not_to_use=(
            "workloads with new popular items — newly cached entries start with a low "
            "frequency counter and get evicted too early before they can prove popularity"
        ),
        key_tradeoff=(
            "protects hot items from one-time scan eviction; "
            "newly cached items start with frequency=1 and are vulnerable to early eviction; "
            "frequency counters add per-key memory overhead"
        ),
        citation="https://redis.io/docs/latest/develop/reference/eviction/",
    ),
    StrategyEntry(
        name="TTL",
        aliases=["time to live", "expiry", "cache expiry", "ttl eviction", "key expiration"],
        applies_to=["cache"],
        when_to_use=(
            "data has a natural expiry: sessions, API tokens, rate limit windows, "
            "DNS records, OTP codes — anything where staleness after time T is unacceptable"
        ),
        when_not_to_use=(
            "data without a natural expiry that should be evicted by access pattern rather "
            "than by clock — a TTL becomes a stale-data footgun here"
        ),
        key_tradeoff=(
            "simple and predictable; "
            "TTL is a manual knob — too long means serving stale data, "
            "too short means cache miss storms hammering the origin DB"
        ),
        citation="https://redis.io/commands/expire/",
    ),
    StrategyEntry(
        name="write-through",
        aliases=["write through cache", "read-through write-through", "synchronous write cache"],
        applies_to=["cache"],
        when_to_use=(
            "read-heavy workload, cache must always be consistent with the DB, "
            "data should be warm in cache from the moment it is written"
        ),
        when_not_to_use=(
            "write-heavy workload — every write pays double latency (cache + DB synchronously); "
            "cold start adds initial write overhead before cache is populated"
        ),
        key_tradeoff=(
            "cache always consistent with DB — no stale reads; "
            "every write hits both cache and DB synchronously — "
            "doubles write latency per write, unsuitable for write-heavy paths"
        ),
        citation="https://learn.microsoft.com/en-us/azure/architecture/patterns/cache-aside",
    ),
    StrategyEntry(
        name="write-back",
        aliases=["write behind", "write-behind cache", "lazy write", "deferred write"],
        applies_to=["cache"],
        when_to_use=(
            "write-heavy workload, eventual consistency is acceptable, "
            "batching writes to the DB reduces write amplification"
        ),
        when_not_to_use=(
            "data loss is unacceptable — if the cache node crashes before flushing, "
            "unflushed writes are lost; strong consistency between cache and DB required"
        ),
        key_tradeoff=(
            "highest write throughput — write to cache only, flush to DB asynchronously; "
            "risk of data loss if the cache node fails before flushing; "
            "batching reduces DB write amplification but adds flush delay"
        ),
        citation="https://learn.microsoft.com/en-us/azure/architecture/patterns/cache-aside",
    ),
    StrategyEntry(
        name="write-around",
        aliases=["write around cache"],
        applies_to=["cache"],
        when_to_use=(
            "write-once data that will not be read back immediately: "
            "logs, batch uploads, archive writes, cold storage ingestion"
        ),
        when_not_to_use=(
            "data that will be read back soon after writing — "
            "first read after a write-around is always a cache miss, forcing a DB hit"
        ),
        key_tradeoff=(
            "prevents cache pollution from infrequently-read write data; "
            "first read after every write is a guaranteed cache miss — "
            "combine with read-through to populate cache on the first miss"
        ),
        citation="https://learn.microsoft.com/en-us/azure/architecture/patterns/cache-aside",
    ),

    # ---------------------------------------------------------------------------
    # Queue delivery (3)
    # ---------------------------------------------------------------------------

    StrategyEntry(
        name="at-least-once delivery",
        aliases=["at least once", "alo delivery", "at-least-once semantics"],
        applies_to=["queue"],
        when_to_use=(
            "default for most queues (Kafka, SQS, Pub/Sub); "
            "acceptable to process duplicates; consumer is idempotent"
        ),
        when_not_to_use=(
            "duplicate processing causes data corruption or double-charges; "
            "need exactly-once semantics for financial or inventory operations"
        ),
        key_tradeoff=(
            "simple to implement — producer retries on failure; "
            "causes duplicates when retries succeed after partial delivery; "
            "consumers must be idempotent or use explicit deduplication"
        ),
        citation="https://kafka.apache.org/documentation/#semantics",
    ),
    StrategyEntry(
        name="exactly-once delivery",
        aliases=["exactly once", "eos", "exactly-once semantics", "idempotent delivery"],
        applies_to=["queue"],
        when_to_use=(
            "financial transactions, inventory updates, any operation where "
            "duplicate processing has real monetary or data-integrity consequences"
        ),
        when_not_to_use=(
            "performance is the priority — Kafka EOS has ~20-50% throughput overhead "
            "vs at-least-once; consumer can cheaply deduplicate duplicates"
        ),
        key_tradeoff=(
            "Kafka EOS requires idempotent producer + transactional API + "
            "transactional consumer; ~20-50% throughput overhead; "
            "adds operational complexity and requires compatible Kafka version"
        ),
        citation="https://www.confluent.io/blog/exactly-once-semantics-are-possible-heres-how-apache-kafka-does-it/",
    ),
    StrategyEntry(
        name="at-most-once delivery",
        aliases=["at most once", "fire and forget", "best-effort delivery"],
        applies_to=["queue"],
        when_to_use=(
            "metrics, logs, analytics events where message loss is acceptable "
            "and low latency matters more than completeness"
        ),
        when_not_to_use=(
            "data loss is unacceptable; any business-critical event; "
            "financial or operational workflows"
        ),
        key_tradeoff=(
            "lowest overhead — no retry, no ack, no deduplication; "
            "message loss is expected and acceptable; "
            "simplest consumer logic: process once, no idempotency needed"
        ),
        citation="https://kafka.apache.org/documentation/#semantics",
    ),

    # ---------------------------------------------------------------------------
    # DB replication (3)
    # ---------------------------------------------------------------------------

    StrategyEntry(
        name="synchronous replication",
        aliases=["sync replication", "synchronous replica", "sync standby"],
        applies_to=["relational_db"],
        when_to_use=(
            "zero data loss required: financial data, audit logs, anything where "
            "losing a committed write is unacceptable"
        ),
        when_not_to_use=(
            "cross-region setups — the round-trip to the replica adds 50-300ms to "
            "every write; replica failure blocks all writes if no async fallback is configured"
        ),
        key_tradeoff=(
            "write latency = round-trip to replica before ack; "
            "replica failure or network partition blocks writes; "
            "zero data loss guarantee — every acked write is on at least two nodes"
        ),
        citation="https://www.postgresql.org/docs/current/warm-standby.html#SYNCHRONOUS-REPLICATION",
    ),
    StrategyEntry(
        name="asynchronous replication",
        aliases=["async replication", "async replica", "eventual replica", "lag replica"],
        applies_to=["relational_db"],
        when_to_use=(
            "geo-distributed replicas, read scale-out, analytics replicas, "
            "disaster recovery standby where some replication lag is acceptable"
        ),
        when_not_to_use=(
            "zero replication lag required; reads from replica must immediately "
            "reflect all committed writes; financial ledger reads"
        ),
        key_tradeoff=(
            "replica lag: reads from replica may be seconds behind primary; "
            "primary write is not blocked by replica; "
            "failover to an async replica risks losing the lag window of writes"
        ),
        citation="https://www.postgresql.org/docs/current/warm-standby.html",
    ),
    StrategyEntry(
        name="read replicas",
        aliases=["read replica", "replica scaling", "read scaling", "follower reads"],
        applies_to=["relational_db"],
        when_to_use=(
            "read-heavy workload, analytics queries, reporting, "
            "offload primary from read traffic without sharding"
        ),
        when_not_to_use=(
            "strongly consistent reads required — replica lag means eventual consistency; "
            "write-heavy workloads — replicas do not help writes, primary is still the bottleneck"
        ),
        key_tradeoff=(
            "read throughput scales horizontally by adding replicas; "
            "replica lag means stale reads; "
            "primary remains the write bottleneck — read replicas buy time, not unlimited scale"
        ),
        citation="https://aws.amazon.com/rds/features/read-replicas/",
    ),

    # ---------------------------------------------------------------------------
    # Partitioning (2)
    # ---------------------------------------------------------------------------

    StrategyEntry(
        name="Kafka partition key",
        aliases=["kafka partitioning", "partition key selection", "kafka key", "message key"],
        applies_to=["queue"],
        when_to_use=(
            "always required with Kafka; choose a key with high cardinality "
            "that evenly distributes writes — user_id, device_id, order_id"
        ),
        when_not_to_use=(
            "null key sends to a random partition and breaks ordering guarantees; "
            "low cardinality key (e.g., country code with 10 values) creates hot partitions"
        ),
        key_tradeoff=(
            "ordering is guaranteed only within a single partition; "
            "partition count is fixed at topic creation — changing it reorders messages; "
            "low cardinality keys cause write skew across partitions"
        ),
        citation="https://www.confluent.io/blog/how-choose-number-topics-partitions-kafka-cluster/",
    ),
    StrategyEntry(
        name="hot partition avoidance",
        aliases=["hot shard avoidance", "partition skew", "write skew", "hot key avoidance"],
        applies_to=["queue", "relational_db", "cache"],
        when_to_use=(
            "always consider when designing partition or shard keys; "
            "use composite keys or randomized suffixes to spread load across partitions"
        ),
        when_not_to_use=(
            "N/A — always relevant when sharding or partitioning; "
            "the question is not whether to apply it but how"
        ),
        key_tradeoff=(
            "adding randomness to keys prevents hot spots but breaks co-location — "
            "related records land on different shards; "
            "scatter-gather reads increase latency; choose between hotspot risk and query cost"
        ),
        citation="https://aws.amazon.com/blogs/database/choosing-the-right-dynamodb-partition-key/",
    ),
]
