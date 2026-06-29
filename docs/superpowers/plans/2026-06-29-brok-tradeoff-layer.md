# Brok Trade-off Knowledge Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Equip Claude Code with the grounded, quantitative design trade-offs it does not reliably know, delivered at the moment it is designing: a curated trade-off KB surfaced in every review, plus tool descriptions and a skill that make CC actually call Brok when it makes an architecture decision.

**Architecture:** Purely additive on the existing engine. A new `brok/tradeoffs.py` holds a curated, cited `TRADEOFFS` table keyed by `ComponentType`. `build_result` gains a `tradeoffs` field and `render_roast` gains a "trade-offs you are making" section, both for the components in the current design. The MCP tool descriptions are rewritten to name the trigger moments, and a small companion skill tells CC to consult Brok during design and scaling decisions. No engine refactor, no model, no new dependency.

**Tech Stack:** Python 3.11+, `pydantic` v2, `pytest`. No model, no network. Builds on the capacity engine + voice (current `development` branch).

## Global Constraints

- Python **3.11+**; Pydantic **v2**.
- **Deterministic, no model, no network.** The trade-offs are curated data, not generated.
- **Cited.** Every trade-off entry carries a `source` string, same discipline as the capacity KB.
- **No em dashes** in any user-facing text (KB content, render, descriptions, skill). Use commas, periods, semicolons.
- **Additive / non-breaking.** Do not change the capacity engine, `report_text`, `roast_text` semantics, or existing fields; only add. All prior tests stay green.
- Base branch for this work is **`development`** (the voice is merged there). Branch off `development`; the PR targets `development`.
- Commits: one per task, no co-author / AI-attribution trailer. (Repo git identity already configured.)

## Per-Task Gate (blocking, deterministic)

After a task's own test step goes green, run the full suite as the gate:

```bash
pytest -q
```

Pass condition: exit 0; every test passes (0 failed, 0 errored); no network/model. If red, stop and fix before the next task.

---

### Task 1: The trade-off KB

**Files:**
- Create: `brok/tradeoffs.py`
- Test: `tests/test_tradeoffs.py`

**Interfaces:**
- Consumes: `ComponentType`, `CapacityReport` from `brok.models`.
- Produces:
  - `Tradeoff(when_fine: str, gain: str, cost: str, move: str, source: str)`
  - `TRADEOFFS: dict[ComponentType, Tradeoff]` (the 7 KB component types)
  - `get_tradeoff(t: ComponentType) -> Tradeoff | None` (None for types not in the table, e.g. UNKNOWN)
  - `tradeoffs_for(report: CapacityReport) -> list[dict]` — for each distinct component TYPE present in `report.utilizations`, in first-seen order, that has a trade-off, returns `{"type": <type value>, **tradeoff.model_dump()}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tradeoffs.py
from brok.models import CapacityReport, ComponentType, Utilization
from brok.tradeoffs import TRADEOFFS, get_tradeoff, tradeoffs_for


def test_all_seven_kb_types_have_full_tradeoffs():
    types = [ComponentType.RELATIONAL_DB, ComponentType.CACHE, ComponentType.QUEUE,
             ComponentType.CDN, ComponentType.APP_SERVER, ComponentType.OBJECT_STORE,
             ComponentType.LOAD_BALANCER]
    for t in types:
        to = get_tradeoff(t)
        assert to is not None
        assert to.when_fine and to.gain and to.cost and to.move and to.source


def test_unknown_has_no_tradeoff():
    assert get_tradeoff(ComponentType.UNKNOWN) is None


def test_tradeoffs_for_returns_present_types_deduped_in_order():
    utils = [
        Utilization(component="api", type=ComponentType.APP_SERVER, load_per_sec=1.0,
                    ceiling_per_sec=2000.0, utilization=0.1, estimated=True),
        Utilization(component="db", type=ComponentType.RELATIONAL_DB, load_per_sec=1.0,
                    ceiling_per_sec=1000.0, utilization=0.1, estimated=True),
        Utilization(component="db2", type=ComponentType.RELATIONAL_DB, load_per_sec=1.0,
                    ceiling_per_sec=1000.0, utilization=0.1, estimated=True),
        Utilization(component="mystery", type=ComponentType.UNKNOWN, load_per_sec=0.0,
                    ceiling_per_sec=None, utilization=None, estimated=False),
    ]
    report = CapacityReport(bottleneck="api", max_dau=100, utilizations=utils,
                            assumptions=[], confidence="high", notes=[])
    rows = tradeoffs_for(report)
    assert [r["type"] for r in rows] == ["app_server", "relational_db"]  # deduped, in order, UNKNOWN skipped
    assert "cost" in rows[0] and "move" in rows[0]


def test_no_em_dash_in_kb():
    for to in TRADEOFFS.values():
        for field in (to.when_fine, to.gain, to.cost, to.move, to.source):
            assert "—" not in field
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tradeoffs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'brok.tradeoffs'`

