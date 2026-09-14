from copy import deepcopy

import ifcopenshell
import pytest

from oma.exporting import export_project
from oma.routing.checker import verify_route_candidate
from oma.routing.engine import route_project_run
from oma.routing.scenario import RoutingScenario
from oma.routing.joint_scenario import parse_joint_request
from oma.store import Store
from oma.verification import CHECKER_VERSION
from oma.worker import WorkerControl, import_sources
from test_ifc_openings import host_fixture, opening_request


def scenario():
    return {"start": [0., -1., 1.5], "end": [0., 1., 1.5], "system_type": "PRESSURE_PIPE",
        "diameter_m": .1, "insulation_m": .02, "bend_radius_m": .3, "minimum_straight_m": .05,
        "clearance_m": .1, "allowed_zone": {"min": [-3., -2., -1.], "max": [3., 2., 4.]},
        "scenario_terminals": True, "max_candidates": 1}


def test_route_through_authorized_host_is_checked_accepted_exported_and_reversible(tmp_path):
    path, guid = host_fixture(tmp_path / "source.ifc")
    original_bytes = path.read_bytes()
    store = Store(tmp_path / "store")
    project = store.create_project("Actual opening and route", {})
    imp = store.create_run(project["id"], {"operation": "import", "paths": [str(path)]})
    import_sources(store, imp, WorkerControl(store, imp["id"]))
    baseline_root = store.project(project["id"])["state_root"]
    baseline = store.get(baseline_root)
    raw = scenario()
    blocked = store.create_run(project["id"], {"operation": "route", "mission": raw, "budget_seconds": 90})
    route_project_run(store, blocked, WorkerControl(store, blocked["id"]))
    assert store.candidates(project["id"])[0]["status"] == "REJECTED"

    raw["authorized_opening"] = opening_request(path, guid)
    run = store.create_run(project["id"], {"operation": "route", "mission": raw, "budget_seconds": 90})
    route_project_run(store, run, WorkerControl(store, run["id"]))
    candidates = [c for c in store.candidates(project["id"]) if c["run_id"] == run["id"]]
    assert len(candidates) == 1, store.run(run["id"])
    candidate = candidates[0]
    assert candidate["status"] == "CHECKED", store.get(candidate["report_root"]) if candidate["report_root"] else candidate
    state = store.get(candidate["state_root"])
    report = store.get(candidate["report_root"])
    host_id = state["derived_artifacts"]["opening_edit"]["host_entity_id"]
    assert state["entities"] == baseline["entities"]
    assert state["mission"]["editable_ids"] == [host_id]
    assert host_id not in state["mission"]["protected_ids"] and host_id in candidate["changed_ids"]
    physical = next(r for r in report["results"] if r["id"] == "physical-interference-and-clearance")
    cad = store.get(physical["witness"]["artifact"])
    assert cad["obstacle_count"] == cad["pairs_accounted"] == 1
    assert len(cad["effective_host_edits"]) == 1
    assert cad["effective_host_edits"][0]["host_guid"] == guid
    assert report["objective"]["length_m"] == pytest.approx(2.)
    accepted = store.accept(project["id"], candidate["id"], 1, "accept-opening", checker_version=CHECKER_VERSION)
    assert accepted["revision"] == 2
    exported = export_project(store, project["id"], candidate["id"], draft=False)
    assert exported["status"] == "CHECKED_LOCAL_SCOPE" and exported["round_trip"] == "PASS"
    assert len(exported["files"]) == 1 and exported["files"][0]["changed"]
    assert path.read_bytes() == original_bytes
    assert store.get(baseline_root) == baseline

    for fault in ("permission", "lineage", "missing_host_change", "manifest", "protected_host", "source_frame", "extra_entity", "duplicate_entity", "port_position", "extra_port", "missing_port", "section_shape"):
        mutated = deepcopy(state)
        changed_ids = list(candidate["changed_ids"])
        if fault == "permission":
            mutated["derived_artifacts"]["routing_scenario"]["authorized_opening"]["permission"]["statement"] = "Different unauthorized permission."
        elif fault == "lineage":
            mutated["derived_artifacts"]["opening_edit"]["base_root"] = "b" * 64
        elif fault == "missing_host_change":
            changed_ids.remove(host_id)
        elif fault == "manifest":
            mutated["derived_artifacts"]["opening_edit"]["manifest_root"] = "b" * 64
        elif fault == "protected_host":
            mutated["mission"]["editable_ids"] = []
            mutated["mission"]["protected_ids"].append(host_id)
        elif fault == "source_frame":
            materialized = store.get(mutated["derived_artifacts"]["route_materialization"]["root"])
            materialized["route_spec"]["source_to_federation_matrix"][0][3] += 10
            mutated["derived_artifacts"]["route_materialization"]["root"] = store.put(materialized)
        elif fault in ("extra_entity", "duplicate_entity"):
            entity = deepcopy(mutated["entities"][0])
            if fault == "extra_entity":
                entity["id"] += ":forged"
            mutated["entities"].append(entity)
        elif fault == "port_position":
            mutated["ports"][-1]["position_m"][0] += 10
        elif fault == "extra_port":
            port = deepcopy(mutated["ports"][-1])
            port["id"] += ":forged"
            mutated["ports"].append(port)
        elif fault == "missing_port":
            mutated["ports"].pop()
        elif fault == "section_shape":
            for section in (mutated["mission"]["demands"][0]["section"], mutated["routes"][0]["section"]):
                section.update(shape="rectangular", width_m=.1, height_m=.1)
        forged = store.add_candidate(run["id"], mutated, {"kind": "physical_route", "changed_ids": changed_ids})
        assert verify_route_candidate(store, forged["id"]).status == "FAIL", fault
    store.revert(project["id"], 1, 2, "undo-opening")
    assert store.get(store.project(project["id"])["state_root"]) == baseline


