"""Retain the exact completed private merge without changing application files."""
from pathlib import Path
import hashlib
import json
import shutil

STAGE = Path(__file__).resolve().parent
ROOT = next(p for p in STAGE.parents if (p / "AGENTS.md").is_file())
AGENT = ROOT / ".oma/development/passive-residual-bound"
FOCUSED = STAGE / "evidence/integration-98356ee06355401b826b4a1eb3f1e43a"
PUBLIC = ROOT / "evidence/math/passive-residual-bound"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def copy(source, target, expected=None):
    expected = expected or sha(source)
    assert sha(source) == expected
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        assert sha(target) == expected
    else:
        shutil.copyfile(source, target)
    assert sha(target) == expected


def main():
    source = AGENT / "evidence/math/passive-residual-bound"
    assert sha(source / "handoff.json") == "c34419e0049921668ba52acdda996501caa297b043059d56d1509ecb0db28c00"
    assert sha(source / "contents.json") == "a8dd89550d1f2ad33a819dcb7fac83b0de9aa2b36131433707af3466d9eada67"
    handoff = read(source / "handoff.json")
    focus = read(FOCUSED / "result.json")
    assert focus["status"] == "PASS" and focus["passed"] == 303
    assert focus["snapshot_unchanged"] and focus["frozen_source_unchanged"] and focus["exact_case_identities_checked"]
    assert focus["checker_version"] == "oma-independent-checker/2:ada34434d2576cc5efa07087a04e75a412b64fab439330fe5b71b30f5ca69dcf"
    assert len(focus["source_files"]) == 103 and len(focus["snapshot_files"]) == 120
    assert sha(FOCUSED / "tests.xml") == focus["test_xml_sha256"]
    for row in read(source / "contents.json")["files"]:
        copy(source / row["path"], PUBLIC / row["path"], row["sha256"])
    for name in ("contents.json", "handoff.json"):
        copy(source / name, PUBLIC / name)
    for name in ("result.json", "tests.xml", "test-nodes.json", "runner.py", "inventory-helper.py", "pytest.log", "collection.log"):
        copy(FOCUSED / name, PUBLIC / "combined-focused" / name)
    for relative, expected in focus["source_files"].items():
        copy(Path(focus["source_directory"]) / "oma" / relative, PUBLIC / "tested-source/oma" / relative, expected)
    for relative, expected in focus["snapshot_files"].items():
        copy(Path(focus["test_snapshot"]) / relative, PUBLIC / "focused-inputs" / relative, expected)
    doc = handoff["documentation"]
    copy(AGENT / doc["path"], PUBLIC / "private-documentation.md", doc["sha256"])
    copy(Path(__file__), PUBLIC / "retain-private.py")
    result = {"schema": "oma.passive-residual-integration/1", "status": "PRIVATE_COMBINED_COMPATIBILITY_PASS_AWAITING_PRODUCTION_MERGE",
        "production_application_modified": False, "source_before": "oma-independent-checker/2:4044a58d563922530546897240791354f7557e40471f6b4222b23f065f5610ef",
        "tested_combined_source": focus["checker_version"], "focused_tests": 303, "focused_pytest_seconds": 33.60,
        "source_files": 103, "test_support_files": 120, "focused_xml_sha256": focus["test_xml_sha256"],
        "agent_handoff_sha256": sha(PUBLIC / "handoff.json"), "independent_review": handoff["independent_review"],
        "merge_files": handoff["merge_files"], "production_merge_blocked_on_existing_full_regression": True,
        "full_source_algorithms_complete": False, "scope": handoff["scope"],
        "retained_files": {p.relative_to(PUBLIC).as_posix(): {"sha256": sha(p), "bytes": p.stat().st_size}
            for p in PUBLIC.rglob("*") if p.is_file() and p.name != "latest.json"}}
    (PUBLIC / "latest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    print(json.dumps({k: result[k] for k in ("status", "tested_combined_source", "focused_tests", "source_files", "test_support_files")}))


if __name__ == "__main__":
    main()
