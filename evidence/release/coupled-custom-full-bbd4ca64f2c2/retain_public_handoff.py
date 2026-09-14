"""Retain completed custom-native supervision and exact evidence closure."""
from hashlib import sha256
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[3]


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def inventory(directory):
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(directory.rglob("*")) if p.is_file()}


def main():
    source = ROOT / ".oma/development/coupled-custom-validation/prepared/1b5cc5fcc3954014a498296d58df76ef"
    completion = json.loads((source / "completion.json").read_text())
    assert completion["status"] == "CUSTOM_NATIVE_EXACT_2467_CASE_COMPLETION_AUDIT_PASS"
    out = ROOT / "evidence/release/coupled-custom-full-bbd4ca64f2c2"
    assert not out.exists()
    out.mkdir(parents=True)
    shutil.copytree(source, out / "supervision")
    for name in ("audit.py", "retain_public_handoff.py"):
        shutil.copyfile(Path(__file__).parent / name, out / name)
    checkpoint = ROOT / "evidence/dependencies/native-build/checkpoint-validation/5e8fe9659cfd-bbd4ca64f2c2"
    commands = [ROOT / "evidence/dependencies/native-build/commands" / name for name in
                ("checkpoint-test-collection-652517d323", "checkpoint-full-suite-e47bebbd90")]
    result = {
        "status": "COMPLETED_CUSTOM_NATIVE_2467_TEST_EVIDENCE_HANDOFF",
        "source_checkpoint": completion["source_checkpoint"],
        "custom_checker_version": completion["custom_checker_version"],
        "passed": 2467, "failed": 0, "skipped": 0,
        "source_files": 107, "test_input_files": 131, "generated_output_files": 6,
        "pytest_command_seconds": 770.4600221000001,
        "driver_seconds": completion["seconds"],
        "test_xml_sha256": completion["xml_sha256"],
        "native_extension_sha256": completion["native_extension_sha256"],
        "checkpoint_directory": checkpoint.relative_to(ROOT).as_posix(),
        "checkpoint_files": inventory(checkpoint),
        "command_directories": [p.relative_to(ROOT).as_posix() for p in commands],
        "command_files": {k: v for p in commands for k, v in inventory(p).items()},
        "supervision_files": inventory(out),
        "original_full_receipt": "evidence/release/coupled-tree-full-17ea63bc503a4b78bb572ffee1dce06f/result.json",
        "scope": "Exact completed original/custom-native application compatibility; independent packet remains a later package validation task",
        "tests_rerun": False,
        "package_build_completed": False,
    }
    target = out / "completed-handoff.json"
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"handoff": target.relative_to(ROOT).as_posix(), "sha256": sha(target)}))


if __name__ == "__main__":
    main()
