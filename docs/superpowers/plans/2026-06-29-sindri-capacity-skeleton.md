# Sindri Capacity Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a working Sindri MCP where `review_architecture(compose_yaml)` parses a docker-compose into a Design Graph, runs the deterministic capacity lens against a cited capability KB, and returns a verdict-first report with the bottleneck component and the max user capacity.

**Architecture:** Deterministic engine, no model. A config parser turns docker-compose into a typed Design Graph. An assume-and-state layer fills missing traffic numbers from archetype defaults. The capacity lens computes per-component load, compares it to cited KB ceilings, and reports the weakest link + max DAU. A plain-text renderer produces the verdict. An MCP tool wires it together.

**Tech Stack:** Python 3.11+, `mcp` (FastMCP), `pydantic` v2, `pyyaml`, `pytest`. No model, no network.

## Global Constraints

- Python **3.11+**; Pydantic **v2** for every model.
- **The deterministic core uses NO model and makes NO network calls.** (The roast narrator + prose parser are later plans.)
- **Cited KB + order-of-magnitude.** Every capability number is a range with a `source` string. Verdicts use the conservative (low) end of the range.
- **Abstain outside coverage.** A component type not in the KB is `UNKNOWN`; it is reported as "not estimated", never assigned a fabricated number.
- **Assume-and-state.** Missing traffic numbers are filled from defaults and the assumptions are returned and shown at the top of the report.
- **No em dashes (`—`) in user-facing report copy.** Use commas or periods.
- **Never crash.** Unparseable input returns a clear message, not an exception.
- Product name in user-facing strings is **Sindri**.
- Commits: one per task, no co-author / AI-attribution trailer. (Repo already configured with name `Rudra Dudhat`, email `contact.rdudhat@gmail.com`.)

## Per-Task Gate (blocking, deterministic)

After a task's own test step goes green, run the full suite as the gate:

```bash
pytest -q
```

Pass condition (all must hold): exit code 0; every test passes (0 failed, 0 errored); no network or model calls anywhere in the suite. If red, stop and fix before the next task.

---

### Task 1: Scaffold + Design Graph models

**Files:**
- Create: `pyproject.toml`
- Create: `sindri/__init__.py`
- Create: `sindri/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `ComponentType` enum: `RELATIONAL_DB, CACHE, QUEUE, CDN, APP_SERVER, OBJECT_STORE, LOAD_BALANCER, UNKNOWN`
  - `Component(name: str, type: ComponentType)`
  - `NFRs(dau: int, requests_per_user_per_day: int, read_write_ratio: float, payload_kb: float, peak_factor: float)`
  - `DesignGraph(components: list[Component], nfrs: NFRs | None = None)`
  - `Utilization(component: str, type: ComponentType, load_per_sec: float, ceiling_per_sec: float | None, utilization: float | None, estimated: bool)`
  - `CapacityReport(bottleneck: str | None, max_dau: int | None, utilizations: list[Utilization], assumptions: list[str], confidence: str, notes: list[str])`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "sindri"
version = "0.1.0"
description = "Sindri: an MCP that reviews architecture, estimates capacity, and roasts bad design decisions."
requires-python = ">=3.11"
dependencies = ["mcp>=1.2.0", "pydantic>=2.6", "pyyaml>=6.0"]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
addopts = "-q"
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_models.py
from sindri.models import (
    ComponentType, Component, NFRs, DesignGraph, Utilization, CapacityReport,
)


def test_component_holds_type():
    c = Component(name="orders-db", type=ComponentType.RELATIONAL_DB)
    assert c.type is ComponentType.RELATIONAL_DB


def test_nfrs_fields():
    n = NFRs(dau=100_000, requests_per_user_per_day=50, read_write_ratio=10.0,
             payload_kb=50.0, peak_factor=3.0)
    assert n.dau == 100_000


def test_design_graph_defaults_no_nfrs():
    g = DesignGraph(components=[Component(name="db", type=ComponentType.RELATIONAL_DB)])
    assert g.nfrs is None
    assert len(g.components) == 1


def test_capacity_report_round_trips():
    r = CapacityReport(bottleneck="db", max_dau=12_000, utilizations=[],
                       assumptions=["assumed 100k DAU"], confidence="low", notes=[])
    assert r.bottleneck == "db"
    assert r.max_dau == 12_000
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sindri'`

