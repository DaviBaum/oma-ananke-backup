"""Recheck retained real exported IFC bytes using only the isolated native build.

The original database is opened read-only. A consistent SQLite snapshot and the
target project's immutable artifact/asset closure are copied to an isolated
store. Fresh supervised children can read those copies without Python-only
read-through overrides; only their parent may publish a completed recheck.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sqlite3
import time
import uuid

from native_prepare import ROOT, DEST, EVIDENCE, sha, json_write
from native_build import run


CANDIDATE = "fa36c40e41834d629450ba61cfaf5ad6"


def isolate_candidate(original, directory, candidate_id):
    """Copy one project's required closure from a read-only database snapshot.

    Other project rows remain in the SQLite snapshot as historical metadata,
    but their unrelated blobs and assets are not copied. This is a validation
    workspace, not a complete portable backup of the original store.
    """
    from oma.backup import _asset_references, _content_roots
    from oma.store import Store

    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    with original.connect() as source_db:
        with sqlite3.connect(directory / "oma.sqlite3") as target_db:
            source_db.backup(target_db)
    store = Store(directory)
    candidate = store.candidate(candidate_id)
    project_id = candidate["project_id"]
    with store.connect() as db:
        roots = {r[0] for r in db.execute(
            "SELECT state_root FROM projects WHERE id=? UNION SELECT root FROM revisions WHERE project_id=? "
            "UNION SELECT state_root FROM candidates WHERE project_id=? UNION SELECT report_root FROM candidates "
            "WHERE project_id=? AND report_root IS NOT NULL UNION SELECT base_root FROM runs WHERE project_id=?",
            (project_id,) * 5)}
        documents = [json.loads(r[0]) for r in db.execute(
            "SELECT payload FROM events WHERE project_id=? UNION ALL SELECT request FROM runs WHERE project_id=? "
            "UNION ALL SELECT payload FROM candidates WHERE project_id=? UNION ALL SELECT response FROM requests WHERE project_id=?",
            (project_id,) * 4)]
    references, copied = set(), set()
    for document in documents:
        references.update(_asset_references(document))
        roots.update(r for r in _content_roots(document) if (original.blobs / f"{r}.json.z").is_file())
    while roots:
        root = roots.pop()
        if root in copied:
            continue
        document = original.get(root)  # Validate content identity before copying.
        shutil.copyfile(original.blobs / f"{root}.json.z", store.blobs / f"{root}.json.z")
        assert store.get(root) == document
        copied.add(root)
        references.update(_asset_references(document))
        roots.update(r for r in _content_roots(document)
                     if r not in copied and (original.blobs / f"{r}.json.z").is_file())
    assets, aliases = [], []
    for reference in sorted(references):
        resolved = original.resolve_path(reference).resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"Required validation input is missing: {resolved}")
        hashed = sha(resolved)
        relative = Path("validation-inputs") / hashed / resolved.name
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copyfile(resolved, target)
        if sha(target) != hashed or sha(resolved) != hashed:
            raise RuntimeError(f"Input changed during validation snapshot: {resolved}")
        aliases.append((str(Path(reference).expanduser()), str(relative), hashed))
        assets.append({"reference": reference, "original_resolved_path": str(resolved),
                       "copied_path": str(relative), "sha256": hashed})
        if resolved.suffix.lower() == ".ifc":
            sidecar = resolved.with_suffix(".manifest.json")
            if sidecar.is_file():
                sidecar_hash = sha(sidecar)
                copied_sidecar = target.with_suffix(".manifest.json")
                shutil.copyfile(sidecar, copied_sidecar)
                if sha(copied_sidecar) != sidecar_hash or sha(sidecar) != sidecar_hash:
                    raise RuntimeError(f"IFC sidecar changed during validation snapshot: {sidecar}")
                assets.append({"original_resolved_path": str(sidecar),
                               "copied_path": str(copied_sidecar.relative_to(directory)), "sha256": sidecar_hash})
    with store.transaction() as db:
        db.execute("DELETE FROM run_owners")
        db.execute("DELETE FROM asset_aliases")
        db.execute("DELETE FROM metadata WHERE key='relocation_roots'")
        db.executemany("INSERT INTO asset_aliases VALUES(?,?,?)", aliases)
    evidence = {"schema": "oma.native-validation-input-copy/1", "project_id": project_id,
                "candidate_id": candidate_id, "candidate_root": candidate["state_root"],
                "copied_artifact_roots": sorted(copied), "assets": assets,
                "scope": "Target project artifact closure; other database rows are metadata only",
                "original_database_access": "READ_ONLY", "child_input_resolution": "COPIED_ASSET_ALIASES"}
    json_write(directory / "validation-input-copy.json", evidence)
    return store, evidence


def managed_recheck(store, candidate_id, *, deadline, environment):
    from oma.routing.check_execution import run_candidate_check

    candidate = store.candidate(candidate_id)
    owner = store.create_run(candidate["project_id"], {"operation": "recheck", "candidate_id": candidate_id,
        "budget_seconds": max(0., deadline - time.monotonic()), "validation": "isolated-native-real-model"})
    store.update_run(owner["id"], "CHECKING", "Fresh isolated native-runtime recheck", "recheck")
    try:
        execution = run_candidate_check(store, candidate_id, deadline=deadline,
            control_run_id=owner["id"], environment=environment)
        complete = execution["status"] == "COMPLETED" and execution["report_published"]
        store.update_run(owner["id"], "COMPLETED" if complete else "FAILED",
                         "Isolated native execution " + execution["status"], "recheck")
        return {**execution, "control_run_id": owner["id"]}
    except BaseException:
        store.update_run(owner["id"], "FAILED", "Isolated recheck interrupted before completion", "recheck")
        raise


def child(directory, candidate_id=CANDIDATE, source_checkpoint="94e74251a39d1f0d8cc77feb9d2df686e3927eb49473b67d09d8bdf66843c93f", expected_export_sha256=None, prior_checker_version=None):
    from oma.build_identity import checker_version
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

    directory = Path(directory).resolve()
    assert directory.is_relative_to(DEST.resolve()) and not directory.exists()
    store, copied_inputs = isolate_candidate(original, directory, candidate_id)
    candidate = store.candidate(candidate_id)
    original_head = original.project(candidate["project_id"])
    state = store.get(candidate["state_root"])
    assert candidate["kind"] in {"physical_route", "physical_route_set"}
    materializations = [store.get(r["geometry_artifact"]) for r in state["routes"]]
    assert materializations
    files = {str(original.resolve_path(s["immutable_path"])): s["sha256"] for s in state["sources"]}
    files.update({str(original.resolve_path(m["export_path"])): m["export_sha256"] for m in materializations})
    if expected_export_sha256 is not None:
        assert {m["export_sha256"] for m in materializations} == {expected_export_sha256}
    assert all(sha(Path(p)) == h for p, h in files.items())
    previous = store.get(candidate["report_root"])
    assert previous["status"] == "PASS" and previous["candidate_root"] == candidate["state_root"]
    if prior_checker_version is not None:
        assert previous["checker_version"] == prior_checker_version
    assert os.environ["OMA_EXECUTABLE_BUILD"] == checker_version()
    start = time.monotonic()
    result = {"status": "RUNNING", "candidate_id": candidate_id, "source_checkpoint": source_checkpoint,
              "candidate_root": candidate["state_root"], "checker_version": checker_version(),
              "prior_report_root": candidate["report_root"], "prior_checker_version": previous["checker_version"],
              "requested_prior_checker_version": prior_checker_version, "source_and_exported_files": files,
              "isolated_store": str(directory), "active_store_write_mode": "READ_ONLY",
              "copied_input_evidence": str(directory / "validation-input-copy.json"),
              "scope": "Existing real Office exported route set, same fixed mission and bytes; complete independent candidate check under candidate native runtime"}
    json_write(directory / "real-model-result.json", result)
    try:
        execution = managed_recheck(store, candidate_id, deadline=start + 1100., environment=os.environ.copy())
        result["execution"] = execution
        assert execution["status"] == "COMPLETED" and execution["report_published"], execution
        checked = store.get(execution["candidate"]["report_root"])
        result["report"] = checked
        result["report_root"] = store.candidate(candidate_id)["report_root"]
        assert checked["status"] == "PASS"
        assert checked["candidate_root"] == candidate["state_root"]
        assert checked["checker_version"] == checker_version() and checked["checker_version"] != previous["checker_version"]
        assert checked["objective"] == previous["objective"]
        assert {r["id"]: r["status"] for r in checked["results"]} == {r["id"]: r["status"] for r in previous["results"]}
        assert all(sha(Path(p)) == h for p, h in files.items())
        assert all(sha(Path(a["original_resolved_path"])) == a["sha256"]
                   and sha(directory / a["copied_path"]) == a["sha256"] for a in copied_inputs["assets"])
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
    parser.add_argument("--prior-checker-version", help="Optional exact immutable prior report identity; independent of the current source checkpoint")
    parser.add_argument("--checkpoint-validation", type=Path)
    parser.add_argument("--portable-validation", type=Path)
    parser.add_argument("--output-directory", type=Path)
    args = parser.parse_args()
    if args.child_directory:
        return child(args.child_directory, args.candidate_id, args.source_checkpoint, args.expected_export_sha256, args.prior_checker_version)
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
    if args.prior_checker_version:
        command.extend(["--prior-checker-version", args.prior_checker_version])
    record = run("real-office-export-recheck", command, cwd=ROOT, env=env, budget=1200)
    result = json.loads((directory / "real-model-result.json").read_text())
    result.update(command_record=str(record / "record.json"), script_sha256=sha(Path(__file__)))
    json_write((args.output_directory or EVIDENCE) / "real-office-validation.json", result)


if __name__ == "__main__":
    main()
