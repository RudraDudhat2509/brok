from sindri.models import ComponentType
from sindri.parsers.compose import classify_image, parse_compose

COMPOSE = """
services:
  api:
    build: .
  db:
    image: postgres:16
  cache:
    image: redis:7
  edge:
    image: nginx:latest
"""


def test_classify_known_images():
    assert classify_image("postgres:16") is ComponentType.RELATIONAL_DB
    assert classify_image("redis:7") is ComponentType.CACHE
    assert classify_image("nginx:latest") is ComponentType.LOAD_BALANCER


def test_classify_unknown_image():
    assert classify_image("ghcr.io/acme/weird-thing:1") is ComponentType.UNKNOWN


def test_parse_compose_builds_graph():
    g = parse_compose(COMPOSE)
    by = {c.name: c.type for c in g.components}
    assert by["db"] is ComponentType.RELATIONAL_DB
    assert by["cache"] is ComponentType.CACHE
    assert by["edge"] is ComponentType.LOAD_BALANCER
    assert by["api"] is ComponentType.APP_SERVER  # has build:, no known image


def test_malformed_yaml_returns_empty_graph_not_crash():
    g = parse_compose("::: not yaml :::")
    assert g.components == []
