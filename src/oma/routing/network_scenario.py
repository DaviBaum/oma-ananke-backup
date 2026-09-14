"""Explicit finite physical trees. Geometry proposals carry no checking authority."""
from __future__ import annotations

import math
from typing import Annotated, Literal

import numpy as np
from pydantic import Field, model_validator

from oma.models import Bounds, Model, Nonnegative, Positive, Vec3

Identifier = Annotated[str, Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.:-]+$")]
Service = Literal["PRESSURE_PIPE", "ROUND_DUCT", "FIRE_PROTECTION"]
Slot = Literal["a", "b", "branch"]
Matrix = tuple[tuple[float, float, float, float], tuple[float, float, float, float],
               tuple[float, float, float, float], tuple[float, float, float, float]]


class Endpoint(Model):
    component: Identifier
    port: Slot

    def key(self):
        return self.component, self.port


class SegmentGeometry(Model):
    start_m: Vec3
    end_m: Vec3


class ElbowGeometry(Model):
    center_m: Vec3
    start_m: Vec3
    end_m: Vec3
    normal: Vec3
    bend_radius_m: Positive
    angle_rad: Annotated[float, Field(gt=0, lt=math.pi, allow_inf_nan=False)]


class TeeGeometry(Model):
    frame_m: Matrix
    trunk_takeout_m: Positive
    branch_takeout_m: Positive

    @model_validator(mode="after")
    def rigid(self):
        frame = np.asarray(self.frame_m)
        if (not np.isfinite(frame).all() or not np.allclose(frame[3], [0, 0, 0, 1], atol=1e-12, rtol=0)
                or not np.allclose(frame[:3, :3].T @ frame[:3, :3], np.eye(3), atol=1e-10, rtol=0)
                or abs(np.linalg.det(frame[:3, :3]) - 1) > 1e-10):
            raise ValueError("Tee frame must be a finite proper rigid transform")
        return self


class Component(Model):
    id: Identifier
    system_type: Service
    diameter_m: Positive
    insulation_m: Nonnegative
    ports: dict[Slot, Literal["SINK", "SOURCE"]]

    @property
    def outer_radius(self):
        return self.diameter_m / 2 + self.insulation_m

    @model_validator(mode="after")
    def roles(self):
        expected = {"a": "SINK", "b": "SOURCE"}
        if self.kind == "tee":
            expected["branch"] = "SOURCE"
        if self.ports != expected:
            raise ValueError("Distribution component requires its declared inlet and outlet slots")
        return self


class Segment(Component):
    kind: Literal["segment"]
    geometry: SegmentGeometry

    @model_validator(mode="after")
    def nonzero(self):
        if math.dist(self.geometry.start_m, self.geometry.end_m) <= 1e-6:
            raise ValueError("Segment must have positive resolvable length")
        return self


class Elbow(Component):
    kind: Literal["elbow"]
    geometry: ElbowGeometry

    @model_validator(mode="after")
    def bend(self):
        g = self.geometry
        a, b = np.array(g.start_m) - g.center_m, np.array(g.end_m) - g.center_m
        normal = np.asarray(g.normal)
        if (g.bend_radius_m <= self.outer_radius or abs(np.linalg.norm(normal) - 1) > 1e-10
                or any(abs(np.linalg.norm(v) - g.bend_radius_m) > 1e-7 or abs(v @ normal) > 1e-7 for v in (a, b))):
            raise ValueError("Elbow endpoints and normal do not define the declared circle")
        rotated = a * math.cos(g.angle_rad) + np.cross(normal, a) * math.sin(g.angle_rad)
        if np.linalg.norm(rotated - b) > 1e-7:
            raise ValueError("Elbow endpoint does not match its directed arc")
        return self


