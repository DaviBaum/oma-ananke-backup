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
from oma.ifc.cad import cad_check_routes, load_cad, _has_native_geometry
from oma.ifc.ports import ownership_ledger, port_facts, connected_pair_errors, circular_owner_radius
from oma.models import CheckResult, VerificationReport, Verdict, Section, Route
from oma.store import Store, digest, utcnow
from oma.verification import CHECKER_VERSION
from .scenario import RoutingScenario


def _finite_route_points(value):
    if not isinstance(value,(list,tuple)) or not 2 <= len(value) <= 10000:
        raise ValueError("A bounded explicit route point sequence is required")
    if any(not isinstance(p,(list,tuple)) or len(p)!=3 or any(type(x) not in (int,float) for x in p) for p in value):
        raise ValueError("Route coordinates must be finite real numbers, not Boolean or symbolic values")
    points=np.asarray(value,dtype=float)
    if not np.isfinite(points).all():
        raise ValueError("Nonfinite route coordinates")
    return points


def _route_metadata_binding(store,state,requested,materialization,route_ids,selected_source,*,composite):
    """Bind each displayed route and export instruction to the checked artifact."""
    try:
        all_routes=state.get("routes",[])
        identities=[r["id"] for r in all_routes]
        if len(set(identities))!=len(identities) or len(set(route_ids))!=len(route_ids):
            raise ValueError("Duplicate route or changed-component identities")
        rid=materialization["route_id"]
        routes=[r for r in all_routes if r["id"]==rid]
        if len(routes)!=1 or rid not in route_ids:
            raise ValueError("Exactly one checked route must own the materialization identity")
        route=routes[0]
        Route.model_validate(route)
        if len(route["demand_ids"])!=1 or len(route["port_ids"])!=2 or len(set(route["port_ids"]))!=2:
            raise ValueError("Ordinary route requires one demand and two distinct terminal identities")
        if route.get("fittings") or route.get("shared_trunk_id") is not None:
            raise ValueError("Unsupported extra fitting or shared-trunk metadata on an ordinary route")
        editable={f"{requested.authorized_opening.source_sha256}:{requested.authorized_opening.host_step_id}"} if requested.authorized_opening else set()
        if composite:
            if list(route_ids)!=[rid]:raise ValueError("Composite subcheck must select exactly its own route")
        elif len(all_routes)!=1 or set(route_ids)!={rid}|editable:
            raise ValueError("Standalone route and changed-component inventory must be exactly one route plus its authorized host")
        spec=materialization["route_spec"]
        expected={"route_id":rid,"diameter_m":requested.diameter_m,"insulation_m":requested.insulation_m,
            "bend_radius_m":requested.bend_radius_m,"minimum_straight_m":requested.minimum_straight_m,
            "system_type":requested.system_type,"assumption_root":digest(requested.model_dump(mode="json"))}
        if not selected_source:raise ValueError("Missing authorized source")
        for key in ("source_port_guid","sink_port_guid"):
            if getattr(requested,key) is not None:expected[key]=getattr(requested,key)
        if selected_source.get("transform_m") is not None:expected["source_to_federation_matrix"]=selected_source["transform_m"]
        if set(spec)!=(set(expected)|{"points_m"}):
            raise ValueError("Route specification contains missing or unsupported fields")
        if digest({k:spec[k] for k in expected})!=digest(expected):
            raise ValueError("Materialization route identity, size, service, source frame or assumption root differs")
        points=_finite_route_points(route["points_m"])
        declared=_finite_route_points(spec["points_m"])
        if points.shape!=declared.shape or not np.array_equal(points,declared):
            raise ValueError("Displayed route points differ from the materialization specification")
        artifact_root=digest(materialization)
        if route.get("geometry_artifact")!=artifact_root or digest(store.get(artifact_root))!=artifact_root:
            raise ValueError("Route geometry artifact is not the complete currently checked materialization")
        derived=state.get("derived_artifacts",{})
        fabrication=derived.get("fabrication_evidence_by_route",{})
        if (not isinstance(fabrication,dict) or not set(fabrication)<=set(identities)
                or any(not isinstance(value,dict) for value in fabrication.values())):
            raise ValueError("Fabrication evidence names missing or phantom routes")
        exports=derived.get("route_exports",[])
        export_ids=[r["route_spec"]["route_id"] for r in exports]
        if len(export_ids)!=len(set(export_ids)) or set(export_ids)!=set(identities):
            raise ValueError("Complete unique route-export instruction inventory required")
        own=next(e for e in exports if e["route_spec"]["route_id"]==rid)
        if own["source_id"]!=selected_source["id"] or digest(own["route_spec"])!=digest(spec):
            raise ValueError("Export instruction changed the checked source or route specification")
        if not composite:
            binding=derived["route_materialization"]
            if (binding["root"]!=artifact_root or binding["source_id"]!=selected_source["id"]
                    or store.resolve_path(binding["path"])!=store.resolve_path(materialization["export_path"])):
                raise ValueError("Standalone materialization root, source or file pointer differs")
        parts=materialization["added_parts"]
        guids=[p["ifc_guid"] for p in parts]
        steps=[p["step_id"] for p in parts]
        if not parts or len(guids)!=len(set(guids)) or len(steps)!=len(set(steps)):
            raise ValueError("Physical parts require complete unique IFC and STEP identities")
        for index,part in enumerate(parts):
            if part["route_id"]!=rid or type(part["part_index"]) is not int or part["part_index"]!=index:
                raise ValueError("Physical part sequence or route owner differs")
        return {"status":"PASS","route_id":rid,"materialization_root":artifact_root,
            "route_count":len(all_routes),"part_count":len(parts),"points_bound":len(points),"composite_subcheck":composite}
    except (ValueError,KeyError,TypeError,IndexError,StopIteration,OverflowError) as exc:
        return {"status":"FAIL","reason":str(exc)}


