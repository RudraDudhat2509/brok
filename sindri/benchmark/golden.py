from __future__ import annotations

from pydantic import BaseModel

from sindri.models import Component, ComponentType, DesignGraph, NFRs


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
