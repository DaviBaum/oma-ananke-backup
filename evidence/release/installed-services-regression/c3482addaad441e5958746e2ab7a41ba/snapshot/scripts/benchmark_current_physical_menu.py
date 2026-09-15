"""Regenerate the frozen real Office joint scenario with current native checks."""
from pathlib import Path
import os
import subprocess
import sys

if not os.environ.get("OMA_EXECUTABLE_BUILD"):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from oma.build_identity import frozen_environment
    if __name__ == "__main__":
        raise SystemExit(subprocess.call([sys.executable, __file__], env=frozen_environment(Path(".oma") / "benchmark-builds")))

import copy
import json
import time
import uuid

from oma.build_identity import checker_version
from oma.exporting import export_project
from oma.ifc.audit import atomic_json
from oma.routing.engine import route_project_run
from oma.store import Store
from oma.worker import WorkerControl


def main():
    store = Store(Path(".oma"))
    historical = store.candidate("f583693cce4644ad8306b31d51c8540f")
    historical_run = store.run(historical["run_id"])
    baseline = store.get(historical_run["base_root"])
    assert not baseline.get("routes") and not baseline.get("physical_networks") and not baseline.get("mission")
    project = store.create_project("WBDG Office · checked finite physical menu", baseline)
    request = copy.deepcopy(historical_run["request"])
    request.update(operation="optimize", budget_seconds=600)
    request.pop("idempotency_key", None)
    directory = Path("evidence/benchmarks/physical-menu/office") / uuid.uuid4().hex
    directory.mkdir(parents=True)
    run = store.create_run(project["id"], request)
    atomic_json(directory / "input.json", {"project_id": project["id"], "run": run,
        "historical_run_id": historical_run["id"], "historical_base_root": historical_run["base_root"],
        "checker_version": checker_version(), "scope": "Current regeneration of the same two frozen design alternatives; no new continuous optimization claim"})
    print(json.dumps({"directory": str(directory), "project_id": project["id"], "run_id": run["id"]}), flush=True)
    start = time.monotonic()
    route_project_run(store, run, WorkerControl(store, run["id"]))
    candidates = [c for c in store.candidates(project["id"]) if c["run_id"] == run["id"]]
    for candidate in candidates:
        atomic_json(directory / f"{candidate['id']}.candidate.json", candidate)
        if candidate["report_root"]:
            atomic_json(directory / f"{candidate['id']}.report.json", store.get(candidate["report_root"]))
    events = store.events(project["id"], limit=1000)
    event = next(e for e in events if e["stage"] == "physical_menu_compilation")
    archive = store.get(event["artifacts"][0])
    atomic_json(directory / "archive.json", archive)
    for key in ("problem_root", "certificate_root", "frozen_menu_root"):
        if archive.get(key):
            atomic_json(directory / f"{key}.json", store.get(archive[key]))
    assert archive["independent_check"]["status"] == "PASS", archive
    assert archive["summary"]["verdict_counts"] == {"FAIL": 1, "PASS": 1}, archive
    checked = next(c for c in candidates if c["status"] == "CHECKED")
    accepted = store.accept(project["id"], checked["id"], project["revision"], "current-menu-accept", checker_version=checker_version())
    exported = export_project(store, project["id"], checked["id"], draft=False)
    result = {"status": "CHECKED_ACCEPTED_EXPORTED_RECHECKED", "project_id": project["id"], "run_id": run["id"],
        "candidate_ids": [c["id"] for c in candidates], "selected_candidate_id": checked["id"],
        "accepted": accepted, "export": exported, "archive_root": event["artifacts"][0],
        "archive_summary": archive["summary"], "checker_version": checker_version(),
        "elapsed_seconds": time.monotonic() - start, "continuous_optimality": "NOT_ESTABLISHED",
        "native_verdict_reuse": False, "scope": "Same frozen Office mission, regenerated actual candidates and independent mathematical report projection"}
    atomic_json(directory / "result.json", result)
    print(json.dumps({"status": result["status"], "directory": str(directory), "elapsed_seconds": result["elapsed_seconds"],
        "candidate_id": checked["id"], "export_id": exported["export_id"], "summary": archive["summary"]}), flush=True)


if __name__ == "__main__":
    main()
