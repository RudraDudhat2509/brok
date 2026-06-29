from __future__ import annotations

from pydantic import BaseModel

from brok.models import ComponentType


class Capability(BaseModel):
    write_low: float | None
    write_high: float | None
    read_low: float | None
    read_high: float | None
    source: str


# Conservative ranges, ops/sec, single instance. Verdicts use the LOW end.
CAPABILITY_KB: dict[ComponentType, Capability] = {
    ComponentType.RELATIONAL_DB: Capability(
        write_low=1000, write_high=1875, read_low=5000, read_high=10000,
        source="Postgres single-primary benchmarks: ~1.1k-1.9k w/s ceiling, "
               "plan change at 500+ (dev.to/haikasatryan PG write perf, 2025)",
    ),
    ComponentType.CACHE: Capability(
        write_low=80000, write_high=100000, read_low=100000, read_high=1000000,
        source="Redis benchmarks: ~100k ops/s single instance, 1M+ pipelined "
               "(redis.io optimization/benchmarks)",
    ),
    ComponentType.QUEUE: Capability(
        write_low=100000, write_high=1000000, read_low=100000, read_high=1000000,
        source="Kafka performance: ~millions msg/s per cluster "
               "(developer.confluent.io/learn/kafka-performance)",
    ),
    ComponentType.CDN: Capability(
        write_low=None, write_high=None, read_low=1000000, read_high=10000000,
        source="CDN: massive read fan-out; writes do not belong on a CDN.",
    ),
    ComponentType.APP_SERVER: Capability(
        write_low=2000, write_high=8000, read_low=2000, read_high=8000,
        source="Single app instance: low thousands RPS typical (order-of-magnitude).",
    ),
    ComponentType.OBJECT_STORE: Capability(
        write_low=3500, write_high=5500, read_low=5500, read_high=20000,
        source="Object store (S3-class) per-prefix: ~3.5k w/s, ~5.5k r/s "
               "(order-of-magnitude).",
    ),
    ComponentType.LOAD_BALANCER: Capability(
        write_low=10000, write_high=50000, read_low=10000, read_high=50000,
        source="L7 load balancer: tens of thousands RPS per node "
               "(order-of-magnitude).",
    ),
}


def get_capability(t: ComponentType) -> Capability | None:
    return CAPABILITY_KB.get(t)
