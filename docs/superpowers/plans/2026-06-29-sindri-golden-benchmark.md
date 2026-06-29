# Sindri Golden-Set Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a deterministic benchmark harness + a curated golden set that measures whether Sindri's capacity engine is internally consistent with its cited ceilings, behaves correctly (abstains, does not cry wolf, flags overload), and is honest about out-of-model cases.

**Architecture:** A `GoldenCase` model encodes each scenario (components + NFRs + expected outcome + provenance). A curated `GOLDEN_CASES` list holds consistency, behavior, and out-of-model cases. A deterministic scorer compares Sindri's `analyze_capacity` output to each case's expectation; an aggregator computes the §3.1 metrics. A runner prints a scorecard and a benchmark test asserts the acceptance thresholds on the scored cases.

**Tech Stack:** Python 3.11+, `pydantic` v2, `pytest`. No model, no network. Builds on Plan 1 (`sindri.models`, `sindri.kb`, `sindri.lenses.capacity`).

## Global Constraints

- Python **3.11+**; Pydantic **v2**.
- **Deterministic, no model, no network** anywhere (including the benchmark itself).
- **Honest scope:** the benchmark validates internal consistency + behavior, NOT accuracy against multi-instance production scale (Sindri v1 is single-instance). Out-of-model cases are documented, not counted toward accuracy.
- **Anti-circularity:** each case's `expected_*` is derived from an external source (a cited ceiling or a documented bottleneck), NOT from running Sindri. Provenance lives in `source_url` + `note`.
- **Citeability is a hard gate:** every scored (estimated) component must resolve to a KB entry with a non-empty `source`.
- **No em dashes** in the scorecard output.
- Commits: one per task, no co-author / AI-attribution trailer. (Repo git identity already configured: `Rudra Dudhat <contact.rdudhat@gmail.com>`.)

## Per-Task Gate (blocking, deterministic)

After a task's own test step goes green, run the full suite as the gate:

```bash
pytest -q
```

Pass condition: exit 0; every test passes (0 failed, 0 errored); no network/model. If red, stop and fix before the next task.

---

### Task 1: GoldenCase model + graph builder

**Files:**
- Create: `sindri/benchmark/__init__.py`
- Create: `sindri/benchmark/golden.py`
- Test: `tests/test_golden_model.py`

