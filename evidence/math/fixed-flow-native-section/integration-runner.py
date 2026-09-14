"""Integrate only independently reviewed fixed-flow source and focused tests."""
from pathlib import Path
import hashlib
import json
import shutil
import sys

STAGE = Path(__file__).resolve().parent
ROOT = next(p for p in STAGE.parents if (p / "AGENTS.md").is_file())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    before = json.loads((STAGE / "base-source.json").read_text(encoding="utf8"))
    actual = {p.relative_to(ROOT / "src").as_posix(): sha(p) for p in (ROOT / "src/oma").rglob("*.py")}
    assert before == actual
    result_path = STAGE / "evidence/focused-55b455c289314bf1aba97437be8f7678/result.json"
    result = json.loads(result_path.read_text(encoding="utf8"))
    assert result["status"] == "PASS" and result["passed"] == 172 and result["snapshot_unchanged"]
    peer_root = ROOT / ".oma/development/passive-pressure-networks"
    peer = json.loads((peer_root / "evidence/fixed-flow-review/result.json").read_text(encoding="utf8"))
    frozen = STAGE / "runtimes/4f524101a53fe75c2dedd741b1e2aa9cb4390139ffcd9622a17764ed43a380cc/src"
    proposed = {p.relative_to(STAGE / "src").as_posix(): sha(p) for p in (STAGE / "src/oma").rglob("*.py")}
    changed = {k: {"before": before[k], "after": v} for k, v in proposed.items() if before.get(k) != v}
    assert set(changed) == {"oma/routing/network_flow.py", "oma/routing/network_checker.py"}
    for relative, row in changed.items():
        assert sha(frozen / relative) == row["after"]
        shutil.copyfile(STAGE / "src" / relative, ROOT / "src" / relative)
        assert sha(ROOT / "src" / relative) == row["after"]
    tests = {}
    for name in ("test_network_scenario.py", "test_fixed_flow_native_section.py"):
        source = STAGE / "tests" / name
        assert sha(source) == result["snapshot_files"]["tests/" + name]
        shutil.copyfile(source, ROOT / "tests" / name)
        tests[name] = sha(ROOT / "tests" / name)
    out = ROOT / "evidence/math/fixed-flow-native-section"
    for prefix, source in (("focused-55b455c289314bf1aba97437be8f7678", result_path.parent),
                           ("independent-review", peer_root / "evidence/fixed-flow-review")):
        target = out / prefix
        target.mkdir(exist_ok=False)
        for original in source.iterdir():
            assert original.is_file(), original
            shutil.copyfile(original, target / original.name)
            assert sha(original) == sha(target / original.name)
    shutil.copyfile(peer_root / "scripts/review_fixed_flow_sections.py", out / "independent-review/reproduce.py")
    shutil.copyfile(__file__, out / "integration-runner.py")
    integration = {"status": "INTEGRATED_FOCUSED_TESTS_PASS_FULL_REGRESSION_PENDING",
        "source_before": "oma-independent-checker/2:1abe9a077844a184ec17e1c8a0a390aa4bf33d05dd302a6eefff7d770a0ff719",
        "source_after": result["checker_version"], "changes": changed, "test_files": tests,
        "focused_passed": 172, "focused_pytest_seconds": 94.10, "focused_result_sha256": sha(result_path),
        "independent_review_sha256": sha(peer_root / "evidence/fixed-flow-review/result.json"),
        "native_source_applicability": "Native ideal-bore enclosure, with physical wall/transition/catalog assumptions explicit",
        "legacy_mission_hashes_changed": False, "new_pressure_driven_mode_changed": False,
        "private_evidence_unchanged": True, "full_backend_or_package_pass_claim": False}
    (out / "integration.json").write_text(json.dumps(integration, indent=2) + "\n", encoding="utf8")
    print(json.dumps(integration, indent=2))


if __name__ == "__main__":
    main()
