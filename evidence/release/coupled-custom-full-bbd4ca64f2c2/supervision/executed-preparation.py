"""Prepare an exact custom-native full run; this command never launches tests."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import uuid

STAGE = Path(__file__).resolve().parent
ROOT = STAGE.parents[2]
SOURCE = "5e8fe9659cfde60f84f5cf93f38a1959428b3e7522de741e905d1f505db2b73c"
DECLARATION = ROOT / ".oma/development/coupled-native-integration/evidence/integration-5aa41849e4584b10a4368ede96e8d9cb/result.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--integration-record", type=Path, default=DECLARATION)
    args = parser.parse_args()
    declaration_path = args.integration_record.resolve()
    sys.path.insert(0, str(ROOT / "scripts"))
    from native_package_evidence import verify_test_snapshot
    record = json.loads(declaration_path.read_text())
    assert record["checker_version"] == "oma-independent-checker/2:" + SOURCE
    source = Path(record["source_directory"])
    actual_source = {p.relative_to(source / "oma").as_posix(): sha(p) for p in (source / "oma").rglob("*.py")}
    assert actual_source == record["source_files"] and len(actual_source) == 107
    inventory = verify_test_snapshot(record["test_snapshot"], record["snapshot_files"], allow_generated_evidence=True)
    assert len(inventory["inputs"]) == 131
    wheel_path = ROOT / "evidence/dependencies/native-build/candidate-wheel.json"
    wheel = json.loads(wheel_path.read_text())
    assert Path(wheel["wheel"]).is_file()
    python = ROOT / ".release/native-build/test-venv/Scripts/python.exe"
    assert python.is_file()
    target = STAGE / "prepared" / uuid.uuid4().hex
    target.mkdir(parents=True)
    driver_files = {}
    for name in ("native_validate_checkpoint.py", "native_package_evidence.py", "native_prepare.py", "native_build.py", "native_checkpoint_audit.py"):
        path = ROOT / "scripts" / name
        driver_files[name] = sha(path)
        (target / "driver-sources").mkdir(exist_ok=True)
        shutil.copyfile(path, target / "driver-sources" / name)
    shutil.copyfile(Path(__file__), target / "executed-preparation.py")
    shutil.copyfile(STAGE / "run.ps1", target / "run.ps1")
    (target / "integration-declaration.json").write_bytes(declaration_path.read_bytes())
    (target / "source-files.json").write_text(json.dumps(actual_source, indent=2) + "\n", encoding="utf-8")
    (target / "snapshot-files.json").write_text(json.dumps(inventory["inputs"], indent=2) + "\n", encoding="utf-8")
    result = {
        "status": "PREPARED_NOT_LAUNCHED_AWAITING_ROOT_FULL_SUITE_DECLARATION",
        "source_checkpoint": SOURCE,
        "source_directory": str(source),
        "expected_source_file_count": 107,
        "expected_test_input_count": 131,
        "expected_full_test_nodes": 2467,
        "integration_selected_nodes_not_full_suite": record["test_node_count"],
        "integration_declaration_path": str(declaration_path),
        "integration_declaration_sha256": sha(target / "integration-declaration.json"),
        "test_snapshot": record["test_snapshot"],
        "source_file_manifest_sha256": sha(target / "source-files.json"),
        "test_input_manifest_sha256": sha(target / "snapshot-files.json"),
        "driver_source_files": driver_files,
        "custom_python": str(python),
        "custom_python_sha256": sha(python),
        "native_wheel_record_sha256": sha(wheel_path),
        "native_wheel": wheel["wheel"],
        "native_wheel_sha256": sha(Path(wheel["wheel"])),
        "native_extension_sha256": wheel["variant"]["native_extension_sha256"],
        "wrapper_sha256": sha(target / "run.ps1"),
        "prepared_command": [str(ROOT / ".venv/Scripts/python.exe"), "scripts/native_validate_checkpoint.py", "--source-checkpoint", SOURCE,
            "--source-directory", str(source), "--test-snapshot-record", "<ROOT_FULL_SUITE_RESULT_JSON_WITH_EXACT_2467_NODE_DECLARATION>"],
        "launch_rule": "Root must explicitly announce full-suite start after integration success; wrapper requires exact source/input/node declaration and retained driver bytes before execution",
        "collection_rule": "Validator collects independently under the custom native build and requires exact ordered equality with the root full node manifest",
        "completion_rule": "Completed process exit zero, exact node XML, 107 current source files, 131 unchanged inputs and only the two explicit three-file derived-output families; no guessed pass counts",
        "package_build_started": False,
        "tests_started_by_preparation": False,
    }
    (target / "preparation.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"preparation": str(target / "preparation.json"), "sha256": sha(target / "preparation.json"), "status": result["status"]}))


if __name__ == "__main__":
    main()