- [ ] **Step 4: Write `sindri/__init__.py`**

```python
# sindri/__init__.py
```

- [ ] **Step 5: Write `sindri/models.py`**

```python
# sindri/models.py
from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class ComponentType(str, Enum):
    RELATIONAL_DB = "relational_db"
    CACHE = "cache"
    QUEUE = "queue"
    CDN = "cdn"
    APP_SERVER = "app_server"
    OBJECT_STORE = "object_store"
    LOAD_BALANCER = "load_balancer"
    UNKNOWN = "unknown"


class Component(BaseModel):
    name: str
    type: ComponentType


class NFRs(BaseModel):
    dau: int
    requests_per_user_per_day: int
    read_write_ratio: float  # reads per write
    payload_kb: float
    peak_factor: float


class DesignGraph(BaseModel):
    components: list[Component] = Field(default_factory=list)
    nfrs: NFRs | None = None


class Utilization(BaseModel):
    component: str
    type: ComponentType
    load_per_sec: float
    ceiling_per_sec: float | None
    utilization: float | None
    estimated: bool


class CapacityReport(BaseModel):
    bottleneck: str | None
    max_dau: int | None
    utilizations: list[Utilization] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    confidence: str
    notes: list[str] = Field(default_factory=list)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS (4 passed)

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml sindri/__init__.py sindri/models.py tests/test_models.py
git commit -m "feat: scaffold + design graph models"
```

---

### Task 2: Capability KB (cited ranges)

**Files:**
- Create: `sindri/kb.py`
- Test: `tests/test_kb.py`

**Interfaces:**
- Consumes: `ComponentType`.
- Produces:
  - `Capability(write_low: float | None, write_high: float | None, read_low: float | None, read_high: float | None, source: str)`
  - `CAPABILITY_KB: dict[ComponentType, Capability]`
  - `get_capability(t: ComponentType) -> Capability | None` (returns `None` for types not in the KB, e.g. UNKNOWN)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_kb.py
from sindri.models import ComponentType
from sindri.kb import get_capability, CAPABILITY_KB


def test_relational_db_has_cited_conservative_write_ceiling():
    cap = get_capability(ComponentType.RELATIONAL_DB)
    assert cap is not None
    # conservative low end around ~1k writes/sec, with a source
    assert cap.write_low is not None and cap.write_low <= 1000
    assert cap.source  # non-empty citation


def test_cache_read_far_exceeds_db():
    db = get_capability(ComponentType.RELATIONAL_DB)
    cache = get_capability(ComponentType.CACHE)
    assert cache.read_low > db.read_low


def test_cdn_does_not_serve_writes():
    cdn = get_capability(ComponentType.CDN)
    assert cdn.write_low is None and cdn.write_high is None


def test_unknown_has_no_capability():
    assert get_capability(ComponentType.UNKNOWN) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_kb.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sindri.kb'`

- [ ] **Step 3: Write `sindri/kb.py`**

