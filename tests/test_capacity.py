from sindri.models import Component, ComponentType, DesignGraph, NFRs
from sindri.lenses.capacity import analyze_capacity, peak_rps


def _nfrs(dau):
    return NFRs(dau=dau, requests_per_user_per_day=50, read_write_ratio=10.0,
               payload_kb=50.0, peak_factor=3.0)


def test_peak_rps_math():
    # 100k * 50 / 86400 * 3 ~= 173.6
    assert round(peak_rps(_nfrs(100_000)), 1) == 173.6


def test_db_is_bottleneck_when_writes_exceed_ceiling():
    g = DesignGraph(components=[Component(name="db", type=ComponentType.RELATIONAL_DB)])
    # crank DAU so writes/sec >> 1000 ceiling
    rep = analyze_capacity(g, _nfrs(50_000_000), [], "high")
    assert rep.bottleneck == "db"
    assert rep.max_dau is not None and rep.max_dau < 50_000_000


def test_cache_absorbs_reads_off_the_db():
    g_no_cache = DesignGraph(components=[Component(name="db", type=ComponentType.RELATIONAL_DB)])
    g_cache = DesignGraph(components=[
        Component(name="db", type=ComponentType.RELATIONAL_DB),
        Component(name="cache", type=ComponentType.CACHE),
    ])
    nfrs = _nfrs(2_000_000)
    db_util_no_cache = next(u.utilization for u in analyze_capacity(g_no_cache, nfrs, [], "high").utilizations if u.component == "db")
    db_util_cache = next(u.utilization for u in analyze_capacity(g_cache, nfrs, [], "high").utilizations if u.component == "db")
    # with a cache, the db no longer carries reads, so its utilization is lower
    assert db_util_cache < db_util_no_cache


def test_unknown_component_is_not_fabricated():
    g = DesignGraph(components=[Component(name="mystery", type=ComponentType.UNKNOWN)])
    rep = analyze_capacity(g, _nfrs(100_000), [], "high")
    u = next(u for u in rep.utilizations if u.component == "mystery")
    assert u.ceiling_per_sec is None and u.utilization is None
    assert any("mystery" in n for n in rep.notes)
