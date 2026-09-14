"""Retain all original native counterexample bytes except redundant runtimes."""
from pathlib import Path
import hashlib
import json
import shutil

STAGE = Path(__file__).resolve().parent
ROOT = next(p for p in STAGE.parents if (p / "AGENTS.md").is_file())
SOURCE = STAGE / "evidence/df84bdb223ee49a5a5faa33b975a9580"
TARGET = ROOT / "evidence/math/fixed-flow-native-section/original"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    result = json.loads((SOURCE / "independent-completion.json").read_text())
    assert result["status"] == "NATIVE_FIXED_FLOW_FALSE_VELOCITY_PASS_REPRODUCED"
    TARGET.mkdir(parents=True, exist_ok=False)
    files = {}
    for original in sorted(SOURCE.rglob("*")):
        relative = original.relative_to(SOURCE)
        if not original.is_file() or {"runtimes", "__pycache__"}.intersection(relative.parts):
            continue
        target = TARGET / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        expected = sha(original)
        shutil.copyfile(original, target)
        assert sha(original) == sha(target) == expected
        files[relative.as_posix()] = {"sha256": expected, "bytes": target.stat().st_size}
    shutil.copyfile(__file__, TARGET / "retention-runner.py")
    files["retention-runner.py"] = {"sha256": sha(TARGET / "retention-runner.py"), "bytes": Path(__file__).stat().st_size}
    manifest = {"status": "ORIGINAL_FALSE_PASS_RETAINED_CORRECTION_IN_PROGRESS", "source_directory": str(SOURCE),
        "scope": "Exact native IFC, report, candidate and Store artifact bytes; relocated absolute paths remain historical provenance",
        "excluded": ["Redundant complete frozen runtime tree", "Python bytecode caches"], "files": files,
        "source_files_unchanged": True, "completed_native_run_not_repeated": True, "production_correction_integrated": False}
    (TARGET / "retention.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"status": manifest["status"], "files": len(files), "bytes": sum(v["bytes"] for v in files.values()), "manifest_sha256": sha(TARGET / "retention.json")}))


if __name__ == "__main__":
    main()
