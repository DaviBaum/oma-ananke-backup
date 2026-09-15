"""Frozen three-demand Office campaign for freshly checked conflict hints.

The original two-demand benchmark is retained byte-for-byte. This separately
declared mission adds a parallel third service with two lateral alternatives.
Its first two assignments repeat the original crossing; the remaining two
separate that crossing by the originally authorized elevation choice.
"""
import argparse
from copy import deepcopy
from datetime import datetime
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


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_RUN = "785da50c269c497cbbc96f05979a7b96"


def physical_metrics(store, report):
    """Count only work that the actual current native artifacts account for."""
    source, cross, hint = [], None, None
    for check in report["results"]:
        if check["id"].endswith(":physical-interference-and-clearance"):
            item = {"id": check["id"], "status": check["status"]}
            if check["status"] != "NOT_RUN":
                native = store.get(check["witness"]["artifact"])
                item.update({key: native[key] for key in (
                    "pairs_accounted", "obstacle_count", "route_count", "failed_pairs", "unknown_pairs", "blocked_pairs")})
            source.append(item)
        elif check["id"] == "cross-route-interference":
            cross = {"status": check["status"], **check["witness"]}
        elif check["id"] == "native-cross-route-counterexample":
            hint = store.get(check["witness"]["artifact"])
    return {"source_obligations": source,
        "completed_source_pairs": sum(s.get("pairs_accounted", 0) for s in source),
        "source_obligations_not_run": sum(s["status"] == "NOT_RUN" for s in source),
        "cross_route": cross, "fresh_counterexample": hint}


def require_hint_evidence(store, candidates, result):
    second = result["candidates"][1]
    metrics = second["physical_metrics"]
    hint = metrics["fresh_counterexample"]
    assert hint and hint["status"] == "FAIL"
    assert hint["probe_count"] == 1 and hint["supervision"]["status"] == "COMPLETED"
    assert hint["old_verdict_reused"] is False and hint["new_native_verification_performed"] is True
    assert hint["full_source_denominator"] == hint["full_cross_route_denominator"] == "NOT_RUN"
    assert hint["acceptance_authority"] == hint["objective_authority"] == "NONE"
    assert hint["witness"]["native_pair_result"]["status"] == "FAIL"
    assert metrics["completed_source_pairs"] == 0 and metrics["source_obligations_not_run"] == 3
    assert metrics["cross_route"]["status"] == "NOT_RUN" and second["objective"] == {}
    original_guids = set()
    for route in store.get(candidates[0]["state_root"])["routes"]:
        original_guids.update(p["ifc_guid"] for p in store.get(route["geometry_artifact"])["added_parts"])
    current_guids = hint["witness"]["native_pair_result"]["participant_guids"]
    assert len(current_guids) == 2 and not original_guids.intersection(current_guids)
    for candidate in result["candidates"][2:]:
        measured = candidate["physical_metrics"]
        assert measured["fresh_counterexample"] is None
        assert measured["completed_source_pairs"] == 2409 and measured["source_obligations_not_run"] == 0
        assert measured["cross_route"]["status"] == "PASS" and measured["cross_route"]["pairs_accounted"] == 3
        assert candidate["objective"] == {"length_m": 3.600000000000005, "fitting_count": 0.0}
    result["fresh_hint_assertions"] = {"status": "PASS", "repeated_pair_has_new_guids": True,
        "early_rejection_source_pairs_avoided": 2409, "passing_assignments_fully_checked": 2,
        "scope": "One repeated crossing in this explicit four-assignment mission; no global speedup or no-good cut claim"}