- [ ] **Step 3: Write `brok/tradeoffs.py`**

```python
# brok/tradeoffs.py
from __future__ import annotations

from pydantic import BaseModel

from brok.models import CapacityReport, ComponentType


class Tradeoff(BaseModel):
    when_fine: str
    gain: str
    cost: str
    move: str  # the move when you outgrow it
    source: str


TRADEOFFS: dict[ComponentType, Tradeoff] = {
    ComponentType.RELATIONAL_DB: Tradeoff(
        when_fine="under about 500 writes/sec and a dataset one machine can hold",
        gain="simple, transactional, strong consistency",
        cost="a single point of failure, writes cap near 1k/sec, scales only by a bigger box",
        move="read-heavy: add read replicas (accept replication lag). write-bound: shard by a "
             "high cardinality key (lose cross-shard joins, gain ops work). spiky writes: put a "
             "queue in front (adds latency).",
        source="Hello Interview (sharding); Postgres write benchmarks",
    ),
    ComponentType.CACHE: Tradeoff(
        when_fine="read-heavy traffic where slightly stale data is acceptable",
        gain="cuts read latency and offloads the database",
        cost="adds a cache invalidation problem and a staleness window; long TTL means stale, "
             "short TTL means more database hits",
        move="if the hit rate is low the cache is not earning its keep; if you need fresh data, "
             "shorten the TTL or invalidate on write",
        source="Azure caching guidance",
    ),
    ComponentType.QUEUE: Tradeoff(
        when_fine="spiky or write-heavy workloads that tolerate async processing",
        gain="smooths spikes, decouples producers from consumers, turns sync writes async",
        cost="adds end to end latency, plus at-least-once delivery and ordering concerns",
        move="size the consumers to drain faster than the arrival rate, or the queue grows "
             "unbounded",
        source="System Design Primer (message queues)",
    ),
    ComponentType.CDN: Tradeoff(
        when_fine="static or cacheable read content served to many users",
        gain="massive read fan-out, served close to the user",
        cost="useless for writes or per-user dynamic data; cache purge complexity",
        move="never route writes through it; for dynamic data use a cache or an edge function",
        source="CDN fundamentals",
    ),
    ComponentType.APP_SERVER: Tradeoff(
        when_fine="almost always, as a stateless app tier",
        gain="scales out horizontally behind a load balancer, cheaply",
        cost="a single instance caps at low thousands of req/sec; state must live elsewhere",
        move="add instances behind the load balancer; keep the handlers stateless",
        source="horizontal scaling fundamentals",
    ),
    ComponentType.OBJECT_STORE: Tradeoff(
        when_fine="large blobs (images, video, files) and high-throughput reads",
        gain="cheap, durable, effectively unlimited capacity",
        cost="higher per-request latency than memory or a database; some stores list "
             "eventually consistently",
        move="put a CDN in front of the hot read paths",
        source="object storage fundamentals",
    ),
    ComponentType.LOAD_BALANCER: Tradeoff(
        when_fine="any multi-instance tier",
        gain="distributes load, enables horizontal scale and failover",
        cost="itself a single point of failure if not redundant; adds a network hop",
        move="run it redundant, or use a managed balancer",
        source="load balancing fundamentals",
    ),
}


def get_tradeoff(t: ComponentType) -> Tradeoff | None:
    return TRADEOFFS.get(t)


def tradeoffs_for(report: CapacityReport) -> list[dict]:
    rows: list[dict] = []
    seen: set[ComponentType] = set()
    for u in report.utilizations:
        if u.type in seen:
            continue
        to = get_tradeoff(u.type)
        if to is None:
            continue
        seen.add(u.type)
        rows.append({"type": u.type.value, **to.model_dump()})
    return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tradeoffs.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add brok/tradeoffs.py tests/test_tradeoffs.py
git commit -m "feat: curated trade-off knowledge base"
```

