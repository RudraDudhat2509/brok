from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class ComponentType(str, Enum):
    RELATIONAL_DB = "relational_db"
    CACHE = "cache"
    QUEUE = "queue"
    CDN = "cdn"
    APP_SERVER = "app_server"
    OBJECT_STORE = "object_store"
    LOAD_BALANCER = "load_balancer"
    UNKNOWN = "unknown"


class Component(BaseModel):
    name: str
    type: ComponentType


class NFRs(BaseModel):
    dau: int
    requests_per_user_per_day: int
    read_write_ratio: float  # reads per write
    payload_kb: float
    peak_factor: float


class DesignGraph(BaseModel):
    components: list[Component] = Field(default_factory=list)
    nfrs: NFRs | None = None


class Utilization(BaseModel):
    component: str
    type: ComponentType
    load_per_sec: float
    ceiling_per_sec: float | None
    utilization: float | None
    estimated: bool


class CapacityReport(BaseModel):
    bottleneck: str | None
    max_dau: int | None
    utilizations: list[Utilization] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    confidence: str
    notes: list[str] = Field(default_factory=list)
