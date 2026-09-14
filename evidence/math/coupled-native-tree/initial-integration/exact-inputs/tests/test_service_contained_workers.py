"""The actual service owns native worker/checker descendants until job exit."""
import time

from oma.build_identity import checker_version
from oma.service import EngineService
from test_joint_negative_hint_adversarial import _native_candidate


def until(predicate, seconds=30):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.03)
    raise AssertionError("Service did not reach the expected bounded state")


def test_service_native_recheck_completes_nested_jobs_and_keeps_exact_acceptance(tmp_path):
    case = _native_candidate(tmp_path / "native", crossing=False)
    service = EngineService(case["store"].directory)
    store, candidate = service.store, case["candidate"]
    try:
        run = service.start_run(candidate["project_id"], {
            "operation": "recheck", "candidate_id": candidate["id"], "budget_seconds": 45})
        until(lambda: run["id"] not in service.threads)
        assert store.run(run["id"])["status"] == "COMPLETED"
        current = store.candidate(candidate["id"])
        assert current["status"] == "CHECKED" and store.get(current["report_root"])["status"] == "PASS"
        event = next(e for e in reversed(store.events(candidate["project_id"]))
            if e["run_id"] == run["id"] and e["stage"] == "worker_supervision")
        result = store.get(event["artifacts"][0])
        assert result["status"] == "COMPLETED" and result["containment"]["active_processes"] == 0
        assert result["containment"]["assigned_before_resume"] and result["containment"]["total_processes"] >= 2
        project = store.project(candidate["project_id"])
        assert store.accept(project["id"], candidate["id"], project["revision"], "service-checked",
            checker_version=checker_version())["status"] == "ACCEPTED"
    finally:
        service.shutdown()


def test_service_shutdown_stops_a_real_paused_worker_job_without_candidate_publication(tmp_path):
    case = _native_candidate(tmp_path / "native", crossing=False)
    service = EngineService(case["store"].directory)
    store, candidate = service.store, case["candidate"]
    run = store.create_run(candidate["project_id"], {
        "operation": "recheck", "candidate_id": candidate["id"], "budget_seconds": 45})
    store.control(run["id"], "pause")
    try:
        service.schedule(run["id"])
        until(lambda: store.run(run["id"])["status"] == "PAUSED")
        service.shutdown()
        assert run["id"] not in service.threads
        assert store.run(run["id"])["status"] == "CANCELLED"
        current = store.candidate(candidate["id"])
        assert current["status"] != "CHECKED" and current["report_root"] is None
        event = next(e for e in reversed(store.events(candidate["project_id"]))
            if e["run_id"] == run["id"] and e["stage"] == "worker_supervision")
        result = store.get(event["artifacts"][0])
        assert result["status"] == "CANCELLED"
        assert result["termination"]["active_processes_after"] == 0
    finally:
        service.shutdown()
