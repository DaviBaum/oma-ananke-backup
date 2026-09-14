"""Interleavings at real Store publication boundaries, with analytic reports."""
from copy import deepcopy
import uuid

import pytest

from oma.build_identity import checker_version
from oma.store import Conflict, IntegrityError, Store, digest, utcnow


@pytest.fixture
def case(tmp_path):
    store = Store(tmp_path / "store")
    mission = {"id": "fixed", "rule_hash": "fixed-rules"}
    project = store.create_project("Execution publication interleavings", {"mission": mission})
    run = store.create_run(project["id"], {"operation": "check"})
    state = store.get(project["state_root"])
    candidate = store.add_candidate(run["id"], state, {"kind": "analytic-fixture"})
    report = {"candidate_root": candidate["state_root"], "mission_hash": digest(mission), "rule_hash": mission["rule_hash"],
        "checker_version": checker_version(), "status": "PASS", "scope": "Analytic fixture only",
        "results": [{"id": "analytic-value", "status": "PASS", "reason": "Fixed synthetic reference", "scope": "Analytic fixture only"}],
        "objective": {"value": 1.}, "created_at": utcnow()}
    return store, project, run, candidate, report


def begin(case, *, candidate=None, control_run_id=None, deadline=None):
    store, _, _, original, _ = case
    candidate = candidate or original
    token = uuid.uuid4().hex
    binding = store.begin_check_execution(candidate["id"], token, checker_version=checker_version(),
        control_run_id=control_run_id, deadline=deadline)
    return token, binding


def test_private_pending_and_timed_out_report_cannot_be_accepted_or_republished(case):
    store, project, run, candidate, report = case
    token, binding = begin(case)
    assert store.candidate(candidate["id"])["status"] == "CHECKING"
    with pytest.raises(IntegrityError):
        store.accept(project["id"], candidate["id"], 0, "pending", checker_version=checker_version())
    observed = store.put({"process_status": "UNKNOWN_TIMEOUT", "private_report_root": store.put(report)})
    unknown = store.finish_check_execution(candidate["id"], token, status="UNKNOWN_TIMEOUT", report=report, evidence_root=observed)
    assert unknown["status"] == "UNKNOWN" and unknown["report_root"] is None
    with pytest.raises(IntegrityError, match="stale, completed"):
        store.finish_check_execution(candidate["id"], token, status="COMPLETED", report=report)
    with pytest.raises(IntegrityError, match="Managed candidate"):
        store.record_verification(candidate["id"], report)
    event = next(e for e in reversed(store.events(project["id"])) if e["stage"] == "check_execution")
    assert store.put(report) in event["artifacts"] and observed in event["artifacts"]
    assert store.project(project["id"])["revision"] == 0


@pytest.mark.parametrize("interruption", ["cancel", "pause", "terminal", "deadline"])
def test_stop_arriving_during_assurance_work_prevents_atomic_pass(case, monkeypatch, interruption):
    import oma.project_assurance as assurance
    import oma.store as store_module
    store, project, run, candidate, report = case
    clock = [10.]
    monkeypatch.setattr(store_module.time, "monotonic", lambda: clock[0])
    token, _ = begin(case, deadline=20.)
    original = assurance.build_report_assurance
    def interrupted(*args, **kwargs):
        result = original(*args, **kwargs)
        if interruption in {"cancel", "pause"}:
            store.control(run["id"], interruption)
        elif interruption == "terminal":
            store.update_run(run["id"], "TIMED_OUT")
        else:
            clock[0] = 20.
        return result
    monkeypatch.setattr(assurance, "build_report_assurance", interrupted)
    with pytest.raises(IntegrityError, match="before report publication"):
        store.finish_check_execution(candidate["id"], token, status="COMPLETED", report=report)
    assert store.candidate(candidate["id"])["status"] == "CHECKING"
    store.finish_check_execution(candidate["id"], token, status="UNKNOWN_ADMISSION_REJECTED", report=report)
    assert store.candidate(candidate["id"])["status"] == "UNKNOWN"
    assert not any(e["stage"] == "verification" for e in store.events(project["id"]))


