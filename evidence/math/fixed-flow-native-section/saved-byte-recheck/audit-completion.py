"""Audit completed saved-byte recheck without repeating its native execution."""
from pathlib import Path
import json
import shutil
import sys

STAGE = Path(__file__).resolve().parent
ROOT = next(p for p in STAGE.parents if (p / "AGENTS.md").is_file())
sys.path[:0] = [str(STAGE / "src"), str(STAGE), str(ROOT / "scripts")]
from oma.build_identity import checker_version
from oma.ifc.audit import sha256_file, atomic_json
from oma.store import Store, IntegrityError
from recheck_saved_counterexample import Original, CANDIDATE
from native_real_model_validation import network_validation_evidence

OUT = STAGE / "evidence/saved-byte-recheck-643431c75bc84264a17d339c486273f6"


def main():
    declared = json.loads((OUT / "declaration.json").read_text(encoding="utf8"))
    assert sha256_file(STAGE / "recheck_saved_counterexample.py") == declared["script_sha256"]
    shutil.copyfile(STAGE / "recheck_saved_counterexample.py", OUT / "original-runner.py")
    (OUT / "wrapper-failure.txt").write_text("Fresh native check completed with UNKNOWN service and unchanged geometry. Acceptance was correctly rejected by Store.IntegrityError('Candidate has no complete passing independent report'); wrapper expected Store.Conflict. Original completed native evidence retained without rerun.\n", encoding="utf8")
    original = Original()
    store = Store(OUT / "isolated-store")
    candidate = store.candidate(CANDIDATE)
    report = store.get(candidate["report_root"])
    state = store.get(candidate["state_root"])
    assert candidate == json.loads((OUT / "corrected-candidate.json").read_text(encoding="utf8"))
    assert report == json.loads((OUT / "corrected-report.json").read_text(encoding="utf8"))
    rows = {row["id"]: row for row in report["results"]}
    assert len(rows) == len(report["results"]) == 11
    assert rows["network-demand-conditioned-service"]["status"] == report["status"] == "UNKNOWN"
    assert all(row["status"] == "PASS" for name, row in rows.items() if name != "network-demand-conditioned-service")
    native = network_validation_evidence(store, state, report, OUT, "audit-native", retain=False)
    try:
        store.accept(declared["project"]["id"], CANDIDATE, declared["project"]["revision"], "verify-uncertain-section-rejection", checker_version=checker_version())
    except IntegrityError as exc:
        assert str(exc) == "Candidate has no complete passing independent report"
        rejection = str(exc)
    else:
        raise AssertionError("Uncertain fixed-flow candidate accepted")
    assert original.candidate(CANDIDATE) == declared["candidate"]
    assert original.project(declared["project"]["id"]) == declared["project"]
    assert sha256_file(original.database) == declared["original_database_sha256"]
    assert candidate["state_root"] == declared["candidate"]["state_root"]
    assert state == original.get(declared["candidate"]["state_root"])
    inputs = json.loads((store.directory / "validation-input-copy.json").read_text(encoding="utf8"))
    for row in inputs["assets"]:
        assert sha256_file(Path(row["original_resolved_path"])) == row["sha256"]
        assert sha256_file(store.directory / row["copied_path"]) == row["sha256"]
    execution_file, = (store.directory / "checks/candidate-executions").glob("*/execution.json")
    execution = json.loads(execution_file.read_text(encoding="utf8"))
    assert execution["status"] == "COMPLETED" and execution["report_published"]
    assert execution["report_root"] == candidate["report_root"]
    result = {"status": "SAVED_BYTES_CORRECTED_UNKNOWN_AND_ACCEPTANCE_REJECTED_INDEPENDENT_COMPLETION_PASS",
        "checker_version": checker_version(), "original_report_root": declared["candidate"]["report_root"],
        "corrected_report_root": candidate["report_root"], "candidate_state_root_unchanged": candidate["state_root"],
        "original_report_status": "PASS", "corrected_report_status": report["status"], "checks": {name: row["status"] for name, row in rows.items()},
        "native": native, "execution_evidence_root": execution["evidence_root"], "execution_file_sha256": sha256_file(execution_file),
        "acceptance_rejection": rejection, "original_store_head_candidate_source_export_bytes_unchanged": True,
        "same_geometry_rechecked_without_regeneration": True, "same_original_mission": True, "native_execution_repeated": False,
        "initial_wrapper_exception_type_mismatch_retained": True, "audit_script_sha256": sha256_file(__file__)}
    atomic_json(OUT / "independent-completion.json", result)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
