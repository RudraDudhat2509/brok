"""Static validation for TechEntry KB.

These tests do not call any LLM or embedding model.
They enforce structural invariants: every entry is present, every mandatory
field is non-empty, and every citation points to a real-looking URL.
"""
from __future__ import annotations

import pytest

from brok.kb_tech import TECH_KB, TechEntry
from brok.models import ComponentType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ENTRY_NAMES = {e.name for e in TECH_KB}
EXPECTED_COUNT = 25


def entry(name: str) -> TechEntry:
    for e in TECH_KB:
        if e.name == name:
            return e
    raise KeyError(name)


# ---------------------------------------------------------------------------
# Structural invariants
# ---------------------------------------------------------------------------

def test_entry_count():
    assert len(TECH_KB) == EXPECTED_COUNT, (
        f"Expected {EXPECTED_COUNT} entries, got {len(TECH_KB)}"
    )


def test_all_entries_have_name():
    for e in TECH_KB:
        assert e.name.strip(), f"Entry with empty name: {e!r}"


def test_all_entries_have_citation():
    for e in TECH_KB:
        assert e.citation.startswith("http"), (
            f"{e.name}: citation must be a URL, got {e.citation!r}"
        )


def test_all_entries_have_non_empty_mandatory_fields():
    fields = ["when_to_pick", "when_not_to_pick", "throughput_ceiling", "key_tradeoff"]
    for e in TECH_KB:
        for field in fields:
            value = getattr(e, field)
            assert value.strip(), f"{e.name}.{field} is empty"


def test_all_entries_have_aliases():
    for e in TECH_KB:
        assert len(e.aliases) >= 1, f"{e.name}: must have at least one alias"


def test_no_duplicate_names():
    names = [e.name for e in TECH_KB]
    assert len(names) == len(set(names)), "Duplicate entry names found"


def test_all_categories_are_valid_component_types():
    for e in TECH_KB:
        assert isinstance(e.category, ComponentType), (
            f"{e.name}: category must be ComponentType, got {type(e.category)}"
        )


# ---------------------------------------------------------------------------
# Category coverage — at least one entry per expected category
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("category", [
    ComponentType.QUEUE,
    ComponentType.CACHE,
    ComponentType.RELATIONAL_DB,
    ComponentType.OBJECT_STORE,
    ComponentType.CDN,
    ComponentType.LOAD_BALANCER,
    ComponentType.APP_SERVER,
])
def test_category_has_entries(category: ComponentType):
    matching = [e for e in TECH_KB if e.category == category]
    assert len(matching) >= 1, f"No entries for category {category.value}"


# ---------------------------------------------------------------------------
# Guard-critical entries — when_not_to_pick must contain the right warnings
# ---------------------------------------------------------------------------

def test_cassandra_warns_about_eventual_consistency():
    e = entry("Cassandra")
    text = e.when_not_to_pick.lower()
    assert any(w in text for w in ("eventual", "leaderless", "tunable")), (
        "Cassandra.when_not_to_pick must warn about eventual/leaderless consistency"
    )


def test_redis_warns_about_memory_limit():
    e = entry("Redis")
    text = e.when_not_to_pick.lower()
    assert any(w in text for w in ("ram", "memory", "in-memory")), (
        "Redis.when_not_to_pick must warn about RAM/memory limit"
    )


def test_memcached_warns_about_no_persistence():
    e = entry("Memcached")
    text = e.when_not_to_pick.lower()
    assert any(w in text for w in ("no persistence", "evicts", "volatile")), (
        "Memcached.when_not_to_pick must warn about volatility"
    )


def test_pubsub_warns_about_ordering():
    e = entry("Pub/Sub")
    text = e.when_not_to_pick.lower()
    assert "ordering" in text, (
        "Pub/Sub.when_not_to_pick must warn about no global ordering"
    )


def test_kafka_warns_about_self_hosted_and_pull():
    e = entry("Kafka")
    text = e.when_not_to_pick.lower()
    assert any(w in text for w in ("self-hosted", "pull", "ops")), (
        "Kafka.when_not_to_pick must warn about self-hosted/pull-based nature"
    )


def test_mysql_warns_about_vertical_scaling():
    e = entry("MySQL")
    text = e.when_not_to_pick.lower()
    assert any(w in text for w in ("vertical", "shard", "horizontal")), (
        "MySQL.when_not_to_pick must warn about vertical scaling"
    )


def test_cockroachdb_warns_about_cross_region_latency():
    e = entry("CockroachDB")
    text = e.when_not_to_pick.lower()
    assert any(w in text for w in ("cross-region", "latency", "global")), (
        "CockroachDB.when_not_to_pick must warn about cross-region latency"
    )


# ---------------------------------------------------------------------------
# Specific entry presence
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", [
    "Kafka", "Pub/Sub", "SQS", "RabbitMQ", "Celery",
    "Redis", "Memcached", "DynamoDB DAX",
    "PostgreSQL", "MySQL", "CockroachDB", "PlanetScale", "Cassandra",
    "S3", "GCS", "Azure Blob",
    "Cloudflare", "CloudFront", "Fastly",
    "ALB", "nginx", "HAProxy",
    "FastAPI", "Express", "Spring Boot",
])
def test_expected_entry_present(name: str):
    assert name in ENTRY_NAMES, f"Expected entry {name!r} not found in TECH_KB"
