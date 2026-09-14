import json

import numpy as np
import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.gp import gp_Pnt

from oma.ifc.cad import CadObject, _inspect_shape, check_pair, cad_check_routes, load_cad
from oma.ifc.export import export_route
from test_ifc_pipeline import make_fixture


def box(identity, origin=(0.,0.,0.), size=(1.,1.,1.)):
    shape = BRepPrimAPI_MakeBox(gp_Pnt(*origin), *size).Shape()
    bounds, volume, tolerance, valid, reason = _inspect_shape(shape)
    return CadObject(identity, identity, 1, "analytical-reference", "Box", shape, bounds, volume, tolerance, valid, reason)


def test_native_kernel_containment_crossing_and_legal_separation():
    outer = box("outer", size=(2.,2.,2.))
    contained = box("contained", origin=(.5,.5,.5), size=(.1,.1,.1))
    result = check_pair(outer, contained)
    assert result["status"] == "FAIL"
    assert result["common_volume_m3"] == pytest.approx(.001)
    assert check_pair(outer, box("separate", origin=(3.,0.,0.)), clearance_m=.5)["status"] == "PASS"
    crossing = box("crossing", origin=(-1.,.99,.99), size=(4.,.01,.01))
    assert check_pair(outer, crossing)["status"] == "FAIL"


def test_native_tangency_and_threshold_remain_ambiguous():
    first = box("first")
    assert check_pair(first, box("tangent", origin=(1.,0.,0.)))["status"] == "UNKNOWN"
    assert check_pair(first, box("threshold", origin=(1.1,0.,0.)), clearance_m=.1)["status"] == "UNKNOWN"
    assert check_pair(first, box("badclearance", origin=(1.05,0.,0.)), clearance_m=.1)["status"] == "FAIL"


def test_ifc_serialized_brep_has_native_geometry_and_units(tmp_path):
    source = make_fixture(tmp_path / "source.ifc", millimeters=True)
    shapes, failures = load_cad(source)
    assert not failures
    assert len(shapes) == 1 and shapes[0].valid
    assert shapes[0].volume_m3 == pytest.approx(8.)
    # BRepBndLib expands bounds by the CAD entity's actual kernel tolerance.
    assert shapes[0].bounds[3:] == pytest.approx((2.,2.,2.), abs=2*shapes[0].kernel_tolerance_m)


def test_reloaded_route_checks_real_fitting_joints_and_source_preservation(tmp_path):
    source = make_fixture(tmp_path / "source.ifc")
    export = tmp_path / "route.ifc"
    manifest = export_route(source, export, {"route_id":"native-route", "system_type":"PRESSURE_PIPE",
        "points_m":[[0.,4.,3.],[4.,4.,3.],[4.,7.,3.]], "diameter_m":.1, "insulation_m":.02, "bend_radius_m":.3})
    result = cad_check_routes([source], export, [p["ifc_guid"] for p in manifest["added_parts"]], clearance_m=.05)
    assert result["coordinate_status"] == "VERIFIED_SAME_SOURCE_RECORDS"
    assert result["self_interference_status"] == "PASS", json.dumps(result["self_pair_results"], indent=2)
    assert result["status"] == "PASS"
    assert result["pairs_accounted"] == 3


def test_real_sweep_through_solid_fails(tmp_path):
    source = make_fixture(tmp_path / "source.ifc")
    export = tmp_path / "route.ifc"
    manifest = export_route(source, export, {"route_id":"bad-native-route", "system_type":"PRESSURE_PIPE",
        "points_m":[[-1.,1.,1.],[3.,1.,1.]], "diameter_m":.1})
    result = cad_check_routes([source], export, [p["ifc_guid"] for p in manifest["added_parts"]])
    assert result["status"] == "FAIL"
    assert result["failed_pairs"] == 1


def test_missing_obstacle_never_becomes_empty_space(tmp_path):
    source = make_fixture(tmp_path / "source.ifc", missing=True)
    export = tmp_path / "route.ifc"
    manifest = export_route(source, export, {"route_id":"unresolved", "system_type":"PRESSURE_PIPE",
        "points_m":[[0.,4.,3.],[4.,4.,3.]], "diameter_m":.1})
    result = cad_check_routes([source], export, [p["ifc_guid"] for p in manifest["added_parts"]])
    assert result["status"] == "BLOCKED"
    assert result["missing_geometry"]


