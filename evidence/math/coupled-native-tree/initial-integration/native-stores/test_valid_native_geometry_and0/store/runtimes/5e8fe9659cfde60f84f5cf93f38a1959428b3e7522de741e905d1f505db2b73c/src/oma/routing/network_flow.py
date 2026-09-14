"""Demand-conditioned equal-round tree energy accounting, with rational bounds.

The fixed flows are inputs, not an operating-point solution. Tee loss factors
include the entire fitting and use inlet velocity; elbow factors exclude the
separately counted curved-pipe friction. No pump, compressibility or terminal
equipment loss is introduced implicitly.
"""
from __future__ import annotations

from fractions import Fraction

from oma.optimization.master import rational
from oma.optimization.physical import Interval, as_interval, bounded_le, combine_verdicts, pi_interval


def evaluate_network_flow(scenario, network, component_lengths, terminal_positions, *, component_outer_radii=None):
    missing = []
    if scenario.physics is None:
        missing.append("physics")
    for sink in scenario.sinks:
        for key in ("required_flow_m3_s", "available_static_pressure_pa"):
            if getattr(sink, key) is None:
                missing.append(f"sinks.{sink.id}.{key}")
    components = {c.id: c for c in network.components}
    if set(component_lengths) != set(components):
        missing.append("complete_native_component_lengths")
    if component_outer_radii is None or set(component_outer_radii) != set(components):
        missing.append("complete_native_component_outer_radii")
    if (not terminal_positions or set(terminal_positions) != {"source", "sinks"}
            or set(terminal_positions.get("sinks", {})) != {s.id for s in scenario.sinks}):
        missing.append("complete_native_terminal_positions")
    if missing:
        return {"verdict": "BLOCKED", "missing": missing, "model": "fixed_flow_equal_round_tree"}
    lengths = {cid: as_interval(value) for cid, value in component_lengths.items()}
    if any(value.lo < 0 for value in lengths.values()):
        raise ValueError("Native length enclosures must be nonnegative")
    radii = {cid: as_interval(value) for cid, value in component_outer_radii.items()}
    insulation = rational(scenario.insulation_m)
    diameters = {cid: 2 * (radius - insulation) for cid, radius in radii.items()}
    if any(value.lo <= 0 for value in diameters.values()):
        return {"verdict": "UNKNOWN", "missing": ["positive_native_hydraulic_bore_enclosure"],
            "model": "fixed_flow_equal_round_tree",
            "reason": "A current native outer-radius enclosure does not establish a positive ideal bore after declared insulation"}
    areas = {cid: pi_interval() * diameter.square() / 4 for cid, diameter in diameters.items()}
    physics = scenario.physics
    sinks = {s.id: s for s in scenario.sinks}
    paths = {p.sink_id: p for p in network.demand_paths}
    # Model validation establishes exact path coverage; sum every distinct
    # downstream demand, preserving multiplicity of physically distinct sinks.
    inlet_flow = {cid: Fraction(0) for cid in components}
    port_flow = {cid: {p: Fraction(0) for p in c.ports} for cid, c in components.items()}
    for sid, path in paths.items():
        flow = rational(sinks[sid].required_flow_m3_s)
        for step in path.steps:
            inlet_flow[step.component] += flow
            port_flow[step.component][step.entry_port] += flow
            port_flow[step.component][step.exit_port] += flow
    density = rational(physics.density_kg_m3)
    friction = rational(physics.darcy_friction)
    velocity = {cid: {p: Interval.point(q) / areas[cid] for p, q in flows.items()} for cid, flows in port_flow.items()}
    component_records, checks = {}, []
    for cid, component in components.items():
        conserved = port_flow[cid]["a"] == sum(q for p, q in port_flow[cid].items() if p != "a")
        verdicts = {p: bounded_le(v, physics.maximum_velocity_m_s) for p, v in velocity[cid].items()}
        verdicts["conservation"] = "PASS" if conserved else "FAIL"
        checks.extend(verdicts.values())
        component_records[cid] = {"kind": component.kind, "flow_m3_s": {p: str(q) for p, q in port_flow[cid].items()},
            "velocity_m_s": {p: v.encoded() for p, v in velocity[cid].items()}, "checks": verdicts}
    connection_checks = []
    for link in network.connections:
        a, b = link.source, link.sink
        conserved = port_flow[a.component][a.port] == port_flow[b.component][b.port]
        checks.append("PASS" if conserved else "FAIL")
        connection_checks.append({"source": a.model_dump(), "sink": b.model_dump(), "status": "PASS" if conserved else "FAIL"})
    source_velocity = velocity[network.source.component][network.source.port]
    source_z = as_interval(terminal_positions["source"][2])
    path_records = {}
    for sid, path in paths.items():
        irreversible = Interval.point(0)
        terms = []
        for step in path.steps:
            component = components[step.component]
            v = velocity[step.component]["a"]
            if component.kind == "tee":
                coefficient = physics.tee_straight_loss_coefficient if step.exit_port == "b" else physics.tee_branch_loss_coefficient
                factor = Interval.point(coefficient)
                convention = "TOTAL_TEE_LOSS_AT_INLET_VELOCITY"
            else:
                coefficient = physics.elbow_loss_coefficient if component.kind == "elbow" else 0
                factor = friction * lengths[step.component] / diameters[step.component] + coefficient
                convention = "DARCY_LENGTH_PLUS_EXCESS_LOCAL_LOSS"
            loss = factor * density * v.square() / 2
            irreversible += loss
            terms.append({"component": step.component, "entry_port": step.entry_port, "exit_port": step.exit_port,
                          "loss_pa": loss.encoded(), "convention": convention})
        sink_endpoint = next(s.endpoint for s in network.sinks if s.id == sid)
        sink_velocity = velocity[sink_endpoint.component][sink_endpoint.port]
        elevation = density * rational(physics.gravity_m_s2) * (as_interval(terminal_positions["sinks"][sid][2]) - source_z)
        kinetic = density / 2 * (rational(physics.sink_kinetic_energy_correction) * sink_velocity.square()
                   - rational(physics.source_kinetic_energy_correction) * source_velocity.square())
        required_pressure = irreversible + elevation + kinetic
        verdict = bounded_le(required_pressure, sinks[sid].available_static_pressure_pa)
        checks.append(verdict)
        path_records[sid] = {"demand_id": sinks[sid].demand_id, "terms": terms,
            "irreversible_loss_pa": irreversible.encoded(), "elevation_pressure_pa": elevation.encoded(),
            "kinetic_pressure_pa": kinetic.encoded(), "required_source_minus_sink_static_pressure_pa": required_pressure.encoded(),
            "available_source_minus_sink_static_pressure_pa": str(rational(sinks[sid].available_static_pressure_pa)), "status": verdict}
    return {"verdict": combine_verdicts(checks), "missing": [], "model": "fixed_flow_equal_round_tree",
        "components": component_records, "connections": connection_checks, "paths": path_records,
        "source_flow_m3_s": str(sum((rational(s.required_flow_m3_s) for s in scenario.sinks), Fraction(0))),
        "unique_physical_components": len(components), "arithmetic": "exact_rational_enclosures_given_supplied_length_bounds",
        "section_model": {
            "hydraulic_section_interpretation": "IDEAL_CIRCULAR_BORE_FROM_NATIVE_ENVELOPE_MINUS_DECLARED_INSULATION",
            "component_outer_radii_m": {cid: value.encoded() for cid, value in radii.items()},
            "component_hydraulic_diameters_m": {cid: value.encoded() for cid, value in diameters.items()},
            "component_section_areas_m2": {cid: value.encoded() for cid, value in areas.items()},
            "native_inner_bore_or_wall_thickness_measured": False,
            "native_metric_bounds_are_supplied": True,
            "native_geometry_rechecked_by_this_function": False,
            "scope": "Declared equal-round ideal-bore model, with current component-specific native section uncertainty; physical wall, reducer and loss applicability remain assumptions"},
        "model_inputs": physics.model_dump(), "scope": "Required head and velocity at explicitly supplied simultaneous sink flows between the physical network ports",
        "operating_point_solution": "NOT_ESTABLISHED", "terminal_equipment_and_pumps": "OUTSIDE_MODEL",
        "geometry_and_fitting_catalog_applicability": "SEPARATELY_REQUIRED"}
