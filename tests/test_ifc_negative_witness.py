import copy
import json
import time

import ifcopenshell
import ifcopenshell.api
import numpy as np
import pytest

from oma.ifc.audit import sha256_file
from oma.ifc.export import export_route
from oma.ifc.federation import audited_local_federation
from oma.ifc.negative_witness import find_forbidden_volume_witness, _run
from test_ifc_pipeline import make_fixture


def case(tmp_path, points=None, mutate=None):
    source = make_fixture(tmp_path / "source.ifc", missing=mutate == "missing")
    model = ifcopenshell.open(str(source))
    target = model.by_type("IfcBuildingElementProxy")[0]
    if mutate == "partial":
        representation = target.Representation.Representations[0]
        existing = representation.Items[0]
        profile = model.create_entity("IfcCircleProfileDef", ProfileType="AREA", Radius=-1.)
        malformed = model.create_entity("IfcExtrudedAreaSolid", SweptArea=profile, Position=existing.Position,
            ExtrudedDirection=existing.ExtrudedDirection, Depth=1.)
        representation.Items = list(representation.Items) + [malformed]
    elif mutate == "duplicate":
        duplicate = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuildingElementProxy")
        duplicate.GlobalId = target.GlobalId
    elif mutate == "missing":
        target = model.by_type("IfcBeam")[0]
    elif mutate == "open_shell":
        vertices = [model.create_entity("IfcCartesianPoint", Coordinates=p) for p in
                    [(1., 0., 0.), (1., 2., 0.), (1., 2., 2.), (1., 0., 2.)]]
        loop = model.create_entity("IfcPolyLoop", Polygon=vertices)
        bound = model.create_entity("IfcFaceOuterBound", Bound=loop, Orientation=True)
        face = model.create_entity("IfcFace", Bounds=[bound])
        shell = model.create_entity("IfcOpenShell", CfsFaces=[face])
        surface = model.create_entity("IfcShellBasedSurfaceModel", SbsmBoundary=[shell])
        target.Representation.Representations[0].Items = [surface]
    model.write(str(source))
    exported = tmp_path / "route.ifc"
    manifest = export_route(source, exported, {"route_id": "negative-case", "system_type": "PRESSURE_PIPE",
        "points_m": points or [[-1., 1., 1.], [3., 1., 1.]], "diameter_m": .1})
    return {"original_paths": [str(source)], "export_path": str(exported),
        "route_guids": [p["ifc_guid"] for p in manifest["added_parts"]],
        "expected_source_sha256s": [sha256_file(source)], "expected_export_sha256": sha256_file(exported),
        "authoring_source_sha256": sha256_file(source),
        "obstacle_hints": [{"source_sha256": sha256_file(source), "ifc_guid": target.GlobalId}],
        "coordinate_evidence": None, "max_probes": 16, "max_seconds": 30.}


def direct(tmp_path, request):
    return _run(request, tmp_path / "result.json")


def assert_no_authority(result):
    assert result["status"] == "NO_COUNTEREXAMPLE_FOUND", result
    assert result["continue_full_check"] is True
    assert result["full_source_denominator"] == result["feasibility_verdict"] == "NOT_RUN"
    assert result["acceptance_authority"] == "NONE"
    assert "witness" not in result


def test_fresh_child_establishes_only_one_positive_volume_counterexample(tmp_path):
    request = case(tmp_path)
    result = find_forbidden_volume_witness(**request)
    assert result["status"] == "FAIL", result
    assert result["scope"] == "ONE_COUNTEREXAMPLE"
    assert result["full_source_denominator"] == "NOT_RUN"
    assert result["probe_count"] == 1 and result["child_exit_code"] == 0
    assert result["witness"]["native_pair_result"]["common_volume_m3"] == pytest.approx(np.pi * .05**2 * 2.)
    assert result["witness"]["native_pair_result"]["participant_guids"] == [request["route_guids"][0], request["obstacle_hints"][0]["ifc_guid"]]
    assert result["witness"]["obstacle_support"]["complete_supported_body_representation"]


@pytest.mark.parametrize("points", [ [[-1., 4., 1.], [3., 4., 1.]], [[-1., 2.05, 1.], [3., 2.05, 1.]],
    [[-1., 2.06, 1.], [3., 2.06, 1.]] ])
def test_separation_tangency_and_clearance_only_never_certify_or_fail(tmp_path, points):
    assert_no_authority(direct(tmp_path, case(tmp_path, points)))


@pytest.mark.parametrize("fault", ["source_hash", "export_hash", "original_step", "route_member", "datum"])
def test_hash_original_identity_membership_and_claimed_datum_fail_closed(tmp_path, fault):
    request = case(tmp_path)
    if fault == "source_hash":
        request["expected_source_sha256s"] = ["0" * 64]
    elif fault == "export_hash":
        request["expected_export_sha256"] = "0" * 64
    elif fault == "original_step":
        model = ifcopenshell.open(request["export_path"])
        model.by_type("IfcBuildingElementProxy")[0].Name = "Changed original object"
        model.write(request["export_path"])
        request["expected_export_sha256"] = sha256_file(request["export_path"])
    elif fault == "route_member":
        request["route_guids"] = [request["obstacle_hints"][0]["ifc_guid"]]
    else:
        request["coordinate_evidence"] = {"status": "VERIFIED", "sources": [{"source_sha256": request["authoring_source_sha256"], "transform": np.eye(4).tolist()}]}
    result = direct(tmp_path, request)
    assert_no_authority(result)
    assert result["stop_reason"] == "INPUT_OR_DATUM_UNRESOLVED"


