from concurrent.futures import ThreadPoolExecutor

import pytest

from oma.models import VerificationReport
from oma.store import Conflict, IntegrityError, Store, digest, utcnow


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "live")


def test_immutable_branches_idempotent_retry_and_conflict(store):
    p = store.create_project("test", {"routes": [{"points": [[0, 0, 0], [1, 0, 0]]}]})
    original = store.get(p["state_root"])
    sibling = store.get(p["state_root"])
    original["routes"][0]["points"][1][0] = 2
    assert sibling["routes"][0]["points"][1][0] == 1
    result = store.publish(p["id"], original, 0, "edit-1")
    assert store.publish(p["id"], original, 0, "edit-1") == result
    with pytest.raises(Conflict):
        store.publish(p["id"], sibling, 0, "edit-1")
    with pytest.raises(Conflict):
        store.publish(p["id"], sibling, 0, "edit-2")
    assert len(store.history(p["id"])) == 2
    assert len(store.events(p["id"])) == 2


def test_concurrent_writers_publish_only_one_revision_and_event(store):
    p = store.create_project("test", {})
    def write(i):
        try:
            return store.publish(p["id"], {"project_id": p["id"], "value": i}, 0, str(i))
        except Conflict:
            return None
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(write, range(12)))
    assert sum(r is not None for r in results) == 1
    assert len(store.events(p["id"])) == 2


def test_failed_publication_rolls_back_revision_and_outbox(store, monkeypatch):
    p = store.create_project("test", {})
    def fail(*args, **kwargs):
        raise RuntimeError("injected outbox failure")
    monkeypatch.setattr(store, "_event", fail)
    with pytest.raises(RuntimeError):
        store.publish(p["id"], {"project_id": p["id"], "edit": 1}, 0, "edit")
    assert store.project(p["id"])["revision"] == 0
    assert len(store.history(p["id"])) == 1


def test_corrupt_blob_and_nonfinite_inputs_rejected(store):
    root = store.put({"value": 1})
    (store.blobs / f"{root}.json.z").write_bytes(b"corrupt")
    with pytest.raises(IntegrityError):
        store.get(root)
    with pytest.raises(ValueError):
        store.put({"nan": float("nan")})
    with pytest.raises(IntegrityError):
        store.get("../anything")


def test_acceptance_requires_exact_root_mission_and_checker_version(store):
    mission = {"id": "mission", "rule_hash": "rules-1"}
    p = store.create_project("test", {"mission": mission})
    run = store.create_run(p["id"], {"operation": "route"})
    state = store.get(p["state_root"])
    state["routes"] = [{"id": "r1"}]
    candidate = store.add_candidate(run["id"], state, {"changed_ids": ["r1"]})
    with pytest.raises(IntegrityError):
        store.accept(p["id"], candidate["id"], 0, "accept", checker_version="v1")
    report = {"candidate_root": candidate["state_root"], "mission_hash": digest(mission), "rule_hash": "rules-1",
              "checker_version": "v1", "status": "PASS", "scope": "fixture", "results": [
                  {"id": "fixture-proof", "status": "PASS", "reason": "Analytic reference fixture", "scope": "fixture"}],
              "objective": {"length_m": 1}, "created_at": utcnow()}
    store.record_verification(candidate["id"], report)
    with pytest.raises(IntegrityError):
        store.accept(p["id"], candidate["id"], 0, "accept", checker_version="v2")
    accepted = store.accept(p["id"], candidate["id"], 0, "accept", checker_version="v1")
    assert accepted["status"] == "ACCEPTED"
    assert store.accept(p["id"], candidate["id"], 0, "accept", checker_version="v1") == accepted
    report["results"] = []
    with pytest.raises(ValueError):
        VerificationReport.model_validate(report)


