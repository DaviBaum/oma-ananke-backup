"""Read-only evidence inspection plus an isolated summary-validator fault probe."""
import copy
import hashlib
import importlib.util
import itertools
import json
import sqlite3
import sys
import zlib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
CASE = ROOT / "evidence/release/pressure-office-native-recheck-d3e1c124c6604535bd102c7d7fee0698"


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def connection(directory):
    db = sqlite3.connect((directory / "oma.sqlite3").resolve().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


class ReadOnlyBlobs:
    def __init__(self, directory):
        self.directory = directory

    def get(self, root):
        raw = zlib.decompress((self.directory / "blobs" / (root + ".json.z")).read_bytes())
        assert hashlib.sha256(raw).hexdigest() == root
        return json.loads(raw)


def main():
    document = json.loads((CASE / "result.json").read_text())
    result = document["validation"]
    directory = Path(document["isolated_store"])
    original = Path(document["original_store"])
    assert not directory.is_relative_to(original)
    store = ReadOnlyBlobs(directory)
    original_blobs = ReadOnlyBlobs(original)
    db, original_db = connection(directory), connection(original)
    cid = document["candidate_id"]
    candidate = dict(db.execute("SELECT * FROM candidates WHERE id=?", (cid,)).fetchone())
    original_candidate = dict(original_db.execute("SELECT * FROM candidates WHERE id=?", (cid,)).fetchone())
    assert candidate["state_root"] == original_candidate["state_root"] == result["candidate_root"]
    assert candidate["report_root"] == result["report_root"] and candidate["status"] == "CHECKED"
    assert original_candidate["report_root"] == result["prior_report_root"]
    original_report = original_blobs.get(original_candidate["report_root"])
    report = store.get(candidate["report_root"])
    assert report == result["report"]
    assert report["checker_version"] == "oma-independent-checker/2:bac10b7f20d44219f13fe5df2a70600f22b4fe69a4021dbe0e8e2172f76743ac"
    assert original_report["checker_version"] == document["prior_checker_version"]
    state = store.get(candidate["state_root"])
    assert state == original_blobs.get(candidate["state_root"])
    original_head = dict(original_db.execute("SELECT * FROM projects WHERE id=?", (candidate["project_id"],)).fetchone())
    copied_head = dict(db.execute("SELECT * FROM projects WHERE id=?", (candidate["project_id"],)).fetchone())
    assert copied_head == original_head and copied_head["revision"] == 1
    for table in ["runs"]:
        assert dict(db.execute(f"SELECT * FROM {table} WHERE id=?", (candidate["run_id"],)).fetchone()) == dict(original_db.execute(f"SELECT * FROM {table} WHERE id=?", (candidate["run_id"],)).fetchone())
    execution = dict(db.execute("SELECT * FROM check_executions WHERE execution_id=?", (result["execution"]["execution_id"],)).fetchone())
    assert execution["status"] == "COMPLETED" and execution["report_root"] == candidate["report_root"]
    assert result["execution"]["report_published"]
    assert result["execution"]["supervision"]["containment"]["active_processes"] == 0
    assert result["execution"]["supervision"]["containment"]["assigned_before_resume"]
    assert original_report["objective"] == report["objective"]
    checks = {r["id"]: r for r in report["results"]}
    assert len(checks) == len(report["results"]) == 13
    assert all(r["status"] == "PASS" for r in report["results"])
    cad_root = checks["network-all-source-clearance"]["witness"]["artifact"]
    cad = store.get(cad_root)
    semantics = store.get(checks["network-native-semantics"]["witness"]["artifact"])
    pressure = store.get(checks["network-pressure-operating-point"]["witness"]["artifact"])
    for name, value in [("cad", cad), ("semantics", semantics), ("pressure", pressure)]:
        assert json.loads((CASE / ("current-" + name + ".json")).read_text()) == value
    guids = [p["ifc_guid"] for p in semantics["parts"]]
    assert len(guids) == len(set(guids)) == 4
    assert cad["route_count"] == 4 and cad["obstacle_count"] == 803 and cad["pairs_accounted"] == 3212
    actual_pairs = [tuple(sorted(p["participant_guids"])) for p in cad["self_pair_results"]]
    expected_pairs = set(itertools.combinations(sorted(guids), 2))
    assert len(actual_pairs) == len(set(actual_pairs)) == 6 and set(actual_pairs) == expected_pairs
    assert all(p["status"] == "PASS" for p in cad["self_pair_results"])
    assert pressure["independent_check"]["model_root"] != result["prior_network_evidence"]["pressure_model_root"]
    assert pressure["deliveries"] == result["prior_network_evidence"]["deliveries"]
    assert semantics["physical_ports"] == result["network_evidence"]["component_velocity_count"] == 9
    copies = json.loads((directory / "validation-input-copy.json").read_text())
    for asset in copies["assets"]:
        assert sha(asset["original_resolved_path"]) == sha(directory / asset["copied_path"]) == asset["sha256"]
    for path, expected in result["source_and_exported_files"].items():
        assert sha(path) == expected
    assert document["expected_export_sha256"] == cad["export_sha256"] == "c116e3cf909e97719a613888043ca2b214aba538575e17f79dd3639bb5a12e58"
    assert sha(CASE / "native_real_model_validation.py") == document["script_sha256"]

    # This proxy models a malformed summary artifact only. It is not a fresh
    # checker, a published report, a Store hash-bypass exploit, or native proof.
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("reviewed_native_validation", CASE / "native_real_model_validation.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class DuplicatePairProxy:
        def get(self, root):
            value = copy.deepcopy(store.get(root))
            if root == cad_root:
                value["self_pair_results"] = [copy.deepcopy(value["self_pair_results"][0])] * 6
            return value

    probe = OUT / "duplicate-pair-summary-probe"
    probe.mkdir(exist_ok=True)
    returned = module.network_validation_evidence(DuplicatePairProxy(), state, report, probe, "malformed")
    assert returned["complete_native_status"] == "PASS"
    summary = {"status": "RETAINED_NATIVE_RECHECK_VERIFIED_WITH_SUMMARY_VALIDATOR_FINDING", "reviewed_at": datetime.now(timezone.utc).isoformat(), "reviewed_script_sha256": document["script_sha256"], "reviewed_test_sha256": sha(ROOT / "tests/test_native_pressure_model_validation.py"), "retained_result_sha256": sha(CASE / "result.json"), "source_checkpoint": document["source_checkpoint"], "candidate_id": cid, "candidate_root": candidate["state_root"], "current_report_root": candidate["report_root"], "prior_report_root": original_candidate["report_root"], "original_store_read_only": True, "isolated_store": str(directory), "no_geometry_regeneration": True, "expected_export_sha256": document["expected_export_sha256"], "required_checks": len(checks), "native_components": 4, "physical_ports": 9, "original_obstacles": 803, "source_pairs": 3212, "complete_unique_self_pairs": 6, "pressure_model_root_changed": True, "exact_deliveries_preserved": True, "original_head": original_head, "original_run_and_candidate_unchanged": True, "copied_asset_pairs_rehashed": len(copies["assets"]), "findings": [{"id": "SUMMARY-DUPLICATE-PAIR", "scope": "Evidence helper only; actual retained fresh native evidence has all six unique pairs", "reproduction": "Replace six self-pair rows with six copies of the first PASS pair through a read-only test proxy; network_validation_evidence still returns complete_native_status PASS", "missing_pairs": 5, "recommendation": "Require unique unordered participant GUID pairs equal to all combinations of actual unique native part GUIDs; reject duplicate route/component identifier lists too", "ordinary_API_or_fresh_checker_exploit": False}], "compatibility": "Existing default .oma remains supported; explicit original Store is read-only, output is resolved and disjoint, one shared network/no routes is an explicit bounded scope. Same objective/obligation/disposition and distinct checker assertions intentionally reject changed requirements or incomplete historical evidence.", "test_review": "Three new tests exercise actual exported pressure IFC from an explicit Store, incorrect expected IFC hash before checker launch, and missing part/sink/velocity summaries. Together with the four prior tests they cover true managed publication and incomplete-child exclusion; no native rerun performed by this review.", "audit_script_sha256": sha(__file__)}
    (OUT / "review.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    db.close()
    original_db.close()
    print(json.dumps({"status": summary["status"], "path": str(OUT / "review.json"), "sha256": sha(OUT / "review.json")}))


if __name__ == "__main__":
    main()
