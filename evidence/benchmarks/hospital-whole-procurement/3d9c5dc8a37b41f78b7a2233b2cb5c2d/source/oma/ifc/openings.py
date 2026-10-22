"""One explicitly authorized rectangular through-opening in an immutable IFC.

Exact subtraction is local to the declared host frame. Native IFC realization
is checked numerically; structural/fire suitability and routing are separate.
"""
from __future__ import annotations

from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path

import numpy as np

from .audit import atomic_json, sha256_file
from .cad import CadObject, _has_native_geometry, _inspect_shape, _transform_object, load_cad
from .enclosure import ExactIfcEncloser
from .export import _guid
from oma.optimization.rectilinear_opening import compile_rectilinear_opening, verify_rectilinear_opening

CODE_SHA256 = sha256_file(__file__)
NUMERICAL_TOLERANCE_M = 1e-6


def _root(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _request(value):
    from oma.routing.opening_scenario import AuthorizedOpening
    return AuthorizedOpening.model_validate(value).model_dump(mode="json")


def _rigid(matrix):
    matrix = np.asarray(matrix, dtype=float)
    if (matrix.shape != (4, 4) or not np.isfinite(matrix).all() or not np.array_equal(matrix[3], [0., 0., 0., 1.])
            or not np.allclose(matrix[:3, :3].T @ matrix[:3, :3], np.eye(3), rtol=0, atol=1e-9)
            or np.linalg.det(matrix[:3, :3]) <= 0):
        raise ValueError("Host requires a finite proper rigid frame")
    return matrix


def _axis_declared(raw, axis):
    if axis is None:
        return
    if axis.is_a() == "IfcAxis2Placement2D":
        direction = raw.get(axis, "RefDirection")
        vector = raw.get(direction, "DirectionRatios") if direction else (Q(1), Q(0))
        if len(vector) != 2 or not any(vector):
            raise ValueError("Invalid profile frame direction")
        return
    if axis.is_a() != "IfcAxis2Placement3D":
        raise ValueError("Unsupported host placement")
    xdir, zdir = raw.get(axis, "RefDirection"), raw.get(axis, "Axis")
    x = raw.get(xdir, "DirectionRatios") if xdir else (Q(1), Q(0), Q(0))
    z = raw.get(zdir, "DirectionRatios") if zdir else (Q(0), Q(0), Q(1))
    if len(x) != 3 or len(z) != 3 or not any(x) or not any(z) or sum(a*b for a, b in zip(x, z)) != 0:
        raise ValueError("Host placement axes must be explicitly orthogonal")


def _placement_chain(raw, placement):
    seen = set()
    while placement is not None:
        if placement.id() in seen or placement.is_a() != "IfcLocalPlacement":
            raise ValueError("Cyclic or unsupported host placement chain")
        seen.add(placement.id())
        _axis_declared(raw, raw.get(placement, "RelativePlacement"))
        placement = raw.get(placement, "PlacementRelTo")


def _rectangular_descriptor(path, model, host, *, require_unvoided=True):
    import ifcopenshell.util.placement
    if not (host.is_a("IfcWall") or host.is_a("IfcSlab") or host.is_a("IfcOpeningElement")):
        raise ValueError("First opening contract supports walls and slabs only")
    if require_unvoided and any(r.RelatingBuildingElement == host for r in model.by_type("IfcRelVoidsElement")):
        raise ValueError("Existing host voids require a separate edit contract")
    if require_unvoided and getattr(host, "IsDecomposedBy", ()):
        raise ValueError("Composite or decomposed hosts are unsupported")
    if host.Representation is None:
        raise ValueError("Missing host representation")
    bodies = [r for r in host.Representation.Representations if r.RepresentationIdentifier == "Body"]
    if len(bodies) != 1 or len(bodies[0].Items) != 1:
        raise ValueError("Host requires exactly one complete Body item")
    if any(r.RepresentationIdentifier not in ("Body", "Axis") for r in host.Representation.Representations):
        raise ValueError("Unsupported additional host representation")
    item = bodies[0].Items[0]
    if item.is_a() != "IfcExtrudedAreaSolid" or item.SweptArea.is_a() != "IfcRectangleProfileDef":
        raise ValueError("Host requires a direct rectangular linear extrusion")
    profile = item.SweptArea
    if profile.ProfileType != "AREA":
        raise ValueError("Host rectangle must be an area profile")
    helper = ExactIfcEncloser(path, model)
    raw = helper.raw
    units = [u for a in model.by_type("IfcUnitAssignment") for u in a.Units if getattr(u, "UnitType", None) == "LENGTHUNIT"]
    if len(units) != 1:
        raise ValueError("Ambiguous or undeclared source length units")
    scale = helper._unit(units[0])
    dimensions = [raw.get(profile, "XDim") * scale, raw.get(profile, "YDim") * scale, raw.get(item, "Depth") * scale]
    if any(not isinstance(v, Q) or v <= 0 for v in dimensions):
        raise ValueError("Positive rational source rectangle dimensions required")
    direction = raw.get(item.ExtrudedDirection, "DirectionRatios")
    if len(direction) != 3 or direction[0] or direction[1] or direction[2] <= 0:
        raise ValueError("Oblique or reversed host extrusion unsupported")
    _placement_chain(raw, host.ObjectPlacement)
    _axis_declared(raw, item.Position)
    _axis_declared(raw, profile.Position)
    product_matrix = ifcopenshell.util.placement.get_local_placement(host.ObjectPlacement)
    item_matrix = ifcopenshell.util.placement.get_axis2placement(item.Position) if item.Position else np.eye(4)
    profile_matrix = ifcopenshell.util.placement.get_axis2placement(profile.Position) if profile.Position else np.eye(4)
    frame = product_matrix @ item_matrix @ profile_matrix
    frame[:3, 3] *= float(scale)
    frame = _rigid(frame)
    bounds = [[str(-dimensions[0]/2), str(-dimensions[1]/2), "0"],
              [str(dimensions[0]/2), str(dimensions[1]/2), str(dimensions[2])]]
    descriptor = {"schema": "oma.rectangular-host/1", "source_sha256": raw.source_sha256,
        "host_guid": host.GlobalId, "host_step_id": host.id(), "host_type": host.is_a(),
        "body_representation_step_id": bodies[0].id(), "extrusion_step_id": item.id(), "profile_step_id": profile.id(),
        "units_to_m": str(scale), "host_bounds_local_m": bounds, "host_local_to_source_matrix_m": frame.tolist(),
        "frame_scope": "SOURCE_LOCAL_ENGINEERING_METRES_NUMERICAL_RIGID_FRAME; NO_FEDERATION_OR_GIS_CERTIFICATION",
        "source_dimensions": "RAW_STEP_DECIMAL_RATIONALS", "source_enclosure_reader_sha256": __import__(__package__ + ".enclosure", fromlist=["CODE_SHA256"]).CODE_SHA256}
    descriptor["frame_root"] = _root({"source": raw.source_sha256, "frame": frame.tolist(), "scale": str(scale)})
    descriptor["host_geometry_root"] = _root(descriptor)
    return descriptor


def _box_shape(bounds, frame):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt
    lo, hi = [np.asarray([float(Q(v)) for v in row]) for row in bounds]
    shape = BRepPrimAPI_MakeBox(gp_Pnt(*lo), *(hi-lo)).Shape()
    box, volume, tolerance, valid, reason = _inspect_shape(shape)
    obj = CadObject("expected-cell", "expected-cell", 1, "independent-local-cell", "Box", shape, box, volume, tolerance, valid, reason)
    return _transform_object(obj, frame).shape


def _cell_union(cells, frame):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
    shapes = [_box_shape(cell["bounds_local"], frame) for cell in cells]
    result = shapes[0]
    for shape in shapes[1:]:
        operation = BRepAlgoAPI_Fuse(result, shape)
        operation.SetFuzzyValue(0.)
        operation.Build()
        if not operation.IsDone():
            raise ValueError("Expected source-cell union failed")
        result = operation.Shape()
    return result


def _native_agreement(actual, expected):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_SOLID
    from .cad import _subshapes
    if not _has_native_geometry(actual):
        raise ValueError("Host has no complete valid native solid authority")
    bounds, expected_volume, tolerance, valid, reason = _inspect_shape(expected)
    if not valid or len(_subshapes(actual.shape, TopAbs_SOLID)) != 1 or len(_subshapes(expected, TopAbs_SOLID)) != 1:
        raise ValueError("Host realization must remain one valid closed solid")
    extents = np.asarray(bounds[3:]) - np.asarray(bounds[:3])
    area_scale = 2 * (extents[0]*extents[1] + extents[1]*extents[2] + extents[0]*extents[2])
    linear_budget = NUMERICAL_TOLERANCE_M + tolerance + actual.kernel_tolerance_m
    volume_budget = linear_budget * area_scale
    differences = []
    for first, second in ((actual.shape, expected), (expected, actual.shape)):
        operation = BRepAlgoAPI_Cut(first, second)
        operation.SetFuzzyValue(0.)
        operation.Build()
        if not operation.IsDone():
            raise ValueError("Native host symmetric difference failed")
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(operation.Shape(), props)
        volume = float(props.Mass())
        if not np.isfinite(volume) or volume < 0 or volume > volume_budget:
            raise ValueError("Native host support differs from expected local-cell support")
        differences.append(volume)
    if abs(actual.volume_m3 - expected_volume) > volume_budget:
        raise ValueError("Native host volume disagrees with expected support")
    return {"status": "PASS", "actual_volume_m3": actual.volume_m3, "expected_volume_m3": expected_volume,
        "symmetric_difference_volumes_m3": differences, "linear_budget_m": linear_budget, "volume_budget_m3": volume_budget,
        "proof_level": "NUMERICAL_CAD_SYMMETRIC_DIFFERENCE_AND_VOLUME; NOT_FORMAL_NATIVE_EQUALITY"}


def inspect_host(source_path, host_guid, host_step_id=None):
    import ifcopenshell
    path = Path(source_path)
    model = ifcopenshell.open(str(path))
    matching = [e for e in model.by_type("IfcElement") if e.GlobalId == host_guid]
    if len(matching) != 1 or (host_step_id is not None and matching[0].id() != host_step_id):
        raise ValueError("Host GUID/STEP identity missing or ambiguous")
    if not (matching[0].is_a("IfcWall") or matching[0].is_a("IfcSlab")):
        raise ValueError("Only a wall or slab can be an editable host in this contract")
    descriptor = _rectangular_descriptor(path, model, matching[0])
    objects, errors = load_cad(path, guids={host_guid})
    if errors or len(objects) != 1:
        raise ValueError("Host native conversion failed or is incomplete")
    expected = _box_shape(descriptor["host_bounds_local_m"], descriptor["host_local_to_source_matrix_m"])
    agreement = _native_agreement(objects[0], expected)
    return {**descriptor, "status": "ELIGIBLE_NATIVE_RECTANGULAR_HOST", "native_agreement": agreement,
            "opening_permission": "NOT_INFERRED", "structural_fire_status": "NOT_CHECKED"}


def _prepare(source_path, request):
    request = _request(request)
    descriptor = inspect_host(source_path, request["host_guid"], request["host_step_id"])
    if descriptor["source_sha256"] != request["source_sha256"] or descriptor["host_geometry_root"] != request["host_geometry_root"]:
        raise ValueError("Immutable host source/geometry identity changed")
    roots = {"source": descriptor["source_sha256"], "host": descriptor["host_geometry_root"], "frame": descriptor["frame_root"], "authorization": _root(request)}
    opening = request["opening_bounds_local_m"]
    bounds = [opening["min"], opening["max"]]
    certificate = compile_rectilinear_opening(descriptor["host_bounds_local_m"], bounds,
        through_axis=request["through_axis"], context_root=_root(request), source_roots=roots)
    verified = verify_rectilinear_opening(descriptor["host_bounds_local_m"], bounds, certificate,
        through_axis=request["through_axis"], context_root=_root(request), source_roots=roots)
    if verified.get("status") != "PASS":
        raise ValueError("Independent exact opening-cell verification failed")
    return request, descriptor, certificate, verified


def export_opening(source_path, export_path, request, fresh_recheck=False):
    import ifcopenshell
    import ifcopenshell.util.placement
    source, destination = Path(source_path).resolve(), Path(export_path).resolve()
    if source == destination or destination.exists():
        raise ValueError("Opening export requires a new immutable output path")
    request, descriptor, certificate, verified = _prepare(source, request)
    model = ifcopenshell.open(str(source))
    before = {e.id(): str(e) for e in model}
    host = model.by_id(request["host_step_id"])
    scale = float(Q(descriptor["units_to_m"]))
    frame = np.asarray(descriptor["host_local_to_source_matrix_m"])
    owner = host.OwnerHistory
    namespace = "oma-opening:" + _root(request)
    def point(coords):
        return model.create_entity("IfcCartesianPoint", Coordinates=[float(v)/scale for v in coords])
    def direction(coords):
        return model.create_entity("IfcDirection", DirectionRatios=[float(v) for v in coords])
    def axis(coords, z=(0., 0., 1.), x=(1., 0., 0.)):
        return model.create_entity("IfcAxis2Placement3D", Location=point(coords), Axis=direction(z), RefDirection=direction(x))
    parent = ifcopenshell.util.placement.get_local_placement(host.ObjectPlacement)
    parent[:3, 3] *= scale
    relative = _rigid(np.linalg.inv(parent) @ frame)
    placement = model.create_entity("IfcLocalPlacement", PlacementRelTo=host.ObjectPlacement,
        RelativePlacement=axis(relative[:3, 3], relative[:3, 2], relative[:3, 0]))
    lo, hi = [np.asarray(request["opening_bounds_local_m"][k]) for k in ("min", "max")]
    profile_position = model.create_entity("IfcAxis2Placement2D", Location=model.create_entity("IfcCartesianPoint", Coordinates=[0., 0.]))
    profile = model.create_entity("IfcRectangleProfileDef", ProfileType="AREA", Position=profile_position,
        XDim=float(hi[0]-lo[0])/scale, YDim=float(hi[1]-lo[1])/scale)
    solid = model.create_entity("IfcExtrudedAreaSolid", SweptArea=profile,
        Position=axis(((lo[0]+hi[0])/2, (lo[1]+hi[1])/2, lo[2])), ExtrudedDirection=direction((0., 0., 1.)), Depth=float(hi[2]-lo[2])/scale)
    context = model.by_id(descriptor["body_representation_step_id"]).ContextOfItems
    representation = model.create_entity("IfcShapeRepresentation", ContextOfItems=context, RepresentationIdentifier="Body", RepresentationType="SweptSolid", Items=[solid])
    opening = model.create_entity("IfcOpeningElement", GlobalId=_guid(namespace, "opening"), OwnerHistory=owner,
        Name="OMA explicitly authorized scenario opening", ObjectPlacement=placement,
        Representation=model.create_entity("IfcProductDefinitionShape", Representations=[representation]))
    if hasattr(opening, "PredefinedType"):
        opening.PredefinedType = "OPENING"
    relation = model.create_entity("IfcRelVoidsElement", GlobalId=_guid(namespace, "void-relation"), OwnerHistory=owner,
        RelatingBuildingElement=host, RelatedOpeningElement=opening)
    if any(str(model.by_id(step)) != record for step, record in before.items()):
        raise ValueError("Opening writer changed original source STEP records")
    destination.parent.mkdir(parents=True, exist_ok=True)
    model.write(str(destination))
    manifest = {"schema": "oma.authorized-opening/1", "source_sha256": descriptor["source_sha256"],
        "export_sha256": sha256_file(destination), "request": request, "request_root": _root(request),
        "host": descriptor, "opening_guid": opening.GlobalId, "opening_step_id": opening.id(),
        "void_relation_guid": relation.GlobalId, "void_relation_step_id": relation.id(),
        "added_step_ids": sorted(e.id() for e in model if e.id() not in before), "original_records_changed": [],
        "opening_records_root": _root({str(e.id()): str(e) for e in model if e.id() not in before}),
        "exact_cell_certificate": certificate, "exact_cell_verification": verified, "writer_code_sha256": CODE_SHA256,
        "scope": "SCENARIO_GEOMETRY_ONLY; NO_STRUCTURAL_FIRE_OR_WHOLE_BUILDING_CERTIFICATE"}
    if fresh_recheck:
        manifest["recheck"] = check_opening_semantics(destination, source, request, manifest)
    atomic_json(destination.with_suffix(".opening.json"), manifest)
    return manifest


def check_opening_semantics(export_path, source_path, request, manifest, *, allowed_new_step_ids=(),
                            allowed_new_element_guids=(), allowed_existing_terminal_guids=(), expected_export_sha256=None):
    """Reopen actual IFC; no manifest claim can substitute for geometry checks."""
    import ifcopenshell
    try:
        request, descriptor, certificate, verified = _prepare(source_path, request)
        if manifest["request_root"] != _root(request) or manifest["request"] != request:
            raise ValueError("Opening request or permission changed")
        permitted_steps = set(allowed_new_step_ids)
        permitted_elements = set(allowed_new_element_guids)
        permitted_terminals = set(allowed_existing_terminal_guids)
        if (permitted_steps or permitted_elements or permitted_terminals) and expected_export_sha256 is None:
            raise ValueError("Combined route/opening check requires its immutable final export hash")
        export_hash = expected_export_sha256 or manifest["export_sha256"]
        if manifest["source_sha256"] != sha256_file(source_path) or export_hash != sha256_file(export_path):
            raise ValueError("Source or export byte identity mismatch")
        if manifest["exact_cell_certificate"] != certificate:
            raise ValueError("Opening expected-support certificate changed")
        before, after = ifcopenshell.open(str(source_path)), ifcopenshell.open(str(export_path))
        original_ids = {e.id() for e in before}
        original_terminals = {}
        for guid in permitted_terminals:
            matches = [e for e in before.by_type("IfcDistributionPort") if e.GlobalId == guid]
            if len(matches) != 1 or matches[0].ConnectedTo or matches[0].ConnectedFrom:
                raise ValueError("Requested original terminal is absent, ambiguous or already occupied")
            original_terminals[matches[0].id()] = guid
        if any(str(e) != str(after.by_id(e.id())) for e in before):
            raise ValueError("An original source STEP record changed")
        additions = [e for e in after if e.id() not in original_ids]
        opening_steps = set(manifest["added_step_ids"])
        if original_ids & permitted_steps or opening_steps & permitted_steps:
            raise ValueError("Additional route STEP allowance overlaps source or opening records")
        if {e.id() for e in additions} != opening_steps | permitted_steps:
            raise ValueError("Appended STEP accounting changed")
        if _root({str(step): str(after.by_id(step)) for step in opening_steps}) != manifest["opening_records_root"]:
            raise ValueError("Immutable authored opening records changed")
        allowed = [after.by_id(step) for step in permitted_steps]
        if {e.GlobalId for e in allowed if e.is_a("IfcElement")} != permitted_elements:
            raise ValueError("Separately checked route element accounting changed")
        used_terminals = []
        for entity in allowed:
            if (entity.is_a("IfcFeatureElement") or entity.is_a("IfcRelVoidsElement")
                    or entity.is_a("IfcRelProjectsElement")):
                raise ValueError("Additional route allowance cannot authorize another host geometric effect")
            if entity.is_a("IfcRelationship"):
                original_targets = [linked for linked in after.traverse(entity, max_levels=1)
                    if linked.id() in original_ids and linked.is_a("IfcObjectDefinition")]
                if original_targets:
                    contained = list(entity.RelatedElements) if entity.is_a() == "IfcRelContainedInSpatialStructure" else []
                    intentional_containment = (bool(contained)
                        and len({e.id() for e in contained}) == len(contained)
                        and all(e.id() in permitted_steps and e.is_a("IfcElement") and e.GlobalId in permitted_elements for e in contained)
                        and entity.RelatingStructure.id() in original_ids
                        and entity.RelatingStructure.is_a("IfcSpatialStructureElement")
                        and {e.id() for e in original_targets} == {entity.RelatingStructure.id()})
                    intentional_terminal = False
                    if entity.is_a() == "IfcRelConnectsPorts":
                        from .ports import connected_pair_errors, ownership_ledger
                        import ifcopenshell.util.unit
                        endpoints = [entity.RelatingPort, entity.RelatedPort]
                        old = [p for p in endpoints if p.id() in original_terminals]
                        new = [p for p in endpoints if p.id() in permitted_steps and p.is_a("IfcDistributionPort")]
                        intentional_terminal = (len(old) == len(new) == 1
                            and {e.id() for e in original_targets} == {old[0].id()}
                            and entity.RealizingElement is not None and entity.RealizingElement.id() in permitted_steps
                            and entity.RealizingElement.GlobalId in permitted_elements
                            and not connected_pair_errors(endpoints[0], endpoints[1], ownership_ledger(after),
                                ifcopenshell.util.unit.calculate_unit_scale(after)))
                        if intentional_terminal:
                            used_terminals.append(old[0].GlobalId)
                    if not intentional_containment and not intentional_terminal:
                        raise ValueError("Additional relationship changes an original object's inverse semantics")
        if len(used_terminals) != len(set(used_terminals)) or set(used_terminals) != permitted_terminals:
            raise ValueError("Requested original terminal attachment accounting changed")
        roots = [e for e in additions if e.id() in opening_steps and e.is_a("IfcRoot")]
        openings = [e for e in roots if e.is_a() == "IfcOpeningElement"]
        relations = [e for e in roots if e.is_a() == "IfcRelVoidsElement"]
        if len(roots) != 2 or len(openings) != 1 or len(relations) != 1:
            raise ValueError("Exactly one authorized opening and one void relation are required")
        opening, relation = openings[0], relations[0]
        for guid in (request["host_guid"], opening.GlobalId, relation.GlobalId):
            if len([e for e in after.by_type("IfcRoot") if e.GlobalId == guid]) != 1:
                raise ValueError("Ambiguous source host/opening/relationship GUID")
        host = after.by_id(request["host_step_id"])
        if (opening.GlobalId != manifest["opening_guid"] or opening.id() != manifest["opening_step_id"]
                or relation.GlobalId != manifest["void_relation_guid"] or relation.id() != manifest["void_relation_step_id"]
                or relation.RelatingBuildingElement != host or relation.RelatedOpeningElement != opening):
            raise ValueError("Opening void relation identity or host binding changed")
        if len([r for r in after.by_type("IfcRelVoidsElement") if r.RelatingBuildingElement == host or r.RelatedOpeningElement == opening]) != 1:
            raise ValueError("Additional or ambiguous opening relationships")
        reachable = {e.id() for root in (opening, relation) for e in after.traverse(root)}
        if not opening_steps <= reachable:
            raise ValueError("Unaccounted appended geometry or relationship")
        if opening.ObjectPlacement.PlacementRelTo != host.ObjectPlacement:
            raise ValueError("Opening placement must be relative to its actual host")
        actual_opening = _rectangular_descriptor(export_path, after, opening, require_unvoided=False)
        expected_frame = np.asarray(descriptor["host_local_to_source_matrix_m"])
        local = np.linalg.inv(expected_frame) @ np.asarray(actual_opening["host_local_to_source_matrix_m"])
        if not np.allclose(local[:3, :3], np.eye(3), rtol=0, atol=1e-10):
            raise ValueError("Opening orientation differs from its authorized host-local box")
        actual_bounds = np.asarray([[float(Q(v)) for v in row] for row in actual_opening["host_bounds_local_m"]]) + local[:3, 3]
        requested_bounds = np.asarray([request["opening_bounds_local_m"][k] for k in ("min", "max")])
        if not np.allclose(actual_bounds, requested_bounds, rtol=0, atol=NUMERICAL_TOLERANCE_M):
            raise ValueError("Actual opening geometry differs from the authorized local volume")
        objects, errors = load_cad(export_path, guids={request["host_guid"]})
        if errors or len(objects) != 1:
            raise ValueError("Effective host native conversion failed")
        expected = _cell_union(certificate["remaining_cells"], expected_frame)
        agreement = _native_agreement(objects[0], expected)
        return {"status": "PASS", "scope": "ONE_AUTHORIZED_HOST_GEOMETRIC_SUBTRACTION", "source_sha256": sha256_file(source_path),
            "export_sha256": sha256_file(export_path), "request_root": _root(request), "host_guid": request["host_guid"],
            "host_step_id": request["host_step_id"], "host_geometry_root": descriptor["host_geometry_root"],
            "edited_host_geometry_root": _root({"original": descriptor["host_geometry_root"], "cut": certificate["root"], "export": sha256_file(export_path)}),
            "opening_guid": opening.GlobalId, "void_relation_guid": relation.GlobalId,
            "exact_cell_verification": verified, "native_effective_host": agreement, "original_record_count": len(original_ids),
            "remaining_cell_count": len(certificate["remaining_cells"]), "checker_code_sha256": CODE_SHA256,
            "separately_checked_route_step_count": len(permitted_steps),
            "separately_checked_route_guids": sorted(permitted_elements),
            "explicit_original_terminal_guids": sorted(permitted_terminals),
            "route_clearance_status": "NOT_RUN", "all_other_obstacles_status": "NOT_RUN", "structural_fire_status": "NOT_CHECKED"}
    except (ValueError, KeyError, TypeError, AttributeError, RuntimeError, OverflowError) as exc:
        return {"status": "FAIL", "scope": "ONE_AUTHORIZED_HOST_GEOMETRIC_SUBTRACTION", "errors": [f"{type(exc).__name__}: {exc}"],
                "route_clearance_status": "NOT_RUN", "all_other_obstacles_status": "NOT_RUN", "checker_code_sha256": CODE_SHA256}


def load_checked_effective_host(export_path, source_path, request, manifest, *, source_to_federation_matrix=None,
                                allowed_new_step_ids=(), allowed_new_element_guids=(), allowed_existing_terminal_guids=(), expected_export_sha256=None):
    """Return (CadObject, report) only after fresh authored-opening checking.

    Object identity remains the original source/GUID/STEP for exact replacement.
    Its shape is the edited source's effective native solid in source-world
    metres, optionally transformed by an independently authenticated caller's
    federation matrix. The report retains edited bytes and geometry identities.
    This function does not authenticate an externally supplied federation matrix.
    """
    from dataclasses import replace
    report = check_opening_semantics(export_path, source_path, request, manifest,
        allowed_new_step_ids=allowed_new_step_ids, allowed_new_element_guids=allowed_new_element_guids,
        allowed_existing_terminal_guids=allowed_existing_terminal_guids,
        expected_export_sha256=expected_export_sha256)
    if report["status"] != "PASS":
        raise ValueError("Edited host failed independent opening check: " + "; ".join(report.get("errors", [])))
    objects, errors = load_cad(export_path, guids={report["host_guid"]})
    if errors or len(objects) != 1 or not _has_native_geometry(objects[0]):
        raise ValueError("Edited native host disappeared after checking")
    if sha256_file(export_path) != report["export_sha256"] or sha256_file(source_path) != report["source_sha256"]:
        raise ValueError("Source or edited artifact changed during host reconstruction")
    obj = objects[0]
    obj = replace(obj, entity_id=report["source_sha256"] + ":" + str(report["host_step_id"]),
        source_sha256=report["source_sha256"], support_evidence={**(obj.support_evidence or {}),
            "effective_host_edit": {"source_sha256": report["source_sha256"], "edited_source_sha256": report["export_sha256"],
                "request_root": report["request_root"], "edited_host_geometry_root": report["edited_host_geometry_root"],
                "native_frame": "SOURCE_WORLD_ENGINEERING_METRES", "replacement_scope": "EXACTLY_ONE_ORIGINAL_SOURCE_GUID_STEP"}})
    if source_to_federation_matrix is not None:
        matrix = _rigid(source_to_federation_matrix)
        obj = _transform_object(obj, matrix)
        report = {**report, "caller_supplied_federation_matrix": matrix.tolist(), "federation_authentication": "CALLER_OBLIGATION"}
    return obj, report
