from pathlib import Path
import json

import ifcopenshell
import ifcopenshell.api
import numpy as np
import pytest

from oma.ifc.audit import audit_file, federation_manifest, load_mesh_payload
from oma.ifc.check import check_files
from oma.ifc.export import export_route, fillet_route


def make_fixture(path, missing=False, containment=False, millimeters=False):
    model = ifcopenshell.api.run("project.create_file", version="IFC4")
    project = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcProject", name="Independent analytic boxes")
    ifcopenshell.api.run("unit.assign_unit", model, length={"is_metric": True, "raw": "MILLIMETERS" if millimeters else "METERS"})
    unit_assignment = model.by_type("IfcUnitAssignment")[0]
    radian = model.create_entity("IfcSIUnit", UnitType="PLANEANGLEUNIT", Name="RADIAN")
    unit_assignment.Units = list(unit_assignment.Units)+[radian]
    context = ifcopenshell.api.run("context.add_context", model, context_type="Model")
    body = ifcopenshell.api.run("context.add_context", model, context_type="Model", context_identifier="Body", target_view="MODEL_VIEW", parent=context)
    storey = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="Ground")
    ifcopenshell.api.run("aggregate.assign_object", model, products=[storey], relating_object=project)
    shapes = [((0., 0., 0.), (2., 2., 2.)), ((0.5, 0.5, 0.5), (0.3, 0.3, 0.3))] if containment else [((0., 0., 0.), (2., 2., 2.))]
    for origin, size in shapes:
        product = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuildingElementProxy", name="Analytic solid")
        representation = ifcopenshell.api.run("geometry.add_wall_representation", model, context=body, length=size[0], thickness=size[1], height=size[2])
        ifcopenshell.api.run("geometry.assign_representation", model, product=product, representation=representation)
        matrix = np.eye(4)
        matrix[:3, 3] = origin
        ifcopenshell.api.run("geometry.edit_object_placement", model, product=product, matrix=matrix)
        ifcopenshell.api.run("spatial.assign_container", model, products=[product], relating_structure=storey)
    if missing:
        ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBeam", name="Obstacle without geometry")
    model.write(str(path))
    return path


def test_every_physical_product_accounted_missing_obstacle_blocks(tmp_path):
    path = make_fixture(tmp_path / "missing.ifc", missing=True)
    audit = audit_file(path, tmp_path / "audit")
    assert audit["physical_object_count"] == 2
    assert audit["physical_geometry_counts"] == {"represented": 1, "unresolved": 1}
    assert audit["blockers"][0]["code"] == "INCOMPLETE_PHYSICAL_GEOMETRY"
    assert audit["coordination_verification"]["status"] != "PASS"
    assert len(load_mesh_payload(audit)["meshes"]) == 1
    assert audit["inferred_connections"] == []


def test_world_units_are_meters_and_no_centering(tmp_path):
    path = make_fixture(tmp_path / "millimeters.ifc", millimeters=True)
    audit = audit_file(path, tmp_path / "audit")
    assert audit["units"]["source_to_m"] == 0.001
    assert audit["bounds"]["min"] == pytest.approx([0., 0., 0.])
    assert audit["bounds"]["max"] == pytest.approx([2., 2., 2.])
    assert federation_manifest([audit], "one")["alignment_status"] == "UNRESOLVED"
    with pytest.raises(ValueError, match="rigid"):
        federation_manifest([audit], "bad", {audit["source_id"]: {"matrix": np.diag([1000., 1000., 1000., 1.]).tolist()}})


def test_intersection_baseline_catches_complete_containment(tmp_path):
    path = make_fixture(tmp_path / "contained.ifc", containment=True)
    result = check_files([path])
    assert result["issue_count"] >= 1
    assert result["mesh_check_status"] == "FAIL"
    assert result["coordination_status"] != "PASS"


def test_tree_checkpoint_reaches_safe_prequery_boundary(tmp_path):
    source=make_fixture(tmp_path / "source.ifc")
    stages=[]
    def checkpoint(stage):
        stages.append(stage)
        if stage == "ifc_tree_intersection":
            raise RuntimeError("pause/cancel before native query")
    with pytest.raises(RuntimeError,match="pause/cancel"):
        check_files([source],checkpoint=checkpoint)
    assert stages == ["ifc_tree_source","ifc_tree_object","ifc_tree_intersection"]


def test_multiple_declared_port_owners_remain_explicitly_ambiguous(tmp_path):
    source=make_fixture(tmp_path / "ambiguous-port.ifc")
    model=ifcopenshell.open(str(source))
    first=model.by_type("IfcBuildingElementProxy")[0]
    second=model.create_entity("IfcBeam",GlobalId=ifcopenshell.guid.new(),Name="Second declared owner")
    port=model.create_entity("IfcDistributionPort",GlobalId=ifcopenshell.guid.new(),Name="Ambiguous declared port")
    for owner in (first,second):
        model.create_entity("IfcRelConnectsPortToElement",GlobalId=ifcopenshell.guid.new(),RelatingPort=port,RelatedElement=owner)
    model.write(str(source))
    audited=audit_file(source,geometry=False,mesh=False)
    declared=audited["ports"][0]
    assert declared["owner_status"] == "ambiguous"
    assert declared["owner_step_id"] is None
    assert declared["owner_step_ids"] == sorted([first.id(),second.id()])
    assert len(declared["owner_relationship_step_ids"]) == 2