def _actual_route_directrix(model,materialization):
    """Numerically verify actual tangent primitives against every declared leg.

    This reads IFC independently and checks line/circle tangent identities; it
    never invokes the writer or trusts its `expected` geometry as the oracle.
    """
    from oma.ifc.network_semantics import read_component_geometry
    tolerance=1e-7
    try:
        spec=materialization["route_spec"]
        points=_finite_route_points(spec["points_m"])
        matrix=np.asarray(spec.get("source_to_federation_matrix",np.eye(4)),dtype=float)
        if (matrix.shape!=(4,4) or not np.isfinite(matrix).all()
                or not np.allclose(matrix[3],[0,0,0,1],rtol=0,atol=1e-12)
                or not np.allclose(matrix[:3,:3].T@matrix[:3,:3],np.eye(3),rtol=0,atol=1e-9)
                or np.linalg.det(matrix[:3,:3])<=0):raise ValueError("Unsupported route source frame")
        inverse=np.linalg.inv(matrix)
        points=points@inverse[:3,:3].T+inverse[:3,3]
        vectors=np.diff(points,axis=0);lengths=np.linalg.norm(vectors,axis=1)
        if not np.isfinite(lengths).all() or (lengths<=1e-9).any():raise ValueError("Invalid declared route leg")
        directions=vectors/lengths[:,None]
        turns={}
        for i,(u,v) in enumerate(zip(directions,directions[1:]),1):
            cosine=float(np.clip(np.dot(u,v),-1,1));theta=math.acos(cosine)
            if math.pi-theta<1e-6:raise ValueError("Declared U-turn has no supported tangent bend")
            if theta>=1e-8:turns[i]=(cosine,theta)
        order=[]
        for i in range(len(vectors)):
            order.append(("segment",i))
            if i+1 in turns:order.append(("elbow",i+1))
        parts=materialization["added_parts"]
        if len(parts)!=len(order):raise ValueError("Actual component denominator differs from the declared polyline realization")
        facts=[]
        for part,(kind,index) in zip(parts,order,strict=True):
            element=model.by_guid(part["ifc_guid"])
            if element.id()!=part["step_id"] or part["kind"]!=kind:
                raise ValueError("Part kind, GUID or STEP identity differs")
            actual=read_component_geometry(model,element)
            if actual["kind"]!=kind:raise ValueError("Actual IFC directrix family differs")
            expected_class=("IfcDuct" if spec["system_type"]=="ROUND_DUCT" else "IfcPipe")+("Segment" if kind=="segment" else "Fitting")
            if model.schema=="IFC2X3":expected_class="IfcFlowSegment" if kind=="segment" else "IfcFlowFitting"
            if element.is_a()!=expected_class:raise ValueError("Actual IFC service family differs")
            psets=[r.RelatingPropertyDefinition for r in element.IsDefinedBy if r.is_a("IfcRelDefinesByProperties")
                and r.RelatingPropertyDefinition.is_a("IfcPropertySet") and r.RelatingPropertyDefinition.Name=="OMA_RouteProvenance"]
            if len(psets)!=1:raise ValueError("Unique actual route provenance required")
            properties={p.Name:p.NominalValue.wrappedValue for p in psets[0].HasProperties if p.is_a("IfcPropertySingleValue") and p.NominalValue is not None}
            if len(properties)!=len(psets[0].HasProperties):raise ValueError("Duplicate or unsupported route provenance")
            for key,wanted in (("RouteId",spec["route_id"]),("AssumptionRoot",spec.get("assumption_root","EXPLICIT_ROUTE_SPEC")),("SystemFamily",spec["system_type"])):
                if properties.get(key)!=wanted:raise ValueError("Actual IFC route identity or assumption provenance differs")
            for key,wanted in (("Diameter_m",spec["diameter_m"]),("Insulation_m",spec.get("insulation_m",0))):
                if type(properties.get(key)) not in (int,float) or properties[key]!=wanted:raise ValueError("Actual IFC size provenance differs")
            a,b=np.asarray(actual["start_m"]),np.asarray(actual["end_m"])
            if kind=="segment":
                u=directions[index]
                start_distance=float(np.dot(a-points[index],u));end_distance=float(np.dot(b-points[index],u))
                if (np.linalg.norm(a-points[index]-start_distance*u)>tolerance
                        or np.linalg.norm(b-points[index]-end_distance*u)>tolerance
                        or start_distance < -tolerance or end_distance>lengths[index]+tolerance or end_distance<=start_distance
                        or np.linalg.norm(np.asarray(actual["caps"]["b"]["outward_normal"])-u)>tolerance):
                    raise ValueError("Actual straight is not the declared directed polyline leg")
                if index not in turns and np.linalg.norm(a-points[index])>tolerance:
                    raise ValueError("Actual straight starts at a different fixed vertex")
                if index+1 not in turns and np.linalg.norm(b-points[index+1])>tolerance:
                    raise ValueError("Actual straight ends at a different fixed vertex")
            else:
                u,v=directions[index-1:index+1];cosine,theta=turns[index]
                center=np.asarray(actual["center_m"]);R=float(spec["bend_radius_m"])
                sine=float(np.linalg.norm(np.cross(u,v)))
                if (not math.isfinite(R) or R<=0 or abs(actual["bend_radius_m"]-R)>tolerance
                        or abs(actual["angle_rad"]-theta)>tolerance
                        or np.linalg.norm(np.asarray(actual["normal"])-np.cross(u,v)/sine)>tolerance
                        or np.linalg.norm(a-center+R*(v-cosine*u)/sine)>tolerance
                        or np.linalg.norm(b-center-R*(u-cosine*v)/sine)>tolerance
                        or np.linalg.norm(np.asarray(actual["caps"]["a"]["outward_normal"])+u)>tolerance
                        or np.linalg.norm(np.asarray(actual["caps"]["b"]["outward_normal"])-v)>tolerance):
                    raise ValueError("Actual circular bend differs from the declared tangent corner and radius")
            if facts and np.linalg.norm(np.asarray(facts[-1]["end_m"])-a)>tolerance:
                raise ValueError("Actual ordered primitive directrices do not join")
            claimed=part["expected"]
            if claimed["kind"]!=kind or not math.isfinite(claimed["length_m"]) or abs(claimed["length_m"]-actual["length_m"])>tolerance:
                raise ValueError("Materialization component metadata differs from its actual directrix")
            for key,actual_key in (("start","start_m"),("end","end_m"),("center","center_m"),("normal","normal")):
                if key in claimed:
                    value=np.asarray(claimed[key],dtype=float)
                    if value.shape!=(3,) or not np.isfinite(value).all() or np.linalg.norm(value-np.asarray(actual[actual_key]))>tolerance:
                        raise ValueError("Materialization component coordinate metadata differs from actual IFC")
            if kind=="elbow":
                for key in ("bend_radius_m","angle_rad"):
                    if not math.isfinite(claimed[key]) or abs(claimed[key]-actual[key])>tolerance:
                        raise ValueError("Materialization bend metadata differs from actual IFC")
            facts.append(actual)
        return {"errors":[],"parts_checked":len(facts),"tolerance_m":tolerance,
            "scope":"NUMERICAL_ACTUAL_IFC_DIRECTRIX_CORRESPONDENCE_TO_COMPLETE_DECLARED_POLYLINE"}
    except (ValueError,KeyError,TypeError,IndexError,RuntimeError,OverflowError,np.linalg.LinAlgError) as exc:
        return {"errors":[str(exc)],"tolerance_m":tolerance}


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
        if facts["errors"] or not _has_native_geometry(solid):
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
    accounted_guids = expected_guids if known_physical_guids is None else set(known_physical_guids)
    if materialization.get("authorized_opening"):
        accounted_guids = accounted_guids | {materialization["authorized_opening"]["opening_guid"]}
    if len(new_physical) != len(accounted_guids) or {e.GlobalId for e in new_physical} != accounted_guids:
        errors.append("Materialized part accounting differs from actual added IFC physical entities")
    new_part_ids = {e.id() for e in new_physical if e.GlobalId in (known_physical_guids if known_physical_guids is not None else expected_guids)}
    permitted_void = (materialization.get("authorized_opening") or {}).get("void_relation_step_id")
    from oma.ifc.protected_semantics import added_relationship_effects
    errors.extend(added_relationship_effects(model, original_ids, new_part_ids,
        checked_void_id=permitted_void, separately_checked_original_ports=True))
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
    directrix=_actual_route_directrix(model,materialization)
    errors.extend(directrix["errors"])
    return {"errors": errors, "length_m": sum(lengths), "fitting_count": fittings, "parts": records,"route_directrix":directrix,
            "connections": len(links), "original_records_checked": len(original_ids), "slope_margins": slopes}


