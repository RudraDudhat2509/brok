from brok.models import CapacityReport, ComponentType, Utilization
from brok.voice import render_roast


def _report(bottleneck, max_dau, util, confidence="high", assumptions=None, notes=None):
    utils = ([Utilization(component=bottleneck, type=ComponentType.RELATIONAL_DB,
                          load_per_sec=8000.0, ceiling_per_sec=1000.0,
                          utilization=util, estimated=True)] if bottleneck else [])
    return CapacityReport(bottleneck=bottleneck, max_dau=max_dau, utilizations=utils,
                          assumptions=assumptions or [], confidence=confidence,
                          notes=notes or [])


def test_card_leads_with_brok_headline_and_roasts():
    card = render_roast(_report("db", 12000, 8.0))
    assert card.splitlines()[0].startswith("BROK:")
    assert "WALK AWAY" in card
    assert "db" in card and "12,000" in card


def test_card_shows_fits_when_under():
    card = render_roast(_report("db", 5_000_000, 0.2))
    assert "IT HOLDS" in card


def test_card_shows_assumptions_and_single_confidence():
    card = render_roast(_report("db", 12000, 8.0, confidence="low",
                                assumptions=["Assumed 100,000 daily active users."]))
    assert "Assumed 100,000 daily active users." in card
    assert card.count("Confidence:") == 1


def test_card_lists_not_estimated_notes():
    card = render_roast(_report(None, None, None,
                                notes=["mystery (unknown) is outside the KB."]))
    assert "Not estimated" in card and "mystery" in card


def test_card_has_no_em_dash():
    assert "—" not in render_roast(_report("db", 12000, 8.0))