---

### Task 2: Surface trade-offs in the result and the roast

**Files:**
- Modify: `brok/pipeline.py`
- Modify: `brok/voice.py`
- Test: `tests/test_tradeoff_surface.py`

**Interfaces:**
- Consumes: `tradeoffs_for`, `render_roast`, `build_result`.
- Produces:
  - `build_result` returns an additional `"tradeoffs": tradeoffs_for(report)` key (and `_empty_result` gets `"tradeoffs": []`).
  - `render_roast` gains a closing section: when there are trade-offs, append a blank line, a `THE TRADE-OFFS YOU ARE MAKING:` header, and per type a two-line entry: `  {type}: fine {when_fine}.` and `    cost: {cost}. outgrow it: {move}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tradeoff_surface.py
from brok.models import Component, ComponentType, DesignGraph
from brok.pipeline import build_result, review_from_components
from brok.voice import render_roast
from brok.models import CapacityReport, Utilization


def _graph():
    return DesignGraph(components=[
        Component(name="api", type=ComponentType.APP_SERVER),
        Component(name="db", type=ComponentType.RELATIONAL_DB),
    ])


def test_build_result_includes_tradeoffs():
    res = build_result(_graph(), {"dau": 2_000_000})
    assert "tradeoffs" in res
    types = [t["type"] for t in res["tradeoffs"]]
    assert "app_server" in types and "relational_db" in types


def test_empty_result_has_tradeoffs_key():
    res = review_from_components([])
    assert res["tradeoffs"] == []


def test_render_roast_has_tradeoff_section():
    utils = [Utilization(component="db", type=ComponentType.RELATIONAL_DB,
                         load_per_sec=8000.0, ceiling_per_sec=1000.0, utilization=8.0,
                         estimated=True)]
    report = CapacityReport(bottleneck="db", max_dau=12000, utilizations=utils,
                            assumptions=[], confidence="high", notes=[])
    card = render_roast(report)
    assert "TRADE-OFFS YOU ARE MAKING" in card
    assert "single point of failure" in card  # from the relational_db cost
    assert "—" not in card


def test_render_roast_no_tradeoff_section_when_none():
    report = CapacityReport(bottleneck=None, max_dau=None, utilizations=[],
                            assumptions=[], confidence="low", notes=[])
    assert "TRADE-OFFS YOU ARE MAKING" not in render_roast(report)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tradeoff_surface.py -v`
Expected: FAIL (`tradeoffs` not in result / section missing)

- [ ] **Step 3: Update `brok/voice.py`** (append the section to `render_roast`)

Add the import at the top of `brok/voice.py`:

```python
from brok.tradeoffs import tradeoffs_for
```

Then, inside `render_roast`, just before the final `return "\n".join(lines)`, insert:

```python
    tos = tradeoffs_for(report)
    if tos:
        lines.append("")
        lines.append("THE TRADE-OFFS YOU ARE MAKING:")
        for to in tos:
            lines.append(f"  {to['type']}: fine {to['when_fine']}.")
            lines.append(f"    cost: {to['cost']}. outgrow it: {to['move']}")
```

- [ ] **Step 4: Update `brok/pipeline.py`** (add `tradeoffs` to both result shapes)

