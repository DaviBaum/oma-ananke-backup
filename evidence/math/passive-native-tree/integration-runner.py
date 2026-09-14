"""Integrate exactly the independently reviewed and natively tested checkpoint."""
from pathlib import Path
import hashlib
import json
import shutil
import sqlite3
import sys

STAGE = Path(__file__).resolve().parent
ROOT = next(p for p in STAGE.parents if (p / "AGENTS.md").is_file())
sys.path.insert(0, str(ROOT / "src"))
from oma.build_identity import checker_version

BUILD = "oma-independent-checker/2:4044a58d563922530546897240791354f7557e40471f6b4222b23f065f5610ef"
FOCUSED = STAGE / "evidence/integration-ce41d25462dd482584555e5377333548"
PUBLIC = ROOT / "evidence/math/passive-native-tree"
OWNED = ("routing/network_scenario.py", "routing/network_checker.py", "routing/selection.py",
    "routing/network_export.py", "project_assurance.py", "routing/passive_tree_pressure.py", "routing/passive_tree_scenario.py")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def copy(source, target, expected=None):
    before = sha(source)
    if expected is not None:
        assert before == expected
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    assert sha(source) == sha(target) == before


def main():
    before = checker_version()
    assert before == "oma-independent-checker/2:52bd5d29217117127da6dc0576a1626c8512ae7e145132ba9f9ef7b8ed12ea52"
    focused = read(FOCUSED / "result.json")
    assert focused["status"] == "PASS" and focused["passed"] == 267 and focused["checker_version"] == BUILD
    snapshot, frozen = Path(focused["test_snapshot"]), Path(focused["source_directory"]) / "oma"
    assert len(focused["snapshot_files"]) == 118 and len(focused["source_files"]) == 102
    assert sha(FOCUSED / "tests.xml") == focused["test_xml_sha256"]
    expected = focused["source_files"]
    current = {p.relative_to(ROOT / "src/oma").as_posix(): sha(p) for p in (ROOT / "src/oma").rglob("*.py")}
    assert set(current) <= set(expected)
    assert {name for name, value in expected.items() if current.get(name) != value} == set(OWNED)
    agent_public = STAGE / "evidence/math/passive-native-tree"
    handoff = read(agent_public / "handoff.json")
    assert handoff["status"] == "PRIVATE_ADAPTER_TESTED_AND_INDEPENDENTLY_REVIEWED"
    for row in handoff["agent_owned_merge_files"]:
        source = frozen.parent / row["path"].removeprefix("src/") if row["path"].startswith("src/") else snapshot / row["path"]
        assert sha(source) == row["sha256"]
    PUBLIC.mkdir(parents=True, exist_ok=False)
    for row in [*read(agent_public / "contents.json")["files"], *[{"path": n, "sha256": sha(agent_public / n)} for n in ("contents.json", "handoff.json")]]:
        copy(agent_public / row["path"], PUBLIC / row["path"], row["sha256"])
    for name in ("result.json", "tests.xml", "test-nodes.json", "runner.py", "pytest.log", "collection.log"):
        copy(FOCUSED / name, PUBLIC / "integrated-focused" / name)
    for relative, value in focused["snapshot_files"].items():
        copy(snapshot / relative, PUBLIC / "focused-inputs" / relative, value)
    for relative, value in expected.items():
        copy(frozen / relative, PUBLIC / "tested-source/oma" / relative, value)
    # The completed native tests use real private Stores and real exported IFC.
    # Capture their byte closure before pytest's later cleanup can remove it.
    temp = Path("C:/Users/Davi/AppData/Local/Temp/pytest-of-Davi/pytest-305")
    names = ["test_native_three_sink_pressur0", "test_final_forced_control_reje0"]
    names += [p.name for p in temp.iterdir() if p.is_dir() and p.name.startswith("test_valid_native_geometry_and")]
    assert len(names) == len(set(names)) == 5, names
    workflows, locators = {}, {}
    for name in names:
        origin = temp / name
        dbpath = origin / "store/oma.sqlite3"
        with sqlite3.connect(dbpath.as_uri() + "?mode=ro", uri=True) as db:
            db.row_factory = sqlite3.Row
            candidates = [dict(r) for r in db.execute("SELECT id,status,state_root,report_root FROM candidates")]
            runs = [dict(r) for r in db.execute("SELECT id,status FROM runs")]
        assert candidates and all(c["report_root"] for c in candidates)
        assert {c["status"] for c in candidates} <= {"CHECKED", "ACCEPTED", "REJECTED"}
        for path in origin.rglob("*"):
            relative = path.relative_to(origin)
            if not path.is_file() or {"runtimes", "__pycache__", ".pytest_cache"}.intersection(relative.parts):
                continue
            destination = PUBLIC / "native-workflows" / name / relative
            copy(path, destination)
            locators[str(path)] = destination.relative_to(PUBLIC).as_posix()
        workflows[name] = {"candidates": candidates, "runs": runs, "original_directory": str(origin)}
    for relative in OWNED:
        copy(frozen / relative, ROOT / "src/oma" / relative, expected[relative])
    old_inputs = read(ROOT / "evidence/release/combined-pressure-full-9d7898a1fcca4928a1f3159ec64f81d0/result.json")["snapshot_files"]
    test_added = set(focused["snapshot_files"]) - set(old_inputs)
    assert len(test_added) == 8
    for relative in test_added:
        assert not (ROOT / relative).exists()
        copy(snapshot / relative, ROOT / relative, focused["snapshot_files"][relative])
    doc = handoff["documentation"]
    copy(STAGE / doc["path"], ROOT / doc["path"], doc["sha256"])
    assert checker_version() == BUILD
    copy(Path(__file__), PUBLIC / "integration-runner.py")
    result = {"schema": "oma.integrated-passive-native-tree/1", "status": "INTEGRATED_NATIVE_FOCUSED_AND_INDEPENDENT_REVIEW_PASS",
        "source_before": before, "source_after": BUILD, "merged_application_files": list(OWNED), "added_test_files": sorted(test_added),
        "focused_tests": 267, "focused_pytest_seconds": 102.19, "focused_input_files": 118, "application_files": 102,
        "focused_xml_sha256": focused["test_xml_sha256"], "agent_handoff_sha256": sha(PUBLIC / "handoff.json"),
        "native_workflows": workflows, "full_regression": "PENDING", "original_missions_reinterpreted": False,
        "full_source_algorithms_complete": False, "known_initial_native_polling_timeout_retained": str(STAGE / "evidence/integration-e5cc911be3384e4ebd8ad00e6a485fb9"),
        "scope": "Explicit common-outlet positive-loss native pressure trees; model-conditional forward service, current geometry and fresh export checks"}
    (PUBLIC / "native-workflow-locator.json").write_text(json.dumps(locators, indent=2) + "\n", encoding="utf8")
    result["retained_files"] = {p.relative_to(PUBLIC).as_posix(): {"sha256": sha(p), "bytes": p.stat().st_size}
        for p in PUBLIC.rglob("*") if p.is_file()}
    (PUBLIC / "latest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    print(json.dumps({k: result[k] for k in ("status", "source_after", "focused_tests", "focused_input_files", "application_files")}))


if __name__ == "__main__":
    main()
