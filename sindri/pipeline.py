from __future__ import annotations

from sindri.lenses.capacity import analyze_capacity
from sindri.models import DesignGraph
from sindri.nfr import resolve_nfrs
from sindri.parsers.compose import parse_compose
from sindri.report import render_report

_NO_COMPONENTS_TEXT = (
    "Sindri capacity review\n\n"
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
    return {**report.model_dump(mode="json"), "report_text": render_report(report)}


def review(compose_yaml: str, nfrs: dict | None = None) -> str:
    graph = parse_compose(compose_yaml)
    if not graph.components:
        return _NO_COMPONENTS_TEXT
    return build_result(graph, nfrs)["report_text"]
