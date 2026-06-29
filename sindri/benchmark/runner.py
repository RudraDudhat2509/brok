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
        overload_accuracy=_rate([r.overload_correct for r in results
                                   if r.category != "out_of_model"]),
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