@pytest.mark.parametrize("points", [
    [[0.,4.,3.],[4.,4.,3.],[4.,4.,6.]],
    [[0.,4.,3.],[4.,4.,3.],[6.,6.,3.]],
    [[0.,4.,3.],[4.,4.,3.],[4.,1.,3.]],
])
def test_native_3d_acute_and_reverse_turn_volume(tmp_path, points):
    source = make_fixture(tmp_path / "source.ifc")
    export = tmp_path / "route.ifc"
    manifest = export_route(source, export, {"route_id":"varied-turn", "system_type":"PRESSURE_PIPE",
        "points_m":points, "diameter_m":.1, "bend_radius_m":.3})
    objects, failures = load_cad(export, guids={p["ifc_guid"] for p in manifest["added_parts"]})
    assert not failures
    assert all(p.valid for p in objects)
    assert sum(p.volume_m3 for p in objects) == pytest.approx(np.pi*.05**2*manifest["length_m"], rel=1e-8)


def test_nonadjacent_self_overlap_cannot_hide_behind_joint_exemptions(tmp_path):
    source = make_fixture(tmp_path / "source.ifc")
    export = tmp_path / "route.ifc"
    manifest = export_route(source, export, {"route_id":"self-intersection", "system_type":"PRESSURE_PIPE",
        "points_m":[[0.,4.,3.],[4.,4.,3.],[4.,7.,3.],[0.,7.,3.],[0.,3.,3.]], "diameter_m":.1, "bend_radius_m":.3})
    result = cad_check_routes([source], export, [p["ifc_guid"] for p in manifest["added_parts"]])
    assert result["self_interference_status"] == "FAIL"


def test_federation_inverse_export_preserves_project_coordinates(tmp_path):
    source = make_fixture(tmp_path / "source.ifc")
    export = tmp_path / "route.ifc"
    transform = np.eye(4)
    transform[:3,3] = [100.,200.,300.]
    manifest = export_route(source, export, {"route_id":"transformed", "system_type":"PRESSURE_PIPE",
        "points_m":[[100.,204.,303.],[104.,204.,303.]], "diameter_m":.1,
        "source_to_federation_matrix":transform.tolist()})
    assert manifest["added_parts"][0]["expected"]["start"] == pytest.approx([0.,4.,3.])
    assert manifest["reimport"]["status"] == "PASS"


def test_native_cache_cold_equivalence_and_corruption_rebuild(tmp_path):
    source = make_fixture(tmp_path / "source.ifc")
    cache = tmp_path / "cad-cache"
    cold_report, warm_report, corrupted_report = {},{},{}
    cold, cold_errors = load_cad(source, cache_directory=cache, cache_report=cold_report)
    warm, warm_errors = load_cad(source, cache_directory=cache, cache_report=warm_report)
    assert cold_report["status"] == "MISS"
    assert warm_report["status"] == "HIT_REVALIDATED"
    assert cold_errors == warm_errors == []
    assert [(x.entity_id,x.volume_m3,x.bounds,x.valid) for x in cold] == [(x.entity_id,x.volume_m3,tuple(x.bounds),x.valid) for x in warm]
    blob = next((cache / "objects").glob("*.brep.gz"))
    blob.write_bytes(b"corrupted native geometry")
    restored, errors = load_cad(source, cache_directory=cache, cache_report=corrupted_report)
    assert corrupted_report["status"] == "CORRUPT_REBUILT"
    assert errors == [] and restored[0].valid
    assert restored[0].volume_m3 == pytest.approx(cold[0].volume_m3)