```python
# sindri/kb.py
from __future__ import annotations

from pydantic import BaseModel

from sindri.models import ComponentType


class Capability(BaseModel):
    write_low: float | None
    write_high: float | None
    read_low: float | None
    read_high: float | None
    source: str


# Conservative ranges, ops/sec, single instance. Verdicts use the LOW end.
CAPABILITY_KB: dict[ComponentType, Capability] = {
    ComponentType.RELATIONAL_DB: Capability(
        write_low=1000, write_high=1875, read_low=5000, read_high=10000,
        source="Postgres single-primary benchmarks: ~1.1k-1.9k w/s ceiling, "
               "plan change at 500+ (dev.to/haikasatryan PG write perf, 2025)",
    ),
    ComponentType.CACHE: Capability(
        write_low=80000, write_high=100000, read_low=100000, read_high=1000000,
        source="Redis benchmarks: ~100k ops/s single instance, 1M+ pipelined "
               "(redis.io optimization/benchmarks)",
    ),
    ComponentType.QUEUE: Capability(
        write_low=100000, write_high=1000000, read_low=100000, read_high=1000000,
        source="Kafka performance: ~millions msg/s per cluster "
               "(developer.confluent.io/learn/kafka-performance)",
    ),
    ComponentType.CDN: Capability(
        write_low=None, write_high=None, read_low=1000000, read_high=10000000,
        source="CDN: massive read fan-out; writes do not belong on a CDN.",
    ),
    ComponentType.APP_SERVER: Capability(
        write_low=2000, write_high=8000, read_low=2000, read_high=8000,
        source="Single app instance: low thousands RPS typical (order-of-magnitude).",
    ),
    ComponentType.OBJECT_STORE: Capability(
        write_low=3500, write_high=5500, read_low=5500, read_high=20000,
        source="Object store (S3-class) per-prefix: ~3.5k w/s, ~5.5k r/s "
               "(order-of-magnitude).",
    ),
    ComponentType.LOAD_BALANCER: Capability(
        write_low=10000, write_high=50000, read_low=10000, read_high=50000,
        source="L7 load balancer: tens of thousands RPS per node "
               "(order-of-magnitude).",
    ),
}


def get_capability(t: ComponentType) -> Capability | None:
    return CAPABILITY_KB.get(t)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_kb.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add sindri/kb.py tests/test_kb.py
git commit -m "feat: cited capability KB with conservative ranges"
```

---

### Task 3: NFR defaults (assume-and-state)

**Files:**
- Create: `sindri/nfr.py`
- Test: `tests/test_nfr.py`

**Interfaces:**
- Consumes: `NFRs`.
- Produces:
  - `DEFAULT_NFRS: NFRs` (dau=100_000, requests_per_user_per_day=50, read_write_ratio=10.0, payload_kb=50.0, peak_factor=3.0)
  - `resolve_nfrs(partial: dict | None) -> tuple[NFRs, list[str]]` — merges any provided fields over defaults; returns the resolved NFRs and a list of plain-English assumption strings for every field that fell back to a default.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_nfr.py
from sindri.nfr import resolve_nfrs, DEFAULT_NFRS


def test_no_input_uses_all_defaults_and_states_them():
    nfrs, assumptions = resolve_nfrs(None)
    assert nfrs == DEFAULT_NFRS
    assert any("100,000" in a or "100000" in a for a in assumptions)
    assert len(assumptions) == 5  # one per defaulted field


def test_provided_field_overrides_and_is_not_assumed():
    nfrs, assumptions = resolve_nfrs({"dau": 5_000_000})
    assert nfrs.dau == 5_000_000
    assert not any("daily" in a.lower() and "assum" in a.lower() for a in assumptions
                   if "5,000,000" not in a)
    # dau was provided, so there is no dau assumption line
    assert all("daily active users" not in a for a in assumptions)


def test_no_em_dash_in_assumptions():
    _, assumptions = resolve_nfrs(None)
    assert all("—" not in a for a in assumptions)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_nfr.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sindri.nfr'`

- [ ] **Step 3: Write `sindri/nfr.py`**

```python
# sindri/nfr.py
from __future__ import annotations

from sindri.models import NFRs

DEFAULT_NFRS = NFRs(
    dau=100_000, requests_per_user_per_day=50, read_write_ratio=10.0,
    payload_kb=50.0, peak_factor=3.0,
)

_LABELS = {
    "dau": "daily active users",
    "requests_per_user_per_day": "requests per user per day",
    "read_write_ratio": "reads per write",
    "payload_kb": "KB per request",
    "peak_factor": "peak-to-average traffic factor",
}


def resolve_nfrs(partial: dict | None) -> tuple[NFRs, list[str]]:
    partial = partial or {}
    merged = DEFAULT_NFRS.model_dump()
    assumptions: list[str] = []
    for field, default_value in DEFAULT_NFRS.model_dump().items():
        if field in partial and partial[field] is not None:
            merged[field] = partial[field]
        else:
            assumptions.append(f"Assumed {default_value:,} {_LABELS[field]}.")
    return NFRs(**merged), assumptions
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_nfr.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add sindri/nfr.py tests/test_nfr.py
git commit -m "feat: NFR defaults with assume-and-state"
```

