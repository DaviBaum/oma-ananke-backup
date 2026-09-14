"""Retain successful correction evidence and exact focused test input bytes."""
from pathlib import Path
import hashlib
import json
import shutil

STAGE = Path(__file__).resolve().parent
ROOT = next(p for p in STAGE.parents if (p / "AGENTS.md").is_file())
OUT = ROOT / "evidence/math/fixed-flow-native-section"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    files = {}
    def retain(original, relative, expected=None):
        digest = sha(original)
        if expected is not None:
            assert digest == expected
        target = OUT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        assert not target.exists()
        shutil.copyfile(original, target)
        assert sha(original) == sha(target) == digest
        files[relative] = {"sha256": digest, "bytes": target.stat().st_size}
    focus = STAGE / "evidence/focused-55b455c289314bf1aba97437be8f7678/result.json"
    result = json.loads(focus.read_text(encoding="utf8"))
    assert result["status"] == "PASS" and result["passed"] == 172
    for relative, digest in result["snapshot_files"].items():
        retain(Path(result["test_snapshot"]) / relative, "focused-inputs/" + relative, digest)
    saved = STAGE / "evidence/saved-byte-recheck-643431c75bc84264a17d339c486273f6"
    checked = json.loads((saved / "independent-completion.json").read_text(encoding="utf8"))
    assert checked["status"] == "SAVED_BYTES_CORRECTED_UNKNOWN_AND_ACCEPTANCE_REJECTED_INDEPENDENT_COMPLETION_PASS"
    for original in saved.rglob("*"):
        relative = original.relative_to(saved)
        if original.is_file() and not {"runtimes", "__pycache__"}.intersection(relative.parts):
            retain(original, "saved-byte-recheck/" + relative.as_posix())
    retain(STAGE / "audit_saved_completion.py", "saved-byte-recheck/audit-completion.py")
    retain(Path(__file__), "retention-correction.py")
    index = {"schema": "oma.fixed-flow-native-section-evidence/1",
        "status": "INTEGRATED_SCOPED_CORRECTION_PASS_FULL_REGRESSION_PENDING",
        "source_checkpoint": result["checker_version"], "focused_tests": 172, "focused_pytest_seconds": 94.10,
        "independent_corner_cases": 128, "correction": "Current per-component native radius uncertainty propagates to bore, area, velocity, Darcy, tee-inlet loss and endpoint kinetic-pressure bounds",
        "original_false_pass": "original/independent-completion.json", "saved_byte_recheck": "saved-byte-recheck/independent-completion.json",
        "saved_ifc_reauthored": False, "native_checks": checked["native"], "acceptance_of_uncertain_service": "REJECTED",
        "full_original_failure_receipts_preserved": True, "native_inner_bore_measured": False,
        "new_pressure_driven_model_changed": False, "legacy_mission_hashes_changed": False,
        "scope": "Prescribed-flow ideal-round tree model under declared loss and native numerical enclosure assumptions; no operating-point or complete physical-model applicability claim",
        "newly_retained_files": files}
    (OUT / "latest.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"status": index["status"], "new_files": len(files), "index_sha256": sha(OUT / "latest.json")}))


if __name__ == "__main__":
    main()
