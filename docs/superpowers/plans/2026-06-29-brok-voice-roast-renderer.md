# Brok Voice (Roast Renderer) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Brok its voice: a deterministic roast renderer that phrases the capacity verdict in Brok's dry, blunt register (per `docs/brok-voice.md`), anchored to the real numbers, with the personality coming from a curated template library, not a model.

**Architecture:** A new `brok/voice.py` holds Brok-voiced templates keyed by finding type and severity, a deterministic selector (stable hash, same input gives same roast), per-component fix hints, and `render_roast(report)` which builds the roasted card. It is wired into the pipeline result as a new `roast_text` field, alongside the existing plain `report_text`. No model, no network: the humor lives in fixed templates, the punch is the real cited number, so a roast can never be hallucinated or wrong.

**Tech Stack:** Python 3.11+, `pydantic` v2, `pytest`, stdlib `hashlib`. No model, no network. Builds on Plans 1-3.

## Global Constraints

- Python **3.11+**; Pydantic **v2**.
- **Deterministic, no model, no network.** The roast is templated; the same `CapacityReport` always yields the same roast text.
- **No em dashes** anywhere in user-facing text (Brok's copy included). Use commas, periods, parentheses.
- **PG-13.** Blunt and dry, no profanity. The number does the cutting.
- **Confidence gating (voice rule):** never roast hard when the verdict hinges on a guessed scale. If the daily-user count was assumed (not provided), use the hedged template, not the brutal one. If there is no bottleneck (abstain / insufficient data), use the "bring me numbers" template, never a roast.
- **Roast the design, never the person.** Templates target the component and the decision.
- **Non-breaking:** the existing plain `render_report` and `report_text` stay; this adds `roast_text`.
- Commits: one per task, no co-author / AI-attribution trailer. (Repo git identity already configured.)

## Per-Task Gate (blocking, deterministic)

After a task's own test step goes green, run the full suite as the gate:

```bash
pytest -q
```

Pass condition: exit 0; every test passes (0 failed, 0 errored); no network/model. If red, stop and fix before the next task.

---

### Task 1: The Brok template library + roast line

**Files:**
- Create: `brok/voice.py`
- Test: `tests/test_voice.py`

**Interfaces:**
- Consumes: `CapacityReport`, `Utilization`, `ComponentType` from `brok.models`.
- Produces:
  - `FIX_HINTS: dict[ComponentType, str]`
  - `BROK_LINES: dict[str, list[str]]` keyed by bucket: `"brutal"`, `"bad"`, `"slight"`, `"fits"`, `"low_conf_over"`, `"insufficient"`. Templates use `{component}`, `{factor}`, `{max_dau}`, `{fix}` placeholders.
  - `classify(report: CapacityReport) -> str` returns the bucket.
  - `roast_line(report: CapacityReport) -> str` classifies, picks a template deterministically (stable hash of the bottleneck name, or `"_"` when none), and slots in the real values.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_voice.py
from brok.models import CapacityReport, ComponentType, Utilization
from brok.voice import classify, roast_line


def _util(name, ctype, util):
    return Utilization(component=name, type=ctype, load_per_sec=8000.0,
                       ceiling_per_sec=1000.0, utilization=util, estimated=True)


def _report(bottleneck, max_dau, util, ctype=ComponentType.RELATIONAL_DB,
            confidence="high", assumptions=None):
    utils = [_util(bottleneck, ctype, util)] if bottleneck else []
    return CapacityReport(bottleneck=bottleneck, max_dau=max_dau, utilizations=utils,
                          assumptions=assumptions or [], confidence=confidence, notes=[])


def test_classify_buckets():
    assert classify(_report("db", 12000, 8.0)) == "brutal"
    assert classify(_report("db", 30000, 3.0)) == "bad"
    assert classify(_report("db", 90000, 1.4)) == "slight"
    assert classify(_report("db", 5_000_000, 0.2)) == "fits"
    assert classify(_report(None, None, None)) == "insufficient"


def test_classify_hedges_when_dau_assumed():
    r = _report("db", 12000, 8.0, confidence="low",
                assumptions=["Assumed 100,000 daily active users."])
    assert classify(r) == "low_conf_over"


def test_roast_line_contains_the_numbers():
    line = roast_line(_report("orders-db", 12000, 8.0))
    assert "orders-db" in line
    assert "12,000" in line
    assert "8" in line  # the over factor


def test_roast_line_deterministic():
    r = _report("db", 12000, 8.0)
    assert roast_line(r) == roast_line(r)


def test_roast_line_insufficient_has_no_fabricated_number():
    line = roast_line(_report(None, None, None))
    assert "numbers" in line.lower() or "design" in line.lower()


def test_no_em_dash_in_any_template():
    from brok.voice import BROK_LINES
    for lines in BROK_LINES.values():
        for t in lines:
            assert "—" not in t
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_voice.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'brok.voice'`

- [ ] **Step 3: Write `brok/voice.py`**

```python
# brok/voice.py
from __future__ import annotations

import hashlib

from brok.models import CapacityReport, ComponentType

FIX_HINTS: dict[ComponentType, str] = {
    ComponentType.RELATIONAL_DB: "shard it by a high cardinality key, or put a write queue in front",
    ComponentType.APP_SERVER: "run more instances behind the load balancer, it scales out fine",
    ComponentType.CACHE: "shard the cache or add read replicas",
    ComponentType.LOAD_BALANCER: "add another node or move to a managed balancer",
    ComponentType.OBJECT_STORE: "spread the keys across more prefixes",
    ComponentType.QUEUE: "add partitions or brokers",
    ComponentType.CDN: "stop sending writes to a read cache",
}
_DEFAULT_FIX = "scale that component out before it is the wall"

BROK_LINES: dict[str, list[str]] = {
    "brutal": [
        "Your {component} is doing the work of {factor} of itself and getting paid for one. It dies near {max_dau} users. {fix}.",
        "{factor}x over the line on {component}. That is not a database, that is a hostage situation. It taps out around {max_dau} users. {fix}.",
        "{component} folds near {max_dau} users, then it is {factor}x underwater. {fix}.",
    ],
    "bad": [
        "{component} is about {factor}x over its ceiling. It holds to roughly {max_dau} users, then it folds. {fix}.",
        "You are leaning on {component} {factor}x harder than it wants. Wall is about {max_dau} users. {fix}.",
    ],
    "slight": [
        "{component} is a touch over, about {factor}x. You get to about {max_dau} users before it complains. {fix}.",
        "{component} is just past its line, {factor}x. Roughly {max_dau} users and then it grumbles. {fix}.",
    ],
    "fits": [
        "Fine. It holds to about {max_dau} users before {component} is the wall. I have seen worse today.",
        "This one holds, about {max_dau} users of room before {component} gives. Do not get used to me saying that.",
    ],
    "low_conf_over": [
        "If your numbers are real, {component} is about {factor}x over and caps near {max_dau} users. But you gave me a user count out of thin air, so do not quote me. {fix}.",
        "On my assumed scale, {component} is {factor}x over, wall near {max_dau} users. Give me a real user count and I will give you a real verdict. {fix}.",
    ],
    "insufficient": [
        "You gave me half a design. I do not guess. Bring me the pieces and a user count and I will bring you a verdict.",
        "Nothing here I can put a number to. Hand me real components and a scale, then we talk.",
    ],
}


def _bottleneck_util_and_type(report: CapacityReport):
    for u in report.utilizations:
        if u.component == report.bottleneck and u.utilization is not None:
            return u.utilization, u.type
    return None, None


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
    return "fits"


def _pick(options: list[str], seed: str) -> str:
    idx = int(hashlib.md5(seed.encode()).hexdigest(), 16) % len(options)
    return options[idx]


def roast_line(report: CapacityReport) -> str:
    bucket = classify(report)
    template = _pick(BROK_LINES[bucket], report.bottleneck or "_")
    if bucket == "insufficient":
        return template
    util, ctype = _bottleneck_util_and_type(report)
    fix = FIX_HINTS.get(ctype, _DEFAULT_FIX)
    factor = f"{round(util, 1):g}" if util is not None else "?"
    max_dau = f"{report.max_dau:,}" if report.max_dau is not None else "?"
    return template.format(component=report.bottleneck, factor=factor,
                           max_dau=max_dau, fix=fix)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_voice.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add brok/voice.py tests/test_voice.py
git commit -m "feat: Brok template library + deterministic roast line"
```

---

### Task 2: `render_roast` (the full roasted card)

**Files:**
- Modify: `brok/voice.py`
- Test: `tests/test_render_roast.py`

**Interfaces:**
- Consumes: `roast_line`, `classify`, `CapacityReport`.
- Produces: `render_roast(report: CapacityReport) -> str` building a verdict-first roasted card:
  - a headline tag by bucket (`brutal`/`bad`/`low_conf_over` -> `WALK AWAY (for now)`; `slight` -> `PUSHING IT`; `fits` -> `IT HOLDS`; `insufficient` -> `NOT ENOUGH TO JUDGE`), prefixed `BROK:`;
  - the `roast_line`;
  - the assumptions block (when present), then a single `Confidence: <level>.` line;
  - the receipts: one line per estimated utilization (`component: <load>/sec vs ~<ceiling> ceiling`), and the `notes` under `Not estimated:` when present;
  - no em dashes.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_render_roast.py
from brok.models import CapacityReport, ComponentType, Utilization
from brok.voice import render_roast


def _report(bottleneck, max_dau, util, confidence="high", assumptions=None, notes=None):
    utils = ([Utilization(component=bottleneck, type=ComponentType.RELATIONAL_DB,
                          load_per_sec=8000.0, ceiling_per_sec=1000.0,
                          utilization=util, estimated=True)] if bottleneck else [])
    return CapacityReport(bottleneck=bottleneck, max_dau=max_dau, utilizations=utils,
                          assumptions=assumptions or [], confidence=confidence,
                          notes=notes or [])


def test_card_leads_with_brok_headline_and_roasts():
    card = render_roast(_report("db", 12000, 8.0))
    assert card.splitlines()[0].startswith("BROK:")
    assert "WALK AWAY" in card
    assert "db" in card and "12,000" in card


def test_card_shows_fits_when_under():
    card = render_roast(_report("db", 5_000_000, 0.2))
    assert "IT HOLDS" in card


def test_card_shows_assumptions_and_single_confidence():
    card = render_roast(_report("db", 12000, 8.0, confidence="low",
                                assumptions=["Assumed 100,000 daily active users."]))
    assert "Assumed 100,000 daily active users." in card
    assert card.count("Confidence:") == 1


def test_card_lists_not_estimated_notes():
    card = render_roast(_report(None, None, None,
                                notes=["mystery (unknown) is outside the KB."]))
    assert "Not estimated" in card and "mystery" in card


def test_card_has_no_em_dash():
    assert "—" not in render_roast(_report("db", 12000, 8.0))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_render_roast.py -v`
Expected: FAIL with `ImportError: cannot import name 'render_roast'`

- [ ] **Step 3: Append to `brok/voice.py`**

```python
# --- append to brok/voice.py ---

_HEADLINE = {
    "brutal": "WALK AWAY (for now)",
    "bad": "WALK AWAY (for now)",
    "low_conf_over": "WALK AWAY (for now)",
    "slight": "PUSHING IT",
    "fits": "IT HOLDS",
    "insufficient": "NOT ENOUGH TO JUDGE",
}


def render_roast(report: CapacityReport) -> str:
    bucket = classify(report)
    lines = [f"BROK: {_HEADLINE[bucket]}", "", roast_line(report)]

    if report.assumptions:
        lines.append("")
        lines.append("Working off these assumptions (give me real ones and I re-run):")
        lines.extend(f"  {a}" for a in report.assumptions)
    lines.append("")
    lines.append(f"Confidence: {report.confidence}.")

    estimated = [u for u in report.utilizations if u.estimated and u.ceiling_per_sec]
    if estimated:
        lines.append("")
        lines.append("Receipts:")
        for u in estimated:
            lines.append(f"  {u.component}: ~{u.load_per_sec:,.0f}/sec vs "
                         f"~{u.ceiling_per_sec:,.0f} ceiling")

    if report.notes:
        lines.append("")
        lines.append("Not estimated:")
        lines.extend(f"  {n}" for n in report.notes)

    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_render_roast.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add brok/voice.py tests/test_render_roast.py
git commit -m "feat: render_roast, the verdict-first roasted card"
```

---

### Task 3: Wire `roast_text` into the pipeline and tools

**Files:**
- Modify: `brok/pipeline.py`
- Modify: `brok/server.py`
- Test: `tests/test_roast_wiring.py`

**Interfaces:**
- Consumes: `render_roast`, `analyze_capacity`, `resolve_nfrs`, `render_report`.
- Produces:
  - `build_result` adds `"roast_text": render_roast(report)` to its returned dict (keeping `report_text` plain).
  - The two MCP tools (`review_architecture`, `review_components`) therefore return `roast_text` too. Their docstrings gain one line: present `roast_text` to the user as the headline, use the structured fields to reason.
  - The empty/no-components result dict (`_empty_result`) gains a `"roast_text"` key set to the same friendly no-components text (so the shape is consistent).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_roast_wiring.py
import brok.server as server
from brok.pipeline import build_result, review_from_components
from brok.models import Component, ComponentType, DesignGraph


def _graph():
    return DesignGraph(components=[
        Component(name="api", type=ComponentType.APP_SERVER),
        Component(name="db", type=ComponentType.RELATIONAL_DB),
    ])


def test_build_result_includes_roast_text():
    res = build_result(_graph(), {"dau": 5_000_000})
    assert "roast_text" in res
    assert res["roast_text"].startswith("BROK:")


def test_tool_returns_roast_text():
    res = server.review_architecture(
        "services:\n  api: { build: . }\n  db: { image: postgres:16 }\n",
        expected_dau=50_000_000)
    assert "roast_text" in res and res["roast_text"].startswith("BROK:")


def test_empty_result_has_roast_text_key():
    res = review_from_components([])
    assert "roast_text" in res
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_roast_wiring.py -v`
Expected: FAIL (`roast_text` not in result)

- [ ] **Step 3: Update `brok/pipeline.py`**

Add the import and the `roast_text` key. In the imports near the top add:

```python
from brok.voice import render_roast
```

Change `build_result` to include the roast:

```python
def build_result(graph: DesignGraph, traffic: dict | None = None) -> dict:
    resolved, assumptions = resolve_nfrs(traffic)
    confidence = "low" if assumptions else "high"
    report = analyze_capacity(graph, resolved, assumptions, confidence)
    return {
        **report.model_dump(mode="json"),
        "report_text": render_report(report),
        "roast_text": render_roast(report),
    }
```

Change `_empty_result` to carry a `roast_text` key:

```python
def _empty_result() -> dict:
    return {
        "bottleneck": None, "max_dau": None, "utilizations": [],
        "assumptions": [], "confidence": "low", "notes": [],
        "report_text": _NO_COMPONENTS_TEXT,
        "roast_text": _NO_COMPONENTS_TEXT,
    }
```

- [ ] **Step 4: Update `brok/server.py` docstrings**

In each tool docstring, add one line after the "show the user" guidance:

```
       Prefer report["roast_text"] as the headline to show the user (Brok's voice);
       report["report_text"] is the same verdict in a neutral tone.
```

(Add it to both `review_architecture` and `review_components`. No code change to the tool bodies.)

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_roast_wiring.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Run the full suite (gate)**

Run: `pytest -q`
Expected: PASS (all green; Plan 1-3 tests untouched since `report_text` is unchanged).

- [ ] **Step 7: Commit**

```bash
git add brok/pipeline.py brok/server.py tests/test_roast_wiring.py
git commit -m "feat: expose roast_text from pipeline and MCP tools"
```

---

## Manual Verification (after Task 3)

```python
import brok.server as s
r = s.review_architecture(
    "services:\n  api: { build: . }\n  db: { image: postgres:16 }\n  cache: { image: redis:7 }\n",
    expected_dau=2_000_000)
print(r["roast_text"])
```

Confirm: a `BROK:` headline, a dry roast line naming the bottleneck with the real over-factor and max users, the one fix, receipts, and no em dashes. Run twice and confirm the roast text is identical (deterministic).

---

## Self-Review Notes (author)

- **Spec coverage:** §4 layer 4 (roast narrator) and `docs/brok-voice.md` (the persona): verdict-first (Task 2 headline), numbers-are-the-punchline (every roast line slots the real factor + max_dau), earn-the-praise (the `fits` lines are grudging), end-on-the-fix (FIX_HINTS), never-roast-when-uncertain (`low_conf_over` and `insufficient` buckets, gated on whether DAU was assumed), PG-13 + no copied lines (original templates), no em dashes (pinned by a test).
- **Design decision:** the roast is deterministic templates, not a model. This preserves Brok's identity (free, runs anywhere, deterministic, never hallucinates a roast). A model paraphrase layer is possible later but is explicitly out of scope here; flagged for the human at plan review.
- **Non-breaking:** `report_text` and `render_report` are unchanged; this only adds `roast_text`. Plan 1-3 tests stay green.
- **Confidence gating nuance:** hedging keys off whether the daily-user count specifically was assumed (`"daily active users"` in assumptions), not the coarse low/high flag, so a roast lands when the user supplied scale and softens when they did not.
- **Placeholder scan:** none; every step ships real code + a real command.
- **Type consistency:** `classify`/`roast_line`/`render_roast` signatures and the `CapacityReport`/`Utilization` fields match Plans 1-3; `build_result` return shape extended, not changed.
```