---

### Task 4: docker-compose parser (deterministic)

**Files:**
- Create: `sindri/parsers/__init__.py`
- Create: `sindri/parsers/compose.py`
- Test: `tests/test_compose.py`

**Interfaces:**
- Consumes: `Component`, `ComponentType`, `DesignGraph`.
- Produces:
  - `IMAGE_TYPE_MAP: dict[str, ComponentType]` (substring keys, e.g. `"postgres" -> RELATIONAL_DB`)
  - `classify_image(image: str) -> ComponentType` (UNKNOWN if no substring matches)
  - `parse_compose(yaml_text: str) -> DesignGraph` (one Component per service; name = service name; type via image; services with no recognizable image become APP_SERVER if they have a `build:` key else UNKNOWN). Malformed YAML returns an empty `DesignGraph` (never raises).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_compose.py
from sindri.models import ComponentType
from sindri.parsers.compose import classify_image, parse_compose

COMPOSE = """
services:
  api:
    build: .
  db:
    image: postgres:16
  cache:
    image: redis:7
  edge:
    image: nginx:latest
"""


def test_classify_known_images():
    assert classify_image("postgres:16") is ComponentType.RELATIONAL_DB
    assert classify_image("redis:7") is ComponentType.CACHE
    assert classify_image("nginx:latest") is ComponentType.LOAD_BALANCER


def test_classify_unknown_image():
    assert classify_image("ghcr.io/acme/weird-thing:1") is ComponentType.UNKNOWN


def test_parse_compose_builds_graph():
    g = parse_compose(COMPOSE)
    by = {c.name: c.type for c in g.components}
    assert by["db"] is ComponentType.RELATIONAL_DB
    assert by["cache"] is ComponentType.CACHE
    assert by["edge"] is ComponentType.LOAD_BALANCER
    assert by["api"] is ComponentType.APP_SERVER  # has build:, no known image


def test_malformed_yaml_returns_empty_graph_not_crash():
    g = parse_compose("::: not yaml :::")
    assert g.components == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_compose.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sindri.parsers'`

- [ ] **Step 3: Write `sindri/parsers/__init__.py`**

```python
# sindri/parsers/__init__.py
```

- [ ] **Step 4: Write `sindri/parsers/compose.py`**

```python
# sindri/parsers/compose.py
from __future__ import annotations

import yaml

from sindri.models import Component, ComponentType, DesignGraph

IMAGE_TYPE_MAP: dict[str, ComponentType] = {
    "postgres": ComponentType.RELATIONAL_DB,
    "mysql": ComponentType.RELATIONAL_DB,
    "mariadb": ComponentType.RELATIONAL_DB,
    "redis": ComponentType.CACHE,
    "memcached": ComponentType.CACHE,
    "kafka": ComponentType.QUEUE,
    "rabbitmq": ComponentType.QUEUE,
    "nginx": ComponentType.LOAD_BALANCER,
    "haproxy": ComponentType.LOAD_BALANCER,
    "traefik": ComponentType.LOAD_BALANCER,
    "minio": ComponentType.OBJECT_STORE,
}


def classify_image(image: str) -> ComponentType:
    name = image.lower()
    for key, ctype in IMAGE_TYPE_MAP.items():
        if key in name:
            return ctype
    return ComponentType.UNKNOWN


def parse_compose(yaml_text: str) -> DesignGraph:
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError:
        return DesignGraph(components=[])
    if not isinstance(data, dict):
        return DesignGraph(components=[])
    services = data.get("services") or {}
    if not isinstance(services, dict):
        return DesignGraph(components=[])

    components: list[Component] = []
    for name, spec in services.items():
        spec = spec or {}
        image = spec.get("image") if isinstance(spec, dict) else None
        if image:
            ctype = classify_image(str(image))
        elif isinstance(spec, dict) and "build" in spec:
            ctype = ComponentType.APP_SERVER
        else:
            ctype = ComponentType.UNKNOWN
        components.append(Component(name=str(name), type=ctype))
    return DesignGraph(components=components)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_compose.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add sindri/parsers/__init__.py sindri/parsers/compose.py tests/test_compose.py
git commit -m "feat: deterministic docker-compose parser"
```

