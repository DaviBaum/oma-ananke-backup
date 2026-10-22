"""Source-bound two-outlet pressure model; native geometry remains a prerequisite.

Boundary pressures include kinetic pressure and exclude elevation. Elevation is
subtracted using the independently reconstructed native terminal coordinates.
Loss coefficients and boundary control are supplied engineering assumptions.
"""
from __future__ import annotations

import copy
from fractions import Fraction

from oma.optimization.master import rational
from oma.optimization.physical import Interval, as_interval, circular_section, combine_verdicts
from oma.store import digest
from .network_scenario import NetworkDesign, SharedNetworkScenario


def _encoded(value):
    return {"lower": str(value.lo), "upper": str(value.hi)}


def _decoded(value):
    return Interval(Fraction(value["lower"]), Fraction(value["upper"]))


def _le(left, right):
    left, right = as_interval(left), as_interval(right)
    return "PASS" if left.hi <= right.lo else "FAIL" if left.lo > right.hi else "UNKNOWN"


def partition_two_sink_tree(network):
    """Reparse wiring/path obligations and account for every physical component."""
    network = NetworkDesign.model_validate(network.model_dump(mode="json", by_alias=True))
    components = {c.id: c for c in network.components}
    tees = [c.id for c in network.components if c.kind == "tee"]
    if len(tees) != 1 or len(network.sinks) != 2:
        raise ValueError("Operating-point model requires exactly one tee and two outlets")
    tee = tees[0]
    paths = {p.sink_id: p for p in network.demand_paths}
    common, branches, exits = None, {}, {}
    for sid in sorted(paths):
        steps = paths[sid].steps
        indices = [i for i, step in enumerate(steps) if step.component == tee]
        if len(indices) != 1:
            raise ValueError("Each complete outlet path must traverse the unique tee once")
        index = indices[0]
        prefix = [step.component for step in steps[:index]]
        branch = [step.component for step in steps[index + 1:]]
        if common is not None and prefix != common:
            raise ValueError("Outlet paths must share the same oriented trunk before the tee")
        common = prefix
        branches[sid], exits[sid] = branch, steps[index].exit_port
    if set(exits.values()) != {"b", "branch"}:
        raise ValueError("Each distinct tee outlet requires exactly one branch")
    accounted = [*common, tee, *(cid for branch in branches.values() for cid in branch)]
    if len(accounted) != len(set(accounted)) or set(accounted) != set(components):
        raise ValueError("Trunk, tee and two exclusive branches must account for every component once")
    return {"tee": tee, "common_trunk": common, "branches": branches,
            "tee_exit_ports": exits, "component_ids": sorted(components)}


