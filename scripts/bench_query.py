"""Advisory KB benchmark — two gates that must both pass before shipping.

Gate 1: Golden retrieval set  — 30 queries, target >= 85% recall@3
Gate 2: Hallucination guard   — 10 queries, target 100% correct grounding

Recall@3 per query = (expected entries found in top-3) / (total expected entries).
Overall recall = mean across all queries.

Guard check: for each guard query, the named entry must appear in the top-3
AND its when_not_to_pick + extra fields must contain at least one must_warn word.

Run:
    python scripts/bench_query.py

Exit code 0 = both gates pass. Exit code 1 = one or more gates fail.
"""
from __future__ import annotations

import sys

from brok.query import search

# ---------------------------------------------------------------------------
# Golden retrieval set (30 queries)
# ---------------------------------------------------------------------------

GOLDEN: list[tuple[str, list[str]]] = [
    # tech head-to-head comparisons
    ("kafka vs pubsub",                 ["Kafka", "Pub/Sub"]),
    ("kafka vs sqs",                    ["Kafka", "SQS"]),
    ("redis vs memcached session",      ["Redis", "Memcached"]),
    ("postgres vs cockroachdb global",  ["PostgreSQL", "CockroachDB"]),
    ("s3 vs gcs object storage",        ["S3", "GCS"]),
    ("cloudflare vs cloudfront cdn",    ["Cloudflare", "CloudFront"]),
    ("nginx vs alb load balancer",      ["nginx", "ALB"]),
    ("rabbitmq vs kafka ordering",      ["RabbitMQ", "Kafka"]),
    # strategy queries
    ("how to shard postgres",           ["consistent hashing", "hash-based sharding"]),
    ("cache eviction session data",     ["LRU", "TTL"]),
    ("write through vs write back",     ["write-through", "write-back"]),
    ("hot partition kafka",             ["Kafka partition key", "hot partition avoidance"]),
    ("at least once exactly once",      ["at-least-once delivery", "exactly-once delivery"]),
    ("read replicas async replication", ["read replicas", "asynchronous replication"]),
    ("range vs hash sharding",          ["range-based sharding", "hash-based sharding"]),
    # pattern queries
    ("when to use cqrs",                ["CQRS"]),
    ("distributed transaction saga",    ["Saga", "Outbox Pattern"]),
    ("circuit breaker pattern",         ["Circuit Breaker"]),
    ("event sourcing vs crud",          ["Event Sourcing"]),
    ("strangler fig migration",         ["Strangler Fig"]),
    ("rate limiting token bucket",      ["Rate Limiter"]),
    ("bulkhead pattern isolation",      ["Bulkhead"]),
    # cross-cutting
    ("spiky writes queue",              ["Kafka", "SQS"]),
    ("read heavy cache strategy",       ["Redis", "write-through"]),
    ("global distributed database",     ["CockroachDB", "PlanetScale"]),
    ("static asset delivery cdn",       ["Cloudflare", "CloudFront"]),
    ("monolith to microservices",       ["Strangler Fig"]),
    ("decoupled services resilience",   ["Circuit Breaker", "Bulkhead"]),
    ("blob storage large files",        ["S3", "GCS"]),
    ("push notification queue managed", ["Pub/Sub", "SQS"]),
]

# ---------------------------------------------------------------------------
# Hallucination guard set (10 queries)
# Each tuple: (query, expected_entry_name, must_warn_words)
# The must_warn check covers when_not_to_pick + extra (common_mistake for patterns,
# throughput_ceiling for tech entries).
# ---------------------------------------------------------------------------

