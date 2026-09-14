"""Freshly recheck exact false-PASS IFC bytes in an isolated corrected runtime."""
from pathlib import Path
import json
import sqlite3
import sys
import time
import uuid

STAGE = Path(__file__).resolve().parent
ROOT = next(p for p in STAGE.parents if (p / "AGENTS.md").is_file())
sys.path[:0] = [str(STAGE / "src"), str(ROOT / "scripts")]
from oma.build_identity import checker_version, frozen_environment
from oma.ifc.audit import atomic_json, sha256_file
from oma.store import Store, _Connection, Conflict
from native_real_model_validation import isolate_candidate, managed_recheck, network_validation_evidence

ORIGINAL = STAGE / "evidence/df84bdb223ee49a5a5faa33b975a9580"
CANDIDATE = "589b12bc3dae4483b14584d6a8c84801"


class Original(Store):
    def __init__(self):
        self.directory = ORIGINAL / "store"
        self.database = self.directory / "oma.sqlite3"
        self.blobs = self.directory / "blobs"

    def connect(self):
        db = sqlite3.connect(self.database.as_uri() + "?mode=ro", uri=True, factory=_Connection)
        db.row_factory = sqlite3.Row
        return db

    def put(self, value):
        raise RuntimeError("Retained original store is read-only")


def main():
    out = STAGE / "evidence" / ("saved-byte-recheck-" + uuid.uuid4().hex)
    out.mkdir(parents=True)
    original = Original()
    candidate = original.candidate(CANDIDATE)
    project = original.project(candidate["project_id"])
    old_report = original.get(candidate["report_root"])
    old_state = original.get(candidate["state_root"])
    assert candidate["status"] == "CHECKED" and old_report["status"] == "PASS"
    original_db = sha256_file(original.database)
    environment = frozen_environment(STAGE)
    declaration = {"schema": "oma.fixed-flow-saved-byte-recheck/1", "status": "PREDECLARED",
        "checker_version": checker_version(), "candidate": candidate, "project": project,
        "original_database_sha256": original_db, "script_sha256": sha256_file(__file__),
        "copy_and_native_helper_sha256": sha256_file(ROOT / "scripts/native_real_model_validation.py"),
        "expected_geometry": "PASS", "expected_service": "UNKNOWN", "expected_acceptance": "REJECTED",
        "new_geometry_authored": False}
    atomic_json(out / "declaration.json", declaration)
    store, inputs = isolate_candidate(original, out / "isolated-store", CANDIDATE)
    before_assets = {row["original_resolved_path"]: row["sha256"] for row in inputs["assets"]}
    started = time.perf_counter()
    execution = managed_recheck(store, CANDIDATE, deadline=time.monotonic() + 90, environment=environment)
    assert execution["status"] == "COMPLETED" and execution["report_published"], execution
    checked = store.candidate(CANDIDATE)
    report = store.get(checked["report_root"])
    state = store.get(checked["state_root"])
    atomic_json(out / "corrected-candidate.json", checked)
    atomic_json(out / "corrected-report.json", report)
    assert state == old_state and checked["state_root"] == candidate["state_root"]
    rows = {r["id"]: r for r in report["results"]}
    assert len(rows) == len(report["results"]) == 11
    assert rows["network-demand-conditioned-service"]["status"] == "UNKNOWN"
    assert all(r["status"] == "PASS" for name, r in rows.items() if name != "network-demand-conditioned-service")
    assert report["status"] == "UNKNOWN" and checked["status"] != "CHECKED"
    native = network_validation_evidence(store, state, report, out, "corrected-native")
    try:
        store.accept(project["id"], CANDIDATE, project["revision"], "reject-uncertain-native-bore", checker_version=checker_version())
    except Conflict as exc:
        rejection = str(exc)
    else:
        raise AssertionError("Uncertain fixed-flow candidate was accepted")
    assert original.candidate(CANDIDATE) == candidate
    assert original.project(project["id"]) == project
    assert sha256_file(original.database) == original_db
    assert all(sha256_file(Path(p)) == digest for p, digest in before_assets.items())
    assert all(sha256_file(store.directory / row["copied_path"]) == row["sha256"] for row in inputs["assets"])
    result = {"status": "CORRECTED_SAVED_BYTES_UNKNOWN_AND_ACCEPTANCE_REJECTED", "seconds": time.perf_counter() - started,
        "checker_version": checker_version(), "original_report_root": candidate["report_root"], "corrected_report_root": checked["report_root"],
        "candidate_state_root_unchanged": candidate["state_root"], "original_candidate_status": candidate["status"],
        "corrected_candidate_status": checked["status"], "original_report_status": old_report["status"], "corrected_report_status": report["status"],
        "checks": {name: row["status"] for name, row in rows.items()}, "native": native,
        "execution_evidence_root": execution["evidence_root"], "acceptance_rejection": rejection,
        "original_store_head_candidate_source_export_bytes_unchanged": True,
        "same_geometry_rechecked_without_regeneration": True, "same_original_mission": True,
        "declaration_sha256": sha256_file(out / "declaration.json")}
    atomic_json(out / "result.json", result)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
