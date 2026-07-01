"""Static validation for PatternEntry KB."""
from __future__ import annotations

import pytest

from brok.kb_patterns import PATTERN_KB, PatternEntry

ENTRY_NAMES = {e.name for e in PATTERN_KB}
EXPECTED_COUNT = 10


def entry(name: str) -> PatternEntry:
    for e in PATTERN_KB:
        if e.name == name:
            return e
    raise KeyError(name)


def test_entry_count():
    assert len(PATTERN_KB) == EXPECTED_COUNT


def test_no_duplicate_names():
    names = [e.name for e in PATTERN_KB]
    assert len(names) == len(set(names))


def test_all_entries_have_citation():
    for e in PATTERN_KB:
        assert e.citation.startswith("http"), (
            f"{e.name}: citation must be a URL, got {e.citation!r}"
        )


def test_all_mandatory_fields_non_empty():
    fields = ["when_to_use", "when_not_to_use", "operational_cost", "common_mistake"]
    for e in PATTERN_KB:
        for field in fields:
            assert getattr(e, field).strip(), f"{e.name}.{field} is empty"


def test_all_entries_have_aliases():
    for e in PATTERN_KB:
        assert len(e.aliases) >= 1, f"{e.name}: must have at least one alias"


@pytest.mark.parametrize("name", [
    "CQRS",
    "Event Sourcing",
    "Saga",
    "Outbox Pattern",
    "Circuit Breaker",
    "Bulkhead",
    "Strangler Fig",
    "API Gateway",
    "Sidecar",
    "Rate Limiter",
])
def test_expected_entry_present(name: str):
    assert name in ENTRY_NAMES, f"Expected pattern {name!r} not in PATTERN_KB"


# ---------------------------------------------------------------------------
# Guard-critical: common_mistake must contain words that directly contradict
# the wrong use cases the benchmark tests against.
# ---------------------------------------------------------------------------

def test_cqrs_common_mistake_mentions_simple_crud():
    e = entry("CQRS")
    text = e.common_mistake.lower()
    assert any(w in text for w in ("simple", "crud", "overhead")), (
        "CQRS.common_mistake must warn that applying it to simple CRUD adds overhead"
    )


def test_saga_common_mistake_mentions_2pc_blocking():
    e = entry("Saga")
    text = e.common_mistake.lower()
    assert "two-phase" in text or "2pc" in text, (
        "Saga.common_mistake must warn about 2PC / two-phase commit"
    )
    assert "blocking" in text, (
        "Saga.common_mistake must describe 2PC as blocking"
    )


def test_event_sourcing_warns_about_simple_use():
    e = entry("Event Sourcing")
    text = e.when_not_to_use.lower() + " " + e.common_mistake.lower()
    assert any(w in text for w in ("simple", "overhead", "complex")), (
        "Event Sourcing must warn about overhead for simple apps"
    )


def test_outbox_pattern_warns_dual_write():
    e = entry("Outbox Pattern")
    text = e.common_mistake.lower()
    assert "dual write" in text or "lost" in text, (
        "Outbox Pattern.common_mistake must warn about dual-write data loss"
    )


def test_circuit_breaker_warns_about_timeouts_first():
    e = entry("Circuit Breaker")
    text = e.common_mistake.lower()
    assert "timeout" in text, (
        "Circuit Breaker.common_mistake must warn about setting timeouts first"
    )


def test_rate_limiter_warns_about_per_server_limits():
    e = entry("Rate Limiter")
    text = e.common_mistake.lower()
    assert "per-server" in text or "shared state" in text or "k*n" in text, (
        "Rate Limiter.common_mistake must warn about per-server limits without shared state"
    )


def test_strangler_fig_warns_against_big_bang():
    e = entry("Strangler Fig")
    text = e.common_mistake.lower()
    assert "big-bang" in text or "rewrite" in text, (
        "Strangler Fig.common_mistake must warn against big-bang rewrites"
    )


def test_api_gateway_warns_against_business_logic():
    e = entry("API Gateway")
    text = e.common_mistake.lower()
    assert "business logic" in text or "logic" in text, (
        "API Gateway.common_mistake must warn against business logic in the gateway"
    )