GUARD: list[tuple[str, str, list[str]]] = [
    ("cassandra strong consistency",
     "Cassandra",      ["eventual", "leaderless", "tunable"]),
    ("redis terabyte storage",
     "Redis",          ["ram", "memory", "in-memory"]),
    ("pubsub strict per key ordering",
     "Pub/Sub",        ["ordering", "no global ordering"]),
    ("use cqrs for simple crud app",
     "CQRS",           ["simple", "crud", "overhead"]),
    ("2pc distributed transaction scale",
     "Saga",           ["two-phase", "blocking"]),
    ("mysql horizontal write scale",
     "MySQL",          ["vertical", "shard", "horizontal"]),
    ("memcached persistent storage",
     "Memcached",      ["no persistence", "evicts", "volatile"]),
    ("event sourcing simple app",
     "Event Sourcing", ["simple", "overhead", "complex"]),
    ("kafka push delivery managed",
     "Kafka",          ["self-hosted", "pull", "ops"]),
    ("cockroachdb single region low latency",
     "CockroachDB",    ["cross-region", "latency"]),
]

# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def recall_at_k(query: str, expected: list[str], top_k: int = 3) -> tuple[float, list[str]]:
    result = search(query, top_k=top_k)
    found_names = {m["name"] for m in result["matches"]}
    hits = [e for e in expected if e in found_names]
    return len(hits) / len(expected), hits


def check_guard(query: str, expected_name: str, must_warn: list[str]) -> tuple[bool, str]:
    result = search(query)
    for m in result["matches"]:
        if m["name"].lower() == expected_name.lower():
            combined = (m["when_not_to_pick"] + " " + m["extra"]).lower()
            triggered = [w for w in must_warn if w in combined]
            if triggered:
                return True, f"found '{triggered[0]}' in {m['name']}"
            return False, f"{m['name']} found but warn words {must_warn!r} absent"
    names = [m["name"] for m in result["matches"]]
    return False, f"{expected_name!r} not in top-3 (got {names})"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Loading KB and model (first run downloads ~90 MB)...")
    print()

    # --- Golden set ---
    print(f"{'GOLDEN RETRIEVAL SET':=<60}")
    per_query_recalls: list[float] = []
    misses: list[tuple[str, list[str], list[str]]] = []

    for query, expected in GOLDEN:
        rec, hits = recall_at_k(query, expected)
        per_query_recalls.append(rec)
        missed = [e for e in expected if e not in hits]
        status = "OK" if rec == 1.0 else f"MISS({', '.join(missed)})"
        print(f"  {query:<42}  recall={rec:.2f}  {status}")
        if missed:
            misses.append((query, expected, missed))

    overall_recall = sum(per_query_recalls) / len(per_query_recalls)
    golden_pass = overall_recall >= 0.85
    print()
    print(f"  Overall recall@3: {overall_recall:.1%}  (target >= 85%)  {'PASS' if golden_pass else 'FAIL'}")

    # --- Guard set ---
    print()
    print(f"{'HALLUCINATION GUARD SET':=<60}")
    guard_results: list[bool] = []

    for query, expected_name, must_warn in GUARD:
        passed, detail = check_guard(query, expected_name, must_warn)
        guard_results.append(passed)
        print(f"  {query:<42}  {'PASS' if passed else 'FAIL'}  {detail}")

    guard_pass = all(guard_results)
    print()
    print(f"  Guard pass rate: {sum(guard_results)}/{len(guard_results)}  (target 100%)  {'PASS' if guard_pass else 'FAIL'}")

    # --- Summary ---
    print()
    print("=" * 60)
    print(f"  Golden recall: {overall_recall:.1%}  {'PASS' if golden_pass else 'FAIL'}")
    print(f"  Guard:         {sum(guard_results)}/{len(guard_results)}  {'PASS' if guard_pass else 'FAIL'}")
    print("=" * 60)

    if not golden_pass or not guard_pass:
        print()
        print("FIX HINTS")
        for query, expected, missed in misses:
            print(f"  query: {query!r}")
            for m in missed:
                print(f"    missing: {m!r} -- add its keywords to aliases or when_to_pick")
        sys.exit(1)

    print()
    print("Both gates pass. KB is ready to ship.")