def test_newer_execution_finishing_during_old_assurance_cannot_be_overwritten(case, monkeypatch):
    import oma.project_assurance as assurance
    store, _, _, candidate, report = case
    first, _ = begin(case)
    newer = deepcopy(report)
    newer["objective"] = {"value": 2.}
    invoked = []
    original = assurance.build_report_assurance
    def interleave(*args, **kwargs):
        if not invoked:
            invoked.append(True)
            second, _ = begin(case)
            store.finish_check_execution(candidate["id"], second, status="COMPLETED", report=newer)
        return original(*args, **kwargs)
    monkeypatch.setattr(assurance, "build_report_assurance", interleave)
    with pytest.raises(IntegrityError, match="no longer owns"):
        store.finish_check_execution(candidate["id"], first, status="COMPLETED", report=report)
    with pytest.raises(IntegrityError):
        store.finish_check_execution(candidate["id"], first, status="UNKNOWN_TIMEOUT")
    current = store.candidate(candidate["id"])
    assert current["status"] == "CHECKED" and store.get(current["report_root"])["objective"] == newer["objective"]


@pytest.mark.parametrize("fault", ["root", "mission", "rules", "build", "origin_request", "control_request", "candidate_scope"])
def test_execution_receipt_cannot_change_bound_inputs_at_commit(case, fault):
    store, _, run, candidate, report = case
    control = store.create_run(run["project_id"], {"operation": "recheck", "candidate_id": candidate["id"]})
    token, _ = begin(case, control_run_id=control["id"])
    changed = deepcopy(report)
    if fault == "root": changed["candidate_root"] = "a" * 64
    elif fault == "mission": changed["mission_hash"] = "a" * 64
    elif fault == "rules": changed["rule_hash"] = "other-rules"
    elif fault == "build": changed["checker_version"] = "unrelated-build"
    elif fault == "candidate_scope":
        with store.transaction() as db:
            db.execute("UPDATE candidates SET payload=? WHERE id=?", ('{"kind":"unrelated-scope"}', candidate["id"]))
    else:
        rid = run["id"] if fault == "origin_request" else control["id"]
        with store.transaction() as db:
            db.execute("UPDATE runs SET request=? WHERE id=?", ('{"operation":"changed"}', rid))
    with pytest.raises(IntegrityError):
        store.finish_check_execution(candidate["id"], token, status="COMPLETED", report=changed)
    assert store.candidate(candidate["id"])["status"] != "CHECKED"


def test_completed_origin_can_be_rechecked_only_by_fresh_owned_control_run(case):
    store, project, run, candidate, report = case
    first, _ = begin(case)
    store.finish_check_execution(candidate["id"], first, status="COMPLETED", report=report)
    prior_root = store.candidate(candidate["id"])["report_root"]
    store.update_run(run["id"], "COMPLETED")
    with pytest.raises(IntegrityError, match="fresh recheck run"):
        begin(case)
    owner = store.create_run(project["id"], {"operation": "recheck", "candidate_id": candidate["id"]})
    token, binding = begin(case, control_run_id=owner["id"])
    assert binding["prior_report_root"] == prior_root
    assert binding["control_run_id"] == owner["id"] and binding["origin_run_id"] == run["id"]
    checked = store.finish_check_execution(candidate["id"], token, status="COMPLETED", report=report)
    assert checked["status"] == "CHECKED"


def test_timeout_does_not_discard_another_completed_incumbent(case):
    store, project, run, candidate, report = case
    first, _ = begin(case)
    store.finish_check_execution(candidate["id"], first, status="COMPLETED", report=report)
    other = store.add_candidate(run["id"], store.get(candidate["state_root"]), {"kind": "analytic-fixture"})
    second, _ = begin(case, candidate=other)
    store.finish_check_execution(other["id"], second, status="UNKNOWN_TIMEOUT", report=report)
    store.update_run(run["id"], "BUDGET_EXHAUSTED")
    assert store.candidate(candidate["id"])["status"] == "CHECKED"
    assert store.accept(project["id"], candidate["id"], 0, "retain-earlier", checker_version=checker_version())["status"] == "ACCEPTED"