def derive_two_sink_pressure_model(scenario, network, component_lengths, terminal_positions, *, component_outer_radii, context):
    """Build coefficient enclosures from complete current native metric inputs."""
    from oma.optimization.two_sink_pressure import MODEL_ASSUMPTIONS

    scenario = SharedNetworkScenario.model_validate(scenario.model_dump(mode="json", by_alias=True))
    if scenario.pressure_driven is None:
        raise ValueError("No explicit pressure-driven boundary contract was supplied")
    raw_network = network.model_dump(mode="json", by_alias=True)
    if raw_network not in [n.model_dump(mode="json", by_alias=True) for n in scenario.network_alternatives]:
        raise ValueError("The pressure model network is not an authorized complete alternative")
    partition = partition_two_sink_tree(network)
    components = {c.id: c for c in network.components}
    if set(component_lengths) != set(components):
        raise ValueError("Every unique physical component requires its current native length enclosure")
    lengths = {cid: as_interval(value) for cid, value in component_lengths.items()}
    if any(value.lo < 0 for value in lengths.values()):
        raise ValueError("Native component lengths must have nonnegative bounds")
    branch_ids = sorted(partition["branches"])
    if set(terminal_positions) != {"source", "sinks"} or set(terminal_positions["sinks"]) != set(branch_ids):
        raise ValueError("Complete current native source and outlet coordinates are required")
    positions = {"source": [as_interval(v) for v in terminal_positions["source"]],
                 "sinks": {sid: [as_interval(v) for v in terminal_positions["sinks"][sid]] for sid in branch_ids}}
    if len(positions["source"]) != 3 or any(len(v) != 3 for v in positions["sinks"].values()):
        raise ValueError("Every terminal requires three SI coordinate enclosures")
    if not isinstance(context, dict) or not context:
        raise ValueError("Current candidate/native-input context is required")
    boundary = scenario.pressure_driven
    diameter = rational(scenario.diameter_m)
    area = circular_section("pressure-section", diameter, insulation_m=scenario.insulation_m, cost_per_m=0).area_m2
    density, friction = rational(boundary.density_kg_m3), rational(boundary.darcy_friction)
    if set(component_outer_radii) != set(components):
        raise ValueError("Every unique physical component requires its current native outer-radius enclosure")
    radii = {cid: as_interval(value) for cid, value in component_outer_radii.items()}
    insulation = rational(scenario.insulation_m)
    bores = {cid: 2 * (radius - insulation) for cid, radius in radii.items()}
    if any(value.lo <= 0 for value in bores.values()):
        raise ValueError("The ideal hydraulic bore must remain positive throughout every native section enclosure")
    areas = {cid: area * (bore / diameter).square() for cid, bore in bores.items()}
    # A_ref/A_c=(D_ref/D_c)^2: pi cancels exactly in this ratio.
    # The fixed reference beta is only a normalization. Each component retains
    # its own bore, resistance and port velocity throughout the uncertainty box.
    area_ratios_squared = {cid: (Interval.point(diameter) / bore).square().square() for cid, bore in bores.items()}

    def loss_factor(ids):
        result = Interval.point(0)
        for cid in ids:
            component = components[cid]
            if component.kind not in {"segment", "elbow"}:
                raise ValueError("Only straight pipes and supported elbows may occur outside the tee")
            component_loss = friction * lengths[cid] / bores[cid]
            if component.kind == "elbow":
                component_loss += rational(boundary.elbow_loss_coefficient)
            result += component_loss * area_ratios_squared[cid]
        return result

    common = loss_factor(partition["common_trunk"])
    parameters = {"beta": _encoded(density / 2 * (Interval.point(1) / area.square()))}
    elevations = {}
    for index, sid in enumerate(branch_ids, 1):
        tee_k = (boundary.tee_straight_loss_coefficient if partition["tee_exit_ports"][sid] == "b"
                 else boundary.tee_branch_loss_coefficient)
        elevation = density * rational(boundary.gravity_m_s2) * (positions["sinks"][sid][2] - positions["source"][2])
        pressure = Interval.point(rational(boundary.source_total_pressure_pa) - rational(boundary.sink_total_pressures_pa[sid])) - elevation
        parameters.update({f"P{index}": _encoded(pressure), f"A{index}": _encoded(common + rational(tee_k) * area_ratios_squared[partition["tee"]]),
                           f"B{index}": _encoded(loss_factor(partition["branches"][sid]))})
        elevations[sid] = _encoded(elevation)
    derivation = {"schema": "oma.native-two-sink-pressure-derivation/1", "network": raw_network,
        "boundary": boundary.model_dump(mode="json", by_alias=True), "partition": partition,
        "component_lengths_m": {cid: _encoded(value) for cid, value in sorted(lengths.items())},
        "terminal_positions_m": {"source": [_encoded(v) for v in positions["source"]],
            "sinks": {sid: [_encoded(v) for v in positions["sinks"][sid]] for sid in branch_ids}},
        "reference_section_area_m2": _encoded(area), "reference_diameter_m": str(diameter),
        "component_outer_radii_m": {cid: _encoded(value) for cid, value in sorted(radii.items())},
        "component_hydraulic_diameters_m": {cid: _encoded(value) for cid, value in sorted(bores.items())},
        "component_section_areas_m2": {cid: _encoded(value) for cid, value in sorted(areas.items())},
        "hydraulic_section_interpretation": boundary.hydraulic_section_interpretation,
        "native_inner_bore_or_wall_thickness_measured": False,
        "section_model_scope": "Ideal circular bore from native outer envelope minus declared insulation; unchanged section-correspondence gates and declared loss applicability remain prerequisites; no reducer or unmodeled junction-loss authorization",
        "elevation_pressure_pa": elevations, "parameters": parameters,
        "tee_darcy_length_charged": False, "coefficient_uncertainty": "CARTESIAN_OUTER_BOX_CONTAINS_CORRELATED_NATIVE_METRIC_MODEL",
        "native_metric_bounds_are_supplied": True, "native_geometry_rechecked_by_this_function": False}
    model = {"schema": "oma.two-sink-pressure-model/1", "branch_ids": branch_ids, "parameters": parameters,
        "context_root": digest({"context": context, "scenario": scenario.model_dump(mode="json", by_alias=True)}),
        "physical_model_root": digest(derivation), "assumptions": copy.deepcopy(MODEL_ASSUMPTIONS)}
    return model, derivation


