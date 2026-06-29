# Brok Latency + Cost Lenses Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two grounded, deterministic lenses to Brok: a queueing-aware latency signal (the utilization knee, not a fabricated millisecond number) and a rough monthly cost estimate (curated compute table + egress computed from data Brok already has), both surfaced in the roast card.

**Architecture:** Additive on the existing engine. A tiny new `brok/lenses/latency.py` holds the knee constant and the relative latency multiplier `1/(1-rho)`. The voice gains a `degrading` verdict band (utilization at or past the 0.7 knee but still under cap) that reports the latency multiplier and the safe user count (`max_dau * KNEE`). A new `brok/lenses/cost.py` holds a curated, cited cost table and computes monthly compute + egress; `build_result` gains a `cost` field and the roast card gains a cost section. No model, no network, no change to the capacity math itself.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest. Builds on the capacity engine + voice + trade-off layer (current `development` branch).

## Global Constraints

- Python **3.11+**; Pydantic **v2**.
- **Deterministic, no model, no network.** Latency is a relative multiplier from utilization; cost is a curated table plus arithmetic. No absolute latency in milliseconds (the inputs that would require, per-language compute time and cache hit ratio, are unmeasurable here).
- **Cited.** The cost table carries a `source` string, same discipline as the capacity KB.
- **No em dashes** in any user-facing text (KB content, render, docstrings, tests). Use commas, periods, semicolons.
- **Additive.** Do not change the capacity math (`analyze_capacity`, `peak_rps`), `report_text`, the `tradeoffs` field, or existing model fields. The only intended behavior change is `classify` gaining the `degrading` band for utilization in `[0.7, 1.0]` (previously `fits`); this is the point of the latency lens. All other prior tests stay green.
- Base branch is **`development`**. Branch off `development`; the PR targets `development`.
- Commits: one per task, no co-author / AI-attribution trailer. (Repo git identity already configured.)

## Per-Task Gate (blocking, deterministic)

After a task's own test step goes green, run the full suite as the gate:

```bash
pytest -q
```

Pass condition: exit 0; every test passes; no network/model. If red, stop and fix before the next task.

---

### Task 1: The latency lens (the knee)

**Files:**
- Create: `brok/lenses/latency.py`
- Test: `tests/test_latency.py`

**Interfaces:**
- Consumes: nothing (pure functions).
- Produces:
  - `KNEE: float = 0.7` (the utilization past which queueing latency climbs sharply, M/M/1).
  - `latency_multiplier(util: float | None) -> float | None` returns `1 / (1 - util)` for `0 <= util < 1`; returns `None` when `util is None`, `util >= 1.0` (saturated, latency is not a finite multiple), or `util < 0`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_latency.py
from brok.lenses.latency import KNEE, latency_multiplier


def test_knee_is_point_seven():
    assert KNEE == 0.7


def test_multiplier_matches_queueing_formula():
    assert latency_multiplier(0.5) == 2.0
    assert latency_multiplier(0.8) == 5.0
    assert round(latency_multiplier(0.9), 1) == 10.0


def test_multiplier_none_when_unknown_or_saturated():
    assert latency_multiplier(None) is None
    assert latency_multiplier(1.0) is None
    assert latency_multiplier(3.0) is None
    assert latency_multiplier(-0.1) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_latency.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'brok.lenses.latency'`

- [ ] **Step 3: Write `brok/lenses/latency.py`**

```python
# brok/lenses/latency.py
from __future__ import annotations

# Utilization past which queueing latency climbs sharply (M/M/1 knee).
KNEE: float = 0.7


def latency_multiplier(util: float | None) -> float | None:
    """Relative latency vs the idle baseline under M/M/1 queueing: 1 / (1 - rho).

    None when utilization is unknown, negative, or at/over capacity. At or past
    1.0 the component is saturated and latency is not a finite multiple of the
    baseline, so Brok declines to put a number on it rather than fabricate one.
    """
    if util is None or util < 0 or util >= 1.0:
        return None
    return 1.0 / (1.0 - util)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_latency.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add brok/lenses/latency.py tests/test_latency.py
