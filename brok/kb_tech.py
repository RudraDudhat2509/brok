"""Technology knowledge base — 25 entries across 7 categories.

Every entry has a `citation` field pointing to an official source for its
throughput numbers and trade-off claims. Nothing is invented here: if a claim
cannot be traced to a citation it does not belong in this file.
"""
from __future__ import annotations

from dataclasses import dataclass

from brok.models import ComponentType


@dataclass(frozen=True)
class TechEntry:
    name: str
    aliases: list[str]
    category: ComponentType
    hosted: bool                # True = managed cloud service, False = self-hosted
    when_to_pick: str
    when_not_to_pick: str
    throughput_ceiling: str     # conservative real-world number, sourced
    key_tradeoff: str           # the one thing you must know before choosing this
    citation: str               # URL that backs the throughput number or claim above


# ---------------------------------------------------------------------------
# QUEUE (5)
# ---------------------------------------------------------------------------

TECH_KB: list[TechEntry] = [
    TechEntry(
        name="Kafka",
        aliases=["apache kafka", "confluent kafka", "kafka broker", "kafka cluster"],
        category=ComponentType.QUEUE,
        hosted=False,
        when_to_pick=(
            "high-throughput event streaming, replay required, ordered per partition, "
            "millions of messages per second, fan-out to many independent consumers"
        ),
        when_not_to_pick=(
            "managed zero-ops preferred, push delivery needed, simple task queue; "
            "Kafka is self-hosted and pull-based — consumers poll and track their own offsets"
        ),
        throughput_ceiling=(
            "millions of messages/sec per cluster; single partition ~100 MB/s "
            "(Confluent performance benchmarks)"
        ),
        key_tradeoff=(
            "pull-based — consumers must track offsets; partition count is the unit of "
            "parallelism and is fixed at topic creation; ordering only within a partition"
        ),
        citation="https://developer.confluent.io/learn/kafka-performance/",
    ),
    TechEntry(
        name="Pub/Sub",
        aliases=["google pub/sub", "google cloud pub/sub", "gcp pubsub", "cloud pubsub"],
        category=ComponentType.QUEUE,
        hosted=True,
        when_to_pick=(
            "managed push delivery, Google Cloud ecosystem, global fan-out to many "
            "subscribers, zero-ops queue at large scale"
        ),
        when_not_to_pick=(
            "strict per-key message ordering — Pub/Sub has no global ordering guarantee; "
            "replay at consumer scale; non-GCP stack"
        ),
        throughput_ceiling=(
            "millions of messages/sec globally; push delivery adds one HTTP round-trip "
            "per message to your endpoint"
        ),
        key_tradeoff=(
            "no global ordering guarantee; ordering within a single ordering key is "
            "preserved but across keys it is not — do not use when Kafka partition-level "
            "ordering is required"
        ),
        citation="https://cloud.google.com/pubsub/docs/overview",
    ),
    TechEntry(
        name="SQS",
        aliases=["amazon sqs", "aws sqs", "simple queue service"],
        category=ComponentType.QUEUE,
        hosted=True,
        when_to_pick=(
            "simple managed decoupling on AWS, at-least-once delivery, visibility timeout "
            "pattern, dead-letter queue, spiky or burst traffic"
        ),
        when_not_to_pick=(
            "strict ordering without the FIFO variant; Kafka-scale throughput; "
            "replay of already-consumed messages (SQS deletes on ack)"
        ),
        throughput_ceiling=(
            "standard: nearly unlimited TPS; "
            "FIFO: 300 TPS without batching, 3,000 with (AWS quotas docs)"
        ),
        key_tradeoff=(
            "standard queue delivers at-least-once and may deliver out of order; "
            "FIFO guarantees strict ordering but caps at 3,000 TPS — pick the right variant"
        ),
        citation="https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/quotas.html",
    ),
    TechEntry(
        name="RabbitMQ",
        aliases=["rabbit mq", "amqp", "rabbitmq broker"],
        category=ComponentType.QUEUE,
        hosted=False,
        when_to_pick=(
            "complex routing (topic, fanout, direct exchanges), AMQP protocol, "
            "per-message acknowledgements, flexible pub-sub and point-to-point topologies"
        ),
        when_not_to_pick=(
            "very high throughput (Kafka-scale), message replay after ack, "
            "long-term event storage"
        ),
        throughput_ceiling=(
            "50,000-100,000 messages/sec per node depending on message size and "
            "persistence settings (RabbitMQ performance guide)"
        ),
        key_tradeoff=(
            "messages are deleted on ack — no built-in replay; "
            "exchange routing is powerful but adds configuration complexity; "
            "clustering requires careful setup for HA"
        ),
        citation="https://www.rabbitmq.com/docs/performance",
    ),
    TechEntry(
        name="Celery",
        aliases=["celery redis", "celery+redis", "celery broker", "celery worker"],
        category=ComponentType.QUEUE,
        hosted=False,
        when_to_pick=(
            "Python task queue, periodic tasks via beat scheduler, "
            "delayed execution, result storage needed, background jobs in Django/FastAPI"
        ),
        when_not_to_pick=(
            "non-Python stack, high-throughput event streaming, "
            "strict ordering guarantees, message replay"
        ),
        throughput_ceiling=(
            "depends on broker; Redis-backed Celery typically handles "
            "thousands of tasks/sec per worker pool"
        ),
        key_tradeoff=(
            "Python-only; broker (Redis or RabbitMQ) is a hard dependency; "
            "tasks are functions not events — wrong abstraction for streaming; "
            "beat scheduler is a single point of failure"
        ),
        citation="https://docs.celeryq.dev/en/stable/getting-started/introduction.html",
    ),

    # ---------------------------------------------------------------------------
    # CACHE (3)
    # ---------------------------------------------------------------------------

    TechEntry(
        name="Redis",
        aliases=["redis cache", "elasticache redis", "redis cluster", "redis sentinel"],
        category=ComponentType.CACHE,
        hosted=False,
        when_to_pick=(
            "session storage, leaderboards, pub-sub, rate limiting, "
            "complex data structures (sorted sets, streams), sub-millisecond latency"
        ),
        when_not_to_pick=(
            "dataset larger than available RAM — Redis is an in-memory store; "
            "not for multi-terabyte datasets or durable primary storage"
        ),
        throughput_ceiling=(
            "~100,000 ops/sec single instance; "
            "1,000,000+ pipelined (Redis official benchmarks)"
        ),
        key_tradeoff=(
            "all data lives in RAM; persistence (AOF/RDB) adds disk I/O overhead; "
            "cluster mode complicates multi-key operations and Lua scripts"
        ),
        citation="https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/benchmarks/",
    ),
    TechEntry(
        name="Memcached",
        aliases=["memcache"],
        category=ComponentType.CACHE,
        hosted=False,
        when_to_pick=(
            "pure key-value cache, multi-threaded high throughput, "
            "horizontal slab scaling, simple string/byte caching"
        ),
        when_not_to_pick=(
            "persistent storage — Memcached has no persistence and evicts all data on "
            "restart; not for complex data types, pub-sub, data structures, or replication"
        ),
        throughput_ceiling=(
            "100,000-200,000 ops/sec per node; "
            "multi-threaded so scales better with CPU cores than single-threaded Redis"
        ),
        key_tradeoff=(
            "no persistence — all data is volatile and lost on restart or eviction; "
            "no replication built-in; simpler and faster for pure cache with no durability needs"
        ),
        citation="https://memcached.org/about",
    ),
    TechEntry(
        name="DynamoDB DAX",
        aliases=["dax", "dynamodb accelerator", "aws dax"],
        category=ComponentType.CACHE,
        hosted=True,
        when_to_pick=(
            "DynamoDB read acceleration, microsecond read latency, "
            "drop-in API-compatible cache — same DynamoDB API, no code changes"
        ),
        when_not_to_pick=(
            "non-DynamoDB tables; write-heavy workloads (DAX does not accelerate writes); "
            "strongly consistent reads (DAX only serves eventually consistent reads)"
        ),
        throughput_ceiling=(
            "microsecond read latency at millions of requests/sec; "
            "fully managed, scales automatically (AWS DAX docs)"
        ),
        key_tradeoff=(
            "vendor-locked to DynamoDB; adds cost per node-hour; "
            "strongly consistent reads bypass DAX and hit DynamoDB directly — "
            "DAX only helps eventual-consistency reads"
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
            "ACID transactions, complex queries, JSONB, extensions (PostGIS, pgvector), "
            "strong single-region consistency, rich type system"
        ),
        when_not_to_pick=(
            "horizontal write scale beyond one machine; multi-region strong consistency; "
            "default max_connections is 100 — add PgBouncer before scaling app instances"
        ),
        throughput_ceiling=(
            "~1,000 writes/sec on a single mid-tier instance; "
            "plan an architecture change above 500 writes/sec sustained"
        ),
        key_tradeoff=(
            "scales vertically; horizontal scaling needs read replicas (replication lag) "
            "or sharding (complexity); connection limit (default 100) is the first wall "
            "when adding app servers"
        ),
        citation="https://dev.to/haikasatryan/postgresql-write-performance-what-the-benchmarks-wont-tell-you-mm7",
    ),
    TechEntry(
        name="MySQL",
        aliases=["mysql", "aurora mysql", "mariadb"],
        category=ComponentType.RELATIONAL_DB,
        hosted=False,
        when_to_pick=(
            "read-heavy workloads, simple schemas, wide hosting support, "
            "replication-based HA, e-commerce, WordPress-style applications"
        ),
        when_not_to_pick=(
            "horizontal write scale — MySQL scales vertically by default; "
            "sharding requires Vitess or PlanetScale; advanced JSON or complex analytical queries"
        ),
        throughput_ceiling=(
            "similar to PostgreSQL: ~1,000 writes/sec single instance; "
            "InnoDB row-level locking helps concurrent writes (MySQL InnoDB benchmarks)"
        ),
        key_tradeoff=(
            "replication is async by default — replicas may lag; "
            "horizontal write scale needs Vitess sharding; "
            "simpler to operate than Postgres for basic use cases"
        ),
        citation="https://dev.mysql.com/doc/refman/8.0/en/innodb-benchmarks.html",
    ),
    TechEntry(
        name="CockroachDB",
        aliases=["cockroach", "cockroachdb", "crdb"],
        category=ComponentType.RELATIONAL_DB,
        hosted=True,
        when_to_pick=(
            "global distributed SQL, survive region failures, "
            "strong consistency across regions, PostgreSQL-compatible wire protocol"
        ),
        when_not_to_pick=(
            "single-region low-latency — cross-region consensus (Raft) adds 100ms+ "
            "per write; simple workloads where single-region Postgres suffices; cost-sensitive"
        ),
        throughput_ceiling=(
            "scales horizontally; single-region throughput similar to PostgreSQL; "
            "cross-region: every write pays the round-trip latency to the farthest region "
            "(CockroachDB TPC-C benchmarks)"
        ),
        key_tradeoff=(
            "cross-region consensus means every write pays cross-region latency; "
            "optimized for global availability not single-region speed; "
            "more expensive to run than single-region Postgres"
        ),
        citation="https://www.cockroachlabs.com/docs/stable/performance-benchmarking-with-tpcc-large",
    ),
    TechEntry(
        name="PlanetScale",
        aliases=["planetscale", "planet scale", "vitess"],
        category=ComponentType.RELATIONAL_DB,
        hosted=True,
        when_to_pick=(
            "MySQL-compatible serverless scaling, schema branching workflow (like git for schemas), "
            "high write throughput via Vitess horizontal sharding"
        ),
        when_not_to_pick=(
            "foreign key constraints — PlanetScale's sharded mode does not support them; "
            "cross-shard joins are expensive; non-MySQL applications"
        ),
        throughput_ceiling=(
            "horizontal write scale via Vitess sharding; "
            "single shard is MySQL-equivalent (~1,000 writes/sec)"
        ),
        key_tradeoff=(
            "no foreign key constraints in production (Vitess limitation); "
            "schema changes go through a branching workflow, not plain ALTER TABLE; "
            "vendor lock-in to PlanetScale's managed platform"
        ),
        citation="https://planetscale.com/docs/concepts/vitess-backups",
    ),
    TechEntry(
        name="Cassandra",
        aliases=["apache cassandra", "cassandra db", "datastax cassandra", "astra db"],
        category=ComponentType.RELATIONAL_DB,
        hosted=False,
        when_to_pick=(
            "high write throughput, time-series data, wide-column model, "
            "multi-region active-active, linear horizontal write scale"
        ),
        when_not_to_pick=(
            "strong consistency requirements — Cassandra is leaderless with eventual "
            "consistency by default; tunable consistency exists but adds latency cost; "
            "not for complex queries, joins, transactions, or ad-hoc queries"
        ),
        throughput_ceiling=(
            "linear write scale; single node ~10,000-20,000 writes/sec; "
            "petabyte-scale across a cluster (Apache Cassandra architecture docs)"
        ),
        key_tradeoff=(
            "leaderless, eventual consistency by default; tunable consistency (QUORUM) "
            "increases latency; no joins, no transactions; "
            "query patterns must be designed around partition keys at schema time"
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
            "blobs, backups, static assets, data lake, ML training data; "
            "11-nines durability at low cost; de facto industry standard"
        ),
        when_not_to_pick=(
            "frequent small writes to the same key prefix — per-prefix throughput is "
            "bounded; low-latency random access; relational queries on stored data"
        ),
        throughput_ceiling=(
            "~3,500 PUT/sec and ~5,500 GET/sec per prefix; "
            "spread keys across prefixes to multiply throughput linearly (AWS S3 docs)"
        ),
        key_tradeoff=(
            "per-prefix throughput limit causes throttling with hot prefixes; "
            "use random or date-prefixed key names to distribute load; "
            "now strongly consistent after 2020 update (no more eventual-consistency gotcha)"
        ),
        citation="https://docs.aws.amazon.com/AmazonS3/latest/userguide/optimizing-performance.html",
    ),
    TechEntry(
        name="GCS",
        aliases=["google cloud storage", "gcs", "google storage"],
        category=ComponentType.OBJECT_STORE,
        hosted=True,
        when_to_pick=(
            "GCP ecosystem, BigQuery/Dataflow integration, strongly consistent reads, "
            "multi-regional storage for global access"
        ),
        when_not_to_pick=(
            "AWS-centric stack (use S3); cost-sensitive on egress (GCS egress pricing "
            "is comparable to S3 but varies by region)"
        ),
        throughput_ceiling=(
            "similar to S3; per-bucket rate limits apply at very high throughput; "
            "use multiple buckets or key prefix diversity (GCS request rate docs)"
        ),
        key_tradeoff=(
            "strongly consistent by default (unlike older S3); "
            "GCP-native tooling integrates better than S3 for BigQuery or Dataflow; "
            "outside GCP the integration advantage disappears"
        ),
        citation="https://cloud.google.com/storage/docs/request-rate",
    ),
    TechEntry(
        name="Azure Blob",
        aliases=["azure blob storage", "azure blob", "wasb", "adls gen2"],
        category=ComponentType.OBJECT_STORE,
        hosted=True,
        when_to_pick=(
            "Azure ecosystem, tiered storage (hot/cool/archive), "
            "Azure Data Lake Gen2 for analytics, Azure ML integration"
        ),
        when_not_to_pick=(
            "non-Azure stack; archive tier retrieval is slow (hours); "
            "hot-tier performance is comparable to S3 but tooling is Azure-specific"
        ),
        throughput_ceiling=(
            "up to 20,000 requests/sec per storage account; "
            "60 Gbps ingress/egress per account (Azure scalability targets)"
        ),
        key_tradeoff=(
            "hot/cool/archive tiers reduce cost for cold data but archive retrieval "
            "takes hours; Azure-native tooling ties you to the ecosystem"
        ),
        citation="https://learn.microsoft.com/en-us/azure/storage/blobs/scalability-targets",
    ),

    # ---------------------------------------------------------------------------
    # CDN (3)
    # ---------------------------------------------------------------------------

    TechEntry(
        name="Cloudflare",
        aliases=["cloudflare cdn", "cloudflare workers", "cf", "cloudflare pages"],
        category=ComponentType.CDN,
        hosted=True,
        when_to_pick=(
            "DDoS protection, global edge network (300+ PoPs), "
            "Cloudflare Workers for edge compute, free tier, DNS + CDN in one"
        ),
        when_not_to_pick=(
            "complex AWS-integrated origin behavior that needs tight AWS IAM; "
            "vendor lock-in concern with Workers"
        ),
        throughput_ceiling=(
            "global edge; handles terabit-scale DDoS; "
            "200+ PoPs worldwide (Cloudflare network page)"
        ),
        key_tradeoff=(
            "CDN is a read cache — writes bypass it and hit origin; "
            "Workers add edge compute but use a different programming model (V8 isolates); "
            "best value when DNS is also on Cloudflare"
        ),
        citation="https://www.cloudflare.com/network/",
    ),
    TechEntry(
        name="CloudFront",
        aliases=["aws cloudfront", "cloudfront"],
        category=ComponentType.CDN,
        hosted=True,
        when_to_pick=(
            "AWS origins (S3, ALB, API Gateway), Lambda@Edge for request manipulation, "
            "tight AWS IAM integration, signed URLs for private content"
        ),
        when_not_to_pick=(
            "non-AWS origins (works but loses tight integration); "
            "cost-sensitive at high traffic volumes compared to Cloudflare"
        ),
        throughput_ceiling=(
            "global edge; 600+ PoPs; no published throughput cap; "
            "auto-scales with demand (AWS CloudFront docs)"
        ),
        key_tradeoff=(
            "best value when origin is AWS; Lambda@Edge adds latency vs Cloudflare Workers; "
            "pricing per request and data transfer adds up at scale"
        ),
        citation="https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Introduction.html",
    ),
    TechEntry(
        name="Fastly",
        aliases=["fastly cdn"],
        category=ComponentType.CDN,
        hosted=True,
        when_to_pick=(
            "instant cache purge (<150ms globally), VCL customization, "
            "streaming media, real-time content updates where stale cache is unacceptable"
        ),
        when_not_to_pick=(
            "simple static delivery (Cloudflare free tier is sufficient); "
            "cost-sensitive (Fastly is premium-priced); small teams without VCL expertise"
        ),
        throughput_ceiling=(
            "global edge; used by GitHub, Twitter, NY Times at scale; "
            "no published cap (Fastly product page)"
        ),
        key_tradeoff=(
            "fastest cache purge in the industry (<150ms) but at premium cost; "
            "VCL (Varnish Configuration Language) is powerful but adds operational complexity"
        ),
        citation="https://www.fastly.com/products/cdn",
    ),

    # ---------------------------------------------------------------------------
    # LOAD_BALANCER (3)
    # ---------------------------------------------------------------------------

    TechEntry(
        name="ALB",
        aliases=["aws alb", "application load balancer", "aws load balancer", "elastic load balancer"],
        category=ComponentType.LOAD_BALANCER,
        hosted=True,
        when_to_pick=(
            "AWS infrastructure, HTTP/2, WebSockets, "
            "path-based and host-based routing, auto-scaling target groups"
        ),
        when_not_to_pick=(
            "TCP/UDP load balancing (use NLB instead); "
            "non-AWS environment; raw TCP performance where NLB latency matters"
        ),
        throughput_ceiling=(
            "scales automatically; supports millions of requests/sec; "
            "AWS manages capacity with no pre-warming needed (AWS ALB docs)"
        ),
        key_tradeoff=(
            "HTTP-only (L7); for raw TCP use NLB; "
            "cost is per LCU (load balancer capacity unit) so very spiky traffic can surprise on cost; "
            "tightly coupled to AWS ecosystem"
        ),
        citation="https://docs.aws.amazon.com/elasticloadbalancing/latest/application/introduction.html",
    ),
    TechEntry(
        name="nginx",
        aliases=["nginx lb", "nginx reverse proxy", "openresty", "nginx plus"],
        category=ComponentType.LOAD_BALANCER,
        hosted=False,
        when_to_pick=(
            "self-hosted, reverse proxy + static file serving + SSL termination in one process, "
            "flexible Lua-based config, high concurrency"
        ),
        when_not_to_pick=(
            "managed auto-scale preferred; "
            "H2 upstream proxying (nginx terminates HTTP/2 but proxies as HTTP/1.1 by default)"
        ),
        throughput_ceiling=(
            "tens of thousands of concurrent connections per instance; "
            "~100,000 req/sec for simple reverse proxying (nginx.org docs)"
        ),
        key_tradeoff=(
            "config complexity grows with routing rules; "
            "requires manual HA setup (keepalived or a cloud LB in front); "
            "Lua/OpenResty for dynamic behavior adds a second language to the stack"
        ),
        citation="https://nginx.org/en/docs/",
    ),
    TechEntry(
        name="HAProxy",
        aliases=["ha proxy", "haproxy"],
        category=ComponentType.LOAD_BALANCER,
        hosted=False,
        when_to_pick=(
            "high-performance L4/L7 load balancing, TCP load balancing, "
            "battle-tested HA patterns, detailed stats dashboard, health checking"
        ),
        when_not_to_pick=(
            "managed preferred; serving static files (use nginx for that); "
            "gRPC load balancing (limited H2 support)"
        ),
        throughput_ceiling=(
            "300,000-500,000 req/sec at L7; higher at L4; "
            "multi-process model, one process per core (HAProxy intro doc)"
        ),
        key_tradeoff=(
            "configuration is ACL-based and verbose; "
            "does one thing (load balancing) extremely well; "
            "no static file serving — pair with nginx or a CDN for assets"
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
            "Python async APIs, OpenAPI/Swagger auto-generation, Pydantic validation, "
            "data science or ML integration, rapid development"
        ),
        when_not_to_pick=(
            "CPU-intensive workloads — Python GIL limits parallelism; "
            "very high single-instance request volume (scale by adding instances, not threads)"
        ),
        throughput_ceiling=(
            "~2,000-8,000 req/sec per worker depending on async vs sync handlers "
            "and I/O bound work (FastAPI benchmarks)"
        ),
        key_tradeoff=(
            "Python GIL limits true CPU parallelism; async helps for I/O-bound work; "
            "scale by running more Uvicorn worker processes, not more threads"
        ),
        citation="https://fastapi.tiangolo.com/benchmarks/",
    ),
    TechEntry(
        name="Express",
        aliases=["express.js", "expressjs", "node express", "node.js", "nodejs"],
        category=ComponentType.APP_SERVER,
        hosted=False,
        when_to_pick=(
            "Node.js, non-blocking I/O, real-time apps (WebSockets), "
            "vast npm ecosystem, JavaScript full-stack"
        ),
        when_not_to_pick=(
            "CPU-intensive workloads — Node.js event loop blocks on CPU work; "
            "type safety critical (use TypeScript + Fastify instead)"
        ),
        throughput_ceiling=(
            "~10,000-30,000 req/sec for simple JSON APIs; "
            "Node.js event loop handles high I/O concurrency at low CPU cost "
            "(Node.js event loop guide)"
        ),
        key_tradeoff=(
            "single-threaded event loop — any synchronous CPU work blocks all requests; "
            "cluster mode adds processes but not threads; "
            "callback/promise model can be verbose"
        ),
        citation="https://nodejs.org/en/docs/guides/dont-block-the-event-loop",
    ),
    TechEntry(
        name="Spring Boot",
        aliases=["spring", "spring framework", "spring mvc", "java spring", "spring webflux"],
        category=ComponentType.APP_SERVER,
        hosted=False,
        when_to_pick=(
            "Java/Kotlin enterprise, mature ecosystem, Spring Cloud microservices, "
            "strong typing, large team, long-lived services"
        ),
        when_not_to_pick=(
            "rapid prototyping or small team — JVM startup time and memory footprint are high; "
            "startup latency makes it a poor fit for serverless cold starts"
        ),
        throughput_ceiling=(
            "~5,000-15,000 req/sec per instance; "
            "JVM JIT compilation means performance improves after warmup "
            "(Spring Boot docs)"
        ),
        key_tradeoff=(
            "heavy startup time and memory footprint; "
            "JVM JIT warmup period means first-minute performance is lower; "
            "Spring auto-configuration hides complexity and makes debugging harder"
        ),
        citation="https://spring.io/projects/spring-boot",
    ),
]
