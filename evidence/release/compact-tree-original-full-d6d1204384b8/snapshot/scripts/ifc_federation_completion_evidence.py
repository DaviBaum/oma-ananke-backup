"""Bind the completed federation export to every retained campaign attempt."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "src"))
from oma.ifc.audit import atomic_json, sha256_file
from oma.store import Store, digest, utcnow


def main():
    store=Store(ROOT / ".oma")
    directory=ROOT / "evidence/benchmarks/real-repair/digital_hub"
    candidate_id="4bcf73e8605844908a5d550dcbf5a9a1"
    completion_path=directory / (candidate_id+".federation-accepted-export.json")
    completion=json.loads(completion_path.read_text())
    assert completion["status"]=="CHECKED_ACCEPTED_EXPORTED_RECHECKED"
    candidate=store.candidate(candidate_id)
    state=store.get(candidate["state_root"])
    run=store.run(candidate["run_id"])
    frozen_path=directory / "source-vertex-hull/federation/b0ee53f5755e4a951762.frozen.json"
    frozen=json.loads(frozen_path.read_text())
    assert frozen["specification_root"]==digest({k:v for k,v in frozen.items() if k!="specification_root"})
    assert run["request"]["mission"]==frozen["scenario"]["mission"]
    attempt=directory / "source-vertex-hull/federation/attempts/834613f116dd45e7a0c627fe02f1c791"
    prior=json.loads((attempt / "result.json").read_text())
    reference=json.loads((attempt / "independent-reference.check.json").read_text())
    semantics=json.loads((attempt / "independent-reference.semantics.json").read_text())
    assert reference["status"]==semantics["status"]=="PASS"
    assert not semantics["semantics"]["errors"] and not semantics["native_errors"]
    assert all(p["status"]=="PASS" for p in semantics["native_caps"])
    assert sha256_file(attempt / "corrected-independent-reference.ifc")==reference["export_sha256"]==semantics["export_sha256"]
    reports={label:store.get(completion[key]) for label,key in [("accepted","original_report_root"),("exported","export_report_root")]}
    native={label:store.get(next(r for r in report["results"] if r["id"]=="physical-interference-and-clearance")["witness"]["artifact"])
            for label,report in reports.items()}
    source_hashes={row["sha256"] for row in frozen["sources"]}
    for evidence in [reference,*native.values()]:
        assert evidence["status"]=="PASS" and evidence["obstacle_count"]==4820 and evidence["pairs_accounted"]==24100
        assert not any(evidence[k] for k in ("failed_pairs","unknown_pairs","blocked_pairs"))
        assert {row["sha256"] for row in evidence["sources"]}==source_hashes
    for source in state["sources"]:
        assert sha256_file(store.resolve_path(source["immutable_path"]))==source["sha256"]
    attempts=[]
    for original in prior["candidates"]:
        observed=store.candidate(original["id"])
        assert observed["run_id"]==run["id"] and not observed.get("export_recheck")
        report=store.get(observed["report_root"])
        attempts.append({"candidate_id":observed["id"],"state_root":observed["state_root"],
            "original_status":original["status"],"original_report_root":original["report_root"],
            "observed_status":observed["status"],"observed_report_root":observed["report_root"],
            "checker_version":report["checker_version"],"objective":report["objective"]})
    actual=[c for c in store.candidates(candidate["project_id"]) if c["run_id"]==run["id"] and not c.get("export_recheck")]
    assert {c["id"] for c in actual}=={row["candidate_id"] for row in attempts}
    ref_length=semantics["semantics"]["length_m"]
    length=reports["accepted"]["objective"]["length_m"]
    inventory_path=directory / (candidate_id+".inventory-reconciliation.json")
    inventory=json.loads(inventory_path.read_text())
    assert inventory["status"]=="COMPLETE_SOURCE_DENOMINATOR_RECONCILED"
    def link(path):
        return {"path":str(path.relative_to(ROOT)),"sha256":sha256_file(path)}
    result={"status":"FEDERATION_REPAIR_ACCEPTED_EXPORTED_RECHECKED","created_at":utcnow(),
        "candidate_id":candidate_id,"project_id":candidate["project_id"],"run_id":run["id"],
        "candidate_root":candidate["state_root"],"checker_version":completion["checker_version"],
        "accepted_revision":completion["accepted_revision"],"completion":link(completion_path),
        "frozen_specification":link(frozen_path),"specification_root":frozen["specification_root"],
        "fixed_mission_exactly_equal":True,"source_count":len(source_hashes),
        "source_physical_records":4828,"obstacle_objects":4820,"accounted_assemblies":8,"pairs_per_complete_check":24100,
        "inventory_amendment":link(inventory_path),"optimizer_candidate_count":len(attempts),
        "optimizer_attempts":attempts,"optimizer_run_status":run["status"],"optimizer_run_detail":run["detail"],
        "export_verification_is_separate_from_optimizer_attempts":True,
        "reference_check":link(attempt / "independent-reference.check.json"),
        "reference_semantics":link(attempt / "independent-reference.semantics.json"),
        "reference_implementation":reference["implementation"],
        "reference_length_m":ref_length,"selected_length_m":length,"selected_minus_reference_m":length-ref_length,
        "reduction_percent_of_reference":100*(ref_length-length)/ref_length,"selected_fittings":reports["accepted"]["objective"]["fitting_count"],
        "comparison_scope":"Frozen independently checked feasible witness; no continuous or global optimality claim",
        "native_timings_seconds":{label:value["performance"]["total_seconds"] for label,value in native.items()},
        "reference_native_seconds":reference["performance"]["total_seconds"],
        "checked_scope":reports["accepted"]["scope"],"whole_building":"NOT_CERTIFIED",
        "engineering_limits":"Hypothetical added terminals and explicit source vertex-hull support interpretation; no hydraulic, geospatial or original-source solid-validity approval",
        "retained_failures":[link(p) for p in sorted(directory.glob(candidate_id+".*"))
             if any(part in p.name for part in ("timeout","postcondition"))],
        "postprocessing_note":"Native checks passed unchanged. Assembly assertions were corrected to retain legitimate NOT_APPLICABLE obligations and require the additional exported-federation correspondence PASS.",
        "native_reports":{label:{"report_root":completion["original_report_root" if label=="accepted" else "export_report_root"],
            "status":report["status"],"obligations":[{"id":r["id"],"status":r["status"]} for r in report["results"]]} for label,report in reports.items()}}
    output=directory / (candidate_id+".federation-completion-summary.json")
    atomic_json(output,result)
    print(json.dumps({k:result[k] for k in ["status","source_count","optimizer_candidate_count","selected_length_m","reduction_percent_of_reference","native_timings_seconds"]}),flush=True)


if __name__=="__main__":
    main()
