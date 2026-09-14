"""Freshly recertify, accept and independently recheck an actual repair export."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from oma.build_identity import checker_version,frozen_environment
from oma.exporting import export_project
from oma.ifc.audit import atomic_json,sha256_file
from oma.store import Store


def finalize(candidate_id,project_label):
    start=time.perf_counter()
    store=Store(ROOT/".oma")
    candidate=store.candidate(candidate_id)
    version=checker_version()
    print(json.dumps({"stage":"FRESH_CHECK","candidate_id":candidate_id,"checker_version":version}),flush=True)
    process=subprocess.run([sys.executable,"-m","oma.verification",str(store.directory),candidate_id],
                           capture_output=True,text=True,timeout=900,env=frozen_environment(store.directory),
                           creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    if process.returncode:
        raise RuntimeError(process.stderr[-5000:])
    checked=store.candidate(candidate_id)
    report=store.get(checked["report_root"])
    if checked["status"]!="CHECKED" or report["checker_version"]!=version or checker_version()!=version:
        raise RuntimeError("Current immutable build did not freshly check the complete proposed repair")
    print(json.dumps({"stage":"FRESHLY_CHECKED","status":checked["status"],"seconds":time.perf_counter()-start}),flush=True)
    project=store.project(candidate["project_id"])
    accepted=store.accept(project["id"],candidate_id,project["revision"],"final-native-real-repair:"+candidate_id,checker_version=version)
    print(json.dumps({"stage":"ACCEPTED","project_id":project["id"],"revision":accepted["revision"]}),flush=True)
    exported=export_project(store,project["id"],candidate_id,draft=False)
    bundle=Path(exported["directory"])
    attribution=[]
    for filename,destination in (("license.txt","source-license.txt"),("model_card.md","source-model-card.md")):
        original=ROOT/"data/ifc-bench/projects"/project_label/filename
        if original.exists():
            copied=bundle/destination
            shutil.copyfile(original,copied)
            attribution.append({"path":str(copied),"sha256":sha256_file(copied),"source_path":str(original)})
    result={"status":"CHECKED_ACCEPTED_EXPORTED_RECHECKED","candidate_id":candidate_id,"project_id":project["id"],
            "accepted_revision":accepted["revision"],"checker_version":version,"report_root":checked["report_root"],
            "candidate_root":checked["state_root"],"report":report,"export":exported,"source_attribution":attribution,
            "scope":"Local proposed routes under their explicitly frozen source representation interpretation; whole building not certified",
            "seconds":time.perf_counter()-start}
    request=store.run(candidate["run_id"])["request"]["mission"]
    comparisons=[]
    for frozen_path in (ROOT/"evidence/benchmarks/real-repair"/project_label).rglob("*.frozen.json"):
        frozen=json.loads(frozen_path.read_text(encoding="utf-8"))
        for scenario in frozen.get("scenarios",[]):
            if scenario["mission"]!=request:
                continue
            reference_path=ROOT/"data/outputs/real-repair"/project_label/scenario["scenario_id"]/"independent_reference.manifest.json"
            reference=json.loads(reference_path.read_text(encoding="utf-8"))
            reference_length=reference["length_m"]
            accepted_length=report["objective"]["length_m"]
            comparisons.append({"scenario_id":scenario["scenario_id"],"specification_root":frozen["specification_root"],
                "reference_length_m":reference_length,"accepted_length_m":accepted_length,
                "accepted_minus_reference_m":accepted_length-reference_length,
                "relative_reference_gap":(accepted_length-reference_length)/reference_length,
                "scope":"Comparison with independently checked frozen feasibility witness; no continuous optimality claim"})
    result["reference_comparisons"]=comparisons
    joint_references=[]
    for frozen_path in (ROOT/"evidence/benchmarks/real-repair"/project_label).rglob("*.joint-frozen.json"):
        frozen=json.loads(frozen_path.read_text(encoding="utf-8"))
        for scenario in frozen["scenarios"]:
            if scenario["mission"]!=request:
                continue
            lengths=[]
            for option in ("main","separated"):
                reference=ROOT/"data/outputs/real-repair"/project_label/"joint"/scenario["scenario_id"]/option/"reference.manifest.json"
                lengths.append(json.loads(reference.read_text(encoding="utf-8"))["length_m"])
            joint_references.append({"scenario_id":scenario["scenario_id"],"specification_root":frozen["specification_root"],
                "frozen_specification_path":str(frozen_path.relative_to(ROOT)),"reference_assignment_length_m":sum(lengths),
                "accepted_assignment_length_m":report["objective"]["length_m"],
                "scope":"Explicit independent-route design alternatives; examined incompatible crossing and feasible separated assignment, no continuous optimality claim"})
    result["joint_references"]=joint_references
    regeneration=[]
    for regeneration_path in (ROOT/"evidence/benchmarks/real-repair"/project_label/"port-regeneration").glob("*/result.json"):
        provenance=json.loads(regeneration_path.read_text(encoding="utf-8"))
        if provenance.get("candidate_id")==candidate_id:
            regeneration.append({"path":str(regeneration_path.relative_to(ROOT)),"sha256":sha256_file(regeneration_path),
                "previous_candidate_id":provenance["previous_candidate_id"],"previous_candidate_root":provenance["previous_candidate_root"],
                "fixed_request_root":provenance["fixed_request_root"],"route_mapping":provenance["route_mapping"],
                "scope":"Corrected port semantics for prior geometric proposal; no new optimizer comparison"})
    result["port_semantic_regeneration"]=regeneration
    atomic_json(ROOT/"evidence/benchmarks/real-repair"/project_label/(candidate_id+".accepted-export.json"),result)
    atomic_json(bundle/"repair-evidence.json",result)
    for frozen_path in (ROOT/"evidence/benchmarks/real-repair"/project_label).rglob("*.frozen.json"):
        frozen=json.loads(frozen_path.read_text(encoding="utf-8"))
        for scenario in frozen.get("scenarios",[]):
            if scenario["mission"]!=request:
                continue
            results_path=frozen_path.parent/"results.json"
            summary=json.loads(results_path.read_text(encoding="utf-8")) if results_path.exists() else {"project":project_label,"records":[]}
            summary["records"].append({"scenario_id":scenario["scenario_id"],"specification_root":frozen["specification_root"],
                "source":frozen["source"],"status":"REPAIRED_CHECKED_ACCEPTED_EXPORTED","candidate_id":candidate_id,
                "project_id":project["id"],"accepted_revision":accepted["revision"],"report_root":checked["report_root"],
                "accepted_objective":report["objective"],"selection_scope":"Explicit current-build feasible candidate; no best-of-run claim",
                "checked_export":exported,"evidence_path":str((ROOT/"evidence/benchmarks/real-repair"/project_label/(candidate_id+".accepted-export.json")).relative_to(ROOT))})
            atomic_json(results_path,summary)
    print(json.dumps({k:result[k] for k in ("status","candidate_id","project_id","accepted_revision","seconds","export")}),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate",required=True)
    parser.add_argument("--project-label",required=True)
    args=parser.parse_args()
    finalize(args.candidate,args.project_label)
