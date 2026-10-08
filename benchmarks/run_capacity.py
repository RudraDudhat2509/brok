import json, statistics as st, sys, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from capacity_cases import CASES
from brok.pipeline import review_from_components

def brok(comps, traffic):
    r = review_from_components([{"name": n, "type": t} for n, t in comps], traffic)
    return r["bottleneck"], r["max_dau"], r

def score(pred_b, pred_d, exp_b, exp_d):
    bn = pred_b == exp_b
    if exp_d is None:
        return bn, (pred_d is None), None
    ratio = (pred_d / exp_d) if pred_d else None
    return bn, (ratio is not None and 0.5 <= ratio <= 2), ratio

rows = []
for name, comps, traffic, eb, ed in CASES:
    pb, pd, _ = brok(comps, traffic)
    bn, w2, ratio = score(pb, pd, eb, ed)
    rows.append((name, eb, pb, ed, pd, bn, w2, ratio))
    print(f"{name:30s} exp=({eb},{ed}) got=({pb},{pd}) bn={bn} within2x={w2}")
n = len(rows)
cap = [r for r in rows if r[3] is not None]
print(f"\nbottleneck accuracy {sum(r[5] for r in rows)}/{n}")
print(f"within 2x (capacity cases, n={len(cap)}) {sum(r[6] for r in cap)}/{len(cap)}")
print(f"off by >=100x {sum(1 for r in cap if r[7] is None or r[7]>=100 or r[7]<=0.01)}/{len(cap)}")
print(f"abstain correct {sum(r[5] for r in rows if r[3] is None)}/{sum(1 for r in rows if r[3] is None)}")
print(f"max |pred/exp-1| {max(abs(r[7]-1) for r in cap):.6f}")

# speed
from brok.pipeline import review_from_components as rfc
comps = [{"name": n, "type": t} for n, t in CASES[2][1]]
t = []
for _ in range(500):
    s = time.perf_counter(); rfc(comps, CASES[2][2]); t.append((time.perf_counter() - s) * 1000)
t.sort(); print(f"review_from_components ms p50={t[250]:.3f} p95={t[475]:.3f} (n=500)")

# determinism: 20 designs x 10 runs, byte-identical full output
ident = True
for name, cs, tr, *_ in CASES[:20]:
    outs = {json.dumps(rfc([{"name": n, "type": ty} for n, ty in cs], tr), sort_keys=True, default=str) for _ in range(10)}
    ident &= len(outs) == 1
print("deterministic (20 designs x 10 runs byte-identical):", ident)