def evaluate_pressure_network(scenario, network, component_lengths, terminal_positions, *, component_outer_radii, context, checkpoint=None):
    """Check the operating relation first, then minimum delivery and all velocities."""
    from oma.optimization.two_sink_pressure import compile_two_sink_pressure, verify_two_sink_pressure

    if checkpoint:
        checkpoint("pressure_model_inputs")
    try:
        model, derivation = derive_two_sink_pressure_model(scenario, network, component_lengths, terminal_positions,
            component_outer_radii=component_outer_radii, context=context)
        fixed_scenario = SharedNetworkScenario.model_validate(scenario.model_dump(mode="json", by_alias=True))
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        return {"verdict": "BLOCKED", "operating_point_status": "NOT_ESTABLISHED", "reason": str(exc),
                "model": "one_tee_two_outlet_pressure_driven"}
    result = compile_two_sink_pressure(model, checkpoint=checkpoint)
    certificate = result.get("certificate")
    checked = (verify_two_sink_pressure(model, certificate, checkpoint=checkpoint)
               if result.get("status") == "CERTIFIED" and certificate is not None else None)
    output = {"model": "one_tee_two_outlet_pressure_driven", "model_input": model, "derivation": derivation,
              "producer": result, "independent_check": checked, "operating_point_status": "NOT_ESTABLISHED",
              "scope": "Unique forward operating point for each admitted fixed-loss model; supplied total-pressure boundaries and native metric enclosures",
              "catalog_and_boundary_applicability": "DECLARED_ASSUMPTIONS", "general_nonlinear_network_solution": False}
    if not checked or checked.get("status") != "PASS":
        output["verdict"] = "BLOCKED" if result.get("status") == "INVALID_INPUT" else "UNKNOWN"
        return output
    enclosures = checked["enclosures"]
    total = _decoded(enclosures["total_flow_m3_s"])
    flows = {sid: _decoded(value) for sid, value in enclosures["branch_flows_m3_s"].items()}
    partition = derivation["partition"]
    areas = {cid: _decoded(value) for cid, value in derivation["component_section_areas_m2"].items()}
    boundary = fixed_scenario.pressure_driven
    deliveries = {sink.id: {"required_minimum_flow_m3_s": str(rational(sink.required_flow_m3_s)),
        "flow_m3_s": _encoded(flows[sink.id]), "status": _le(sink.required_flow_m3_s, flows[sink.id])} for sink in fixed_scenario.sinks}
    component_flows = {cid: {"a": total, "b": total} for cid in partition["common_trunk"]}
    component_flows[partition["tee"]] = {"a": total}
    for sid, ids in partition["branches"].items():
        component_flows[partition["tee"]][partition["tee_exit_ports"][sid]] = flows[sid]
        component_flows.update({cid: {"a": flows[sid], "b": flows[sid]} for cid in ids})
    velocities = {cid: {port: {"velocity_m_s": _encoded(flow / areas[cid]),
        "status": _le(flow / areas[cid], boundary.maximum_velocity_m_s)} for port, flow in ports.items()}
        for cid, ports in component_flows.items()}
    verdicts = [item["status"] for item in deliveries.values()]
    verdicts += [item["status"] for ports in velocities.values() for item in ports.values()]
    output.update(verdict=combine_verdicts(verdicts), operating_point_status="PASS", deliveries=deliveries,
                  component_velocities=velocities, source_flow_m3_s=_encoded(total),
                  unique_physical_components=len(component_flows), conservation="Q=q1+q2 in the independently checked parametric relation")
    if checkpoint:
        checkpoint("pressure_service_complete")
    try:
        current_model, _ = derive_two_sink_pressure_model(scenario, network, component_lengths, terminal_positions,
            component_outer_radii=component_outer_radii, context=context)
        bound = current_model == model
    except (ValueError, TypeError, KeyError, OverflowError):
        bound = False
    if not bound:
        return {"model": "one_tee_two_outlet_pressure_driven", "verdict": "UNKNOWN",
            "operating_point_status": "NOT_ESTABLISHED", "reason": "Pressure-model inputs changed during calculation",
            "input_binding": "CHANGED"}
    output["input_binding"] = "UNCHANGED_AFTER_FINAL_CHECKPOINT"
    return output
