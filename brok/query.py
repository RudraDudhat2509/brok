"""Embedding-based retrieval across the three KB files.

Lazy-loads all-MiniLM-L6-v2 on first search() call (22MB, local, no API key).
Embeddings are cached in-process for the lifetime of the MCP server — re-embedding
53 entries on every query would add ~2.5 s per call.

Public surface: search(question, top_k=3) -> dict
"""
from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

from brok.kb_patterns import PATTERN_KB, PatternEntry
from brok.kb_strategies import STRATEGY_KB, StrategyEntry
from brok.kb_tech import TECH_KB, TechEntry

_MODEL_NAME = "all-MiniLM-L6-v2"
THRESHOLD = 0.25

_MODEL: SentenceTransformer | None = None
_ENTRIES: list[TechEntry | StrategyEntry | PatternEntry] | None = None
_VECS: np.ndarray | None = None   # shape (n_entries, 384), L2-normalised


def _embed_text(entry: TechEntry | StrategyEntry | PatternEntry) -> str:
    """Build the text that represents an entry in embedding space.

    Aliases are prepended so variant names (e.g. 'SQS', 'amazon sqs') all pull
    the right entry regardless of which name the caller uses.
    """
    aliases = " ".join(entry.aliases)
    if isinstance(entry, TechEntry):
        return f"{entry.name} {aliases}. {entry.when_to_pick}. {entry.key_tradeoff}"
    if isinstance(entry, StrategyEntry):
        return f"{entry.name} {aliases}. {entry.when_to_use}. {entry.key_tradeoff}"
    # PatternEntry
    return f"{entry.name} {aliases}. {entry.when_to_use}. {entry.operational_cost}"


def _init() -> None:
    """Embed all KB entries on first call; no-op on subsequent calls."""
    global _MODEL, _ENTRIES, _VECS
    if _VECS is not None:
        return
    _MODEL = SentenceTransformer(_MODEL_NAME)
    all_entries: list[TechEntry | StrategyEntry | PatternEntry] = (
        list(TECH_KB) + list(STRATEGY_KB) + list(PATTERN_KB)
    )
    texts = [_embed_text(e) for e in all_entries]
    _VECS = _MODEL.encode(texts, normalize_embeddings=True)
    _ENTRIES = all_entries


def _normalize(entry: TechEntry | StrategyEntry | PatternEntry) -> dict:
    """Return a uniform dict shape regardless of entry type.

    Consumers always see the same keys. The `extra` slot carries the
    guard-critical content: common_mistake for PatternEntry,
    throughput_ceiling for TechEntry, empty string for StrategyEntry.
    """
    if isinstance(entry, TechEntry):
        return {
            "name": entry.name,
            "type": "tech",
            "category": entry.category.value,
            "when_to_pick": entry.when_to_pick,
            "when_not_to_pick": entry.when_not_to_pick,
            "key_tradeoff": entry.key_tradeoff,
            "extra": entry.throughput_ceiling,
            "citation": entry.citation,
        }
    if isinstance(entry, StrategyEntry):
        return {
            "name": entry.name,
            "type": "strategy",
            "category": entry.applies_to[0] if entry.applies_to else "general",
            "when_to_pick": entry.when_to_use,
            "when_not_to_pick": entry.when_not_to_use,
            "key_tradeoff": entry.key_tradeoff,
            "extra": "",
            "citation": entry.citation,
        }
    # PatternEntry
    return {
        "name": entry.name,
        "type": "pattern",
        "category": "pattern",
        "when_to_pick": entry.when_to_use,
        "when_not_to_pick": entry.when_not_to_use,
        "key_tradeoff": entry.operational_cost,
        "extra": entry.common_mistake,
        "citation": entry.citation,
    }


def _comparison(tech_matches: list[dict]) -> str | None:
    """Generate a head-to-head block when 2+ TechEntries share the same category.

    Only fires for TechEntry matches — comparing strategies or patterns side by side
    is not meaningful without a shared numerical basis.
    """
    by_cat: dict[str, list[dict]] = {}
    for m in tech_matches:
        by_cat.setdefault(m["category"], []).append(m)
    for _cat, group in by_cat.items():
        if len(group) >= 2:
            a, b = group[0], group[1]
            return (
                f"{a['name'].upper()} vs {b['name'].upper()}\n"
                f"  pick {a['name']} when: {a['when_to_pick']}\n"
                f"  pick {b['name']} when: {b['when_to_pick']}\n"
                f"  citations: {a['citation']} | {b['citation']}"
            )
    return None


def search(question: str, top_k: int = 3) -> dict:
    """Find the top-k KB entries most relevant to `question`.

    Returns a dict with keys: matches, comparison, note.
    Returns empty matches (not an error) when nothing scores above THRESHOLD.
    """
    _init()
    assert _MODEL is not None and _ENTRIES is not None and _VECS is not None

    q_vec: np.ndarray = _MODEL.encode([question], normalize_embeddings=True)[0]
    scores = [
        (entry, float(np.dot(q_vec, vec)))
        for entry, vec in zip(_ENTRIES, _VECS)
    ]
    scores.sort(key=lambda x: x[1], reverse=True)

    top_entries = [e for e, s in scores[:top_k] if s >= THRESHOLD]
    normalized = [_normalize(e) for e in top_entries]
    tech_matches = [m for m in normalized if m["type"] == "tech"]

    return {
        "matches": normalized,
        "comparison": _comparison(tech_matches),
        "note": "Brok surfaces trade-offs. You decide.",
    }
