# Sindri Usable MCP Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Sindri's MCP usable by Claude Code: let the caller pass the expected scale (so verdicts are high-confidence, not always assumed), accept a structured component list (so it works without a docker-compose), return structured output the assistant can reason over, and give the tools rich descriptions that tell the assistant how to use them.

**Architecture:** The caller (Claude Code) does the natural-language / code parsing and passes Sindri either a docker-compose string or a structured component list, plus optional traffic numbers. Sindri stays 100% deterministic (no embedded model). Tools return a JSON-serializable dict (the full capacity report fields + a human-readable `report_text`).

**Tech Stack:** Python 3.11+, `mcp` (FastMCP), `pydantic` v2, `pytest`. No model, no network. Builds on Plans 1-2.

## Global Constraints

- Python **3.11+**; Pydantic **v2**.
- **Deterministic, no model, no network** anywhere (including tests). The caller does any NL parsing; Sindri only consumes structured input.
- **Backward compatibility:** the existing `review(compose_yaml, nfrs=None) -> str` (used by Plan 1 tests) must keep returning the report text.
- Structured tool output must be **JSON-serializable** (use `model_dump(mode="json")` so enums become their string values).
- **No em dashes** in any user-facing report text.
- **Never crash:** unparseable / empty input returns a friendly structured result, not an exception.
- Commits: one per task, no co-author / AI-attribution trailer. (Repo git identity already configured: `Rudra Dudhat <contact.rdudhat@gmail.com>`.)

## Per-Task Gate (blocking, deterministic)

After a task's own test step goes green, run the full suite as the gate:

```bash
pytest -q
```

Pass condition: exit 0; every test passes (0 failed, 0 errored); no network/model. If red, stop and fix before the next task.

---

### Task 1: Structured review core + traffic builder

**Files:**
- Modify: `sindri/pipeline.py`
- Test: `tests/test_pipeline_core.py`

**Interfaces:**
- Consumes: `parse_compose`, `resolve_nfrs`, `analyze_capacity`, `render_report`, `DesignGraph`.
- Produces:
  - `build_result(graph: DesignGraph, traffic: dict | None = None) -> dict` — resolves NFRs (assume-and-state), sets confidence (`"low"` if any field was assumed else `"high"`), analyzes capacity, renders text. Returns `{**report.model_dump(mode="json"), "report_text": <text>}`.
  - `build_traffic(expected_dau: int | None, requests_per_user_per_day: int | None, read_write_ratio: float | None, payload_kb: float | None, peak_factor: float | None) -> dict | None` — assembles a traffic dict from the non-None args (mapping `expected_dau` -> `"dau"`); returns `None` if all args are `None`.
  - `review(compose_yaml: str, nfrs: dict | None = None) -> str` — unchanged public behavior (returns report text); now implemented via `build_result`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pipeline_core.py
from sindri.models import Component, ComponentType, DesignGraph
from sindri.pipeline import build_result, build_traffic, review

COMPOSE = """
services:
  api: { build: . }
  db: { image: postgres:16 }
"""


def _graph():
    return DesignGraph(components=[
        Component(name="api", type=ComponentType.APP_SERVER),
        Component(name="db", type=ComponentType.RELATIONAL_DB),
    ])


def test_build_result_returns_structured_plus_text():
    res = build_result(_graph(), {"dau": 5_000_000})
    assert "report_text" in res and isinstance(res["report_text"], str)
    assert "bottleneck" in res and "max_dau" in res and "confidence" in res
    # enums serialized to strings (json mode)
    assert all(isinstance(u["type"], str) for u in res["utilizations"])


def test_build_result_high_confidence_when_dau_provided_partial_still_low():
    # only dau provided: the other NFR fields are still assumed => low confidence,
    # but the dau assumption line must be gone and dau must be honored.
    res = build_result(_graph(), {"dau": 5_000_000})
    assert res["confidence"] == "low"
    assert all("daily active users" not in a for a in res["assumptions"])


def test_build_traffic_maps_and_drops_none():
    assert build_traffic(2_000_000, None, 4.0, None, None) == {"dau": 2_000_000, "read_write_ratio": 4.0}
    assert build_traffic(None, None, None, None, None) is None


