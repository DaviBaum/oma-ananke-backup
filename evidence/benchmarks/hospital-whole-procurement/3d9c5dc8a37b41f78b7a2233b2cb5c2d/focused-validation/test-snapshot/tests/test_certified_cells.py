from copy import deepcopy
import time

import ifcopenshell
import numpy as np
import pytest

from oma.ifc.audit import sha256_file
from oma.routing.certified_cells import build_certified_cell_proposals, verify_cell_coverage
from oma.routing.scenario import RoutingScenario
from test_ifc_openings import host_fixture, opening_request


def _scenario(**extra):
    return RoutingScenario(start=(0.,-1.,1.5), end=(0.,1.,1.5), system_type="PRESSURE_PIPE",
        diameter_m=.1, insulation_m=0., bend_radius_m=.2, minimum_straight_m=.01,
        clearance_m=.1, allowed_zone={"min":[-4.,-2.,-1.],"max":[4.,2.,4.]}, scenario_terminals=True, **extra)


def _sources(path):
    return [{"path":path,"sha256":sha256_file(path),"transform_m":np.eye(4).tolist()}]


def _run(path, **options):
    return build_certified_cell_proposals(_sources(path),_scenario(),context_root="frozen-fixture",grid_divisions=6,**options)


def test_actual_ifc_wall_detour_is_checked_and_complete_without_inner_occupancy(tmp_path):
    source,_ = host_fixture(tmp_path/"wall.ifc")
    result = _run(source)
    assert result["status"] == "CHECKED_GEOMETRIC_PROPOSALS", result
    assert result["independent_check"]["status"] == result["coverage_check"]["status"] == "PASS"
    assert result["coverage_check"]["physical_elements"] == result["coverage_check"]["loaded_obstacles"] == 1
    assert not result["model"]["inner_obstacles"]
    assert all(c["classification"] != "BLOCKED" for c in result["certificate"]["cells"])
    assert all(not p["route_acceptance"] and not p["physical_infeasibility_claim"] for p in result["proposals"])
    # A continuous path from negative to positive Y must leave the wall's X/Z
    # footprint; this assertion is independent of the cell producer.
    assert all(any(abs(p[0]) > 2. or p[2] < 0. or p[2] > 3. for p in route["points_m"]) for route in result["proposals"])
    assert verify_cell_coverage(result["coverage"],result["model"])["status"] == "PASS"


@pytest.mark.parametrize("fault",["hash","duplicate_source","missing_frame","translated_frame","unsupported_policy"])
def test_source_identity_and_frame_failures_do_not_produce_paths(tmp_path,fault):
    source,_ = host_fixture(tmp_path/"wall.ifc")
    specs, scenario = _sources(source), _scenario()
    if fault == "hash": specs[0]["sha256"] = "b"*64
    elif fault == "duplicate_source": specs += specs
    elif fault == "missing_frame": specs[0]["transform_m"] = None
    elif fault == "translated_frame": specs[0]["transform_m"][0][3] = 1.
    else: scenario = scenario.model_copy(update={"source_representation_policy":"UNSUPPORTED"})
    result = build_certified_cell_proposals(specs,scenario,context_root="frozen")
    assert result["status"] == "BLOCKED" and not result["proposals"],result


@pytest.mark.parametrize("fault",["omitted_object","duplicate_object","wrong_identity","partial_native","nan_tolerance"])
def test_actual_loaded_geometry_failures_are_not_hidden_by_finite_boxes(tmp_path,monkeypatch,fault):
    from oma.ifc import cad
    source,_ = host_fixture(tmp_path/"wall.ifc")
    load = cad.load_cad
    def corrupted(*args,**kwargs):
        objects,errors = load(*args,**kwargs)
        if fault == "omitted_object": return [],[]
        if fault == "duplicate_object": return objects+objects,errors
        if fault == "wrong_identity": objects[0].source_sha256 = "b"*64
        elif fault == "partial_native": objects[0].support_evidence["complete_supported_body_representation"] = False
        elif fault == "nan_tolerance": objects[0].kernel_tolerance_m = float("nan")
        return objects,errors
    monkeypatch.setattr(cad,"load_cad",corrupted)
    result = _run(source)
    assert result["status"] == "BLOCKED" and not result["proposals"],result


