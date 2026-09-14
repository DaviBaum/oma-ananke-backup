"""Adversarial attribution and preservation of exact nominal proof references.

These tests do not turn optional exact-model proofs into native acceptance
authority. They require claimed producer origin and retained evidence to be true.
"""
import pytest

from oma.optimization.fabrication import compile_orthogonal_fabrication, verify_orthogonal_fabrication
from oma.routing.fabrication_evidence import persist_fabrication_proposal, replay_fabrication_proposal
from oma.routing.scenario import RoutingScenario
from oma.store import digest
from test_fabrication_evidence import prepared


def _coherent_reference(store, reference, scenario, points, changes):
    artifact = store.get(reference["artifact_root"])
    artifact["context"].update(changes)
    context_root = digest(artifact["context"])
    certificate = compile_orthogonal_fabrication(scenario, points, context_root=context_root)
    replay = verify_orthogonal_fabrication(scenario, points, certificate, context_root=context_root)
    assert replay["status"] == "PASS"
    artifact.update(certificate=certificate, producer_check=replay)
    return {**reference, "artifact_root": store.put(artifact), "certificate_root": replay["certificate_root"],
        "fabrication_status": replay["fabrication_status"]}


@pytest.mark.parametrize("fault", ["producer_version", "unrelated_origin", "nonrouting_origin"])
def test_coherent_math_cannot_forge_its_actual_publication_origin(tmp_path, fault):
    points = [[0., 0., 0.], [2., 0., 0.], [2., 2., 0.]]
    store, project, run, scenario, reference = prepared(tmp_path, points)
    changes = {"producer_version": "invented-build-that-never-produced-this-proof"}
    if fault != "producer_version":
        unrelated = store.create_run(project["id"], {**run["request"],
            "operation": "check" if fault == "nonrouting_origin" else "route"})
        changes = {"run_id": unrelated["id"], "base_root": unrelated["base_root"],
            "request_root": digest(unrelated["request"])}
    forged = _coherent_reference(store, reference, scenario, points, changes)
    # Mathematics and all internal hashes agree. No origin publication event
    # ever recorded this artifact under its newly claimed run/build context.
    assert not any(forged["artifact_root"] in e.get("artifacts", []) for e in store.events(project["id"]))
    checked = replay_fabrication_proposal(store, forged, scenario, points, project_id=project["id"])
    assert checked["status"] == "FAIL", checked


def test_origin_publication_and_missing_reference_detection_exceed_ui_event_window(tmp_path):
    from oma.routing.fabrication_evidence import check_route_fabrication_evidence
    points = [[0., 0., 0.], [2., 0., 0.], [2., 2., 0.]]
    store, project, _, scenario, _ = prepared(tmp_path, points)
    origin = store.create_run(project["id"], {"operation": "route", "mission": scenario.model_dump(mode="json")})
    for index in range(1001):
        store.append_event(project["id"], run_id=origin["id"], state_root=origin["base_root"],
            stage="search", status="RUNNING", message=f"Unrelated progress {index}")
    reference = persist_fabrication_proposal(store, origin, scenario, {"points_m": points},
        checkpoint=lambda stage: None)["fabrication_evidence"]
    assert not any(reference["artifact_root"] in e.get("artifacts", []) for e in store.events(project["id"], limit=1000))
    route = {"id": "route", "points_m": points}
    state = {"project_id": project["id"], "routes": [route], "derived_artifacts": {"fabrication_evidence_by_route": {"route": reference}}}
    assert replay_fabrication_proposal(store, reference, scenario, points, project_id=project["id"])["status"] == "PASS"
    assert check_route_fabrication_evidence(store, state, {}, scenario, route, origin)["status"] == "PASS"
    state["derived_artifacts"]["fabrication_evidence_by_route"] = {}
    assert check_route_fabrication_evidence(store, state, {}, scenario, route, origin)["status"] == "FAIL"


@pytest.mark.parametrize("points,minimum,disposition", [
    ([[0., 0., 0.], [.75, 0., 0.], [.75, .75, 0.]], .25, "FAIL"),
    ([[0., 0., 0.], [1., 1., 0.]], .1, "UNKNOWN"),
])
def test_route_binding_pass_does_not_upgrade_nominal_failure_or_unknown(tmp_path, points, minimum, disposition):
    from oma.routing.fabrication_evidence import check_route_fabrication_evidence
    store, project, run, scenario, reference = prepared(tmp_path, points, minimum)
    route = {"id": "route", "points_m": points}
    state = {"project_id": project["id"], "routes": [route], "derived_artifacts": {"fabrication_evidence_by_route": {"route": reference}}}
    checked = check_route_fabrication_evidence(store, state, {}, scenario, route, run)
    assert checked["status"] == "PASS" and checked["fabrication_status"] == disposition
    assert checked["disposition"]["status"] == disposition
    assert not checked["candidate_acceptance_authority"]
    assert not checked["limitations"]["automatic_numerical_writer_pruning_authority"]


