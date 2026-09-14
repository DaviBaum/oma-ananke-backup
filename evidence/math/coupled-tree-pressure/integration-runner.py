"""Retain and integrate exactly the reviewed positive-box kernel and its test."""
from pathlib import Path
import hashlib
import json
import shutil
import sys

STAGE = Path(__file__).resolve().parent
ROOT = next(p for p in STAGE.parents if (p / "AGENTS.md").is_file())
AGENT = ROOT / ".oma/development/coupled-tree-pressure"
PACKAGE = AGENT / "evidence/math/coupled-tree-pressure"
FOCUSED = STAGE / "evidence/integration-a4e0cccd5fde48a3882a29d53ae29b64"
PUBLIC = ROOT / "evidence/math/coupled-tree-pressure"
BEFORE = "oma-independent-checker/2:ada34434d2576cc5efa07087a04e75a412b64fab439330fe5b71b30f5ca69dcf"
AFTER = "oma-independent-checker/2:8f6f5c18b77bb9ef45e7cd3b2c24987a13c822cca706178f0a8d173fc03c1206"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def copy(source, destination, expected=None):
    expected = expected or sha(source)
    assert sha(source) == expected, source
    destination.parent.mkdir(parents=True, exist_ok=True)
    assert not destination.exists(), destination
    shutil.copyfile(source, destination)
    assert sha(source) == sha(destination) == expected


def main():
    sys.path.insert(0, str(ROOT / "src"))
    from oma.build_identity import checker_version
    assert checker_version() == BEFORE
    assert sha(PACKAGE / "handoff.json") == "a0c6db69ed128d2725da044e11bd7da45d62da491e1d73c34dad4f75101c2fc5"
    handoff, focused = read(PACKAGE / "handoff.json"), read(FOCUSED / "result.json")
    assert handoff["tests"] == 124 and handoff["peer_rejected_attacks"] == 293
    assert focused["status"] == "PASS" and focused["passed"] == 427 and focused["checker_version"] == AFTER
    assert focused["frozen_source_unchanged"] and focused["snapshot_unchanged"] and focused["exact_case_identities_checked"]
    assert len(focused["source_files"]) == 104 and len(focused["snapshot_files"]) == 121
    assert sha(FOCUSED / "tests.xml") == focused["test_xml_sha256"]
    current = {p.relative_to(ROOT / "src/oma").as_posix(): sha(p) for p in (ROOT / "src/oma").rglob("*.py")}
    assert current == focused["base_application_hashes"]
    assert set(focused["source_files"]) - set(current) == {"optimization/coupled_tree_pressure.py"}
    assert all(focused["source_files"][k] == v for k, v in current.items())
    contents = read(PACKAGE / "contents.json")
    files = contents["files"]
    rows = files if isinstance(files, list) else [{"path": k, **(v if isinstance(v, dict) else {"sha256": v})} for k, v in files.items()]
    for row in rows:
        copy(PACKAGE / row["path"], PUBLIC / row["path"], row["sha256"])
    for name in ("contents.json", "handoff.json"):
        copy(PACKAGE / name, PUBLIC / name)
    for name in ("result.json", "tests.xml", "test-nodes.json", "runner.py", "inventory-helper.py", "pytest.log", "collection.log"):
        copy(FOCUSED / name, PUBLIC / "combined-focused" / name)
    for relative, expected in focused["source_files"].items():
        copy(Path(focused["source_directory"]) / "oma" / relative, PUBLIC / "tested-source/oma" / relative, expected)
    for relative, expected in focused["snapshot_files"].items():
        copy(Path(focused["test_snapshot"]) / relative, PUBLIC / "focused-inputs" / relative, expected)
    for relative, expected in handoff["merge_files"].items():
        source = PUBLIC / "tested-source/oma" / relative.removeprefix("src/oma/") if relative.startswith("src/oma/") else PUBLIC / "focused-inputs" / relative
        copy(source, ROOT / relative, expected)
    for relative, expected in handoff["docs"].items():
        copy(AGENT / relative, ROOT / relative, expected)
    assert checker_version() == AFTER
    copy(Path(__file__), PUBLIC / "integration-runner.py")
    result = {"schema": "oma.integrated-coupled-tree-pressure/1", "status": "INTEGRATED_FOCUSED_AND_INDEPENDENT_REVIEW_PASS",
        "source_before": BEFORE, "source_after": AFTER, "focused_tests": 427, "focused_pytest_seconds": 31.51,
        "focused_wrapper_seconds": focused["seconds"], "source_python_files": 104, "test_support_files": 121,
        "focused_xml_sha256": focused["test_xml_sha256"], "agent_handoff_sha256": sha(PUBLIC / "handoff.json"),
        "merge_files": handoff["merge_files"], "kernel_tests": 124, "independent_parameter_corners": 4096,
        "independent_peer_models": 24, "independent_peer_exact_instances": 96, "independent_peer_rejected_attacks": 293,
        "full_source_algorithms_complete": False, "native_adapter_integrated": False, "current_full_regression": "NOT_YET_RUN_ON_NEW_SOURCE",
        "scope": handoff["scope"], "retained_files": {p.relative_to(PUBLIC).as_posix(): {"sha256": sha(p), "bytes": p.stat().st_size}
            for p in PUBLIC.rglob("*") if p.is_file()}}
    (PUBLIC / "latest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    print(json.dumps({k: result[k] for k in ("status", "source_after", "focused_tests", "source_python_files", "test_support_files")}))


if __name__ == "__main__":
    main()
