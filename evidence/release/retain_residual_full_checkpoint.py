"""Retain exact completed private inputs, outputs and independent audit.

The original runner rejection remains unchanged. This is evidence relocation,
not a test rerun or a replacement for the separate native/package checks.
"""
from pathlib import Path
import hashlib
import json
import shutil


ROOT = Path(__file__).resolve().parents[2]
IDENTITY = "14bff19b88c54779af3d15b1295b5d8b"
ORIGINAL = ROOT / ".oma/development/next-best-fabrication/evidence" / ("full-backend-" + IDENTITY)
OUT = ROOT / "evidence/release" / ("residual-full-backend-" + IDENTITY)
AUDIT = ROOT / "evidence/release/pressure-package-harness-peer-review/private-1abe-completed-audit.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    result = json.loads((ORIGINAL / "result.json").read_text())
    audit = json.loads(AUDIT.read_text())
    assert audit["status"] == "RETAINED_PRIVATE_SUITE_INDEPENDENT_COMPLETION_PASS"
    assert audit["original_result_sha256"] == sha(ORIGINAL / "result.json")
    assert audit["xml"]["passed"] == result["test_node_count"] == 1847
    assert audit["xml"]["failed"] == audit["xml"]["skipped"] == 0
    assert audit["snapshot"]["declared_input_count"] == len(result["snapshot_files"]) == 106
    assert result["returncode"] == 0
    assert result["status"] == "FAIL"
    assert result["error"] == "AssertionError('Unexpected files outside declared test inputs')"
    snapshot = Path(result["test_snapshot"])
    OUT.mkdir(parents=True, exist_ok=False)
    files = {}

    def retain(source, relative, expected=None):
        digest = sha(source)
        if expected is not None:
            assert digest == expected, source
        target = OUT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        assert sha(source) == sha(target) == digest, source
        files[relative] = {"sha256": digest, "bytes": target.stat().st_size}

    for source in sorted(ORIGINAL.iterdir()):
        assert source.is_file(), source
        retain(source, "original/" + source.name)
    retain(AUDIT, "independent-completion-audit.json")
    retain(Path(__file__), "retention-runner.py")
    for relative, digest in sorted(result["snapshot_files"].items()):
        retain(snapshot / relative, "retained-snapshot/" + relative, digest)
    for relative, digest in sorted(audit["snapshot"]["derived_output_sha256"].items()):
        retain(snapshot / relative, "retained-snapshot/" + relative, digest)
    for relative, digest in audit["rederived_identity"]["source_files"].items():
        assert sha(ROOT / "src/oma" / relative) == digest, relative
    assert len(audit["rederived_identity"]["source_files"]) == 99
    nodes = json.loads((ORIGINAL / "test-nodes.json").read_text())
    arguments = OUT / "test-nodes.args"
    arguments.write_text("\n".join(nodes) + "\n", encoding="utf8")
    files["test-nodes.args"] = {"sha256": sha(arguments), "bytes": arguments.stat().st_size}
    manifest = {
        "schema": "oma.retained-completed-regression/1",
        "status": "INDEPENDENT_COMPLETION_PASS",
        "scope": "Original native runtime, exact frozen 1847 cases and 106 inputs; separate package validation required",
        "checker_version": result["checker_version"],
        "passed": 1847, "failures": 0, "skips": 0,
        "pytest_seconds": 692.48,
        "wrapper_seconds": result["seconds"],
        "original_wrapper_status": result["status"],
        "original_wrapper_error": result["error"],
        "accounted_derived_outputs": len(audit["snapshot"]["derived_output_sha256"]),
        "source_files": audit["rederived_identity"]["source_files"],
        "working_source_equal_frozen_at_retention": True,
        "files": files,
        "original_locations": {"evidence": str(ORIGINAL), "test_snapshot": str(snapshot), "audit": str(AUDIT)},
        "raw_evidence_and_snapshot_unchanged": True,
        "test_rerun": False,
    }
    (OUT / "retention.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"status": manifest["status"], "directory": str(OUT), "files": len(files), "passed": 1847, "manifest_sha256": sha(OUT / "retention.json")}))


if __name__ == "__main__":
    main()
