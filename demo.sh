#!/usr/bin/env bash
# Brok interview demo. Run: bash demo.sh   (NOPAUSE=1 skips the Enter prompts)
# Needs the repo's Python env with brok installed. No API keys, no network.
cd "$(dirname "$0")" || exit 1
export PYTHONIOENCODING=utf-8 PYTHONWARNINGS=ignore PYTHONPATH=.
PY=""
for c in python python3 python.exe py; do command -v "$c" >/dev/null 2>&1 && PY="$c" && break; done
[ "$c" = py ] && PY="py -3"
[ -n "$PY" ] || { echo "No Python found. Open Git Bash or an Anaconda prompt in this folder and run: bash demo.sh"; exit 1; }
TMPPY="$(mktemp "${TMPDIR:-/tmp}/brok_demo.XXXXXX.py")"
trap 'rm -f "$TMPPY"' EXIT
cat > "$TMPPY" <<'PY'
import json, os
from brok.pipeline import review_from_components

def pause():
    if not os.environ.get("NOPAUSE"):
        input("\n[Enter for next step] ")
    print()

def step(t): print(f"\n=== {t} ===")

def comps(*pairs): return [{"name": n, "type": t} for n, t in pairs]

LOAD = dict(expected_dau=3_000_000, requests_per_user_per_day=60, read_write_ratio=4, payload_kb=20)
def review(components, expected_dau=None, **kw):
    return review_from_components(components, {"dau": expected_dau, "requests_per_user_per_day": kw.get("requests_per_user_per_day"),
                                               "read_write_ratio": kw.get("read_write_ratio"), "payload_kb": kw.get("payload_kb")})

step("1/5  You design a system. How long until it falls over?")
print("Design: one API server + one Postgres. 3M daily users, 60 requests each, 4 reads per write.")
r = review(comps(("api", "app_server"), ("orders-db", "relational_db")), **LOAD)
print(r["roast_text"])
print(f"\nbottleneck: {r['bottleneck']}   max DAU before it saturates: {r['max_dau']:,}")
pause()

step("2/5  Obvious fix: add a cache. Does that help?")
r = review(comps(("api", "app_server"), ("orders-db", "relational_db"), ("cache", "cache")), **LOAD)
print(f"bottleneck: {r['bottleneck']}   max DAU: {r['max_dau']:,}")
for u in r["utilizations"]:
    if u["utilization"] is not None:
        print(f"  {u['component']:10s} load {u['load_per_sec']:>9,.0f}/s   ceiling {u['ceiling_per_sec']:>9,.0f}/s   utilization {u['utilization']:.2f}")
print("\nThe wall moves off the database onto the single app server. Every ceiling is cited in brok/kb.py.")
pause()

step("3/5  It refuses to guess: unknown tech means no made-up verdict")
r = review(comps(("mystery", "cassandra")), expected_dau=100_000)
print(f"bottleneck: {r['bottleneck']}   max_dau: {r['max_dau']}   confidence: {r['confidence']}")
print("notes:", r["notes"])
pause()

step("4/5  Trade-off lookup (local embeddings, cited knowledge base, no API calls)")
try:
    print("(loading the embedding model, a few seconds)")
    from brok.query import search
    matches = search("kafka vs sqs")["matches"]
except ImportError as e:
    matches = []
    print(f"skipped, missing package ({e}). Fix once with: pip install -e .")
for m in matches:
    print(f"- {m['name']}\n    pick when:  {m['when_to_pick'][:140]}...\n    avoid when: {m['when_not_to_pick'][:140]}...\n    source:     {m['citation']}")
pause()

step("5/5  Deterministic: same input, same bytes, 10 runs")
args = comps(("api", "app_server"), ("db", "relational_db"))
outs = {json.dumps(review(args, expected_dau=500_000, requests_per_user_per_day=50, read_write_ratio=10), sort_keys=True, default=str) for _ in range(10)}
print("distinct outputs across 10 runs:", len(outs), "(1 = identical)")
print("\nProof: BENCHMARKS.md. 359 tests, 98% coverage, 21/21 bottlenecks on a hand-derived set.")
PY
$PY "$(cygpath -w "$TMPPY" 2>/dev/null || echo "$TMPPY")"