git commit -m "feat: latency lens, the queueing knee and relative multiplier"
```

---

### Task 2: Surface the knee in the voice

**Files:**
- Modify: `brok/voice.py`
- Test: `tests/test_knee_voice.py`

**Interfaces:**
- Consumes: `KNEE`, `latency_multiplier` from `brok.lenses.latency`.
- Produces:
  - `classify` returns `"degrading"` when the bottleneck utilization is in `[KNEE, 1.0]` (was `"fits"`).
  - `_HEADLINE["degrading"] = "CUTTING IT CLOSE"`.
  - `BROK_LINES["degrading"]` templates that use `{component}`, `{pct}`, `{mult}`, `{safe_dau}`, `{max_dau}`, `{fix}`.
  - `roast_line` computes and passes `pct`, `mult`, and `safe_dau` (= `int(max_dau * KNEE)`) to `.format` for every non-insufficient bucket.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_knee_voice.py
from brok.models import CapacityReport, ComponentType, Utilization
from brok.voice import classify, render_roast


def _report(util, max_dau=1_000_000, assumptions=None):
    u = Utilization(component="db", type=ComponentType.RELATIONAL_DB,
                    load_per_sec=util * 1000, ceiling_per_sec=1000.0,
                    utilization=util, estimated=True)
    return CapacityReport(bottleneck="db", max_dau=max_dau, utilizations=[u],
                          assumptions=assumptions or [], confidence="high", notes=[])


def test_knee_band_is_degrading():
    assert classify(_report(0.85)) == "degrading"
    assert classify(_report(0.7)) == "degrading"


def test_below_knee_still_fits():
    assert classify(_report(0.5)) == "fits"


def test_over_cap_unchanged():
    assert classify(_report(3.0)) == "bad"


def test_degrading_card_shows_multiplier_and_safe_dau():
    card = render_roast(_report(0.8, max_dau=1_000_000))
    assert "CUTTING IT CLOSE" in card
    assert "5.0" in card          # 1/(1-0.8) latency multiplier
    assert "700,000" in card      # safe_dau = max_dau * 0.7
    assert "—" not in card
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_knee_voice.py -v`
Expected: FAIL (`classify(_report(0.85))` returns `"fits"`, not `"degrading"`)

- [ ] **Step 3: Add the import at the top of `brok/voice.py`**

Below the existing `from brok.tradeoffs import tradeoffs_for` line, add:

```python
from brok.lenses.latency import KNEE, latency_multiplier
```

- [ ] **Step 4: Add the `degrading` bucket to `classify`**

Replace the `classify` function with this version (the only change is the two lines before the final `return "fits"`):

```python
def classify(report: CapacityReport) -> str:
    util, _ = _bottleneck_util_and_type(report)
    if report.bottleneck is None or util is None:
        return "insufficient"
    if util > 1.0:
        dau_assumed = any("daily active users" in a for a in report.assumptions)
        if dau_assumed:
            return "low_conf_over"
        if util >= 5:
            return "brutal"
        if util >= 2:
            return "bad"
        return "slight"
    if util >= KNEE:
        return "degrading"
    return "fits"
```

- [ ] **Step 5: Add the `degrading` templates and headline**

In `BROK_LINES`, add a `"degrading"` entry (place it after the `"slight"` list, before `"fits"`):

```python
    "degrading": [
        "{component} is running {pct} hot. Under the cap, sure, but past the knee, so queueing already puts latency near {mult}x idle. Real headroom is about {safe_dau} users, not {max_dau}. {fix}.",
        "{component} sits at {pct} of its ceiling. It works until it does not; at this load latency is about {mult}x its idle baseline. Plan for about {safe_dau} users. {fix}.",
    ],
```

In the `_HEADLINE` dict, add the `"degrading"` key:

```python
    "degrading": "CUTTING IT CLOSE",
```

- [ ] **Step 6: Extend `roast_line` to supply `pct`, `mult`, `safe_dau`**

Replace `roast_line` with this version (adds three computed format values; the `degrading` templates consume them and the other buckets ignore the extras):