def test_export_round_sweeps_and_connectivity_fresh_process(tmp_path):
    path = make_fixture(tmp_path / "before.ifc", millimeters=True)
    result = export_route(path, tmp_path / "after.ifc", {
        "route_id": "independent-pipe", "system_type": "PRESSURE_PIPE", "points_m": [[0.,4.,3.],[4.,4.,3.],[4.,7.,3.]],
        "diameter_m": 0.1, "insulation_m": 0.02, "bend_radius_m": 0.3})
    assert len(result["added_parts"]) == 3
    assert result["reimport"]["status"] == "PASS"
    assert result["reimport"]["fresh_process"]
    assert result["original_records_changed"] == []
    assert result["explicit_internal_connections"] == 2
    assert result["status"] == "DRAFT"


def test_ifc2x3_export_profiles_have_required_positions(tmp_path):
    from oma.ifc.cad import load_cad
    model=ifcopenshell.file(schema="IFC2X3")
    origin=model.create_entity("IfcCartesianPoint",Coordinates=[0.,0.,0.])
    placement=model.create_entity("IfcAxis2Placement3D",Location=origin)
    context=model.create_entity("IfcGeometricRepresentationContext",ContextType="Model",CoordinateSpaceDimension=3,
                                Precision=1e-6,WorldCoordinateSystem=placement)
    units=model.create_entity("IfcUnitAssignment",Units=[model.create_entity("IfcSIUnit",UnitType="LENGTHUNIT",Name="METRE"),
                                                        model.create_entity("IfcSIUnit",UnitType="PLANEANGLEUNIT",Name="RADIAN")])
    organization=model.create_entity("IfcOrganization",Name="Independent IFC fixture")
    person=model.create_entity("IfcPerson",FamilyName="Fixture")
    author=model.create_entity("IfcPersonAndOrganization",ThePerson=person,TheOrganization=organization)
    application=model.create_entity("IfcApplication",ApplicationDeveloper=organization,Version="1",ApplicationFullName="OMA test",ApplicationIdentifier="OMA")
    owner=model.create_entity("IfcOwnerHistory",OwningUser=author,OwningApplication=application,ChangeAction="ADDED",CreationDate=1)
    model.create_entity("IfcProject",GlobalId=ifcopenshell.guid.new(),OwnerHistory=owner,Name="IFC2X3 profile fidelity fixture",RepresentationContexts=[context],UnitsInContext=units)
    source=tmp_path / "ifc2x3.ifc";model.write(str(source))
    target=tmp_path / "physical-route.ifc"
    exported=export_route(source,target,{"route_id":"ifc2x3-required-positions","system_type":"PRESSURE_PIPE",
        "points_m":[[0.,4.,3.],[4.,4.,3.],[4.,7.,3.]],"diameter_m":.1,"bend_radius_m":.3})
    assert exported["reimport"]["status"] == "PASS"
    reopened=ifcopenshell.open(str(target))
    assert all(profile.Position is not None for profile in reopened.by_type("IfcCircleProfileDef"))
    objects,errors=load_cad(target)
    assert not errors and len(objects)==3 and all(obj.valid for obj in objects)


def test_fillet_rejects_impossible_fittings_and_original_overwrite(tmp_path):
    with pytest.raises(ValueError, match="consume"):
        fillet_route([[0,0,0],[0.1,0,0],[0.1,0.1,0]], 0.3)
    path = make_fixture(tmp_path / "protected.ifc")
    with pytest.raises(ValueError, match="overwritten"):
        export_route(path, path, {})


def test_degree_angle_units_export_exact_quarter_turn(tmp_path):
    path = make_fixture(tmp_path / "degrees.ifc")
    model = ifcopenshell.open(str(path))
    radians = model.create_entity("IfcSIUnit", UnitType="PLANEANGLEUNIT", Name="RADIAN")
    conversion = model.create_entity("IfcMeasureWithUnit", ValueComponent=model.create_entity("IfcReal", np.pi/180), UnitComponent=radians)
    dimensions = model.create_entity("IfcDimensionalExponents", 0,0,0,0,0,0,0)
    degree = model.create_entity("IfcConversionBasedUnit", Dimensions=dimensions, UnitType="PLANEANGLEUNIT", Name="DEGREE", ConversionFactor=conversion)
    assignment = model.by_type("IfcUnitAssignment")[0]
    assignment.Units = [u for u in assignment.Units if getattr(u, "UnitType", None) != "PLANEANGLEUNIT"]+[degree]
    model.write(str(path))
    result = export_route(path, tmp_path / "degree-route.ifc", {"route_id":"degree-route", "system_type":"PRESSURE_PIPE",
        "points_m":[[0.,4.,3.],[4.,4.,3.],[4.,7.,3.]], "diameter_m":.1, "bend_radius_m":.3})
    assert result["reimport"]["status"] == "PASS"
