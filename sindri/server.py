from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from sindri.pipeline import build_traffic, review_from_components, review_from_compose

mcp = FastMCP("sindri")


@mcp.tool()
def review_architecture(
    compose_yaml: str,
    expected_dau: int | None = None,
    requests_per_user_per_day: int | None = None,
    read_write_ratio: float | None = None,
    payload_kb: float | None = None,
    peak_factor: float | None = None,
) -> dict:
    """Estimate the capacity of a system from its docker-compose and find the bottleneck.

    How to use this (for the calling assistant):
    1. If the project has a docker-compose.yml, read it and pass its full contents
       as compose_yaml.
    2. Ask the user for their expected scale and pass expected_dau (daily active
       users), plus read_write_ratio if known. Without expected_dau the result
       assumes 100k users and is reported as low confidence.
    3. Show the user `report_text`; use the structured fields to reason or compare.

    Returns a dict: bottleneck (component name or null), max_dau (int or null),
    confidence ('low'|'high'), assumptions (list of stated assumptions),
    utilizations (per-component load vs ceiling), notes, and report_text.
    """
    traffic = build_traffic(expected_dau, requests_per_user_per_day,
                            read_write_ratio, payload_kb, peak_factor)
    return review_from_compose(compose_yaml, traffic)


@mcp.tool()
def review_components(
    components: list[dict],
    expected_dau: int | None = None,
    requests_per_user_per_day: int | None = None,
    read_write_ratio: float | None = None,
    payload_kb: float | None = None,
    peak_factor: float | None = None,
) -> dict:
    """Estimate capacity from a structured component list (use when there is no
    docker-compose).

    How to use this (for the calling assistant): infer the components yourself from
    the user's description or code, and pass them as a list of {"name", "type"}
    dicts. Valid types: relational_db, cache, queue, cdn, app_server, object_store,
    load_balancer. Any other type string is reported as not-estimated (Sindri will
    not guess). Pass expected_dau for a high-confidence result.

    Returns the same dict shape as review_architecture.
    """
    traffic = build_traffic(expected_dau, requests_per_user_per_day,
                            read_write_ratio, payload_kb, peak_factor)
    return review_from_components(components, traffic)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
