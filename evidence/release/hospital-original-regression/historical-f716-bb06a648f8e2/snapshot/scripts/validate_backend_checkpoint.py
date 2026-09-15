"""Run the complete backend suite with pinned executable and test/support bytes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from oma.build_identity import checker_version, frozen_environment
from oma.ifc.audit import atomic_json


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", args.label):
        parser.error("label requires 1 to 64 lowercase letters, digits or hyphens")
    identity = args.label + "-" + uuid.uuid4().hex
    snapshot = ROOT / ".oma/test-snapshots" / identity
    snapshot.mkdir(parents=True)
    evidence = ROOT / "evidence/release" / identity
    evidence.mkdir(parents=True)
    paths = list((ROOT / "tests").rglob("*.py"))
    paths += [ROOT / p for p in ("pyproject.toml", "Start-OMA.ps1", "docs/ifc-network-spec.json",
        "scripts/corpus_route_metadata_probe.py", "scripts/native_real_model_validation.py",
        "scripts/native_prepare.py", "scripts/native_build.py")]
    files = {}
    for source in paths:
        relative = source.relative_to(ROOT)
        before = file_hash(source)
        target = snapshot / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if file_hash(source) != before or file_hash(target) != before:
            raise RuntimeError("Test/support file changed while snapshotting: " + str(relative))
        files[relative.as_posix()] = before
    env = frozen_environment(ROOT / ".oma")
    version = env["OMA_EXECUTABLE_BUILD"]
    command = [sys.executable, "-m", "pytest", "-o", "pythonpath=" + env["PYTHONPATH"], str(snapshot / "tests"),
        "-q", "--junitxml=" + str(evidence / "tests.xml")]
    result = {"status": "RUNNING", "checker_version": version, "test_snapshot": str(snapshot),
        "snapshot_files": files, "command": command, "runner_sha256": file_hash(Path(__file__)),
        "scope": "All backend tests present when the immutable test/support snapshot was captured"}
    atomic_json(evidence / "result.json", result)
    print(json.dumps({"stage": "FROZEN", "checker_version": version, "snapshot_files": len(files), "evidence": str(evidence)}), flush=True)
    started = time.perf_counter()
    with (evidence / "pytest.log").open("w", encoding="utf-8") as log:
        completed = subprocess.run(command, cwd=snapshot, env=env, stdout=log, stderr=subprocess.STDOUT)
    result.update(returncode=completed.returncode, elapsed_seconds=time.perf_counter() - started,
        snapshot_unchanged=all(file_hash(snapshot / p) == h for p, h in files.items()),
        working_source_still_matches_snapshot=checker_version() == version)
    result["status"] = "PASS" if completed.returncode == 0 and result["snapshot_unchanged"] else "FAIL"
    atomic_json(evidence / "result.json", result)
    print((evidence / "pytest.log").read_text(encoding="utf-8"), flush=True)
    print(json.dumps({k: v for k, v in result.items() if k != "snapshot_files"}), flush=True)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
