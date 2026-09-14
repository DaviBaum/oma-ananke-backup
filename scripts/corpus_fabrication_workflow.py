"""Replay an existing explicit real-IFC mission through the current full backend.

Original state, scenario and source bytes are retained. A separate project/run
generates fresh candidates, checks their physical geometry and nominal proofs,
then accepts and independently checks the exported replacement federation.
"""
import argparse
import json
from pathlib import Path
import sys
import time
import uuid

from oma.build_identity import checker_version, frozen_environment
from oma.export_checks import supervise_check
from oma.exporting import export_project
from oma.ifc.audit import atomic_json, sha256_file
from oma.store import Store, digest, utcnow


def collect_existing_attempt(store, directory):
    """Recover collection after completed checks without relabeling a new run."""
    out = Path(directory).resolve()
    original = json.loads((out/"result.json").read_text(encoding="utf-8"))
    bundle = original["export"]
    manifest = store.get(bundle["artifact_root"])
    on_disk = json.loads(Path(bundle["manifest"]).read_text(encoding="utf-8"))
    report = store.get(manifest["verification_root"])
    checks = {
        "export_manifest_identity":digest(on_disk) == bundle["artifact_root"],
        "passing_export":manifest["status"] == "CHECKED_LOCAL_SCOPE" and manifest["round_trip"] == "PASS",
        "report_bindings":report["status"] == "PASS" and report["candidate_root"] == manifest["exported_state_root"]
            and report["checker_version"] == original["checker_version"],
        "release_bindings":bool(manifest["checking"]["release_bindings"]) and all(manifest["checking"]["release_bindings"].values()),
        "actual_exported_bytes":all(sha256_file(f["path"]) == f["sha256"] for f in manifest["files"]),
        "original_preservation":original["original_project_unchanged"] and original["original_source_bytes_unchanged"],
    }
    baseline = store.get(original["baseline_root"])
    checks["current_source_bytes"] = all(sha256_file(store.resolve_path(s["immutable_path"])) == s["sha256"] for s in baseline["sources"])
    recovered = {**original,"status":"PASS" if all(checks.values()) else "FAIL_COLLECTION_BINDING",
        "collection_recovery":{"original_result":"result.json","original_collection_error":original.get("error"),
            "checks":checks,"collected_at":utcnow(),"native_checks_reexecuted":False},
        "export_verification_root":manifest["verification_root"],"exported_state_root":manifest["exported_state_root"]}
    recovered.pop("error",None)
    path = out/("collected-"+uuid.uuid4().hex+".json")
    atomic_json(out/"export.verification.json",report)
    atomic_json(path,recovered)
    print(json.dumps({"artifact":str(path),"status":recovered["status"],"checker_version":report["checker_version"]}),flush=True)
    if not all(checks.values()):
        raise RuntimeError(checks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", default=".oma")
    parser.add_argument("--historical-candidate", default="f583693cce4644ad8306b31d51c8540f")
    parser.add_argument("--budget", type=float, default=900.)
    parser.add_argument("--collect-attempt")
    args = parser.parse_args()
    if args.collect_attempt:
        return collect_existing_attempt(Store(Path(args.store).resolve()),args.collect_attempt)
    root = Path(__file__).resolve().parents[1]
    out = root / "evidence/benchmarks/fabrication-workflow" / uuid.uuid4().hex
    out.mkdir(parents=True)
    store = Store(Path(args.store).resolve())
    historical = store.candidate(args.historical_candidate)
    origin = store.run(historical["run_id"])
    old_project = store.project(origin["project_id"])
    baseline = store.get(origin["base_root"])
    source_hashes = {source["id"]: sha256_file(store.resolve_path(source["immutable_path"])) for source in baseline["sources"]}
    if any(source_hashes[s["id"]] != s["sha256"] for s in baseline["sources"]):
        raise RuntimeError("Original source bytes changed before reproduction")
    project = store.create_project("Fresh fabrication and native IFC workflow", baseline)
    request = {**origin["request"], "budget_seconds": args.budget}
    request.pop("idempotency_key", None)
    run = store.create_run(project["id"], request)
    started = time.monotonic()
    result = {"status":"RUNNING", "started_at":utcnow(), "checker_version":checker_version(),
        "project_id":project["id"], "run_id":run["id"], "baseline_root":run["base_root"],
        "historical_candidate_id":historical["id"], "historical_baseline_root":origin["base_root"],
        "original_mission_root":digest(origin["request"]["mission"]), "mission_unchanged":True,
        "source_hashes":source_hashes, "prior_physical_verdict_reused":False,
        "scope":"EXPLICIT_REAL_SOURCE_LOCAL_ROUTE_MISSION; NOT_WHOLE_BUILDING_CERTIFICATION"}
    atomic_json(out / "result.json", result)
    print(json.dumps({"attempt":str(out),"project_id":project["id"],"run_id":run["id"]}), flush=True)
    try:
        child = supervise_check([sys.executable,"-m","oma.worker",str(store.directory),run["id"]],
            environment=frozen_environment(store.directory), directory=out/"worker", deadline=started+args.budget+15)
        result["worker"] = child
        result["run"] = store.run(run["id"])
        candidates = store.candidates(project["id"])
        result["candidates"] = []
        feasible = []
        for candidate in candidates:
            report = store.get(candidate["report_root"]) if candidate.get("report_root") else None
            entry = {"id":candidate["id"], "state_root":candidate["state_root"], "status":candidate["status"],
                "report_root":candidate.get("report_root"), "objective":report["objective"] if report else None}
            if report:
                atomic_json(out / f"{candidate['id']}.verification.json", report)
                entry["fabrication_proofs"] = [r for r in report["results"] if r["id"].endswith("nominal-fabrication-witness-integrity")]
                entry["failed_checks"] = [r["id"] for r in report["results"] if r["status"] == "FAIL"]
            result["candidates"].append(entry)
            if candidate["status"] == "CHECKED":
                feasible.append(candidate)
        atomic_json(out / "result.json", result)
        if child["status"] != "COMPLETED" or not feasible:
            raise RuntimeError("Fresh worker did not finish with a physically checked candidate")
        complete = next(e for e in reversed(store.events(project["id"],limit=1000))
            if e["run_id"] == run["id"] and e["stage"] == "complete")
        selected_ids = complete["payload"]["selected_candidate_ids"]
        if len(selected_ids) != 1:
            raise RuntimeError("Expected one independently checked finite-design selection")
        selected = next(c for c in feasible if c["id"] == selected_ids[0])
        result["selection_event"] = complete
        result["acceptance"] = store.accept(project["id"],selected["id"],project["revision"],
            "fresh-fabrication-workflow",checker_version=checker_version())
        result["export"] = export_project(store,project["id"],selected["id"],draft=False,budget_seconds=args.budget)
        exported = store.get(store.get(result["export"]["artifact_root"])["verification_root"])
        atomic_json(out / "export.verification.json", exported)
        result["status"] = "PASS" if result["export"]["status"] == "CHECKED_LOCAL_SCOPE" else "FAIL"
    except Exception as error:
        result.update(status="INCOMPLETE", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        result["elapsed_seconds"] = time.monotonic()-started
        result["original_project_unchanged"] = store.project(origin["project_id"]) == old_project
        result["original_source_bytes_unchanged"] = all(sha256_file(store.resolve_path(s["immutable_path"])) == source_hashes[s["id"]] for s in baseline["sources"])
        if not result["original_project_unchanged"] or not result["original_source_bytes_unchanged"]:
            result["status"] = "FAIL_ORIGINAL_PRESERVATION"
        atomic_json(out / "result.json", result)
        print(json.dumps({"attempt":str(out),"status":result["status"],"elapsed_seconds":result["elapsed_seconds"]}),flush=True)


if __name__ == "__main__":
    main()