class Tee(Component):
    kind: Literal["tee"]
    geometry: TeeGeometry

    @model_validator(mode="after")
    def takeouts(self):
        if min(self.geometry.trunk_takeout_m, self.geometry.branch_takeout_m) <= self.outer_radius + 1e-6:
            raise ValueError("Tee takeouts must leave its three exterior caps separate")
        return self


PhysicalComponent = Annotated[Segment | Elbow | Tee, Field(discriminator="kind")]


class Connection(Model):
    source: Endpoint
    sink: Endpoint


class Sink(Model):
    id: Identifier
    endpoint: Endpoint


class PathStep(Model):
    component: Identifier
    entry_port: Slot
    exit_port: Slot


class DemandPath(Model):
    demand_id: Identifier
    sink_id: Identifier
    steps: tuple[PathStep, ...] = Field(min_length=1, max_length=512)


def proposed_cap(component, port):
    """Proposal geometry only; the native checker reconstructs the actual caps."""
    g = component.geometry
    if component.kind == "tee":
        local = {"a": [-g.trunk_takeout_m, 0, 0], "b": [g.trunk_takeout_m, 0, 0],
                 "branch": [0, g.branch_takeout_m, 0]}[port]
        frame = np.asarray(g.frame_m)
        return tuple(frame[:3, :3] @ local + frame[:3, 3])
    return g.start_m if port == "a" else g.end_m


class NetworkDesign(Model):
    schema_: Literal["oma-physical-network/1"] = Field(default="oma-physical-network/1", alias="schema")
    network_id: Identifier
    system_type: Service
    components: tuple[PhysicalComponent, ...] = Field(min_length=1, max_length=512)
    connections: tuple[Connection, ...] = Field(max_length=511)
    source: Endpoint
    sinks: tuple[Sink, ...] = Field(min_length=2, max_length=32)
    demand_paths: tuple[DemandPath, ...] = Field(min_length=2, max_length=32)

    @model_validator(mode="after")
    def tree(self):
        components = {c.id: c for c in self.components}
        if len(components) != len(self.components) or any(c.system_type != self.system_type for c in self.components):
            raise ValueError("Network component IDs must be unique and service-compatible")
        slots = {(c.id, p): role for c in self.components for p, role in c.ports.items()}
        used, incoming, outgoing = set(), {}, {}
        for link in self.connections:
            a, b = link.source.key(), link.sink.key()
            if slots.get(a) != "SOURCE" or slots.get(b) != "SINK" or a in used or b in used or a[0] == b[0]:
                raise ValueError("Connections require unique SOURCE-to-SINK slots on distinct components")
            ca, cb = components[a[0]], components[b[0]]
            if (ca.diameter_m, ca.insulation_m) != (cb.diameter_m, cb.insulation_m):
                raise ValueError("Connected equal-round sections must match; reducers need a separate catalog")
            if math.dist(proposed_cap(ca, a[1]), proposed_cap(cb, b[1])) > 1e-7:
                raise ValueError("Connected proposal caps do not coincide")
            used.update((a, b))
            incoming[b[0]], outgoing[a] = link, b
        if slots.get(self.source.key()) != "SINK" or self.source.key() in used:
            raise ValueError("One unconnected physical inlet is required")
        used.add(self.source.key())
        sink_ids = set()
        for sink in self.sinks:
            key = sink.endpoint.key()
            if sink.id in sink_ids or slots.get(key) != "SOURCE" or key in used:
                raise ValueError("Unique sink IDs must name remaining unconnected physical outlets")
            sink_ids.add(sink.id)
            used.add(key)
        if used != set(slots):
            raise ValueError("Every physical slot must be a connection or an authorized terminal")
        if len(self.connections) != len(components) - 1:
            raise ValueError("The physical component graph must be a tree")
        seen, pending = set(), [self.source.component]
        while pending:
            cid = pending.pop()
            if cid in seen:
                raise ValueError("Physical component graph has a directed cycle")
            seen.add(cid)
            pending.extend(b[0] for a, b in outgoing.items() if a[0] == cid)
        if seen != set(components):
            raise ValueError("All components must be reachable from the single source")
        paths = {p.sink_id: p for p in self.demand_paths}
        if set(paths) != sink_ids or len(paths) != len(self.demand_paths) or len({p.demand_id for p in paths.values()}) != len(paths):
            raise ValueError("Every sink requires one unique complete demand path")
        for sink in self.sinks:
            endpoint, expected = sink.endpoint, []
            while True:
                expected.append((endpoint.component, "a", endpoint.port))
                if endpoint.component == self.source.component:
                    break
                link = incoming.get(endpoint.component)
                if link is None:
                    raise ValueError("Demand path cannot reach the source")
                endpoint = link.source
            actual = [(p.component, p.entry_port, p.exit_port) for p in paths[sink.id].steps]
            if actual != list(reversed(expected)):
                raise ValueError("Demand path must exactly match the physical tree's oriented slots")
        return self


