from brok.models import CapacityReport, ComponentType, Utilization
from brok.tradeoffs import TRADEOFFS, get_tradeoff, tradeoffs_for


def test_all_seven_kb_types_have_full_tradeoffs():
    types = [ComponentType.RELATIONAL_DB, ComponentType.CACHE, ComponentType.QUEUE,
             ComponentType.CDN, ComponentType.APP_SERVER, ComponentType.OBJECT_STORE,
             ComponentType.LOAD_BALANCER]
    for t in types:
        to = get_tradeoff(t)
        assert to is not None
        assert to.when_fine and to.gain and to.cost and to.move and to.source


def test_unknown_has_no_tradeoff():
    assert get_tradeoff(ComponentType.UNKNOWN) is None


def test_tradeoffs_for_returns_present_types_deduped_in_order():
    utils = [
        Utilization(component="api", type=ComponentType.APP_SERVER, load_per_sec=1.0,
                    ceiling_per_sec=2000.0, utilization=0.1, estimated=True),
        Utilization(component="db", type=ComponentType.RELATIONAL_DB, load_per_sec=1.0,
                    ceiling_per_sec=1000.0, utilization=0.1, estimated=True),
        Utilization(component="db2", type=ComponentType.RELATIONAL_DB, load_per_sec=1.0,
                    ceiling_per_sec=1000.0, utilization=0.1, estimated=True),
        Utilization(component="mystery", type=ComponentType.UNKNOWN, load_per_sec=0.0,
                    ceiling_per_sec=None, utilization=None, estimated=False),
    ]
    report = CapacityReport(bottleneck="api", max_dau=100, utilizations=utils,
                            assumptions=[], confidence="high", notes=[])
    rows = tradeoffs_for(report)
    assert [r["type"] for r in rows] == ["app_server", "relational_db"]  # deduped, in order, UNKNOWN skipped
    assert "cost" in rows[0] and "move" in rows[0]


def test_no_em_dash_in_kb():
    for to in TRADEOFFS.values():
        for field in (to.when_fine, to.gain, to.cost, to.move, to.source):
            assert "—" not in field
