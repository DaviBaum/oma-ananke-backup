"""A genuine managed native PASS cannot authorize changed physical input bytes."""
from pathlib import Path
import time

import ifcopenshell
import pytest

from oma.ifc.audit import sha256_file
from oma.routing.check_execution import run_candidate_check
from oma.store import IntegrityError
from test_joint_negative_hint_adversarial import _native_candidate


def native_managed_case(directory):
    case = _native_candidate(directory,crossing=False)
    execution = run_candidate_check(case["store"],case["candidate"]["id"],deadline=time.monotonic()+45,reserve_bytes=0)
    assert execution["status"] == "COMPLETED" and execution["report_published"], execution
    assert execution["report_status"] == "PASS"
    case["execution"] = execution
    case["candidate"] = case["store"].candidate(case["candidate"]["id"])
    return case


def change_physical_input(case,target):
    source = case["state"]["sources"][0]
    material = case["materialized"]["audit-first"]
    path = case["store"].resolve_path(source["immutable_path"] if target == "source" else material["export_path"])
    original = path.read_bytes()
    model = ifcopenshell.open(str(path))
    if target == "source":
        # Move the represented source box from y=[0,2] to y=[3,5], crossing
        # both genuinely checked routes at y=4 and y=4.25.
        body = model.by_type("IfcBuildingElementProxy")[0]
        body.ObjectPlacement.RelativePlacement.Location.Coordinates = (0.,3.,0.)
    elif target == "export":
        # Enlarge a real route cylinder enough to overlap the other route.
        product = model.by_guid(material["added_parts"][0]["ifc_guid"])
        solid = product.Representation.Representations[0].Items[0]
        assert solid.is_a("IfcExtrudedAreaSolid")
        solid.SweptArea.Radius *= 10
    else:
        raise ValueError(target)
    model.write(str(path))
    return path,original


def current_native_diagnostic(case):
    from oma.ifc.cad import cad_check_routes
    source = case["store"].resolve_path(case["state"]["sources"][0]["immutable_path"])
    output = case["store"].resolve_path(case["materialized"]["audit-first"]["export_path"])
    guids = {part["ifc_guid"] for material in case["materialized"].values() for part in material["added_parts"]}
    return cad_check_routes([source],output,guids,clearance_m=.1)


@pytest.fixture(scope="module")
def managed(tmp_path_factory):
    return native_managed_case(tmp_path_factory.mktemp("acceptance-physical-inputs"))


@pytest.mark.parametrize("target",["source","export"])
def test_changed_actual_geometry_after_managed_native_pass_cannot_be_accepted(managed,target):
    store,candidate = managed["store"],managed["candidate"]
    project = store.project(candidate["project_id"])
    before_events = store.events(project["id"],limit=1000)
    path,original = change_physical_input(managed,target)
    try:
        current = current_native_diagnostic(managed)
        assert current["status"] == "FAIL", current
        expected = (managed["state"]["sources"][0]["sha256"] if target == "source"
            else managed["materialized"]["audit-first"]["export_sha256"])
        assert sha256_file(path) != expected
        with pytest.raises(IntegrityError,match="[Bb]ytes|[Ii]nput|[Cc]hanged|[Hh]ash"):
            store.accept(project["id"],candidate["id"],project["revision"],"changed-"+target,
                checker_version=managed["execution"]["observed_receipt"]["checker_version"])
        assert store.project(project["id"]) == project
        assert store.events(project["id"],limit=1000) == before_events
        assert store.candidate(candidate["id"])["report_root"] == candidate["report_root"]
    finally:
        path.write_bytes(original)


def test_actual_private_native_pass_is_not_published_after_source_mutates_during_assurance(tmp_path,monkeypatch):
    from oma import project_assurance
    case = _native_candidate(tmp_path/"during-assurance",crossing=False)
    store,candidate = case["store"],case["candidate"]
    build = project_assurance.build_report_assurance
    changed = []
    def mutate_after_actual_assurance(*args,**kwargs):
        evidence = build(*args,**kwargs)
        assert evidence["recorded_engineering_status"] == "PASS"
        changed.append(change_physical_input(case,"source"))
        return evidence
    monkeypatch.setattr(project_assurance,"build_report_assurance",mutate_after_actual_assurance)
    try:
        result = run_candidate_check(store,candidate["id"],deadline=time.monotonic()+45,reserve_bytes=0)
        assert result["supervision"]["status"] == "COMPLETED", result
        assert result["observed_receipt"]["report_status"] == "PASS"
        assert result["status"] == "UNKNOWN_ADMISSION_REJECTED" and not result["report_published"]
        assert "physical input bytes changed" in result["reason"]
        current = store.candidate(candidate["id"])
        assert current["status"] == "UNKNOWN" and current["report_root"] is None
        events = store.events(candidate["project_id"],limit=1000)
        assert not any(e["stage"] == "verification" and e["status"] == "CHECKED" for e in events)
        assert len(changed) == 1
    finally:
        for path,original in changed:
            path.write_bytes(original)


def test_unchanged_actual_native_inputs_are_accepted_with_explicit_byte_evidence(tmp_path):
    case = native_managed_case(tmp_path/"unchanged")
    store,candidate = case["store"],case["candidate"]
    project = store.project(candidate["project_id"])
    accepted = store.accept(project["id"],candidate["id"],project["revision"],"fresh-physical-inputs",
        checker_version=case["execution"]["observed_receipt"]["checker_version"])
    assert accepted["status"] == "ACCEPTED" and accepted["revision"] == project["revision"]+1
    events = store.events(project["id"],limit=1000)
    completion = next(e for e in events if e["stage"] == "check_execution" and e["status"] == "COMPLETED")
    evidence = store.get(completion["payload"]["current_physical_input_root"])
    assert evidence["all_expected_hashes_match"] and evidence["file_count"] == 2
    assert not evidence["native_geometry_rechecked"] and not evidence["arbitrary_filesystem_mutations_locked_out"]
