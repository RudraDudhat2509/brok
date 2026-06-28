from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from sindri.pipeline import review

mcp = FastMCP("sindri")


@mcp.tool()
def review_architecture(compose_yaml: str) -> str:
    """Review a system architecture (from a docker-compose) for capacity:
    returns the bottleneck component and the max user capacity, with stated
    assumptions."""
    return review(compose_yaml)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
