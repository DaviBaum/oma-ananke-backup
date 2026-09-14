from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator

from oma.models import Bounds, Vec3


class RoutingScenario(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    start: Vec3
    end: Vec3
    system_type: Literal["PRESSURE_PIPE", "GRAVITY_DRAINAGE", "ROUND_DUCT", "FIRE_PROTECTION"]
    diameter_m: FiniteFloat = Field(gt=0)
    insulation_m: FiniteFloat = Field(ge=0)
    bend_radius_m: FiniteFloat = Field(gt=0)
    minimum_straight_m: FiniteFloat = Field(ge=0)
    clearance_m: FiniteFloat = Field(ge=0)
    allowed_zone: Bounds
    source_id: str | None = None
    source_port_guid: str | None = None
    sink_port_guid: str | None = None
    scenario_terminals: bool = False
    min_slope: FiniteFloat | None = Field(default=None, ge=0)
    provenance: str = "user_supplied_scenario"
    source: str = "api"
    assumptions: list[str] = Field(default_factory=list)
    target_modality: Literal["LOCAL_GEOMETRIC_COORDINATION", "ENGINEERING_SERVICE"] = "LOCAL_GEOMETRIC_COORDINATION"
    source_representation_policy: Literal[
        "NATIVE_CAD_WITH_EXACT_PLANAR_ENCLOSURES",
        "NATIVE_CAD_WITH_SOURCE_VERTEX_HULL_ENCLOSURES",
    ] = "NATIVE_CAD_WITH_EXACT_PLANAR_ENCLOSURES"
    physics: dict[str, Any] | None = None
    objective_weights: dict[str, FiniteFloat] = Field(default_factory=lambda: {"length_m": 1.0, "fitting_count": 0.0})
    search_step_m: FiniteFloat = Field(default=.25, gt=0)
    max_candidates: int = Field(default=12, ge=1, le=100)

    @property
    def outer_radius(self):
        return self.diameter_m / 2 + self.insulation_m

    @model_validator(mode="after")
    def physical(self):
        if self.start == self.end:
            raise ValueError("Start and terminal cannot coincide")
        if not self.scenario_terminals and not (self.source_port_guid and self.sink_port_guid):
            raise ValueError("Provide explicit source/sink IFC ports or explicitly authorize scenario terminals")
        if self.bend_radius_m <= self.outer_radius:
            raise ValueError("Bend radius must exceed the insulated outer radius")
        if any(w < 0 for w in self.objective_weights.values()) or not any(self.objective_weights.values()):
            raise ValueError("Objective priorities must be nonnegative and at least one positive")
        if any(k not in {"length_m", "fitting_count"} for k in self.objective_weights):
            raise ValueError("This route model supports measured length and fitting count objectives only")
        for point in (self.start, self.end):
            if any(p - self.outer_radius < lo or p + self.outer_radius > hi for p, lo, hi in zip(point, self.allowed_zone.min, self.allowed_zone.max)):
                raise ValueError("A terminal's full physical envelope lies outside the permitted zone")
        if self.system_type == "GRAVITY_DRAINAGE":
            if self.min_slope is None:
                raise ValueError("Gravity drainage requires explicit minimum slope")
            if self.end[2] >= self.start[2]:
                raise ValueError("Gravity sink must be lower than the source in this direction convention")
        return self
