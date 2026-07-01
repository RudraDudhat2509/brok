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

    if ComponentType.RELATIONAL_DB in types and app_count >= 3:
        found.append(AntiPattern(
            code="CONNECTION_POOL_RISK",
            message=(
                f"{app_count} app servers sharing one Postgres. "
                "Default max_connections is 100; at 20-30 connections per server "
                f"you are already at {app_count * 25} connections. "
                "Throughput looks fine, connections are the real wall. "
                "Add PgBouncer in transaction mode in front."
            ),
        ))

    if (
        ComponentType.RELATIONAL_DB in types
        and ComponentType.OBJECT_STORE not in types
        and nfrs.dau >= 5_000_000
    ):
        found.append(AntiPattern(
            code="DATA_VOLUME_WALL",
            message=(
                f"{nfrs.dau:,} DAU on one relational DB with no object store. "
                "Data volume becomes the wall before writes do at this scale. "
                "Offload blobs to object storage and plan for horizontal sharding."
            ),
        ))

    return found
