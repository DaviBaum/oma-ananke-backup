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
    from oma.verification import CHECKER_VERSION
    result = store.accept(project["id"], checked[0]["id"], 1, "accept", checker_version=CHECKER_VERSION)
    assert result["revision"] == 2
    report = store.get(checked[0]["report_root"])
    assert report["status"] == "PASS"
    assert report["objective"]["length_m"] > 4
    assert len(report["results"]) >= 9
    assert store.get(store.history(project["id"])[-1]["root"])["sources"] == []
    assert store.project(project["id"])["state_root"] == checked[0]["state_root"]
    from oma.exporting import export_project
    bundle = export_project(store, project["id"], checked[0]["id"], draft=False)
    assert bundle["status"] == "CHECKED_LOCAL_SCOPE"
    assert bundle["round_trip"] == "PASS"
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
    import subprocess
    import sys
    backup = store.backup(tmp_path / "backup")
    store.directory.rename(tmp_path / "original-unavailable")
    restored = restore_store(backup, tmp_path / "relocated")
    result = subprocess.run([sys.executable, "-m", "oma.verification", str(restored.directory), checked[0]["id"]],
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    relocated = restored.candidate(checked[0]["id"])
    assert relocated["state_root"] == checked[0]["state_root"]
    assert relocated["status"] == "CHECKED"
    assert restored.get(relocated["report_root"])["objective"] == report["objective"]
    view = EngineService(restored.directory).geometry(project["id"], candidate_id=checked[0]["id"])
    assert any(mesh["entity_id"] in checked[0]["changed_ids"] for mesh in view["meshes"])


def test_missing_mission_is_recorded_not_a_fabricated_route(tmp_path):
    store = Store(tmp_path / "store")
    project = store.create_project("empty", {})
    run = store.create_run(project["id"], {"operation": "route", "mission": None})
    route_project_run(store, run, WorkerControl(store, run["id"]))
    assert store.run(run["id"])["status"] == "MISSING_INPUTS"
    assert store.candidates(project["id"]) == []
