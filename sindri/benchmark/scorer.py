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
