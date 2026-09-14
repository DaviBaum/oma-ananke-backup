"""Actual checked candidates must remain valid when final selection is published."""
import importlib
from copy import deepcopy

import pytest

from oma.routing.engine import route_project_run
from oma.store import Store
from oma.worker import WorkerControl, import_sources
from test_ifc_pipeline import make_fixture


def imported_case(tmp_path, kind):
    store = Store(tmp_path / "store")
    project = store.create_project("Selection interleaving", {})
    source = make_fixture(tmp_path / "source.ifc")
    imported = store.create_run(project["id"], {"operation": "import", "paths": [str(source)]})
    import_sources(store, imported, WorkerControl(store, imported["id"]))
    route = {"start": [-1., -1., 1.], "end": [3., -1., 1.], "system_type": "PRESSURE_PIPE",
        "diameter_m": .1, "insulation_m": .02, "bend_radius_m": .3, "minimum_straight_m": .05,
        "clearance_m": .1, "allowed_zone": {"min": [-2., -2., -2.], "max": [4., 4., 4.]},
        "scenario_terminals": True, "max_candidates": 1}
    if kind == "joint":
        mission = {"route_demands": [{"id": "one", "alternatives": [route]}], "max_joint_candidates": 1}
    elif kind == "network":
        from test_network_scenario import network_scenario
        mission = network_scenario()
    else:
        mission = route
    run = store.create_run(project["id"], {"operation": "optimize", "mission": mission, "budget_seconds": 90})
    return store, project, run


def final_event(store, project, run):
    return next(e for e in reversed(store.events(project["id"], limit=1000))
        if e.get("run_id") == run["id"] and e["stage"] == "complete")


@pytest.fixture(scope="module")
def genuine_selected_candidate(tmp_path_factory):
    store, project, run = imported_case(tmp_path_factory.mktemp("selection-binding"), "single")
    route_project_run(store, run, WorkerControl(store, run["id"]))
    candidate = store.candidates(project["id"])[0]
    assert candidate["status"] == "CHECKED"
    return store, project, run, candidate


@pytest.mark.parametrize("fault", ["root", "version", "mission", "rules", "scope", "missing_body_check", "duplicate_check", "negative_objective"])
def test_current_checked_flag_cannot_admit_a_misbound_report(genuine_selected_candidate, monkeypatch, fault):
    from oma.routing.selection import try_selection_evidence
    store, _, run, candidate = genuine_selected_candidate
    state = store.get(candidate["state_root"])
    report = store.get(candidate["report_root"])
    if fault == "root": report["candidate_root"] = "a" * 64
    elif fault == "version": report["checker_version"] = "oma-independent-checker/2:" + "a" * 64
    elif fault == "mission": report["mission_hash"] = "a" * 64
    elif fault == "rules": report["rule_hash"] = "a" * 64
    elif fault == "scope": report["scope"] = "Imported baseline only"
    elif fault == "missing_body_check": report["results"] = [r for r in report["results"] if r["id"] != "physical-interference-and-clearance"]
    elif fault == "duplicate_check": report["results"].append(deepcopy(report["results"][0]))
    elif fault == "negative_objective": report["objective"]["length_m"] = -1.
    forged = {**candidate, "report_root": store.put(report)}
    original_lookup = store.candidate
    monkeypatch.setattr(store, "candidate", lambda cid: forged if cid == candidate["id"] else original_lookup(cid))
    row, failure = try_selection_evidence(store, run, candidate["id"], "physical_route", state["mission"]["objective_weights"])
    assert row is None and failure


def test_current_checked_flag_cannot_hide_changed_materialized_bytes(genuine_selected_candidate):
    from oma.routing.selection import try_selection_evidence
    store, _, run, candidate = genuine_selected_candidate
    state = store.get(candidate["state_root"])
    path = store.resolve_path(store.get(state["routes"][0]["geometry_artifact"])["export_path"])
    original = path.read_bytes()
    try:
        path.write_bytes(original + b"\n")
        assert store.candidate(candidate["id"])["status"] == "CHECKED"
        row, failure = try_selection_evidence(store, run, candidate["id"], "physical_route", state["mission"]["objective_weights"])
        assert row is None and "bytes changed" in failure["reason"]
    finally:
        path.write_bytes(original)


@pytest.fixture(scope="module", params=["single", "joint", "network"])
def complete_scope_candidate(tmp_path_factory, request):
    kind = request.param
    store, project, run = imported_case(tmp_path_factory.mktemp("selection-full-scope-" + kind), kind)
    route_project_run(store, run, WorkerControl(store, run["id"]))
    candidate = store.candidates(project["id"])[0]
    assert candidate["status"] == "CHECKED"
    assert final_event(store, project, run)["payload"]["selected_candidate_ids"] == [candidate["id"]]
    return store, run, candidate


def test_every_report_obligation_must_remain_present_and_keep_its_applicable_status(complete_scope_candidate, monkeypatch):
    from oma.routing.selection import try_selection_evidence
    store, run, candidate = complete_scope_candidate
    state = store.get(candidate["state_root"])
    original = store.get(candidate["report_root"])
    lookup = store.candidate
    for index, check in enumerate(original["results"]):
        for fault in ("omitted", "wrong_applicability"):
            report = deepcopy(original)
            if fault == "omitted":
                report["results"].pop(index)
            else:
                report["results"][index]["status"] = "NOT_APPLICABLE" if check["status"] == "PASS" else "PASS"
            forged = {**candidate, "report_root": store.put(report)}
            with monkeypatch.context() as patch:
                patch.setattr(store, "candidate", lambda cid: forged if cid == candidate["id"] else lookup(cid))
                evidence, reason = try_selection_evidence(store, run, candidate["id"], candidate["kind"], state["mission"]["objective_weights"])
            assert evidence is None and reason, {"check": check["id"], "fault": fault, "scope": candidate["kind"]}


