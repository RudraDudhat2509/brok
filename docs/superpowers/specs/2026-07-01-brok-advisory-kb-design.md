# Brok Advisory KB Design

> **Date:** 2026-07-01
> **Status:** Approved, ready for implementation planning

---

## Goal

Add a `query_tradeoffs` MCP tool to Brok that lets Claude Code ask technology and architecture questions mid-decision and receive grounded, cited answers — before committing to a choice. The existing review engine is untouched. This is a pure additive layer.

## Problem

Brok's review tools (`review_architecture`, `review_components`) fire after a design exists. Claude Code often makes the wrong technology or pattern choice before Brok sees the design. By then the choice is embedded in code.

The gap: Claude Code confidently recommends Cassandra for strong consistency, Redis for multi-TB datasets, CQRS everywhere, and Pub/Sub when Kafka is required — because its training data contains these patterns without the operational costs. Brok's KB has the correct grounding. The advisory tool makes it available pre-decision.

---

## Architecture

Three new files, zero changes to the existing review engine:

```
brok/
  kb_tech.py        — 25 technology entries across 7 categories, cited
  kb_strategies.py  — 15 operational strategy entries (sharding, eviction, replication, etc.)
  kb_patterns.py    — 10 architectural pattern entries (CQRS, Saga, Circuit Breaker, etc.)
  query.py          — embedding-based retrieval across all three KBs, comparison block
  server.py         — one new tool added: query_tradeoffs (existing tools untouched)
skill/SKILL.md      — updated: also trigger query_tradeoffs on technology choice questions
scripts/
  bench_query.py    — golden retrieval set + hallucination guard set benchmark
tests/
  test_kb_tech.py       — static validation: all entries present, all fields populated, all cited
  test_kb_strategies.py — same
  test_kb_patterns.py   — same
  test_query.py         — retrieval accuracy on known queries
  test_query_guard.py   — hallucination guard: KB must contradict 10 known wrong claims
  test_server_query.py  — integration: query_tradeoffs tool returns correct shape
```

Data flow:

```
Claude Code: "kafka vs pubsub for spiky writes"
        |
        v
query_tradeoffs(question)        <- new MCP tool in server.py
        |
        v
query.py: embed question with all-MiniLM-L6-v2 (22MB, local, cached)
          cosine similarity over all ~50 embedded KB entries
          top-3 matches above threshold 0.25
        |
        v
if 2+ results from same category:
  deterministic comparison block (template, no LLM)
        |
        v
{matches: [...], comparison: "KAFKA vs PUB/SUB\n  ...", note: "Brok surfaces trade-offs. You decide."}
```

The model never touches the judgment. It gets cited entries and a structured comparison. It decides.

---

## KB Entry Types

### TechEntry — 25 entries, 7 categories

```python
@dataclass
class TechEntry:
    name: str                  # "Kafka"
    aliases: list[str]         # ["apache kafka", "confluent kafka"]
    category: ComponentType    # ComponentType.QUEUE
    hosted: bool               # True = managed cloud service
    when_to_pick: str          # key signal to choose this
    when_not_to_pick: str      # key signal to avoid it — includes known wrong uses
    throughput_ceiling: str    # rough numbers with source
    key_tradeoff: str          # the one thing you must know
    source: str                # cited URL or named reference
```

| Category | Technologies |
|---|---|
| QUEUE | Kafka, Google Pub/Sub, AWS SQS, RabbitMQ, Celery+Redis |
| CACHE | Redis, Memcached, DynamoDB DAX |
| RELATIONAL_DB | PostgreSQL, MySQL, CockroachDB, PlanetScale |
| OBJECT_STORE | AWS S3, Google Cloud Storage, Azure Blob |
| CDN | Cloudflare, AWS CloudFront, Fastly |
| LOAD_BALANCER | AWS ALB, nginx, HAProxy |
| APP_SERVER | FastAPI, Express.js, Spring Boot |

`when_not_to_pick` is the critical field. It must explicitly state known wrong uses:
- Kafka: "not when you need managed zero-ops or push delivery"
- Redis: "not for datasets larger than available RAM; not for durable primary storage"
- Cassandra: "not when you need strong consistency or complex queries"
- Pub/Sub: "not when you need strict per-key ordering or replay at scale"

### StrategyEntry — 15 entries

```python
@dataclass
class StrategyEntry:
    name: str                  # "consistent hashing"
    aliases: list[str]         # ["ketama", "ring hashing"]
    applies_to: list[str]      # ["cache", "relational_db", "queue"]
    when_to_use: str
    when_not_to_use: str
    key_tradeoff: str
    source: str
```

| Domain | Strategies |
|---|---|
| Sharding | consistent hashing, range-based sharding, hash-based sharding, directory-based sharding |
| Cache eviction | LRU, LFU, TTL, write-through, write-back, write-around |
| Queue delivery | at-least-once, exactly-once, at-most-once |
| DB replication | synchronous replication, asynchronous replication, read replicas |
| Partitioning | Kafka partition key selection, hot partition avoidance |

