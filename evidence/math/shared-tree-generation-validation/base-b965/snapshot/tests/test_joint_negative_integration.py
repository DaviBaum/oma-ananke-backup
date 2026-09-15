"""Real materialization/search checks for same-menu fresh pair scheduling."""
from copy import deepcopy

import pytest

from oma.routing.engine import route_project_run
from oma.routing.joint_checker import verify_joint_candidate
from oma.routing.joint_negative_probe import _route_keys
from oma.store import Store
from oma.worker import WorkerControl, import_sources
from test_ifc_pipeline import make_fixture


@pytest.fixture(scope="module")
def repeated_conflict_campaign(tmp_path_factory):
    directory = tmp_path_factory.mktemp("joint-repeated-native-conflict")
    source = make_fixture(directory / "source.ifc")
    store = Store(directory / "store")
    project = store.create_project("Three-demand repeated native pair conflict", {})
    imported = store.create_run(project["id"], {"operation": "import", "paths": [str(source)]})
    import_sources(store, imported, WorkerControl(store, imported["id"]))
    first = {"start": [-1., 4., 1.], "end": [3., 4., 1.], "system_type": "PRESSURE_PIPE",
        "diameter_m": .1, "insulation_m": .02, "bend_radius_m": .3, "minimum_straight_m": .05,
        "clearance_m": .1, "allowed_zone": {"min": [-2., -2., -2.], "max": [6., 7., 6.]},
        "scenario_terminals": True, "max_candidates": 1}
    crossing = {**first, "start": [1., 3., 1.], "end": [1., 5., 1.]}
    separated = {**crossing, "start": [1., 3., 2.], "end": [1., 5., 2.]}
    other = {**first, "start": [-1., 5.5, 3.], "end": [3., 5.5, 3.]}
    other_moved = {**other, "start": [-1., 5.5, 4.], "end": [3., 5.5, 4.]}
    mission = {"route_demands": [{"id": "first", "alternatives": [first]},
        {"id": "second", "alternatives": [crossing, separated]},
        {"id": "third", "alternatives": [other, other_moved]}],
        "max_joint_candidates": 4, "max_paths_per_alternative": 1}
    run = store.create_run(project["id"], {"operation": "optimize", "mission": mission, "budget_seconds": 120})
    route_project_run(store, run, WorkerControl(store, run["id"]))
    candidates = [c for c in store.candidates(project["id"]) if c["run_id"] == run["id"]]
    return store, run, candidates


def test_three_demands_recheck_remapped_conflict_then_check_moved_choice_completely(repeated_conflict_campaign):
    store, run, candidates = repeated_conflict_campaign
    assert len(candidates) == 4
    assert [c["status"] for c in candidates] == ["REJECTED", "REJECTED", "CHECKED", "CHECKED"]
    first, second, third, fourth = candidates
    assert first["physical_menu_assignment"] == ["0:0", "0:0", "0:0"]
    assert second["physical_menu_assignment"] == ["0:0", "0:0", "1:0"]
    reports = [store.get(c["report_root"]) for c in candidates]
    full = next(r for r in reports[0]["results"] if r["id"] == "cross-route-interference")
    assert full["status"] == "FAIL" and full["witness"]["pairs_accounted"] == 3
    repeated = {r["id"]: r for r in reports[1]["results"]}
    counterexample = repeated["native-cross-route-counterexample"]
    artifact = store.get(counterexample["witness"]["artifact"])
    assert artifact["status"] == "FAIL" and artifact["probe_count"] == 1
    assert artifact["supervision"]["status"] == "COMPLETED"
    assert artifact["old_verdict_reused"] is False and artifact["new_native_verification_performed"] is True
    assert artifact["acceptance_authority"] == artifact["objective_authority"] == "NONE"
    assert artifact["full_source_denominator"] == artifact["full_cross_route_denominator"] == "NOT_RUN"
    assert reports[1]["objective"] == {}
    assert repeated["joint-objective"]["status"] == repeated["cross-route-interference"]["status"] == "NOT_RUN"
    state = store.get(second["state_root"])
    for route in state["routes"]:
        assert repeated[route["id"] + ":exported-physical-semantics"]["status"] == "PASS"
        assert repeated[route["id"] + ":physical-interference-and-clearance"]["status"] == "NOT_RUN"
    old_guids = set(full["witness"]["findings"][0]["participant_guids"])
    fresh_guids = set(artifact["witness"]["native_pair_result"]["participant_guids"])
    assert old_guids.isdisjoint(fresh_guids), "Each assignment must reload its newly materialized GUIDs"
    for report in reports[2:]:
        checks = {r["id"]: r for r in report["results"]}
        assert "native-cross-route-counterexample" not in checks
        assert checks["cross-route-interference"]["status"] == "PASS"
        assert checks["cross-route-interference"]["witness"]["pairs_accounted"] == 3
        assert report["objective"] == {"length_m": 10., "fitting_count": 0.}
    assert store.run(run["id"])["status"] == "COMPLETED"
    final = next(e for e in reversed(store.events(run["project_id"], limit=1000)) if e["stage"] == "complete")
    assert final["payload"]["selected_candidate_ids"][0] in {third["id"], fourth["id"]}
    assert final["payload"]["global_lower_bound"] is None


def test_fabricated_old_failure_against_current_separated_parts_falls_through(repeated_conflict_campaign):
    store, run, candidates = repeated_conflict_campaign
    source = candidates[2]
    state = store.get(source["state_root"])
    keys = _route_keys(store, source, state)
    members = [{"route": keys[r["id"]], "part_index": 0, "part_kind": "segment"} for r in state["routes"][:2]]
    hints = [{"frozen_menu_root": source["physical_menu_root"], "origin_candidate_id": "invented",
        "origin_report_root": "f" * 64, "members": members, "status": "FAIL", "common_volume_m3": 1000.,
        "required_clearance_m": 1_000_000., "authority": "CLAIMED_BUT_UNTRUSTED"}]
    candidate = store.add_candidate(run["id"], deepcopy(state), {"kind": "physical_route_set", "changed_ids": source["changed_ids"],
        "physical_menu_root": source["physical_menu_root"], "physical_menu_assignment": source["physical_menu_assignment"],
        "joint_pair_hints": hints})
    report = verify_joint_candidate(store, candidate["id"])
    assert report.status == "PASS", report.model_dump(mode="json")
    checks = {r.id: r for r in report.results}
    assert "native-cross-route-counterexample" not in checks
    witness = checks["cross-route-interference"].witness
    assert witness["pairs_accounted"] == 3 and witness["complete_component_coverage"] is True
    probe = store.get(witness["negative_probe_artifact"])
    assert probe["status"] == "NO_COUNTEREXAMPLE_FOUND" and probe["probe_count"] == 1
    pair = probe["probes"][0]["native_pair_result"]
    assert pair["status"] == "PASS" and pair["required_clearance_m"] == .1
    assert report.objective == {"length_m": 10., "fitting_count": 0.}