@pytest.mark.parametrize("fault", ["residual_edge", "other_obstacle"])
def test_opening_does_not_omit_its_residual_host_or_any_other_original_obstacle(tmp_path, fault):
    path, guid = host_fixture(tmp_path / "source.ifc")
    if fault == "other_obstacle":
        model = ifcopenshell.open(str(path))
        host = model.by_guid(guid)
        location = model.create_entity("IfcCartesianPoint", Coordinates=[0., .7, 0.])
        placement = model.create_entity("IfcLocalPlacement", RelativePlacement=model.create_entity("IfcAxis2Placement3D", Location=location))
        model.create_entity("IfcWall", GlobalId=ifcopenshell.guid.new(), ObjectPlacement=placement, Representation=host.Representation)
        model.write(str(path))
    store = Store(tmp_path / "store")
    project = store.create_project("Complete edited obstacle inventory", {})
    imp = store.create_run(project["id"], {"operation": "import", "paths": [str(path)]})
    import_sources(store, imp, WorkerControl(store, imp["id"]))
    raw = scenario()
    raw["authorized_opening"] = opening_request(path, guid)
    if fault == "residual_edge":
        raw["start"][0] = raw["end"][0] = .48
    run = store.create_run(project["id"], {"operation": "route", "mission": raw, "budget_seconds": 90})
    route_project_run(store, run, WorkerControl(store, run["id"]))
    candidate = store.candidates(project["id"])[0]
    assert candidate["status"] == "REJECTED"
    report = store.get(candidate["report_root"])
    assert next(r for r in report["results"] if r["id"] == "authorized-host-subtraction")["status"] == "PASS"
    physical = next(r for r in report["results"] if r["id"] == "physical-interference-and-clearance")
    assert physical["status"] == "FAIL"
    cad = store.get(physical["witness"]["artifact"])
    assert cad["obstacle_count"] == cad["pairs_accounted"] == (2 if fault == "other_obstacle" else 1)
    assert len(cad["effective_host_edits"]) == 1
    assert cad["failed_pairs"] >= 1


def test_historical_route_serialization_omits_absent_opening_and_joint_rejects_it(tmp_path):
    raw = scenario()
    assert "authorized_opening" not in RoutingScenario.model_validate(raw).model_dump(mode="json")
    path, guid = host_fixture(tmp_path / "source.ifc")
    raw["authorized_opening"] = opening_request(path, guid)
    with pytest.raises(ValueError, match="single-route"):
        parse_joint_request(raw)
    raw["target_modality"] = "ENGINEERING_SERVICE"
    with pytest.raises(ValueError, match="geometric coordination only"):
        RoutingScenario.model_validate(raw)
