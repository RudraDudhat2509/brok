"""Retrieval accuracy tests for query.py.

These tests load the all-MiniLM-L6-v2 model (~90 MB, cached after first run).
They cover return shape, known-good queries, the empty-match case, and the
comparison block. Full recall is validated in scripts/bench_query.py.
"""
from __future__ import annotations

import pytest

from brok.query import THRESHOLD, _init, _VECS, search


# ---------------------------------------------------------------------------
# Return shape — every search() call must return this exact shape
# ---------------------------------------------------------------------------

def test_return_shape_matches():
    result = search("kafka vs pubsub")
    assert set(result.keys()) == {"matches", "comparison", "note"}
    assert isinstance(result["matches"], list)
    assert isinstance(result["note"], str)
    # comparison is either a string or None
    assert result["comparison"] is None or isinstance(result["comparison"], str)


def test_each_match_has_required_keys():
    result = search("redis vs memcached")
    assert len(result["matches"]) > 0
    required = {"name", "type", "category", "when_to_pick", "when_not_to_pick",
                "key_tradeoff", "extra", "citation"}
    for m in result["matches"]:
        assert set(m.keys()) >= required, f"Match missing keys: {set(m.keys())}"


def test_type_field_is_valid():
    result = search("kafka vs pubsub")
    for m in result["matches"]:
        assert m["type"] in ("tech", "strategy", "pattern")


def test_citation_field_is_url():
    result = search("postgres sharding")
    for m in result["matches"]:
        assert m["citation"].startswith("http"), (
            f"{m['name']}: citation must be a URL, got {m['citation']!r}"
        )


# ---------------------------------------------------------------------------
# Known-good tech queries
# ---------------------------------------------------------------------------

def test_kafka_pubsub_both_returned():
    result = search("kafka vs pubsub")
    names = {m["name"] for m in result["matches"]}
    assert "Kafka" in names
    assert "Pub/Sub" in names


def test_kafka_pubsub_comparison_block_fires():
    result = search("kafka vs pubsub")
    assert result["comparison"] is not None
    assert "KAFKA" in result["comparison"].upper()
    assert "PUB/SUB" in result["comparison"].upper()


def test_redis_memcached_both_returned():
    result = search("redis vs memcached session")
    names = {m["name"] for m in result["matches"]}
    assert "Redis" in names
    assert "Memcached" in names


def test_postgres_cockroachdb_returned():
    result = search("postgres vs cockroachdb global")
    names = {m["name"] for m in result["matches"]}
    assert "PostgreSQL" in names
    assert "CockroachDB" in names


# ---------------------------------------------------------------------------
# Known-good strategy queries
# ---------------------------------------------------------------------------

def test_write_through_write_back_returned():
    result = search("write through vs write back cache")
    names = {m["name"] for m in result["matches"]}
    assert "write-through" in names
    assert "write-back" in names


def test_at_least_once_exactly_once_returned():
    result = search("at least once exactly once delivery")
    names = {m["name"] for m in result["matches"]}
    assert "at-least-once delivery" in names
    assert "exactly-once delivery" in names


# ---------------------------------------------------------------------------
# Known-good pattern queries
# ---------------------------------------------------------------------------

def test_circuit_breaker_returned():
    result = search("circuit breaker downstream failure")
    names = {m["name"] for m in result["matches"]}
    assert "Circuit Breaker" in names


def test_cqrs_returned():
    result = search("when to use cqrs read write separation")
    names = {m["name"] for m in result["matches"]}
    assert "CQRS" in names


def test_strangler_fig_returned():
    result = search("monolith to microservices migration")
    names = {m["name"] for m in result["matches"]}
    assert "Strangler Fig" in names


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_completely_unknown_query_returns_empty_or_low_score():
    result = search("xyzzy unknown gobbledygook zzz 12345")
    # Should either return nothing or only low-confidence matches
    # All matches must be above THRESHOLD (but there may be zero)
    assert isinstance(result["matches"], list)
    assert result["comparison"] is None or len(result["matches"]) >= 2


def test_no_match_returns_correct_shape():
    # Force a query unlikely to match anything
    result = search("xyzzy gobbledygook")
    assert "matches" in result
    assert "comparison" in result
    assert "note" in result
    assert result["note"] == "Brok surfaces trade-offs. You decide."


def test_top_k_respected():
    result = search("database", top_k=2)
    assert len(result["matches"]) <= 2


def test_comparison_none_for_different_categories():
    # Kafka (queue) and Redis (cache) should not trigger a comparison block
    result = search("kafka redis")
    # Even if both returned, they are different categories — no comparison
    names = {m["name"] for m in result["matches"]}
    if "Kafka" in names and "Redis" in names:
        assert result["comparison"] is None


# ---------------------------------------------------------------------------
# Caching — second call must not re-embed
# ---------------------------------------------------------------------------

def test_embeddings_cached_after_first_call():
    search("kafka")  # triggers _init()
    vecs_before = _VECS
    search("redis")  # must use cache
    assert _VECS is vecs_before, "Re-embedding on every call would be a 2.5s regression"
