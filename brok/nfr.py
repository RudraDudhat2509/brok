from __future__ import annotations

from brok.models import NFRs

DEFAULT_NFRS = NFRs(
    dau=100_000, requests_per_user_per_day=50, read_write_ratio=10.0,
    payload_kb=50.0, peak_factor=3.0,
)

_LABELS = {
    "dau": "daily active users",
    "requests_per_user_per_day": "requests per user per day",
    "read_write_ratio": "reads per write",
    "payload_kb": "KB per request",
    "peak_factor": "peak-to-average traffic factor",
}


def resolve_nfrs(partial: dict | None) -> tuple[NFRs, list[str]]:
    partial = partial or {}
    merged = DEFAULT_NFRS.model_dump()
    assumptions: list[str] = []
    for field, default_value in DEFAULT_NFRS.model_dump().items():
        if field in partial and partial[field] is not None:
            merged[field] = partial[field]
        else:
            assumptions.append(f"Assumed {default_value:,} {_LABELS[field]}.")
    return NFRs(**merged), assumptions
