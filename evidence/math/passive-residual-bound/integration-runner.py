"""Integrate only the tested residual delta after both prior full suites finish."""
from pathlib import Path
import hashlib
import json
import shutil
import sys

STAGE = Path(__file__).resolve().parent
ROOT = next(p for p in STAGE.parents if (p / "AGENTS.md").is_file())
PUBLIC = ROOT / "evidence/math/passive-residual-bound"
BEFORE = "oma-independent-checker/2:4044a58d563922530546897240791354f7557e40471f6b4222b23f065f5610ef"
AFTER = "oma-independent-checker/2:ada34434d2576cc5efa07087a04e75a412b64fab439330fe5b71b30f5ca69dcf"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def main():
    sys.path.insert(0, str(ROOT / "src"))
    from oma.build_identity import checker_version
    assert checker_version() == BEFORE
    full_path = ROOT / "evidence/release/passive-tree-full-c4e9176a8a97438d892dccd7779cee99/result.json"
    custom_path = ROOT / "evidence/dependencies/native-build/checkpoint-validation/4044a58d5639-392726a4ae64/result.json"
    full, custom = read(full_path), read(custom_path)
    assert full["status"] == "PASS" and full["passed"] == 2067
    assert custom["status"] == "CUSTOM_NATIVE_NEW_CHECKPOINT_FULL_SUITE_PASS" and custom["passed"] == 2067, custom.get("status")
    latest = read(PUBLIC / "latest.json")
    assert latest["status"] == "PRIVATE_COMBINED_COMPATIBILITY_PASS_AWAITING_PRODUCTION_MERGE"
    focus = read(PUBLIC / "combined-focused/result.json")
    assert focus["status"] == "PASS" and focus["passed"] == 303 and focus["checker_version"] == AFTER
    current = {p.relative_to(ROOT / "src/oma").as_posix(): sha(p) for p in (ROOT / "src/oma").rglob("*.py")}
    assert current == full["source_files"] == focus["base_application_hashes"]
    handoff = read(PUBLIC / "handoff.json")
    assert len(handoff["merge_files"]) == 3
    for row in handoff["merge_files"]:
        source = PUBLIC / "tested-source/oma" / row["path"].removeprefix("src/oma/") if row["path"].startswith("src/oma/") else PUBLIC / "focused-inputs" / row["path"]
        assert sha(source) == row["sha256"]
        assert not (ROOT / row["path"]).exists(), row["path"]
    for row in handoff["merge_files"]:
        source = PUBLIC / "tested-source/oma" / row["path"].removeprefix("src/oma/") if row["path"].startswith("src/oma/") else PUBLIC / "focused-inputs" / row["path"]
        target = ROOT / row["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        assert sha(target) == row["sha256"]
    doc = ROOT / handoff["documentation"]["path"]
    assert not doc.exists()
    shutil.copyfile(PUBLIC / "private-documentation.md", doc)
    assert sha(doc) == handoff["documentation"]["sha256"]
    assert checker_version() == AFTER
    assert {p.relative_to(ROOT / "src/oma").as_posix(): sha(p) for p in (ROOT / "src/oma").rglob("*.py")} == focus["source_files"]
    shutil.copyfile(Path(__file__), PUBLIC / "integration-runner.py")
    latest.update(status="INTEGRATED_FOCUSED_AND_INDEPENDENT_REVIEW_PASS", production_application_modified=True,
        production_merge_blocked_on_existing_full_regression=False, source_after=AFTER,
        previous_full_regression={"original_receipt": full_path.relative_to(ROOT).as_posix(),
            "original_sha256": sha(full_path), "custom_receipt": custom_path.relative_to(ROOT).as_posix(),
            "custom_sha256": sha(custom_path), "cases": 2067},
        current_full_regression="NOT_YET_RUN_ON_NEW_SOURCE", integration_runner_sha256=sha(PUBLIC / "integration-runner.py"))
    (PUBLIC / "latest.json").write_text(json.dumps(latest, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"status": latest["status"], "source_before": BEFORE, "source_after": AFTER, "minimal_merge_files": 3, "focused_tests": 303}))


if __name__ == "__main__":
    main()
