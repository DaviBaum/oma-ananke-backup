import json

from oma.routing.engine import route_project_run
from oma.store import Store
from oma.worker import WorkerControl, import_sources
from test_ifc_pipeline import make_fixture


def test_real_ifc_pipeline_rejects_intersecting_baseline_then_accepts_checked_route(tmp_path):
    source = make_fixture(tmp_path / "obstacle.ifc")
    store = Store(tmp_path / "store")
    project = store.create_project("Analytic seeded building", {"sources": [], "entities": []})
    imp = store.create_run(project["id"], {"operation": "import", "paths": [str(source)]})
    import_sources(store, imp, WorkerControl(store, imp["id"]))
    scenario = {"start": [-1., 1., 1.], "end": [3., 1., 1.], "system_type": "PRESSURE_PIPE",
                "diameter_m": .1, "insulation_m": .02, "bend_radius_m": .3, "minimum_straight_m": .05,
                "clearance_m": .1, "allowed_zone": {"min": [-2., -2., -2.], "max": [4., 4., 4.]},
                "scenario_terminals": True, "max_candidates": 12}
    run = store.create_run(project["id"], {"operation": "route", "mission": scenario, "budget_seconds": 90})
    route_project_run(store, run, WorkerControl(store, run["id"]))
    candidates = store.candidates(project["id"])
    assert candidates[0]["status"] == "REJECTED"
    rejected = store.get(candidates[0]["report_root"])
    assert next(r["status"] for r in rejected["results"] if r["id"] == "native-forbidden-volume-counterexample") == "FAIL"
    assert next(r["status"] for r in rejected["results"] if r["id"] == "physical-interference-and-clearance") == "NOT_RUN"
    checked = [c for c in candidates if c["status"] == "CHECKED"]
    assert checked, [(c["status"], store.get(c["report_root"])["results"] if c["report_root"] else None) for c in candidates]
    # This native workflow must consume a source-bound fabrication-state path,
    # then independently check actual elbows and the complete obstacle set.
    certified = [c for c in checked if c.get("proposal_evidence")]
    assert certified
    checked = certified + [c for c in checked if not c.get("proposal_evidence")]
    evidence = checked[0]["proposal_evidence"]
    model = store.get(evidence["report_root"])
    assert model["context"]["base_root"] == run["base_root"]
    assert evidence["method"] == "SOURCE_BOUND_FABRICATION_GRAPH"
    assert model["report"]["status"] == "CHECKED_FABRICATION_PROPOSALS"
    assert model["report"]["source_coverage_check"]["physical_elements"] == 1
    assert model["report"]["binary64_fabrication_check"]["fabrication_status"] == "PASS"
    assert not evidence["route_acceptance"] and not evidence["physical_infeasibility_claim"]
    assert store.get(checked[0]["state_root"])["derived_artifacts"]["route_proposal_evidence"] == evidence
    from oma.verification import CHECKER_VERSION
    result = store.accept(project["id"], checked[0]["id"], 1, "accept", checker_version=CHECKER_VERSION)
    assert result["revision"] == 2
    report = store.get(checked[0]["report_root"])
    assert report["status"] == "PASS"
    fabrication = next(r for r in report["results"] if r["id"] == "nominal-fabrication-witness-integrity")
    assert fabrication["status"] == "PASS"
    assert fabrication["witness"]["origin_run_id"] == run["id"]
    assert fabrication["witness"]["producer_check_reused"] is False
    assert fabrication["witness"]["candidate_acceptance_authority"] is False
    assert report["objective"]["length_m"] > 4
    assert len(report["results"]) >= 9
    assert store.get(store.history(project["id"])[-1]["root"])["sources"] == []
    assert store.project(project["id"])["state_root"] == checked[0]["state_root"]
    from oma.exporting import export_project
    bundle = export_project(store, project["id"], checked[0]["id"], draft=False)
    assert bundle["status"] == "CHECKED_LOCAL_SCOPE"
    assert bundle["round_trip"] == "PASS"
    exported_report = store.get(store.get(bundle["artifact_root"])["verification_root"])
    exported_fabrication = next(r for r in exported_report["results"] if r["id"] == "nominal-fabrication-witness-integrity")
    assert exported_fabrication["status"] == "PASS"
    assert exported_fabrication["witness"]["artifact_root"] == fabrication["witness"]["artifact_root"]
    assert len(bundle["files"]) == 1  # Edited source replaces original; no duplicate discipline.
    assert bundle["files"][0]["changed"]
    store.revert(project["id"], 1, 2, "undo-repair")
    assert store.project(project["id"])["revision"] == 3
    assert store.get(store.project(project["id"])["state_root"])["routes"] == []
    # An optimizer cannot weaken its own fixed mission and then certify the edit.
    modified = store.get(checked[0]["state_root"])
    modified["derived_artifacts"]["routing_scenario"]["clearance_m"] = 0
    adversarial = store.add_candidate(run["id"], modified, {"kind": "physical_route", "changed_ids": checked[0]["changed_ids"]})
    from oma.routing.checker import verify_route_candidate
    mutated_report = verify_route_candidate(store, adversarial["id"])
    assert next(r for r in mutated_report.results if r.id == "fixed-request-assumptions").status == "FAIL"
    # Portability is checked with actual imported meshes and IFC solids, then
    # independently verified in a new process with the old store unavailable.
    from oma.backup import restore_store
    from oma.service import EngineService
    from oma.verification import recheck_candidate_run
    backup = store.backup(tmp_path / "backup")
    store.directory.rename(tmp_path / "original-unavailable")
    restored = restore_store(backup, tmp_path / "relocated")
    recheck = restored.create_run(project["id"], {"operation": "recheck", "candidate_id": checked[0]["id"], "budget_seconds": 90})
    recheck_candidate_run(restored, recheck, WorkerControl(restored, recheck["id"]))
    assert restored.run(recheck["id"])["status"] == "COMPLETED"
    relocated = restored.candidate(checked[0]["id"])
    assert relocated["state_root"] == checked[0]["state_root"]
    assert relocated["status"] == "CHECKED"
    assert restored.get(relocated["report_root"])["objective"] == report["objective"]
    restored_fabrication = next(r for r in restored.get(relocated["report_root"])["results"] if r["id"] == "nominal-fabrication-witness-integrity")
    assert restored_fabrication["status"] == "PASS"
    assert restored_fabrication["witness"]["artifact_root"] == fabrication["witness"]["artifact_root"]
    view = EngineService(restored.directory).geometry(project["id"], candidate_id=checked[0]["id"])
    assert any(mesh["entity_id"] in checked[0]["changed_ids"] for mesh in view["meshes"])


def test_missing_mission_is_recorded_not_a_fabricated_route(tmp_path):
    store = Store(tmp_path / "store")
    project = store.create_project("empty", {})
    run = store.create_run(project["id"], {"operation": "route", "mission": None})
    route_project_run(store, run, WorkerControl(store, run["id"]))
    assert store.run(run["id"])["status"] == "MISSING_INPUTS"
    assert store.candidates(project["id"]) == []