def test_recovery_revert_backup_and_restore(store, tmp_path, monkeypatch):
    p = store.create_project("test", {"mission": {"fixed": True}})
    run = store.create_run(p["id"], {"operation": "route"})
    store.update_run(run["id"], "RUNNING", "working")
    store.control(run["id"], "cancel")
    assert store.run(run["id"])["status"] == "RUNNING"  # Request is not worker acknowledgement.
    assert store.recover() == []  # A different API instance must preserve a live CLI.
    monkeypatch.setattr(store, "_owner_alive", lambda row: False)
    assert store.recover() == [run["id"]]
    assert store.run(run["id"])["status"] == "CRASHED"
    store.publish(p["id"], {"project_id": p["id"], "changed": True}, 0, "edit")
    store.revert(p["id"], 0, 1, "undo")
    assert store.project(p["id"])["state_root"] == p["state_root"]
    backup = store.backup(tmp_path / "backup")
    restored = Store(backup)
    assert restored.project(p["id"]) == store.project(p["id"])
    assert restored.events(p["id"]) == store.events(p["id"])
    assert restored.get(p["state_root"]) == store.get(p["state_root"])


def test_terminal_job_cannot_be_resurrected_by_late_supervisor(store):
    p = store.create_project("test", {})
    run = store.create_run(p["id"], {"operation": "route"})
    store.update_run(run["id"], "CANCELLED")
    count = len(store.events(p["id"]))
    assert store.update_run(run["id"], "RUNNING")["status"] == "CANCELLED"
    assert store.update_run(run["id"], "CRASHED")["status"] == "CANCELLED"
    assert len(store.events(p["id"])) == count


def test_import_and_run_retries_create_one_durable_job(store):
    with ThreadPoolExecutor(max_workers=4) as pool:
        imports = list(pool.map(lambda _: store.create_import("sources", {}, ["source.ifc"], "retry-import"), range(8)))
    assert len({p["id"] for p in imports}) == 1
    assert len({p["import_run_id"] for p in imports}) == 1
    assert len(store.projects()) == 1
    p = imports[0]
    assert len(store.events(p["id"])) == 1
    with pytest.raises(Conflict):
        store.create_import("different", {}, ["source.ifc"], "retry-import")
    request = {"operation": "check", "budget_seconds": 30, "idempotency_key": "retry-check"}
    with ThreadPoolExecutor(max_workers=4) as pool:
        runs = list(pool.map(lambda _: store.create_run(p["id"], request), range(8)))
    assert len({r["id"] for r in runs}) == 1
    assert len(store.runs(p["id"])) == 2
    with pytest.raises(Conflict):
        store.create_run(p["id"], {**request, "budget_seconds": 60})


def test_portable_backup_binds_bytes_and_resolves_without_original(store, tmp_path):
    from oma.backup import restore_store, verify_backup
    asset = store.directory / "imports" / "source.ifc"
    asset.parent.mkdir()
    asset.write_bytes(b"immutable source fixture")
    external = tmp_path / "external.ifc"
    external.write_bytes(b"external materialized fixture")
    p = store.create_project("portable", {"sources": [{"immutable_path": str(asset)}], "export_path": str(external)})
    backup = store.backup(tmp_path / "backup")
    assert verify_backup(backup)["status"] == "PASS"
    # Rename original store and source to prove no successful read falls back.
    store.directory.rename(tmp_path / "unavailable-original")
    external.rename(tmp_path / "unavailable-external.ifc")
    restored = restore_store(backup, tmp_path / "restored")
    state = restored.get(p["state_root"])
    assert restored.project(p["id"])["state_root"] == p["state_root"]
    assert restored.resolve_path(state["sources"][0]["immutable_path"]).read_bytes() == b"immutable source fixture"
    assert restored.resolve_path(state["export_path"]).read_bytes() == b"external materialized fixture"
    second = restored.backup(tmp_path / "second-backup")
    store2 = restore_store(second, tmp_path / "second-restore")
    assert store2.resolve_path(state["sources"][0]["immutable_path"]).read_bytes() == b"immutable source fixture"
    copied = backup / "imports" / "source.ifc"
    copied.write_bytes(b"tampered source fixture")
    with pytest.raises(IntegrityError, match="hash mismatch"):
        restore_store(backup, tmp_path / "tampered-restore")
