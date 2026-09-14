"""Authoritative, unit-explicit state types. Display data never grants a verdict."""
from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator

Vec3 = tuple[FiniteFloat, FiniteFloat, FiniteFloat]
Positive = Annotated[FiniteFloat, Field(gt=0)]
Nonnegative = Annotated[FiniteFloat, Field(ge=0)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Verdict(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_RUN = "NOT_RUN"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    BLOCKED = "BLOCKED"


class Provenance(Model):
    source_id: str
    content_hash: str
    step_id: int | None = None
    guid: str | None = None
    kind: Literal["imported", "scenario", "derived"] = "imported"
    description: str = ""


class Bounds(Model):
    min: Vec3
    max: Vec3

    @model_validator(mode="after")
    def ordered(self):
        if any(a > b for a, b in zip(self.min, self.max)):
            raise ValueError("bounds minimum exceeds maximum")
        return self


class Geometry(Model):
    status: Literal["represented", "non_geometric", "unsupported", "invalid", "unresolved"]
    representation: Literal["ifc_brep", "triangle_mesh", "analytic", "none"]
    artifact: str | None = None
    bounds: Bounds | None = None
    approximation_bound_m: Nonnegative | None = None
    transform_error_m: Nonnegative | None = None
    reason: str = ""


class Entity(Model):
    id: str
    name: str = ""
    ifc_type: str
    provenance: Provenance
    geometry: Geometry
    discipline: str = "unclassified"
    storey: str | None = None
    system_ids: tuple[str, ...] = ()
    protected: bool = True
    properties: dict[str, Any] = Field(default_factory=dict)


class Section(Model):
    shape: Literal["circular", "rectangular"]
    diameter_m: Positive | None = None
    width_m: Positive | None = None
    height_m: Positive | None = None
    rotation_rad: FiniteFloat = 0
    insulation_m: Nonnegative = 0

    @model_validator(mode="after")
    def dimensions(self):
        if self.shape == "circular" and self.diameter_m is None:
            raise ValueError("circular section requires diameter_m")
        if self.shape == "rectangular" and (self.width_m is None or self.height_m is None):
            raise ValueError("rectangular section requires width_m and height_m")
        return self


class Port(Model):
    id: str
    entity_id: str | None
    position_m: Vec3 | None
    axis: Vec3 | None = None
    physical_outward_normal: Vec3 | None = None
    axis_convention: str = "HISTORICAL_UNKNOWN"
    owner_placement_status: Literal["OWNER_RELATIVE", "INVALID", "UNVERIFIED", "SCENARIO_NOT_APPLICABLE"] = "UNVERIFIED"
    coordinate_frame: str = "federation"
    position_status: Literal["KNOWN", "MISSING", "INVALID", "UNRESOLVED_FEDERATION"] = "KNOWN"
    ownership_status: Literal["DECLARED", "MISSING", "AMBIGUOUS", "UNVERIFIED"] = "DECLARED"
    direction: Literal["SOURCE", "SINK", "SOURCEANDSINK", "NOTDEFINED"]
    service: str
    section: Section | None = None
    connection_evidence: Literal["explicit_ifc", "scenario", "hypothesis"]
    provenance: Provenance

    @model_validator(mode="after")
    def position_obligation(self):
        if self.position_status == "KNOWN" and self.position_m is None:
            raise ValueError("Known port position requires actual coordinates")
        return self


class Demand(Model):
    id: str
    source_port: str
    sink_ports: tuple[str, ...]
    service: str
    section: Section
    required_flow_m3_s: Positive | None = None
    min_slope: Nonnegative | None = None
    clearance_m: Nonnegative = 0
    maintenance_clearance_m: Nonnegative = 0
    provenance: Provenance


class Fitting(Model):
    id: str
    kind: Literal["elbow", "tee", "reducer", "transition", "joint"]
    position_m: Vec3
    catalog_id: str
    bend_radius_m: Positive | None = None
    geometry_artifact: str
    connection_ids: tuple[str, ...]


class Route(Model):
    id: str
    demand_ids: tuple[str, ...]
    service: str
    points_m: tuple[Vec3, ...]
    section: Section
    fittings: tuple[Fitting, ...] = ()
    port_ids: tuple[str, ...] = ()
    shared_trunk_id: str | None = None
    geometry_artifact: str | None = None
    status: Literal["CANDIDATE", "MATERIALIZED", "CHECKED"] = "CANDIDATE"

    @model_validator(mode="after")
    def nonempty(self):
        if len(self.points_m) < 2:
            raise ValueError("route requires at least two points")
        if any(a == b for a, b in zip(self.points_m, self.points_m[1:])):
            raise ValueError("route has zero-length segment")
        return self


class NumericalPolicy(Model):
    units: Literal["m"] = "m"
    absolute_tolerance_m: Positive = 1e-6
    ambiguity_band_m: Nonnegative = 1e-5
    touching_policy: Literal["forbidden_unless_authorized"] = "forbidden_unless_authorized"
    mesh_clearance_requires_error_bound: bool = True


class PhysicalNetwork(Model):
    id: str
    demand_ids: tuple[str, ...]
    component_ids: tuple[str, ...]
    port_ids: tuple[str, ...]
    service: str
    section: Section
    geometry_artifact: str
    status: Literal["MATERIALIZED", "CHECKED"] = "MATERIALIZED"


class Mission(Model):
    id: str
    demands: tuple[Demand, ...]
    protected_ids: tuple[str, ...]
    editable_ids: tuple[str, ...] = ()
    allowed_zones: tuple[Bounds, ...] = ()
    rule_hash: str
    catalog_hash: str
    scenario_hash: str
    objective_weights: dict[str, Nonnegative] = Field(default_factory=lambda: {"length_m": 1})
    assumptions: tuple[str, ...] = ()


class EngineeringState(Model):
    schema_version: Literal[1] = 1
    project_id: str
    units: Literal["m"] = "m"
    sources: tuple[dict[str, Any], ...] = ()
    entities: tuple[Entity, ...] = ()
    ports: tuple[Port, ...] = ()
    routes: tuple[Route, ...] = ()
    physical_networks: tuple[PhysicalNetwork, ...] = ()
    explicit_connections: tuple[tuple[str, str], ...] = ()
    inferred_connections: tuple[dict[str, Any], ...] = ()
    mission: Mission | None = None
    numerical_policy: NumericalPolicy = NumericalPolicy()
    assumptions: tuple[dict[str, Any], ...] = ()
    dependencies: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    derived_artifacts: dict[str, dict[str, Any]] = Field(default_factory=dict)


class CheckResult(Model):
    id: str
    status: Verdict
    reason: str
    scope: str
    participants: tuple[str, ...] = ()
    witness: dict[str, Any] = Field(default_factory=dict)


class VerificationReport(Model):
    schema_version: Literal[1] = 1
    candidate_root: str
    mission_hash: str
    rule_hash: str
    checker_version: str
    status: Verdict
    scope: str
    results: tuple[CheckResult, ...]
    objective: dict[str, FiniteFloat]
    common_mode_risks: tuple[str, ...] = ()
    created_at: str

    @model_validator(mode="after")
    def no_vacuous_pass(self):
        if self.status == Verdict.PASS:
            if not self.results or any(r.status not in (Verdict.PASS, Verdict.NOT_APPLICABLE) for r in self.results):
                raise ValueError("PASS requires a nonempty, complete successful check set")
        return self
