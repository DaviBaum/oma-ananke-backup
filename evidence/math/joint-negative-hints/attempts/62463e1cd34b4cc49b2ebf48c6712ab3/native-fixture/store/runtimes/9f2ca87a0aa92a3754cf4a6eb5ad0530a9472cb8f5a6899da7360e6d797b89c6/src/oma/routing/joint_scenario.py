"""Explicit finite choices for simultaneous route design; no inferred freedom."""
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .scenario import RoutingScenario


class RouteDemandOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.:-]+$")
    alternatives: list[RoutingScenario] = Field(min_length=1, max_length=16)


class JointRoutingScenario(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    route_demands: list[RouteDemandOptions] = Field(min_length=1, max_length=16)
    max_joint_candidates: int = Field(default=32, ge=1, le=256)
    max_paths_per_alternative: int = Field(default=4, ge=1, le=32)

    @model_validator(mode="after")
    def unique(self):
        if len({d.id for d in self.route_demands}) != len(self.route_demands):
            raise ValueError("Joint demand identifiers must be unique")
        weights = self.route_demands[0].alternatives[0].objective_weights
        for demand in self.route_demands:
            if any(s.authorized_opening is not None for s in demand.alternatives):
                raise ValueError("An opening requires the single-route imported-baseline edit contract")
            if any(s.objective_weights != weights for s in demand.alternatives):
                raise ValueError("All simultaneous alternatives must use the same objective policy")
            fixed = ("system_type", "clearance_m", "target_modality", "min_slope", "physics", "source_representation_policy", "scenario_terminals")
            first = demand.alternatives[0]
            if any(any(getattr(s, key) != getattr(first, key) for key in fixed) for s in demand.alternatives):
                raise ValueError("Design alternatives must preserve service, loads, clearance, slope and assurance requirements")
        return self


def parse_joint_request(raw):
    if "route_demands" in raw:
        return JointRoutingScenario.model_validate(raw)
    return JointRoutingScenario(route_demands=[RouteDemandOptions(id="additional-route", alternatives=[RoutingScenario.model_validate(raw)])])