---

### Task 5: Capacity lens (the core math)

**Files:**
- Create: `sindri/lenses/__init__.py`
- Create: `sindri/lenses/capacity.py`
- Test: `tests/test_capacity.py`

**Interfaces:**
- Consumes: `DesignGraph`, `NFRs`, `ComponentType`, `Utilization`, `CapacityReport`, `get_capability`.
- Produces:
  - `peak_rps(nfrs: NFRs) -> float` = `nfrs.dau * nfrs.requests_per_user_per_day / 86400 * nfrs.peak_factor`
  - `analyze_capacity(graph: DesignGraph, nfrs: NFRs, assumptions: list[str], confidence: str) -> CapacityReport`
    - writes/sec = `peak_rps / (1 + read_write_ratio)`; reads/sec = `peak_rps - writes/sec`.
    - Assign load: a `RELATIONAL_DB` carries writes/sec on its write ceiling; reads go to a `CACHE` if one exists in the graph, else to the DB read ceiling. `APP_SERVER`/`LOAD_BALANCER` carry full `peak_rps`. `CDN`/`OBJECT_STORE`/`QUEUE` carry 0 in v1 (not on the modeled hot path).
    - For each component with a KB capability, `utilization = load / ceiling_low` (ceiling_low = write_low for write load, read_low for read load). `UNKNOWN`/no-KB components get `ceiling_per_sec=None, utilization=None, estimated=False` and a note.
    - Bottleneck = component with the highest utilization. `max_dau = int(nfrs.dau / bottleneck_utilization)` (load scales linearly with dau). If no component has a utilization, bottleneck is `None`, `max_dau` is `None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_capacity.py
from sindri.models import Component, ComponentType, DesignGraph, NFRs
from sindri.lenses.capacity import analyze_capacity, peak_rps


def _nfrs(dau):
    return NFRs(dau=dau, requests_per_user_per_day=50, read_write_ratio=10.0,
               payload_kb=50.0, peak_factor=3.0)


def test_peak_rps_math():
    # 100k * 50 / 86400 * 3 ~= 173.6
    assert round(peak_rps(_nfrs(100_000)), 1) == 173.6


def test_db_is_bottleneck_when_writes_exceed_ceiling():
    g = DesignGraph(components=[Component(name="db", type=ComponentType.RELATIONAL_DB)])
    # crank DAU so writes/sec >> 1000 ceiling
    rep = analyze_capacity(g, _nfrs(50_000_000), [], "high")
    assert rep.bottleneck == "db"
    assert rep.max_dau is not None and rep.max_dau < 50_000_000


def test_cache_absorbs_reads_off_the_db():
    g_no_cache = DesignGraph(components=[Component(name="db", type=ComponentType.RELATIONAL_DB)])
    g_cache = DesignGraph(components=[
        Component(name="db", type=ComponentType.RELATIONAL_DB),
        Component(name="cache", type=ComponentType.CACHE),
    ])
    nfrs = _nfrs(2_000_000)
    db_util_no_cache = next(u.utilization for u in analyze_capacity(g_no_cache, nfrs, [], "high").utilizations if u.component == "db")
    db_util_cache = next(u.utilization for u in analyze_capacity(g_cache, nfrs, [], "high").utilizations if u.component == "db")
    # with a cache, the db no longer carries reads, so its utilization is lower
    assert db_util_cache < db_util_no_cache


def test_unknown_component_is_not_fabricated():
    g = DesignGraph(components=[Component(name="mystery", type=ComponentType.UNKNOWN)])
    rep = analyze_capacity(g, _nfrs(100_000), [], "high")
    u = next(u for u in rep.utilizations if u.component == "mystery")
    assert u.ceiling_per_sec is None and u.utilization is None
    assert any("mystery" in n for n in rep.notes)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_capacity.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sindri.lenses'`