class SinkRequirement(Model):
    id: Identifier
    demand_id: Identifier
    end_m: Vec3
    required_flow_m3_s: Positive | None = None
    available_static_pressure_pa: Nonnegative | None = None


class NetworkPhysics(Model):
    density_kg_m3: Positive
    darcy_friction: Nonnegative
    maximum_velocity_m_s: Positive
    gravity_m_s2: Nonnegative
    elbow_loss_coefficient: Nonnegative
    tee_straight_loss_coefficient: Nonnegative
    tee_branch_loss_coefficient: Nonnegative
    source_kinetic_energy_correction: Positive
    sink_kinetic_energy_correction: Positive
    applicability: Annotated[str, Field(min_length=1)]
    fixed_flow_control_assumption: Annotated[str, Field(min_length=1)]
    friction_convention: Literal["DARCY"]
    elbow_loss_reference: Literal["EXCESS_LOCAL_LOSS_EXCLUDING_CURVED_PIPE_FRICTION"]
    tee_loss_reference: Literal["INLET_VELOCITY_TOTAL_IRREVERSIBLE_LOSS"]
    boundary_loss_scope: Literal["BETWEEN_PHYSICAL_NETWORK_PORTS_ONLY"]


class SharedNetworkScenario(Model):
    mission_type: Literal["shared_network"]
    source_id: Identifier | None = None
    system_type: Service
    start_m: Vec3
    sinks: tuple[SinkRequirement, ...] = Field(min_length=2, max_length=32)
    diameter_m: Positive
    insulation_m: Nonnegative
    clearance_m: Nonnegative
    minimum_straight_m: Nonnegative
    minimum_bend_radius_m: Positive
    allowed_zone: Bounds
    scenario_terminals: Literal[True]
    target_modality: Literal["LOCAL_GEOMETRIC_COORDINATION", "ENGINEERING_SERVICE"]
    source_representation_policy: Literal["NATIVE_CAD_WITH_EXACT_PLANAR_ENCLOSURES", "NATIVE_CAD_WITH_SOURCE_VERTEX_HULL_ENCLOSURES"]
    network_alternatives: tuple[NetworkDesign, ...] = Field(min_length=1, max_length=32)
    physics: NetworkPhysics | None = None
    objective_weights: dict[Literal["length_m", "fitting_count"], Nonnegative] = Field(default_factory=lambda: {"length_m": 1.})
    assumptions: tuple[str, ...] = ()

    @model_validator(mode="after")
    def fixed_contract(self):
        required = {s.id: s for s in self.sinks}
        if len(required) != len(self.sinks) or len({s.demand_id for s in self.sinks}) != len(self.sinks):
            raise ValueError("Sink and demand identities must be unique")
        if len({n.network_id for n in self.network_alternatives}) != len(self.network_alternatives):
            raise ValueError("Network alternative identities must be unique")
        if not any(self.objective_weights.values()):
            raise ValueError("At least one positive objective weight is required")
        for network in self.network_alternatives:
            components = {c.id: c for c in network.components}
            if network.system_type != self.system_type or {s.id for s in network.sinks} != set(required):
                raise ValueError("Alternatives must preserve fixed service and sink coverage")
            if math.dist(proposed_cap(components[network.source.component], network.source.port), self.start_m) > 1e-7:
                raise ValueError("Alternative moved the fixed source terminal")
            for sink in network.sinks:
                if math.dist(proposed_cap(components[sink.endpoint.component], sink.endpoint.port), required[sink.id].end_m) > 1e-7:
                    raise ValueError("Alternative moved a fixed sink terminal")
            if any(p.demand_id != required[p.sink_id].demand_id for p in network.demand_paths):
                raise ValueError("Alternative changed the sink's fixed demand identity")
            for c in network.components:
                if (c.diameter_m, c.insulation_m) != (self.diameter_m, self.insulation_m):
                    raise ValueError("Alternative changed the fixed circular section")
                if c.kind == "segment" and math.dist(c.geometry.start_m, c.geometry.end_m) < self.minimum_straight_m:
                    raise ValueError("Alternative violates minimum straight length")
                if c.kind == "elbow" and c.geometry.bend_radius_m < self.minimum_bend_radius_m:
                    raise ValueError("Alternative violates minimum bend radius")
        return self