class _RoutePreflight:
    """One-shot local continuation; never a persisted or caller-authored proof."""
    def __init__(self, evaluation):
        self._evaluation = evaluation
        self._terminal = None
        self._used = False
        try:
            self.checks = next(evaluation)
            self.ready = True
        except StopIteration as completed:
            self._terminal = completed.value
            self.checks = self._terminal[0]
            self.ready = False

    def finish(self):
        if self._used:
            raise RuntimeError("A route preflight can only be consumed once")
        self._used = True
        if self._terminal is not None:
            return self._terminal
        try:
            next(self._evaluation)
        except StopIteration as completed:
            return completed.value
        finally:
            self._evaluation.close()
        raise RuntimeError("Route checker unexpectedly paused more than once")

    def close(self):
        self._used = True
        self._evaluation.close()


def prepare_route_state(*args, **kwargs):
    """Run the same invocation's input/mission/IFC semantics before native work."""
    return _RoutePreflight(_evaluate_route_state(*args, **kwargs))


def evaluate_route_state(store, state, baseline, requested, scenario, mission, materialization, route_ids, control, *, candidate_run=None, known_physical_guids=None):
    prepared = prepare_route_state(store, state, baseline, requested, scenario, mission, materialization, route_ids,
        control, candidate_run=candidate_run, known_physical_guids=known_physical_guids)
    try:
        return prepared.finish()
    finally:
        prepared.close()