def test_review_still_returns_text():
    out = review(COMPOSE)
    assert isinstance(out, str)
    assert "Sindri capacity review" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline_core.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_result'`

- [ ] **Step 3: Rewrite `sindri/pipeline.py`**

```python
# sindri/pipeline.py
from __future__ import annotations

from sindri.lenses.capacity import analyze_capacity
from sindri.models import DesignGraph
from sindri.nfr import resolve_nfrs
from sindri.parsers.compose import parse_compose
from sindri.report import render_report

_NO_COMPONENTS_TEXT = (
    "Sindri capacity review\n\n"
    "I couldn't find any components. Give me a docker-compose with services, "
    "or pass a component list."
)


def build_traffic(expected_dau, requests_per_user_per_day, read_write_ratio,
                  payload_kb, peak_factor) -> dict | None:
    traffic = {
        "dau": expected_dau,
        "requests_per_user_per_day": requests_per_user_per_day,
        "read_write_ratio": read_write_ratio,
        "payload_kb": payload_kb,
        "peak_factor": peak_factor,
    }
    traffic = {k: v for k, v in traffic.items() if v is not None}
    return traffic or None


def build_result(graph: DesignGraph, traffic: dict | None = None) -> dict:
    resolved, assumptions = resolve_nfrs(traffic)
    confidence = "low" if assumptions else "high"
    report = analyze_capacity(graph, resolved, assumptions, confidence)
    return {**report.model_dump(mode="json"), "report_text": render_report(report)}


def review(compose_yaml: str, nfrs: dict | None = None) -> str:
    graph = parse_compose(compose_yaml)
    if not graph.components:
        return _NO_COMPONENTS_TEXT
    return build_result(graph, nfrs)["report_text"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline_core.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Run the full suite (backward-compat check)**

Run: `pytest -q`
Expected: PASS (Plan 1's `tests/test_pipeline.py` still green — `review` unchanged).

- [ ] **Step 6: Commit**

```bash
git add sindri/pipeline.py tests/test_pipeline_core.py
git commit -m "feat: structured review core + traffic builder"
```

---

### Task 2: Compose + component entry functions

**Files:**
- Modify: `sindri/pipeline.py`
- Test: `tests/test_pipeline_entries.py`

**Interfaces:**
- Consumes: `build_result`, `parse_compose`, `Component`, `ComponentType`, `DesignGraph`, `_NO_COMPONENTS_TEXT`.
- Produces:
  - `review_from_compose(compose_yaml: str, traffic: dict | None = None) -> dict` — parses compose; if no components, returns a friendly empty result dict (`bottleneck=None, max_dau=None, utilizations=[], assumptions=[], confidence="low", notes=[], report_text=_NO_COMPONENTS_TEXT`); else `build_result`.
  - `review_from_components(components: list[dict], traffic: dict | None = None) -> dict` — each item is `{"name": str, "type": str}`; maps `type` via `ComponentType(value)` falling back to `UNKNOWN`; builds a `DesignGraph`; same empty handling; else `build_result`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pipeline_entries.py
from sindri.pipeline import review_from_compose, review_from_components

COMPOSE = """
services:
  api: { build: . }
  db: { image: postgres:16 }
"""


def test_compose_entry_honors_provided_dau():
    res = review_from_compose(COMPOSE, {"dau": 50_000_000})
    assert res["bottleneck"] is not None
    assert all("daily active users" not in a for a in res["assumptions"])


def test_compose_entry_empty_is_friendly():
    res = review_from_compose("::: not yaml :::")
    assert res["bottleneck"] is None
    assert "couldn't find any components" in res["report_text"].lower()


def test_components_entry_builds_graph():
    res = review_from_components(
        [{"name": "api", "type": "app_server"}, {"name": "db", "type": "relational_db"}],
        {"dau": 2_000_000})
    assert res["bottleneck"] in ("api", "db")
    assert "report_text" in res


def test_components_entry_unknown_type_abstains():
    res = review_from_components([{"name": "mystery", "type": "cassandra"}])
    # unknown component is not scored => no bottleneck fabricated
    assert res["bottleneck"] is None


def test_components_entry_empty_list_is_friendly():
    res = review_from_components([])
    assert res["bottleneck"] is None
    assert "couldn't find any components" in res["report_text"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline_entries.py -v`