**Interfaces:**
- Consumes: `Component`, `ComponentType`, `DesignGraph`, `NFRs` from `sindri.models`.
- Produces:
  - `GoldenCase(name: str, source_url: str, category: str, components: list[tuple[str, str]], nfrs: dict, expected_bottleneck_type: str | None, expected_capacity_dau: int | None, expect_overload: bool, scored_for_accuracy: bool, note: str)`
    - `category` is one of `"consistency"`, `"behavior"`, `"out_of_model"`.
    - `components` is a list of `(name, component_type_value)` pairs; `component_type_value` is a `ComponentType` value string (e.g. `"relational_db"`).
  - `GoldenCase.to_graph() -> DesignGraph` (builds components; unknown type strings map to `ComponentType.UNKNOWN`).
  - `GoldenCase.to_nfrs() -> NFRs` (`NFRs(**self.nfrs)`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_golden_model.py
from sindri.models import ComponentType
from sindri.benchmark.golden import GoldenCase


def _case(**kw):
    base = dict(
        name="x", source_url="http://example.com", category="consistency",
        components=[("app", "app_server"), ("db", "relational_db")],
        nfrs={"dau": 500000, "requests_per_user_per_day": 50,
              "read_write_ratio": 10.0, "payload_kb": 50.0, "peak_factor": 3.0},
        expected_bottleneck_type="relational_db", expected_capacity_dau=576000,
        expect_overload=False, scored_for_accuracy=True, note="n")
    base.update(kw)
    return GoldenCase(**base)


def test_to_graph_maps_types():
    g = _case().to_graph()
    by = {c.name: c.type for c in g.components}
    assert by["db"] is ComponentType.RELATIONAL_DB
    assert by["app"] is ComponentType.APP_SERVER


def test_unknown_type_string_maps_to_unknown():
    g = _case(components=[("mystery", "cassandra")]).to_graph()
    assert g.components[0].type is ComponentType.UNKNOWN


def test_to_nfrs_round_trips():
    n = _case().to_nfrs()
    assert n.dau == 500000 and n.read_write_ratio == 10.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_golden_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sindri.benchmark'`

- [ ] **Step 3: Write `sindri/benchmark/__init__.py`**

```python
# sindri/benchmark/__init__.py
```

- [ ] **Step 4: Write `sindri/benchmark/golden.py`** (the GoldenCase model only; the curated list comes in Task 2)

```python
# sindri/benchmark/golden.py
from __future__ import annotations

from pydantic import BaseModel

from sindri.models import Component, ComponentType, DesignGraph, NFRs


class GoldenCase(BaseModel):
    name: str
    source_url: str
    category: str  # "consistency" | "behavior" | "out_of_model"
    components: list[tuple[str, str]]
    nfrs: dict
    expected_bottleneck_type: str | None
    expected_capacity_dau: int | None
    expect_overload: bool
    scored_for_accuracy: bool
    note: str

    def to_graph(self) -> DesignGraph:
        comps = []
        for name, type_value in self.components:
            try:
                ctype = ComponentType(type_value)
            except ValueError:
                ctype = ComponentType.UNKNOWN
            comps.append(Component(name=name, type=ctype))
        return DesignGraph(components=comps)

    def to_nfrs(self) -> NFRs:
        return NFRs(**self.nfrs)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_golden_model.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add sindri/benchmark/__init__.py sindri/benchmark/golden.py tests/test_golden_model.py
git commit -m "feat: GoldenCase model + graph/nfrs builders"
```

---

### Task 2: Curated golden set

**Files:**
- Modify: `sindri/benchmark/golden.py` (append `GOLDEN_CASES`)
- Test: `tests/test_golden_cases.py`

**Interfaces:**
- Consumes: `GoldenCase`.
- Produces: `GOLDEN_CASES: list[GoldenCase]` — 7 curated cases. Each consistency case's `expected_capacity_dau` is derived from an external cited ceiling divided by the per-user load implied by its NFRs (see `note`), NOT from running Sindri.

**Provenance note (do not skip):** the three consistency capacities are derived by hand from the KB's cited ceilings:
- per-second peak load = `dau * requests_per_user_per_day / 86400 * peak_factor`.
- A no-cache `relational_db` carries the full peak at ceiling 1000 (Postgres cited low end). Wall DAU = `1000 * 86400 / (requests_per_user_per_day * peak_factor)`. For rpd=50, peak=3: `1000*86400/150 = 576000`.
- An `app_server` (ceiling 2000) carrying full peak: wall DAU = `2000*86400/150 = 1152000`.
- A write-heavy `relational_db` behind a cache carries `peak/(1+rw)` writes at ceiling 1000; for rw=0.5, rpd=50, peak=3: writes = peak/1.5, wall DAU = `1000*1.5*86400/150 = 864000`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_golden_cases.py
from sindri.benchmark.golden import GOLDEN_CASES


def test_has_all_three_categories():
    cats = {c.category for c in GOLDEN_CASES}
    assert {"consistency", "behavior", "out_of_model"} <= cats


def test_every_case_is_cited():
    assert all(c.source_url.startswith("http") for c in GOLDEN_CASES)
    assert all(c.note for c in GOLDEN_CASES)


def test_consistency_cases_have_expected_outcomes():
    cons = [c for c in GOLDEN_CASES if c.category == "consistency"]
    assert len(cons) >= 3
    assert all(c.scored_for_accuracy and c.expected_capacity_dau for c in cons)


def test_out_of_model_cases_not_scored_for_accuracy():
    oom = [c for c in GOLDEN_CASES if c.category == "out_of_model"]
    assert len(oom) >= 2
    assert all(not c.scored_for_accuracy for c in oom)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_golden_cases.py -v`
Expected: FAIL with `ImportError: cannot import name 'GOLDEN_CASES'`

- [ ] **Step 3: Append `GOLDEN_CASES` to `sindri/benchmark/golden.py`**

```python
# --- append to sindri/benchmark/golden.py ---

GOLDEN_CASES: list[GoldenCase] = [
    # ---- consistency: pipeline must reproduce the cited ceilings ----
    GoldenCase(
        name="single-postgres-no-cache-write-wall",
        source_url="https://dev.to/haikasatryan/postgresql-write-performance-what-the-benchmarks-wont-tell-you-mm7",
        category="consistency",
        components=[("app", "app_server"), ("db", "relational_db")],
        nfrs={"dau": 500000, "requests_per_user_per_day": 50,
              "read_write_ratio": 10.0, "payload_kb": 50.0, "peak_factor": 3.0},
        expected_bottleneck_type="relational_db",
        expected_capacity_dau=576000,
        expect_overload=False,
        scored_for_accuracy=True,
        note="No cache: Postgres carries all traffic at the cited ~1k/s low end. "
             "Wall = 1000*86400/150 = 576000 DAU. Derived from the cited ceiling.",
    ),
    GoldenCase(
        name="app-tier-is-the-wall-with-cache",
        source_url="https://bytebytego.com/courses/system-design-interview/back-of-the-envelope-estimation",
        category="consistency",
        components=[("api", "app_server"), ("db", "relational_db"), ("cache", "cache")],
        nfrs={"dau": 2000000, "requests_per_user_per_day": 50,
              "read_write_ratio": 10.0, "payload_kb": 50.0, "peak_factor": 3.0},
        expected_bottleneck_type="app_server",
        expected_capacity_dau=1152000,
        expect_overload=True,
        scored_for_accuracy=True,
        note="Cache absorbs reads, so the single app instance (ceiling ~2k/s) is the "
             "wall before the DB. Wall = 2000*86400/150 = 1152000 DAU.",
    ),
    GoldenCase(
        name="write-heavy-db-wall-even-with-cache",
        source_url="https://en.wikipedia.org/wiki/Little's_law",
        category="consistency",
        components=[("api", "app_server"), ("db", "relational_db"), ("cache", "cache")],
        nfrs={"dau": 500000, "requests_per_user_per_day": 50,
              "read_write_ratio": 0.5, "payload_kb": 50.0, "peak_factor": 3.0},
        expected_bottleneck_type="relational_db",
        expected_capacity_dau=864000,
        expect_overload=False,
        scored_for_accuracy=True,
        note="Write-heavy (rw=0.5): a cache cannot save the write path, so the DB is "
             "the wall. Wall = 1000*1.5*86400/150 = 864000 DAU.",
    ),
    # ---- behavior: abstain, and do not cry wolf ----
    GoldenCase(
        name="abstain-on-unknown-only",
        source_url="https://modelcontextprotocol.io/",
        category="behavior",
        components=[("mystery", "cassandra")],
        nfrs={"dau": 100000, "requests_per_user_per_day": 50,
              "read_write_ratio": 10.0, "payload_kb": 50.0, "peak_factor": 3.0},
        expected_bottleneck_type=None,
        expected_capacity_dau=None,
        expect_overload=False,
        scored_for_accuracy=True,
        note="An all-unknown graph must abstain: no fabricated bottleneck.",
    ),
    GoldenCase(
        name="tiny-hobby-app-fits",
        source_url="https://bytebytego.com/courses/system-design-interview/back-of-the-envelope-estimation",
        category="behavior",
        components=[("app", "app_server"), ("db", "relational_db")],
        nfrs={"dau": 1000, "requests_per_user_per_day": 50,
              "read_write_ratio": 10.0, "payload_kb": 50.0, "peak_factor": 3.0},
        expected_bottleneck_type="relational_db",
        expected_capacity_dau=576000,
        expect_overload=False,
        scored_for_accuracy=False,
        note="A 1k-user app must NOT be roasted as overloaded. Do not cry wolf.",
    ),
    # ---- out of model: documented real systems Sindri v1 cannot fully judge ----
    GoldenCase(
        name="instagram-2011-volume-bound",
        source_url="https://read.engineerscodex.com/p/how-instagram-scaled-to-14-million",
        category="out_of_model",
        components=[("django", "app_server"), ("db", "relational_db"), ("memcache", "cache")],
        nfrs={"dau": 14000000, "requests_per_user_per_day": 10,
              "read_write_ratio": 10.0, "payload_kb": 50.0, "peak_factor": 2.0},
        expected_bottleneck_type=None,
        expected_capacity_dau=None,
        expect_overload=False,
        scored_for_accuracy=False,
        note="Instagram sharded Postgres at ~14M users due to DATA VOLUME + connection "
             "overhead + hot rows, at only ~115 writes/s. Throughput was fine, so Sindri "
             "correctly says 'fits'. The real wall is outside v1's throughput model.",
    ),
    GoldenCase(
        name="discord-message-store-hot-partition",
        source_url="https://discord.com/blog/how-discord-stores-trillions-of-messages",
        category="out_of_model",
        components=[("api", "app_server"), ("messages", "cassandra")],
        nfrs={"dau": 5000000, "requests_per_user_per_day": 200,
              "read_write_ratio": 5.0, "payload_kb": 1.0, "peak_factor": 3.0},
        expected_bottleneck_type=None,
        expected_capacity_dau=None,
        expect_overload=False,
        scored_for_accuracy=False,
        note="Discord's wall was a READ hot-partition on Cassandra (not in the KB, so "
             "Sindri abstains on it). Hot partitions are a Plan 4 anti-pattern, not a "
             "v1 throughput verdict.",
    ),
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_golden_cases.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add sindri/benchmark/golden.py tests/test_golden_cases.py
git commit -m "feat: curated golden set (consistency + behavior + out-of-model)"
```

---

### Task 3: Per-case scorer

**Files:**
- Create: `sindri/benchmark/scorer.py`
- Test: `tests/test_scorer.py`

**Interfaces:**
- Consumes: `GoldenCase`, `CapacityReport`, `Utilization`, `get_capability`, `ComponentType`.
- Produces:
  - `CaseResult(name: str, category: str, scored: bool, bottleneck_correct: bool | None, within_2x: bool | None, off_by_100x: bool, cited: bool, overload_correct: bool)`
  - `score_case(case: GoldenCase, report: CapacityReport) -> CaseResult`
    - `predicted_type` = the `ComponentType` value string of the component named `report.bottleneck` (look up in `report.utilizations`), or `None` if `report.bottleneck is None`.
    - `bottleneck_correct` = `predicted_type == case.expected_bottleneck_type` if `case.scored_for_accuracy` else `None`.
    - `within_2x`: if `case.scored_for_accuracy` and `case.expected_capacity_dau` and `report.max_dau`: `0.5*exp <= report.max_dau <= 2*exp`; else `None`.
    - `off_by_100x`: if both capacities present: `report.max_dau < exp/100 or report.max_dau > exp*100`; else `False`.
    - `cited` = every `estimated` utilization resolves to a KB capability with a non-empty `source`.
    - `overload` = `report` has a bottleneck whose utilization `> 1.0`. `overload_correct` = `overload == case.expect_overload`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_scorer.py
from sindri.models import CapacityReport, ComponentType, Utilization
from sindri.benchmark.golden import GoldenCase
from sindri.benchmark.scorer import score_case


def _case(**kw):
    base = dict(name="x", source_url="http://e.com", category="consistency",
                components=[("db", "relational_db")],
                nfrs={"dau": 1, "requests_per_user_per_day": 1, "read_write_ratio": 1.0,
                      "payload_kb": 1.0, "peak_factor": 1.0},
                expected_bottleneck_type="relational_db", expected_capacity_dau=576000,
                expect_overload=False, scored_for_accuracy=True, note="n")
    base.update(kw)
    return GoldenCase(**base)


def _report(bottleneck, max_dau, util):
    u = Utilization(component="db", type=ComponentType.RELATIONAL_DB,
                    load_per_sec=1.0, ceiling_per_sec=1000.0, utilization=util,
                    estimated=True)
    return CapacityReport(bottleneck=bottleneck, max_dau=max_dau, utilizations=[u],
                          assumptions=[], confidence="high", notes=[])


def test_correct_bottleneck_and_capacity():
    r = score_case(_case(), _report("db", 600000, 0.5))
    assert r.bottleneck_correct is True
    assert r.within_2x is True
    assert r.off_by_100x is False
    assert r.cited is True


def test_wrong_capacity_outside_2x():
    r = score_case(_case(), _report("db", 50000, 0.5))  # exp 576k, far under
    assert r.within_2x is False


def test_off_by_100x_flagged():
    r = score_case(_case(), _report("db", 100, 0.5))  # 5760x under
    assert r.off_by_100x is True


def test_abstain_case_correct_when_no_bottleneck():
    c = _case(expected_bottleneck_type=None, expected_capacity_dau=None)
    r = score_case(c, _report(None, None, None))
    assert r.bottleneck_correct is True


def test_overload_correct():
    c = _case(expect_overload=True)
    r = score_case(c, _report("db", 600000, 8.0))  # util > 1 => overloaded
    assert r.overload_correct is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_scorer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sindri.benchmark.scorer'`

- [ ] **Step 3: Write `sindri/benchmark/scorer.py`**

```python
# sindri/benchmark/scorer.py
from __future__ import annotations

from pydantic import BaseModel

from sindri.benchmark.golden import GoldenCase
from sindri.kb import get_capability
from sindri.models import CapacityReport


class CaseResult(BaseModel):
    name: str
    category: str
    scored: bool
    bottleneck_correct: bool | None
    within_2x: bool | None
    off_by_100x: bool
    cited: bool
    overload_correct: bool


def _predicted_type(report: CapacityReport) -> str | None:
    if report.bottleneck is None:
        return None
    for u in report.utilizations:
        if u.component == report.bottleneck:
            return u.type.value
    return None


def score_case(case: GoldenCase, report: CapacityReport) -> CaseResult:
    predicted = _predicted_type(report)

    bottleneck_correct: bool | None = None
    if case.scored_for_accuracy:
        bottleneck_correct = predicted == case.expected_bottleneck_type

    within_2x: bool | None = None
    off_by_100x = False
    exp = case.expected_capacity_dau
    got = report.max_dau
    if case.scored_for_accuracy and exp and got:
        within_2x = (0.5 * exp) <= got <= (2 * exp)
        off_by_100x = got < (exp / 100) or got > (exp * 100)

    cited = all(
        (get_capability(u.type) is not None and bool(get_capability(u.type).source))
        for u in report.utilizations if u.estimated
    )

    overload = any(
        u.component == report.bottleneck and u.utilization is not None and u.utilization > 1.0
        for u in report.utilizations
    )
    overload_correct = overload == case.expect_overload

    return CaseResult(
        name=case.name, category=case.category, scored=case.scored_for_accuracy,
        bottleneck_correct=bottleneck_correct, within_2x=within_2x,
        off_by_100x=off_by_100x, cited=cited, overload_correct=overload_correct,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_scorer.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add sindri/benchmark/scorer.py tests/test_scorer.py
git commit -m "feat: per-case benchmark scorer"
```

---

### Task 4: Aggregate + runner

**Files:**
- Create: `sindri/benchmark/runner.py`
- Test: `tests/test_runner.py`

**Interfaces:**
- Consumes: `GOLDEN_CASES`, `GoldenCase`, `CaseResult`, `score_case`, `analyze_capacity`.
- Produces:
  - `BenchmarkResult(results: list[CaseResult], bottleneck_accuracy: float, within_2x_rate: float, off_by_100x_count: int, citeability: float, overload_accuracy: float)`
  - `run_case(case: GoldenCase) -> CaseResult` — builds the graph + NFRs, calls `analyze_capacity(graph, nfrs, [], "high")`, scores.
  - `run_benchmark(cases: list[GoldenCase] | None = None) -> BenchmarkResult` — runs all (defaults to `GOLDEN_CASES`), aggregates. Rates are computed over the cases where the metric is non-null; `0.0`-safe if the denominator is empty (returns `1.0`).
  - `format_scorecard(result: BenchmarkResult) -> str` — a plain-text table, no em dashes.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_runner.py
from sindri.benchmark.golden import GoldenCase
from sindri.benchmark.runner import run_case, run_benchmark, format_scorecard


def _consistency_db_case():
    return GoldenCase(
        name="db-wall", source_url="http://e.com", category="consistency",
        components=[("app", "app_server"), ("db", "relational_db")],
        nfrs={"dau": 500000, "requests_per_user_per_day": 50, "read_write_ratio": 10.0,
              "payload_kb": 50.0, "peak_factor": 3.0},
        expected_bottleneck_type="relational_db", expected_capacity_dau=576000,
        expect_overload=False, scored_for_accuracy=True, note="n")


def test_run_case_reproduces_cited_db_wall():
    r = run_case(_consistency_db_case())
    assert r.bottleneck_correct is True
    assert r.within_2x is True   # ~576000 reproduced end-to-end
    assert r.cited is True


def test_run_benchmark_aggregates():
    res = run_benchmark([_consistency_db_case()])
    assert res.bottleneck_accuracy == 1.0
    assert res.within_2x_rate == 1.0
    assert res.off_by_100x_count == 0
    assert res.citeability == 1.0


def test_format_scorecard_has_no_em_dash():
    res = run_benchmark([_consistency_db_case()])
    assert "—" not in format_scorecard(res)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sindri.benchmark.runner'`

- [ ] **Step 3: Write `sindri/benchmark/runner.py`**

```python
# sindri/benchmark/runner.py
from __future__ import annotations

from pydantic import BaseModel

from sindri.benchmark.golden import GOLDEN_CASES, GoldenCase
from sindri.benchmark.scorer import CaseResult, score_case
from sindri.lenses.capacity import analyze_capacity


class BenchmarkResult(BaseModel):
    results: list[CaseResult]
    bottleneck_accuracy: float
    within_2x_rate: float
    off_by_100x_count: int
    citeability: float
    overload_accuracy: float


def run_case(case: GoldenCase) -> CaseResult:
    report = analyze_capacity(case.to_graph(), case.to_nfrs(), [], "high")
    return score_case(case, report)


def _rate(values: list[bool]) -> float:
    return sum(values) / len(values) if values else 1.0


def run_benchmark(cases: list[GoldenCase] | None = None) -> BenchmarkResult:
    cases = cases if cases is not None else GOLDEN_CASES
    results = [run_case(c) for c in cases]
    return BenchmarkResult(
        results=results,
        bottleneck_accuracy=_rate([r.bottleneck_correct for r in results
                                   if r.bottleneck_correct is not None]),
        within_2x_rate=_rate([r.within_2x for r in results if r.within_2x is not None]),
        off_by_100x_count=sum(1 for r in results if r.off_by_100x),
        citeability=_rate([r.cited for r in results]),
        overload_accuracy=_rate([r.overload_correct for r in results]),
    )


def format_scorecard(result: BenchmarkResult) -> str:
    lines = ["Sindri benchmark scorecard", ""]
    lines.append(f"  bottleneck accuracy : {result.bottleneck_accuracy:.0%}")
    lines.append(f"  capacity within 2x  : {result.within_2x_rate:.0%}")
    lines.append(f"  off by 100x         : {result.off_by_100x_count}")
    lines.append(f"  citeability         : {result.citeability:.0%}")
    lines.append(f"  overload accuracy   : {result.overload_accuracy:.0%}")
    lines.append("")
    for r in result.results:
        tag = "scored" if r.scored else "documented"
        lines.append(f"  [{tag}] {r.name}: "
                     f"bottleneck={r.bottleneck_correct} within2x={r.within_2x} "
                     f"overload_ok={r.overload_correct} cited={r.cited}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_runner.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add sindri/benchmark/runner.py tests/test_runner.py
git commit -m "feat: benchmark aggregate + runner + scorecard"
```

---

### Task 5: Benchmark CLI + acceptance test (the §3.1 measurement)

**Files:**
- Create: `scripts/bench.py`
- Test: `tests/test_benchmark_acceptance.py`

**Interfaces:**
- Consumes: `run_benchmark`, `format_scorecard`, `GOLDEN_CASES`.
- Produces: `scripts/bench.py` prints `format_scorecard(run_benchmark())` when run as a script. The acceptance test asserts the §3.1 thresholds on the real `GOLDEN_CASES`.

**Honesty note:** if the acceptance test fails on first run, that is a REAL RESULT. Do NOT re-encode the golden cases to make it pass (that is the circularity trap). Report the actual measured numbers and stop; the fix is KB/engine tuning in a follow-up, not editing the cases.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_benchmark_acceptance.py
from sindri.benchmark.runner import run_benchmark


def test_meets_section_3_1_thresholds_on_golden_set():
    res = run_benchmark()  # the real GOLDEN_CASES
    # §3.1 acceptance bar, measured on the cases Sindri can faithfully score:
    assert res.bottleneck_accuracy >= 0.8
    assert res.within_2x_rate >= 0.8
    assert res.off_by_100x_count == 0
    assert res.citeability == 1.0


def test_does_not_cry_wolf_or_overclaim():
    res = run_benchmark()
    # behavior + out-of-model honesty: every case's overload verdict matches expectation
    # (tiny app fits; Instagram throughput fits; Discord store abstained).
    assert res.overload_accuracy == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_benchmark_acceptance.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tests.test_benchmark_acceptance'`... actually it will fail because the file does not exist yet; create it as written above and the assertions exercise the real benchmark. If any assertion fails, STOP and report the measured numbers per the honesty note.

- [ ] **Step 3: Write `scripts/bench.py`**

```python
# scripts/bench.py
from sindri.benchmark.runner import run_benchmark, format_scorecard


def main() -> None:
    print(format_scorecard(run_benchmark()))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the acceptance test**

Run: `pytest tests/test_benchmark_acceptance.py -v`
Expected: PASS (2 passed). If it does not pass, STOP and report the real numbers (do not edit the golden cases to force a pass).

- [ ] **Step 5: Run the scorecard for the record**

Run: `python scripts/bench.py`
Expected: a printed scorecard. Paste it into the task report.

- [ ] **Step 6: Run the full suite (gate)**

Run: `pytest -q`
Expected: PASS (all tasks green).

- [ ] **Step 7: Commit**

```bash
git add scripts/bench.py tests/test_benchmark_acceptance.py
git commit -m "feat: benchmark CLI + section 3.1 acceptance test"
```

---

## Manual Verification (after Task 5)

1. `python scripts/bench.py` and read the scorecard.
2. Confirm: bottleneck accuracy and within-2x are high on the consistency cases, citeability is 100%, off-by-100x is 0, and the out-of-model rows are marked `documented` (not counted toward accuracy) with overload verdicts matching honesty (Instagram/Discord do not get a false overload roast).

---

## Self-Review Notes (author)

- **Spec coverage (Plan 2 slice):** golden set (T2), per-case scorer + the §3.1 metrics (T3), aggregate + scorecard (T4), the acceptance thresholds wired as a test + a CLI (T5), abstain-outside-coverage and don't-cry-wolf pinned by the behavior cases, out-of-model honesty pinned by the documented cases. Deferred (named plan sequence, not gaps): latency + cost lenses (Plan 3), anti-pattern linter incl hot-partition (Plan 4) which is what the Discord case motivates, roast narrator (Plan 5).
- **Honest scope is explicit:** the benchmark validates internal consistency with cited ceilings + behavior, not accuracy against multi-instance production scale (single-instance v1). Out-of-model cases are documented, not scored.
- **Anti-circularity:** consistency capacities are derived from the externally-cited ceilings (provenance in each `note`), then reproduced end-to-end; the honesty note in T5 forbids re-encoding cases to force a pass.
- **Placeholder scan:** none; every step has real code + a real command.
- **Type consistency:** `GoldenCase`, `CaseResult`, `BenchmarkResult` fields and `score_case`/`run_case`/`run_benchmark`/`format_scorecard` signatures are consistent across T1->T5 and match Plan 1's `CapacityReport`/`Utilization`/`analyze_capacity`/`get_capability`.
