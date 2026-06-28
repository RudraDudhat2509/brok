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