- [ ] **Step 3: Write `sindri/lenses/__init__.py`**

```python
# sindri/lenses/__init__.py
```

- [ ] **Step 4: Write `sindri/lenses/capacity.py`**

```python
# sindri/lenses/capacity.py
from __future__ import annotations

from sindri.kb import get_capability
from sindri.models import (
    CapacityReport, ComponentType, DesignGraph, NFRs, Utilization,
)


def peak_rps(nfrs: NFRs) -> float:
    avg = nfrs.dau * nfrs.requests_per_user_per_day / 86400
    return avg * nfrs.peak_factor


def analyze_capacity(graph: DesignGraph, nfrs: NFRs, assumptions: list[str],
                     confidence: str) -> CapacityReport:
    total = peak_rps(nfrs)
    writes = total / (1 + nfrs.read_write_ratio)
    reads = total - writes
    has_cache = any(c.type is ComponentType.CACHE for c in graph.components)

    utilizations: list[Utilization] = []
    notes: list[str] = []

    for comp in graph.components:
        cap = get_capability(comp.type)
        if cap is None:
            utilizations.append(Utilization(
                component=comp.name, type=comp.type, load_per_sec=0.0,
                ceiling_per_sec=None, utilization=None, estimated=False))
            notes.append(f"{comp.name} ({comp.type.value}) is outside the KB, "
                         f"so it was not estimated.")
            continue

        if comp.type is ComponentType.RELATIONAL_DB:
            load = writes if has_cache else writes + reads
            ceiling = cap.write_low if has_cache else min(
                v for v in [cap.write_low, cap.read_low] if v is not None)
        elif comp.type is ComponentType.CACHE:
            load = reads
            ceiling = cap.read_low
        elif comp.type in (ComponentType.APP_SERVER, ComponentType.LOAD_BALANCER):
            load = total
            ceiling = cap.read_low
        else:  # cdn, object_store, queue: not on the modeled hot path in v1
            load = 0.0
            ceiling = cap.read_low

        util = (load / ceiling) if ceiling else None
        utilizations.append(Utilization(
            component=comp.name, type=comp.type, load_per_sec=load,
            ceiling_per_sec=ceiling, utilization=util, estimated=True))

    scored = [u for u in utilizations if u.utilization is not None]
    if not scored:
        return CapacityReport(bottleneck=None, max_dau=None,
                              utilizations=utilizations, assumptions=assumptions,
                              confidence=confidence, notes=notes)

    worst = max(scored, key=lambda u: u.utilization)
    max_dau = int(nfrs.dau / worst.utilization) if worst.utilization > 0 else None
    return CapacityReport(
        bottleneck=worst.component, max_dau=max_dau, utilizations=utilizations,
        assumptions=assumptions, confidence=confidence, notes=notes)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_capacity.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add sindri/lenses/__init__.py sindri/lenses/capacity.py tests/test_capacity.py
git commit -m "feat: capacity lens with bottleneck + max-DAU math"
```

---

### Task 6: Report renderer (verdict-first, no em dashes)

