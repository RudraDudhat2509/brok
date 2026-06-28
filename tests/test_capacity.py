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


def test_all_unknown_graph_has_no_bottleneck():
    # All UNKNOWN components → no scored utilizations → bottleneck and max_dau both None.
    g = DesignGraph(components=[
        Component(name="thing1", type=ComponentType.UNKNOWN),
        Component(name="thing2", type=ComponentType.UNKNOWN),
    ])
    rep = analyze_capacity(g, _nfrs(100_000), [], "low")
    assert rep.bottleneck is None
    assert rep.max_dau is None


def test_cdn_only_graph_is_not_scored():
    # CDN carries 0 load in v1; after the fix it must have utilization=None and
    # must not be elected as bottleneck.
    g = DesignGraph(components=[Component(name="cdn", type=ComponentType.CDN)])
    rep = analyze_capacity(g, _nfrs(100_000), [], "low")
    u = next(u for u in rep.utilizations if u.component == "cdn")
    assert u.utilization is None
    assert u.estimated is False
    assert rep.bottleneck is None
    assert rep.max_dau is None


def test_unknown_never_bottleneck_alongside_db():
    # A graph with a RELATIONAL_DB (under load) and an UNKNOWN component:
    # the bottleneck must be the DB, never the unknown.
    g = DesignGraph(components=[
        Component(name="db", type=ComponentType.RELATIONAL_DB),
        Component(name="mystery", type=ComponentType.UNKNOWN),
    ])
    rep = analyze_capacity(g, _nfrs(50_000_000), [], "high")
    assert rep.bottleneck == "db"


def test_max_dau_is_dau_independent():
    # For a DB-bottlenecked graph, max_dau = dau / utilization.
    # utilization = load / ceiling, and load scales linearly with dau,
    # so max_dau = dau / (load(dau) / ceiling) = ceiling / (load_per_dau).
    # Therefore max_dau must be independent of the dau used to compute it.
    g = DesignGraph(components=[Component(name="db", type=ComponentType.RELATIONAL_DB)])
    nfrs_a = _nfrs(1_000_000)
    nfrs_b = _nfrs(2_000_000)
    rep_a = analyze_capacity(g, nfrs_a, [], "high")
    rep_b = analyze_capacity(g, nfrs_b, [], "high")
    assert rep_a.max_dau is not None and rep_b.max_dau is not None
    assert abs(rep_a.max_dau - rep_b.max_dau) <= 1