def specification(store):
    path = ROOT/"evidence/benchmarks/real-repair/wbdg_office/joint-demand/arc.joint-frozen.json"
    original = json.loads(path.read_text(encoding="utf-8"))
    scenario = original["scenarios"][0]
    mission = deepcopy(scenario["mission"])
    third = []
    for offset in (.4,.5):
        option = deepcopy(mission["route_demands"][0]["alternatives"][0])
        for key in ("start","end"):
            option[key][1] -= offset
        option["provenance"] = "Explicit frozen third parallel service for repeated-counterexample campaign"
        option["assumptions"].append("This third hypothetical service and its two lateral choices extend the separately retained two-demand mission")
        third.append(option)
    mission["route_demands"].append({"id":"parallel-third-service","alternatives":third})
    mission["max_joint_candidates"] = 4
    origin = store.run(ORIGINAL_RUN)
    baseline = store.get(origin["base_root"])
    assert not baseline.get("routes") and not baseline.get("physical_networks")
    assert origin["request"]["mission"] == scenario["mission"]
    result = {"schema":"oma.frozen-joint-counterexample-campaign/1",
        "original_specification_path":str(path),"original_specification_sha256":sha256_file(path),
        "original_specification_root":original["specification_root"],"original_run_id":ORIGINAL_RUN,
        "baseline_root":origin["base_root"],"source_sha256":[s["sha256"] for s in baseline["sources"]],
        "original_two_demands_unchanged":True,"new_third_demand_explicit":True,
        "mission":mission,"assignment_denominator":4,
        "scope":"Hypothetical fixed independent round services against every original source obstacle; no whole-building or continuous optimum claim"}
    result["specification_root"] = digest(result)
    return result, baseline, origin


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build",required=True)
    parser.add_argument("--label",required=True)
    parser.add_argument("--budget",type=float,default=1200.)
    parser.add_argument("--export",action="store_true")
    parser.add_argument("--require-hint", action="store_true")
    args = parser.parse_args()
    assert checker_version().endswith(args.build)
    assert os.environ.get("OMA_EXECUTABLE_BUILD","").endswith(args.build)
    store = Store(ROOT/".oma")
    spec,baseline,origin = specification(store)
    original_head = store.project(origin["project_id"])
    for source in baseline["sources"]:
        assert sha256_file(store.resolve_path(source["immutable_path"])) == source["sha256"]
    out = ROOT/"evidence/benchmarks/joint-counterexample/office"/uuid.uuid4().hex
    out.mkdir(parents=True)
    atomic_json(out/"specification.json",spec)
    project = store.create_project("Office three-demand counterexample campaign · "+args.label,baseline)
    run = store.create_run(project["id"],{"operation":"optimize","mission":spec["mission"],"budget_seconds":args.budget})
    started = time.monotonic()
    result = {"status":"RUNNING","label":args.label,"started_at":utcnow(),"checker_version":checker_version(),
        "script_sha256":sha256_file(__file__),"specification_root":spec["specification_root"],
        "project_id":project["id"],"run_id":run["id"],"baseline_root":run["base_root"],
        "candidate_acceptance_authority":"FRESH_COMPLETE_NATIVE_CHECK_ONLY","prior_native_verdict_reused":False}
    atomic_json(out/"result.json",result)
    print(json.dumps({"directory":str(out),"project_id":project["id"],"run_id":run["id"]}),flush=True)
    try:
        result["worker"] = supervise_check([sys.executable,"-m","oma.worker",str(store.directory),run["id"]],
            environment=frozen_environment(store.directory),directory=out/"worker",deadline=started+args.budget+30)
        result["run"] = store.run(run["id"])
        result["candidates"] = []
        candidates = [c for c in store.candidates(project["id"]) if c["run_id"] == run["id"] and not c.get("export_recheck")]
        for candidate in candidates:
            report = store.get(candidate["report_root"]) if candidate.get("report_root") else None
            atomic_json(out/(candidate["id"]+".candidate.json"),candidate)
            if report is not None:
                atomic_json(out/(candidate["id"]+".verification.json"),report)
                for check in report["results"]:
                    for key,value in (check.get("witness") or {}).items():
                        if key.endswith("artifact") and isinstance(value,str) and len(value)==64:
                            atomic_json(out/(value+".artifact.json"),store.get(value))
            result["candidates"].append({"id":candidate["id"],"status":candidate["status"],
                "assignment":candidate.get("physical_menu_assignment"),"root":candidate["state_root"],
                "report_root":candidate.get("report_root"),"objective":report.get("objective") if report else None,
                "physical_metrics":physical_metrics(store, report) if report else None,
                "checks":[{"id":c["id"],"status":c["status"]} for c in report["results"]] if report else []})
        events = store.events(project["id"],limit=10000)
        atomic_json(out/"events.json",events)
        assert result["worker"]["status"] == "COMPLETED", result["worker"]
        assert len(candidates) == 4, result["candidates"]
        assert [c["status"] for c in candidates] == ["REJECTED","REJECTED","CHECKED","CHECKED"], result["candidates"]
        for summary in result["candidates"]:
            start = next(e for e in events if e["run_id"] == run["id"] and e["stage"] == "joint_verification"
                         and e["payload"].get("candidate_id") == summary["id"])
            end = next(e for e in events if e["run_id"] == run["id"] and e["stage"] == "joint_selection"
                       and e["seq"] > start["seq"])
            summary["check_and_selection_seconds"] = (datetime.fromisoformat(end["timestamp"])
                - datetime.fromisoformat(start["timestamp"])).total_seconds()
        if args.require_hint:
            require_hint_evidence(store, candidates, result)
        completion = next(e for e in reversed(events) if e["run_id"]==run["id"] and e["stage"]=="complete")
        result["selection"] = completion
        selected_ids = completion["payload"]["selected_candidate_ids"]
        assert len(selected_ids)==1
        selected = next(c for c in candidates if c["id"]==selected_ids[0])
        result["selected_candidate_id"] = selected["id"]
        if args.export:
            result["acceptance"] = store.accept(project["id"],selected["id"],project["revision"],
                "three-demand-native-counterexample-campaign",checker_version=checker_version())
            result["export"] = export_project(store,project["id"],selected["id"],draft=False,budget_seconds=args.budget)
            manifest = store.get(result["export"]["artifact_root"])
            report = store.get(manifest["verification_root"])
            atomic_json(out/"export.manifest.json",manifest)
            atomic_json(out/"export.verification.json",report)
            assert report["status"]=="PASS" and report["checker_version"]==checker_version()
            assert report["candidate_root"]==manifest["exported_state_root"]
            assert all(manifest["checking"]["release_bindings"].values())
            assert all(sha256_file(f["path"])==f["sha256"] for f in manifest["files"])
        result["status"] = "FOUR_FROZEN_ASSIGNMENTS_CHECKED"+("_ACCEPTED_EXPORTED_RECHECKED" if args.export else "")
    except BaseException as error:
        result.update(status="INCOMPLETE",error=f"{type(error).__name__}: {error}")
        raise
    finally:
        result["elapsed_seconds"] = time.monotonic()-started
        result["original_project_unchanged"] = store.project(origin["project_id"])==original_head
        result["original_source_bytes_unchanged"] = all(sha256_file(store.resolve_path(s["immutable_path"]))==s["sha256"] for s in baseline["sources"])
        if not result["original_project_unchanged"] or not result["original_source_bytes_unchanged"]:
            result["status"] = "FAIL_ORIGINAL_PRESERVATION"
        atomic_json(out/"result.json",result)
        print(json.dumps({"status":result["status"],"directory":str(out),"elapsed_seconds":result["elapsed_seconds"]}),flush=True)


if __name__=="__main__":
    main()