def _evaluate_route_state(store, state, baseline, requested, scenario, mission, materialization, route_ids, control, *, candidate_run=None, known_physical_guids=None):
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
    editable = {f"{requested.authorized_opening.source_sha256}:{requested.authorized_opening.host_step_id}"} if requested.authorized_opening else set()
    preserved = (same_sources and state.get("entities", []) == baseline.get("entities", [])
                 and len(protected) == len(baseline.get("entities", []))
                 and set(mission["protected_ids"]) == set(protected) - editable)
    preserved &= set(mission.get("editable_ids", [])) == editable
    base_ports = {p["id"]: digest(p) for p in baseline.get("ports", [])}
    after_ports = {p["id"]: digest(p) for p in state.get("ports", [])}
    preserved &= all(after_ports.get(k) == v for k, v in base_ports.items())
    preserved &= len(base_ports) == len(baseline.get("ports", [])) and len(after_ports) == len(state.get("ports", []))
    declared_terminal_ids = {p for d in (state.get("mission") or {}).get("demands", []) for p in (d["source_port"], *d["sink_ports"])}
    preserved &= set(after_ports) <= set(base_ports) | declared_terminal_ids
    preserved &= state.get("explicit_connections", []) == baseline.get("explicit_connections", [])
    preserved &= state.get("inferred_connections", []) == baseline.get("inferred_connections", [])
    add("protected-source-preservation", "PASS" if preserved else "FAIL", "All baseline entity content and source identities preserved" if preserved else "Protected entities or source identities changed")
    hash_match = path.is_file() and sha256_file(path) == materialization["export_sha256"]
    original_match = all(store.resolve_path(s["immutable_path"]).is_file() and sha256_file(store.resolve_path(s["immutable_path"])) == s["sha256"] for s in state["sources"])
    add("materialized-input-integrity", "PASS" if hash_match and original_match else "FAIL", "Persisted IFC hashes rechecked" if hash_match and original_match else "Persisted physical artifact or source hash changed")
    selected_source = next((s for s in baseline["sources"] if s["id"] == requested.source_id),
        baseline["sources"][0] if requested.source_id is None and baseline["sources"] else None)
    declared_source_path = store.resolve_path(materialization["source_path"])
    source_frame_bound = bool(selected_source and materialization["source_sha256"] == selected_source["sha256"]
        and declared_source_path.is_file() and sha256_file(declared_source_path) == selected_source["sha256"]
        and materialization.get("route_spec", {}).get("source_to_federation_matrix") == selected_source.get("transform_m"))
    add("materialization-source-frame", "PASS" if source_frame_bound else "FAIL",
        "Route source bytes and source-to-federation frame match the immutable imported source" if source_frame_bound else "Route materialization changed its source identity or coordinate frame")
    metadata=_route_metadata_binding(store,state,requested,materialization,route_ids,selected_source,
        composite=known_physical_guids is not None)
    add("route-materialization-correspondence",metadata["status"],
        "Complete route, changed-component and export inventories bind the actual checked materialization" if metadata["status"]=="PASS" else metadata["reason"],witness=metadata)
    if metadata["status"]!="PASS":
        add("physical-interference-and-clearance","NOT_RUN","Route metadata and materialized geometry identities do not agree")
        return results,objective,[]
    from .fabrication_evidence import check_route_fabrication_evidence
    route=next(r for r in state["routes"] if r["id"]==metadata["route_id"])
    checked=check_route_fabrication_evidence(store,state,baseline,scenario,route,candidate_run)
    add("nominal-fabrication-witness-integrity",checked["status"],
        "Independent proof replay validates the stated nominal disposition only; native geometry and acceptance remain separate" if checked["status"]=="PASS" else checked["reason"],
        witness=checked,scope="Optional exact nominal model proof integrity; no native PASS or pruning authority")
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
    coverage = len(routes) == 1 and set(routes[0]["demand_ids"]) == demand_ids and len(demand_ids) == len(mission["demands"]) == 1
    if coverage:
        demand = mission["demands"][0]
        required_section = Section(shape="circular", diameter_m=requested.diameter_m, insulation_m=requested.insulation_m).model_dump(mode="json")
        coverage &= routes[0]["section"] == demand["section"] == required_section and routes[0]["service"] == demand["service"]
        coverage &= set(routes[0]["port_ids"]) == {demand["source_port"], *demand["sink_ports"]}
        coverage &= demand["section"]["diameter_m"] == requested.diameter_m and demand["section"]["insulation_m"] == requested.insulation_m
        coverage &= demand["clearance_m"] == requested.clearance_m and demand["service"] == requested.system_type
        coverage &= demand.get("min_slope") == requested.min_slope
    add("fixed-service-obligations", "PASS" if coverage else "FAIL", "All declared terminals, section and insulation obligations preserved" if coverage else "A service/terminal/section obligation changed or lacks coverage")
    terminal_state = coverage
    if coverage:
        indexed_ports = {p["id"]: p for p in state.get("ports", [])}
        for identity, point, direction in ((demand["source_port"], requested.start, "SOURCE"), (demand["sink_ports"][0], requested.end, "SINK")):
            port = indexed_ports.get(identity, {})
            provenance = port.get("provenance", {})
            terminal_state &= (port.get("position_m") == list(point) and port.get("entity_id") == identity
                and port.get("coordinate_frame") == "federation" and port.get("position_status") == "KNOWN"
                and port.get("direction") == direction and port.get("service") == requested.system_type
                and port.get("section") == required_section and port.get("connection_evidence") == "scenario"
                and provenance.get("kind") == "scenario" and provenance.get("content_hash") == mission["scenario_hash"]
                and provenance.get("source_id") == f"scenario:{mission['scenario_hash']}")
    add("declared-terminal-state", "PASS" if terminal_state else "FAIL", "Persisted scenario terminal positions, service, section and provenance agree with the fixed physical mission" if terminal_state else "Persisted terminal metadata disagrees with the fixed physical mission")
    semantics = None
    if hash_match and original_match:
        semantics = _semantics(path, store.resolve_path(materialization["source_path"]), materialization, scenario, known_physical_guids)
        add("exported-physical-semantics", "PASS" if not semantics["errors"] else "FAIL", "Fresh IFC directrices, sections, terminal locations, connections and original STEP records agree" if not semantics["errors"] else "; ".join(semantics["errors"]), witness={"recomputed": semantics})
        objective = {"length_m": semantics["length_m"], "fitting_count": float(semantics["fitting_count"])}
        guids = {p["ifc_guid"] for p in materialization["added_parts"]}
        # Joint verification may schedule one fresh native counterexample here.
        # All locals remain in this exact invocation; no stored preparation or
        # prior numerical result is accepted by the continuation.
        yield results
        opening_args = None
        opening_manifest = materialization.get("authorized_opening")
        opening_edit = state.get("derived_artifacts", {}).get("opening_edit")
        if requested.authorized_opening is not None:
            try:
                from .opening import opening_context, opening_check_arguments, edit_record
                from oma.ifc.openings import check_opening_semantics
                source = next(s for s in baseline["sources"] if s["sha256"] == requested.authorized_opening.source_sha256)
                context = opening_context(baseline, requested, source)
                if materialization["source_sha256"] != source["sha256"]:
                    raise ValueError("Route materialization changed the opening's selected source")
                if opening_edit != edit_record(context, opening_manifest, digest(baseline)):
                    raise ValueError("Versioned opening edit, permission, source facts or predecessor root changed")
                if set(route_ids) != {r["id"] for r in state["routes"]} | editable:
                    raise ValueError("Changed component inventory omits or adds a physical route/host edit")
                if store.get(opening_edit["manifest_root"]) != opening_manifest:
                    raise ValueError("Opening materialization differs from its versioned manifest")
                opening_args = opening_check_arguments(path, store.resolve_path(materialization["source_path"]),
                    requested.authorized_opening.model_dump(mode="json"), opening_manifest, materialization["export_sha256"], guids,
                    terminal_guids=tuple(g for g in (requested.source_port_guid, requested.sink_port_guid) if g))
                opening_report = check_opening_semantics(path, store.resolve_path(materialization["source_path"]), **opening_args)
                if opening_report["status"] != "PASS":
                    raise ValueError("; ".join(opening_report.get("errors", [])))
                add("authorized-host-subtraction", "PASS", "Immutable permission, exact remaining support and actual IFC void/effective host independently agree",
                    participants=tuple(editable), witness={"artifact": store.put(opening_report)})
            except (ValueError, KeyError, TypeError, RuntimeError, StopIteration) as exc:
                add("authorized-host-subtraction", "FAIL", f"Opening edit verification failed: {exc}")
                add("physical-interference-and-clearance", "NOT_RUN", "No edited host may enter the obstacle inventory without its complete opening check")
                return results, objective, []
        elif opening_manifest or opening_edit:
            add("authorized-host-subtraction", "FAIL", "No opening was authorized by the immutable original request")
            add("physical-interference-and-clearance", "NOT_RUN", "Unauthorized architectural edit")
            return results, objective, []
        from .negative_probe import probe_candidate_failure
        probe = ({"status": "NOT_RUN", "reason": "Edited host requires the complete fresh replacement-obstacle check"}
                 if opening_args else probe_candidate_failure(store, state, materialization, guids, control))
        probe_root = store.put(probe)
        if probe["status"] == "FAIL":
            pair = probe["witness"]["native_pair_result"]
            add("native-forbidden-volume-counterexample", "FAIL", "One freshly reopened original obstacle intersects a new route solid",
                participants=pair["participants"], witness={"artifact": probe_root, "point": pair.get("witness", {}).get("p1"), "other_point": pair.get("witness", {}).get("p2")})
            for identity in ("physical-interference-and-clearance", "physical-self-interference", "physical-port-body-attachment",
                             "permitted-zone-containment", "independent-objective-recomputation", "engineering-service"):
                add(identity, "NOT_RUN", "Stopped after one forbidden-volume witness; full denominator and remaining feasibility were not checked", witness={"artifact": probe_root})
            return results, objective, []
        cad = cad_check_routes([store.resolve_path(s["immutable_path"]) for s in state["sources"]], path, guids, clearance_m=scenario.clearance_m,
                               numerical_tolerance_m=1e-6, coordinate_evidence=state.get("derived_artifacts", {}).get("local_coordinate_evidence"),
                               cache_directory=store.directory / "cad-cache",
                               source_representation_policy=scenario.source_representation_policy,
                               authorized_opening=opening_args,
                               checkpoint=control.checkpoint)
        cad_root = store.put(cad)
        add("physical-interference-and-clearance", cad["coordination_status"], f"Native solids checked: {cad['pairs_accounted']} route/obstacle pairs, {cad['failed_pairs']} forbidden pairs, {cad['unknown_pairs']} ambiguous pairs; datum {cad['coordinate_status']}", witness={"artifact": cad_root, "negative_probe_artifact": probe_root}, scope="New route versus every source physical obstacle; pre-existing building defects remain outside this local repair claim")
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
        from .native_zone import check_native_zone
        zone = check_native_zone(actual,scenario.allowed_zone,expected_count=len(guids),
            errors=errors,checkpoint=control.checkpoint)
        volume_length = 0.
        for solid in actual:
            if not _has_native_geometry(solid) or solid.bounds is None:
                continue
            volume_length += solid.volume_m3 / (math.pi * scenario.outer_radius ** 2)
        add("permitted-zone-containment",zone["status"],
            "Full native route envelopes checked against permitted zone boundary",witness=zone["witness"])
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
        RoutingScenario.model_validate(run["request"]["mission"]), scenario, mission, materialization, candidate["changed_ids"], control,candidate_run=run)
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
                                scope=f"{scenario.target_modality}: proposed route{' and one explicitly authorized host opening' if scenario.authorized_opening else ' only'}; numerical CAD contract, not whole-building approval",
                                results=tuple(results), objective=objective,
                                common_mode_risks=("IfcOpenShell source parsing shared with importer", "OCP numerical kernel is not a formally certified interval geometry solver", "Route specification and IFC exporter share parametric conventions; checker separately reads native geometry, topology and volume"), created_at=utcnow())
    store.record_verification(candidate_id, report)
    return report
