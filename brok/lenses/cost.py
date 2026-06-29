from __future__ import annotations

from brok.models import ComponentType, DesignGraph, NFRs

# Normalized monthly USD, one mid-tier instance, order-of-magnitude.
COMPUTE_USD_PER_MONTH: dict[ComponentType, float] = {
    ComponentType.APP_SERVER: 60.0,
    ComponentType.RELATIONAL_DB: 120.0,
    ComponentType.CACHE: 80.0,
    ComponentType.QUEUE: 100.0,
    ComponentType.LOAD_BALANCER: 20.0,
}
EGRESS_USD_PER_GB = 0.09
SECONDS_PER_MONTH = 2_592_000
COST_SOURCE = ("Normalized cloud list prices (AWS/GCP/Azure), one mid-tier instance, "
               "order-of-magnitude; internet egress about $0.09/GB")


def estimate_cost(graph: DesignGraph, nfrs: NFRs) -> dict:
    breakdown: list[dict] = []
    compute_total = 0.0
    for c in graph.components:
        usd = COMPUTE_USD_PER_MONTH.get(c.type)
        if usd is None:
            continue
        compute_total += usd
        breakdown.append({"component": c.name, "type": c.type.value,
                          "monthly_usd": round(usd, 2)})

    avg_rps = nfrs.dau * nfrs.requests_per_user_per_day / 86400
    egress_gb = avg_rps * (nfrs.payload_kb * 1024) * SECONDS_PER_MONTH / (1024 ** 3)
    egress_usd = egress_gb * EGRESS_USD_PER_GB

    return {
        "monthly_compute_usd": round(compute_total, 2),
        "monthly_egress_usd": round(egress_usd, 2),
        "monthly_total_usd": round(compute_total + egress_usd, 2),
        "egress_gb_per_month": round(egress_gb, 1),
        "breakdown": breakdown,
        "assumptions": [
            "One instance per component at a mid-tier size.",
            "All response payload counts as internet egress.",
            "Storage volume and per-request charges not modeled.",
        ],
        "source": COST_SOURCE,
    }
