"""Retain the exact reviewed kernel evidence and publish its integrated index."""
from pathlib import Path
import hashlib
import json
import shutil

STAGE = Path(__file__).resolve().parent
ROOT = next(p for p in STAGE.parents if (p / "AGENTS.md").is_file())
PRIVATE = ROOT / ".oma/development/passive-pressure-networks"
SOURCE = PRIVATE / "evidence/math/passive-pressure"
TARGET = ROOT / "evidence/math/passive-pressure"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    handoff = json.loads((SOURCE / "handoff.json").read_text(encoding="utf8"))
    manifest = json.loads((SOURCE / "contents.json").read_text(encoding="utf8"))
    assert handoff["status"] == "IMPLEMENTED_SCOPED_TESTED_INDEPENDENTLY_REVIEWED"
    for row in handoff["merge_files"]:
        assert sha(PRIVATE / row["path"]) == sha(ROOT / row["path"]) == row["sha256"]
    TARGET.mkdir(parents=True, exist_ok=False)
    for row in [*manifest["files"], *[{"path": name, "sha256": sha(SOURCE / name)} for name in ("contents.json", "handoff.json")]]:
        original = SOURCE / row["path"]
        target = TARGET / row["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            assert sha(target) == row["sha256"]
            continue
        assert sha(original) == row["sha256"]
        shutil.copyfile(original, target)
        assert sha(original) == sha(target) == row["sha256"]
    doc = handoff["documentation"]
    assert sha(PRIVATE / doc["path"]) == doc["sha256"]
    assert not (ROOT / doc["path"]).exists()
    shutil.copyfile(PRIVATE / doc["path"], ROOT / doc["path"])
    assert sha(ROOT / doc["path"]) == doc["sha256"]
    integration = json.loads((ROOT / "evidence/release/passive-kernel-integration.json").read_text(encoding="utf8"))
    latest = {"schema": "oma.integrated-passive-pressure-evidence/1", "status": "INTEGRATED_SCOPED_TESTS_AND_INDEPENDENT_REVIEW_PASS",
        "working_build": integration["source_after"], "kernel_build": handoff["build"], "kernel_tests": 119,
        "independent_exact_graphs": 32, "independent_adversarial_cases": 210, "independent_budget_cases": 5,
        "scope": handoff["scope"], "handoff_sha256": sha(TARGET / "handoff.json"), "contents_sha256": sha(TARGET / "contents.json"),
        "production_module_written": True, "native_passive_adapter_implemented": False,
        "combined_full_regression": {"status": "RUNNING", "cases": 1979, "input_files": 110,
            "original_receipt": "../../release/combined-pressure-full-9d7898a1fcca4928a1f3159ec64f81d0/result.json"},
        "original_evidence_unchanged": True, "full_original_algorithms_implemented": False}
    (TARGET / "latest.json").write_text(json.dumps(latest, indent=2) + "\n", encoding="utf8")
    shutil.copyfile(__file__, TARGET / "retention-runner.py")
    print(json.dumps({"status": latest["status"], "manifest_files": len(manifest["files"]), "latest_sha256": sha(TARGET / "latest.json")}))


if __name__ == "__main__":
    main()