### PatternEntry — 10 entries

```python
@dataclass
class PatternEntry:
    name: str                  # "CQRS"
    aliases: list[str]         # ["command query responsibility segregation"]
    when_to_use: str           # "read and write load differ significantly in shape or volume"
    when_not_to_use: str       # "simple CRUD, small team, early product — adds complexity for no gain"
    operational_cost: str      # "dual model sync, eventual consistency on reads, two codepaths"
    common_mistake: str        # "applying it by default; most apps don't need it"
    source: str
```

Patterns: CQRS, Event Sourcing, Saga, Outbox Pattern, Circuit Breaker, Bulkhead, Strangler Fig, API Gateway, Sidecar, Rate Limiter (token bucket vs sliding window).

`common_mistake` is mandatory. This is the hallucination-prevention field — it directly contradicts the confident-but-wrong pattern the model learned.

---

## Query Engine

**Model:** `sentence-transformers/all-MiniLM-L6-v2` — 22MB, local, no API key, ~50ms first embed.

**Embedding strategy:**
- Each KB entry is embedded as: `f"{entry.name}. {entry.when_to_pick or entry.when_to_use}. {entry.key_tradeoff or entry.operational_cost}"`
- Embeddings computed at first `query_tradeoffs` call, cached in module-level dict for process lifetime
- Re-embedding on every query would be ~50ms × 50 entries = 2.5s — unacceptable

**Retrieval:**
- Embed the question
- Cosine similarity against all cached entry embeddings
- Return top-3 above threshold `0.25` (below threshold = no match, return empty)
- Threshold prevents noise on unrelated queries

**Comparison block** (deterministic, no LLM):
```
# only fires for TechEntry matches — comparing strategies or patterns is not meaningful
tech_matches = [m for m in top_matches if m.type == "tech"]
if len({m.category for m in tech_matches}) < len(tech_matches):
    # 2+ TechEntries from same category → generate comparison
    KAFKA vs PUB/SUB
      pick Kafka when: [when_to_pick]
      pick Pub/Sub when: [when_to_pick]
      both: [shared key_tradeoff if overlap]
      sources: [source], [source]
```

---

## MCP Tool

```python
@mcp.tool()
def query_tradeoffs(question: str) -> dict:
    """Call this BEFORE choosing between technologies or architectural patterns.
    Works for: datastores, queues, caches, CDNs, load balancers, sharding strategies,
    cache eviction policies, delivery guarantees, and architectural patterns (CQRS, Saga, etc.).

    Examples:
      "kafka vs pubsub for spiky writes"
      "should I use consistent hashing or range sharding"
      "when does CQRS make sense"
      "redis or memcached for session data"
      "how to avoid hot partitions in Kafka"
      "is Cassandra good for strong consistency"  <- guard case, returns: no

    Returns matched entries with cited trade-offs, a head-to-head comparison when two
    technologies from the same category match, and a note that Brok surfaces the trade-offs
    but you decide.
    """
```

Return shape — all fields normalized regardless of entry type:
```python
{
    "matches": [
        {
            "name": str,
            "type": "tech" | "strategy" | "pattern",
            "category": str,           # ComponentType value for tech; applies_to[0] for strategy; "pattern" for pattern
            "when_to_pick": str,       # normalized: TechEntry.when_to_pick, StrategyEntry.when_to_use, PatternEntry.when_to_use
            "when_not_to_pick": str,   # normalized: TechEntry.when_not_to_pick, StrategyEntry.when_not_to_use, PatternEntry.when_not_to_use
            "key_tradeoff": str,       # normalized: TechEntry.key_tradeoff, StrategyEntry.key_tradeoff, PatternEntry.operational_cost
            "extra": str,              # TechEntry: throughput_ceiling; PatternEntry: common_mistake; StrategyEntry: ""
            "source": str,
        },
        ...
    ],
    "comparison": str | None,   # only generated when 2+ TechEntry matches share the same category; None otherwise
    "note": "Brok surfaces trade-offs. You decide.",
}
```

Normalization happens in `query.py` before returning. Consumers always see the same keys regardless of entry type. The `extra` field carries the guard-critical content for PatternEntry (`common_mistake`) and throughput numbers for TechEntry.

---

## SKILL.md Update

Add to the "When to call Brok" section:

> **Also call `query_tradeoffs` before choosing between specific technologies or patterns:**
> choosing a queue (Kafka, Pub/Sub, SQS, RabbitMQ), a cache (Redis, Memcached), a database (Postgres, CockroachDB, Cassandra), an object store, a CDN, or a load balancer implementation. Call it before applying an architectural pattern (CQRS, Saga, Event Sourcing, Circuit Breaker). Pass the question in natural language — "kafka vs pubsub for spiky writes", "should I use CQRS here", "how to shard this postgres".

---

## Benchmark

Two sets, both must pass before shipping.

### Golden retrieval set — 30 queries, target ≥85% recall@3

