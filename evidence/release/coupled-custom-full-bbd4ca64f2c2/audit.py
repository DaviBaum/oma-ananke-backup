"""Audit one completed exact custom-native run; never executes application tests."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preparation", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    prepared = args.preparation.resolve()
    output = prepared / "completion.json"
    assert not output.exists(), "Preserve prior completion audit"
    preparation = read(prepared / "preparation.json")
    exit_record = read(prepared / "exit.json")
    assert exit_record["status"] == "WRAPPER_EXIT_OBSERVED" and exit_record["exit_code"] == 0
    result_path = args.result.resolve()
    result = read(result_path)
    assert result["status"] == "CUSTOM_NATIVE_NEW_CHECKPOINT_FULL_SUITE_PASS"
    assert result["source_checkpoint"] == preparation["source_checkpoint"]
    assert result["passed"] == result["test_node_count"] == preparation["expected_full_test_nodes"] == 2467
    assert result["failed"] == result["skipped"] == 0
    for name, expected in preparation["driver_source_files"].items():
        assert sha(ROOT / "scripts" / name) == sha(prepared / "driver-sources" / name) == expected
    assert result["driver_bytes_unchanged"] is True
    assert result["driver_source_files"] == {k: v for k, v in preparation["driver_source_files"].items() if k != "native_checkpoint_audit.py"}
    source = Path(preparation["source_directory"]) / "oma"
    sources = {p.relative_to(source).as_posix(): sha(p) for p in source.rglob("*.py")}
    expected_sources = read(prepared / "source-files.json")
    assert sources == expected_sources and len(sources) == 107
    declared = read(result_path.parent / "declared-test-snapshot.json")
    assert declared["snapshot_files"] == read(prepared / "snapshot-files.json")
    assert declared["source_files"] == sources
    snapshot = read(result_path.parent / "test-source-manifest.json")
    assert snapshot["files"] == declared["snapshot_files"] and len(snapshot["files"]) == 131
    completed_audit = result_path.parent / "post-run-exact-audit.json"
    if not completed_audit.exists():
        command = [str(ROOT / ".venv/Scripts/python.exe"), str(ROOT / "scripts/native_checkpoint_audit.py"), "--result", str(result_path)]
        audit = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=120)
        (prepared / "completion-audit-output.log").write_text(audit.stdout + audit.stderr, encoding="utf-8")
        assert audit.returncode == 0, audit.stdout + audit.stderr
    exact = read(completed_audit)
    assert exact["status"] == "EXISTING_NATIVE_RUN_EXACT_INPUT_NODE_XML_IDENTITY_AUDIT_PASS"
    assert exact["result_sha256"] == sha(result_path)
    assert exact["test_node_count"] == 2467 and exact["test_input_files"] == 131 and exact["source_python_files"] == 107
    assert len(exact["copied_snapshot"]["generated_evidence"]) == 6
    assert exact["tests_rerun"] is False
    identity = read(result_path.parent / "identity-comparison.json")
    assert identity["original"]["source_files"] == identity["candidate"]["source_files"] == sources
    assert identity["original"]["checker_version"] == "oma-independent-checker/2:" + preparation["source_checkpoint"]
    assert identity["candidate"]["checker_version"] == result["runtime"]["OMA_EXECUTABLE_BUILD"]
    assert result["native_extension_sha256"] == preparation["native_extension_sha256"]
    retained = {
        "status": "CUSTOM_NATIVE_EXACT_2467_CASE_COMPLETION_AUDIT_PASS",
        "source_checkpoint": preparation["source_checkpoint"],
        "custom_checker_version": result["runtime"]["OMA_EXECUTABLE_BUILD"],
        "source_files": 107, "test_input_files": 131, "passed": 2467, "failed": 0, "skipped": 0,
        "generated_output_files": 6,
        "result": str(result_path), "result_sha256": sha(result_path),
        "post_run_audit": str(completed_audit), "post_run_audit_sha256": sha(completed_audit),
        "preparation_sha256": sha(prepared / "preparation.json"),
        "wrapper_exit_sha256": sha(prepared / "exit.json"),
        "xml_sha256": result["test_xml_sha256"],
        "native_extension_sha256": result["native_extension_sha256"],
        "seconds": result["seconds"],
        "original_and_custom_application_bytes_equal": True,
        "all_declared_inputs_and_driver_bytes_unchanged": True,
        "tests_rerun": False, "package_built": False,
        "audit_script_sha256": sha(Path(__file__)),
    }
    output.write_text(json.dumps(retained, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"completion": str(output), "sha256": sha(output), "status": retained["status"]}))


if __name__ == "__main__":
    main()
