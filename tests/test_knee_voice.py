from brok.models import CapacityReport, ComponentType, Utilization
from brok.voice import classify, render_roast


def _report(util, max_dau=1_000_000, assumptions=None):
    u = Utilization(component="db", type=ComponentType.RELATIONAL_DB,
                    load_per_sec=util * 1000, ceiling_per_sec=1000.0,
                    utilization=util, estimated=True)
    return CapacityReport(bottleneck="db", max_dau=max_dau, utilizations=[u],
                          assumptions=assumptions or [], confidence="high", notes=[])


def test_knee_band_is_degrading():
    assert classify(_report(0.85)) == "degrading"
    assert classify(_report(0.7)) == "degrading"


def test_below_knee_still_fits():
    assert classify(_report(0.5)) == "fits"


def test_over_cap_unchanged():
    assert classify(_report(3.0)) == "bad"


def test_degrading_card_shows_multiplier_and_safe_dau():
    card = render_roast(_report(0.8, max_dau=1_000_000))
    assert "CUTTING IT CLOSE" in card
    assert "5.0" in card          # 1/(1-0.8) latency multiplier
    assert "700,000" in card      # safe_dau = max_dau * 0.7
    assert "—" not in card