def test_equal_scenarios_in_one_joint_run_still_have_distinct_demand_attribution(tmp_path):
    from oma.routing.fabrication_evidence import check_route_fabrication_evidence
    points = [[0., 0., 0.], [2., 0., 0.], [2., 2., 0.]]
    store, project, _, scenario, _ = prepared(tmp_path, points)
    raw = scenario.model_dump(mode="json")
    origin = store.create_run(project["id"], {"operation": "route", "mission": {"route_demands": [
        {"id": "first", "alternatives": [raw]}, {"id": "second", "alternatives": [raw]}]}})
    reference = persist_fabrication_proposal(store, origin, scenario, {"points_m": points},
        checkpoint=lambda stage: None, request_demand_id="second")["fabrication_evidence"]
    assert replay_fabrication_proposal(store, reference, scenario, points, project_id=project["id"])["status"] == "PASS"
    route = {"id": "route-first", "points_m": points}
    state = {"project_id": project["id"], "routes": [route], "derived_artifacts": {
        "routing_contracts": {"route-first": {"request_demand_id": "first"}},
        "fabrication_evidence_by_route": {"route-first": reference}}}
    checked = check_route_fabrication_evidence(store, state, {}, scenario, route, origin)
    assert checked["status"] == "FAIL", checked


@pytest.fixture(scope="module")
def native_candidates(tmp_path_factory):
    from oma.build_identity import checker_version
    from oma.routing.engine import route_project_run
    from oma.store import Store
    from oma.worker import WorkerControl, import_sources
    from test_ifc_pipeline import make_fixture

    directory = tmp_path_factory.mktemp("fabrication-origin-native")
    source = make_fixture(directory / "source.ifc")
    store = Store(directory / "store")
    project = store.create_project("Fabrication lineage", {})
    imported = store.create_run(project["id"], {"operation": "import", "paths": [str(source)]})
    import_sources(store, imported, WorkerControl(store, imported["id"]))
    scenario = {"start": [-1., -1., 1.], "end": [3., -1., 1.], "system_type": "PRESSURE_PIPE",
        "diameter_m": .1, "insulation_m": .02, "bend_radius_m": .3, "minimum_straight_m": .05,
        "clearance_m": .1, "allowed_zone": {"min": [-2., -2., -2.], "max": [4., 4., 4.]},
        "scenario_terminals": True, "max_candidates": 1}
    first = store.create_run(project["id"], {"operation": "route", "mission": scenario, "budget_seconds": 90})
    route_project_run(store, first, WorkerControl(store, first["id"]))
    original = next(c for c in store.candidates(project["id"]) if c["run_id"] == first["id"])
    assert original["status"] == "CHECKED", store.get(original["report_root"])
    store.accept(project["id"], original["id"], 1, "first-route", checker_version=checker_version())
    extra = {**scenario, "start": [-1., 3., 1.], "end": [3., 3., 1.]}
    second = store.create_run(project["id"], {"operation": "route", "mission": extra, "budget_seconds": 90})
    route_project_run(store, second, WorkerControl(store, second["id"]))
    joint = next(c for c in store.candidates(project["id"]) if c["run_id"] == second["id"])
    assert joint["status"] == "CHECKED", store.get(joint["report_root"])
    return store, project, original, joint


def _check_mutation(store, candidate, state):
    from oma.routing.checker import verify_route_candidate
    from oma.routing.joint_checker import verify_joint_candidate
    changed = store.add_candidate(candidate["run_id"], state, {"kind": candidate["kind"],
        "changed_ids": candidate["changed_ids"], "routes": state["routes"]})
    checker = verify_joint_candidate if candidate["kind"] == "physical_route_set" else verify_route_candidate
    return checker(store, changed["id"])


@pytest.mark.parametrize("which", ["standalone", "new_joint_route", "preserved_joint_route"])
def test_generated_or_preserved_nominal_evidence_cannot_be_stripped(native_candidates, which):
    store, _, original, joint = native_candidates
    candidate = original if which == "standalone" else joint
    state = store.get(candidate["state_root"])
    previous_id = store.get(original["state_root"])["routes"][0]["id"]
    target = joint["changed_ids"][0] if which == "new_joint_route" else previous_id
    assert target in state["derived_artifacts"]["fabrication_evidence_by_route"]
    del state["derived_artifacts"]["fabrication_evidence_by_route"][target]
    checked = _check_mutation(store, candidate, state)
    assert checked.status == "FAIL", checked.model_dump(mode="json")


@pytest.mark.parametrize("which", ["standalone", "new_joint_route", "preserved_joint_route"])
def test_valid_same_project_proof_from_unrelated_run_does_not_replace_route_lineage(native_candidates, which):
    store, project, original, joint = native_candidates
    candidate = original if which == "standalone" else joint
    state = store.get(candidate["state_root"])
    previous_id = store.get(original["state_root"])["routes"][0]["id"]
    target = joint["changed_ids"][0] if which == "new_joint_route" else previous_id
    route = next(r for r in state["routes"] if r["id"] == target)
    raw = (state["derived_artifacts"]["routing_contracts"][target]["scenario"]
        if which != "standalone" else state["derived_artifacts"]["routing_scenario"])
    scenario = RoutingScenario.model_validate(raw)
    unrelated = store.create_run(project["id"], {"operation": "route", "mission": raw})
    reference = persist_fabrication_proposal(store, unrelated, scenario, {"points_m": route["points_m"]},
        checkpoint=lambda stage: None)["fabrication_evidence"]
    # It really is a published, independently valid proof of the same nominal
    # model, but it did not produce this route or its preserved baseline evidence.
    pure = replay_fabrication_proposal(store, reference, scenario, route["points_m"], project_id=project["id"])
    assert pure["status"] == "PASS" and not pure["candidate_acceptance_authority"]
    state["derived_artifacts"]["fabrication_evidence_by_route"][target] = reference
    checked = _check_mutation(store, candidate, state)
    assert checked.status == "FAIL", checked.model_dump(mode="json")