```python
def roast_line(report: CapacityReport) -> str:
    bucket = classify(report)
    template = _pick(BROK_LINES[bucket], report.bottleneck or "_")
    if bucket == "insufficient":
        return template
    util, ctype = _bottleneck_util_and_type(report)
    fix = FIX_HINTS.get(ctype, _DEFAULT_FIX)
    factor = f"{round(util, 1):g}" if util is not None else "?"
    max_dau = f"{report.max_dau:,}" if report.max_dau is not None else "?"
    safe_dau = f"{int(report.max_dau * KNEE):,}" if report.max_dau is not None else "?"
    pct = f"{round(util * 100)}%" if util is not None else "?"
    mult_val = latency_multiplier(util)
    mult = f"{mult_val:.1f}" if mult_val is not None else "?"
    return template.format(component=report.bottleneck, factor=factor,
                           max_dau=max_dau, fix=fix, safe_dau=safe_dau,
                           pct=pct, mult=mult)
```

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest tests/test_knee_voice.py -v`
Expected: PASS (4 passed)

- [ ] **Step 8: Run the full suite (gate)**

Run: `pytest -q`
Expected: PASS (all green). The existing `test_classify_buckets` uses utilization 0.2 for `fits`, which is below the knee, so it stays `fits`; no existing voice test uses a 0.7 to 1.0 utilization.

- [ ] **Step 9: Commit**

```bash
git add brok/voice.py tests/test_knee_voice.py
git commit -m "feat: degrading verdict band with latency multiplier and safe user count"
```

---

### Task 3: The cost lens

**Files:**
- Create: `brok/lenses/cost.py`
- Modify: `brok/voice.py` (add `render_cost`)
- Modify: `brok/pipeline.py` (compute cost, surface it)
- Modify: `brok/server.py` (mention `cost` in both docstrings' return lines)
- Test: `tests/test_cost.py`

**Interfaces:**
- Consumes: `ComponentType`, `DesignGraph`, `NFRs`; `estimate_cost`; `render_cost`.
- Produces:
  - `estimate_cost(graph: DesignGraph, nfrs: NFRs) -> dict` with keys `monthly_compute_usd`, `monthly_egress_usd`, `monthly_total_usd`, `egress_gb_per_month`, `breakdown` (list of `{component, type, monthly_usd}`), `assumptions` (list), `source`.
  - `render_cost(cost: dict | None) -> str` returns `""` when cost is falsy, else `"\n\n"` followed by a `WHAT IT COSTS (rough monthly):` block.
  - `build_result` returns `"cost": estimate_cost(graph, resolved)` and its `roast_text` is `render_roast(report) + render_cost(cost)`. `_empty_result` returns `"cost": None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cost.py
from brok.lenses.cost import estimate_cost
from brok.models import Component, ComponentType, DesignGraph, NFRs
from brok.pipeline import build_result, review_from_components


def _nfrs():
    return NFRs(dau=1_000_000, requests_per_user_per_day=100,
                read_write_ratio=10.0, payload_kb=10.0, peak_factor=3.0)


def _graph():
    return DesignGraph(components=[
        Component(name="api", type=ComponentType.APP_SERVER),
        Component(name="db", type=ComponentType.RELATIONAL_DB),
    ])


def test_compute_cost_sums_known_components():
    cost = estimate_cost(_graph(), _nfrs())
    assert cost["monthly_compute_usd"] == 180.0  # 60 app + 120 db


def test_egress_matches_formula():
    nfrs = _nfrs()
    cost = estimate_cost(_graph(), nfrs)
    avg_rps = nfrs.dau * nfrs.requests_per_user_per_day / 86400
    expected_gb = avg_rps * (nfrs.payload_kb * 1024) * 2_592_000 / (1024 ** 3)
    assert abs(cost["monthly_egress_usd"] - round(expected_gb * 0.09, 2)) < 0.01


def test_total_is_compute_plus_egress():
    cost = estimate_cost(_graph(), _nfrs())
    assert abs(cost["monthly_total_usd"]
               - (cost["monthly_compute_usd"] + cost["monthly_egress_usd"])) < 0.01


