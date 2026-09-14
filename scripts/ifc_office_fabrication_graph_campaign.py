"""Replay the frozen obstructed Office mission through source-bound fabrication search."""
import copy
import argparse
import json
import os
from pathlib import Path
import sys
import time
import uuid

from oma.build_identity import checker_version, frozen_environment
from oma.export_checks import supervise_check
from oma.exporting import export_project
from oma.ifc.audit import atomic_json, sha256_file
from oma.store import Store, digest, utcnow

ROOT=Path(__file__).resolve().parents[1]
BUILD="94e74251a39d1f0d8cc77feb9d2df686e3927eb49473b67d09d8bdf66843c93f"


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build",default=BUILD,help="Required immutable executable build hash")
    parser.add_argument("--require-pricing",action="store_true",help="Require an independently priced path to pass native checks and exported-byte recheck")
    args=parser.parse_args()
    assert os.environ.get("OMA_EXECUTABLE_BUILD")==args.build
    assert checker_version().endswith(args.build)
    store=Store(ROOT / ".oma")
    historical=store.candidate("f23ca52d9caf4b0ca8d2e123bc7fc011")
    origin=store.run(historical["run_id"])
    original_project=store.project(origin["project_id"])
    baseline=store.get(origin["base_root"])
    frozen_path=ROOT / "evidence/benchmarks/real-repair/wbdg_office/source-vertex-hull/bounds-screened-v2/arc.frozen.json"
    frozen=json.loads(frozen_path.read_text())
    scenario=next(s for s in frozen["scenarios"] if s["scenario_id"]=="b185aad281acfe439d15")
    assert origin["request"]["mission"]==scenario["mission"]
    assert not baseline.get("routes") and not baseline.get("physical_networks")
    assert all(sha256_file(store.resolve_path(s["immutable_path"]))==s["sha256"] for s in baseline["sources"])
    project=store.create_project("WBDG Office · obstructed source-bound fabrication " + ("pricing" if args.require_pricing else "graph"),baseline)
    request=copy.deepcopy(origin["request"])
    request.update(budget_seconds=1200)
    request.pop("idempotency_key",None)
    run=store.create_run(project["id"],request)
    out=ROOT / ("evidence/benchmarks/fabrication-pricing/office" if args.require_pricing else "evidence/benchmarks/fabrication-graph/office") / uuid.uuid4().hex
    out.mkdir(parents=True)
    start=time.monotonic()
    result={"status":"RUNNING","started_at":utcnow(),"checker_version":checker_version(),
        "project_id":project["id"],"run_id":run["id"],"baseline_root":run["base_root"],
        "historical_candidate_id":historical["id"],"historical_run_id":origin["id"],
        "historical_baseline_root":origin["base_root"],"frozen_specification_root":frozen["specification_root"],
        "frozen_specification_path":str(frozen_path),"frozen_specification_sha256":sha256_file(frozen_path),
        "scenario_id":scenario["scenario_id"],"mission":scenario["mission"],"mission_root":digest(scenario["mission"]),
        "mission_unchanged":True,"original_source_hashes":[s["sha256"] for s in baseline["sources"]],
        "prior_native_verdict_reused":False,"worker_budget_seconds":1200,"export_budget_seconds":1200,
        "require_pricing":args.require_pricing,
        "scope":"Existing hypothetical added-service mission against every original obstacle; source outer-model assumptions explicit; no whole-building or continuous-optimum claim"}
    atomic_json(out / "result.json",result)
    print(json.dumps({"directory":str(out),"project_id":project["id"],"run_id":run["id"]}),flush=True)
    try:
        result["worker"]=supervise_check([sys.executable,"-m","oma.worker",str(store.directory),run["id"]],
            environment=frozen_environment(store.directory),directory=out / "worker",deadline=start+1230)
        result["run"]=store.run(run["id"])
        candidates=[c for c in store.candidates(project["id"]) if c["run_id"]==run["id"] and not c.get("export_recheck")]
        result["candidates"]=[]
        for c in candidates:
            report=store.get(c["report_root"]) if c.get("report_root") else None
            atomic_json(out / (c["id"]+".candidate.json"),c)
            if report:
                atomic_json(out / (c["id"]+".verification.json"),report)
            result["candidates"].append({"id":c["id"],"state_root":c["state_root"],"status":c["status"],
                "report_root":c.get("report_root"),"objective":report["objective"] if report else None,
                "proposal_evidence":c.get("proposal_evidence"),
                "checks":[{"id":r["id"],"status":r["status"]} for r in report["results"]] if report else []})
        events=store.events(project["id"],limit=2000)
        atomic_json(out / "events.json",events)
        for event in events:
            if event["stage"] in ("route_geometry_model","fabrication_graph","physical_menu_compilation"):
                for artifact in event["artifacts"]:
                    atomic_json(out / (event["stage"]+"-"+artifact+".json"),store.get(artifact))
        atomic_json(out / "result.json",result)
        assert result["worker"]["status"]=="COMPLETED",result["worker"]
        graph=[c for c in candidates if (c.get("proposal_evidence") or {}).get("method")=="SOURCE_BOUND_FABRICATION_GRAPH"]
        result["graph_candidate_ids"]=[c["id"] for c in graph]
        assert graph,"No source-bound fabrication graph candidate was actually materialized; retain all outcomes"
        checked_graph=[c for c in graph if c["status"]=="CHECKED"]
        assert checked_graph,"Graph proposal did not pass full independent native checking"
        for c in checked_graph:
            artifact=store.get(c["proposal_evidence"]["report_root"])
            model_report=artifact["report"]
            assert model_report["independent_check"]["status"]=="PASS"
            assert model_report["binary64_fabrication_check"]["status"]=="PASS"
            assert model_report["binary64_fabrication_check"]["fabrication_status"]=="PASS"
        priced=[c for c in checked_graph if c["proposal_evidence"].get("path_certificate_kind")=="FABRICATION_PRICING"]
        result["native_checked_priced_candidate_ids"]=[c["id"] for c in priced]
        if args.require_pricing:
            assert priced,"No independently priced route passed native checks; retain bounded/inconclusive results"
            for c in priced:
                model_report=store.get(c["proposal_evidence"]["report_root"])["report"]
                assert model_report["pricing_check"]["status"]=="PASS"
                assert model_report["pricing_check"]["pricing_outcome"]=="OPTIMAL_PATH"
                assert model_report["priced_binary64_fabrication_check"]["fabrication_status"]=="PASS"
                assert c["proposal_evidence"]["path_certificate_root"]==digest(model_report["pricing_certificate"])
                assert c["proposal_evidence"]["binary64_fabrication_certificate_root"]==digest(model_report["priced_binary64_fabrication_certificate"])
        completion=next(e for e in reversed(events) if e["run_id"]==run["id"] and e["stage"]=="complete")
        selected_ids=completion["payload"]["selected_candidate_ids"]
        assert len(selected_ids)==1
        selected=next(c for c in candidates if c["id"]==selected_ids[0])
        assert selected["status"]=="CHECKED"
        result["selection_event"]=completion
        result["selected_candidate_id"]=selected["id"]
        result["selected_method"]=(selected.get("proposal_evidence") or {}).get("method","HEURISTIC")
        result["acceptance"]=store.accept(project["id"],selected["id"],project["revision"],"office-source-fabrication-graph",checker_version=checker_version())
        result["export"]=export_project(store,project["id"],selected["id"],draft=False,budget_seconds=1200)
        manifest=store.get(result["export"]["artifact_root"])
        exported=store.get(manifest["verification_root"])
        atomic_json(out / "export.verification.json",exported)
        assert exported["status"]=="PASS" and exported["checker_version"]==checker_version()
        assert exported["candidate_root"]==manifest["exported_state_root"]
        assert all(manifest["checking"]["release_bindings"].values())
        assert all(sha256_file(f["path"])==f["sha256"] for f in manifest["files"])
        if args.require_pricing:
            priced_candidate=priced[0]
            if priced_candidate["id"]==selected["id"]:
                result["priced_export"]=copy.deepcopy(result["export"])
            else:
                accepted_head=store.project(project["id"])
                result["priced_export"]=export_project(store,project["id"],priced_candidate["id"],draft=False,budget_seconds=1200)
                assert store.project(project["id"])["state_root"]==accepted_head["state_root"]
                assert store.project(project["id"])["revision"]==accepted_head["revision"]
            priced_manifest=store.get(result["priced_export"]["artifact_root"])
            priced_report=store.get(priced_manifest["verification_root"])
            atomic_json(out / "priced-export.verification.json",priced_report)
            assert priced_report["status"]=="PASS" and priced_report["checker_version"]==checker_version()
            assert priced_report["candidate_root"]==priced_manifest["exported_state_root"]
            assert all(priced_manifest["checking"]["release_bindings"].values())
            assert all(sha256_file(f["path"])==f["sha256"] for f in priced_manifest["files"])
        result["status"]="GRAPH_NATIVE_CHECKED_AND_SELECTED_CANDIDATE_ACCEPTED_EXPORTED_RECHECKED"
        if args.require_pricing:
            result["status"]="PRICED_ROUTE_NATIVE_AND_EXPORTED_BYTES_CHECKED_WITH_SELECTED_CANDIDATE_ACCEPTED"
    except BaseException as error:
        result.update(status="INCOMPLETE",error=f"{type(error).__name__}: {error}")
        raise
    finally:
        result["elapsed_seconds"]=time.monotonic()-start
        result["original_project_unchanged"]=store.project(origin["project_id"])==original_project
        result["original_source_bytes_unchanged"]=all(sha256_file(store.resolve_path(s["immutable_path"]))==s["sha256"] for s in baseline["sources"])
        if not result["original_project_unchanged"] or not result["original_source_bytes_unchanged"]:
            result["status"]="FAIL_ORIGINAL_PRESERVATION"
        atomic_json(out / "result.json",result)
        print(json.dumps({"directory":str(out),"status":result["status"],"elapsed_seconds":result["elapsed_seconds"]}),flush=True)


if __name__=="__main__":
    main()
