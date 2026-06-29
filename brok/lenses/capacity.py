from __future__ import annotations

from brok.kb import get_capability
from brok.models import (
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
            if has_cache:
                ceiling = cap.write_low
            else:
                vals = [v for v in [cap.write_low, cap.read_low] if v is not None]
                ceiling = min(vals) if vals else None
        elif comp.type is ComponentType.CACHE:
            load = reads
            ceiling = cap.read_low
        elif comp.type in (ComponentType.APP_SERVER, ComponentType.LOAD_BALANCER):
            load = total
            ceiling = cap.read_low
        else:  # cdn, object_store, queue: not on the modeled hot path in v1
            utilizations.append(Utilization(
                component=comp.name, type=comp.type, load_per_sec=0.0,
                ceiling_per_sec=None, utilization=None, estimated=False))
            continue

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