Add the import near the top:

```python
from brok.tradeoffs import tradeoffs_for
```

In `build_result`, add the `tradeoffs` key:

```python
def build_result(graph: DesignGraph, traffic: dict | None = None) -> dict:
    resolved, assumptions = resolve_nfrs(traffic)
    confidence = "low" if assumptions else "high"
    report = analyze_capacity(graph, resolved, assumptions, confidence)
    return {
        **report.model_dump(mode="json"),
        "report_text": render_report(report),
        "roast_text": render_roast(report),
        "tradeoffs": tradeoffs_for(report),
    }
```

In `_empty_result`, add `"tradeoffs": []`:

```python
def _empty_result() -> dict:
    return {
        "bottleneck": None, "max_dau": None, "utilizations": [],
        "assumptions": [], "confidence": "low", "notes": [],
        "report_text": _NO_COMPONENTS_TEXT,
        "roast_text": _NO_COMPONENTS_TEXT,
        "tradeoffs": [],
    }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_tradeoff_surface.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Run the full suite (gate)**

Run: `pytest -q`
Expected: PASS (all green; existing tests untouched).

- [ ] **Step 7: Commit**

```bash
git add brok/pipeline.py brok/voice.py tests/test_tradeoff_surface.py
git commit -m "feat: surface trade-offs in result and roast card"
```

---

### Task 3: Trigger, the sharpened tool descriptions + a companion skill

**Files:**
- Modify: `brok/server.py`
- Create: `skill/SKILL.md`
- Test: `tests/test_triggers.py`

**Interfaces:**
- Consumes: the two MCP tools.
- Produces:
  - Rewritten docstrings on `review_architecture` and `review_components` that lead with the trigger moments (designing, scaling, reviewing a system, choosing or changing a datastore/cache/queue) and the value (grounded capacity numbers + trade-offs), keeping the existing param + return guidance.
  - `skill/SKILL.md`: a small Claude Code skill instructing CC to consult Brok when making an architecture or scaling decision.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_triggers.py
import os
import brok.server as server


def test_review_architecture_description_names_trigger_moments():
    doc = server.review_architecture.__doc__.lower()
    assert "scal" in doc          # scaling / scale
    assert "design" in doc
    assert "trade-off" in doc or "tradeoff" in doc


def test_review_components_description_names_trigger_moments():
    doc = server.review_components.__doc__.lower()
    assert "design" in doc or "scal" in doc
    assert "component" in doc


def test_skill_file_exists_and_triggers_on_design():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skill", "SKILL.md")
    text = open(path, encoding="utf-8").read().lower()
    assert "brok" in text
    assert "scal" in text and "design" in text
    assert "—" not in open(path, encoding="utf-8").read()  # no em dash in shipped copy
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_triggers.py -v`
Expected: FAIL (skill file missing / description lacks the trigger words)

- [ ] **Step 3: Rewrite the docstrings in `brok/server.py`**

Replace the `review_architecture` docstring with:

```python
    """Estimate a system's capacity, find its bottleneck, and surface the trade-offs of its
    design choices. Use this when designing, scaling, or reviewing a system, or when choosing
    or changing a datastore, cache, or queue, so you decide with grounded numbers and known
    trade-offs instead of guessing.

    How to use this (for the calling assistant):
    1. If the project has a docker-compose.yml, read it and pass its full contents as compose_yaml.
    2. Ask the user for their expected scale and pass expected_dau (and read_write_ratio if known).
       Without expected_dau the result assumes 100k users and is reported as low confidence.
    3. Prefer report["roast_text"] as the headline to show the user (Brok's voice); use the
       structured fields and report["tradeoffs"] to reason about the design.

    Returns a dict: bottleneck, max_dau, confidence, assumptions, utilizations, notes,
    tradeoffs (the grounded pros, cons, and next move for each component), report_text, roast_text.
    """
```

Replace the `review_components` docstring with:

