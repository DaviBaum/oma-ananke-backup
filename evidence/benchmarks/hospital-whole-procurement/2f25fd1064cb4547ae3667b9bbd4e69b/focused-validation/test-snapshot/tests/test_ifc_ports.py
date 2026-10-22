import json

import ifcopenshell
import numpy as np
import pytest

from oma.ifc.audit import audit_file, sha256_file
from oma.ifc.cad import _explicit_joints, cad_check_routes, load_cad
from oma.ifc.export import export_route
from oma.ifc.ports import AXIS_CONVENTION, connected_pair_errors, ownership_ledger, port_facts
from oma.ifc.recheck import recheck
from oma.normalization import normalize_connectivity
from oma.routing.checker import _semantics, check_physical_ports
from oma.routing.scenario import RoutingScenario
from test_ifc_pipeline import make_fixture


def empty_ifc2x3(path):
    model = ifcopenshell.file(schema="IFC2X3")
    origin = model.create_entity("IfcCartesianPoint", Coordinates=[0., 0., 0.])
    context = model.create_entity("IfcGeometricRepresentationContext", ContextType="Model", CoordinateSpaceDimension=3,
        Precision=1e-6, WorldCoordinateSystem=model.create_entity("IfcAxis2Placement3D", Location=origin))
    units = model.create_entity("IfcUnitAssignment", Units=[model.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE", Prefix="MILLI"),
        model.create_entity("IfcSIUnit", UnitType="PLANEANGLEUNIT", Name="RADIAN")])
    organization = model.create_entity("IfcOrganization", Name="Port fixture")
    author = model.create_entity("IfcPersonAndOrganization", ThePerson=model.create_entity("IfcPerson", FamilyName="Fixture"), TheOrganization=organization)
    application = model.create_entity("IfcApplication", ApplicationDeveloper=organization, Version="1", ApplicationFullName="OMA test", ApplicationIdentifier="OMA")
    owner = model.create_entity("IfcOwnerHistory", OwningUser=author, OwningApplication=application, ChangeAction="ADDED", CreationDate=1)
    model.create_entity("IfcProject", GlobalId=ifcopenshell.guid.new(), OwnerHistory=owner, Name="Port fixture", RepresentationContexts=[context], UnitsInContext=units)
    model.write(str(path))
    return path


def route_spec(points=None, **extras):
    return {"route_id": "correct-flow-axes", "system_type": "PRESSURE_PIPE",
            "points_m": points or [[0., 4., 3.], [4., 4., 3.], [4., 7., 3.]],
            "diameter_m": .1, "insulation_m": .02, "bend_radius_m": .3, **extras}


def mission(points=None, **extras):
    spec = route_spec(points)
    return RoutingScenario(start=spec["points_m"][0], end=spec["points_m"][-1], system_type="PRESSURE_PIPE", diameter_m=.1,
        insulation_m=.02, bend_radius_m=.3, minimum_straight_m=0, clearance_m=.1,
        allowed_zone={"min": [-20., -20., -20.], "max": [20., 20., 20.]}, scenario_terminals=True, **extras)