@pytest.mark.parametrize("interruption", ["new_pending", "new_rejection"])
def test_acceptance_revalidates_latest_report_inside_revision_transaction(case, monkeypatch, interruption):
    store, project, _, candidate, report = case
    first, _ = begin(case)
    store.finish_check_execution(candidate["id"], first, status="COMPLETED", report=report)
    original = store.publish
    def concurrent(*args, **kwargs):
        # accept() has already read its old CHECKED/report pair at this point.
        newer, _ = begin(case)
        if interruption == "new_rejection":
            rejected = deepcopy(report)
            rejected["status"] = rejected["results"][0]["status"] = "FAIL"
            store.finish_check_execution(candidate["id"], newer, status="COMPLETED", report=rejected)
        return original(*args, **kwargs)
    monkeypatch.setattr(store, "publish", concurrent)
    with pytest.raises(IntegrityError, match="acceptance transaction"):
        store.accept(project["id"], candidate["id"], 0, "stale-accept", checker_version=checker_version())
    assert store.project(project["id"])["revision"] == 0
    assert not any(e["status"] == "ACCEPTED" for e in store.events(project["id"]))


def test_tokens_and_control_owners_cannot_be_rebound_to_unrelated_candidates(case):
    store, project, run, candidate, report = case
    token, _ = begin(case)
    other = store.add_candidate(run["id"], store.get(candidate["state_root"]), {"kind": "analytic-fixture"})
    with pytest.raises(IntegrityError):
        store.finish_check_execution(other["id"], token, status="COMPLETED", report=report)
    with pytest.raises(Conflict):
        store.begin_check_execution(candidate["id"], token, checker_version=checker_version())
    unrelated = store.create_run(project["id"], {"operation": "recheck", "candidate_id": other["id"]})
    with pytest.raises(IntegrityError, match="does not own"):
        begin(case, control_run_id=unrelated["id"])


def test_step_control_can_publish_a_completed_owned_check(case):
    store, _, run, candidate, report = case
    token, _ = begin(case)
    store.control(run["id"], "step")
    assert store.consume_step(run["id"])
    assert store.finish_check_execution(candidate["id"], token, status="COMPLETED", report=report)["status"] == "CHECKED"


def test_completed_execution_cannot_cover_changed_candidate_scope_metadata(case):
    store, project, _, candidate, report = case
    token, _ = begin(case)
    store.finish_check_execution(candidate["id"], token, status="COMPLETED", report=report)
    with store.transaction() as db:
        db.execute("UPDATE candidates SET payload=? WHERE id=?", ('{"kind":"unrelated-scope"}', candidate["id"]))
    with pytest.raises(IntegrityError, match="scope changed"):
        store.accept(project["id"], candidate["id"], 0, "changed-scope", checker_version=checker_version())


def test_backup_retains_execution_fences_and_prior_report_evidence(case, tmp_path):
    store, _, _, candidate, report = case
    first, _ = begin(case)
    prior = store.finish_check_execution(candidate["id"], first, status="COMPLETED", report=report)["report_root"]
    second, _ = begin(case)
    store.finish_check_execution(candidate["id"], second, status="UNKNOWN_TIMEOUT", report=report)
    restored = Store(store.backup(tmp_path / "restored"))
    assert restored.candidate(candidate["id"])["status"] == "UNKNOWN"
    assert restored.get(prior)["status"] == "PASS"
    with pytest.raises(IntegrityError):
        restored.finish_check_execution(candidate["id"], first, status="COMPLETED", report=report)
    with pytest.raises(IntegrityError):
        restored.record_verification(candidate["id"], report)
    with restored.connect() as db:
        history = [dict(row) for row in db.execute("SELECT * FROM check_executions WHERE candidate_id=?", (candidate["id"],))]
    assert {row["status"] for row in history} == {"COMPLETED", "UNKNOWN_TIMEOUT"}