def network_requirements(baseline, scenario):
    """Canonical requirement projection; contains no geometry or solver verdict."""
    from oma.models import Demand, Mission, Port, Provenance, Section
    from oma.store import digest
    raw = scenario.model_dump(mode="json", by_alias=True)
    scenario_hash = digest(raw)
    prefix = f"scenario-network:{scenario_hash[:20]}"
    section = Section(shape="circular", diameter_m=scenario.diameter_m, insulation_m=scenario.insulation_m)
    provenance = Provenance(source_id=f"scenario:{scenario_hash}", content_hash=scenario_hash,
        kind="scenario", description="Explicit hypothetical network terminals and fixed demands")
    terminals = [(f"{prefix}:source", scenario.start_m, "SOURCE")]
    terminals += [(f"{prefix}:sink:{s.id}", s.end_m, "SINK") for s in scenario.sinks]
    ports = [Port(id=pid, entity_id=None, position_m=point, direction=role, service=scenario.system_type,
        section=section, connection_evidence="scenario", provenance=provenance,
        ownership_status="UNVERIFIED", owner_placement_status="SCENARIO_NOT_APPLICABLE") for pid, point, role in terminals]
    demands = [Demand(id=s.demand_id, source_port=ports[0].id, sink_ports=(ports[i+1].id,),
        service=scenario.system_type, section=section, required_flow_m3_s=s.required_flow_m3_s,
        clearance_m=scenario.clearance_m, provenance=provenance) for i, s in enumerate(scenario.sinks)]
    rule = {"clearance_m": scenario.clearance_m, "allowed_zone": scenario.allowed_zone.model_dump(),
        "target_modality": scenario.target_modality, "source_representation_policy": scenario.source_representation_policy,
        "physics": raw["physics"], "numerical_policy": baseline.get("numerical_policy", {})}
    catalog = {"section": section.model_dump(mode="json"), "minimum_straight_m": scenario.minimum_straight_m,
        "minimum_bend_radius_m": scenario.minimum_bend_radius_m, "component_alternatives": raw["network_alternatives"]}
    mission = Mission(id=f"mission:{prefix}", demands=tuple(demands), protected_ids=tuple(e["id"] for e in baseline.get("entities", [])),
        allowed_zones=(scenario.allowed_zone,), rule_hash=digest(rule), catalog_hash=digest(catalog), scenario_hash=scenario_hash,
        objective_weights=scenario.objective_weights, assumptions=scenario.assumptions)
    return mission.model_dump(mode="json"), [p.model_dump(mode="json") for p in ports], section.model_dump(mode="json")
