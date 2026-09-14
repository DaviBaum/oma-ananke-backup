"""Preserve the completed slow-control regression and its honest no-report exits."""
from pathlib import Path
import hashlib
import json
import shutil
import sqlite3

STAGE = Path(__file__).resolve().parent
ROOT = next(p for p in STAGE.parents if (p / "AGENTS.md").is_file())
SOURCE = STAGE / "evidence/integration-e5cc911be3384e4ebd8ad00e6a485fb9"
TARGET = ROOT / "evidence/math/passive-native-tree/initial-control-timeouts"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy(source, target, expected=None):
    value = sha(source)
    if expected is not None:
        assert value == expected
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    assert sha(source) == sha(target) == value


def main():
    result = json.loads((SOURCE / "result.json").read_text(encoding="utf8"))
    assert result["status"] == "FAIL" and result["passed"] == 252 and result["failed"] == 4 and result["skipped"] == 0
    assert result["inputs_unchanged"] and result["source_unchanged"] and result["exact_case_identities_checked"]
    TARGET.mkdir(parents=True, exist_ok=False)
    for name in ("result.json", "tests.xml", "test-nodes.json", "runner.py", "pytest.log", "collection.log"):
        copy(SOURCE / name, TARGET / name)
    for relative, expected in result["snapshot_files"].items():
        copy(Path(result["test_snapshot"]) / relative, TARGET / "test-inputs" / relative, expected)
    for relative, expected in result["source_files"].items():
        copy(Path(result["source_directory"]) / "oma" / relative, TARGET / "tested-source/oma" / relative, expected)
    temp = Path("C:/Users/Davi/AppData/Local/Temp/pytest-of-Davi/pytest-304")
    names = ["test_native_three_sink_pressur0", *["test_valid_native_geometry_and" + str(i) for i in range(3)]]
    outcomes = {}
    for name in names:
        origin = temp / name
        with sqlite3.connect((origin / "store/oma.sqlite3").as_uri() + "?mode=ro", uri=True) as db:
            db.row_factory = sqlite3.Row
            candidates = [dict(r) for r in db.execute("SELECT id,status,state_root,report_root FROM candidates")]
            executions = [dict(r) for r in db.execute("SELECT execution_id,status,report_root FROM check_executions")]
        assert len(candidates) == len(executions) == 1
        assert candidates[0]["report_root"] is None and executions[0]["report_root"] is None
        records = list((origin / "store/checks/candidate-executions").glob("*/execution.json"))
        assert len(records) == 1
        receipt = json.loads(records[0].read_text(encoding="utf8"))
        assert receipt["status"] == "UNKNOWN_TIMEOUT" and receipt["report_published"] is False
        assert receipt["supervision"]["termination"]["active_processes_after"] == 0
        outcomes[name] = {"candidates": candidates, "executions": executions,
            "elapsed_seconds": receipt["supervision"]["elapsed_seconds"], "no_report_published": True,
            "process_tree_terminated": True, "original_directory": str(origin)}
        for path in origin.rglob("*"):
            relative = path.relative_to(origin)
            if not path.is_file() or {"runtimes", "__pycache__", ".pytest_cache"}.intersection(relative.parts):
                continue
            copy(path, TARGET / "native-workflows" / name / relative)
    copy(Path(__file__), TARGET / "retain.py")
    manifest = {"status": "FOUR_NATIVE_CONTROL_TIMEOUTS_AND_NO_REPORT_EXITS_RETAINED",
        "original_result_sha256": sha(TARGET / "result.json"), "cases": outcomes,
        "explanation": "Forced SQLite control reads on every arithmetic checkpoint exhausted the unchanged 90-second budgets. Test helpers then raised while attempting to read absent report roots. No candidate passed, report published or engineering result inferred.",
        "correction": "Only hot arithmetic uses existing bounded control polling; forced start/end boundaries remain. The corrected 267-case suite passes, including native final-boundary cancellation.",
        "tests_rerun_for_retention": False,
        "files": {p.relative_to(TARGET).as_posix(): {"sha256": sha(p), "bytes": p.stat().st_size} for p in TARGET.rglob("*") if p.is_file()}}
    (TARGET / "retention.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"status": manifest["status"], "cases": len(outcomes), "files": len(manifest["files"])}))


if __name__ == "__main__":
    main()
