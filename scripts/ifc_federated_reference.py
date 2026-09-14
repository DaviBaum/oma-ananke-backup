"""Freeze an independently checked reference against a complete source federation."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from oma.ifc.audit import atomic_json,sha256_file
from oma.ifc.cad import cad_check_routes
from oma.ifc.federation import audited_local_federation
from oma.store import digest


def run(project,scenario_id,track=None,optimize=False,budget=1800):
    acquisition=json.loads((ROOT/"evidence/ifc/acquisition.json").read_text(encoding="utf-8"))
    entries=[e for e in acquisition["files"] if e["is_ifc"] and e["project"]==project
             and (not track or track in Path(e["path"]).stem)]
    entries.sort(key=lambda e:(Path(e["path"]).stem not in ("arc","arc_ifc2x3","arc_ifc4"),e["path"]))
    if not entries:
        raise ValueError("No source federation matches the explicit source selection")
    if any("ifc2x3" in e["path"] for e in entries) and any("ifc4" in e["path"] for e in entries):
        raise ValueError("Separate hospital schema tracks; select --track")
    folder=ROOT/"evidence/benchmarks/real-repair"/project/"source-vertex-hull"
    frozen=json.loads((folder/(Path(entries[0]["path"]).stem+".frozen.json")).read_text(encoding="utf-8"))
    if digest({k:v for k,v in frozen.items() if k!="specification_root"})!=frozen["specification_root"]:
        raise ValueError("Frozen source scenario specification digest mismatch")
    scenario=next(s for s in frozen["scenarios"] if s["scenario_id"]==scenario_id)
    source_paths=[ROOT/e["local_path"] for e in entries]
    audits=[{"source_path":str(p.resolve()),"source_sha256":e["sha256"],"units":{"status":"KNOWN"}} for p,e in zip(source_paths,entries)]
    datum=audited_local_federation(audits,entries[0]["sha256"])
    specification={"project":project,"scenario":scenario,"single_source_specification_root":frozen["specification_root"],
                   "sources":[{"path":e["path"],"sha256":e["sha256"]} for e in entries],
                   "scope":"ALL_SELECTED_FEDERATION_SOURCE_PHYSICAL_OBSTACLES",
                   "coordinate_evidence":datum,"reference_hidden_from_optimizer":True}
    specification["specification_root"]=digest(specification)
    target=folder/"federation"
    target.mkdir(exist_ok=True)
    locked=target/(scenario_id+".frozen.json")
    if locked.exists():
        previous=json.loads(locked.read_text(encoding="utf-8"))
        if (digest({k:v for k,v in previous.items() if k!="specification_root"})!=previous["specification_root"]
                or previous["specification_root"] != specification["specification_root"]):
            raise ValueError("Frozen federation specification changed")
    else:
        atomic_json(locked,specification)
    attempt_id=uuid.uuid4().hex
    attempt=target/"attempts"/attempt_id
    attempt.mkdir(parents=True,exist_ok=False)
    record={"attempt_id":attempt_id,"specification_root":specification["specification_root"],
            "scenario_id":scenario_id,"source_count":len(source_paths),"status":"ATTEMPTING",
            "started_at":time.time()}
    atomic_json(attempt/"attempt.json",record)
    if datum["status"]!="VERIFIED":
        atomic_json(attempt/"result.json",record|{"status":"BLOCKED_UNRESOLVED_LOCAL_DATUM","coordinate_evidence":datum})
        return
    reference=ROOT/"data/outputs/real-repair"/project/scenario_id/"independent_reference.ifc"
    manifest=json.loads(reference.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    # Frozen reference centerlines survive the port-convention amendment, but
    # old authored IFC bytes cannot supply current port-semantic evidence.
    record["original_reference_export_sha256"] = sha256_file(reference)
    if manifest.get("port_axis_convention") != "IFC_FLOW_AXIS_V1":
        from oma.ifc.export import export_route
        reference = attempt / "corrected-independent-reference.ifc"
        manifest = export_route(source_paths[0], reference, manifest["route_spec"])
        record["reference_regeneration"] = {"advisory":"IFC-PORT-001", "physical_requirements_changed":False,
            "corrected_export_sha256":manifest["export_sha256"], "scope":"Same frozen reference geometry, corrected port representation"}
    reference_source_transform=next(s["transform"] for s in datum["sources"] if s["source_sha256"]==manifest["source_sha256"])
    if reference_source_transform != [[1.,0.,0.,0.],[0.,1.,0.,0.],[0.,0.,1.,0.],[0.,0.,0.,1.]]:
        raise ValueError("Reference route was authored in a different source frame; explicitly re-export via inverse transform")
    last=time.monotonic()
    def checkpoint(stage):
        nonlocal last
        if time.monotonic()-last>30:
            print(json.dumps({"status":"CHECKING","stage":stage,"scenario_id":scenario_id}),flush=True)
            last=time.monotonic()
    checked=cad_check_routes(source_paths,reference,[p["ifc_guid"] for p in manifest["added_parts"]],
                            clearance_m=scenario["mission"]["clearance_m"],coordinate_evidence=datum,
                            source_representation_policy=scenario["mission"]["source_representation_policy"],
                            cache_directory=ROOT/".oma/cad-cache",checkpoint=checkpoint,
                            output_path=attempt/"independent-reference.check.json")
    from oma.ifc.cad import load_cad
    from oma.routing.checker import _semantics,check_physical_ports
    from oma.routing.scenario import RoutingScenario
    physical_scenario=RoutingScenario.model_validate(scenario["mission"])
    semantics=_semantics(reference,source_paths[0],manifest,physical_scenario)
    native,native_errors=load_cad(reference,guids={p["ifc_guid"] for p in manifest["added_parts"]})
    caps=check_physical_ports(reference,native)
    zone_complete=all(obj.valid and obj.bounds is not None and
        min(*(obj.bounds[i]-physical_scenario.allowed_zone.min[i] for i in range(3)),
            *(physical_scenario.allowed_zone.max[i]-obj.bounds[i+3] for i in range(3))) > 1e-6+obj.kernel_tolerance_m for obj in native)
    semantic_pass=not semantics["errors"] and not native_errors and len(caps)==2*len(manifest["added_parts"]) and all(p["status"]=="PASS" for p in caps) and zone_complete
    atomic_json(attempt/"independent-reference.semantics.json", {"status":"PASS" if semantic_pass else "FAIL",
        "semantics":semantics,"native_caps":caps,"native_errors":native_errors,"complete_zone_containment":zone_complete,
        "export_sha256":manifest["export_sha256"]})
    record["independent_reference"]={"status":checked["coordination_status"],"check_path":str((attempt/"independent-reference.check.json").relative_to(ROOT)),
                                     "physical_obstacles":checked["obstacle_count"],"failed_pairs":checked["failed_pairs"],
                                     "unknown_pairs":checked["unknown_pairs"],"blocked_pairs":checked["blocked_pairs"]}
    record["independent_reference"]["physical_semantics_status"]="PASS" if semantic_pass else "FAIL"
    record["status"]="ELIGIBLE_REFERENCE_CHECKED" if checked["coordination_status"]=="PASS" and semantic_pass else "INELIGIBLE_NO_CHECKED_FEDERATION_REFERENCE"
    atomic_json(attempt/"result.json",record)
    print(json.dumps({k:checked[k] for k in ("status","coordination_status","coordinate_status","obstacle_count","failed_pairs","unknown_pairs","blocked_pairs","performance")}),flush=True)
    if not optimize or checked["coordination_status"]!="PASS" or not semantic_pass:
        return record
    planted=ROOT/"data/outputs/real-repair"/project/scenario_id/"planted_direct.ifc"
    from ifc_planted_failure_witness import failure_witness
    bad=failure_witness(source_paths,planted,scenario,datum,attempt/"planted-direct.target-witness.json")
    record["planted_direct"]={"status":bad["status"],"check_path":str((attempt/"planted-direct.target-witness.json").relative_to(ROOT)),
                               "scope":bad["scope"],"source_obstacles_checked":1,"pairs_accounted":bad["pairs_accounted"],
                               "full_reference_and_candidate_denominators_unchanged":True}
    if bad["status"]!="FAIL":
        record["status"]="INELIGIBLE_PLANTED_INTERFERENCE_NOT_CONFIRMED"
        atomic_json(attempt/"result.json",record)
        return record
    from oma.store import Store
    from oma.worker import WorkerControl,import_sources
    from oma.routing.engine import route_project_run
    store=Store(ROOT/".oma")
    created=store.create_project(f"{project.replace('_',' ').title()} - full federation repair benchmark",{"sources":[],"entities":[]})
    imported=store.create_run(created["id"],{"operation":"import","paths":[str(p.resolve()) for p in source_paths]})
    record.update(project_id=created["id"],import_run_id=imported["id"],status="IMPORTING_ALL_FEDERATION_SOURCES")
    atomic_json(attempt/"result.json",record)
    try:
        import_sources(store,imported,WorkerControl(store,imported["id"]))
        run_state=store.create_run(created["id"],{"operation":"route","mission":scenario["mission"],"budget_seconds":budget})
        record.update(run_id=run_state["id"],status="OPTIMIZING")
        atomic_json(attempt/"result.json",record)
        route_project_run(store,run_state,WorkerControl(store,run_state["id"]))
        candidates=store.candidates(created["id"])
        record["candidates"]=[{"id":c["id"],"status":c["status"],"report_root":c.get("report_root")} for c in candidates]
        record["run_status"]=store.run(run_state["id"])["status"]
        record["status"]="REPAIRED_CHECKED_AWAITING_CURRENT_BUILD_ACCEPTANCE" if any(c["status"]=="CHECKED" for c in candidates) else "NO_CHECKED_REPAIR"
    except Exception as exc:
        record.update(status="FAILED",error=f"{type(exc).__name__}: {exc}")
        if record.get("run_id"):
            store.update_run(record["run_id"],"FAILED",record["error"],"federated_campaign_failure")
    atomic_json(attempt/"result.json",record)
    print(json.dumps(record),flush=True)
    return record


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project",required=True)
    parser.add_argument("--scenario-id",required=True)
    parser.add_argument("--track")
    parser.add_argument("--optimize",action="store_true")
    parser.add_argument("--budget",type=int,default=1800)
    args=parser.parse_args()
    run(args.project,args.scenario_id,args.track,args.optimize,args.budget)