**Files:**
- Create: `sindri/report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: `CapacityReport`, `Utilization`.
- Produces: `render_report(report: CapacityReport) -> str` — a plain-text, verdict-first report:
  - assumptions block at the top (each on its own line) when present;
  - the bottleneck line with its utilization and the max DAU when present;
  - an "everything fits" line when no bottleneck exceeds 100%;
  - a "not estimated" line listing components from `notes`;
  - contains no em dash.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_report.py
from sindri.models import CapacityReport, ComponentType, Utilization
from sindri.report import render_report


def _util(name, util):
    return Utilization(component=name, type=ComponentType.RELATIONAL_DB,
                       load_per_sec=8000.0, ceiling_per_sec=1000.0,
                       utilization=util, estimated=True)


def test_report_leads_with_assumptions():
    r = CapacityReport(bottleneck="db", max_dau=12_000, utilizations=[_util("db", 8.0)],
                       assumptions=["Assumed 100,000 daily active users."],
                       confidence="low", notes=[])
    out = render_report(r)
    assert "Assumed 100,000 daily active users." in out


def test_report_states_bottleneck_and_max_dau():
    r = CapacityReport(bottleneck="db", max_dau=12_000, utilizations=[_util("db", 8.0)],
                       assumptions=[], confidence="high", notes=[])
    out = render_report(r)
    assert "db" in out
    assert "12,000" in out


def test_report_says_fits_when_no_overload():
    r = CapacityReport(bottleneck="db", max_dau=5_000_000,
                       utilizations=[_util("db", 0.2)], assumptions=[],
                       confidence="high", notes=[])
    out = render_report(r)
    assert "fits" in out.lower() or "holds" in out.lower()


def test_report_lists_not_estimated_notes():
    r = CapacityReport(bottleneck=None, max_dau=None, utilizations=[],
                       assumptions=[], confidence="low",
                       notes=["mystery (unknown) is outside the KB, so it was not estimated."])
    out = render_report(r)
    assert "mystery" in out


def test_report_has_no_em_dash():
    r = CapacityReport(bottleneck="db", max_dau=12_000, utilizations=[_util("db", 8.0)],
                       assumptions=[], confidence="high", notes=[])
    assert "—" not in render_report(r)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_report.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sindri.report'`

- [ ] **Step 3: Write `sindri/report.py`**

```python
# sindri/report.py
from __future__ import annotations

from sindri.models import CapacityReport

_OVERLOAD = 1.0


def render_report(report: CapacityReport) -> str:
    lines: list[str] = ["Sindri capacity review", ""]

    if report.assumptions:
        lines.append("Assumptions (correct me and I will re-run):")
        lines.extend(f"  {a}" for a in report.assumptions)
        lines.append("")

    bottleneck_util = None
    for u in report.utilizations:
        if u.component == report.bottleneck and u.utilization is not None:
            bottleneck_util = u.utilization

    if report.bottleneck and bottleneck_util is not None and bottleneck_util > _OVERLOAD:
        over = round(bottleneck_util, 1)
        lines.append(f"BOTTLENECK: {report.bottleneck}")
        lines.append(f"  It is about {over}x over its safe ceiling.")
        if report.max_dau is not None:
            lines.append(f"  Max capacity as designed: ~{report.max_dau:,} daily users.")
        lines.append(f"  Confidence: {report.confidence}.")
    elif report.bottleneck and bottleneck_util is not None:
        lines.append("This design fits the assumed load.")
        if report.max_dau is not None:
            lines.append(f"  Headroom to about ~{report.max_dau:,} daily users "
                         f"before {report.bottleneck} is the wall.")
    else:
        lines.append("Nothing estimable was found on the hot path.")

    if report.notes:
        lines.append("")
        lines.append("Not estimated:")
        lines.extend(f"  {n}" for n in report.notes)

    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_report.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add sindri/report.py tests/test_report.py
git commit -m "feat: verdict-first plain-text report renderer"
```

---

### Task 7: Pipeline + MCP server

