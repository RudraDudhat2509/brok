from brok.models import ComponentType
from brok.benchmark.golden import GoldenCase


def _case(**kw):
    base = dict(
        name="x", source_url="http://example.com", category="consistency",
        components=[("app", "app_server"), ("db", "relational_db")],
        nfrs={"dau": 500000, "requests_per_user_per_day": 50,
              "read_write_ratio": 10.0, "payload_kb": 50.0, "peak_factor": 3.0},
        expected_bottleneck_type="relational_db", expected_capacity_dau=576000,
        expect_overload=False, scored_for_accuracy=True, note="n")
    base.update(kw)
    return GoldenCase(**base)


def test_to_graph_maps_types():
    g = _case().to_graph()
    by = {c.name: c.type for c in g.components}
    assert by["db"] is ComponentType.RELATIONAL_DB
    assert by["app"] is ComponentType.APP_SERVER


def test_unknown_type_string_maps_to_unknown():
    g = _case(components=[("mystery", "cassandra")]).to_graph()
    assert g.components[0].type is ComponentType.UNKNOWN


def test_to_nfrs_round_trips():
    n = _case().to_nfrs()
    assert n.dau == 500000 and n.read_write_ratio == 10.0
