from __future__ import annotations

from dataclasses import dataclass

from brok.models import ComponentType, DesignGraph, NFRs


@dataclass(frozen=True)
class AntiPattern:
    code: str
    message: str


def lint(graph: DesignGraph, nfrs: NFRs) -> list[AntiPattern]:
    found: list[AntiPattern] = []
    types = {c.type for c in graph.components}

    if ComponentType.CDN in types and nfrs.read_write_ratio < 9.0:
        found.append(AntiPattern(
            code="WRITE_TO_CDN",
            message=(
                f"CDN in the design but the traffic mix is "
                f"{nfrs.read_write_ratio:.0f} reads per write. "
                "A CDN is a read cache. Writes skip it or fail silently."
            ),
        ))

    app_count = sum(1 for c in graph.components if c.type == ComponentType.APP_SERVER)
    if app_count >= 2 and ComponentType.LOAD_BALANCER not in types:
        found.append(AntiPattern(
            code="NO_LOAD_BALANCER",
            message=(
                f"{app_count} app servers with no load balancer. "
                "Traffic has nowhere to distribute between them."
            ),
        ))

    if (
        ComponentType.RELATIONAL_DB in types
        and ComponentType.CACHE not in types
        and nfrs.read_write_ratio >= 5.0
        and nfrs.dau >= 100_000
    ):
        found.append(AntiPattern(
            code="UNPROTECTED_DB",
            message=(
                f"Read-heavy workload ({nfrs.read_write_ratio:.0f}:1 reads) "
                "hitting the database directly with no cache. "
                "A cache in front absorbs most of that load."
            ),
        ))

    return found
