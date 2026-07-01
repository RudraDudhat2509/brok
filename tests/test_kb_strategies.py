"""Static validation for StrategyEntry KB."""
from __future__ import annotations

import pytest

from brok.kb_strategies import STRATEGY_KB, StrategyEntry

ENTRY_NAMES = {e.name for e in STRATEGY_KB}
EXPECTED_COUNT = 18


def entry(name: str) -> StrategyEntry:
    for e in STRATEGY_KB:
        if e.name == name:
            return e
    raise KeyError(name)


def test_entry_count():
    assert len(STRATEGY_KB) == EXPECTED_COUNT


def test_no_duplicate_names():
    names = [e.name for e in STRATEGY_KB]
    assert len(names) == len(set(names))


def test_all_entries_have_citation():
    for e in STRATEGY_KB:
        assert e.citation.startswith("http"), (
            f"{e.name}: citation must be a URL, got {e.citation!r}"
        )


def test_all_mandatory_fields_non_empty():
    fields = ["when_to_use", "when_not_to_use", "key_tradeoff"]
    for e in STRATEGY_KB:
        for field in fields:
            assert getattr(e, field).strip(), f"{e.name}.{field} is empty"


def test_all_entries_have_aliases():
    for e in STRATEGY_KB:
        assert len(e.aliases) >= 1, f"{e.name}: must have at least one alias"


def test_all_entries_have_applies_to():
    for e in STRATEGY_KB:
        assert len(e.applies_to) >= 1, f"{e.name}: applies_to must not be empty"


# Domain coverage
@pytest.mark.parametrize("domain,expected_min", [
    ("sharding", 4),
    ("eviction", 3),
    ("delivery", 3),
    ("replication", 3),
    ("partitioning", 2),
])
def test_domain_coverage(domain: str, expected_min: int):
    keyword_map = {
        "sharding": ["sharding", "hashing"],
        "eviction": ["lru", "lfu", "ttl", "write-through", "write-back", "write-around"],
        "delivery": ["once"],
        "replication": ["replication", "replica"],
        "partitioning": ["partition"],
    }
    keywords = keyword_map[domain]
    matching = [
        e for e in STRATEGY_KB
        if any(k in e.name.lower() for k in keywords)
    ]
    assert len(matching) >= expected_min, (
        f"Domain {domain!r}: expected at least {expected_min} entries, "
        f"found {len(matching)}: {[e.name for e in matching]}"
    )


# Specific entries present
@pytest.mark.parametrize("name", [
    "consistent hashing",
    "range-based sharding",
    "hash-based sharding",
    "directory-based sharding",
    "LRU", "LFU", "TTL",
    "write-through", "write-back", "write-around",
    "at-least-once delivery",
    "exactly-once delivery",
    "at-most-once delivery",
    "synchronous replication",
    "asynchronous replication",
    "read replicas",
    "Kafka partition key",
    "hot partition avoidance",
])
def test_expected_entry_present(name: str):
    assert name in ENTRY_NAMES, f"Expected strategy entry {name!r} not in STRATEGY_KB"


# Guard-critical: at-most-once must warn about data loss
def test_at_most_once_warns_data_loss():
    e = entry("at-most-once delivery")
    text = e.when_not_to_use.lower()
    assert "loss" in text or "unacceptable" in text, (
        "at-most-once.when_not_to_use must warn about data loss"
    )


# Guard-critical: exactly-once must mention overhead
def test_exactly_once_mentions_overhead():
    e = entry("exactly-once delivery")
    text = e.key_tradeoff.lower()
    assert "overhead" in text or "throughput" in text, (
        "exactly-once.key_tradeoff must mention overhead or throughput cost"
    )


# Guard-critical: range sharding must warn about hot shard from monotonic keys
def test_range_sharding_warns_hot_shard():
    e = entry("range-based sharding")
    text = e.when_not_to_use.lower()
    assert "hot" in text or "monoton" in text, (
        "range-based sharding.when_not_to_use must warn about hot shards from monotonic keys"
    )