@pytest.mark.parametrize("kind", ["single", "joint", "network"])
def test_fresh_rejection_of_cached_incumbent_is_not_selected(kind, tmp_path, monkeypatch):
    store, project, run = imported_case(tmp_path, kind)
    update = store.update_run
    rejected = []

    def concurrent_recheck(run_id, status, detail="", stage="compute", **fields):
        result = update(run_id, status, detail, stage, **fields)
        if run_id != run["id"] or stage not in {"selection", "joint_selection", "network_selection"} or rejected:
            return result
        candidate = next(c for c in store.candidates(project["id"]) if c["run_id"] == run_id)
        assert candidate["status"] == "CHECKED"
        state = store.get(candidate["state_root"])
        record = state["physical_networks"][0] if kind == "network" else state["routes"][0]
        path = store.resolve_path(store.get(record["geometry_artifact"])["export_path"])
        original = path.read_bytes()
        # A real second verifier observes changed candidate bytes while the
        # optimizer still holds its first PASS/cost. Restoring the file does
        # not erase that latest rejection or authorize the old cached verdict.
        try:
            path.write_bytes(original + b"\n")
            from oma.routing.check_execution import run_candidate_check
            import time
            execution = run_candidate_check(store, candidate["id"], deadline=time.monotonic() + 60)
            assert execution["status"] == "COMPLETED" and execution["report_published"]
            assert execution["report_status"] == "FAIL"
        finally:
            path.write_bytes(original)
        assert store.candidate(candidate["id"])["status"] == "REJECTED"
        rejected.append(candidate["id"])
        return result

    monkeypatch.setattr(store, "update_run", concurrent_recheck)
    route_project_run(store, run, WorkerControl(store, run["id"]))
    assert rejected
    event = final_event(store, project, run)
    selected = event["payload"]["selected_candidate_ids"]
    assert not set(selected) & set(rejected), {"selected": selected, "now_rejected": rejected}
    assert all(store.candidate(cid)["status"] == "CHECKED" for cid in selected)


@pytest.mark.parametrize("kind", ["single", "joint", "network"])
def test_finite_selection_limit_retains_a_separately_checked_incumbent_without_optimum_claim(kind, tmp_path, monkeypatch):
    store, project, run = imported_case(tmp_path, kind)
    module = importlib.import_module("oma.routing." + {"single": "engine", "joint": "joint", "network": "network_engine"}[kind])
    name = "solve_master" if kind == "single" else "solve_finite_codesign"
    solve = getattr(module, name)
    interrupted = []

    def one_node(problem, **kwargs):
        result = solve(problem, **{**kwargs, "max_nodes": 1})
        interrupted.append(result.status if kind == "single" else result["status"])
        return result

    monkeypatch.setattr(module, name, one_node)
    route_project_run(store, run, WorkerControl(store, run["id"]))
    candidates = [c for c in store.candidates(project["id"]) if c["run_id"] == run["id"]]
    assert len(candidates) == 1 and candidates[0]["status"] == "CHECKED"
    assert interrupted and all("UNKNOWN" in status for status in interrupted)
    event = final_event(store, project, run)
    assert event["payload"]["selected_candidate_ids"] == [candidates[0]["id"]], event["payload"]
    assert event["payload"]["global_lower_bound"] is None and event["payload"]["global_gap"] is None


@pytest.mark.parametrize("kind", ["single", "joint", "network"])
def test_interrupted_child_is_not_admitted_even_if_it_wrote_a_pass_before_timeout(kind, tmp_path, monkeypatch):
    store, project, run = imported_case(tmp_path, kind)
    import json
    from pathlib import Path
    import oma.routing.check_execution as checking
    execute = checking.supervise_check
    interrupted = []

    def late_timeout(command, **kwargs):
        result = execute(command, **kwargs)
        if list(command[1:3]) == ["-m", "oma.routing.check_execution"]:
            request = json.loads(Path(command[-1]).read_text(encoding="utf-8"))
            receipt = json.loads((Path(command[-1]).parent / "receipt.json").read_text(encoding="utf-8"))
            candidate = store.candidate(request["candidate_id"])
            assert result["status"] == "COMPLETED" and candidate["status"] == "CHECKING"
            assert receipt["report_status"] == "PASS"
            interrupted.append(candidate["id"])
            # The actual native report exists only as a private receipt when
            # the parent observes an incomplete checker process.
            return {**result, "status": "UNKNOWN_TIMEOUT", "reason": "Injected timeout after actual native PASS receipt"}
        return result

    monkeypatch.setattr(checking, "supervise_check", late_timeout)
    route_project_run(store, run, WorkerControl(store, run["id"]))
    assert interrupted
    assert all(store.candidate(cid)["status"] == "UNKNOWN" and store.candidate(cid)["report_root"] is None for cid in interrupted)
    from oma.store import IntegrityError
    from oma.build_identity import checker_version
    for cid in interrupted:
        with pytest.raises(IntegrityError, match="passing independent report"):
            store.accept(project["id"], cid, store.project(project["id"])["revision"], "late-pass-" + cid, checker_version=checker_version())
    event = final_event(store, project, run)
    assert not event["payload"]["selected_candidate_ids"]
    retained = store.get(event["payload"]["selection_evidence_root"])
    assert retained["status"] == "NO_CURRENT_CHECKED_INCUMBENT"
    assert not retained["selected_source_and_candidate_bytes_freshly_checked"]
