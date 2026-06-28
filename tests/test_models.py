from sindri.models import (
    ComponentType, Component, NFRs, DesignGraph, Utilization, CapacityReport,
)


def test_component_holds_type():
    c = Component(name="orders-db", type=ComponentType.RELATIONAL_DB)
    assert c.type is ComponentType.RELATIONAL_DB


def test_nfrs_fields():
    n = NFRs(dau=100_000, requests_per_user_per_day=50, read_write_ratio=10.0,
             payload_kb=50.0, peak_factor=3.0)
    assert n.dau == 100_000


def test_design_graph_defaults_no_nfrs():
    g = DesignGraph(components=[Component(name="db", type=ComponentType.RELATIONAL_DB)])
    assert g.nfrs is None
    assert len(g.components) == 1


def test_capacity_report_round_trips():
    r = CapacityReport(bottleneck="db", max_dau=12_000, utilizations=[],
                       assumptions=["assumed 100k DAU"], confidence="low", notes=[])
    assert r.bottleneck == "db"
    assert r.max_dau == 12_000
