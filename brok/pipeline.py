from __future__ import annotations

from brok.lenses.capacity import analyze_capacity
from brok.models import Component, ComponentType, DesignGraph
from brok.nfr import resolve_nfrs
from brok.parsers.compose import parse_compose
from brok.report import render_report
from brok.voice import render_cost, render_roast
from brok.tradeoffs import tradeoffs_for
from brok.lenses.cost import estimate_cost

_NO_COMPONENTS_TEXT = (
    "Brok capacity review\n\n"
    "I couldn't find any components. Give me a docker-compose with services, "
    "or pass a component list."
)


def build_traffic(expected_dau, requests_per_user_per_day, read_write_ratio,
                  payload_kb, peak_factor) -> dict | None:
    traffic = {
        "dau": expected_dau,
        "requests_per_user_per_day": requests_per_user_per_day,
        "read_write_ratio": read_write_ratio,
        "payload_kb": payload_kb,
        "peak_factor": peak_factor,
    }
    traffic = {k: v for k, v in traffic.items() if v is not None}
    return traffic or None


def build_result(graph: DesignGraph, traffic: dict | None = None) -> dict:
    resolved, assumptions = resolve_nfrs(traffic)
    confidence = "low" if assumptions else "high"
    report = analyze_capacity(graph, resolved, assumptions, confidence)
    cost = estimate_cost(graph, resolved)
    return {
        **report.model_dump(mode="json"),
        "report_text": render_report(report),
        "roast_text": render_roast(report) + render_cost(cost),
        "tradeoffs": tradeoffs_for(report),
        "cost": cost,
    }


def review(compose_yaml: str, nfrs: dict | None = None) -> str:
    graph = parse_compose(compose_yaml)
    if not graph.components:
        return _NO_COMPONENTS_TEXT
    return build_result(graph, nfrs)["report_text"]


def _empty_result() -> dict:
    return {
        "bottleneck": None, "max_dau": None, "utilizations": [],
        "assumptions": [], "confidence": "low", "notes": [],
        "report_text": _NO_COMPONENTS_TEXT,
        "roast_text": _NO_COMPONENTS_TEXT,
        "tradeoffs": [],
        "cost": None,
    }


def review_from_compose(compose_yaml: str, traffic: dict | None = None) -> dict:
    graph = parse_compose(compose_yaml)
    if not graph.components:
        return _empty_result()
    return build_result(graph, traffic)


def review_from_components(components: list[dict], traffic: dict | None = None) -> dict:
    comps = []
    for c in components:
        try:
            ctype = ComponentType(c.get("type", ""))
        except ValueError:
            ctype = ComponentType.UNKNOWN
        comps.append(Component(name=str(c.get("name", "?")), type=ctype))
    graph = DesignGraph(components=comps)
    if not graph.components:
        return _empty_result()
    return build_result(graph, traffic)