@pytest.mark.parametrize("child_kind",["IfcSpace","IfcOpeningElement","IfcWall"])
def test_empty_assembly_nonphysical_void_or_missing_leaf_cannot_disappear(tmp_path,child_kind):
    source,_ = host_fixture(tmp_path/"wall.ifc")
    model = ifcopenshell.open(str(source))
    parent = model.create_entity("IfcElementAssembly",GlobalId=ifcopenshell.guid.new())
    child = model.create_entity(child_kind,GlobalId=ifcopenshell.guid.new())
    model.create_entity("IfcRelAggregates",GlobalId=ifcopenshell.guid.new(),RelatingObject=parent,RelatedObjects=[child])
    model.write(str(source))
    result = _run(source)
    assert result["status"] == "BLOCKED" and result["coverage"]["blockers"] and not result["proposals"],result


@pytest.mark.parametrize("relation_type",["IfcRelAggregates","IfcRelNests"])
def test_representation_free_assembly_with_covered_wall_has_full_denominator(tmp_path,relation_type):
    source,guid = host_fixture(tmp_path/"wall.ifc")
    model = ifcopenshell.open(str(source))
    parent = model.create_entity("IfcElementAssembly",GlobalId=ifcopenshell.guid.new())
    model.create_entity(relation_type,GlobalId=ifcopenshell.guid.new(),RelatingObject=parent,RelatedObjects=[model.by_guid(guid)])
    model.write(str(source))
    result = _run(source)
    assert result["status"] == "CHECKED_GEOMETRIC_PROPOSALS",result
    assert result["coverage_check"]["physical_elements"] == 2
    assert result["coverage_check"]["representation_free_assemblies"] == 1


def test_unknown_grid_budget_and_authorized_host_edit_cannot_become_route_proofs(tmp_path):
    source,guid = host_fixture(tmp_path/"wall.ifc")
    result = _run(source,max_cells=1)
    assert result["status"] == "UNKNOWN" and not result["proposals"]
    result = _run(source,deadline=time.monotonic()-1)
    assert result["status"] == "UNKNOWN" and result["reason"] == "CERTIFIED_CELL_DEADLINE"
    scenario = _scenario(authorized_opening=opening_request(source,guid))
    result = build_certified_cell_proposals(_sources(source),scenario,context_root="edit")
    assert result["status"] == "BLOCKED_NOT_APPLICABLE" and not result["proposals"]


@pytest.mark.parametrize("fault",["missing_denominator","missing_object","smaller_group","shifted_image","added_inner","bad_assembly"])
def test_independent_coverage_rejects_forged_complete_models(tmp_path,fault):
    source,_ = host_fixture(tmp_path/"wall.ifc")
    result = _run(source)
    assert result["coverage_check"]["status"] == "PASS"
    coverage, model = deepcopy(result["coverage"]),deepcopy(result["model"])
    if fault == "missing_denominator": coverage["physical_ids"] = []
    elif fault == "missing_object": coverage["objects"] = []
    elif fault == "smaller_group": model["outer_obstacles"][0]["bounds"][1][0] = "0"
    elif fault == "shifted_image": coverage["objects"][0]["bounds_m"][0][0] = "0"
    elif fault == "added_inner": model["inner_obstacles"] = [model["outer_obstacles"][0]]
    else:
        coverage["assemblies"].append({"id":"cycle","children":["cycle"]})
        coverage["physical_ids"].append("cycle")
    assert verify_cell_coverage(coverage,model)["status"] == "FAIL"


def test_complete_grouping_and_out_of_zone_omission_are_independently_checked(tmp_path):
    source,guid = host_fixture(tmp_path/"three-walls.ifc")
    model = ifcopenshell.open(str(source))
    host = model.by_guid(guid)
    for x in (1.,100.):
        placement = model.create_entity("IfcLocalPlacement",RelativePlacement=model.create_entity("IfcAxis2Placement3D",
            Location=model.create_entity("IfcCartesianPoint",Coordinates=[x,0.,0.])))
        model.create_entity("IfcWall",GlobalId=ifcopenshell.guid.new(),ObjectPlacement=placement,Representation=host.Representation)
    model.write(str(source))
    result = _run(source,max_outer_boxes=1)
    assert result["coverage_check"]["status"] == "PASS",result
    assert result["coverage_check"]["physical_elements"] == 3
    assert len(result["model"]["outer_obstacles"]) == 1
    assert sum(o["disposition"] == "GROUPED_OUTER_COVER" for o in result["coverage"]["objects"]) == 2
    omitted = next(o for o in result["coverage"]["objects"] if o["disposition"].startswith("CERTIFIED_OUTSIDE"))
    omitted["separating_normal"] = ["0","0","0"]
    assert verify_cell_coverage(result["coverage"],result["model"])["status"] == "FAIL"


