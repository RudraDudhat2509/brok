from __future__ import annotations

import hashlib

from brok.models import CapacityReport, ComponentType
from brok.tradeoffs import tradeoffs_for
from brok.lenses.latency import KNEE, latency_multiplier

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
    "degrading": [
        "{component} is running {pct} hot. Under the cap, sure, but past the knee, so queueing already puts latency near {mult}x idle. Real headroom is about {safe_dau} users, not {max_dau}. {fix}.",
        "{component} sits at {pct} of its ceiling. It works until it does not; at this load latency is about {mult}x its idle baseline. Plan for about {safe_dau} users. {fix}.",
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
    if util >= 1.0:
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
    safe_dau = f"{int(report.max_dau * KNEE):,}" if report.max_dau is not None else "?"
    pct = f"{round(util * 100)}%" if util is not None else "?"
    mult_val = latency_multiplier(util)
    mult = f"{mult_val:.1f}" if mult_val is not None else "?"
    return template.format(component=report.bottleneck, factor=factor,
                           max_dau=max_dau, fix=fix, safe_dau=safe_dau,
                           pct=pct, mult=mult)


_HEADLINE = {
    "brutal": "WALK AWAY (for now)",
    "bad": "WALK AWAY (for now)",
    "low_conf_over": "WALK AWAY (for now)",
    "slight": "PUSHING IT",
    "degrading": "CUTTING IT CLOSE",
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

    tos = tradeoffs_for(report)
    if tos:
        lines.append("")
        lines.append("THE TRADE-OFFS YOU ARE MAKING:")
        for to in tos:
            lines.append(f"  {to['type']}: fine {to['when_fine']}.")
            lines.append(f"    cost: {to['cost']}. outgrow it: {to['move']}")

    return "\n".join(lines)


def render_antipatterns(antipatterns: list) -> str:
    if not antipatterns:
        return ""
    lines = ["", "", "STRUCTURAL ISSUES:"]
    for ap in antipatterns:
        lines.append(f"  [{ap.code}] {ap.message}")
    return "\n".join(lines)


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
