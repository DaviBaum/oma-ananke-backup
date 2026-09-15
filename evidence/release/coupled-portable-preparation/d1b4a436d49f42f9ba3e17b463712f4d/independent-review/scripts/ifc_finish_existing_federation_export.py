"""Finish an existing federation export after an orchestration timeout.

Uses only the requested immutable checker runtime, unchanged exported bytes and
the original exported candidate. No native or semantic obligation is skipped.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import psutil

ROOT = Path(__file__).resolve().parents[1]
if not os.environ.get("OMA_EXECUTABLE_BUILD"):
    raise RuntimeError("This resumption requires an explicit immutable checker runtime")
from oma.build_identity import checker_version, frozen_environment
from oma.ifc.audit import atomic_json, sha256_file
from oma.store import Store, utcnow


def main(args):
    start = time.perf_counter()
    store = Store(ROOT / ".oma")
    version = checker_version()
    assert version.endswith(os.environ["OMA_EXECUTABLE_BUILD"])
    original = store.candidate(args.candidate)
    exported = store.candidate(args.exported_candidate)
    assert original["project_id"] == exported["project_id"]
    assert store.project(original["project_id"])["state_root"] == original["state_root"]
    export_state = store.get(exported["state_root"])
    correspondence = export_state["derived_artifacts"]["export_correspondence"]
    assert correspondence["input_candidate_root"] == original["state_root"]
    files = correspondence["files"]
    directories = {Path(row["path"]).resolve().parent for row in files}
    assert len(directories) == 1
    directory = directories.pop()
    assert directory.is_relative_to((store.directory / "exports").resolve())
    cancel_file = directory / "CANCEL_CHECK"
    evidence_path = directory / "resume-progress.json"
    evidence = {"status":"WAITING_FOR_EXISTING_CHECK", "candidate_id":args.candidate,
                "exported_candidate_id":args.exported_candidate, "candidate_root":original["state_root"],
                "exported_candidate_root":exported["state_root"], "checker_version":version,
                "deadline_seconds":args.budget, "memory_budget_bytes":32*1024**3, "cancel_file":str(cancel_file),
                "source_and_export_bytes_changed":False, "orchestration_only":True,
                "original_export_timeout_seconds":600, "original_finalizer_timeout_seconds":900}
    spawned = None
    last_print = 0.
    try:
        while True:
            processes = []
            for process in psutil.process_iter(["pid","cmdline"]):
                command = process.info["cmdline"] or []
                if args.exported_candidate in command and "oma.verification" in command:
                    processes.append(process)
            if args.orchestrator_pid and psutil.pid_exists(args.orchestrator_pid):
                parent = psutil.Process(args.orchestrator_pid)
                command = parent.cmdline()
                if args.candidate in command and any("ifc_finalize_checked_repair.py" in part for part in command):
                    processes.append(parent)
            elapsed = time.perf_counter()-start
            rss = 0
            live = []
            for process in processes:
                try:
                    rss += process.memory_info().rss
                    live.append(process)
                except psutil.NoSuchProcess:
                    pass
            processes = live
            if cancel_file.exists() or elapsed > args.budget or rss > 32*1024**3:
                for process in processes:
                    for child in process.children(recursive=True):
                        child.kill()
                    process.kill()
                raise RuntimeError("Cancellation, time or memory budget reached; existing evidence preserved")
            exported = store.candidate(args.exported_candidate)
            if not processes and exported["status"] == "CHECKED":
                break
            if not processes and spawned is None:
                # A timeout may have killed the native child too. Reuse the exact
                # exported state/candidate and give that checker a realistic bound.
                stdout = (directory / "resume-check.stdout.log").open("w",encoding="utf-8")
                stderr = (directory / "resume-check.stderr.log").open("w",encoding="utf-8")
                spawned = subprocess.Popen([sys.executable,"-m","oma.verification",str(store.directory),args.exported_candidate],
                    stdout=stdout,stderr=stderr,env=frozen_environment(store.directory),
                    creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
                stdout.close(); stderr.close()
            elif not processes and spawned is not None:
                raise RuntimeError("Independent exported candidate did not finish CHECKED")
            evidence.update(seconds=elapsed, observed_pids=[p.pid for p in processes], observed_rss_bytes=rss)
            atomic_json(evidence_path,evidence)
            if elapsed-last_print > 30:
                print(json.dumps({k:evidence[k] for k in ["status","seconds","observed_pids","observed_rss_bytes"]}),flush=True)
                last_print=elapsed
            time.sleep(2)
        original_report = store.get(original["report_root"])
        report = store.get(exported["report_root"])
        for checked, root in [(original_report,original["state_root"]),(report,exported["state_root"])]:
            assert checked["status"] == "PASS" and checked["candidate_root"] == root and checked["checker_version"] == version
            assert all(r["status"] in ("PASS","NOT_APPLICABLE") for r in checked["results"])
            required={"fixed-request-assumptions","protected-source-preservation","materialized-input-integrity",
                "fixed-service-obligations","exported-physical-semantics","physical-interference-and-clearance",
                "physical-self-interference","physical-port-body-attachment","permitted-zone-containment",
                "independent-objective-recomputation"}
            assert required <= {r["id"] for r in checked["results"] if r["status"] == "PASS"}
        # Export has every original obligation plus its independently checked
        # byte-for-byte federation/source correspondence.
        assert {(r["id"],r["status"]) for r in report["results"]} == (
            {(r["id"],r["status"]) for r in original_report["results"]}
            | {("export-federation-correspondence","PASS")})
        assert report["objective"] == original_report["objective"]
        state = store.get(original["state_root"])
        sources = {s["id"]:s for s in state["sources"]}
        assert len(files) == len(sources) and {r["source_id"] for r in files} == set(sources)
        for row in files:
            source = sources[row["source_id"]]
            assert row["source_sha256"] == source["sha256"] == sha256_file(store.resolve_path(source["immutable_path"]))
            assert sha256_file(row["path"]) == row["sha256"]
            if not row["changed"]:
                assert row["sha256"] == source["sha256"]
        materialization = store.get(export_state["derived_artifacts"]["route_materialization"]["root"])
        assert materialization["reimport"]["status"] == "PASS"
        assert sha256_file(materialization["export_path"]) == materialization["export_sha256"]
        expected = copy.deepcopy(state)
        expected["derived_artifacts"]["route_materialization"] = export_state["derived_artifacts"]["route_materialization"]
        for route in expected["routes"]:
            if route["id"] in original["changed_ids"]:
                route["geometry_artifact"] = export_state["derived_artifacts"]["route_materialization"]["root"]
        expected["derived_artifacts"]["export_correspondence"] = correspondence
        assert expected == export_state, "Exported state changed beyond the exact byte-copy correspondence"
        manifest_path = directory / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            assert manifest["status"] == "CHECKED_LOCAL_SCOPE" and manifest["verification_root"] == exported["report_root"]
        else:
            manifest = {"export_id":directory.name,"project_id":original["project_id"],"candidate_id":args.candidate,
                "state_root":original["state_root"],"created_at":utcnow(),"status":"CHECKED_LOCAL_SCOPE",
                "files":files,"round_trip":"PASS","whole_building_release":"NOT_CERTIFIED",
                "exported_state_root":exported["state_root"],"verification_root":exported["report_root"],
                "objective":report["objective"],"checked_scope":report["scope"],
                "correspondences":[{"source_id":materialization["source_sha256"],"replacement_path":materialization["export_path"],
                    "route_id":materialization["route_id"],"part_guids":[p["ifc_guid"] for p in materialization["added_parts"]]}],
                "limitations":["Local route checks do not certify pre-existing defects or whole-building adequacy",
                    "Completed from the unchanged exported candidate after the original orchestration timeout"],
                "source_redistribution":"Local user export; original project license terms retained"}
            atomic_json(manifest_path,manifest)
            atomic_json(directory / "verification.json",report)
            atomic_json(directory / "state.json",state)
            manifest_root = store.put(manifest)
            store.append_event(original["project_id"],state_root=original["state_root"],candidate_id=args.candidate,
                stage="export",status="CHECKED_LOCAL_SCOPE",message="Existing exported IFC bytes independently checked under the pinned runtime; timeout resumed",
                artifacts=[manifest_root],payload={"directory":str(directory),"round_trip":"PASS"})
        for filename,label in [("license.txt","source-license.txt"),("model_card.md","source-model-card.md")]:
            source = ROOT / "data/ifc-bench/projects" / args.project_label / filename
            if source.exists():
                shutil.copyfile(source,directory / label)
        evidence.update(status="CHECKED_ACCEPTED_EXPORTED_RECHECKED", seconds=time.perf_counter()-start,
            accepted_revision=store.project(original["project_id"])["revision"], original_report_root=original["report_root"],
            export_report_root=exported["report_root"], export=manifest, export_manifest_sha256=sha256_file(manifest_path))
        atomic_json(evidence_path,evidence)
        output = ROOT / "evidence/benchmarks/real-repair" / args.project_label / (args.candidate + ".federation-accepted-export.json")
        atomic_json(output,evidence)
        print(json.dumps({"status":evidence["status"],"evidence":str(output),"seconds":evidence["seconds"]}),flush=True)
    except BaseException as exc:
        evidence.update(status="RESUME_FAILED",error=repr(exc),seconds=time.perf_counter()-start)
        atomic_json(evidence_path,evidence)
        raise


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate",required=True)
    parser.add_argument("--exported-candidate",required=True)
    parser.add_argument("--project-label",required=True)
    parser.add_argument("--orchestrator-pid",type=int)
    parser.add_argument("--budget",type=float,default=3600)
    main(parser.parse_args())