Each query has an expected set of entry names. Recall@3 = fraction of expected entries appearing in the top-3 results.

```python
GOLDEN = [
    # tech comparisons
    ("kafka vs pubsub",                  ["Kafka", "Pub/Sub"]),
    ("kafka vs sqs",                     ["Kafka", "SQS"]),
    ("redis vs memcached session",       ["Redis", "Memcached"]),
    ("postgres vs cockroachdb global",   ["PostgreSQL", "CockroachDB"]),
    ("s3 vs gcs object storage",         ["S3", "GCS"]),
    ("cloudflare vs cloudfront cdn",     ["Cloudflare", "CloudFront"]),
    ("nginx vs alb load balancer",       ["nginx", "ALB"]),
    ("rabbitmq vs kafka ordering",       ["RabbitMQ", "Kafka"]),
    # strategy queries
    ("how to shard postgres",            ["consistent hashing", "hash-based sharding"]),
    ("cache eviction session data",      ["LRU", "TTL"]),
    ("write through vs write back",      ["write-through", "write-back"]),
    ("hot partition kafka",              ["Kafka partition key", "hot partition avoidance"]),
    ("at least once exactly once",       ["at-least-once", "exactly-once"]),
    ("read replicas async replication",  ["read replicas", "asynchronous replication"]),
    ("range vs hash sharding",           ["range-based sharding", "hash-based sharding"]),
    # pattern queries
    ("when to use cqrs",                 ["CQRS"]),
    ("distributed transaction saga",     ["Saga", "Outbox Pattern"]),
    ("circuit breaker pattern",          ["Circuit Breaker"]),
    ("event sourcing vs crud",           ["Event Sourcing"]),
    ("strangler fig migration",          ["Strangler Fig"]),
    ("rate limiting token bucket",       ["Rate Limiter"]),
    ("bulkhead pattern isolation",       ["Bulkhead"]),
    # cross-cutting
    ("spiky writes queue",               ["Kafka", "SQS"]),
    ("read heavy cache strategy",        ["Redis", "write-through"]),
    ("global distributed database",     ["CockroachDB", "PlanetScale"]),
    ("static asset delivery cdn",       ["Cloudflare", "CloudFront"]),
    ("monolith to microservices",        ["Strangler Fig"]),
    ("decoupled services",               ["Circuit Breaker", "Bulkhead"]),
    ("blob storage large files",         ["S3", "GCS"]),
    ("push notification queue",          ["Pub/Sub", "SQS"]),
]
```

### Hallucination guard set — 10 queries, target 100% correct grounding

Each query is a known wrong claim. The returned `when_not_to_pick` or `common_mistake` field of the top match must contain a word from the `must_warn` list.

```python
GUARD = [
    ("cassandra strong consistency",
     "Cassandra", ["eventual", "tunable", "not strong", "leaderless"]),
    ("redis terabyte storage",
     "Redis", ["ram", "memory", "bounded", "in-memory"]),
    ("pubsub strict per key ordering",
     "Pub/Sub", ["no global ordering", "ordering", "partition"]),
    ("use cqrs for simple crud app",
     "CQRS", ["simple", "crud", "overhead", "overkill"]),
    ("2pc distributed transaction scale",
     "Saga", ["blocking", "avoid", "two-phase"]),
    ("mysql horizontal write scale",
     "MySQL", ["vertical", "shard", "write scale"]),
    ("memcached persistent storage",
     "Memcached", ["volatile", "no persistence", "evicts"]),
    ("event sourcing simple app",
     "Event Sourcing", ["complex", "overhead", "simple"]),
    ("kafka push delivery managed",
     "Kafka", ["pull", "self-hosted", "ops"]),
    ("cockroachdb single region low latency",
     "CockroachDB", ["cross-region", "latency", "global"]),
]
```

`scripts/bench_query.py` runs both sets and prints a scorecard. Build does not ship until both pass.

---

## Global Constraints

- `sentence-transformers` added to `[dev]` dependencies in `pyproject.toml`
- Embeddings cached in memory, never written to disk
- Every KB entry must have a non-empty `source` field — no unsourced claims
- `when_not_to_pick` and `common_mistake` fields are mandatory and must be explicit, not vague
- All existing 120 tests must continue to pass
- No changes to `review_architecture`, `review_components`, or any existing pipeline code
- Brok stays fully local — `all-MiniLM-L6-v2` runs offline after first download
- No em dashes in any user-facing text

---

## Success Criteria

1. Golden retrieval: ≥85% recall@3 across all 30 queries
2. Hallucination guard: 100% correct grounding on all 10 guard queries
3. All 120 existing tests pass
4. `query_tradeoffs("completely unknown xyz")` returns `{"matches": [], "comparison": None, "note": "..."}`
5. Second call to `query_tradeoffs` does not re-embed the KB (cache hit)
6. `query_tradeoffs("cassandra strong consistency")` returns Cassandra entry with `when_not_to_pick` explicitly warning against strong consistency