Expected: FAIL with `ImportError: cannot import name 'review_from_compose'`

- [ ] **Step 3: Append to `sindri/pipeline.py`**

```python
# --- append to sindri/pipeline.py ---
from sindri.models import Component, ComponentType  # add to existing imports


def _empty_result() -> dict:
    return {
        "bottleneck": None, "max_dau": None, "utilizations": [],
        "assumptions": [], "confidence": "low", "notes": [],
        "report_text": _NO_COMPONENTS_TEXT,
    }


def review_from_compose(compose_yaml: str, traffic: dict | None = None) -> dict:
    graph = parse_compose(compose_yaml)
    if not graph.components:
        return _empty_result()
    return build_result(graph, traffic)


def review_from_components(components: list[dict], traffic: dict | None = None) -> dict:
    comps = []
    for c in components:
        try:
            ctype = ComponentType(c.get("type", ""))
        except ValueError:
            ctype = ComponentType.UNKNOWN
        comps.append(Component(name=str(c.get("name", "?")), type=ctype))
    graph = DesignGraph(components=comps)
    if not graph.components:
        return _empty_result()
    return build_result(graph, traffic)
```

(Move the `from sindri.models import Component, ComponentType, DesignGraph` import to the top of the file with the other imports; do not leave a mid-file import.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline_entries.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add sindri/pipeline.py tests/test_pipeline_entries.py
git commit -m "feat: compose + structured-component entry functions"
```

---

### Task 3: MCP tools — NFR passthrough, structured output, rich descriptions

**Files:**
- Modify: `sindri/server.py`
- Test: `tests/test_server_tools.py`

**Interfaces:**
- Consumes: `review_from_compose`, `review_from_components`, `build_traffic`.
- Produces (the MCP tool surface):
  - `review_architecture(compose_yaml: str, expected_dau: int | None = None, requests_per_user_per_day: int | None = None, read_write_ratio: float | None = None, payload_kb: float | None = None, peak_factor: float | None = None) -> dict`
  - `review_components(components: list[dict], expected_dau: int | None = None, requests_per_user_per_day: int | None = None, read_write_ratio: float | None = None, payload_kb: float | None = None, peak_factor: float | None = None) -> dict`
  - Both assemble traffic via `build_traffic` and delegate to the pipeline entry functions. Both carry rich docstrings (the docstring IS the calling assistant's instructions).
- Note for the implementer: FastMCP's `@mcp.tool()` leaves the wrapped function directly callable, so the tests call `review_architecture(...)` / `review_components(...)` as plain functions. If your installed `mcp` version does not preserve callability, instead test the delegated pipeline functions directly and assert `import sindri.server` succeeds; report which path you used.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server_tools.py
import sindri.server as server


def test_review_architecture_passthrough_dau_drops_assumption():
    res = server.review_architecture(
        "services:\n  api: { build: . }\n  db: { image: postgres:16 }\n",
        expected_dau=50_000_000)
    assert isinstance(res, dict)
    assert res["bottleneck"] is not None
    assert all("daily active users" not in a for a in res["assumptions"])
    assert "report_text" in res


def test_review_components_tool_builds_and_scores():
    res = server.review_components(
        [{"name": "api", "type": "app_server"}, {"name": "db", "type": "relational_db"}],
        expected_dau=2_000_000)
    assert res["bottleneck"] in ("api", "db")


def test_server_imports_clean():
    assert hasattr(server, "mcp")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_server_tools.py -v`
Expected: FAIL (review_architecture has no `expected_dau` kwarg yet / review_components missing)

- [ ] **Step 3: Rewrite `sindri/server.py`**

```python
# sindri/server.py
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from sindri.pipeline import build_traffic, review_from_components, review_from_compose

mcp = FastMCP("sindri")


@mcp.tool()
def review_architecture(
    compose_yaml: str,
    expected_dau: int | None = None,
    requests_per_user_per_day: int | None = None,
    read_write_ratio: float | None = None,
    payload_kb: float | None = None,
    peak_factor: float | None = None,
) -> dict:
    """Estimate the capacity of a system from its docker-compose and find the bottleneck.

    How to use this (for the calling assistant):
    1. If the project has a docker-compose.yml, read it and pass its full contents
       as compose_yaml.
    2. Ask the user for their expected scale and pass expected_dau (daily active
       users), plus read_write_ratio if known. Without expected_dau the result
       assumes 100k users and is reported as low confidence.
    3. Show the user `report_text`; use the structured fields to reason or compare.

    Returns a dict: bottleneck (component name or null), max_dau (int or null),
    confidence ('low'|'high'), assumptions (list of stated assumptions),
    utilizations (per-component load vs ceiling), notes, and report_text.
    """
    traffic = build_traffic(expected_dau, requests_per_user_per_day,
                            read_write_ratio, payload_kb, peak_factor)
    return review_from_compose(compose_yaml, traffic)


@mcp.tool()
def review_components(
    components: list[dict],
    expected_dau: int | None = None,
    requests_per_user_per_day: int | None = None,
    read_write_ratio: float | None = None,
    payload_kb: float | None = None,
    peak_factor: float | None = None,
) -> dict:
    """Estimate capacity from a structured component list (use when there is no
    docker-compose).

    How to use this (for the calling assistant): infer the components yourself from
    the user's description or code, and pass them as a list of {"name", "type"}
    dicts. Valid types: relational_db, cache, queue, cdn, app_server, object_store,
    load_balancer. Any other type string is reported as not-estimated (Sindri will
    not guess). Pass expected_dau for a high-confidence result.

    Returns the same dict shape as review_architecture.
    """
    traffic = build_traffic(expected_dau, requests_per_user_per_day,
                            read_write_ratio, payload_kb, peak_factor)
    return review_from_components(components, traffic)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_server_tools.py -v`
Expected: PASS (3 passed). If `@mcp.tool()` does not leave the functions callable in your `mcp` version, switch the first two tests to call `review_from_compose` / `review_from_components` with a `build_traffic(...)` argument instead, keep `test_server_imports_clean`, and note this in the report.

- [ ] **Step 5: Confirm the server imports**

Run: `python -c "import sindri.server; print('server import OK')"`
Expected: `server import OK`

- [ ] **Step 6: Run the full suite (gate)**

Run: `pytest -q`
Expected: PASS (all green).

- [ ] **Step 7: Commit**

```bash
git add sindri/server.py tests/test_server_tools.py
git commit -m "feat: MCP tools with NFR passthrough, structured output, rich descriptions"
```

---

## Manual Verification (after Task 3)

1. ```python
   import sindri.server as s
   r = s.review_architecture(
       "services:\n  api: { build: . }\n  db: { image: postgres:16 }\n  cache: { image: redis:7 }\n",
       expected_dau=2_000_000)
   print(r["bottleneck"], r["max_dau"], r["confidence"])
   print(r["report_text"])
   ```
2. Confirm: passing `expected_dau` honors the real scale (no DAU assumption line), the dict has both structured fields and `report_text`, and `review_components([...], expected_dau=...)` works with no compose file.

---

## Self-Review Notes (author)

- **Spec coverage (Plan 3 slice):** §6 input modes (Mode A compose + Mode B-as-structured-components, with the caller doing the NL parse so the core stays model-free), §9 tool surface (the two primary tools with NFR passthrough + structured output + rich descriptions). Deferred (named sequence): latency + cost lenses (now Plan 4), anti-pattern linter (Plan 5), roast narrator (Plan 6), and the remaining spec tools (`estimate_capacity`, `simulate_change`, `explain_finding`) as the surface grows.
- **Backward compatibility:** `review()` keeps returning text; Plan 1's `tests/test_pipeline.py` stays green (verified in Task 1 Step 5).
- **No model added:** the NL parse is the caller's job; Sindri consumes only structured input. Determinism preserved.
- **Placeholder scan:** none; every step has real code + a real command.
- **Type consistency:** `build_result`/`build_traffic`/`review_from_compose`/`review_from_components` signatures match across tasks and match server.py's calls; `model_dump(mode="json")` keeps the dict JSON-serializable for MCP.