@pytest.mark.parametrize("schema", ["IFC4", "IFC2X3"])
def test_flow_axes_aligned_outward_normals_opposed_and_native_caps(tmp_path, schema):
    source = make_fixture(tmp_path / "source.ifc", millimeters=True) if schema == "IFC4" else empty_ifc2x3(tmp_path / "source.ifc")
    output = tmp_path / "route.ifc"
    manifest = export_route(source, output, route_spec())
    assert manifest["port_axis_convention"] == "IFC_FLOW_AXIS_V1"
    model = ifcopenshell.open(str(output))
    ledger = ownership_ledger(model)
    assert len(ledger) == 6
    for record in ledger.values():
        facts = port_facts(record["port"], record, .001)
        assert facts["errors"] == []
        sign = -1 if facts["flow_direction"] == "SINK" else 1
        assert facts["physical_outward_normal"] == pytest.approx(np.asarray(facts["flow_axis"]) * sign)
        assert record["relationships"][0].is_a("IfcRelNests" if schema == "IFC4" else "IfcRelConnectsPortToElement")
    for rel in model.by_type("IfcRelConnectsPorts"):
        assert connected_pair_errors(rel.RelatingPort, rel.RelatedPort, ledger, .001) == []
    guids = {p["ifc_guid"] for p in manifest["added_parts"]}
    objects, errors = load_cad(output, guids=guids)
    assert not errors
    physical = check_physical_ports(output, objects)
    assert len(physical) == 6 and all(p["status"] == "PASS" for p in physical)
    joints = _explicit_joints(output, guids)
    assert len(joints) == 2
    assert all(np.allclose(j["axis_a"], -np.asarray(j["axis_b"])) for j in joints.values())
    assert cad_check_routes([source], output, guids)["self_interference_status"] == "PASS"
    assert _semantics(output, source, manifest, mission())["errors"] == []


@pytest.mark.parametrize("damage", ["legacy_sink_axis", "absolute_placement", "ambiguous_owner", "duplicate_owner", "reverse_connection"])
def test_legacy_and_malformed_ports_fail_independent_checks(tmp_path, damage):
    source = make_fixture(tmp_path / "source.ifc")
    output = tmp_path / "route.ifc"
    manifest = export_route(source, output, route_spec(), fresh_recheck=False)
    model = ifcopenshell.open(str(output))
    port = model.by_guid(manifest["added_parts"][0]["ports"][0])
    if damage == "legacy_sink_axis":
        axis = port.ObjectPlacement.RelativePlacement.Axis
        axis.DirectionRatios = [-v for v in axis.DirectionRatios]
    elif damage == "absolute_placement":
        port.ObjectPlacement.PlacementRelTo = None
    elif damage in ("ambiguous_owner", "duplicate_owner"):
        owner = model.by_guid(manifest["added_parts"][1 if damage == "ambiguous_owner" else 0]["ifc_guid"])
        model.create_entity("IfcRelConnectsPortToElement", GlobalId=ifcopenshell.guid.new(), RelatingPort=port, RelatedElement=owner)
    else:
        rel = model.by_type("IfcRelConnectsPorts")[0]
        rel.RelatingPort, rel.RelatedPort = rel.RelatedPort, rel.RelatingPort
    model.write(str(output))
    manifest["export_sha256"] = sha256_file(output)
    # A forged new-convention marker must not authorize old or malformed bytes.
    manifest["port_axis_convention"] = "IFC_FLOW_AXIS_V1"
    manifest_path = output.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        recheck(manifest_path)
    objects = load_cad(output, guids={p["ifc_guid"] for p in manifest["added_parts"]})[0]
    native = check_physical_ports(output, objects)
    semantic = _semantics(output, source, manifest, mission())
    assert any(p["status"] == "FAIL" for p in native) or semantic["errors"]


def imported_terminals(tmp_path):
    base = make_fixture(tmp_path / "base.ifc")
    left = tmp_path / "left.ifc"
    a = export_route(base, left, route_spec([[-1., 4., 3.], [0., 4., 3.]], route_id="existing-left"))
    right = tmp_path / "terminals.ifc"
    b = export_route(left, right, route_spec([[4., 4., 3.], [5., 4., 3.]], route_id="existing-right"))
    return right, a["added_parts"][0]["ports"][1], b["added_parts"][0]["ports"][0]


