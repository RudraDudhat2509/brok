from __future__ import annotations

from sindri.lenses.capacity import analyze_capacity
from sindri.nfr import resolve_nfrs
from sindri.parsers.compose import parse_compose
from sindri.report import render_report


def review(compose_yaml: str, nfrs: dict | None = None) -> str:
    graph = parse_compose(compose_yaml)
    if not graph.components:
        return ("Sindri capacity review\n\n"
                "I couldn't find any components. Give me a docker-compose with "
                "services, or describe your stack.")
    resolved, assumptions = resolve_nfrs(nfrs)
    confidence = "low" if assumptions else "high"
    report = analyze_capacity(graph, resolved, assumptions, confidence)
    return render_report(report)
