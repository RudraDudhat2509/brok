"""Strategy knowledge base — 18 entries across 5 categories.

Fields are intentionally verbose. Short one-liners hurt both semantic retrieval
and the calling model's ability to reason correctly about when to apply a strategy.
Every entry has a `citation` field pointing to an authoritative source.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyEntry:
    name: str
    aliases: list[str]
    applies_to: list[str]
    when_to_use: str
    when_not_to_use: str
    key_tradeoff: str
    citation: str


STRATEGY_KB: list[StrategyEntry] = [
    # ---------------------------------------------------------------------------
    # SHARDING (4)
    # ---------------------------------------------------------------------------

    StrategyEntry(
        name="consistent hashing",
        aliases=["consistent hash", "ring hash", "hash ring", "consistent hashing ring",
                 "database sharding strategy", "postgres sharding", "how to shard postgres",
                 "cache sharding", "dynamo hashing"],
        applies_to=["distributed cache", "distributed database", "load balancing"],
        when_to_use=(
            "Use consistent hashing when you need to distribute data or requests "
            "across a dynamic set of nodes where nodes are added or removed frequently "
            "without a full data reshuffle. In a standard hash ring, adding or removing "
            "one node only remaps 1/N of the keys instead of all of them, minimizing "
            "cache invalidation storms when your cache cluster scales horizontally. "
            "Consistent hashing is the right strategy for distributed caches (Redis Cluster, "
            "Memcached clusters), distributed key-value stores, and load balancers that need "
            "session affinity without a centralized session store. DynamoDB and Cassandra "
            "both use consistent hashing internally to route keys to the correct node."
        ),
        when_not_to_use=(
            "Do not use consistent hashing when your data has natural range query patterns "
            "that benefit from colocation — consistent hashing scatters data uniformly, "
            "so range queries (all users with IDs 1000-2000) become full scatter-gather "
            "across all nodes instead of a single sequential scan. Avoid it when you have "
            "a fixed, small number of nodes that never change — the benefit of minimal "
            "remapping on node changes is only meaningful when node changes are frequent. "
            "Also avoid when hot keys are a risk: consistent hashing assigns one node per "
            "key, so a single viral key still overloads one node without virtual nodes or "
            "application-level key splitting."
        ),
        key_tradeoff=(
            "Consistent hashing distributes load evenly only in theory — in practice, "
            "with small cluster sizes (fewer than 100 nodes), standard consistent hashing "
            "creates uneven load distribution due to non-uniform spacing on the ring. "
            "Virtual nodes (vnodes), where each physical node is assigned many positions "
            "on the ring, fix this but add complexity to the node removal algorithm. Hot "
            "keys are still a problem even with consistent hashing; a single heavily-"
            "accessed key always maps to the same node."
        ),
        citation="https://www.dynamo.amazon.com/dynamo-sosp2007.pdf",
    ),
    StrategyEntry(
        name="range-based sharding",
        aliases=["range sharding", "range partitioning", "range shard",
                 "time-series sharding"],
        applies_to=["relational database", "time-series database", "distributed database"],
        when_to_use=(
            "Use range-based sharding when your queries are primarily range-based — "
            "scanning users by signup date, fetching orders in a date window, or "
            "querying metrics by time range. Because range sharding colocates adjacent "
            "keys on the same shard, a range query can be served by a single shard "
            "instead of scatter-gathering across all shards. This makes it the natural "
            "strategy for time-series data (logs, IoT readings, financial ticks) where "
            "the query pattern is almost always time-bounded. PostgreSQL partitioning "
            "by date is range-based sharding in practice."
        ),
        when_not_to_use=(
            "Do not use range-based sharding when writes are write-heavy and "
            "monotonically increasing (sequential IDs, timestamps) — all new writes go "
            "to the last range shard, creating a hot shard that handles all writes while "
            "other shards are idle. This is the last-shard hotspot problem and it defeats "
            "the purpose of sharding. Avoid range-based sharding for access patterns that "
            "are not range-based; if queries access random keys uniformly distributed "
            "across the key space, consistent hashing or hash sharding has no range-scan "
            "advantage and makes shard rebalancing more complex."
        ),
        key_tradeoff=(
            "Range-based sharding is excellent for range queries but vulnerable to write "
            "hotspots when the key is monotonically increasing. The classic fix is shard "
            "splitting — when the last shard exceeds a size threshold, split it in two — "
            "but split operations require data movement and brief unavailability in many "
            "systems. Shard rebalancing is more manual than consistent hashing and "
            "typically requires a maintenance window or online migration."
        ),
        citation="https://docs.mongodb.com/manual/core/ranged-sharding/",
    ),
    StrategyEntry(
        name="hash-based sharding",
        aliases=["hash sharding", "hash partition", "hashed sharding", "modulo sharding"],
        applies_to=["relational database", "distributed key-value store"],
        when_to_use=(
            "Use hash-based sharding when you need uniform write distribution across "
            "shards and your access pattern is primarily point lookups by a known key. "
            "Hash sharding applies a hash function to the shard key and assigns the "
            "record to shard hash(key) % N, ensuring writes are distributed evenly and "
            "no single shard becomes a hotspot for new writes. It is the right strategy "
            "for user data sharded by user ID, product data sharded by product ID, "
            "and any workload where writes are random across the key space rather "
            "than monotonically increasing."
        ),
        when_not_to_use=(
            "Do not use hash-based sharding when you need range queries on the shard "
            "key — hashing destroys the ordering of keys, so a range query becomes a "
            "full scatter-gather across all shards. Avoid hash-based sharding when you "
            "need to frequently change the number of shards — changing N in hash(key) % N "
            "remaps the majority of keys, causing a massive data migration. Use consistent "
            "hashing instead if you expect the number of shards to change. Also avoid when "
            "locality matters: related data (all records for one tenant) may end up on "
            "different shards, making cross-shard joins expensive."
        ),
        key_tradeoff=(
            "Hash-based sharding distributes writes evenly but makes range queries and "
            "cross-shard joins expensive scatter-gather operations. The number of shards "
            "is effectively fixed at deployment time — changing N requires a full data "
            "migration in most implementations. Hot keys (a single user with extreme "
            "activity) still overload a single shard; application-level key splitting "
            "is required to handle them."
        ),
        citation="https://www.mongodb.com/docs/manual/core/hashed-sharding/",
    ),
    StrategyEntry(
        name="directory-based sharding",
        aliases=["directory sharding", "lookup table sharding", "shard map"],
        applies_to=["relational database", "multi-tenant system"],
        when_to_use=(
            "Use directory-based sharding when you need maximum flexibility in how data "
            "is routed to shards — for example, when tenants need to be moved between "
            "shards for capacity reasons, or when different tenants have wildly different "
            "data volumes and need custom shard placement. A lookup table maps each "
            "shard key to its assigned shard, giving you complete control over placement. "
            "This is the right strategy for multi-tenant SaaS platforms where a single "
            "enterprise customer may need a dedicated shard and a long tail of small "
            "customers share a shard."
        ),
        when_not_to_use=(
            "Do not use directory-based sharding when the lookup table itself becomes a "
            "bottleneck — every read and write must consult the directory, and if the "
            "directory is a single point of failure, the entire system fails. Avoid it "
            "when your keys are uniformly distributed and consistent hashing or hash "
            "sharding would work — the lookup table adds a read per request and "
            "operational complexity without benefit. Directory-based sharding is also "
            "wrong for extremely high-throughput systems where the extra lookup latency "
            "is unacceptable."
        ),
        key_tradeoff=(
            "The directory is both the power and the weakness of this approach: it "
            "enables arbitrary shard placement and live migration, but it is a centralized "
            "component that must be highly available and low-latency. Caching the "
            "directory in the application tier reduces lookup overhead but introduces "
            "stale routing bugs when shards are migrated. The lookup table itself grows "
            "with the number of tenants and must be maintained as a consistent source "
            "of truth."
        ),
        citation="https://docs.microsoft.com/en-us/azure/architecture/patterns/sharding",
    ),

    # ---------------------------------------------------------------------------
    # CACHE EVICTION (6)
    # ---------------------------------------------------------------------------

    StrategyEntry(
        name="LRU",
        aliases=["lru cache", "lru eviction", "least recently used", "lru policy"],
        applies_to=["cache"],
        when_to_use=(
            "Use LRU eviction when your access pattern has temporal locality — recently "
            "accessed items are likely to be accessed again soon. LRU keeps the most "
            "recently accessed items in the cache and evicts items that have not been "
            "accessed for the longest time. It is the right choice for session caches, "
            "user profile caches, and application-level caches where the working set "
            "shifts over time but recently accessed items are a strong predictor of "
            "future access. Redis uses LRU as its default eviction policy (volatile-lru "
            "and allkeys-lru). LRU is the correct default for most general-purpose caches "
            "when you do not have specific access pattern information."
        ),
        when_not_to_use=(
            "Do not use LRU when your access pattern is scan-heavy — a full table scan "
            "or large batch job will evict the entire working set for the interactive "
            "application, causing a cache miss storm when normal traffic resumes. This "
            "is the cache pollution problem: a one-time sequential scan touches every "
            "key once, making everything look recently used to LRU and evicting the hot "
            "working set. Also avoid LRU for data with non-uniform access frequency "
            "where some items are accessed thousands of times per second and others "
            "rarely — LFU may be a better fit in that case."
        ),
        key_tradeoff=(
            "LRU is vulnerable to cache pollution from sequential scans and batch jobs. "
            "In high-churn environments, the LRU linked list update on every cache hit "
            "adds contention under concurrent access — many implementations use an "
            "approximate LRU (like Redis's random-sample LRU) to avoid this. LRU does "
            "not account for access frequency, only recency, so a rarely accessed item "
            "that was just accessed once will be kept while a frequently accessed item "
            "that was not touched recently gets evicted."
        ),
        citation="https://redis.io/docs/latest/develop/reference/eviction/",
    ),
    StrategyEntry(
        name="LFU",
        aliases=["lfu cache", "lfu eviction", "least frequently used", "lfu policy",
                 "frequency-based eviction"],
        applies_to=["cache"],
        when_to_use=(
            "Use LFU eviction when access frequency is a better predictor of future "
            "access than recency — for example, popular product pages, frequently "
            "queried database rows, or hot API response caches where some items are "
            "accessed orders of magnitude more often than others. LFU tracks access "
            "counts and evicts the item with the lowest count when the cache is full, "
            "which means truly popular items stay in cache even if they were not "
            "accessed in the last few seconds. Redis supports LFU with the allkeys-lfu "
            "and volatile-lfu policies. It is the right choice for workloads with a "
            "clear power-law distribution in access patterns (Pareto distribution)."
        ),
        when_not_to_use=(
            "Do not use LFU when your workload has shifting popularity — an item that "
            "was popular a week ago but is no longer relevant will have a high "
            "historical frequency count and will be retained in cache even if no one "
            "is accessing it now. This is the cache pollution by historical popularity "
            "problem. Avoid LFU for temporal caches like breaking news, trending topics, "
            "or promotional sales where today's hot item is tomorrow's stale data. "
            "LFU also requires maintaining frequency counters for every cached item, "
            "which adds memory overhead compared to LRU."
        ),
        key_tradeoff=(
            "LFU's weakness is that it optimizes for historical popularity, not current "
            "demand. A stale popular item (high count from past traffic but no recent "
            "access) will crowd out a newly popular item still building its count. "
            "Decay mechanisms (halving counts periodically) address this but introduce "
            "tuning parameters. Frequency counters add per-item memory overhead, and "
            "updating them on every access adds write contention in high-throughput "
            "scenarios."
        ),
        citation="https://redis.io/docs/latest/develop/reference/eviction/",
    ),
    StrategyEntry(
        name="TTL",
        aliases=["ttl cache", "time to live", "cache expiry", "cache ttl", "cache expiration",
                 "cache invalidation"],
        applies_to=["cache"],
        when_to_use=(
            "Use TTL eviction when your data has a known staleness window — after T "
            "seconds, the cached value is no longer valid and should be re-fetched "
            "from the source. TTL is the right choice for external API response caching "
            "(weather data valid for 10 minutes, currency exchange rates valid for 1 "
            "minute), database query caches where updates are periodic and a brief "
            "stale window is acceptable, and session tokens that must expire for "
            "security reasons. TTL is simpler to reason about than LRU or LFU because "
            "expiration is deterministic and independent of access patterns."
        ),
        when_not_to_use=(
            "Do not use TTL as the sole invalidation strategy when data changes "
            "unpredictably — if a product price changes mid-TTL window, all users see "
            "the old price until the TTL expires. Avoid TTL for correctness-critical "
            "data like inventory counts or account balances where even a 5-second stale "
            "window causes real harm. Also avoid setting TTLs too short on expensive-to-"
            "compute cache values — a cache that expires every 5 seconds under high "
            "concurrency creates a thundering herd where all misses simultaneously "
            "trigger the same expensive backend computation."
        ),
        key_tradeoff=(
            "TTL creates predictable cache invalidation at the cost of serving potentially "
            "stale data for up to T seconds after an update. The thundering herd problem "
            "occurs when a popular item's TTL expires under high concurrency: many requests "
            "simultaneously miss the cache and all attempt to recompute or refetch the same "
            "value at once. Mitigation techniques include jittered TTLs (randomizing "
            "expiration across a window) and probabilistic early expiration (recomputing "
            "slightly before TTL to warm the cache before the miss)."
        ),
        citation="https://redis.io/docs/latest/commands/expire/",
    ),
    StrategyEntry(
        name="write-through",
        aliases=["write through cache", "synchronous write cache", "write-through strategy"],
        applies_to=["cache"],
        when_to_use=(
            "Use write-through caching when read consistency is critical — every write "
            "updates both the cache and the database in the same synchronous operation "
            "before returning to the caller. This ensures that any subsequent read "
            "from the cache gets the latest data because the cache is always in sync "
            "with the database. It is the right strategy for caches that serve "
            "correctness-critical reads where stale data causes real problems, such "
            "as user profile caches, pricing caches, or configuration caches where "
            "reads must always reflect the latest write."
        ),
        when_not_to_use=(
            "Do not use write-through when your workload is write-heavy — every write "
            "pays double the latency (write to cache and write to database synchronously), "
            "which slows write throughput significantly. Avoid it when the data being "
            "written is rarely read; for write-heavy, read-light data, the cache "
            "consistently holds data that is never requested, wasting memory. Also avoid "
            "write-through when the database write can fail: if the cache updates but "
            "the database write fails, the cache holds data that was never durably "
            "stored, creating an inconsistency that requires cache rollback logic."
        ),
        key_tradeoff=(
            "Write-through guarantees cache-database consistency at the cost of write "
            "latency — every write pays both the cache write and the database write "
            "before returning. For write-heavy workloads, this doubles the latency "
            "on the hot path. The cache may fill with rarely-read data, reducing "
            "the effective hit rate and wasting memory on writes that are never "
            "subsequently read."
        ),
        citation="https://docs.aws.amazon.com/whitepapers/latest/database-caching-strategies-using-redis/caching-patterns.html",
    ),
    StrategyEntry(
        name="write-back",
        aliases=["write behind", "write-behind", "lazy write", "async write cache",
                 "write-back cache"],
        applies_to=["cache"],
        when_to_use=(
            "Use write-back caching (also called write-behind) when your workload is "
            "write-heavy and you can tolerate a window of data loss in an extreme "
            "failure scenario. Write-back writes to the cache first and asynchronously "
            "flushes to the database in the background, removing the database write "
            "from the hot path and dramatically improving write latency. It is the right "
            "strategy for high-frequency counters (view counts, like counts), logging "
            "pipelines, and any write workload where sub-millisecond write latency "
            "matters more than zero data loss on cache failure. Leaderboard writes in "
            "Redis with periodic Postgres sync are a common implementation."
        ),
        when_not_to_use=(
            "Do not use write-back for financial transactions, order records, or any "
            "data where losing writes is unacceptable — if the cache node fails before "
            "flushing to the database, those writes are permanently lost. Avoid it when "
            "correctness of reads is critical: another service reading directly from the "
            "database will see stale data until the async flush completes, causing "
            "read inconsistency. Write-back is also wrong for infrequent writes to "
            "durable data where the added complexity of async flushing and failure "
            "recovery is not justified by performance gains."
        ),
        key_tradeoff=(
            "Write-back maximizes write throughput at the cost of durability: writes "
            "sitting in the cache but not yet flushed to the database are lost on cache "
            "failure. The flush pipeline requires careful implementation — batching, "
            "retry on database errors, ordering guarantees for dependent writes, and "
            "a recovery strategy when the queue grows faster than the database can "
            "absorb it. This is significantly more complex than write-through."
        ),
        citation="https://redis.io/docs/latest/develop/interact/programmability/",
    ),
    StrategyEntry(
        name="write-around",
        aliases=["write around", "cache bypass", "lazy read cache", "read-only cache"],
        applies_to=["cache"],
        when_to_use=(
            "Use write-around caching when your data is written once and then rarely "
            "or never read back — large files, batch job outputs, bulk imports, and "
            "archive writes are good examples. Write-around bypasses the cache entirely "
            "on writes (going directly to the database or object store), preventing "
            "infrequently-accessed write data from polluting the cache and evicting "
            "hot read data. The cache is only populated on reads, so only data that "
            "is actually requested multiple times earns a cache slot. It is the right "
            "strategy when write throughput is high but the majority of written items "
            "will never be read again."
        ),
        when_not_to_use=(
            "Do not use write-around when you need to read the data you just wrote "
            "immediately — the first read after a write will always miss the cache and "
            "go to the database, introducing the read-your-own-write latency on the "
            "first access. Avoid write-around for frequently-updated small objects "
            "where the update is likely to be read soon after — write-through or "
            "cache-aside is better for those patterns. Write-around also provides no "
            "benefit when all data is equally likely to be read, since the cache will "
            "fill up through reads anyway."
        ),
        key_tradeoff=(
            "Write-around keeps the cache clean by preventing write-heavy data from "
            "evicting hot read data, but it means the first read of any recently written "
            "item always goes to the database. In workloads where writes are followed "
            "by reads (e.g., upload an image, then display it on a profile page), the "
            "initial read misses the cache and the latency is higher than with "
            "write-through. The advantage only materializes when written data is "
            "rarely or never read back."
        ),
        citation="https://docs.aws.amazon.com/whitepapers/latest/database-caching-strategies-using-redis/caching-patterns.html",
    ),

    # ---------------------------------------------------------------------------
    # QUEUE DELIVERY (3)
    # ---------------------------------------------------------------------------

    StrategyEntry(
        name="at-least-once delivery",
        aliases=["at least once", "atleastonce", "retry delivery", "exactly-once alternative"],
        applies_to=["message queue"],
        when_to_use=(
            "Use at-least-once delivery when message loss is unacceptable and your "
            "consumers can handle receiving the same message more than once without "
            "causing incorrect behavior — that is, when consumers are idempotent. "
            "At-least-once is the most common delivery guarantee in practice because "
            "it is simple to implement (the broker retries until it receives an "
            "acknowledgement) and the idempotency requirement is usually achievable "
            "by deduplicating on a message ID or making the operation naturally "
            "idempotent (setting a value to X is idempotent; incrementing by 1 is not). "
            "SQS standard queues, Kafka consumer groups, and most pub-sub systems "
            "provide at-least-once delivery by default."
        ),
        when_not_to_use=(
            "Do not use at-least-once delivery when duplicate message processing causes "
            "real harm that cannot be mitigated by idempotency — for example, charging "
            "a credit card twice, sending the same email twice, or creating a duplicate "
            "order. In these cases, you need exactly-once semantics or a deduplication "
            "layer. At-least-once is also the wrong guarantee when the business logic "
            "cannot be made idempotent without significant refactoring — the simplicity "
            "advantage disappears if you end up building a complex deduplication system "
            "that is as hard to operate as exactly-once delivery."
        ),
        key_tradeoff=(
            "At-least-once requires idempotent consumers, which is a design constraint "
            "that propagates through the entire downstream system. Non-idempotent "
            "operations (financial transactions, email sends, inventory decrements) "
            "must be wrapped in deduplication logic keyed on a message ID, and that "
            "deduplication store becomes a component that must be highly available and "
            "consistent. The alternative — exactly-once delivery — is more complex to "
            "build but removes the idempotency burden from consumers."
        ),
        citation="https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/standard-queues.html",
    ),
    StrategyEntry(
        name="at-most-once delivery",
        aliases=["at most once", "atmostone", "fire and forget"],
        applies_to=["message queue"],
        when_to_use=(
            "Use at-most-once delivery when low latency and simplicity matter more "
            "than guaranteed delivery — the broker sends the message once and does not "
            "retry on failure. This is appropriate for metrics, telemetry, real-time "
            "analytics events, and log shipping where a small percentage of dropped "
            "messages is acceptable and does not affect system correctness. At-most-once "
            "is also the right choice for pub-sub notifications where subscribers are "
            "expected to be online and a missed message is not critical (UI push "
            "notifications, live dashboards). It is simpler to implement and has lower "
            "overhead than at-least-once because there is no acknowledgement tracking."
        ),
        when_not_to_use=(
            "Do not use at-most-once delivery for any business-critical message where "
            "loss is unacceptable — order confirmations, payment notifications, user "
            "account creation events, or any message that triggers an irreversible "
            "action. At-most-once is also wrong when you need audit logs or compliance "
            "records where every event must be captured. The simplicity of at-most-once "
            "is only a tradeoff when the dropped message rate is acceptable to the "
            "business, which rules out most transactional use cases."
        ),
        key_tradeoff=(
            "At-most-once is the simplest delivery guarantee to implement but it accepts "
            "message loss as a fact of life. The drop rate depends on the broker, network, "
            "and consumer availability; in a well-operated system it may be under 0.1%, "
            "but under failure conditions it can be much higher. There is no built-in "
            "mechanism for detecting or recovering dropped messages, so monitoring and "
            "alerting on downstream business metrics is the only way to detect silent "
            "message loss."
        ),
        citation="https://kafka.apache.org/documentation/#semantics",
    ),
    StrategyEntry(
        name="exactly-once delivery",
        aliases=["exactly once", "exactlyonce", "kafka exactly once", "deduplication delivery",
                 "transactional messaging"],
        applies_to=["message queue"],
        when_to_use=(
            "Use exactly-once delivery when duplicate message processing causes "
            "irreversible harm that cannot be addressed by making consumers idempotent "
            "— financial double-charges, duplicate order creation, or any operation "
            "where deduplication logic in the consumer is impractical or insufficient. "
            "Kafka supports exactly-once semantics via idempotent producers and "
            "transactional APIs (Kafka Streams and the producer transactional API). "
            "Exactly-once is the right guarantee for payment processing pipelines, "
            "inventory management, and compliance-critical event streams where "
            "correctness is non-negotiable and the additional overhead is worth it."
        ),
        when_not_to_use=(
            "Do not use exactly-once delivery as the default when at-least-once with "
            "idempotent consumers would suffice — exactly-once is significantly more "
            "complex and adds measurable latency and throughput overhead. In Kafka, "
            "transactional producers have higher per-message overhead and require "
            "careful configuration of transaction coordinators and epoch management. "
            "Exactly-once across heterogeneous systems (a Kafka topic and a relational "
            "database in the same transaction) requires the two-phase commit pattern "
            "or the Outbox pattern, both of which add substantial complexity. Do not "
            "use it if your consumers can be made idempotent with a simple deduplication "
            "key."
        ),
        key_tradeoff=(
            "Exactly-once delivery in Kafka requires transactional producers and "
            "consumers, which adds latency overhead per batch and requires the "
            "transactional.id and isolation.level configurations to be set correctly. "
            "The throughput is lower than at-least-once due to the coordination "
            "overhead. Exactly-once within a single Kafka cluster is well-supported; "
            "exactly-once across Kafka and an external database requires the Outbox "
            "pattern or two-phase commit, each with its own complexity and failure modes."
        ),
        citation="https://www.confluent.io/blog/exactly-once-semantics-are-possible-heres-how-apache-kafka-does-it/",
    ),

    # ---------------------------------------------------------------------------
    # DB REPLICATION (3)
    # ---------------------------------------------------------------------------

    StrategyEntry(
        name="synchronous replication",
        aliases=["sync replication", "synchronous replica", "zero-lag replication",
                 "strong consistency replication"],
        applies_to=["relational database", "cache"],
        when_to_use=(
            "Use synchronous replication when you require zero data loss on primary "
            "failure and can accept the write latency cost. In synchronous replication, "
            "the primary waits for at least one replica to acknowledge the write before "
            "returning success to the client — this means a replica is always at least "
            "one write behind the primary, and promoting it on failure loses no committed "
            "data. PostgreSQL synchronous_standby_names and synchronous_commit = on "
            "enables this. Use synchronous replication for financial data, payment "
            "records, and any dataset where losing even one committed transaction is "
            "unacceptable."
        ),
        when_not_to_use=(
            "Do not use synchronous replication when write latency is a hard requirement "
            "— every write now waits for a network round-trip to the synchronous replica "
            "before returning, which adds the full round-trip time (typically 1-30ms "
            "depending on proximity) to every write. For a replica in a different "
            "availability zone or region, this can add 50-200ms to write latency. "
            "Avoid synchronous replication for high-write-throughput workloads where "
            "that latency overhead accumulates under concurrency. If your workload can "
            "tolerate replaying the last few seconds of writes from a WAL backup, "
            "asynchronous replication with point-in-time recovery is usually sufficient."
        ),
        key_tradeoff=(
            "Synchronous replication gives you zero-data-loss failover at the cost of "
            "write latency. Every write adds the replica round-trip time before returning "
            "to the caller. If the synchronous replica becomes unreachable, PostgreSQL "
            "with synchronous_commit = on will block all writes until the replica "
            "reconnects or is removed from the synchronous standby list — making the "
            "synchronous replica a potential availability bottleneck."
        ),
        citation="https://www.postgresql.org/docs/current/warm-standby.html",
    ),
    StrategyEntry(
        name="asynchronous replication",
        aliases=["async replication", "async replica", "lag replication",
                 "eventual consistency replication"],
        applies_to=["relational database", "distributed database"],
        when_to_use=(
            "Use asynchronous replication as the default replication strategy when you "
            "want read scale-out and high availability without paying a write latency "
            "penalty. In asynchronous replication, the primary commits the write and "
            "returns success immediately without waiting for replicas to acknowledge — "
            "replicas apply the changes shortly after, introducing a replication lag "
            "window. This is PostgreSQL's default streaming replication mode and is "
            "appropriate for most web applications where reads heavily outnumber writes "
            "and a brief stale read window is acceptable. It is also the right choice "
            "for running analytical queries on replicas without impacting the primary."
        ),
        when_not_to_use=(
            "Do not use asynchronous replication when your application requires "
            "read-your-own-writes consistency from replicas — a write to the primary "
            "may not yet be visible on the replica when the same request reads from it "
            "milliseconds later. Avoid asynchronous replication when data loss on "
            "primary failure is unacceptable — any writes that were committed to the "
            "primary but not yet applied to the replica at the time of failure are "
            "permanently lost. For RPO = 0 (zero data loss), use synchronous replication "
            "instead."
        ),
        key_tradeoff=(
            "Replication lag is the core operational concern: how far behind the replica "
            "is from the primary determines the staleness window for reads and the "
            "potential data loss window on failover. Under heavy write load, replica lag "
            "can grow to seconds or more, causing visible staleness for read-replica "
            "users. Monitoring replication lag and alerting when it exceeds a threshold "
            "is a required operational practice when relying on async replicas."
        ),
        citation="https://www.postgresql.org/docs/current/warm-standby.html",
    ),
    StrategyEntry(
        name="read replicas",
        aliases=["read replica scaling", "replica routing", "primary-replica routing",
                 "postgres read replicas", "mysql read replicas"],
        applies_to=["relational database"],
        when_to_use=(
            "Use the read replica strategy when your application is read-heavy and a "
            "single database instance cannot serve the read throughput at acceptable "
            "latency. By routing read queries to one or more read replicas and write "
            "queries to the primary, you scale read throughput linearly with the number "
            "of replicas. This is appropriate for web applications where reads outnumber "
            "writes 10:1 or more, for reporting and analytics queries that would overload "
            "the primary, and for geographic distribution (a replica in a different region "
            "serves local users with lower latency). RDS, Cloud SQL, and Heroku Postgres "
            "all offer managed read replicas."
        ),
        when_not_to_use=(
            "Do not use read replicas to scale writes — all writes still go to a single "
            "primary, so adding replicas does nothing for write throughput. Read replicas "
            "introduce eventual consistency: reads from replicas may return data that is "
            "milliseconds to seconds behind the primary, which breaks read-your-own-write "
            "expectations. Avoid routing all reads to replicas if your application "
            "requires strong consistency — instead, route only reads that can tolerate "
            "stale data to replicas, and route consistency-sensitive reads to the primary."
        ),
        key_tradeoff=(
            "Read replicas trade strong consistency for horizontal read scale. The "
            "replication lag — time between a write to the primary and visibility on a "
            "replica — determines the staleness window. Under heavy write load, this lag "
            "can grow. The application must implement read routing logic (or use a "
            "connection proxy) to direct reads to replicas and writes to the primary, "
            "and must gracefully handle the case where a replica lags behind."
        ),
        citation="https://aws.amazon.com/rds/features/read-replicas/",
    ),

    # ---------------------------------------------------------------------------
    # PARTITIONING (2)
    # ---------------------------------------------------------------------------

    StrategyEntry(
        name="Kafka partition key",
        aliases=["kafka partitioning", "kafka key selection", "partition key strategy",
                 "kafka ordering key"],
        applies_to=["message queue", "kafka"],
        when_to_use=(
            "Choose a meaningful Kafka partition key when message ordering within a "
            "logical group matters and you need related messages to land on the same "
            "partition. Kafka guarantees ordering only within a single partition, so "
            "if you need all events for a given user, order, or entity to be processed "
            "in order, use the entity ID as the partition key. With a well-chosen "
            "partition key, a single consumer thread processes all messages for one "
            "entity in sequence, making stateful processing (aggregations, state "
            "machines) straightforward and correct without cross-partition coordination."
        ),
        when_not_to_use=(
            "Do not use a partition key that creates hot partitions — if one key has "
            "dramatically more messages than others (a single viral user, a single hot "
            "product), that partition receives all traffic while other partitions are "
            "idle. Avoid using a high-cardinality field that changes frequently as the "
            "partition key, as this spreads messages for the same entity across multiple "
            "partitions when the key changes. If global message ordering matters (not "
            "just per-entity ordering), a single partition key is insufficient; Kafka "
            "cannot guarantee global order across partitions."
        ),
        key_tradeoff=(
            "A good partition key ensures ordering and locality for related messages "
            "but it determines the partition distribution forever — rekeying (changing "
            "what the partition key is) requires either a topic migration or a period "
            "where both old and new consumers run in parallel. A hot partition key "
            "wastes cluster capacity: parallelism is bounded by partition count, and "
            "if one partition is much busier than others, adding partitions does not "
            "help the hot partition."
        ),
        citation="https://developer.confluent.io/courses/apache-kafka/partitions/",
    ),
    StrategyEntry(
        name="hot partition avoidance",
        aliases=["partition hotspot", "partition skew", "even partition distribution",
                 "partition load balancing"],
        applies_to=["message queue", "distributed database", "kafka"],
        when_to_use=(
            "Apply hot partition avoidance strategies when you observe that one or a few "
            "partitions receive dramatically more traffic than others, causing those "
            "partitions to become bottlenecks while other partitions are underutilized. "
            "Strategies include: adding a random suffix or salt to the partition key to "
            "spread a hot key across multiple partitions, using a time-based partition "
            "key that distributes writes across all partitions as time advances, or "
            "increasing the partition count to give the hash function more space to "
            "distribute keys. Hot partition avoidance is especially important for "
            "Kafka topics that feed real-time processing pipelines where partition "
            "skew causes pipeline stalls."
        ),
        when_not_to_use=(
            "Do not apply hot partition avoidance by adding random salts to partition "
            "keys when ordering within a logical group matters — randomizing the key "
            "scatters related messages across partitions, breaking per-entity ordering "
            "guarantees. In this case, accept the hot partition or redesign the data "
            "model to split the hot entity into sub-entities that can be distributed. "
            "Avoid increasing partition count as a reflexive response to skew — more "
            "partitions increase broker memory overhead, increase the number of open "
            "file handles, and slow down leader election; only increase partitions when "
            "the current count is actually the bottleneck."
        ),
        key_tradeoff=(
            "Hot partition avoidance via key salting trades ordering for distribution — "
            "a salted key distributes load evenly but breaks the guarantee that related "
            "messages go to the same partition. Consumer-side aggregation across "
            "partitions is required, adding complexity and latency to stateful processing. "
            "Increasing partition count reduces skew by giving more hash slots but "
            "has a fixed overhead cost per partition on every broker."
        ),
        citation="https://www.confluent.io/blog/how-choose-number-topics-partitions-kafka-cluster/",
    ),
]
