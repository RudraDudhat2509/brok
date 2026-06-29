from __future__ import annotations

# Utilization past which queueing latency climbs sharply (M/M/1 knee).
KNEE: float = 0.7


def latency_multiplier(util: float | None) -> float | None:
    """Relative latency vs the idle baseline under M/M/1 queueing: 1 / (1 - rho).

    None when utilization is unknown, negative, or at/over capacity. At or past
    1.0 the component is saturated and latency is not a finite multiple of the
    baseline, so Brok declines to put a number on it rather than fabricate one.
    """
    if util is None or util < 0 or util >= 1.0:
        return None
    return 1.0 / (1.0 - util)
