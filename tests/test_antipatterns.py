import pytest
from brok.linters.antipatterns import lint
from brok.models import Component, ComponentType, DesignGraph, NFRs
from brok.nfr import DEFAULT_NFRS


def _nfrs(**kwargs) -> NFRs:
    return DEFAULT_NFRS.model_copy(update=kwargs)


def _graph(*types: ComponentType) -> DesignGraph:
    return DesignGraph(components=[Component(name=t.value, type=t) for t in types])


# --- WRITE_TO_CDN ---

def test_cdn_with_writes_flagged():
    graph = _graph(ComponentType.CDN, ComponentType.APP_SERVER, ComponentType.RELATIONAL_DB)
    codes = [a.code for a in lint(graph, _nfrs(read_write_ratio=3.0))]
    assert "WRITE_TO_CDN" in codes

def test_cdn_read_heavy_not_flagged():
    graph = _graph(ComponentType.CDN, ComponentType.APP_SERVER)
    codes = [a.code for a in lint(graph, _nfrs(read_write_ratio=10.0))]
    assert "WRITE_TO_CDN" not in codes

def test_no_cdn_not_flagged_for_writes():
    graph = _graph(ComponentType.APP_SERVER, ComponentType.RELATIONAL_DB)
    codes = [a.code for a in lint(graph, _nfrs(read_write_ratio=3.0))]
    assert "WRITE_TO_CDN" not in codes


# --- NO_LOAD_BALANCER ---

def test_multiple_app_servers_no_lb_flagged():
    graph = DesignGraph(components=[
        Component(name="api-1", type=ComponentType.APP_SERVER),
        Component(name="api-2", type=ComponentType.APP_SERVER),
        Component(name="db", type=ComponentType.RELATIONAL_DB),
    ])
    codes = [a.code for a in lint(graph, DEFAULT_NFRS)]
    assert "NO_LOAD_BALANCER" in codes

def test_multiple_app_servers_with_lb_ok():
    graph = DesignGraph(components=[
        Component(name="api-1", type=ComponentType.APP_SERVER),
        Component(name="api-2", type=ComponentType.APP_SERVER),
        Component(name="lb", type=ComponentType.LOAD_BALANCER),
    ])
    codes = [a.code for a in lint(graph, DEFAULT_NFRS)]
    assert "NO_LOAD_BALANCER" not in codes

def test_single_app_server_no_lb_ok():
    graph = _graph(ComponentType.APP_SERVER, ComponentType.RELATIONAL_DB)
    codes = [a.code for a in lint(graph, DEFAULT_NFRS)]
    assert "NO_LOAD_BALANCER" not in codes


# --- UNPROTECTED_DB ---

def test_read_heavy_db_no_cache_flagged():
    graph = _graph(ComponentType.APP_SERVER, ComponentType.RELATIONAL_DB)
    codes = [a.code for a in lint(graph, _nfrs(read_write_ratio=9.0, dau=500_000))]
    assert "UNPROTECTED_DB" in codes

def test_db_with_cache_not_flagged():
    graph = _graph(ComponentType.APP_SERVER, ComponentType.RELATIONAL_DB, ComponentType.CACHE)
    codes = [a.code for a in lint(graph, _nfrs(read_write_ratio=9.0, dau=500_000))]
    assert "UNPROTECTED_DB" not in codes

def test_write_heavy_db_no_flag():
    graph = _graph(ComponentType.APP_SERVER, ComponentType.RELATIONAL_DB)
    codes = [a.code for a in lint(graph, _nfrs(read_write_ratio=1.0, dau=500_000))]
    assert "UNPROTECTED_DB" not in codes

def test_small_scale_db_no_flag():
    graph = _graph(ComponentType.APP_SERVER, ComponentType.RELATIONAL_DB)
    codes = [a.code for a in lint(graph, _nfrs(read_write_ratio=9.0, dau=50_000))]
    assert "UNPROTECTED_DB" not in codes


# --- render integration ---

def test_render_antipatterns_shows_in_roast():
    from brok.pipeline import review_from_components
    result = review_from_components(
        [
            {"name": "api-1", "type": "app_server"},
            {"name": "api-2", "type": "app_server"},
            {"name": "db", "type": "relational_db"},
        ],
        traffic={"dau": 500_000, "read_write_ratio": 9.0},
    )
    assert "STRUCTURAL ISSUES" in result["roast_text"]
    assert "NO_LOAD_BALANCER" in result["roast_text"]
    assert result["antipatterns"]

# --- CONNECTION_POOL_RISK ---

def test_three_app_servers_db_flagged():
    graph = DesignGraph(components=[
        Component(name="api-1", type=ComponentType.APP_SERVER),
        Component(name="api-2", type=ComponentType.APP_SERVER),
        Component(name="api-3", type=ComponentType.APP_SERVER),
        Component(name="db", type=ComponentType.RELATIONAL_DB),
    ])
    codes = [a.code for a in lint(graph, DEFAULT_NFRS)]
    assert "CONNECTION_POOL_RISK" in codes

def test_two_app_servers_db_not_flagged():
    graph = DesignGraph(components=[
        Component(name="api-1", type=ComponentType.APP_SERVER),
        Component(name="api-2", type=ComponentType.APP_SERVER),
        Component(name="db", type=ComponentType.RELATIONAL_DB),
    ])
    codes = [a.code for a in lint(graph, DEFAULT_NFRS)]
    assert "CONNECTION_POOL_RISK" not in codes

def test_three_app_servers_no_db_not_flagged():
    graph = DesignGraph(components=[
        Component(name="api-1", type=ComponentType.APP_SERVER),
        Component(name="api-2", type=ComponentType.APP_SERVER),
        Component(name="api-3", type=ComponentType.APP_SERVER),
        Component(name="cache", type=ComponentType.CACHE),
    ])
    codes = [a.code for a in lint(graph, DEFAULT_NFRS)]
    assert "CONNECTION_POOL_RISK" not in codes


# --- DATA_VOLUME_WALL ---

def test_high_dau_db_no_object_store_flagged():
    graph = _graph(ComponentType.APP_SERVER, ComponentType.RELATIONAL_DB)
    codes = [a.code for a in lint(graph, _nfrs(dau=5_000_000))]
    assert "DATA_VOLUME_WALL" in codes

def test_high_dau_db_with_object_store_ok():
    graph = _graph(ComponentType.APP_SERVER, ComponentType.RELATIONAL_DB, ComponentType.OBJECT_STORE)
    codes = [a.code for a in lint(graph, _nfrs(dau=5_000_000))]
    assert "DATA_VOLUME_WALL" not in codes

def test_low_dau_db_no_object_store_ok():
    graph = _graph(ComponentType.APP_SERVER, ComponentType.RELATIONAL_DB)
    codes = [a.code for a in lint(graph, _nfrs(dau=1_000_000))]
    assert "DATA_VOLUME_WALL" not in codes


def test_clean_design_no_structural_issues():
    from brok.pipeline import review_from_components
    result = review_from_components(
        [
            {"name": "lb", "type": "load_balancer"},
            {"name": "api", "type": "app_server"},
            {"name": "cache", "type": "cache"},
            {"name": "db", "type": "relational_db"},
        ],
        traffic={"dau": 500_000, "read_write_ratio": 9.0},
    )
    assert "STRUCTURAL ISSUES" not in result["roast_text"]
    assert result["antipatterns"] == []