**Files:**
- Create: `sindri/pipeline.py`
- Create: `sindri/server.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `parse_compose`, `resolve_nfrs`, `analyze_capacity`, `render_report`.
- Produces:
  - `review(compose_yaml: str, nfrs: dict | None = None) -> str` — parse compose -> resolve NFRs (assume-and-state) -> set confidence (`"low"` if any assumption was made, else `"high"`) -> analyze capacity -> render. If the graph has no components, return a friendly message (never crash).
  - `sindri/server.py` exposes a FastMCP server with tool `review_architecture(compose_yaml: str) -> str` calling `review`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pipeline.py
from sindri.pipeline import review

COMPOSE = """
services:
  api:
    build: .
  db:
    image: postgres:16
"""


def test_review_end_to_end_flags_db_at_scale():
    out = review(COMPOSE, nfrs={"dau": 50_000_000})
    assert "BOTTLENECK: db" in out
    assert "daily users" in out


def test_review_states_assumptions_when_nfrs_missing():
    out = review(COMPOSE, nfrs=None)
    assert "Assumptions" in out
    assert "Confidence: low" in out


def test_review_empty_compose_is_friendly_not_crash():
    out = review("::: not yaml :::")
    assert "Sindri" in out
    assert "couldn't" in out.lower() or "no components" in out.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sindri.pipeline'`

- [ ] **Step 3: Write `sindri/pipeline.py`**

```python
# sindri/pipeline.py
from __future__ import annotations

from sindri.lenses.capacity import analyze_capacity
from sindri.nfr import resolve_nfrs
from sindri.parsers.compose import parse_compose
from sindri.report import render_report


def review(compose_yaml: str, nfrs: dict | None = None) -> str:
    graph = parse_compose(compose_yaml)
    if not graph.components:
        return ("Sindri capacity review\n\n"
                "I couldn't find any components. Give me a docker-compose with "
                "services, or describe your stack.")
    resolved, assumptions = resolve_nfrs(nfrs)
    confidence = "low" if assumptions else "high"
    report = analyze_capacity(graph, resolved, assumptions, confidence)
    return render_report(report)
```

- [ ] **Step 4: Write `sindri/server.py`**

```python
# sindri/server.py
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from sindri.pipeline import review

mcp = FastMCP("sindri")


@mcp.tool()
def review_architecture(compose_yaml: str) -> str:
    """Review a system architecture (from a docker-compose) for capacity:
    returns the bottleneck component and the max user capacity, with stated
    assumptions."""
    return review(compose_yaml)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_pipeline.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Run the full suite (gate)**

Run: `pytest -q`
Expected: PASS (all tasks green)

- [ ] **Step 7: Commit**

```bash
git add sindri/pipeline.py sindri/server.py tests/test_pipeline.py
git commit -m "feat: review pipeline + MCP server"
```

---

## Manual Verification (after Task 7)

1. `pip install -e ".[dev]"`
2. ```python
   from sindri.pipeline import review
   print(review("""
   services:
     api: { build: . }
     db: { image: postgres:16 }
     cache: { image: redis:7 }
   """, nfrs={"dau": 2000000}))
   ```
3. Confirm: a verdict-first report, the bottleneck named, a max-DAU number, assumptions stated, no em dashes, and no model/network calls.

---

## Self-Review Notes (author)

- **Spec coverage (Plan 1 slice):** Design Graph (T1), cited KB + ranges + order-of-magnitude low-end (T2), assume-and-state (T3), deterministic config parsing guardrail (T4), capacity lens + bottleneck + max-DAU (T5), verdict-first report + no-em-dash (T6), `review_architecture` MCP tool + never-crash (T7). Abstain-outside-coverage is enforced in T5 (UNKNOWN -> not estimated) and surfaced in T6. Deferred to later plans (explicitly out of Plan 1): latency + cost lenses, anti-pattern linter, roast narrator + confidence-gated voice + show-graph-back, prose/extra parsers, closed-loop simulate_change, golden-set validation + benchmarks. These are the named plan sequence, not gaps.
- **Confidence is coarse in Plan 1** (`"low"` if any assumption, else `"high"`); the full confidence-gating (soften where the verdict hinges on a guess) lands with the roast narrator in Plan 5. Noted, not a gap.
- **Placeholder scan:** none; every step has real code + a real command.
- **Type consistency:** `ComponentType`, `Component`, `NFRs`, `DesignGraph`, `Utilization`, `CapacityReport` names/fields match across T1->T7; `parse_compose`/`resolve_nfrs`/`analyze_capacity`/`render_report`/`review` signatures consistent with their consumers.
