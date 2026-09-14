"""Retain exact completed combined regression inputs without rerunning tests."""
from pathlib import Path
import hashlib
import importlib.util
import json
import shutil

STAGE = Path(__file__).resolve().parent
ROOT = next(p for p in STAGE.parents if (p / "AGENTS.md").is_file())
OUT = ROOT / "evidence/release/passive-tree-full-c4e9176a8a97438d892dccd7779cee99"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    result = json.loads((OUT / "result.json").read_text(encoding="utf8"))
    assert result["status"] == "PASS" and result["passed"] == 2067
    assert result["snapshot_unchanged"] and result["frozen_source_unchanged"] and result["exact_case_identities_checked"]
    source = Path(result["source_directory"]) / "oma"
    assert {p.relative_to(source).as_posix(): sha(p) for p in source.rglob("*.py")} == result["source_files"]
    assert len(result["source_files"]) == 102 and len(result["snapshot_files"]) == 118
    assert sha(OUT / "tests.xml") == result["test_xml_sha256"]
    assert sha(OUT / "inventory-helper.py") == result["inventory_helper_sha256"]
    spec = importlib.util.spec_from_file_location("retained_inventory", OUT / "inventory-helper.py")
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    nodes = json.loads((OUT / "test-nodes.json").read_text(encoding="utf8"))
    xml = audit.account_xml(OUT / "tests.xml", nodes)
    original = Path(result["test_snapshot"])
    checked = audit.snapshot(original, result["snapshot_files"])
    assert checked["derived_output_sha256"] == result["derived_test_outputs"] and len(result["derived_test_outputs"]) == 6
    retained = OUT / "retained-snapshot"
    retained.mkdir(exist_ok=False)
    for relative, expected in {**result["snapshot_files"], **result["derived_test_outputs"]}.items():
        src, dst = original / relative, retained / relative
        assert sha(src) == expected
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        assert sha(dst) == expected
    assert audit.snapshot(retained, result["snapshot_files"])["derived_output_sha256"] == result["derived_test_outputs"]
    shutil.copyfile(__file__, OUT / "retain-inputs.py")
    record = {"status": "COMPLETED_COMBINED_FULL_REGRESSION_EXACT_INPUTS_RETAINED",
        "checker_version": result["checker_version"], "source_python_files": 102,
        "input_files": 118, "derived_files": 6, "test_nodes": len(nodes), "passed": xml["passed"],
        "completed_result_sha256": sha(OUT / "result.json"), "test_xml_sha256": sha(OUT / "tests.xml"),
        "snapshot_files": result["snapshot_files"], "derived_files_sha256": result["derived_test_outputs"],
        "retained_snapshot": retained.relative_to(ROOT).as_posix(), "retention_script_sha256": sha(OUT / "retain-inputs.py"),
        "tests_rerun": False, "packaging_guard_tests_are_separate": True}
    (OUT / "retention.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf8")
    print(json.dumps({k: record[k] for k in ("status", "input_files", "derived_files", "passed", "tests_rerun")}))


if __name__ == "__main__":
    main()
