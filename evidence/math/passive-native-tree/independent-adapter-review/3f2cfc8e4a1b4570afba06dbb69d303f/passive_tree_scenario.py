"""Explicit new common-outlet passive tree contract; old missions unchanged."""
from __future__ import annotations

from fractions import Fraction
import re
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, model_validator

from oma.models import Model


def _exact(value):
    if type(value) not in (str, int) or type(value) is bool:
        raise ValueError("Use exact integer or rational strings for the passive tree contract")
    if type(value) is int and value.bit_length() > 512:
        raise ValueError("Contract rational exceeds 512 bits")
    if type(value) is str and (len(value) > 320 or not re.fullmatch(r"[+-]?[0-9]+(?:/[0-9]+|\.[0-9]+)?", value)):
        raise ValueError("Malformed or oversized contract rational")
    q = Fraction(value)
    if max(abs(q.numerator).bit_length(), q.denominator.bit_length()) > 512:
        raise ValueError("Contract rational exceeds 512 bits")
    return str(q)


Exact = Annotated[str, BeforeValidator(_exact)]
Identity = Annotated[str, Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.:-]+$")]


class PassiveTreeBoundary(Model):
    schema_: Literal["oma.passive-tree-boundary/1"] = Field(default="oma.passive-tree-boundary/1", alias="schema")
    source_total_pressure_pa: Exact
    sink_total_pressures_pa: dict[Identity, Exact] = Field(min_length=2, max_length=32)
    minimum_sink_flows_m3_s: dict[Identity, Exact] = Field(min_length=2, max_length=32)
    density_kg_m3: Exact
    darcy_friction: Exact
    maximum_velocity_m_s: Exact
    gravity_m_s2: Exact
    elbow_loss_coefficient: Exact
    tee_common_loss_coefficients: dict[Identity, Exact] = Field(min_length=1, max_length=31)
    applicability: Annotated[str, Field(min_length=1, max_length=4096)]
    boundary_control_assumption: Annotated[str, Field(min_length=1, max_length=4096)]
    pressure_reference: Literal["TOTAL_PRESSURE_P_PLUS_KINETIC_EXCLUDING_ELEVATION"]
    loss_model: Literal["FIXED_COEFFICIENT_STEADY_INCOMPRESSIBLE"]
    hydraulic_section_interpretation: Literal["IDEAL_CIRCULAR_BORE_FROM_NATIVE_ENVELOPE_MINUS_DECLARED_INSULATION"]
    friction_convention: Literal["DARCY"]
    elbow_loss_reference: Literal["EXCESS_LOCAL_LOSS_EXCLUDING_CURVED_PIPE_FRICTION"]
    tee_loss_reference: Literal["IDENTICAL_OUTLET_TOTAL_LOSS_AT_INLET_FLOW_COMMON_HEAD"]
    connection_model: Literal["NO_EXTRA_LOSS_AT_CHECKED_MATCHING_CONNECTED_CAPS"]
    boundary_loss_scope: Literal["BETWEEN_PHYSICAL_NETWORK_PORTS_ONLY"]

    @model_validator(mode="after")
    def positive_domains(self):
        if set(self.sink_total_pressures_pa) != set(self.minimum_sink_flows_m3_s):
            raise ValueError("Every sink needs its pressure and minimum delivery")
        if min(Fraction(self.density_kg_m3), Fraction(self.darcy_friction), Fraction(self.maximum_velocity_m_s)) <= 0:
            raise ValueError("Density, Darcy friction and velocity limit must be positive")
        if min(Fraction(self.gravity_m_s2), Fraction(self.elbow_loss_coefficient)) < 0:
            raise ValueError("Gravity and elbow excess loss must be nonnegative")
        if any(Fraction(x) <= 0 for x in [*self.minimum_sink_flows_m3_s.values(), *self.tee_common_loss_coefficients.values()]):
            raise ValueError("Minimum delivery and every common tee coefficient must be positive")
        return self