```python
    """Estimate capacity and surface design trade-offs from a structured component list. Use this
    when designing or scaling a system and there is no docker-compose: infer the components
    yourself from the user's description or code and pass them.

    Pass components as a list of {"name", "type"} dicts. Valid types: relational_db, cache, queue,
    cdn, app_server, object_store, load_balancer. Any other type is reported as not estimated
    (Brok will not guess). Pass expected_dau for a high-confidence result. Prefer roast_text as the
    headline; use the structured fields and tradeoffs to reason. Returns the same dict shape as
    review_architecture.
    """
```

(Do not change the tool bodies or signatures.)

- [ ] **Step 4: Write `skill/SKILL.md`**

```markdown
---
name: brok-design-check
description: Use when designing, scaling, or reviewing a system's architecture, or when choosing or changing a datastore, cache, or queue. Calls the Brok MCP for grounded capacity numbers and design trade-offs.
---

# Brok design check

When you are about to make or finalize an architecture or scaling decision, do not rely on memory for the numbers. Consult Brok first.

## When to call Brok

Call the Brok MCP (`review_architecture` for a docker-compose, `review_components` for a described or inferred stack) whenever the task involves:

- designing a backend or service from scratch,
- a question about whether a design will scale ("will this hold", "how many users"),
- choosing or changing a datastore, cache, queue, or load balancer,
- reviewing an existing architecture.

## How to use the result

- Always pass the expected scale (`expected_dau`, and `read_write_ratio` if known). Without it, the verdict is a low-confidence guess.
- Show the user `roast_text` as the headline.
- Read `tradeoffs` before recommending a change: it gives the grounded gain, cost, and next move for each component, which is more reliable than recalling it from memory.
- If Brok abstains or flags low confidence, ask the user for the missing numbers rather than guessing.

Brok is deterministic and grounded in cited limits. Treat its numbers and trade-offs as the source of truth for capacity decisions, and let it stop you from shipping a design that quietly falls over.
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_triggers.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Run the full suite (gate) + import check**

Run: `pytest -q` then `python -c "import brok.server"`
Expected: PASS (all green); `import brok.server` clean.

- [ ] **Step 7: Commit**

```bash
git add brok/server.py skill/SKILL.md tests/test_triggers.py
git commit -m "feat: trigger-focused tool descriptions + companion design-check skill"
```

---

## Manual Verification (after Task 3)

```python
import brok.server as s
r = s.review_architecture(
    "services:\n  api: { build: . }\n  db: { image: postgres:16 }\n  cache: { image: redis:7 }\n",
    expected_dau=2_000_000)
print(r["roast_text"])      # now ends with THE TRADE-OFFS YOU ARE MAKING
print(r["tradeoffs"])       # structured pros/cons/move per component type
print(s.review_architecture.__doc__[:120])  # leads with the trigger moments
```

Confirm: the roast card now teaches the trade-offs (per component: when it is fine, its cost, the move when you outgrow it), the structured `tradeoffs` list is present, and the descriptions name the design/scaling trigger moments. No em dashes anywhere.

---

## Self-Review Notes (author)

- **Goal coverage:** equip CC with trade-offs it lacks (Task 1 KB), deliver them at decision time (Task 2 surface in result + roast), and make CC actually call Brok (Task 3 trigger-focused descriptions + skill). Maps directly to the user's four questions: better data (KB), how to create trade-offs (curated cited four-field entries), UX/features (surfaced + skill), and when CC calls it (descriptions name the trigger moments + the skill makes it a habit).
- **Simple + additive:** no engine refactor; new module + two additive render/dict changes + docstrings + one skill file. All prior tests stay green (capacity, benchmark, voice unchanged).
- **On-brand:** trade-offs are curated and cited (not model-generated), so Brok feeds CC vetted knowledge, more reliable than CC's recall. Determinism and the no-model property hold.
- **Placeholder scan:** none; every step ships real code/content + a real command.
- **Type consistency:** `Tradeoff`, `TRADEOFFS`, `get_tradeoff`, `tradeoffs_for` match across tasks; `build_result`/`_empty_result`/`render_roast` extended, not changed.
