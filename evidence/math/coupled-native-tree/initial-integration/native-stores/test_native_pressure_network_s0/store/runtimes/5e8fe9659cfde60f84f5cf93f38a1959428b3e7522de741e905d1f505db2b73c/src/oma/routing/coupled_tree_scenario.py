"""Explicit unequal-outlet, inlet-flow quadratic tree boundary contract."""
from fractions import Fraction as Q
from typing import Annotated, Literal

from pydantic import Field, model_validator

from oma.models import Model
from .passive_tree_scenario import Exact, Identity


class ExactInterval(Model):
    lower: Exact
    upper: Exact

    @model_validator(mode="after")
    def ordered(self):
        if Q(self.lower) > Q(self.upper):
            raise ValueError("Reversed exact boundary interval")
        return self


class TeeOutletLoss(Model):
    b: Exact
    branch: Exact

    @model_validator(mode="after")
    def positive(self):
        if min(Q(self.b), Q(self.branch)) <= 0:
            raise ValueError("Both explicit inlet-flow tee outlet coefficients must be positive")
        return self


class CoupledTreeBoundary(Model):
    schema_: Literal["oma.coupled-tree-boundary/1"] = Field(default="oma.coupled-tree-boundary/1", alias="schema")
    source_total_pressure_pa: ExactInterval
    sink_total_pressures_pa: dict[Identity, ExactInterval] = Field(min_length=2, max_length=32)
    minimum_sink_flows_m3_s: dict[Identity, Exact] = Field(min_length=2, max_length=32)
    flow_search_box_m3_s: dict[Identity, ExactInterval] = Field(min_length=2, max_length=32)
    density_kg_m3: Exact
    darcy_friction: Exact
    maximum_velocity_m_s: Exact
    gravity_m_s2: Exact
    elbow_loss_coefficient: Exact
    tee_outlet_loss_coefficients: dict[Identity, TeeOutletLoss] = Field(min_length=1, max_length=31)
    applicability: Annotated[str, Field(min_length=1, max_length=4096)]
    boundary_control_assumption: Annotated[str, Field(min_length=1, max_length=4096)]
    pressure_reference: Literal["TOTAL_PRESSURE_P_PLUS_KINETIC_EXCLUDING_ELEVATION"]
    loss_model: Literal["FIXED_COEFFICIENT_STEADY_INCOMPRESSIBLE"]
    hydraulic_section_interpretation: Literal["IDEAL_CIRCULAR_BORE_FROM_NATIVE_ENVELOPE_MINUS_DECLARED_INSULATION"]
    friction_convention: Literal["DARCY"]
    elbow_loss_reference: Literal["EXCESS_LOCAL_LOSS_EXCLUDING_CURVED_PIPE_FRICTION"]
    tee_loss_reference: Literal["OUTLET_SPECIFIC_TOTAL_LOSS_AT_TOTAL_INLET_FLOW"]
    connection_model: Literal["NO_EXTRA_LOSS_AT_CHECKED_MATCHING_CONNECTED_CAPS"]
    boundary_loss_scope: Literal["BETWEEN_PHYSICAL_NETWORK_PORTS_ONLY"]

    @model_validator(mode="after")
    def domains(self):
        leaves = set(self.sink_total_pressures_pa)
        if set(self.minimum_sink_flows_m3_s) != leaves or set(self.flow_search_box_m3_s) != leaves:
            raise ValueError("Every sink needs exact pressure, minimum and proof-proposal box")
        if min(Q(self.density_kg_m3), Q(self.darcy_friction), Q(self.maximum_velocity_m_s)) <= 0:
            raise ValueError("Density, Darcy friction and velocity limit must be positive")
        if min(Q(self.gravity_m_s2), Q(self.elbow_loss_coefficient)) < 0:
            raise ValueError("Gravity and elbow excess loss must be nonnegative")
        if any(Q(v) <= 0 for v in self.minimum_sink_flows_m3_s.values()):
            raise ValueError("Every minimum delivery must be positive")
        if any(not 0 < Q(v.lower) < Q(v.upper) for v in self.flow_search_box_m3_s.values()):
            raise ValueError("Every flow proof-proposal interval must be strictly positive and nondegenerate")
        return self
