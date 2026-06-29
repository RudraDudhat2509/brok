from brok.models import CapacityReport, ComponentType, Utilization
from brok.voice import classify, roast_line


def _util(name, ctype, util):
    return Utilization(component=name, type=ctype, load_per_sec=8000.0,
                       ceiling_per_sec=1000.0, utilization=util, estimated=True)


def _report(bottleneck, max_dau, util, ctype=ComponentType.RELATIONAL_DB,
            confidence="high", assumptions=None):
    utils = [_util(bottleneck, ctype, util)] if bottleneck else []
    return CapacityReport(bottleneck=bottleneck, max_dau=max_dau, utilizations=utils,
                          assumptions=assumptions or [], confidence=confidence, notes=[])


def test_classify_buckets():
    assert classify(_report("db", 12000, 8.0)) == "brutal"
    assert classify(_report("db", 30000, 3.0)) == "bad"
    assert classify(_report("db", 90000, 1.4)) == "slight"
    assert classify(_report("db", 5_000_000, 0.2)) == "fits"
    assert classify(_report(None, None, None)) == "insufficient"


def test_classify_hedges_when_dau_assumed():
    r = _report("db", 12000, 8.0, confidence="low",
                assumptions=["Assumed 100,000 daily active users."])
    assert classify(r) == "low_conf_over"


def test_roast_line_contains_the_numbers():
    line = roast_line(_report("orders-db", 12000, 8.0))
    assert "orders-db" in line
    assert "12,000" in line
    assert "8" in line  # the over factor


def test_roast_line_deterministic():
    r = _report("db", 12000, 8.0)
    assert roast_line(r) == roast_line(r)


def test_roast_line_insufficient_has_no_fabricated_number():
    line = roast_line(_report(None, None, None))
    assert "numbers" in line.lower() or "design" in line.lower()


def test_no_em_dash_in_any_template():
    from brok.voice import BROK_LINES
    for lines in BROK_LINES.values():
        for t in lines:
            assert "—" not in t
