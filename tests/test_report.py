from brok.models import CapacityReport, ComponentType, Utilization
from brok.report import render_report


def _util(name, util):
    return Utilization(component=name, type=ComponentType.RELATIONAL_DB,
                       load_per_sec=8000.0, ceiling_per_sec=1000.0,
                       utilization=util, estimated=True)


def test_report_leads_with_assumptions():
    r = CapacityReport(bottleneck="db", max_dau=12_000, utilizations=[_util("db", 8.0)],
                       assumptions=["Assumed 100,000 daily active users."],
                       confidence="low", notes=[])
    out = render_report(r)
    assert "Assumed 100,000 daily active users." in out


def test_report_states_bottleneck_and_max_dau():
    r = CapacityReport(bottleneck="db", max_dau=12_000, utilizations=[_util("db", 8.0)],
                       assumptions=[], confidence="high", notes=[])
    out = render_report(r)
    assert "db" in out
    assert "12,000" in out


def test_report_says_fits_when_no_overload():
    r = CapacityReport(bottleneck="db", max_dau=5_000_000,
                       utilizations=[_util("db", 0.2)], assumptions=[],
                       confidence="high", notes=[])
    out = render_report(r)
    assert "fits" in out.lower() or "holds" in out.lower()


def test_report_lists_not_estimated_notes():
    r = CapacityReport(bottleneck=None, max_dau=None, utilizations=[],
                       assumptions=[], confidence="low",
                       notes=["mystery (unknown) is outside the KB, so it was not estimated."])
    out = render_report(r)
    assert "mystery" in out


def test_report_has_no_em_dash():
    r = CapacityReport(bottleneck="db", max_dau=12_000, utilizations=[_util("db", 8.0)],
                       assumptions=[], confidence="high", notes=[])
    assert "—" not in render_report(r)


def test_confidence_appears_exactly_once_with_assumptions_and_overload():
    r = CapacityReport(bottleneck="db", max_dau=12_000,
                       utilizations=[_util("db", 2.5)],
                       assumptions=["Assumed 100,000 daily active users."],
                       confidence="low", notes=[])
    assert render_report(r).count("Confidence:") == 1


def test_confidence_appears_exactly_once_with_no_assumptions():
    r = CapacityReport(bottleneck="db", max_dau=12_000,
                       utilizations=[_util("db", 2.5)],
                       assumptions=[],
                       confidence="high", notes=[])
    assert render_report(r).count("Confidence:") == 1
