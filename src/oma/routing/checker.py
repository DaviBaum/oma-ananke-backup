"""Independent persisted-route checker. No imports from candidate generators.

Reads real exported IFC geometry and connectivity, recomputes objective values,
and calls native solid interference checks. Numerical evidence is explicitly
scoped; this is not a universal building or exact-arithmetic certification.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from oma.ifc.audit import sha256_file
from oma.ifc.cad import cad_check_routes, load_cad
from oma.ifc.ports import ownership_ledger, port_facts, connected_pair_errors, circular_owner_radius
from oma.models import CheckResult, VerificationReport, Verdict
from oma.store import Store, digest, utcnow
from oma.verification import CHECKER_VERSION
from .scenario import RoutingScenario


def check_physical_ports(path, cad_objects, source_matrix=None, port_guids=None):
    """Every IFC port must lie on its own solid cap with the claimed outward axis.

    Checking only port-to-port coincidence can miss a translated/shortened body.
    The classifier probes the boundary and both sides against native solid volume.
    """
    import ifcopenshell
    import ifcopenshell.util.placement
    import ifcopenshell.util.unit
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_IN, TopAbs_ON, TopAbs_OUT
    model = ifcopenshell.open(str(path))
    scale = ifcopenshell.util.unit.calculate_unit_scale(model)
    transform = np.asarray(source_matrix if source_matrix is not None else np.eye(4), dtype=float)
    by_guid = {s.guid: s for s in cad_objects}
    findings = []
    for record in ownership_ledger(model).values():
        if port_guids is not None and record["port"].GlobalId not in port_guids:
            continue
        selected = [o for o in record["owners"].values() if o.GlobalId in by_guid]
        if not selected:
            continue
        port = record["port"]
        solid = by_guid[selected[0].GlobalId]
        facts = port_facts(port, record, scale, transform)
        if facts["errors"] or not solid.valid:
            findings.append({**facts, "owner_guid": solid.guid, "status": "FAIL",
                             "reason": "Invalid owner, owner-relative placement, flow frame or native owner solid"})
            continue
        center = np.asarray(facts["position_m"])
        axis = np.asarray(facts["physical_outward_normal"])
        tolerance = max(1e-7, solid.kernel_tolerance_m)
        probe = max(1e-4, 20 * tolerance)
        states = []
        for point in (center, center + probe * axis, center - probe * axis):
            classifier = BRepClass3d_SolidClassifier(solid.shape, gp_Pnt(*point), tolerance)
            states.append(classifier.State())
        passed = states == [TopAbs_ON, TopAbs_OUT, TopAbs_IN]
        findings.append({**facts, "owner_guid": solid.guid, "status": "PASS" if passed else "FAIL",
                         "reason": "Physical cap agrees with outward normal derived from IFC flow Axis" if passed else "Port does not terminate its owner's actual physical solid with the declared flow Axis",
                         "states": [str(s) for s in states], "point": center.tolist(), "probe_m": probe, "tolerance_m": tolerance})
    return findings


def _semantics(path, source_path, materialization, scenario, known_physical_guids=None):
    import ifcopenshell
    import ifcopenshell.util.placement
    import ifcopenshell.util.unit
    model = ifcopenshell.open(str(path))
    original = ifcopenshell.open(str(source_path))
    scale = ifcopenshell.util.unit.calculate_unit_scale(model)
    angle_scale = ifcopenshell.util.unit.calculate_unit_scale(model, "PLANEANGLEUNIT")
    source_matrix = np.asarray(materialization.get("route_spec", {}).get("source_to_federation_matrix", np.eye(4)), dtype=float)
    records, lengths, fittings, radii = [], [], 0, []
    original_ids = {e.id() for e in original}
    expected_guids = {p["ifc_guid"] for p in materialization["added_parts"]}
    new_physical = [e for e in model.by_type("IfcElement") if e.id() not in original_ids]
    errors = []
    if {e.GlobalId for e in new_physical} != (expected_guids if known_physical_guids is None else set(known_physical_guids)):
        errors.append("Materialized part accounting differs from actual added IFC physical entities")
    new_physical = [e for e in new_physical if e.GlobalId in expected_guids]
    changed = []
    for before in original:
        try:
            after = model.by_id(before.id())
            if str(before) != str(after):
                changed.append(before.id())
        except RuntimeError:
            changed.append(before.id())
    if changed:
        errors.append(f"Original STEP records changed or lost: {changed[:20]}")
    slopes = []
    for element in new_physical:
        representations = [item for rep in element.Representation.Representations for item in rep.Items]
        if len(representations) != 1 or not representations[0].is_a("IfcSweptAreaSolid") or not representations[0].SweptArea.is_a("IfcCircleProfileDef"):
            errors.append("New route requires a single supported physical swept solid per part")
            continue
        solid = representations[0]
        radius = float(solid.SweptArea.Radius) * scale
        radii.append(radius)
        if abs(radius - scenario.outer_radius) > 1e-10:
            errors.append("Exported outer/inner radius does not match required service and insulation envelope")
        if solid.is_a("IfcExtrudedAreaSolid"):
            length = float(solid.Depth) * scale
            if length < scenario.minimum_straight_m:
                errors.append("Exported straight segment violates minimum straight length")
            if scenario.system_type == "GRAVITY_DRAINAGE":
                element_frame = ifcopenshell.util.placement.get_local_placement(element.ObjectPlacement)
                solid_frame = ifcopenshell.util.placement.get_axis2placement(solid.Position)
                direction = np.asarray(solid.ExtrudedDirection.DirectionRatios, dtype=float)
                v = source_matrix[:3, :3] @ element_frame[:3, :3] @ solid_frame[:3, :3] @ direction
                v *= length / np.linalg.norm(v)
                horizontal = float(np.linalg.norm(v[:2]))
                slopes.append(float(-v[2] - scenario.min_slope * horizontal))
        elif solid.is_a("IfcRevolvedAreaSolid"):
            fittings += 1
            profile_center = np.asarray([*solid.SweptArea.Position.Location.Coordinates, 0.], dtype=float)
            axis_origin = np.asarray(solid.Axis.Location.Coordinates, dtype=float)
            axis_direction = np.asarray(solid.Axis.Axis.DirectionRatios, dtype=float)
            axis_direction /= np.linalg.norm(axis_direction)
            relative = profile_center - axis_origin
            radius_bend = float(np.linalg.norm(relative - np.dot(relative, axis_direction) * axis_direction)) * scale
            angle = float(solid.Angle) * angle_scale
            if radius_bend < scenario.bend_radius_m - 1e-12 or angle <= 0 or angle >= math.pi:
                errors.append("Invalid catalog bend radius or arc angle")
            length = radius_bend * angle
            if scenario.system_type == "GRAVITY_DRAINAGE":
                # Continuous derivative envelope is not inferred from endpoint slope.
                slopes.append(None)
        else:
            errors.append("Unsupported physical directrix; cannot verify length/fitting")
            continue
        lengths.append(length)
        records.append({"guid": element.GlobalId, "length_m": length, "radius_m": radius})
    owners, owned = {}, {e.id(): [] for e in new_physical}
    ledger = ownership_ledger(model)
    for pid, record in ledger.items():
        associated = set(record["owners"]) & set(owned)
        if not associated:
            continue
        facts = port_facts(record["port"], record, scale)
        errors.extend(facts["errors"])
        if len(associated) == 1:
            owner_id = next(iter(associated))
            owners[pid] = owner_id
            owned[owner_id].append(record["port"])
    links = []
    degree = {p: 0 for p in owners}
    total_degree = {p: 0 for p in owners}
    external_links = []
    graph = {e: set() for e in owned}
    for rel in model.by_type("IfcRelConnectsPorts"):
        a, b = rel.RelatingPort.id(), rel.RelatedPort.id()
        if a in owners or b in owners:
            errors.extend(connected_pair_errors(rel.RelatingPort, rel.RelatedPort, ledger, scale))
            for pid in (a, b):
                if pid in total_degree:
                    total_degree[pid] += 1
            if (a in owners) != (b in owners):
                external_links.append(rel)
        if a in owners and b in owners:
            links.append((a, b))
            degree[a] += 1
            degree[b] += 1
            graph[owners[a]].add(owners[b])
            graph[owners[b]].add(owners[a])
            if rel.RelatingPort.FlowDirection != "SOURCE" or rel.RelatedPort.FlowDirection != "SINK":
                errors.append("Internal port flow direction reversed or undefined")
            pa = ifcopenshell.util.placement.get_local_placement(rel.RelatingPort.ObjectPlacement)[:3, 3] * scale
            pb = ifcopenshell.util.placement.get_local_placement(rel.RelatedPort.ObjectPlacement)[:3, 3] * scale
            if np.linalg.norm(pa - pb) > 1e-7:
                errors.append("Connected IFC ports occupy different physical positions")
    if any(len(ports) != 2 for ports in owned.values()) or any(d > 1 for d in total_degree.values()):
        errors.append("Part port ownership/connection multiplicity is inconsistent")
    seen, stack = set(), list(graph)[:1]
    while stack:
        item = stack.pop()
        if item not in seen:
            seen.add(item)
            stack.extend(graph[item] - seen)
    if seen != set(graph) or len(links) != max(0, len(graph) - 1):
        errors.append("Physical route is disconnected or contains an unintended cycle")
    endpoints = [model.by_id(p) for p, d in degree.items() if d == 0]
    if len(endpoints) != 2:
        errors.append("Route does not have exactly two declared terminal interfaces")
    else:
        inlet = next((p for p in endpoints if p.FlowDirection == "SINK"), None)
        outlet = next((p for p in endpoints if p.FlowDirection == "SOURCE"), None)
        for port, expected in ((inlet, scenario.start), (outlet, scenario.end)):
            if port is None or np.linalg.norm(source_matrix[:3,:3] @ (ifcopenshell.util.placement.get_local_placement(port.ObjectPlacement)[:3, 3] * scale) + source_matrix[:3,3] - expected) > 1e-7:
                errors.append("Exported route terminal position or direction differs from fixed mission")
        expected_external = set()
        for role, guid, route_port in (("SOURCE", scenario.source_port_guid, inlet), ("SINK", scenario.sink_port_guid, outlet)):
            if guid is None:
                continue
            try:
                before = original.by_guid(guid)
                external = model.by_guid(guid)
                if not before.is_a("IfcDistributionPort") or route_port is None:
                    raise ValueError("Unsupported original terminal")
                if before.FlowDirection != role or before.ConnectedTo or before.ConnectedFrom:
                    raise ValueError("Original terminal has incompatible flow or is already connected")
                if str(before) != str(external):
                    raise ValueError("Original terminal record changed")
                expected_external.add((external.id(), route_port.id()) if role == "SOURCE" else (route_port.id(), external.id()))
                errors.extend(port_facts(external, ledger[external.id()], scale)["errors"])
                declared_owners = ledger[external.id()]["owners"]
                radius = circular_owner_radius(next(iter(declared_owners.values())), scale) if len(declared_owners) == 1 else None
                if radius is None or abs(radius - scenario.outer_radius) > 1e-7:
                    errors.append("Original terminal section is unknown or differs from the fixed service envelope")
            except (RuntimeError, ValueError, KeyError) as exc:
                errors.append(f"Original terminal binding invalid: {exc}")
        actual_external = [(r.RelatingPort.id(), r.RelatedPort.id()) for r in external_links]
        if len(actual_external) != len(expected_external) or set(actual_external) != expected_external:
            errors.append("Actual external port bindings differ from the fixed requested original terminals")
    return {"errors": errors, "length_m": sum(lengths), "fitting_count": fittings, "parts": records,
            "connections": len(links), "original_records_checked": len(original_ids), "slope_margins": slopes}


def evaluate_route_state(store, state, baseline, requested, scenario, mission, materialization, route_ids, control, *, known_physical_guids=None):
    """Independently evaluate one obligation against a pinned composite state."""
    path = store.resolve_path(materialization["export_path"])
    results = []
    objective = {}
    actual = []
    def add(identity, status, reason, *, participants=(), witness=None, scope="Proposed route and its declared obstacle scope"):
        results.append(CheckResult(id=identity, status=Verdict(status), reason=reason, scope=scope, participants=tuple(participants), witness=witness or {}))
    request_bound = scenario.model_dump(mode="json") == requested.model_dump(mode="json") and mission["scenario_hash"] == digest(requested.model_dump(mode="json"))
    add("fixed-request-assumptions", "PASS" if request_bound else "FAIL", "Scenario, clearance, physical sizes and objective policy match the immutable original run request" if request_bound else "Candidate changed the fixed requested engineering assumptions")
    same_sources = state["sources"] == baseline["sources"]
    protected = {e["id"]: digest(e) for e in baseline.get("entities", [])}
    after = {e["id"]: digest(e) for e in state.get("entities", [])}
    preserved = same_sources and all(after.get(k) == v for k, v in protected.items()) and set(mission["protected_ids"]) == set(protected)
    base_ports = {p["id"]: digest(p) for p in baseline.get("ports", [])}
    after_ports = {p["id"]: digest(p) for p in state.get("ports", [])}
    preserved &= all(after_ports.get(k) == v for k, v in base_ports.items())
    preserved &= state.get("explicit_connections", []) == baseline.get("explicit_connections", [])
    preserved &= state.get("inferred_connections", []) == baseline.get("inferred_connections", [])
    add("protected-source-preservation", "PASS" if preserved else "FAIL", "All baseline entity content and source identities preserved" if preserved else "Protected entities or source identities changed")
    hash_match = path.is_file() and sha256_file(path) == materialization["export_sha256"]
    original_match = all(store.resolve_path(s["immutable_path"]).is_file() and sha256_file(store.resolve_path(s["immutable_path"])) == s["sha256"] for s in state["sources"])
    add("materialized-input-integrity", "PASS" if hash_match and original_match else "FAIL", "Persisted IFC hashes rechecked" if hash_match and original_match else "Persisted physical artifact or source hash changed")
    correspondence = state.get("derived_artifacts", {}).get("export_correspondence")
    if correspondence:
        matched = len(correspondence["files"]) == len(state["sources"])
        for exported in correspondence["files"]:
            matched &= store.resolve_path(exported["path"]).is_file() and sha256_file(store.resolve_path(exported["path"])) == exported["sha256"]
            if not exported["changed"]:
                matched &= exported["sha256"] == exported["source_sha256"]
        add("export-federation-correspondence", "PASS" if matched else "FAIL", "Every exported discipline hash and replacement correspondence independently rechecked")
    routes = [r for r in state["routes"] if r["id"] in route_ids]
    demand_ids = {d["id"] for d in mission["demands"]}
    coverage = len(routes) == 1 and set(routes[0]["demand_ids"]) == demand_ids and len(demand_ids) == 1
    if coverage:
        demand = mission["demands"][0]
        coverage &= routes[0]["section"] == demand["section"] and routes[0]["service"] == demand["service"]
        coverage &= set(routes[0]["port_ids"]) == {demand["source_port"], *demand["sink_ports"]}
        coverage &= demand["section"]["diameter_m"] == requested.diameter_m and demand["section"]["insulation_m"] == requested.insulation_m
        coverage &= demand["clearance_m"] == requested.clearance_m and demand["service"] == requested.system_type
    add("fixed-service-obligations", "PASS" if coverage else "FAIL", "All declared terminals, section and insulation obligations preserved" if coverage else "A service/terminal/section obligation changed or lacks coverage")
    semantics = None
    if hash_match and original_match:
        semantics = _semantics(path, store.resolve_path(materialization["source_path"]), materialization, scenario, known_physical_guids)
        add("exported-physical-semantics", "PASS" if not semantics["errors"] else "FAIL", "Fresh IFC directrices, sections, terminal locations, connections and original STEP records agree" if not semantics["errors"] else "; ".join(semantics["errors"]), witness={"recomputed": semantics})
        objective = {"length_m": semantics["length_m"], "fitting_count": float(semantics["fitting_count"])}
        guids = {p["ifc_guid"] for p in materialization["added_parts"]}
        cad = cad_check_routes([store.resolve_path(s["immutable_path"]) for s in state["sources"]], path, guids, clearance_m=scenario.clearance_m,
                               numerical_tolerance_m=1e-6, coordinate_evidence=state.get("derived_artifacts", {}).get("local_coordinate_evidence"),
                               cache_directory=store.directory / "cad-cache",
                               source_representation_policy=scenario.source_representation_policy,
                               checkpoint=control.checkpoint)
        cad_root = store.put(cad)
        add("physical-interference-and-clearance", cad["coordination_status"], f"Native solids checked: {cad['pairs_accounted']} route/obstacle pairs, {cad['failed_pairs']} forbidden pairs, {cad['unknown_pairs']} ambiguous pairs; datum {cad['coordinate_status']}", witness={"artifact": cad_root}, scope="New route versus every source physical obstacle; pre-existing building defects remain outside this local repair claim")
        add("physical-self-interference", cad["self_interference_status"], "All route part pairs checked with local joint-interface authorization", witness={"artifact": cad_root})
        for i, issue in enumerate(cad["pair_results"] + cad.get("self_pair_results", [])):
            if issue["status"] != "PASS":
                witness = issue.get("witness", {})
                add(f"physical-witness:{i}", issue["status"], issue["reason"], participants=issue["participants"], witness={"point": witness.get("p1"), "other_point": witness.get("p2"), "margin_m": issue.get("clearance_margin_m"), "required_clearance_m": issue["required_clearance_m"], "artifact": cad_root})
        actual, errors = load_cad(path, guids=guids)
        matrix = materialization.get("route_spec", {}).get("source_to_federation_matrix")
        if matrix:
            from oma.ifc.cad import _transform_object
            actual = [_transform_object(s, matrix) for s in actual]
        physical_ports = check_physical_ports(path, actual, matrix)
        port_pass = len(physical_ports) == 2 * len(actual) and all(p["status"] == "PASS" for p in physical_ports)
        add("physical-port-body-attachment", "PASS" if port_pass else "FAIL", "Every terminal/joint port independently classified on its actual solid cap with matching outward direction", witness={"ports": physical_ports})
        terminal_guids = {g for g in (scenario.source_port_guid, scenario.sink_port_guid) if g is not None}
        if terminal_guids:
            import ifcopenshell
            source_path = store.resolve_path(materialization["source_path"])
            original_model = ifcopenshell.open(str(source_path))
            terminal_ledger = ownership_ledger(original_model)
            owners = {owner.GlobalId for record in terminal_ledger.values() if record["port"].GlobalId in terminal_guids
                      for owner in record["owners"].values()}
            terminal_objects, terminal_errors = load_cad(source_path, guids=owners, checkpoint=control.checkpoint)
            if matrix:
                terminal_objects = [_transform_object(s, matrix) for s in terminal_objects]
            terminal_ports = check_physical_ports(source_path, terminal_objects, matrix, terminal_guids)
            terminal_pass = not terminal_errors and len(terminal_ports) == len(terminal_guids) and all(p["status"] == "PASS" for p in terminal_ports)
            add("original-terminal-body-attachment", "PASS" if terminal_pass else "FAIL",
                "Requested existing IFC terminal axes and positions independently checked against their own native source solids",
                witness={"ports": terminal_ports, "source_errors": terminal_errors})
        enclosed = not errors and len(actual) == len(guids)
        unknown_zone = False
        volume_length = 0.
        for solid in actual:
            if not solid.valid or solid.bounds is None:
                enclosed = False
                continue
            gap = min(*(solid.bounds[i] - scenario.allowed_zone.min[i] for i in range(3)), *(scenario.allowed_zone.max[i] - solid.bounds[i+3] for i in range(3)))
            if gap < 0:
                enclosed = False
            if gap <= 1e-6 + solid.kernel_tolerance_m:
                unknown_zone = True
            volume_length += solid.volume_m3 / (math.pi * scenario.outer_radius ** 2)
        add("permitted-zone-containment", "FAIL" if not enclosed else "UNKNOWN" if unknown_zone else "PASS", "Full native route envelopes checked against permitted zone boundary")
        error = abs(volume_length - objective["length_m"])
        add("independent-objective-recomputation", "PASS" if error <= max(1e-6, objective["length_m"] * 1e-6) else "FAIL",
            "Length recomputed from IFC directrices and independently cross-checked from solid volumes", witness={"directrix_length_m": objective["length_m"], "volume_length_m": volume_length, "difference_m": error})
        if scenario.system_type == "GRAVITY_DRAINAGE":
            slopes = semantics["slope_margins"]
            status = "FAIL" if any(v is not None and v < 0 for v in slopes) else "UNKNOWN" if any(v is None for v in slopes) else "PASS"
            add("gravity-slope", status, "Gravity direction and minimum slope checked per physical directrix; curved slope enclosures unresolved where present")
        else:
            add("gravity-slope", "NOT_APPLICABLE", "Service is not a gravity network")
    else:
        add("physical-interference-and-clearance", "BLOCKED", "Physical checker cannot run on changed/missing artifacts")
    if scenario.target_modality == "ENGINEERING_SERVICE":
        if scenario.physics and semantics and scenario.system_type in {"PRESSURE_PIPE", "ROUND_DUCT", "FIRE_PROTECTION"}:
            from oma.optimization.physical import circular_section, evaluate_fluid_path
            required = ("flow_m3_s", "density_kg_m3", "darcy_friction", "fitting_loss_coefficient", "maximum_velocity_m_s", "available_pressure_pa", "efficiency")
            values = {k: scenario.physics.get(k) for k in required}
            physical = evaluate_fluid_path(section=circular_section("required", scenario.diameter_m, insulation_m=scenario.insulation_m, cost_per_m=0), length_m=semantics["length_m"], **values)
            add("engineering-service", "BLOCKED" if physical.get("missing") else physical["verdict"], "Fixed-flow Darcy-Weisbach path calculation under explicit supplied parameters", witness={"calculation": physical})
        else:
            add("engineering-service", "BLOCKED", "Requested engineering service lacks a supported physical calculation with complete inputs")
    else:
        add("engineering-service", "NOT_APPLICABLE", "Requested scope is local geometric coordination; hydraulic capacity/fire protection design is not certified")
    return results, objective, actual


def verify_route_candidate(store: Store, candidate_id: str):
    candidate = store.candidate(candidate_id)
    state = store.get(candidate["state_root"])
    run = store.run(candidate["run_id"])
    from oma.verification import candidate_control
    control = candidate_control(store, candidate)
    baseline = store.get(run["base_root"])
    scenario = RoutingScenario.model_validate(state["derived_artifacts"]["routing_scenario"])
    mission = state["mission"]
    materialization = store.get(state["derived_artifacts"]["route_materialization"]["root"])
    path = store.resolve_path(materialization["export_path"])
    results, objective, _ = evaluate_route_state(store, state, baseline,
        RoutingScenario.model_validate(run["request"]["mission"]), scenario, mission, materialization, candidate["changed_ids"], control)
    if any(r.status == Verdict.FAIL for r in results):
        status = Verdict.FAIL
    elif any(r.status == Verdict.BLOCKED for r in results):
        status = Verdict.BLOCKED
    elif any(r.status in {Verdict.UNKNOWN, Verdict.NOT_RUN} for r in results):
        status = Verdict.UNKNOWN
    else:
        status = Verdict.PASS
    report = VerificationReport(candidate_root=candidate["state_root"], mission_hash=digest(mission), rule_hash=mission["rule_hash"],
                                checker_version=CHECKER_VERSION, status=status,
                                scope=f"{scenario.target_modality}: proposed route only; numerical CAD contract, not whole-building approval",
                                results=tuple(results), objective=objective,
                                common_mode_risks=("IfcOpenShell source parsing shared with importer", "OCP numerical kernel is not a formally certified interval geometry solver", "Route specification and IFC exporter share parametric conventions; checker separately reads native geometry, topology and volume"), created_at=utcnow())
    store.record_verification(candidate_id, report)
    return report
