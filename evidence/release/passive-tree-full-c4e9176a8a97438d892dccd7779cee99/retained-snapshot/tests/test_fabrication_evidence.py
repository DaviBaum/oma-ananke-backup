from copy import deepcopy

import pytest

from oma.routing.fabrication_evidence import persist_fabrication_proposal, replay_fabrication_proposal
from oma.routing.scenario import RoutingScenario
from oma.store import Store


def prepared(tmp_path, points, minimum=.1):
    store = Store(tmp_path / "store")
    project = store.create_project("Fabrication evidence", {})
    scenario = RoutingScenario(start=points[0], end=points[-1], system_type="PRESSURE_PIPE",
        diameter_m=.1, insulation_m=.02, bend_radius_m=.5, minimum_straight_m=minimum,
        clearance_m=.1, allowed_zone={"min":[-5.,-5.,-5.],"max":[5.,5.,5.]}, scenario_terminals=True)
    run = store.create_run(project["id"], {"operation":"route", "mission":scenario.model_dump(mode="json")})
    proposal = persist_fabrication_proposal(store,run,scenario,{"points_m":points},checkpoint=lambda stage:None)
    return store,project,run,scenario,proposal["fabrication_evidence"]


@pytest.mark.parametrize("points,minimum,outcome", [
    ([[0.,0.,0.],[2.,0.,0.],[2.,2.,0.]],.1,"PASS"),
    ([[0.,0.,0.],[.75,0.,0.],[.75,.75,0.]],.25,"FAIL"),
    ([[0.,0.,0.],[1.,1.,0.]],.1,"UNKNOWN"),
])
def test_current_replay_preserves_model_disposition_without_route_authority(tmp_path,points,minimum,outcome):
    store,project,run,scenario,reference = prepared(tmp_path,points,minimum)
    checked = replay_fabrication_proposal(store,reference,scenario,points,project_id=project["id"])
    assert checked["status"] == "PASS" and checked["fabrication_status"] == outcome
    assert not checked["producer_check_reused"] and not checked["candidate_acceptance_authority"]
    assert next(e for e in store.events(project["id"]) if e["stage"] == "fabrication_model")["status"] == outcome
    # The same nominal inputs remain replayable after an unrelated revision;
    # this does not transfer any obstacle or native-geometry result.
    store.publish(project["id"], {"project_id":project["id"],"revision_note":"new source context"},0,"revision")
    assert replay_fabrication_proposal(store,reference,scenario,points,project_id=project["id"])["status"] == "PASS"


@pytest.mark.parametrize("fault", ["path","origin","scope","disposition","producer_check","component"])
def test_fabrication_reference_cannot_forge_inputs_origin_scope_or_proof(tmp_path,fault):
    points = [[0.,0.,0.],[2.,0.,0.],[2.,2.,0.]]
    store,project,run,scenario,reference = prepared(tmp_path,points)
    reference = deepcopy(reference)
    artifact = store.get(reference["artifact_root"])
    if fault == "path": points[1] = [3.,0.,0.]
    elif fault == "origin": artifact["context"]["request_root"] = "a"*64
    elif fault == "scope": reference["candidate_acceptance_authority"] = True
    elif fault == "disposition": reference["fabrication_status"] = "UNKNOWN"
    elif fault == "producer_check": artifact["producer_check"]["components_checked"] += 1
    elif fault == "component": artifact["certificate"]["components"][0]["length_m"] = "999"
    reference["artifact_root"] = store.put(artifact)
    assert replay_fabrication_proposal(store,reference,scenario,points,project_id=project["id"])["status"] == "FAIL"