def test_closed_surface_promotion_preserves_containment_blocker(tmp_path):
    import ifcopenshell
    import ifcopenshell.geom
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound
    from OCP.TopAbs import TopAbs_FACE
    from oma.ifc.cad import _subshapes,_promote_closed_surfaces
    original=box("outer",size=(2.,2.,2.))
    faces=TopoDS_Compound();builder=BRep_Builder();builder.MakeCompound(faces)
    for face in _subshapes(original.shape,TopAbs_FACE).values():
        builder.Add(faces,face)
    assert _inspect_shape(faces)[4] == "NO_CLOSED_CAD_SOLID"
    promoted,evidence=_promote_closed_surfaces(faces)
    assert evidence["source_faces"] == evidence["result_faces"] == 6
    assert evidence["free_edges"] == evidence["deleted_faces"] == 0
    bounds,volume,tolerance,valid,reason=_inspect_shape(promoted)
    solid=CadObject("promoted","promoted",2,"reference","Box",promoted,bounds,volume,tolerance,valid,reason)
    assert check_pair(solid,box("contained",origin=(.5,.5,.5),size=(.1,.1,.1)))["status"] == "FAIL"


def test_open_source_face_outer_enclosure_is_occupied_and_nearby_blocked(tmp_path):
    from test_ifc_enclosure import fixture
    source=tmp_path / "open-face.ifc"
    fixture(source)
    objects,errors=load_cad(source)
    assert not errors and len(objects)==1
    face=objects[0]
    assert not face.valid
    assert face.support_kind == "exact_source_support_enclosure"
    remote=box("remote",origin=(10.,10.,10.))
    assert check_pair(remote,face,clearance_m=.1)["status"] == "PASS"
    through=box("through",origin=(1.5,2.5,2.9),size=(.1,.1,.2))
    result=check_pair(through,face,clearance_m=.1)
    assert result["status"] == "BLOCKED"
    assert result["common_volume_m3"] is None


def test_federation_transform_retains_exact_source_enclosure(tmp_path):
    from test_ifc_enclosure import fixture
    from oma.ifc.cad import _transform_object
    source=tmp_path / "open-face.ifc"
    fixture(source)
    original=load_cad(source)[0][0]
    transform=np.array([[0.,-1.,0.,100.],[1.,0.,0.,200.],[0.,0.,1.,300.],[0.,0.,0.,1.]])
    shifted=_transform_object(original,transform)
    assert shifted.support_kind == "exact_source_support_enclosure"
    exact=shifted.support_evidence["federation_enclosure_transform"]["bounds_m"]
    assert exact == [["97", "201", "303"], ["98", "203", "303"]]
    assert shifted.bounds[0] < 97 and shifted.bounds[3] > 98
    assert not shifted.valid


def test_cache_checkpoint_cancellation_is_not_converted_to_corruption(tmp_path):
    source=make_fixture(tmp_path / "source.ifc")
    cache=tmp_path / "cache"
    load_cad(source,cache_directory=cache)
    cancellation=RuntimeError("cooperative cancellation")
    stages=[]
    def checkpoint(stage):
        stages.append(stage)
        if stage == "cad_cache_native_object":
            raise cancellation
    report={}
    with pytest.raises(RuntimeError) as caught:
        load_cad(source,cache_directory=cache,cache_report=report,checkpoint=checkpoint)
    assert caught.value is cancellation
    assert stages == ["cad_cache_native_object"]
    assert not report


def test_accelerator_false_negative_is_restored_by_independent_cpu_guard(tmp_path,monkeypatch):
    import oma.broadphase
    class FaultyIndex:
        backend="deliberately_faulty_accelerator"
        fallback_reason=None
        timings={}
        def __init__(self,*args,**kwargs):
            pass
        def query(self,queries,**kwargs):
            for i in range(len(queries)):
                yield i,np.array([],dtype=np.int64)
        def close(self):
            pass
    monkeypatch.setattr(oma.broadphase,"BroadphaseIndex",FaultyIndex)
    source=make_fixture(tmp_path / "source.ifc")
    export=tmp_path / "colliding.ifc"
    manifest=export_route(source,export,{"route_id":"gpu-false-negative","system_type":"PRESSURE_PIPE",
        "points_m":[[-1.,1.,1.],[3.,1.,1.]],"diameter_m":.1})
    checked=cad_check_routes([source],export,[part["ifc_guid"] for part in manifest["added_parts"]])
    assert checked["status"] == "FAIL"
    assert checked["pairs_accounted"] == 1
    assert checked["performance"]["broadphase"]["false_negative_guard_reinsertions"] == 1