def test_existing_source_and_sink_binding_order_and_original_preservation(tmp_path):
    source, source_guid, sink_guid = imported_terminals(tmp_path)
    output = tmp_path / "linked.ifc"
    points = [[0., 4., 3.], [4., 4., 3.]]
    manifest = export_route(source, output, route_spec(points, source_port_guid=source_guid, sink_port_guid=sink_guid))
    assert manifest["original_records_changed"] == []
    semantic = _semantics(output, source, manifest, mission(points, source_port_guid=source_guid, sink_port_guid=sink_guid))
    assert semantic["errors"] == []
    model = ifcopenshell.open(str(output))
    assert all(rel.RelatingPort.FlowDirection == "SOURCE" and rel.RelatedPort.FlowDirection == "SINK" for rel in model.by_type("IfcRelConnectsPorts"))
    objects = load_cad(source)[0]
    findings = check_physical_ports(source, objects, port_guids={source_guid, sink_guid})
    assert len(findings) == 2 and all(p["status"] == "PASS" for p in findings)
    # No implicit original-owner contact exemption exists in the CAD checker.
    result = cad_check_routes([source], output, [manifest["added_parts"][0]["ifc_guid"]], clearance_m=.1)
    assert result["coordination_status"] != "PASS"


@pytest.mark.parametrize("damage", ["sink_flow", "sink_axis", "sink_position", "missing_owner", "ambiguous_owner", "occupied", "section_mismatch", "unsupported_section"])
def test_incompatible_existing_terminal_is_never_relocated_or_silently_connected(tmp_path, damage):
    source, source_guid, sink_guid = imported_terminals(tmp_path)
    model = ifcopenshell.open(str(source))
    port = model.by_guid(sink_guid)
    if damage == "sink_flow":
        port.FlowDirection = "SOURCE"
    elif damage == "sink_axis":
        axis = port.ObjectPlacement.RelativePlacement.Axis
        axis.DirectionRatios = [-v for v in axis.DirectionRatios]
    elif damage == "sink_position":
        port.ObjectPlacement.RelativePlacement.Location.Coordinates = [4., 5., 3.]
    elif damage == "missing_owner":
        model.remove(ownership_ledger(model)[port.id()]["relationships"][0])
    elif damage == "ambiguous_owner":
        owner = model.by_type("IfcBuildingElementProxy")[0]
        model.create_entity("IfcRelConnectsPortToElement", GlobalId=ifcopenshell.guid.new(), RelatingPort=port, RelatedElement=owner)
    elif damage in ("section_mismatch", "unsupported_section"):
        owner = next(iter(ownership_ledger(model)[port.id()]["owners"].values()))
        if damage == "section_mismatch":
            owner.Representation.Representations[0].Items[0].SweptArea.Radius *= 2
        else:
            owner.Representation = None
    else:
        model.create_entity("IfcRelConnectsPorts", GlobalId=ifcopenshell.guid.new(), RelatingPort=model.by_guid(source_guid), RelatedPort=port)
    model.write(str(source))
    before = sha256_file(source)
    with pytest.raises(ValueError):
        export_route(source, tmp_path / "rejected.ifc", route_spec([[0., 4., 3.], [4., 4., 3.]], source_port_guid=source_guid, sink_port_guid=sink_guid))
    assert sha256_file(source) == before


def test_normalized_import_distinguishes_flow_axis_and_physical_normal_after_rotation(tmp_path):
    source = make_fixture(tmp_path / "source.ifc")
    output = tmp_path / "route.ifc"
    export_route(source, output, route_spec([[0., 4., 3.], [4., 4., 3.]]))
    audit = audit_file(output, geometry=False, mesh=False)
    transform = [[0., -1., 0., 10.], [1., 0., 0., 20.], [0., 0., 1., 30.], [0., 0., 0., 1.]]
    ports, _, _ = normalize_connectivity([audit], [{"id": audit["source_sha256"], "transform_m": transform}])
    sink = next(p for p in ports if p.direction == "SINK")
    assert sink.position_m == pytest.approx([6., 20., 33.])
    assert sink.axis == pytest.approx([0., 1., 0.])
    assert sink.physical_outward_normal == pytest.approx([0., -1., 0.])
    assert sink.axis_convention == AXIS_CONVENTION and sink.owner_placement_status == "OWNER_RELATIVE"
