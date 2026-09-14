"""Do not convert missing completion into a test result; retain frozen inputs."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil

STAGE = Path(__file__).resolve().parent
ROOT = next(p for p in STAGE.parents if (p / "AGENTS.md").is_file())
OUT = ROOT / "evidence/release/passive-tree-full-32b35337603643cb8cb3020033472fed"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    result = json.loads((OUT / "result.json").read_text(encoding="utf8"))
    assert result["status"] == "RUNNING" and not (OUT / "tests.xml").exists()
    snapshot = Path(result["test_snapshot"])
    target = OUT / "retained-inputs"
    target.mkdir(exist_ok=False)
    for relative, value in result["snapshot_files"].items():
        source, copy = snapshot / relative, target / relative
        assert sha(source) == value
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, copy)
        assert sha(copy) == value
    source = Path(result["source_directory"]) / "oma"
    assert {p.relative_to(source).as_posix(): sha(p) for p in source.rglob("*.py")} == result["source_files"]
    shutil.copyfile(__file__, OUT / "retain-interruption.py")
    record = {"status": "INTERRUPTED_WITHOUT_COMPLETION_NO_TEST_RESULT_CLAIMED",
        "observed_at": datetime.now(timezone.utc).isoformat(), "source_build": result["checker_version"],
        "declared_cases": 2067, "input_files": 118, "source_files": 102,
        "raw_receipt_sha256": sha(OUT / "result.json"), "partial_log_sha256": sha(OUT / "pytest.log"),
        "completed_xml_exists": False, "raw_receipt_unchanged": True,
        "completed_pass_count": None, "wrapper_tool_exit_code": 1, "traceback_recorded": False,
        "cause": "UNDETERMINED_EXTERNAL_PROCESS_INTERRUPTION",
        "observations": ["Root wrapper and pytest no longer present in python process inventory",
            "Separate custom-native and bundled wrapper disappeared at the same observed interruption; bundled pytest survived",
            "Independent read-only audit also disappeared without traceback; agents issued no process termination",
            "No matching recent Windows Application crash or System warning record was returned by local queries"],
        "retry_policy": "New receipt and run of the same exact frozen source and test inventory; never overwrite this incomplete run",
        "retention_script_sha256": sha(OUT / "retain-interruption.py")}
    (OUT / "interruption-audit.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf8")
    print(json.dumps({k:record[k] for k in ("status", "declared_cases", "input_files", "completed_pass_count")}))


if __name__ == "__main__":
    main()