@pytest.mark.parametrize("fault", ["missing", "partial", "duplicate", "open_shell"])
def test_missing_partial_native_or_ambiguous_source_never_proves_clash(tmp_path, fault):
    result = direct(tmp_path, case(tmp_path, mutate=fault))
    assert_no_authority(result)
    assert result["probes"][0]["status"].startswith("SKIPPED")


def test_untrusted_hint_order_and_claimed_boxes_cannot_change_proof(tmp_path):
    request = case(tmp_path)
    target = request["obstacle_hints"][0]
    request["obstacle_hints"] = [{"source_sha256": "outside", "ifc_guid": target["ifc_guid"], "verified": True, "bounds": [0]*6}, target]
    request["max_probes"] = 1
    result = direct(tmp_path, request)
    assert_no_authority(result)
    assert result["stop_reason"] == "PROBE_LIMIT" and result["probe_count"] == 1
    request["max_probes"] = 2
    result = direct(tmp_path, request)
    assert result["status"] == "FAIL" and result["probe_count"] == 2


def test_native_source_mutation_during_probe_removes_authority(tmp_path, monkeypatch):
    import oma.ifc.negative_witness as module
    request = case(tmp_path)
    check_pair = module.check_pair
    def changed(*args, **kwargs):
        result = check_pair(*args, **kwargs)
        with open(request["original_paths"][0], "a") as stream:
            stream.write("\n")
        return result
    monkeypatch.setattr(module, "check_pair", changed)
    assert_no_authority(direct(tmp_path, request))


def test_hard_wall_kills_native_child_and_never_returns_partial_authority(tmp_path):
    request = case(tmp_path)
    request["max_seconds"] = .05
    start = time.perf_counter()
    result = find_forbidden_volume_witness(**request)
    assert_no_authority(result)
    assert result["stop_reason"] == "HARD_WALL_LIMIT"
    assert time.perf_counter() - start < 5.


def test_cancellation_checkpoint_propagates_without_leaking_child_authority(tmp_path):
    request = case(tmp_path)
    class Cancelled(Exception):
        pass
    def cancel(stage):
        assert stage == "native_negative_witness_wait"
        raise Cancelled("user cancellation")
    with pytest.raises(Cancelled):
        find_forbidden_volume_witness(**request, checkpoint=cancel)


def test_verified_federation_rederived_transform_and_forgery(tmp_path):
    source = make_fixture(tmp_path / "source.ifc")
    model = ifcopenshell.open(str(source))
    for kind in ("IfcSite", "IfcBuilding"):
        item = ifcopenshell.api.run("root.create_entity", model, ifc_class=kind)
        ifcopenshell.api.run("geometry.edit_object_placement", model, product=item, matrix=np.eye(4))
    model.by_type("IfcBuildingStorey")[0].Elevation = 0.
    model.write(str(source))
    target = model.by_type("IfcBuildingElementProxy")[0]
    second = tmp_path / "second.ifc"
    shift = np.eye(4)
    shift[:3, 3] = [10., 20., 30.]
    for entity in [model.by_type("IfcSite")[0], model.by_type("IfcBuilding")[0], target]:
        ifcopenshell.api.run("geometry.edit_object_placement", model, product=entity, matrix=shift)
    model.write(str(second))
    paths = [source, second]
    hashes = [sha256_file(p) for p in paths]
    datum = audited_local_federation([{"source_path": str(p), "source_sha256": sha, "units": {"status": "KNOWN"}} for p, sha in zip(paths, hashes)], hashes[0])
    assert datum["status"] == "VERIFIED"
    exported = tmp_path / "route.ifc"
    manifest = export_route(source, exported, {"route_id": "federated", "system_type": "PRESSURE_PIPE", "diameter_m": .1,
        "points_m": [[-1., 1., 1.], [3., 1., 1.]]})
    request = {"original_paths": [str(p) for p in paths], "export_path": str(exported), "route_guids": [p["ifc_guid"] for p in manifest["added_parts"]],
        "expected_source_sha256s": hashes, "expected_export_sha256": sha256_file(exported), "authoring_source_sha256": hashes[0],
        "coordinate_evidence": datum, "obstacle_hints": [{"source_sha256": hashes[1], "ifc_guid": target.GlobalId}], "max_probes": 16, "max_seconds": 30.}
    result = direct(tmp_path, request)
    assert result["status"] == "FAIL", result
    forged = copy.deepcopy(request)
    forged["coordinate_evidence"]["sources"][1]["transform"][0][3] += 1.
    assert_no_authority(direct(tmp_path, forged))
