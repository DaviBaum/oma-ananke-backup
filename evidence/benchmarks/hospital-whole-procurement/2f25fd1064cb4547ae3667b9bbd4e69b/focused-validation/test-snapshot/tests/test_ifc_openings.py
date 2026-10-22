from copy import deepcopy
from fractions import Fraction
import json

import ifcopenshell
import numpy as np
import pytest

from oma.ifc.audit import sha256_file
from oma.ifc.cad import cad_check_routes, check_pair
from oma.ifc.export import export_route
from oma.ifc.openings import inspect_host, export_opening, check_opening_semantics, load_checked_effective_host, _root
from test_ifc_ports import empty_ifc2x3
from test_ifc_cad import box


def host_fixture(path, *, schema="IFC4", millimeters=False, rotated=False):
    if schema == "IFC2X3":
        empty_ifc2x3(path)
        model = ifcopenshell.open(str(path))
        # Existing fixture explicitly uses millimetres.
        scale = .001
    else:
        model = ifcopenshell.file(schema=schema)
        scale = .001 if millimeters else 1.
        origin = model.create_entity("IfcCartesianPoint", Coordinates=[0., 0., 0.])
        context = model.create_entity("IfcGeometricRepresentationContext", ContextType="Model", CoordinateSpaceDimension=3,
            Precision=1e-6, WorldCoordinateSystem=model.create_entity("IfcAxis2Placement3D", Location=origin))
        units = model.create_entity("IfcUnitAssignment", Units=[model.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE", Prefix="MILLI" if millimeters else None), model.create_entity("IfcSIUnit", UnitType="PLANEANGLEUNIT", Name="RADIAN")])
        model.create_entity("IfcProject", GlobalId=ifcopenshell.guid.new(), RepresentationContexts=[context], UnitsInContext=units)
    context = model.by_type("IfcGeometricRepresentationContext")[0]
    owner = model.by_type("IfcOwnerHistory")[0] if model.by_type("IfcOwnerHistory") else None
    def point(coords): return model.create_entity("IfcCartesianPoint", Coordinates=[float(v)/scale for v in coords])
    def direction(coords): return model.create_entity("IfcDirection", DirectionRatios=[float(v) for v in coords])
    def axis(coords=(0., 0., 0.), z=(0., 0., 1.), x=(1., 0., 0.)):
        return model.create_entity("IfcAxis2Placement3D", Location=point(coords), Axis=direction(z), RefDirection=direction(x))
    placement = model.create_entity("IfcLocalPlacement", RelativePlacement=axis((10., 20., 30.), (0., 1., 0.), (0., 0., 1.)) if rotated else axis())
    profile_position = model.create_entity("IfcAxis2Placement2D", Location=model.create_entity("IfcCartesianPoint", Coordinates=[0., 0.]))
    profile = model.create_entity("IfcRectangleProfileDef", ProfileType="AREA", Position=profile_position, XDim=4./scale, YDim=.4/scale)
    solid = model.create_entity("IfcExtrudedAreaSolid", SweptArea=profile, Position=axis(), ExtrudedDirection=direction((0., 0., 1.)), Depth=3./scale)
    representation = model.create_entity("IfcShapeRepresentation", ContextOfItems=context, RepresentationIdentifier="Body", RepresentationType="SweptSolid", Items=[solid])
    wall = model.create_entity("IfcWall", GlobalId=ifcopenshell.guid.new(), OwnerHistory=owner, Name="Declared editable fixture host",
        ObjectPlacement=placement, Representation=model.create_entity("IfcProductDefinitionShape", Representations=[representation]))
    model.write(str(path))
    return path, wall.GlobalId


def opening_request(path, guid):
    host = inspect_host(path, guid)
    return {"source_sha256": host["source_sha256"], "host_guid": guid, "host_step_id": host["host_step_id"],
        "host_geometry_root": host["host_geometry_root"], "opening_bounds_local_m": {"min": [-.5, -.4, 1.], "max": [.5, .4, 2.]},
        "allowed_opening_bounds_local_m": {"min": [-.6, -.5, .9], "max": [.6, .5, 2.1]}, "through_axis": 1,
        "permission": {"mode": "EXPLICIT_USER_GEOMETRIC_EDIT", "statement": "Synthetic fixture explicitly permits this bounded geometric opening.",
            "evidence_roots": ["a"*64], "engineering_scope": "SCENARIO_GEOMETRY_ONLY"}}


@pytest.mark.parametrize("schema,millimeters,rotated", [("IFC4", False, False), ("IFC4", True, True), ("IFC2X3", True, False), ("IFC2X3", True, True)])
def test_native_opening_preserves_source_and_matches_exact_four_cells(tmp_path, schema, millimeters, rotated):
    source, guid = host_fixture(tmp_path / "source.ifc", schema=schema, millimeters=millimeters, rotated=rotated)
    request = opening_request(source, guid)
    original = source.read_bytes()
    output = tmp_path / "edited.ifc"
    manifest = export_opening(source, output, request, fresh_recheck=True)
    checked = manifest["recheck"]
    assert checked["status"] == "PASS", checked
    assert source.read_bytes() == original
    assert checked["remaining_cell_count"] == 4
    assert checked["exact_cell_verification"]["status"] == "PASS"
    bounds = manifest["host"]["host_bounds_local_m"]
    assert Fraction(checked["exact_cell_verification"]["removed_volume_m3"]) == Fraction(bounds[1][1]) - Fraction(bounds[0][1])
    assert checked["native_effective_host"]["actual_volume_m3"] == pytest.approx(4.4)
    edited, report = load_checked_effective_host(output, source, request, manifest)
    assert edited.guid == guid and edited.source_sha256 == sha256_file(source)
    assert edited.entity_id == sha256_file(source) + ":" + str(request["host_step_id"])
    assert report["route_clearance_status"] == report["all_other_obstacles_status"] == "NOT_RUN"
    assert edited.support_evidence["effective_host_edit"]["edited_source_sha256"] == sha256_file(output)


def test_actual_round_route_passes_only_through_cut_and_colliding_edge_still_fails(tmp_path):
    source, guid = host_fixture(tmp_path / "source.ifc")
    request = opening_request(source, guid)
    edited = tmp_path / "edited.ifc"
    export_opening(source, edited, request, fresh_recheck=True)
    for x, expected in [(0., "PASS"), (.48, "FAIL")]:
        spec = {"route_id": "cut-route", "system_type": "PRESSURE_PIPE", "points_m": [[x, -1., 1.5], [x, 1., 1.5]], "diameter_m": .1}
        out = tmp_path / (str(x) + ".ifc")
        materialized = export_route(edited, out, spec)
        checked = cad_check_routes([edited], out, [p["ifc_guid"] for p in materialized["added_parts"]], clearance_m=.1)
        assert checked["status"] == expected, checked
        assert checked["obstacle_count"] == 1
    baseline = tmp_path / "uncut-route.ifc"
    materialized = export_route(source, baseline, {"route_id": "baseline", "system_type": "PRESSURE_PIPE", "points_m": [[0., -1., 1.5], [0., 1., 1.5]], "diameter_m": .1})
    assert cad_check_routes([source], baseline, [p["ifc_guid"] for p in materialized["added_parts"]])["status"] == "FAIL"


@pytest.mark.parametrize("fault", ["source", "host_guid", "host_step", "geometry", "permission", "outside_allowed", "blind", "touching_edge"])
def test_invalid_or_unpermitted_opening_is_rejected_before_export(tmp_path, fault):
    source, guid = host_fixture(tmp_path / "source.ifc")
    request = opening_request(source, guid)
    if fault == "source": request["source_sha256"] = "b"*64
    elif fault == "host_guid": request["host_guid"] = ifcopenshell.guid.new()
    elif fault == "host_step": request["host_step_id"] += 1
    elif fault == "geometry": request["host_geometry_root"] = "b"*64
    elif fault == "permission": request.pop("permission")
    elif fault == "outside_allowed": request["opening_bounds_local_m"]["max"][0] = .7
    elif fault == "blind": request["opening_bounds_local_m"]["max"][1] = 0.
    else:
        request["opening_bounds_local_m"]["max"][0] = 2.
        request["allowed_opening_bounds_local_m"]["max"][0] = 2.
    with pytest.raises((ValueError, RuntimeError)):
        export_opening(source, tmp_path / "forbidden.ifc", request)
    assert not (tmp_path / "forbidden.ifc").exists()


@pytest.mark.parametrize("fault", ["missing_relation", "wrong_host", "shift_equal_volume", "blind", "extra_opening", "source_record", "hidden_body", "detached_geometry", "absolute_placement"])
def test_actual_ifc_mutations_fail_independent_opening_check(tmp_path, fault):
    source, guid = host_fixture(tmp_path / "source.ifc")
    request = opening_request(source, guid)
    output = tmp_path / "edited.ifc"
    manifest = export_opening(source, output, request)
    model = ifcopenshell.open(str(output))
    opening = model.by_guid(manifest["opening_guid"])
    relation = model.by_guid(manifest["void_relation_guid"])
    solid = opening.Representation.Representations[0].Items[0]
    if fault == "missing_relation": model.remove(relation)
    elif fault == "wrong_host": relation.RelatingBuildingElement = opening
    elif fault == "shift_equal_volume": solid.Position.Location.Coordinates = [1., 0., 1.]
    elif fault == "blind":
        solid.SweptArea.YDim = .2
        solid.Position.Location.Coordinates = [0., -.2, 1.]
    elif fault == "extra_opening":
        extra = model.create_entity("IfcOpeningElement", GlobalId=ifcopenshell.guid.new(), Representation=opening.Representation, ObjectPlacement=opening.ObjectPlacement)
        model.create_entity("IfcRelVoidsElement", GlobalId=ifcopenshell.guid.new(), RelatingBuildingElement=model.by_guid(guid), RelatedOpeningElement=extra)
    elif fault == "source_record": model.by_guid(guid).Name = "Unauthorized changed source"
    elif fault == "hidden_body": opening.Representation.Representations[0].Items = [solid, solid]
    elif fault == "detached_geometry": model.create_entity("IfcCartesianPoint", Coordinates=[500., 0., 0.])
    else: opening.ObjectPlacement.PlacementRelTo = None
    model.write(str(output))
    # Forged adjacent hashes/counts cannot hide wrong actual geometry/relations.
    manifest["export_sha256"] = sha256_file(output)
    before_ids = {e.id() for e in ifcopenshell.open(str(source))}
    manifest["added_step_ids"] = sorted(e.id() for e in model if e.id() not in before_ids)
    manifest["opening_records_root"] = _root({str(e.id()): str(e) for e in model if e.id() not in before_ids})
    checked = check_opening_semantics(output, source, request, manifest)
    assert checked["status"] == "FAIL", checked


def test_permission_replacement_and_stale_native_host_cannot_pass(tmp_path, monkeypatch):
    import oma.ifc.openings as openings
    source, guid = host_fixture(tmp_path / "source.ifc")
    request = opening_request(source, guid)
    output = tmp_path / "edited.ifc"
    manifest = export_opening(source, output, request)
    changed = deepcopy(request)
    changed["permission"]["statement"] = "This is a different immutable permission statement."
    assert check_opening_semantics(output, source, changed, manifest)["status"] == "FAIL"
    original_loader = openings.load_cad
    def stale_loader(path, **kwargs):
        return original_loader(source if str(path) == str(output) else path, **kwargs)
    monkeypatch.setattr(openings, "load_cad", stale_loader)
    result = check_opening_semantics(output, source, request, manifest)
    assert result["status"] == "FAIL" and "differs from expected" in result["errors"][0]


def test_final_route_file_keeps_opening_identity_and_exact_effective_host_replacement(tmp_path):
    source, guid = host_fixture(tmp_path / "source.ifc")
    request = opening_request(source, guid)
    opening_path = tmp_path / "opening.ifc"
    opening = export_opening(source, opening_path, request)
    output = tmp_path / "route.ifc"
    route = export_route(opening_path, output, {"route_id": "combined", "system_type": "PRESSURE_PIPE",
        "points_m": [[0., -1., 1.5], [0., 1., 1.5]], "diameter_m": .1})
    opening_ids = {e.id() for e in ifcopenshell.open(str(opening_path))}
    allowed_steps = {e.id() for e in ifcopenshell.open(str(output))} - opening_ids
    kwargs = {"allowed_new_step_ids": allowed_steps, "allowed_new_element_guids": {p["ifc_guid"] for p in route["added_parts"]},
        "expected_export_sha256": sha256_file(output)}
    checked = check_opening_semantics(output, source, request, opening, **kwargs)
    assert checked["status"] == "PASS", checked
    obj, report = load_checked_effective_host(output, source, request, opening, **kwargs)
    assert obj.source_sha256 == sha256_file(source) and report["export_sha256"] == sha256_file(output)
    assert check_pair(box("in-opening", origin=(-.05, -.3, 1.45), size=(.1, .6, .1)), obj)["status"] == "PASS"
    kwargs.pop("expected_export_sha256")
    assert check_opening_semantics(output, source, request, opening, **kwargs)["status"] == "FAIL"


@pytest.mark.parametrize("reuse", [True, False])
def test_route_record_allowance_never_authorizes_another_void(tmp_path, reuse):
    source, guid = host_fixture(tmp_path / "source.ifc")
    request = opening_request(source, guid)
    output = tmp_path / "opening.ifc"
    manifest = export_opening(source, output, request)
    model = ifcopenshell.open(str(output))
    if reuse:
        other = model.by_guid(manifest["opening_guid"])
        allowed_elements = set()
    else:
        other = model.create_entity("IfcOpeningElement", GlobalId=ifcopenshell.guid.new())
        allowed_elements = {other.GlobalId}
    model.create_entity("IfcRelVoidsElement", GlobalId=ifcopenshell.guid.new(), RelatingBuildingElement=model.by_guid(guid), RelatedOpeningElement=other)
    original_ids = {e.id() for e in ifcopenshell.open(str(source))}
    allowed = {e.id() for e in model} - original_ids - set(manifest["added_step_ids"])
    model.write(str(output))
    result = check_opening_semantics(output, source, request, manifest, allowed_new_step_ids=allowed,
        allowed_new_element_guids=allowed_elements, expected_export_sha256=sha256_file(output))
    assert result["status"] == "FAIL" and "cannot authorize another host geometric effect" in result["errors"][0]


@pytest.mark.parametrize("fault", ["hidden_body", "wrong_profile", "negative_dimension", "oblique", "nonorthogonal", "missing_units", "existing_void", "duplicate_guid"])
def test_source_host_eligibility_rejects_unsupported_or_ambiguous_geometry(tmp_path, fault):
    source, guid = host_fixture(tmp_path / "source.ifc")
    model = ifcopenshell.open(str(source))
    host = model.by_guid(guid)
    representation = host.Representation.Representations[0]
    solid = representation.Items[0]
    if fault == "hidden_body": representation.Items = [solid, solid]
    elif fault == "wrong_profile": solid.SweptArea = model.create_entity("IfcCircleProfileDef", ProfileType="AREA", Radius=.1)
    elif fault == "negative_dimension": solid.SweptArea.XDim = -1.
    elif fault == "oblique": solid.ExtrudedDirection.DirectionRatios = [.1, 0., 1.]
    elif fault == "nonorthogonal": solid.Position.RefDirection.DirectionRatios = [1., 0., .1]
    elif fault == "missing_units": model.by_type("IfcUnitAssignment")[0].Units = []
    elif fault == "existing_void":
        opening = model.create_entity("IfcOpeningElement", GlobalId=ifcopenshell.guid.new())
        model.create_entity("IfcRelVoidsElement", GlobalId=ifcopenshell.guid.new(), RelatingBuildingElement=host, RelatedOpeningElement=opening)
    else: model.create_entity("IfcWall", GlobalId=guid)
    model.write(str(source))
    with pytest.raises(ValueError): inspect_host(source, guid)


def test_native_checker_protects_original_space_properties_but_allows_route_containment(tmp_path):
    source, guid = host_fixture(tmp_path / "source.ifc")
    model = ifcopenshell.open(str(source))
    space = model.create_entity("IfcSpace", GlobalId=ifcopenshell.guid.new(), Name="Protected source space")
    model.create_entity("IfcBuildingStorey", GlobalId=ifcopenshell.guid.new(), Name="Original containing storey")
    space_id = space.id()
    model.write(str(source))
    request = opening_request(source, guid)
    opening_path = tmp_path / "opening.ifc"
    manifest = export_opening(source, opening_path, request)
    final_path = tmp_path / "route.ifc"
    route = export_route(opening_path, final_path, {"route_id": "contained", "system_type": "PRESSURE_PIPE",
        "points_m": [[0., -1., 1.5], [0., 1., 1.5]], "diameter_m": .1})
    original_ids = {e.id() for e in ifcopenshell.open(str(source))}
    model = ifcopenshell.open(str(final_path))
    assert len(model.by_type("IfcRelContainedInSpatialStructure")) == 1
    allowed_steps = {e.id() for e in model} - original_ids - set(manifest["added_step_ids"])
    kwargs = {"allowed_new_step_ids": allowed_steps, "allowed_new_element_guids": {p["ifc_guid"] for p in route["added_parts"]},
        "expected_export_sha256": sha256_file(final_path)}
    assert check_opening_semantics(final_path, source, request, manifest, **kwargs)["status"] == "PASS"
    value = model.create_entity("IfcPropertySingleValue", Name="Unauthorized status", NominalValue=model.create_entity("IfcLabel", "Approved"))
    properties = model.create_entity("IfcPropertySet", GlobalId=ifcopenshell.guid.new(), Name="Unapproved inverse property", HasProperties=[value])
    model.create_entity("IfcRelDefinesByProperties", GlobalId=ifcopenshell.guid.new(), RelatedObjects=[model.by_id(space_id)], RelatingPropertyDefinition=properties)
    model.write(str(final_path))
    kwargs.update(allowed_new_step_ids={e.id() for e in model} - original_ids - set(manifest["added_step_ids"]), expected_export_sha256=sha256_file(final_path))
    checked = check_opening_semantics(final_path, source, request, manifest, **kwargs)
    assert checked["status"] == "FAIL" and "inverse semantics" in checked["errors"][0]
    assert all(str(e) == str(model.by_id(e.id())) for e in ifcopenshell.open(str(source)))


def test_only_explicit_original_terminal_can_receive_one_compatible_route_connection(tmp_path):
    bare, guid = host_fixture(tmp_path / "bare.ifc")
    source = tmp_path / "original.ifc"
    original_route = export_route(bare, source, {"route_id": "original-port-owner", "system_type": "PRESSURE_PIPE",
        "points_m": [[0., -2., 1.5], [0., -1., 1.5]], "diameter_m": .1, "insulation_m": .02})
    terminal = original_route["added_parts"][0]["ports"][1]
    other_terminal = original_route["added_parts"][0]["ports"][0]
    request = opening_request(source, guid)
    opening_path = tmp_path / "opening.ifc"
    manifest = export_opening(source, opening_path, request)
    final_path = tmp_path / "route.ifc"
    route = export_route(opening_path, final_path, {"route_id": "new-attached-route", "system_type": "PRESSURE_PIPE",
        "points_m": [[0., -1., 1.5], [0., 1., 1.5]], "diameter_m": .1, "insulation_m": .02, "source_port_guid": terminal})
    model = ifcopenshell.open(str(final_path))
    original_ids = {e.id() for e in ifcopenshell.open(str(source))}
    kwargs = {"allowed_new_step_ids": {e.id() for e in model} - original_ids - set(manifest["added_step_ids"]),
        "allowed_new_element_guids": {p["ifc_guid"] for p in route["added_parts"]}, "expected_export_sha256": sha256_file(final_path)}
    assert check_opening_semantics(final_path, source, request, manifest, **kwargs)["status"] == "FAIL"
    checked = check_opening_semantics(final_path, source, request, manifest, allowed_existing_terminal_guids={terminal}, **kwargs)
    assert checked["status"] == "PASS", checked
    assert checked["explicit_original_terminal_guids"] == [terminal]
    assert checked["all_other_obstacles_status"] == "NOT_RUN"
    for wrong in ({other_terminal}, {terminal, other_terminal}, {ifcopenshell.guid.new()}):
        assert check_opening_semantics(final_path, source, request, manifest, allowed_existing_terminal_guids=wrong, **kwargs)["status"] == "FAIL"
    connection = next(r for r in model.by_type("IfcRelConnectsPorts") if r.RelatingPort.GlobalId == terminal)
    model.create_entity("IfcRelConnectsPorts", GlobalId=ifcopenshell.guid.new(), RelatingPort=connection.RelatingPort,
        RelatedPort=connection.RelatedPort, RealizingElement=connection.RealizingElement)
    model.write(str(final_path))
    kwargs.update(allowed_new_step_ids={e.id() for e in model} - original_ids - set(manifest["added_step_ids"]), expected_export_sha256=sha256_file(final_path))
    assert check_opening_semantics(final_path, source, request, manifest, allowed_existing_terminal_guids={terminal}, **kwargs)["status"] == "FAIL"