def test_cited_and_no_em_dash():
    cost = estimate_cost(_graph(), _nfrs())
    assert cost["source"]
    for a in cost["assumptions"]:
        assert "—" not in a
    assert "—" not in cost["source"]


def test_build_result_has_cost_and_roast_shows_it():
    res = build_result(_graph(), {"dau": 1_000_000})
    assert "cost" in res and res["cost"]["monthly_total_usd"] > 0
    assert "WHAT IT COSTS" in res["roast_text"]


def test_empty_result_cost_is_none():
    res = review_from_components([])
    assert res["cost"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cost.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'brok.lenses.cost'`

- [ ] **Step 3: Write `brok/lenses/cost.py`**

```python
# brok/lenses/cost.py
from __future__ import annotations

from brok.models import ComponentType, DesignGraph, NFRs

# Normalized monthly USD, one mid-tier instance, order-of-magnitude.
COMPUTE_USD_PER_MONTH: dict[ComponentType, float] = {
    ComponentType.APP_SERVER: 60.0,
    ComponentType.RELATIONAL_DB: 120.0,
    ComponentType.CACHE: 80.0,
    ComponentType.QUEUE: 100.0,
    ComponentType.LOAD_BALANCER: 20.0,
}
EGRESS_USD_PER_GB = 0.09
SECONDS_PER_MONTH = 2_592_000
COST_SOURCE = ("Normalized cloud list prices (AWS/GCP/Azure), one mid-tier instance, "
               "order-of-magnitude; internet egress about $0.09/GB")


def estimate_cost(graph: DesignGraph, nfrs: NFRs) -> dict:
    breakdown: list[dict] = []
    compute_total = 0.0
    for c in graph.components:
        usd = COMPUTE_USD_PER_MONTH.get(c.type)
        if usd is None:
            continue
        compute_total += usd
        breakdown.append({"component": c.name, "type": c.type.value,
                          "monthly_usd": round(usd, 2)})

    avg_rps = nfrs.dau * nfrs.requests_per_user_per_day / 86400
    egress_gb = avg_rps * (nfrs.payload_kb * 1024) * SECONDS_PER_MONTH / (1024 ** 3)
    egress_usd = egress_gb * EGRESS_USD_PER_GB

    return {
        "monthly_compute_usd": round(compute_total, 2),
        "monthly_egress_usd": round(egress_usd, 2),
        "monthly_total_usd": round(compute_total + egress_usd, 2),
        "egress_gb_per_month": round(egress_gb, 1),
        "breakdown": breakdown,
        "assumptions": [
            "One instance per component at a mid-tier size.",
            "All response payload counts as internet egress.",
            "Storage volume and per-request charges not modeled.",
        ],
        "source": COST_SOURCE,
    }
```

- [ ] **Step 4: Add `render_cost` to `brok/voice.py`**

Append this function at the end of `brok/voice.py`:

```python
def render_cost(cost: dict | None) -> str:
    if not cost:
        return ""
    body = [
        "WHAT IT COSTS (rough monthly):",
        f"  compute ${cost['monthly_compute_usd']:,.0f}, egress "
        f"${cost['monthly_egress_usd']:,.0f}, total ${cost['monthly_total_usd']:,.0f}.",
        f"  about {cost['egress_gb_per_month']:,.0f} GB/month leaving the system, "
        f"order-of-magnitude.",
    ]
    return "\n\n" + "\n".join(body)
```

- [ ] **Step 5: Wire cost into `brok/pipeline.py`**

Update the imports. Change:

```python
from brok.voice import render_roast
```

to:

```python
from brok.voice import render_cost, render_roast
```

and below the existing `from brok.tradeoffs import tradeoffs_for` line add:

```python
from brok.lenses.cost import estimate_cost
```

Replace `build_result` with:

```python
def build_result(graph: DesignGraph, traffic: dict | None = None) -> dict:
    resolved, assumptions = resolve_nfrs(traffic)
    confidence = "low" if assumptions else "high"
    report = analyze_capacity(graph, resolved, assumptions, confidence)
    cost = estimate_cost(graph, resolved)
    return {
        **report.model_dump(mode="json"),
        "report_text": render_report(report),
        "roast_text": render_roast(report) + render_cost(cost),
        "tradeoffs": tradeoffs_for(report),
        "cost": cost,
    }
```

In `_empty_result`, add `"cost": None` (after the `"tradeoffs": []` line):

```python
def _empty_result() -> dict:
    return {
        "bottleneck": None, "max_dau": None, "utilizations": [],
        "assumptions": [], "confidence": "low", "notes": [],
        "report_text": _NO_COMPONENTS_TEXT,
        "roast_text": _NO_COMPONENTS_TEXT,
        "tradeoffs": [],
        "cost": None,
    }
```

- [ ] **Step 6: Mention `cost` in the tool docstrings in `brok/server.py`**

In `review_architecture`, change the final Returns sentence so it ends with `cost`:

Replace:

```python
    Returns a dict: bottleneck, max_dau, confidence, assumptions, utilizations, notes,
    tradeoffs (the grounded pros, cons, and next move for each component), report_text, roast_text.
    """
```

with:

```python
    Returns a dict: bottleneck, max_dau, confidence, assumptions, utilizations, notes,
    tradeoffs (the grounded pros, cons, and next move for each component), cost (a rough
    monthly compute plus egress estimate), report_text, roast_text.
    """
```

In `review_components`, replace the sentence:

```python
    headline; use the structured fields and tradeoffs to reason. Returns the same dict shape as
    review_architecture.
```

with:

```python
    headline; use the structured fields, tradeoffs, and cost to reason. Returns the same dict
    shape as review_architecture.
```

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest tests/test_cost.py -v`
Expected: PASS (6 passed)

- [ ] **Step 8: Run the full suite (gate) + import check**

Run: `pytest -q` then `python -c "import brok.server"`
Expected: PASS (all green); `import brok.server` clean.

- [ ] **Step 9: Commit**

```bash
git add brok/lenses/cost.py brok/voice.py brok/pipeline.py brok/server.py tests/test_cost.py
git commit -m "feat: cost lens, monthly compute and egress estimate in the roast card"
```

---

## Manual Verification (after Task 3)

```python
import brok.server as s
r = s.review_components(
    components=[{"name": "api", "type": "app_server"},
                {"name": "db", "type": "relational_db"},
                {"name": "cache", "type": "cache"}],
    expected_dau=1_500_000, read_write_ratio=8, payload_kb=40)
print(r["roast_text"])   # CUTTING IT CLOSE if a component is in [0.7, 1.0]; ends with WHAT IT COSTS
print(r["cost"])         # structured monthly compute + egress
```

Confirm: when a component lands in the knee band the headline is `CUTTING IT CLOSE`, the line names the latency multiplier and the safe user count, and the roast card ends with a `WHAT IT COSTS (rough monthly)` block. The structured `cost` dict is present. No em dashes anywhere.

---

## Self-Review Notes (author)

- **Goal coverage:** latency lens = the queueing knee as a relative multiplier (Task 1 math + Task 2 surface), deliberately not absolute milliseconds (global constraint). Cost lens = curated cited compute table + egress from existing RPS and payload (Task 3). Both appear in the roast card, the shareable artifact.
- **Honest scope held:** no fabricated precision. Latency is `1/(1-rho)`, a true relative statement that needs only utilization. Cost is order-of-magnitude with stated assumptions and a cited source. Egress reuses inputs Brok already has, so it adds no new guess.
- **Additive:** capacity math, `report_text`, `tradeoffs`, and existing model fields are untouched. The single intended behavior change (the `degrading` band) is the feature, and the one existing `fits` test uses util 0.2, well below the knee.
- **Placeholder scan:** none; every step ships real code and a real command.
- **Type consistency:** `KNEE`, `latency_multiplier`, `estimate_cost`, `render_cost` are defined before use; `build_result` / `_empty_result` extended, not reshaped; `classify` / `roast_line` extended with the new bucket and format values.
