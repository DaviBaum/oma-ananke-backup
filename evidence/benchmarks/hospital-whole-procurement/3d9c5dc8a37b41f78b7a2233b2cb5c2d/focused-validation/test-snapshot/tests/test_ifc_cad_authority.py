"""Fault-injected guards for native numerical and enclosure-only authority."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from itertools import product
import json

import numpy as np
import pytest

import oma.ifc.cad as cad
from oma.ifc.export import export_route
from oma.routing.checker import check_physical_ports
from test_ifc_cad import box
from test_ifc_enclosure import fixture
from test_ifc_pipeline import make_fixture


def face(tmp_path):
    source = tmp_path / "source-face.ifc"
    fixture(source)
    objects, errors = cad.load_cad(source)
    assert not errors and len(objects) == 1
    assert objects[0].support_kind == "exact_source_support_enclosure"
    return objects[0]


@pytest.mark.parametrize("angle", [0., .37, -1.24])
def test_exact_enclosure_transform_has_no_native_authority_and_outward_bounds(tmp_path, monkeypatch, angle):
    original = face(tmp_path)
    matrix = np.eye(4)
    matrix[:3, :3] = [[np.cos(angle), -np.sin(angle), 0.], [np.sin(angle), np.cos(angle), 0.], [0., 0., 1.]]
    if angle:
        matrix[:3, 3] = [100.125, -217.3, .123]
    def forbidden(*args, **kwargs):
        pytest.fail("No native transformation/inspection is allowed for exact enclosure-only support")
    monkeypatch.setattr(cad, "_inspect_shape", forbidden)
    import OCP.BRepBuilderAPI
    monkeypatch.setattr(OCP.BRepBuilderAPI, "BRepBuilderAPI_Transform", forbidden)
    moved = cad._transform_object(original, matrix)
    assert moved.shape is None and moved.volume_m3 is None and not moved.valid
    assert moved.reason == original.reason
    assert moved.support_evidence["native_geometry_authority"] == "NONE_ENCLOSURE_ONLY"
    raw = original.support_evidence["exact_source_enclosure"]["bounds_m"]
    exact = moved.support_evidence["federation_enclosure_transform"]["bounds_m"]
    lo, hi = [[Fraction(x) for x in row] for row in exact]
    for vertex in product(*[(Fraction(raw[0][i]), Fraction(raw[1][i])) for i in range(3)]):
        for axis in range(3):
            value = Fraction.from_float(float(matrix[axis, 3])) + sum(Fraction.from_float(float(matrix[axis, i])) * vertex[i] for i in range(3))
            assert lo[axis] <= value <= hi[axis]
            assert Fraction.from_float(float(moved.bounds[axis])) <= value <= Fraction.from_float(float(moved.bounds[axis + 3]))


def test_enclosure_only_overlap_stays_blocked_and_forged_validity_cannot_pass(tmp_path):
    original = face(tmp_path)
    moved = cad._transform_object(original, np.eye(4))
    remote = box("remote", origin=(10., 10., 10.))
    through = box("through", origin=(1.5, 2.5, 2.9), size=(.1, .1, .2))
    assert cad.check_pair(remote, moved)["status"] == "PASS"
    near = cad.check_pair(through, moved)
    assert near["status"] == "BLOCKED" and near["common_volume_m3"] is None
    forged = replace(moved, valid=True)
    assert cad.check_pair(remote, forged)["status"] == "UNKNOWN"
    assert cad._authorize_joint_contact(remote, forged, {}, 1e-6) == (False, "JOINT_REQUIRES_VALID_NATIVE_SOLIDS")
    with pytest.raises(ValueError, match="cannot acquire native validity"):
        cad._transform_object(forged, np.eye(4))
    pairs, metrics = cad._candidate_obstacle_pairs([remote], [forged], 0., 1e-6, "cpu", None)
    assert pairs == {0: [0]} and metrics["cpu_certified_omitted_pairs"] == 0


@pytest.mark.parametrize("fault", ["source_sha256", "product_step_id", "frame", "status", "bounds_m"])
def test_enclosure_transform_rejects_forged_certificate_identity(tmp_path, fault):
    original = face(tmp_path)
    support = deepcopy(original.support_evidence)
    support["exact_source_enclosure"][fault] = [["5", "5", "5"], ["1", "1", "1"]] if fault == "bounds_m" else "forged"
    with pytest.raises(ValueError):
        cad._transform_object(replace(original, support_evidence=support), np.eye(4))


@pytest.mark.parametrize("fault", ["nonfinite", "nonrigid", "homogeneous"])
def test_transform_rejects_invalid_affine_matrix(tmp_path, fault):
    original = face(tmp_path)
    matrix = np.eye(4)
    if fault == "nonfinite":
        matrix[0, 3] = np.nan
    elif fault == "nonrigid":
        matrix[0, 0] = 1.000001
    else:
        matrix[3, 0] = 1e-13
    with pytest.raises(ValueError, match="must be rigid"):
        cad._transform_object(original, matrix)


def install_distance_fault(monkeypatch, value, witness=(0., 0., 0.)):
    import OCP.BRepExtrema
    class Point:
        def X(self): return witness[0]
        def Y(self): return witness[1]
        def Z(self): return witness[2]
    class Distance:
        def __init__(self, *args): pass
        def Perform(self): pass
        def IsDone(self): return True
        def NbSolution(self): return 1
        def Value(self): return value
        def PointOnShape1(self, index): return Point()
        def PointOnShape2(self, index): return Point()
    monkeypatch.setattr(OCP.BRepExtrema, "BRepExtrema_DistShapeShape", Distance)


@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf, -1.])
def test_nonfinite_or_negative_native_distance_cannot_pass(monkeypatch, value):
    first, second = box("a"), box("b", origin=(2., 0., 0.))
    # A larger conservative box forces actual narrowphase on separated solids.
    first.bounds = (-1., -1., -1., 4., 4., 4.)
    install_distance_fault(monkeypatch, value)
    result = cad.check_pair(first, second)
    assert result["status"] == "UNKNOWN" and result["reason"] == "INVALID_NATIVE_DISTANCE"
    assert result["distance_m"] is None
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf])
def test_nonfinite_native_distance_witness_cannot_pass(monkeypatch, value):
    first, second = box("a"), box("b", origin=(2., 0., 0.))
    first.bounds = (-1., -1., -1., 4., 4., 4.)
    install_distance_fault(monkeypatch, 1., (value, 0., 0.))
    result = cad.check_pair(first, second)
    assert result["status"] == "UNKNOWN" and result["reason"] == "NONFINITE_NATIVE_DISTANCE_WITNESS"
    assert "witness" not in result
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("value", [np.nan, np.inf, -1., None])
@pytest.mark.parametrize("participant", [0, 1])
def test_invalid_kernel_tolerance_cannot_be_broadphase_omitted(value, participant):
    first, second = box("a"), box("b", origin=(100., 0., 0.))
    (first, second)[participant].kernel_tolerance_m = value
    checked = cad.check_pair(first, second)
    assert checked["status"] == "UNKNOWN" and checked["reason"] == "INVALID_NATIVE_NUMERICAL_TOLERANCE"
    assert checked["numerical_budget_m"] is None
    pairs, metrics = cad._candidate_obstacle_pairs([first], [second], 0., 1e-6, "cpu", None)
    assert pairs == {0: [0]} and metrics["cpu_certified_omitted_pairs"] == 0


def test_invalid_native_bounds_cannot_establish_separation():
    first, second = box("a"), box("b", origin=(100., 0., 0.))
    first.bounds = (np.inf,) * 6
    assert cad.check_pair(first, second)["reason"] == "INVALID_FINITE_SUPPORT_BOUNDS"


def test_native_ports_never_classify_an_enclosure_or_missing_shape(tmp_path, monkeypatch):
    import OCP.BRepClass3d
    source = make_fixture(tmp_path / "source.ifc")
    output = tmp_path / "route.ifc"
    manifest = export_route(source, output, {"route_id": "ports", "system_type": "PRESSURE_PIPE",
        "points_m": [[0., 4., 3.], [4., 4., 3.]], "diameter_m": .1})
    objects, errors = cad.load_cad(output, guids={p["ifc_guid"] for p in manifest["added_parts"]})
    assert not errors
    for obj in objects:
        obj.shape = None
        obj.support_kind = "exact_source_support_enclosure"
        obj.valid = True
    def forbidden(*args):
        pytest.fail("Enclosure-only shape must never reach a native solid classifier")
    monkeypatch.setattr(OCP.BRepClass3d, "BRepClass3d_SolidClassifier", forbidden)
    findings = check_physical_ports(output, objects)
    assert len(findings) == 2 and all(item["status"] == "FAIL" for item in findings)


def test_native_cache_explicitly_records_local_conversion_trust(tmp_path):
    source = make_fixture(tmp_path / "source.ifc")
    cache = tmp_path / "cache"
    for expected in ("MISS", "HIT_REVALIDATED"):
        report = {}
        cad.load_cad(source, cache_directory=cache, cache_report=report)
        assert report["status"] == expected and report["cache_trust"] == cad.CACHE_TRUST
    manifest = json.loads(next((cache / "entries").glob("*/manifest.json")).read_text(encoding="utf-8"))
    assert manifest["cache_trust"] == cad.CACHE_TRUST
    assert "not proved" in manifest["cache_trust"]["hostile_replacement"]


def test_one_unavailable_route_cannot_get_empty_self_pair_pass(tmp_path, monkeypatch):
    source = make_fixture(tmp_path / "source.ifc")
    output = tmp_path / "route.ifc"
    manifest = export_route(source, output, {"route_id": "missing-solid", "system_type": "PRESSURE_PIPE",
        "points_m": [[0., 4., 3.], [4., 4., 3.]], "diameter_m": .1})
    original_loader = cad.load_cad
    def faulty_loader(path, **kwargs):
        objects, errors = original_loader(path, **kwargs)
        if kwargs.get("guids"):
            objects = [replace(obj, shape=None, valid=True) for obj in objects]
        return objects, errors
    monkeypatch.setattr(cad, "load_cad", faulty_loader)
    result = cad.cad_check_routes([source], output, [p["ifc_guid"] for p in manifest["added_parts"]])
    assert result["status"] == result["self_interference_status"] == "BLOCKED"
    assert result["self_pair_results"] == []


def test_network_native_volume_and_cap_checks_reject_unavailable_shape(tmp_path, monkeypatch):
    import OCP.BRepClass3d
    from oma.ifc.network import export_network, check_network_semantics
    from test_ifc_network import example
    source = make_fixture(tmp_path / "source.ifc")
    output = tmp_path / "network.ifc"
    manifest = export_network(source, output, example())
    objects, errors = cad.load_cad(output, guids={p["ifc_guid"] for p in manifest["added_parts"]})
    def faulty_loader(path, **kwargs):
        return [replace(obj, shape=None, valid=True) for obj in objects], errors
    def forbidden(*args):
        pytest.fail("Unavailable shape must not reach native topology or cap classification")
    monkeypatch.setattr(cad, "load_cad", faulty_loader)
    monkeypatch.setattr(cad, "_subshapes", forbidden)
    monkeypatch.setattr(OCP.BRepClass3d, "BRepClass3d_SolidClassifier", forbidden)
    result = check_network_semantics(output, source, manifest)
    assert result["status"] == "FAIL"
    assert all(p["status"] == "FAIL" for p in result["ports"])
    assert any("not a completely represented valid native solid" in e for e in result["errors"])
