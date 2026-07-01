"""Hallucination guard tests.

Each test sends a query that a model commonly answers wrong and asserts that
the KB entry returned contains an explicit warning against that wrong answer.
The check covers `when_not_to_pick` + `extra` (which holds `common_mistake`
for PatternEntry and `throughput_ceiling` for TechEntry).

These are the 10 cases from the benchmark GUARD set, expressed as pytest tests
so they run in CI and block a commit if any guard regresses.
"""
from __future__ import annotations

import pytest

from brok.query import search


def _guard(query: str, expected_name: str, must_warn: list[str]) -> None:
    """Assert that `expected_name` appears in top-3 and warns about `must_warn`."""
    result = search(query)
    found = {m["name"]: m for m in result["matches"]}
    assert expected_name in found, (
        f"Guard FAIL: {expected_name!r} not in top-3 for {query!r}. "
        f"Got: {list(found.keys())}"
    )
    m = found[expected_name]
    combined = (m["when_not_to_pick"] + " " + m["extra"]).lower()
    hit = next((w for w in must_warn if w in combined), None)
    assert hit is not None, (
        f"Guard FAIL: {expected_name!r} found but none of {must_warn!r} "
        f"in when_not_to_pick+extra.\n"
        f"  when_not_to_pick: {m['when_not_to_pick']!r}\n"
        f"  extra:            {m['extra']!r}"
    )


def test_cassandra_not_for_strong_consistency():
    _guard(
        "cassandra strong consistency",
        "Cassandra",
        ["eventual", "leaderless", "tunable"],
    )


def test_redis_not_for_terabyte_storage():
    _guard(
        "redis terabyte storage",
        "Redis",
        ["ram", "memory", "in-memory"],
    )


def test_pubsub_not_for_strict_ordering():
    _guard(
        "pubsub strict per key ordering",
        "Pub/Sub",
        ["ordering", "no global ordering"],
    )


def test_cqrs_not_for_simple_crud():
    _guard(
        "use cqrs for simple crud app",
        "CQRS",
        ["simple", "crud", "overhead"],
    )


def test_saga_not_2pc():
    _guard(
        "2pc distributed transaction scale",
        "Saga",
        ["two-phase", "blocking"],
    )


def test_mysql_not_horizontal_write_scale():
    _guard(
        "mysql horizontal write scale",
        "MySQL",
        ["vertical", "shard", "horizontal"],
    )


def test_memcached_not_persistent_storage():
    _guard(
        "memcached persistent storage",
        "Memcached",
        ["no persistence", "evicts", "volatile"],
    )


def test_event_sourcing_not_for_simple_app():
    _guard(
        "event sourcing simple app",
        "Event Sourcing",
        ["simple", "overhead", "complex"],
    )


def test_kafka_not_push_managed():
    _guard(
        "kafka push delivery managed",
        "Kafka",
        ["self-hosted", "pull", "ops"],
    )


def test_cockroachdb_not_single_region_low_latency():
    _guard(
        "cockroachdb single region low latency",
        "CockroachDB",
        ["cross-region", "latency"],
    )
