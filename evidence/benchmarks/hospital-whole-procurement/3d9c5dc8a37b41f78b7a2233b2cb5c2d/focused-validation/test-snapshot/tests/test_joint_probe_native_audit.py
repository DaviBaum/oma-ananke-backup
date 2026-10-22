"""Independent native-byte audit: parsed geometry must belong to declared bytes."""
from copy import deepcopy
from pathlib import Path
import uuid

import ifcopenshell
import pytest

from oma.ifc.audit import atomic_json, sha256_file
from oma.routing.joint_negative_probe import _run_request
from test_joint_negative_hint_adversarial import _native_candidate, _request, _add_hinted_candidate


def test_transient_export_replacement_cannot_bind_other_geometry_to_current_hash(tmp_path, monkeypatch):
    """Real file replacement during open must not certify the other parsed model.

    Current A contains separated tubes. B moves only the second native tube
    onto the first. The file is restored to A immediately after the native
    parser reads B, before either hash guard can inspect the path again.
    """
    case = _native_candidate(tmp_path / "case", crossing=False)
    store = case["store"]
    path = store.resolve_path(case["materialized"]["audit-first"]["export_path"])
    original = path.read_bytes()
    expected_sha = sha256_file(path)
    opening = ifcopenshell.open
    altered = opening(str(path))
    second = altered.by_guid(case["materialized"]["audit-second"]["added_parts"][0]["ifc_guid"])
    position = second.ObjectPlacement.RelativePlacement.Location
    before = list(position.Coordinates)
    position.Coordinates = [before[0], before[1] - .25, before[2]]
    attack_path = tmp_path / "overlapping-only-during-parse.ifc"
    altered.write(str(attack_path))
    attack = attack_path.read_bytes()
    assert attack != original
    request = _request(case)
    clean = _run_request(store, deepcopy(request))
    assert clean["status"] == "NO_COUNTEREXAMPLE_FOUND"
    assert clean["probes"][0]["native_pair_result"]["status"] == "PASS"
    opened_other = []

    def transient(filename, *args, **kwargs):
        if Path(filename).resolve() != path.resolve():
            return opening(filename, *args, **kwargs)
        assert path.read_bytes() == original
        path.write_bytes(attack)
        try:
            model = opening(filename, *args, **kwargs)
            opened_other.append(sha256_file(path))
            return model
        finally:
            path.write_bytes(original)

    monkeypatch.setattr(ifcopenshell, "open", transient)
    observed = _run_request(store, deepcopy(request))
    assert path.read_bytes() == original and sha256_file(path) == expected_sha
    evidence = Path("evidence/release/joint-probe-native-audit") / uuid.uuid4().hex
    evidence.mkdir(parents=True)
    (evidence / "current-separated.ifc").write_bytes(original)
    (evidence / "transient-overlap.ifc").write_bytes(attack)
    atomic_json(evidence / "result.json", {
        "experiment": "Actual native file parse sees B while before/after declared-byte guards see A",
        "current_export_sha256": expected_sha, "transient_parse_sha256s": opened_other,
        "final_export_sha256": sha256_file(path), "current_native_result": clean,
        "transient_native_result": observed,
        "wrong_current_geometry_failure": observed["status"] == "FAIL",
        "kernel_pair_result_not_mocked": True,
    })
    # A safe implementation may parse an already hash-verified immutable byte
    # buffer, in which case the path-based parser hook is never reached.
    assert observed["status"] != "FAIL", {
        "evidence": str(evidence), "parsed_other_bytes": opened_other,
        "current_file_sha256": expected_sha, "observed": observed,
    }


@pytest.mark.parametrize("foreign", ["original_building_object", "other_route_object"])
def test_current_part_manifest_cannot_redirect_the_early_probe_to_an_unrelated_body(tmp_path, monkeypatch, foreign):
    """Current hash-consistent manifests still need the full ownership preflight."""
    import oma.routing.joint_negative_probe as probe
    from oma.routing.joint_checker import verify_joint_candidate

    case = _native_candidate(tmp_path / foreign, crossing=False)
    state = deepcopy(case["state"])
    first, second = state["routes"]
    material = case["store"].get(first["geometry_artifact"])
    if foreign == "original_building_object":
        original = ifcopenshell.open(str(case["store"].resolve_path(state["sources"][0]["immutable_path"])))
        target = original.by_type("IfcBuildingElementProxy")[0]
        guid, step_id = target.GlobalId, target.id()
    else:
        target = case["store"].get(second["geometry_artifact"])["added_parts"][0]
        guid, step_id = target["ifc_guid"], target["step_id"]
    material["added_parts"][0].update(ifc_guid=guid, step_id=step_id)
    first["geometry_artifact"] = case["store"].put(material)
    candidate = _add_hinted_candidate(case, state)

    def forbidden(*args, **kwargs):
        raise AssertionError("An unrelated body cannot reach the early native pair probe")

    monkeypatch.setattr(probe, "probe_joint_failure", forbidden)
    report = verify_joint_candidate(case["store"], candidate["id"])
    assert report.status == "FAIL"
    assert not any(result.id == "native-cross-route-counterexample" for result in report.results)
    assert any(result.status == "FAIL" and (result.id == "physical-part-ownership" or result.id.endswith(":exported-physical-semantics"))
               for result in report.results)
