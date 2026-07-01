"""Technology knowledge base — 25 entries across 7 categories.

Every entry has a `citation` field pointing to an official source for its
throughput numbers and trade-off claims. Nothing is invented here: if a claim
cannot be traced to a citation it does not belong in this file.

Fields are intentionally verbose. Short one-liners hurt both semantic retrieval
(the embedding model needs rich text to build good concept vectors) and the
calling model (which needs enough context to make a real decision, not a keyword).
"""
from __future__ import annotations

from dataclasses import dataclass

from brok.models import ComponentType


@dataclass(frozen=True)
class TechEntry:
    name: str
    aliases: list[str]
    category: ComponentType
    hosted: bool
    when_to_pick: str
    when_not_to_pick: str
    throughput_ceiling: str
    key_tradeoff: str
    citation: str


# ---------------------------------------------------------------------------
# QUEUE (5)
# ---------------------------------------------------------------------------

TECH_KB: list[TechEntry] = [
    TechEntry(
        name="Kafka",
        aliases=["apache kafka", "confluent kafka", "kafka broker", "kafka cluster",
                 "spiky traffic queue", "spiky writes queue", "burst traffic", "event streaming"],
        category=ComponentType.QUEUE,
        hosted=False,
        when_to_pick=(
            "Choose Kafka when you need a durable, ordered event log that multiple "
            "independent consumer groups can read at their own pace, potentially replaying "
            "from any historical offset. It is the right foundation for high-throughput "
            "event streaming — user activity pipelines, real-time analytics, audit logs, "
            "and microservice communication where the same event triggers several downstream "
            "systems. Kafka handles millions of messages per second per cluster and gives you "
            "per-partition ordering guarantees, making it ideal for scenarios where sequence "
            "matters and data must survive broker restarts. If your system needs to know what "
            "happened and in what order, and multiple teams need that same stream independently, "
            "Kafka is the right foundation."
        ),
        when_not_to_pick=(
            "Do not choose Kafka when your team cannot operate a distributed system — it "
            "requires broker sizing, partition management, consumer group coordination, and "
            "either ZooKeeper or KRaft. It is self-hosted and pull-based, meaning consumers "
            "must poll and track their own offsets; if you need the broker to push messages "
            "to your service, use Pub/Sub or SQS instead. Kafka is the wrong choice for "
            "simple task queues where you just need to fire a background job and have it "
            "executed once — Celery or SQS are far simpler fits for that pattern. Also avoid "
            "Kafka for complex exchange-based routing (topic, fanout, direct) where "
            "RabbitMQ's AMQP model is a better semantic match."
        ),
        throughput_ceiling=(
            "Millions of messages/sec per cluster; single partition ~100 MB/s "
            "(Confluent performance benchmarks)"
        ),
        key_tradeoff=(
            "Kafka trades operational simplicity for scale and durability. The pull model "
            "gives consumers control over their own pace, which is powerful but adds the "
            "responsibility of offset management — if a consumer falls behind, it may lag "
            "hours behind the live stream and affect other consumers sharing the same "
            "partition count. Partition count is fixed at topic creation; increasing it later "
            "breaks per-key ordering because existing messages were routed by the old count. "
            "The total ops cost is high: cluster sizing, partition rebalancing, consumer lag "
            "monitoring, and schema evolution via a schema registry are all your problem."
        ),
        citation="https://developer.confluent.io/learn/kafka-performance/",
    ),
    TechEntry(
        name="Pub/Sub",
        aliases=["google pub/sub", "google cloud pub/sub", "gcp pubsub", "cloud pubsub",
                 "push notifications", "push delivery queue", "managed message bus"],
        category=ComponentType.QUEUE,
        hosted=True,
        when_to_pick=(
            "Choose Pub/Sub when you need a fully managed, push-delivery message bus "
            "that scales globally with zero infrastructure to operate. It is the right "
            "choice in Google Cloud ecosystems where your consumers are HTTP endpoints "
            "or Cloud Functions that should receive messages without polling. Pub/Sub "
            "handles fan-out well — one published message can be delivered to many "
            "independent subscriptions simultaneously, making it suitable for event "
            "broadcasting, notification pipelines, and triggering serverless workflows. "
            "If you want Kafka-level scale without Kafka's operational overhead and you "
            "are already in GCP, Pub/Sub is the default answer."
        ),
        when_not_to_pick=(
            "Do not use Pub/Sub when you need strict per-key message ordering across all "
            "messages — Pub/Sub has no global ordering guarantee. While ordering keys exist, "
            "they only guarantee order within a single key, not across the entire topic, "
            "which is fundamentally different from Kafka's partition-level ordering. Avoid "
            "Pub/Sub for message replay at consumer scale — subscriptions start from the "
            "moment they are created and Pub/Sub only retains messages for up to 7 days. "
            "If you are not in a GCP stack, the integration advantage disappears and you "
            "should evaluate SQS or Kafka instead."
        ),
        throughput_ceiling=(
            "Millions of messages/sec globally; push delivery adds one HTTP round-trip "
            "per message to your endpoint (GCP Pub/Sub overview)"
        ),
        key_tradeoff=(
            "Pub/Sub's push model is a double-edged sword: it removes consumer polling "
            "complexity but requires your endpoint to be reachable and handle backpressure "
            "gracefully — if your service is slow, Pub/Sub will retry with exponential "
            "backoff, potentially delivering the same message many times. There is no "
            "global ordering guarantee across ordering keys, which surprises teams expecting "
            "Kafka-style partition ordering. The 7-day message retention limit means it "
            "cannot be used as a replay buffer for long-term event sourcing."
        ),
        citation="https://cloud.google.com/pubsub/docs/overview",
    ),
    TechEntry(
        name="SQS",
        aliases=["amazon sqs", "aws sqs", "simple queue service",
                 "spiky traffic queue", "burst queue", "aws managed queue",
                 "push notification queue managed", "managed push queue"],
        category=ComponentType.QUEUE,
        hosted=True,
        when_to_pick=(
            "Choose SQS when you need a simple, fully managed decoupling layer on AWS "
            "that handles spiky or burst traffic without any infrastructure to operate. "
            "It is the right choice for background job queues, async task pipelines, "
            "and decoupling microservices where at-least-once delivery is acceptable "
            "and you want the visibility timeout pattern for safe retry. SQS integrates "
            "natively with Lambda, ECS, and other AWS services, making it the path of "
            "least resistance for AWS-native async workflows. The standard queue has "
            "virtually unlimited throughput and the dead-letter queue feature makes "
            "poison message handling easy."
        ),
        when_not_to_pick=(
            "Do not use SQS when you need strict FIFO ordering without the FIFO variant "
            "— standard SQS delivers messages at-least-once and may deliver them out of "
            "order. Even the FIFO variant caps at 3,000 TPS with batching, which is orders "
            "of magnitude below Kafka for high-throughput streaming. SQS permanently deletes "
            "messages once consumed, so replay of already-processed messages is impossible — "
            "if your consumers need to reprocess historical events, use Kafka. Also avoid SQS "
            "for complex routing logic (fanout to multiple consumers per message) where "
            "SNS plus SQS fan-out or Kafka is a better fit."
        ),
        throughput_ceiling=(
            "Standard: nearly unlimited TPS; "
            "FIFO: 300 TPS without batching, 3,000 with (AWS SQS quotas)"
        ),
        key_tradeoff=(
            "Standard SQS delivers at-least-once, which means your consumers must be "
            "idempotent or deduplicate explicitly — duplicate delivery is not a bug, it "
            "is the contract. The FIFO variant solves ordering and deduplication but caps "
            "throughput at 3,000 TPS; this is a hard ceiling you will hit fast in "
            "high-volume scenarios. Message retention is 1-14 days and there is no replay "
            "after consumption, making SQS unsuitable as an event log."
        ),
        citation="https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/quotas.html",
    ),
    TechEntry(
        name="RabbitMQ",
        aliases=["rabbit mq", "amqp", "rabbitmq broker"],
        category=ComponentType.QUEUE,
        hosted=False,
        when_to_pick=(
            "Choose RabbitMQ when your messaging topology is complex and you need "
            "fine-grained routing logic that a simple queue cannot express. AMQP exchanges "
            "let you route messages by topic pattern, broadcast to all queues (fanout), "
            "or direct-route to a specific consumer — making RabbitMQ well-suited for "
            "workflows that combine pub-sub and point-to-point messaging. It also supports "
            "per-message acknowledgements and negative acknowledgements, giving you precise "
            "control over when a message is considered successfully processed. If your team "
            "is already familiar with AMQP and needs flexible routing without building "
            "that logic into application code, RabbitMQ is a strong choice."
        ),
        when_not_to_pick=(
            "Do not use RabbitMQ for high-throughput event streaming at Kafka scale — "
            "it tops out at roughly 50,000-100,000 messages per second per node and does "
            "not have Kafka's ability to handle millions of messages with durable retention. "
            "RabbitMQ messages are deleted on acknowledgement, so replay of consumed messages "
            "is not possible — do not use it when consumers need to reprocess historical events. "
            "Clustering RabbitMQ for high availability requires careful configuration and "
            "is operationally more complex than using a managed service like SQS or Pub/Sub."
        ),
        throughput_ceiling=(
            "50,000-100,000 messages/sec per node depending on message size and "
            "persistence settings (RabbitMQ performance guide)"
        ),
        key_tradeoff=(
            "RabbitMQ's exchange model is its superpower and its complexity — the more "
            "routing rules you add, the harder the topology is to reason about and debug. "
            "Messages are ephemeral by default: once acknowledged, they are gone, which "
            "makes RabbitMQ unsuitable as an event store. High availability clustering "
            "uses quorum queues but requires nodes to agree on message writes, adding "
            "latency compared to a single-node setup."
        ),
        citation="https://www.rabbitmq.com/docs/performance",
    ),
    TechEntry(
        name="Celery",
        aliases=["celery redis", "celery+redis", "celery broker", "celery worker"],
        category=ComponentType.QUEUE,
        hosted=False,
        when_to_pick=(
            "Choose Celery when you have a Python application that needs background task "
            "execution, periodic scheduled jobs (cron-style via Celery Beat), or delayed "
            "task processing with result tracking. It integrates naturally with Django and "
            "FastAPI and abstracts the broker (Redis or RabbitMQ) behind a clean Python API. "
            "Celery is the right tool when your team thinks in functions rather than events — "
            "you define a Python function, decorate it with @task, and call it asynchronously "
            "without caring about the underlying queue protocol. The result backend lets you "
            "poll or await task results, which is useful for long-running computations."
        ),
        when_not_to_pick=(
            "Do not use Celery in a non-Python stack — it is Python-only and has no "
            "equivalent client in other languages. It is the wrong abstraction for "
            "high-throughput event streaming where you care about event ordering, retention, "
            "or replay — use Kafka for that. Celery's Beat scheduler is a single point of "
            "failure; if it crashes, periodic tasks stop until it is restarted. Also avoid "
            "Celery when your background jobs need strict ordering guarantees — Celery does "
            "not guarantee task execution order across workers."
        ),
        throughput_ceiling=(
            "Depends on broker; Redis-backed Celery typically handles "
            "thousands of tasks/sec per worker pool"
        ),
        key_tradeoff=(
            "Celery is a task queue, not an event log — tasks are consumed and forgotten, "
            "with no replay capability. The broker (Redis or RabbitMQ) is a hard external "
            "dependency, and if it goes down, task submission fails. The Beat scheduler "
            "running as a single process is a single point of failure for all periodic jobs. "
            "Serialization format (JSON vs pickle) is a footgun: pickle enables arbitrary "
            "code execution if tasks come from untrusted sources."
        ),
        citation="https://docs.celeryq.dev/en/stable/getting-started/introduction.html",
    ),

    # ---------------------------------------------------------------------------
    # CACHE (3)
    # ---------------------------------------------------------------------------

    TechEntry(
        name="Redis",
        aliases=["redis cache", "elasticache redis", "redis cluster", "redis sentinel",
                 "read-heavy cache", "read heavy cache strategy", "cache strategy",
                 "in-memory cache"],
        category=ComponentType.CACHE,
        hosted=False,
        when_to_pick=(
            "Choose Redis when you need sub-millisecond latency on data that fits in RAM "
            "and you want more than a simple key-value store. Redis is the industry default "
            "for session storage, distributed rate limiting windows, leaderboards via sorted "
            "sets, real-time pub-sub for lightweight event fan-out, and distributed locks. "
            "Its rich data structures — lists, sets, sorted sets, hashes, streams, and "
            "geospatial indexes — let you implement complex features entirely in the cache "
            "layer without touching the database. When your bottleneck is read latency and "
            "your working set fits in a few dozen gigabytes, Redis is almost always the "
            "fastest path to solving it."
        ),
        when_not_to_pick=(
            "Do not use Redis when your dataset outgrows available RAM — Redis is an "
            "in-memory store first and storing multi-terabyte datasets in it is prohibitively "
            "expensive. It is not a primary database for large unbounded datasets; use "
            "PostgreSQL, Cassandra, or an object store for that. Do not use Redis as the "
            "sole source of truth for critical data without understanding its persistence "
            "model: AOF and RDB snapshots both have gaps where a crash loses the most recent "
            "writes. Also avoid Redis for pub-sub when delivery guarantees matter — its "
            "pub-sub is fire-and-forget; offline subscribers miss messages permanently."
        ),
        throughput_ceiling=(
            "~100,000 ops/sec single instance; "
            "1,000,000+ pipelined (Redis official benchmarks)"
        ),
        key_tradeoff=(
            "All data lives in RAM, which makes Redis cost-efficient only up to a few "
            "hundred gigabytes before the memory bill becomes significant. Cluster mode "
            "solves the memory limit but breaks multi-key operations — MGET across hash "
            "slots requires scatter-gather, and Lua scripts that touch multiple keys fail "
            "unless all keys hash to the same slot. Persistence via AOF adds disk I/O on "
            "every write; without it, a crash loses all data since the last RDB snapshot."
        ),
        citation="https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/benchmarks/",
    ),
    TechEntry(
        name="Memcached",
        aliases=["memcache"],
        category=ComponentType.CACHE,
        hosted=False,
        when_to_pick=(
            "Choose Memcached when you need a pure, high-performance key-value cache "
            "with no persistence requirements and your access pattern is simple string "
            "or byte storage. Memcached is multi-threaded and scales better with CPU cores "
            "than single-threaded Redis for pure caching workloads, making it faster at "
            "very high request rates on multi-core machines. It is the right choice when "
            "your team wants the simplest possible caching layer with no operational "
            "complexity, no data structures beyond strings, and horizontal scaling by "
            "adding nodes. If your use case is pure object caching — database query results, "
            "rendered HTML fragments, API responses — and you do not need any of Redis's "
            "advanced features, Memcached is leaner and simpler."
        ),
        when_not_to_pick=(
            "Do not use Memcached for persistent storage — it has no persistence mechanism "
            "and evicts all data from memory on restart; everything is volatile. Avoid it "
            "when you need complex data types (lists, sets, sorted sets, hashes), replication, "
            "pub-sub, or any feature beyond simple get/set/delete. Memcached also lacks "
            "built-in replication, so you cannot build a primary-replica setup for "
            "high availability the way you can with Redis Sentinel. If you need to store "
            "session state that must survive a cache restart, use Redis with persistence "
            "enabled instead."
        ),
        throughput_ceiling=(
            "100,000-200,000 ops/sec per node; multi-threaded so scales better "
            "with CPU cores than single-threaded Redis on the same hardware"
        ),
        key_tradeoff=(
            "Memcached is intentionally simple — it does one thing (key-value caching) "
            "extremely well and nothing else. That simplicity is a feature for pure caching "
            "but a hard limitation when requirements grow: there is no built-in replication, "
            "no persistence, no pub-sub, and no data structures beyond strings and bytes. "
            "All data is volatile and evicted on restart or when memory fills up using "
            "LRU eviction — there is no way to mark a key as persistent."
        ),
        citation="https://memcached.org/about",
    ),
    TechEntry(
        name="DynamoDB DAX",
        aliases=["dax", "dynamodb accelerator", "aws dax"],
        category=ComponentType.CACHE,
        hosted=True,
        when_to_pick=(
            "Choose DAX when your application is already built on DynamoDB and you need "
            "microsecond read latency without changing application code. DAX is a fully "
            "managed, DynamoDB-API-compatible in-memory cache that intercepts read requests "
            "transparently — you point your DynamoDB client at the DAX cluster endpoint "
            "instead and reads automatically go to cache first. It is the right choice "
            "when your DynamoDB tables have hot read keys that repeatedly fetch the same "
            "items and the single-digit millisecond DynamoDB latency is not fast enough. "
            "For read-heavy workloads where you want cache-aside behavior without writing "
            "any caching logic, DAX is the zero-effort answer."
        ),
        when_not_to_pick=(
            "Do not use DAX for non-DynamoDB databases — it is only compatible with "
            "DynamoDB's API and has no value outside that ecosystem. Avoid DAX for "
            "write-heavy workloads because it does not cache writes; all writes still "
            "go directly to DynamoDB and the cache is populated only on reads. DAX "
            "only serves eventually consistent reads — strongly consistent read requests "
            "bypass the cache and go directly to DynamoDB, so if your application relies "
            "heavily on strong consistency, DAX provides little benefit and adds cost. "
            "Also avoid DAX when cost is a concern, as DAX nodes are priced per node-hour "
            "regardless of utilization."
        ),
        throughput_ceiling=(
            "Microsecond read latency at millions of requests/sec; "
            "fully managed, scales automatically (AWS DAX documentation)"
        ),
        key_tradeoff=(
            "DAX is narrowly scoped: it only works with DynamoDB, only helps eventually "
            "consistent reads, and adds cost per node-hour. The cache is populated lazily "
            "on cache misses, meaning a cold start after a node replacement will briefly "
            "increase DynamoDB read traffic. Strongly consistent reads bypass DAX entirely, "
            "so applications that need read-your-own-write consistency see no benefit."
        ),
        citation="https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DAX.html",
    ),

    # ---------------------------------------------------------------------------
    # RELATIONAL_DB (5)
    # ---------------------------------------------------------------------------

    TechEntry(
        name="PostgreSQL",
        aliases=["postgres", "postgresql", "psql", "aurora postgres"],
        category=ComponentType.RELATIONAL_DB,
        hosted=False,
        when_to_pick=(
            "Choose PostgreSQL when you need ACID transactions, complex SQL queries with "
            "joins and window functions, or a rich type system including JSONB, arrays, "
            "and custom types. Postgres is the default choice for most web applications — "
            "it handles structured data with strong consistency guarantees, supports "
            "powerful extensions like PostGIS for geospatial data and pgvector for "
            "similarity search, and has excellent tooling and a large community. It is "
            "the right database when your data has relationships, your queries are complex, "
            "and you want the full power of SQL with strict schema enforcement. Single-region "
            "strong consistency is its core strength."
        ),
        when_not_to_pick=(
            "Do not use a single PostgreSQL instance when you need horizontal write scale "
            "beyond what one machine can handle — Postgres scales vertically by default, "
            "and horizontal write sharding requires external tooling like Citus or manual "
            "application-level sharding. Its default max_connections is 100, which means "
            "a fleet of application servers will exhaust connections fast — add PgBouncer "
            "in transaction mode before you hit that wall. Multi-region strong consistency "
            "is also not Postgres's strength; for that, look at CockroachDB. Also avoid "
            "single Postgres for datasets that require horizontal sharding by volume "
            "at the 5M+ DAU scale."
        ),
        throughput_ceiling=(
            "~1,000 writes/sec on a single mid-tier instance; "
            "plan an architecture change above 500 writes/sec sustained"
        ),
        key_tradeoff=(
            "PostgreSQL scales vertically and is a single point of failure without "
            "replication configured. Adding read replicas helps read throughput but "
            "introduces replication lag — reads from replicas may be milliseconds to "
            "seconds behind the primary. The connection limit (default 100) is the first "
            "wall when you scale the application tier; PgBouncer is almost always required "
            "in production. Write throughput is bounded by the single primary instance; "
            "sharding requires significant engineering effort."
        ),
        citation="https://dev.to/haikasatryan/postgresql-write-performance-what-the-benchmarks-wont-tell-you-mm7",
    ),
    TechEntry(
        name="MySQL",
        aliases=["mysql", "aurora mysql", "mariadb"],
        category=ComponentType.RELATIONAL_DB,
        hosted=False,
        when_to_pick=(
            "Choose MySQL when you have a read-heavy workload with a relatively simple "
            "schema and need broad hosting support across managed services (RDS, Cloud SQL, "
            "PlanetScale). MySQL is the default database for PHP-based stacks (WordPress, "
            "Laravel) and many e-commerce platforms, with decades of battle-tested "
            "replication patterns and a large community. It handles standard CRUD workloads "
            "well, replication-based high availability is straightforward to set up, and "
            "InnoDB row-level locking helps concurrent write performance on simple schemas. "
            "If your application is a typical web backend with more reads than writes and "
            "no complex query requirements, MySQL is a solid and widely understood choice."
        ),
        when_not_to_pick=(
            "Do not use MySQL when you need horizontal write scale — MySQL scales vertically "
            "by default and horizontal sharding requires Vitess or PlanetScale on top of it, "
            "which adds significant operational complexity. Avoid MySQL for complex analytical "
            "queries, advanced JSON manipulation, or full-text search — PostgreSQL's query "
            "planner and type system are significantly more powerful for those use cases. "
            "MySQL's replication is asynchronous by default, meaning replicas can lag and "
            "reads from replicas may return stale data. Also avoid MySQL when you need "
            "foreign key constraints in a horizontally sharded setup, as Vitess does not "
            "support them."
        ),
        throughput_ceiling=(
            "Similar to PostgreSQL: ~1,000 writes/sec single instance; "
            "InnoDB row-level locking helps concurrent writes (MySQL InnoDB benchmarks)"
        ),
        key_tradeoff=(
            "MySQL scales vertically by default; horizontal write scale requires Vitess "
            "sharding, which drops support for foreign key constraints and cross-shard "
            "joins. Async replication means replica reads are eventually consistent — "
            "reading your own writes from a replica is not guaranteed. The type system is "
            "simpler than PostgreSQL, which matters when queries grow in complexity. "
            "MySQL's strict mode behavior changed across versions, so schema migrations "
            "require careful testing."
        ),
        citation="https://dev.mysql.com/doc/refman/8.0/en/innodb-benchmarks.html",
    ),
    TechEntry(
        name="CockroachDB",
        aliases=["cockroach", "cockroachdb", "crdb"],
        category=ComponentType.RELATIONAL_DB,
        hosted=True,
        when_to_pick=(
            "Choose CockroachDB when you need globally distributed SQL with strong "
            "consistency across multiple regions and the ability to survive a full region "
            "failure without data loss. It uses the Raft consensus protocol to replicate "
            "data synchronously across nodes and is PostgreSQL wire-protocol compatible, "
            "meaning most PostgreSQL clients work without modification. CockroachDB is "
            "the right choice for applications that must be available in multiple "
            "geographic regions with consistent reads and writes — financial systems, "
            "global SaaS platforms, and anything where a region going down must not cause "
            "a downtime or stale-read window."
        ),
        when_not_to_pick=(
            "Do not use CockroachDB for single-region applications where you just need "
            "a fast relational database — the cross-region Raft consensus adds 50-300ms "
            "of latency to every write that would otherwise be a sub-millisecond local "
            "disk write in Postgres. This latency overhead makes CockroachDB a poor fit "
            "for high-frequency transactional systems in a single data center. Also avoid "
            "it for cost-sensitive workloads — running a CockroachDB cluster is significantly "
            "more expensive than a single Postgres instance for the same throughput. Simple "
            "applications that will never need global distribution are over-engineered by "
            "CockroachDB."
        ),
        throughput_ceiling=(
            "Scales horizontally; single-region throughput similar to PostgreSQL; "
            "cross-region: every write pays the round-trip to the farthest region "
            "(CockroachDB TPC-C benchmarks)"
        ),
        key_tradeoff=(
            "Cross-region Raft consensus means every write in a global cluster pays the "
            "network round-trip latency to the majority of replicas before it is "
            "acknowledged — in a 3-region deployment, that is the round-trip to the "
            "second-closest region. CockroachDB is optimized for global correctness, not "
            "local speed. Running it for single-region workloads is paying the full "
            "operational cost of a distributed system for no benefit."
        ),
        citation="https://www.cockroachlabs.com/docs/stable/performance-benchmarking-with-tpcc-large",
    ),
    TechEntry(
        name="PlanetScale",
        aliases=["planetscale", "planet scale", "vitess", "global distributed database",
                 "globally distributed sql"],
        category=ComponentType.RELATIONAL_DB,
        hosted=True,
        when_to_pick=(
            "Choose PlanetScale when you need MySQL-compatible horizontal write scale "
            "with a developer-friendly schema workflow and you are comfortable giving up "
            "foreign key constraints. PlanetScale is built on Vitess, the same technology "
            "that powers YouTube's database infrastructure, and handles horizontal sharding "
            "transparently behind a MySQL-compatible API. Its schema branching model — "
            "treating schema changes like git branches with deploy requests — makes "
            "zero-downtime migrations much safer than raw ALTER TABLE. It is a good fit "
            "for startups that expect write scale beyond what a single Postgres can handle "
            "but do not want to operate Vitess themselves."
        ),
        when_not_to_pick=(
            "Do not use PlanetScale when your schema relies on foreign key constraints — "
            "Vitess does not support them in sharded mode and enforcing referential integrity "
            "becomes entirely the application's responsibility. Avoid it for complex "
            "cross-shard joins, which become expensive scatter-gather operations. PlanetScale "
            "is also not a good fit for non-MySQL applications or when you need full SQL "
            "feature parity with PostgreSQL (window functions, CTEs, advanced types). "
            "Vendor lock-in to PlanetScale's managed platform is a real consideration "
            "if you later need to migrate to self-hosted infrastructure."
        ),
        throughput_ceiling=(
            "Horizontal write scale via Vitess sharding; "
            "single shard is MySQL-equivalent (~1,000 writes/sec)"
        ),
        key_tradeoff=(
            "PlanetScale trades foreign key constraints and full SQL flexibility for "
            "horizontal write scale. Schema changes go through a branching workflow — "
            "you cannot run raw ALTER TABLE in production, which is safer but adds process "
            "overhead. Vitess's query routing adds a thin latency overhead to every query. "
            "Moving off PlanetScale back to bare MySQL or Postgres requires migrating "
            "the Vitess-specific sharding configuration."
        ),
        citation="https://planetscale.com/docs/concepts/vitess-backups",
    ),
    TechEntry(
        name="Cassandra",
        aliases=["apache cassandra", "cassandra db", "datastax cassandra", "astra db"],
        category=ComponentType.RELATIONAL_DB,
        hosted=False,
        when_to_pick=(
            "Choose Cassandra when you need linear horizontal write scale, high write "
            "throughput, and multi-region active-active replication without a single "
            "master. Cassandra excels at time-series data, IoT event ingestion, activity "
            "logs, and any workload where writes vastly outnumber reads and data access "
            "patterns are well-defined and query-driven rather than ad-hoc. It is "
            "leaderless — any node can accept any write — which means there is no write "
            "bottleneck and adding nodes increases throughput linearly. At petabyte scale "
            "across a cluster, Cassandra is one of the few databases that can keep up."
        ),
        when_not_to_pick=(
            "Do not choose Cassandra when you need strong consistency — Cassandra is a "
            "leaderless system with eventual consistency by default. Tunable consistency "
            "(QUORUM reads and writes) exists but it adds latency by requiring a majority "
            "of replicas to respond, and it is still not the same as single-master ACID "
            "transactions. Avoid Cassandra entirely for use cases requiring complex queries, "
            "joins, secondary indexes at scale, or ad-hoc analytical queries — its data "
            "model forces you to design tables around specific query patterns at schema "
            "time, and deviating from that is painful. It is also wrong for small datasets "
            "where a single Postgres instance is simpler and faster."
        ),
        throughput_ceiling=(
            "Linear write scale; single node ~10,000-20,000 writes/sec; "
            "petabyte-scale across a cluster (Apache Cassandra architecture docs)"
        ),
        key_tradeoff=(
            "Cassandra's leaderless eventual consistency is its core design — not a bug "
            "and not configurable away without paying a latency cost. QUORUM consistency "
            "requires a majority of replicas to acknowledge every read and write, which "
            "adds cross-node round-trip latency to every operation and reduces the "
            "availability benefit of the leaderless model. Schema design is query-first: "
            "you must know your access patterns at schema design time because Cassandra "
            "has no efficient way to do arbitrary queries. Changing data models after the "
            "fact requires table rewrites."
        ),
        citation="https://cassandra.apache.org/doc/stable/cassandra/architecture/dynamo.html",
    ),

    # ---------------------------------------------------------------------------
    # OBJECT_STORE (3)
    # ---------------------------------------------------------------------------

    TechEntry(
        name="S3",
        aliases=["aws s3", "amazon s3", "simple storage service"],
        category=ComponentType.OBJECT_STORE,
        hosted=True,
        when_to_pick=(
            "Choose S3 when you need durable, cheap, scalable object storage for blobs, "
            "backups, static assets, ML training datasets, or a data lake. S3 is the "
            "industry standard for object storage — 11 nines of durability, virtually "
            "unlimited capacity, and native integration with every AWS service. It is "
            "the right choice for storing any file that does not need sub-millisecond "
            "access latency: images, videos, database backups, log archives, model "
            "checkpoints, and static website assets. S3 also works as the foundation "
            "for a data lake, with Athena, Redshift Spectrum, and EMR all reading directly "
            "from it."
        ),
        when_not_to_pick=(
            "Do not use S3 for frequent small writes to the same key prefix — per-prefix "
            "throughput is bounded at 3,500 PUT/sec and 5,500 GET/sec, and hot prefixes "
            "will throttle. Avoid S3 for low-latency random access to small objects — "
            "S3 GET latency is typically 10-100ms, which is fine for batch workflows but "
            "wrong for user-facing hot paths that need sub-millisecond cache. Also avoid "
            "S3 for relational queries on stored data — use a database or Athena with "
            "Parquet for that. S3 is an object store, not a file system; POSIX semantics "
            "(atomic rename, directory listing) are approximated, not guaranteed."
        ),
        throughput_ceiling=(
            "~3,500 PUT/sec and ~5,500 GET/sec per prefix; "
            "spread keys across prefixes to multiply throughput linearly (AWS S3 docs)"
        ),
        key_tradeoff=(
            "Per-prefix throughput limits cause throttling when writes concentrate on a "
            "single prefix — for example, objects named by date (2024/01/01/...) create "
            "hot prefixes when all writes happen on the same day. The fix is randomizing "
            "key prefixes with a hash prefix, which sacrifices key readability. S3 is "
            "eventually consistent for list operations on newly uploaded objects; list-after-write "
            "may not show newly added keys in very high-throughput scenarios."
        ),
        citation="https://docs.aws.amazon.com/AmazonS3/latest/userguide/optimizing-performance.html",
    ),
    TechEntry(
        name="GCS",
        aliases=["google cloud storage", "gcs", "google storage"],
        category=ComponentType.OBJECT_STORE,
        hosted=True,
        when_to_pick=(
            "Choose GCS when your workload lives in the Google Cloud ecosystem and you "
            "want native integration with BigQuery, Dataflow, Vertex AI, and Cloud "
            "Functions. GCS is strongly consistent by default — unlike the older S3 "
            "eventual consistency model, a GCS object is immediately visible after a "
            "successful PUT, which simplifies correctness reasoning for pipelines. It "
            "supports multi-regional storage classes for global low-latency access and "
            "integrates with Google's transfer service for moving data from other clouds. "
            "If your ML pipelines run on GCP and you want tight integration with BigQuery "
            "external tables or Vertex AI datasets, GCS is the native choice."
        ),
        when_not_to_pick=(
            "Do not use GCS when your infrastructure is primarily AWS-based — the "
            "integration advantage disappears and you will pay cross-cloud egress fees. "
            "GCS egress pricing to the internet is comparable to S3 but varies by region, "
            "and moving data between GCS and AWS (for example, to feed an AWS-based ML "
            "training cluster) adds latency and cost. For pure storage without GCP "
            "ecosystem integration, GCS offers no meaningful advantage over S3."
        ),
        throughput_ceiling=(
            "Similar to S3; per-bucket rate limits apply at very high throughput; "
            "use multiple buckets or key prefix diversity (GCS request rate docs)"
        ),
        key_tradeoff=(
            "GCS is strongly consistent by default, which is an advantage over older S3 "
            "behavior but is now matched by S3's strong read-after-write consistency "
            "update. The main GCS advantage is tight GCP integration — if you are not "
            "using GCP services, that advantage is zero. Egress costs to the internet "
            "and to other clouds are the main cost gotcha for data-heavy workloads."
        ),
        citation="https://cloud.google.com/storage/docs/request-rate",
    ),
    TechEntry(
        name="Azure Blob",
        aliases=["azure blob storage", "azure blob", "wasb", "adls gen2"],
        category=ComponentType.OBJECT_STORE,
        hosted=True,
        when_to_pick=(
            "Choose Azure Blob Storage when your workload runs in the Azure ecosystem "
            "and you want native integration with Azure Data Factory, Synapse Analytics, "
            "Azure Machine Learning, and Azure Functions. Azure Data Lake Storage Gen2 "
            "(built on top of Blob Storage) adds a hierarchical namespace, making it "
            "suitable for big data analytics workloads. Tiered storage (hot, cool, and "
            "archive) lets you automatically move infrequently accessed data to cheaper "
            "tiers, which is useful for compliance archives and cold backup retention "
            "with strict cost controls."
        ),
        when_not_to_pick=(
            "Do not use Azure Blob Storage when your stack is primarily AWS or GCP — "
            "you will pay cross-cloud egress fees and lose the ecosystem integration "
            "advantage. Archive tier retrieval is slow (it can take hours) and is only "
            "appropriate for data you access extremely infrequently. Azure's tooling and "
            "SDK ecosystem is smaller than S3's, so third-party integrations are less "
            "common and may require Azure-specific configuration."
        ),
        throughput_ceiling=(
            "Up to 20,000 requests/sec per storage account; "
            "60 Gbps ingress/egress (Azure Blob scalability targets)"
        ),
        key_tradeoff=(
            "Hot/cool/archive tiers reduce cost for cold data but archive tier retrieval "
            "takes hours — the cost saving only makes sense if you truly never need the "
            "data quickly. Moving data between tiers incurs a transition cost. Azure's "
            "ecosystem integration is the core value proposition; without it, S3 or GCS "
            "typically have better third-party tooling support."
        ),
        citation="https://learn.microsoft.com/en-us/azure/storage/blobs/scalability-targets",
    ),

    # ---------------------------------------------------------------------------
    # CDN (3)
    # ---------------------------------------------------------------------------

    TechEntry(
        name="Cloudflare",
        aliases=["cloudflare cdn", "cloudflare workers", "cf", "cloudflare pages",
                 "static asset cdn", "static file delivery", "aws cdn"],
        category=ComponentType.CDN,
        hosted=True,
        when_to_pick=(
            "Choose Cloudflare when you need a global CDN with DDoS protection, DNS "
            "management, and edge compute in a single platform. Cloudflare's 300+ Points "
            "of Presence make it one of the most geographically distributed CDN networks "
            "available, ensuring low latency for users worldwide. It has a generous free "
            "tier that makes it accessible for any project size, and Cloudflare Workers "
            "let you run JavaScript at the edge for A/B testing, authentication, or "
            "request transformation without a backend round-trip. If you want a one-stop "
            "shop for DNS, CDN, and DDoS mitigation with minimal configuration, Cloudflare "
            "is the default answer."
        ),
        when_not_to_pick=(
            "Do not use Cloudflare when your origin is deeply integrated with AWS IAM "
            "signed requests or Lambda@Edge behavior that assumes CloudFront's specific "
            "integration model. Cloudflare Workers use a different programming model "
            "from Lambda@Edge, so existing Lambda@Edge code does not migrate directly. "
            "For complex caching logic tied to AWS service responses, CloudFront's native "
            "AWS integration is simpler. Also consider vendor lock-in if you build "
            "heavily on Cloudflare Workers, Pages, and R2 — moving off becomes difficult."
        ),
        throughput_ceiling=(
            "Global edge; handles terabit-scale DDoS; "
            "300+ PoPs worldwide (Cloudflare network page)"
        ),
        key_tradeoff=(
            "A CDN is a read cache — writes bypass it and hit the origin directly, so "
            "a CDN does nothing for write-heavy workloads. Cloudflare Workers add edge "
            "compute but have a 10ms CPU time limit per request, which constrains "
            "what logic is feasible at the edge. The free tier's rate limiting and "
            "WAF features are basic; enterprise features (advanced WAF rules, Bot "
            "Management) require paid tiers."
        ),
        citation="https://www.cloudflare.com/network/",
    ),
    TechEntry(
        name="CloudFront",
        aliases=["aws cloudfront", "cloudfront", "static asset cdn", "static file delivery", "aws cdn"],
        category=ComponentType.CDN,
        hosted=True,
        when_to_pick=(
            "Choose CloudFront when your origin is AWS-native — S3 buckets, ALBs, API "
            "Gateway, or MediaStore — and you want tight IAM-based access control, "
            "signed URLs for private content, and Lambda@Edge for request manipulation. "
            "CloudFront integrates natively with AWS Shield for DDoS protection and "
            "AWS WAF for web application firewall rules, giving you a security stack "
            "that is configured and billed through a single AWS console. It is also "
            "the right choice for streaming video from AWS MediaStore or delivering "
            "large files from S3 at scale. For teams already operating in AWS who want "
            "to minimize the number of vendors, CloudFront is the natural CDN choice."
        ),
        when_not_to_pick=(
            "Do not use CloudFront when your origin is outside AWS — you can configure "
            "a custom origin, but you lose the tight IAM integration and private origin "
            "access features. CloudFront is more expensive than Cloudflare for similar "
            "traffic volumes, especially at the free or low-traffic tier where Cloudflare "
            "offers a generous free plan and CloudFront charges per request and data "
            "transfer. Lambda@Edge is more powerful than Cloudflare Workers for AWS "
            "ecosystem tasks but has higher cold start latency and more restrictive "
            "deployment constraints."
        ),
        throughput_ceiling=(
            "Global edge; 600+ PoPs; no published throughput cap; "
            "auto-scales with demand (AWS CloudFront docs)"
        ),
        key_tradeoff=(
            "CloudFront's value is maximized when origin is AWS. Outside that context, "
            "pricing per request and data transfer adds up faster than Cloudflare's flat "
            "pricing. Lambda@Edge functions have cold starts and must be deployed to "
            "us-east-1 and replicated globally, adding deployment complexity. Cache "
            "invalidations cost money ($0.005 per path after the first 1,000 per month)."
        ),
        citation="https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Introduction.html",
    ),
    TechEntry(
        name="Fastly",
        aliases=["fastly cdn"],
        category=ComponentType.CDN,
        hosted=True,
        when_to_pick=(
            "Choose Fastly when cache invalidation speed is a hard requirement — Fastly "
            "can purge cached content globally in under 150 milliseconds, which is "
            "orders of magnitude faster than most CDNs that take minutes to propagate "
            "purges. This makes Fastly the right choice for news sites, e-commerce "
            "platforms with rapidly changing inventory, and any application where stale "
            "cache content has real business consequences. Fastly's VCL (Varnish "
            "Configuration Language) gives you extremely fine-grained control over "
            "caching behavior, request routing, and edge logic. Major publishers like "
            "The New York Times, GitHub, and Twitter use Fastly specifically for this "
            "real-time purge capability."
        ),
        when_not_to_pick=(
            "Do not use Fastly if you just need simple static asset delivery — Cloudflare's "
            "free tier handles that more cost-effectively. Fastly is premium-priced and "
            "the cost is only justified when instant purge or deep VCL customization is "
            "a genuine requirement. VCL is a powerful but unusual language that requires "
            "training; small teams without Fastly expertise will find the learning curve "
            "steep. For teams that need edge compute with a standard JavaScript model, "
            "Cloudflare Workers or Lambda@Edge are more accessible."
        ),
        throughput_ceiling=(
            "Global edge; used by GitHub, Twitter, NY Times at scale; "
            "no published throughput cap (Fastly product page)"
        ),
        key_tradeoff=(
            "Fastly's instant purge capability is genuinely differentiated — no other "
            "CDN does sub-150ms global purge at Fastly's scale. The tradeoff is premium "
            "pricing and VCL complexity: VCL gives you power that no other CDN offers, "
            "but it is a specialized language that is not transferable to other platforms. "
            "If you invest heavily in VCL logic, migrating away from Fastly becomes a "
            "significant engineering effort."
        ),
        citation="https://www.fastly.com/products/cdn",
    ),

    # ---------------------------------------------------------------------------
    # LOAD_BALANCER (3)
    # ---------------------------------------------------------------------------

    TechEntry(
        name="ALB",
        aliases=["aws alb", "application load balancer", "aws load balancer",
                 "elastic load balancer"],
        category=ComponentType.LOAD_BALANCER,
        hosted=True,
        when_to_pick=(
            "Choose ALB when your infrastructure is on AWS and you need HTTP/2-aware, "
            "content-based routing that integrates directly with EC2, ECS, EKS, and "
            "Lambda targets. ALB supports path-based routing (send /api/* to one target "
            "group, /static/* to another), host-based routing (different domains to "
            "different backends), and WebSocket connections out of the box. It integrates "
            "with AWS Certificate Manager for free SSL/TLS, auto-scales its own capacity "
            "with traffic, and requires zero infrastructure to operate. For any HTTP/HTTPS "
            "load balancing in AWS without a desire to manage load balancer software, "
            "ALB is the default choice."
        ),
        when_not_to_pick=(
            "Do not use ALB for TCP or UDP load balancing — ALB is an L7 (HTTP) load "
            "balancer and does not understand raw TCP. Use NLB (Network Load Balancer) "
            "for that instead. Avoid ALB for non-AWS environments; it is AWS-specific "
            "and has no equivalent outside the platform. ALB pricing is per LCU (load "
            "balancer capacity unit), which can surprise teams during traffic spikes — "
            "a sudden burst can cause an unexpected cost jump. For gRPC load balancing "
            "with granular control over retry policies, consider a service mesh or nginx "
            "with custom configuration."
        ),
        throughput_ceiling=(
            "Scales automatically; supports millions of requests/sec; "
            "AWS manages capacity with no pre-warming needed (AWS ALB docs)"
        ),
        key_tradeoff=(
            "ALB cost scales with traffic via LCUs, which is great for variable workloads "
            "but can be expensive during sustained high-traffic events. It is L7-only — "
            "there is no way to forward raw TCP, so if you need both HTTP and TCP "
            "load balancing, you need both ALB and NLB. Deep customization of request "
            "handling (complex retry logic, custom health check behavior) requires "
            "Lambda functions or moving to nginx/Envoy."
        ),
        citation="https://docs.aws.amazon.com/elasticloadbalancing/latest/application/introduction.html",
    ),
    TechEntry(
        name="nginx",
        aliases=["nginx lb", "nginx reverse proxy", "openresty", "nginx plus"],
        category=ComponentType.LOAD_BALANCER,
        hosted=False,
        when_to_pick=(
            "Choose nginx when you need a self-hosted, highly configurable reverse proxy "
            "that combines load balancing, SSL termination, static file serving, and "
            "request routing in a single lightweight process. nginx is the right choice "
            "when you want fine-grained control over upstream selection, buffering, "
            "timeouts, and request transformation through its declarative configuration "
            "language. OpenResty (nginx + LuaJIT) extends this with programmable request "
            "handling at the edge without a separate application server. nginx is also "
            "the standard sidecar proxy in many Kubernetes deployments for ingress "
            "traffic management."
        ),
        when_not_to_pick=(
            "Do not choose nginx when you want managed auto-scaling — nginx requires "
            "manual capacity planning and HA setup (typically keepalived or a cloud "
            "load balancer in front). It proxies HTTP/2 from clients but by default "
            "connects to upstreams via HTTP/1.1, which is a gotcha for gRPC backends "
            "that need H2 end-to-end. Configuration complexity grows quickly with "
            "routing rules; a complex nginx config becomes hard to maintain and test. "
            "For AWS deployments, ALB does everything nginx does for L7 load balancing "
            "with less operational overhead."
        ),
        throughput_ceiling=(
            "Tens of thousands of concurrent connections per instance; "
            "~100,000 req/sec for simple reverse proxying (nginx documentation)"
        ),
        key_tradeoff=(
            "nginx is powerful but configuration-heavy — the declarative config language "
            "is not always intuitive and errors only surface at reload time. HA requires "
            "an active-passive setup with keepalived or an external floating IP, which "
            "adds operational complexity not needed with managed load balancers. nginx "
            "terminates HTTP/2 from clients but proxies to upstreams in HTTP/1.1 by "
            "default; enabling H2 upstreams requires explicit configuration."
        ),
        citation="https://nginx.org/en/docs/",
    ),
    TechEntry(
        name="HAProxy",
        aliases=["ha proxy", "haproxy"],
        category=ComponentType.LOAD_BALANCER,
        hosted=False,
        when_to_pick=(
            "Choose HAProxy when you need battle-tested, extremely high-performance "
            "L4/L7 load balancing with detailed health checking, a built-in statistics "
            "dashboard, and fine-grained ACL-based routing. HAProxy is the gold standard "
            "for TCP load balancing — it handles database connection pooling, raw TCP "
            "proxy for non-HTTP protocols, and SSL passthrough with minimal overhead. "
            "Its multi-process model means it can saturate multiple CPU cores for "
            "pure load balancing workloads. HAProxy is commonly used in front of "
            "database clusters for connection distribution and in financial systems "
            "where low-latency TCP routing is critical."
        ),
        when_not_to_pick=(
            "Do not use HAProxy as your primary file server or reverse proxy for static "
            "content — use nginx for that. HAProxy does not serve static files and is "
            "not designed as a general-purpose web server. Avoid HAProxy for gRPC "
            "workloads where HTTP/2 server push and bidirectional streaming matter — "
            "its H2 support is present but less mature than Envoy or nginx Plus. For "
            "teams that want managed infrastructure, a cloud load balancer (ALB or "
            "GCP Load Balancer) eliminates the need to operate HAProxy."
        ),
        throughput_ceiling=(
            "300,000-500,000 req/sec at L7; higher at L4; "
            "multi-process model, one process per core (HAProxy intro doc)"
        ),
        key_tradeoff=(
            "HAProxy's ACL-based configuration is verbose and can become very complex "
            "for advanced routing rules, but it offers precise control unavailable in "
            "simpler load balancers. Like nginx, it requires manual HA configuration "
            "(keepalived or VRRP) for active-passive failover. HAProxy focuses purely "
            "on load balancing and health checking — it does not serve static files, "
            "handle SSL origination well at scale, or provide edge compute."
        ),
        citation="https://www.haproxy.org/download/1.8/doc/intro.txt",
    ),

    # ---------------------------------------------------------------------------
    # APP_SERVER (3)
    # ---------------------------------------------------------------------------

    TechEntry(
        name="FastAPI",
        aliases=["fast api", "fastapi python", "starlette", "uvicorn"],
        category=ComponentType.APP_SERVER,
        hosted=False,
        when_to_pick=(
            "Choose FastAPI when you are building a Python-based HTTP API and want "
            "automatic OpenAPI documentation, request validation via Pydantic, and "
            "async I/O support with minimal boilerplate. FastAPI is the right choice "
            "for data science and ML teams because it integrates naturally with NumPy, "
            "Pandas, and ML inference code already written in Python. It is also a "
            "strong choice for rapid prototyping — the auto-generated Swagger UI means "
            "your API is documented and testable from day one. For I/O-bound services "
            "like proxies, API aggregators, and webhook handlers, the async model "
            "handles high concurrency efficiently per worker process."
        ),
        when_not_to_pick=(
            "Do not use FastAPI for CPU-intensive workloads where Python's GIL is a "
            "bottleneck — heavy computation blocks the event loop and degrades all "
            "concurrent requests. Avoid FastAPI if you need a very high request rate "
            "from a single instance; the Python overhead per request is significantly "
            "higher than Go, Java, or Node.js. Also avoid it when your team is not "
            "primarily Python — the type annotation + Pydantic model pattern is "
            "Pythonic and unfamiliar to teams from other ecosystems. For CPU-bound "
            "ML inference at high throughput, consider a dedicated inference server "
            "like Triton or TorchServe."
        ),
        throughput_ceiling=(
            "~2,000-8,000 req/sec per worker depending on async vs sync handlers "
            "and I/O-bound work (FastAPI benchmarks)"
        ),
        key_tradeoff=(
            "Python's GIL means CPU-bound work blocks all other requests in the same "
            "process — CPU-heavy handlers must be offloaded to a thread pool or a "
            "separate process. Scaling FastAPI means running more Uvicorn worker "
            "processes (not threads), which multiplies memory usage. The Pydantic "
            "validation overhead on every request is measurable at very high RPS, "
            "though it is usually worth it for the correctness guarantee."
        ),
        citation="https://fastapi.tiangolo.com/benchmarks/",
    ),
    TechEntry(
        name="Express",
        aliases=["express.js", "expressjs", "node express", "node.js", "nodejs"],
        category=ComponentType.APP_SERVER,
        hosted=False,
        when_to_pick=(
            "Choose Express when you are building a Node.js API and want a minimal, "
            "unopinionated framework that gives you full control over middleware "
            "composition. Express is the right choice for real-time applications "
            "using WebSockets (Socket.io integrates naturally), JavaScript full-stack "
            "teams who want to share types and code between frontend and backend, "
            "and services that are primarily I/O-bound (database calls, external API "
            "proxying) where Node's non-blocking event loop excels. Its npm ecosystem "
            "is the largest in software, meaning nearly any integration already has "
            "a maintained package."
        ),
        when_not_to_pick=(
            "Do not use Express for CPU-intensive workloads — any synchronous CPU "
            "work blocks Node's single-threaded event loop and degrades all concurrent "
            "requests until the CPU work completes. This makes Express a poor choice "
            "for image processing, cryptographic operations, or heavy JSON transformation "
            "in the request path. Avoid Express when type safety is critical across "
            "a large codebase; plain JavaScript's dynamic typing leads to runtime "
            "errors that TypeScript with Fastify catches at compile time. For Java "
            "or Python teams, the JavaScript ecosystem and async programming model "
            "adds a significant learning curve."
        ),
        throughput_ceiling=(
            "~10,000-30,000 req/sec for simple JSON APIs; "
            "Node.js event loop handles high I/O concurrency at low CPU cost "
            "(Node.js event loop guide)"
        ),
        key_tradeoff=(
            "Node.js is single-threaded — one CPU-bound operation starves all other "
            "concurrent requests. The cluster module or PM2 adds multiple processes "
            "but not threads, multiplying memory usage. Express itself is middleware "
            "composition; an improperly ordered middleware stack is a common source "
            "of bugs where auth runs after the route handler or error handlers do "
            "not catch async errors."
        ),
        citation="https://nodejs.org/en/docs/guides/dont-block-the-event-loop",
    ),
    TechEntry(
        name="Spring Boot",
        aliases=["spring", "spring framework", "spring mvc", "java spring",
                 "spring webflux"],
        category=ComponentType.APP_SERVER,
        hosted=False,
        when_to_pick=(
            "Choose Spring Boot when you are building a Java or Kotlin service for an "
            "enterprise environment where the ecosystem matters — Spring Security, "
            "Spring Data, Spring Cloud (service discovery, circuit breakers, config "
            "server) form a complete microservices platform. Spring Boot is the right "
            "choice for large teams that need strong typing, mature observability "
            "(Micrometer, Actuator), and production-grade dependency injection at "
            "scale. The JVM's JIT compilation delivers excellent throughput after "
            "warmup, making it suitable for long-lived services with stable traffic "
            "patterns. For financial services, insurance, and large enterprise "
            "systems where Java is the standard, Spring Boot is the dominant framework."
        ),
        when_not_to_pick=(
            "Do not use Spring Boot for rapid prototyping or small teams — the "
            "framework's convention-over-configuration auto-wiring is powerful but "
            "hides a lot of complexity that becomes hard to debug for engineers not "
            "deeply familiar with Spring's internal lifecycle. JVM startup time (2-10 "
            "seconds) and memory footprint (200+ MB per instance) make it a poor fit "
            "for serverless cold-start scenarios or Lambda functions. Avoid Spring Boot "
            "when your team is not Java or Kotlin engineers — the framework's idioms "
            "do not translate well to other ecosystems."
        ),
        throughput_ceiling=(
            "~5,000-15,000 req/sec per instance; "
            "JVM JIT compilation means performance improves after warmup "
            "(Spring Boot documentation)"
        ),
        key_tradeoff=(
            "Spring Boot's auto-configuration is convenient but opaque — when something "
            "goes wrong, the bean lifecycle and auto-configuration order are hard to "
            "reason about without deep Spring knowledge. JVM startup time of 2-10 "
            "seconds is a real issue for ephemeral or autoscaling deployments where "
            "new instances must serve traffic quickly. The per-instance memory footprint "
            "is significantly higher than Go or Node.js, increasing compute cost at "
            "the same request volume."
        ),
        citation="https://spring.io/projects/spring-boot",
    ),
]
