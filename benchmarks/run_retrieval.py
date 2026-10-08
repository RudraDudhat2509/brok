"""Retrieval metrics on the repo's 30-query golden set + 20 NEW paraphrase/typo queries (expected entries written before running)."""
import sys, time, statistics as st, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "scripts"))
from bench_query import GOLDEN, GUARD, check_guard
from brok.query import search

PARA = [
 ("should i pick kafka or google pubsub for streaming events",       ["Kafka", "Pub/Sub"]),
 ("kafak versus sqs which one",                                      ["Kafka", "SQS"]),
 ("is redis or memchached better for caching sessions",              ["Redis", "Memcached"]),
 ("postgress or cockroach for a worldwide app",                      ["PostgreSQL", "CockroachDB"]),
 ("amazon s3 compared with google cloud storage",                    ["S3", "GCS"]),
 ("cdn choice: cloudflare or aws cloudfront",                        ["Cloudflare", "CloudFront"]),
 ("my table is too big for one machine, how do i split it up",       ["consistent hashing", "hash-based sharding"]),
 ("which keys should i throw out first when my cache fills up",      ["LRU", "TTL"]),
 ("update the cache and database in the same request or later",      ["write-through", "write-back"]),
 ("one kafka partition is getting all the traffic",                  ["hot partition avoidance"]),
 ("can i guarantee a message is processed only once",                ["exactly-once delivery"]),
 ("split reads away from the primary database",                     ["read replicas"]),
 ("separate the read model from the write model",                    ["CQRS"]),
 ("how do i keep data consistent across microservices without 2pc",  ["Saga"]),
 ("stop calling a failing downstream service repeatedly",            ["Circuit Breaker"]),
 ("store every state change as an immutable log of events",          ["Event Sourcing"]),
 ("gradually replace a legacy monolith piece by piece",              ["Strangler Fig"]),
 ("limit how many requests a client can make per minute",           ["Rate Limiter"]),
 ("one slow dependency should not exhaust all my threads",           ["Bulkhead"]),
 ("serve images and javascript bundles close to users",              ["Cloudflare", "CloudFront"]),
]

def evaluate(rows, k):
    r1 = r3 = r5 = 0.0; rr = []
    for q, exp in rows:
        names = [m["name"] for m in search(q, top_k=5)["matches"]]
        r1 += sum(e in names[:1] for e in exp) / len(exp)
        r3 += sum(e in names[:3] for e in exp) / len(exp)
        r5 += sum(e in names[:5] for e in exp) / len(exp)
        rank = next((i + 1 for i, n in enumerate(names) if n in exp), None)
        rr.append(1 / rank if rank else 0)
    n = len(rows); return r1 / n, r3 / n, r5 / n, st.mean(rr)

search("warmup")
for label, rows in (("golden (n=30)", GOLDEN), ("paraphrase/typo (n=20)", PARA)):
    a, b, c, m = evaluate(rows, 5)
    print(f"{label}: recall@1 {a:.3f}  recall@3 {b:.3f}  recall@5 {c:.3f}  MRR {m:.3f}")
ok = sum(check_guard(q, n, w)[0] for q, n, w in GUARD)
print(f"hallucination guard: {ok}/{len(GUARD)}")
for q, exp in PARA:
    names = [m["name"] for m in search(q, top_k=3)["matches"]]
    miss = [e for e in exp if e not in names]
    if miss: print("  MISS", q, "| missing", miss, "| got", names)
t = []
for i in range(300):
    s = time.perf_counter(); search(GOLDEN[i % 30][0]); t.append((time.perf_counter() - s) * 1000)
t.sort(); print(f"search() ms p50={t[150]:.1f} p95={t[285]:.1f} (n=300, model warm)")
