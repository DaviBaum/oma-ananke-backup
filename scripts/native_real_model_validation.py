"""Recheck retained real exported IFC bytes using only the isolated native build.

The original database is opened read-only. Its consistent SQLite backup and all
new reports/cache artifacts live below .release/native-build. Original blobs
are hash-checked read-through inputs, never output locations.
"""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid

from native_prepare import ROOT, DEST, EVIDENCE, sha, json_write
from native_build import run


CANDIDATE = "fa36c40e41834d629450ba61cfaf5ad6"


def child(directory, candidate_id=CANDIDATE, source_checkpoint="94e74251a39d1f0d8cc77feb9d2df686e3927eb49473b67d09d8bdf66843c93f", expected_export_sha256=None):
    from oma.build_identity import checker_version
    from oma.routing.checker import verify_route_candidate
    from oma.store import Store

    class Original(Store):
        def __init__(self):
            self.directory = ROOT / ".oma"
            self.database = self.directory / "oma.sqlite3"
            self.blobs = self.directory / "blobs"

        def connect(self):
            from oma.store import _Connection
            db = sqlite3.connect(self.database.as_uri() + "?mode=ro", uri=True,
                                 factory=_Connection)
            db.row_factory = sqlite3.Row
            return db

        def put(self, value):
            raise RuntimeError("The original store is a read-only input")

    original = Original()

    class Isolated(Store):
        def get(self, root):
            if (self.blobs / f"{root}.json.z").exists():
                return super().get(root)
            return original.get(root)

        def resolve_path(self, value):
            return original.resolve_path(value)

    directory = Path(directory).resolve()
    assert directory.is_relative_to(DEST.resolve()) and not directory.exists()
    directory.mkdir(parents=True)
    with original.connect() as source_db:
        with sqlite3.connect(directory / "oma.sqlite3") as target_db:
            source_db.backup(target_db)
    store = Isolated(directory)
    candidate = store.candidate(candidate_id)
    original_head = original.project(candidate["project_id"])
    state = store.get(candidate["state_root"])
    materialization = store.get(state["derived_artifacts"]["route_materialization"]["root"])
    files = {str(store.resolve_path(s["immutable_path"])): s["sha256"] for s in state["sources"]}
    files[str(store.resolve_path(materialization["export_path"]))] = materialization["export_sha256"]
    if expected_export_sha256 is not None:
        assert materialization["export_sha256"] == expected_export_sha256
    assert all(sha(Path(p)) == h for p, h in files.items())
    previous = store.get(candidate["report_root"])
    assert previous["status"] == "PASS" and previous["checker_version"].endswith(source_checkpoint)
    start = time.monotonic()
    result = {"status": "RUNNING", "candidate_id": candidate_id, "source_checkpoint": source_checkpoint,
              "candidate_root": candidate["state_root"], "checker_version": checker_version(),
              "prior_report_root": candidate["report_root"], "source_and_exported_files": files,
              "isolated_store": str(directory), "active_store_write_mode": "READ_ONLY",
              "scope": "Existing real Office exported graph route, same fixed mission and bytes; complete independent candidate check under candidate native runtime"}
    json_write(directory / "real-model-result.json", result)
    try:
        checked = verify_route_candidate(store, candidate_id).model_dump(mode="json")
        result["report"] = checked
        result["report_root"] = store.candidate(candidate_id)["report_root"]
        assert checked["status"] == "PASS"
        assert checked["candidate_root"] == candidate["state_root"]
        assert checked["checker_version"] == checker_version() and checked["checker_version"] != previous["checker_version"]
        assert checked["objective"] == previous["objective"]
        assert {r["id"]: r["status"] for r in checked["results"]} == {r["id"]: r["status"] for r in previous["results"]}
        assert all(sha(Path(p)) == h for p, h in files.items())
        assert original.project(candidate["project_id"]) == original_head
        result.update(status="REAL_EXPORTED_OFFICE_RECHECK_PASS", original_bytes_and_head_unchanged=True,
                      same_objective_and_obligation_dispositions=True)
    except BaseException as exc:
        result.update(status="INCOMPLETE_OR_FAILED", error=repr(exc))
        raise
    finally:
        result["seconds"] = time.monotonic() - start
        json_write(directory / "real-model-result.json", result)
        print(json.dumps({k: result.get(k) for k in ("status", "checker_version", "seconds", "report_root")}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--child-directory")
    parser.add_argument("--candidate-id", default=CANDIDATE)
    parser.add_argument("--source-checkpoint", default="94e74251a39d1f0d8cc77feb9d2df686e3927eb49473b67d09d8bdf66843c93f")
    parser.add_argument("--expected-export-sha256")
    parser.add_argument("--checkpoint-validation", type=Path)
    parser.add_argument("--portable-validation", type=Path)
    parser.add_argument("--output-directory", type=Path)
    args = parser.parse_args()
    if args.child_directory:
        return child(args.child_directory, args.candidate_id, args.source_checkpoint, args.expected_export_sha256)
    env = os.environ.copy()
    python = DEST / "test-venv/Scripts/python.exe"
    if args.portable_validation:
        assert args.checkpoint_validation is None
        portable = json.loads(args.portable_validation.read_text())
        assert portable["status"] == "ISOLATED_NATIVE_PORTABLE_OFFLINE_WORKFLOW_PASS"
        assert portable["source_checkpoint"] == args.source_checkpoint
        package = Path(portable["package"])
        python = package / "runtime/python.exe"
        env.update(PYTHONPATH=str(package / "src"), OMA_EXECUTABLE_BUILD=portable["identity"]["checker_version"],
                   PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1", OMA_OFFLINE_DENY_NETWORK="1")
    elif args.checkpoint_validation:
        checkpoint = json.loads(args.checkpoint_validation.read_text())
        assert checkpoint["source_checkpoint"] == args.source_checkpoint
        env.update(checkpoint["runtime"])
    else:
        assert args.source_checkpoint == "94e74251a39d1f0d8cc77feb9d2df686e3927eb49473b67d09d8bdf66843c93f"
        env.update(json.loads((EVIDENCE / "candidate-application-runtime.json").read_text()))
    directory = DEST / "real-model-validation" / uuid.uuid4().hex
    command = [python, Path(__file__).resolve(), "--child-directory", directory,
               "--candidate-id", args.candidate_id, "--source-checkpoint", args.source_checkpoint]
    if args.expected_export_sha256:
        command.extend(["--expected-export-sha256", args.expected_export_sha256])
    record = run("real-office-export-recheck", command, cwd=ROOT, env=env, budget=1200)
    result = json.loads((directory / "real-model-result.json").read_text())
    result.update(command_record=str(record / "record.json"), script_sha256=sha(Path(__file__)))
    json_write((args.output_directory or EVIDENCE) / "real-office-validation.json", result)


if __name__ == "__main__":
    main()
