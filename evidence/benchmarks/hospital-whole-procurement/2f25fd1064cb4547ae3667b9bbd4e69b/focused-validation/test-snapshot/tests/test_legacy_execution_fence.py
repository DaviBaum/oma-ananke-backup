"""Old SQL publication shapes cannot bypass a managed checker execution.

Reports here are explicit analytic fixtures. Native late-PASS process evidence
is exercised separately by test_route_check_execution.py.
"""
from copy import deepcopy
import sqlite3

import pytest

from oma.build_identity import checker_version
from oma.store import Store, utcnow
from test_verification_execution_atomicity import case, begin


def legacy_candidate_write(store, candidate_id, status, report_root):
    # Statement used by pre-execution-protocol Store.record_verification.
    with store.transaction() as db:
        db.execute("UPDATE candidates SET status=?,report_root=? WHERE id=?", (status, report_root, candidate_id))


def legacy_accepted_revision(store, project, candidate):
    # The old publish transaction inserted its revision after reading a report
    # outside the transaction; it had no managed exact-report authorization.
    with store.transaction() as db:
        db.execute("INSERT INTO revisions VALUES(?,?,?,?,?,?,?)", (
            project["id"], 1, candidate["state_root"], project["state_root"], "ACCEPTED", utcnow(), candidate["id"]))


@pytest.mark.parametrize("disposition", ["RUNNING", "UNKNOWN_TIMEOUT", "UNKNOWN_ABNORMAL_EXIT", "UNKNOWN_CANCELLED"])
def test_legacy_late_pass_cannot_publish_during_or_after_incomplete_execution(case, disposition):
    store, project, _, candidate, report = case
    token, _ = begin(case)
    report_root = store.put(report)
    if disposition != "RUNNING":
        store.finish_check_execution(candidate["id"], token, status=disposition, report=report)
    before = store.candidate(candidate["id"])
    with pytest.raises(sqlite3.IntegrityError, match="Managed checker execution"):
        legacy_candidate_write(store, candidate["id"], "CHECKED", report_root)
    assert store.candidate(candidate["id"]) == before
    assert store.project(project["id"])["revision"] == 0


def test_legacy_old_pass_cannot_replace_new_rejected_report(case):
    store, _, _, candidate, report = case
    first, _ = begin(case)
    checked = store.finish_check_execution(candidate["id"], first, status="COMPLETED", report=report)
    second, _ = begin(case)
    rejected = deepcopy(report)
    rejected["status"] = rejected["results"][0]["status"] = "FAIL"
    current = store.finish_check_execution(candidate["id"], second, status="COMPLETED", report=rejected)
    with pytest.raises(sqlite3.IntegrityError, match="Managed checker execution"):
        legacy_candidate_write(store, candidate["id"], "CHECKED", checked["report_root"])
    assert store.candidate(candidate["id"]) == current


@pytest.mark.parametrize("new_check", ["none", "running", "rejected", "new_pass"])
def test_legacy_acceptance_cannot_attach_stale_or_unbound_report_to_managed_revision(case, new_check):
    store, project, _, candidate, report = case
    first, _ = begin(case)
    store.finish_check_execution(candidate["id"], first, status="COMPLETED", report=report)
    if new_check != "none":
        second, _ = begin(case)
        if new_check != "running":
            updated = deepcopy(report)
            updated["objective"] = {"value": 2.}
            if new_check == "rejected":
                updated["status"] = updated["results"][0]["status"] = "FAIL"
            store.finish_check_execution(candidate["id"], second, status="COMPLETED", report=updated)
    with pytest.raises(sqlite3.IntegrityError, match="transactional report authorization"):
        legacy_accepted_revision(store, project, candidate)
    assert len(store.history(project["id"])) == 1


def test_current_managed_acceptance_consumes_exact_report_authorization_and_is_idempotent(case):
    store, project, _, candidate, report = case
    first, _ = begin(case)
    checked = store.finish_check_execution(candidate["id"], first, status="COMPLETED", report=report)
    result = store.accept(project["id"], candidate["id"], 0, "current-pass", checker_version=checker_version())
    assert result["status"] == "ACCEPTED"
    assert store.accept(project["id"], candidate["id"], 0, "current-pass", checker_version=checker_version()) == result
    accepted = [event for event in store.events(project["id"]) if event["status"] == "ACCEPTED"]
    assert len(accepted) == 1 and checked["report_root"] in accepted[0]["artifacts"]
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM managed_acceptance_authorizations").fetchone()[0] == 0


def test_failed_publication_rolls_back_authorization_revision_and_event_together(case, monkeypatch):
    store, project, _, candidate, report = case
    first, _ = begin(case)
    store.finish_check_execution(candidate["id"], first, status="COMPLETED", report=report)
    original_event = store._event
    def fail_outbox(db, project_id, **fields):
        if fields.get("status") == "ACCEPTED":
            raise RuntimeError("Interrupted publication before outbox commit")
        return original_event(db, project_id, **fields)
    with monkeypatch.context() as scoped:
        scoped.setattr(store, "_event", fail_outbox)
        with pytest.raises(RuntimeError, match="Interrupted publication"):
            store.accept(project["id"], candidate["id"], 0, "retry-pass", checker_version=checker_version())
    assert store.project(project["id"])["revision"] == 0 and len(store.history(project["id"])) == 1
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM managed_acceptance_authorizations").fetchone()[0] == 0
    assert store.accept(project["id"], candidate["id"], 0, "retry-pass", checker_version=checker_version())["status"] == "ACCEPTED"


def test_unmanaged_legacy_candidate_remains_compatible_after_store_reopen(case):
    store, project, _, candidate, report = case
    store.record_verification(candidate["id"], report)
    reopened = Store(store.directory)
    assert reopened.accept(project["id"], candidate["id"], 0, "legacy-pass", checker_version=checker_version())["status"] == "ACCEPTED"


def test_database_backup_preserves_managed_publication_fences(case, tmp_path):
    store, project, _, candidate, report = case
    first, _ = begin(case)
    store.finish_check_execution(candidate["id"], first, status="UNKNOWN_TIMEOUT", report=report)
    copied_db = tmp_path / "copy.sqlite3"
    with store.connect() as source, sqlite3.connect(copied_db) as target:
        source.backup(target)
    # Operate the copied DB directly without invoking the new Store initializer.
    with sqlite3.connect(copied_db) as target:
        with pytest.raises(sqlite3.IntegrityError, match="Managed checker execution"):
            target.execute("UPDATE candidates SET status='CHECKED', report_root=? WHERE id=?", (store.put(report), candidate["id"]))
        assert target.execute("SELECT revision FROM projects WHERE id=?", (project["id"],)).fetchone()[0] == 0
