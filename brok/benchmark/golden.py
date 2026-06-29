from __future__ import annotations

from pydantic import BaseModel

from brok.models import Component, ComponentType, DesignGraph, NFRs


class GoldenCase(BaseModel):
    name: str
    source_url: str
    category: str  # "consistency" | "behavior" | "out_of_model"
    components: list[tuple[str, str]]
    nfrs: dict
    expected_bottleneck_type: str | None
    expected_capacity_dau: int | None
    expect_overload: bool
    scored_for_accuracy: bool
    note: str

    def to_graph(self) -> DesignGraph:
        comps = []
        for name, type_value in self.components:
            try:
                ctype = ComponentType(type_value)
            except ValueError:
                ctype = ComponentType.UNKNOWN
            comps.append(Component(name=name, type=ctype))
        return DesignGraph(components=comps)

    def to_nfrs(self) -> NFRs:
        return NFRs(**self.nfrs)


GOLDEN_CASES: list[GoldenCase] = [
    # ---- consistency: pipeline must reproduce the cited ceilings ----
    GoldenCase(
        name="single-postgres-no-cache-write-wall",
        source_url="https://dev.to/haikasatryan/postgresql-write-performance-what-the-benchmarks-wont-tell-you-mm7",
        category="consistency",
        components=[("app", "app_server"), ("db", "relational_db")],
        nfrs={"dau": 500000, "requests_per_user_per_day": 50,
              "read_write_ratio": 10.0, "payload_kb": 50.0, "peak_factor": 3.0},
        expected_bottleneck_type="relational_db",
        expected_capacity_dau=576000,
        expect_overload=False,
        scored_for_accuracy=True,
        note="No cache: Postgres carries all traffic at the cited ~1k/s low end. "
             "Wall = 1000*86400/150 = 576000 DAU. Derived from the cited ceiling.",
    ),
    GoldenCase(
        name="app-tier-is-the-wall-with-cache",
        source_url="https://bytebytego.com/courses/system-design-interview/back-of-the-envelope-estimation",
        category="consistency",
        components=[("api", "app_server"), ("db", "relational_db"), ("cache", "cache")],
        nfrs={"dau": 2000000, "requests_per_user_per_day": 50,
              "read_write_ratio": 10.0, "payload_kb": 50.0, "peak_factor": 3.0},
        expected_bottleneck_type="app_server",
        expected_capacity_dau=1152000,
        expect_overload=True,
        scored_for_accuracy=True,
        note="Cache absorbs reads, so the single app instance (ceiling ~2k/s) is the "
             "wall before the DB. Wall = 2000*86400/150 = 1152000 DAU.",
    ),
    GoldenCase(
        name="write-heavy-db-wall-even-with-cache",
        source_url="https://en.wikipedia.org/wiki/Little's_law",
        category="consistency",
        components=[("api", "app_server"), ("db", "relational_db"), ("cache", "cache")],
        nfrs={"dau": 500000, "requests_per_user_per_day": 50,
              "read_write_ratio": 0.5, "payload_kb": 50.0, "peak_factor": 3.0},
        expected_bottleneck_type="relational_db",
        expected_capacity_dau=864000,
        expect_overload=False,
        scored_for_accuracy=True,
        note="Write-heavy (rw=0.5): a cache cannot save the write path, so the DB is "
             "the wall. Wall = 1000*1.5*86400/150 = 864000 DAU.",
    ),
    # ---- behavior: abstain, and do not cry wolf ----
    GoldenCase(
        name="abstain-on-unknown-only",
        source_url="https://modelcontextprotocol.io/",
        category="behavior",
        components=[("mystery", "cassandra")],
        nfrs={"dau": 100000, "requests_per_user_per_day": 50,
              "read_write_ratio": 10.0, "payload_kb": 50.0, "peak_factor": 3.0},
        expected_bottleneck_type=None,
        expected_capacity_dau=None,
        expect_overload=False,
        scored_for_accuracy=True,
        note="An all-unknown graph must abstain: no fabricated bottleneck.",
    ),
    GoldenCase(
        name="tiny-hobby-app-fits",
        source_url="https://bytebytego.com/courses/system-design-interview/back-of-the-envelope-estimation",
        category="behavior",
        components=[("app", "app_server"), ("db", "relational_db")],
        nfrs={"dau": 1000, "requests_per_user_per_day": 50,
              "read_write_ratio": 10.0, "payload_kb": 50.0, "peak_factor": 3.0},
        expected_bottleneck_type="relational_db",
        expected_capacity_dau=576000,
        expect_overload=False,
        scored_for_accuracy=False,
        note="A 1k-user app must NOT be roasted as overloaded. Do not cry wolf.",
    ),
    # ---- out of model: documented real systems Brok v1 cannot fully judge ----
    GoldenCase(
        name="instagram-2011-volume-bound",
        source_url="https://read.engineerscodex.com/p/how-instagram-scaled-to-14-million",
        category="out_of_model",
        components=[("django", "app_server"), ("db", "relational_db"), ("memcache", "cache")],
        nfrs={"dau": 14000000, "requests_per_user_per_day": 10,
              "read_write_ratio": 10.0, "payload_kb": 50.0, "peak_factor": 2.0},
        expected_bottleneck_type=None,
        expected_capacity_dau=None,
        expect_overload=False,
        scored_for_accuracy=False,
        note="Instagram sharded Postgres at ~14M users due to DATA VOLUME + connection "
             "overhead + hot rows, at only ~115 writes/s. Brok (single-instance, "
             "uniform-traffic) flags the app tier at ~1.6x overloaded, and its Postgres "
             "write throughput is fine. Neither matches the real historical wall (volume), "
             "which is outside v1's throughput model. Documented, not graded.",
    ),
    GoldenCase(
        name="discord-message-store-hot-partition",
        source_url="https://discord.com/blog/how-discord-stores-trillions-of-messages",
        category="out_of_model",
        components=[("api", "app_server"), ("messages", "cassandra")],
        nfrs={"dau": 5000000, "requests_per_user_per_day": 200,
              "read_write_ratio": 5.0, "payload_kb": 1.0, "peak_factor": 3.0},
        expected_bottleneck_type=None,
        expected_capacity_dau=None,
        expect_overload=False,
        scored_for_accuracy=False,
        note="Discord's real wall was a READ hot-partition on Cassandra (unknown to the KB, "
             "so Brok abstains on that store). Under uniform-traffic Brok flags the api "
             "app_server as heavily overloaded. Hot partitions are a Plan 4 anti-pattern, "
             "not a v1 throughput verdict. Documented, not graded.",
    ),
]