@pytest.mark.parametrize("nonplanar",[False,True])
def test_source_enclosure_keeps_native_invalidity_and_explicit_completion_policy(tmp_path,nonplanar):
    from test_ifc_enclosure import fixture
    source = tmp_path/"face.ifc"
    fixture(source,nonplanar=nonplanar)
    result = _run(source)
    if nonplanar:
        assert result["status"] == "BLOCKED",result
        result = build_certified_cell_proposals(_sources(source),_scenario(source_representation_policy="NATIVE_CAD_WITH_SOURCE_VERTEX_HULL_ENCLOSURES"),
            context_root="explicit-completion-family",grid_divisions=4)
    assert result["coverage_check"]["status"] == "PASS",result
    obj = result["coverage"]["objects"][0]
    assert obj["support_authority"] == "CHECKED_EXACT_SUPPORTED_SOURCE_OUTER_ENCLOSURE"
    assert obj["source_native_valid"] is False and obj["source_native_reason"]
    assert result["model"]["inner_obstacles"] == []


def test_two_sources_require_fresh_common_frame_and_full_frame_denominator(tmp_path):
    from oma.ifc.federation import audited_local_federation
    first,guid = host_fixture(tmp_path/"first.ifc")
    model = ifcopenshell.open(str(first))
    origin = model.by_guid(guid).ObjectPlacement
    site = model.create_entity("IfcSite",GlobalId=ifcopenshell.guid.new(),ObjectPlacement=origin)
    building = model.create_entity("IfcBuilding",GlobalId=ifcopenshell.guid.new(),ObjectPlacement=origin)
    model.create_entity("IfcBuildingStorey",GlobalId=ifcopenshell.guid.new(),Name="Shared level",Elevation=0.)
    model.write(str(first))
    origin.RelativePlacement.Location.Coordinates = [10.,20.,30.]
    second = tmp_path/"second.ifc"
    model.write(str(second))
    specs = _sources(first)+_sources(second)
    result = build_certified_cell_proposals(specs,_scenario(),context_root="both")
    assert result["status"] == "BLOCKED"
    audits = [{"source_path":str(s["path"]),"source_sha256":s["sha256"],"units":{"status":"KNOWN"}} for s in specs]
    frame = audited_local_federation(audits)
    assert frame["status"] == "VERIFIED",frame
    for spec,entry in zip(specs,frame["sources"]): spec["transform_m"] = entry["transform"]
    result = build_certified_cell_proposals(specs,_scenario(),context_root="both",coordinate_evidence=frame,grid_divisions=6)
    assert result["coverage_check"]["status"] == "PASS",result
    assert result["coverage_check"]["physical_elements"] == 2
    for fault in ("changed_transform","extra_frame_source"):
        altered_specs,altered_frame = deepcopy(specs),deepcopy(frame)
        if fault == "changed_transform": altered_specs[1]["transform_m"][0][3] += 1.
        else: altered_frame["sources"].append(altered_frame["sources"][0])
        result = build_certified_cell_proposals(altered_specs,_scenario(),context_root="both",coordinate_evidence=altered_frame)
        assert result["status"] == "BLOCKED" and not result["proposals"],result


def test_source_mutation_after_native_loading_discards_all_proposals(tmp_path,monkeypatch):
    from oma.ifc import cad
    source,guid = host_fixture(tmp_path/"wall.ifc")
    original = cad.load_cad
    def changing(*args,**kwargs):
        result = original(*args,**kwargs)
        model = ifcopenshell.open(str(source))
        model.by_guid(guid).Name = "Source changed while checking"
        model.write(str(source))
        return result
    monkeypatch.setattr(cad,"load_cad",changing)
    result = _run(source)
    assert result["status"] == "BLOCKED" and not result["proposals"]
    assert "changed during support loading" in result["reason"]


def test_worker_cancellation_propagates_instead_of_becoming_geometry_unknown(tmp_path):
    from oma.worker import Cancelled
    source,_ = host_fixture(tmp_path/"wall.ifc")
    def cancel(stage): raise Cancelled()
    with pytest.raises(Cancelled): _run(source,checkpoint=cancel)
