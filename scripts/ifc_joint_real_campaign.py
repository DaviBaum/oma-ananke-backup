"""Freeze real-model two-demand alternatives and independently check eligibility."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
import time
import uuid

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from oma.ifc.audit import atomic_json,sha256_file
from oma.ifc.cad import cad_check_routes,load_cad,check_pair,VERTEX_HULL_SOURCE_REPRESENTATION_POLICY
from oma.ifc.export import export_route
from oma.routing.engine import route_project_run
from oma.store import Store,digest
from oma.worker import WorkerControl,import_sources


def select_spaces(audit,max_probes):
    physical=[p for p in audit["products"] if p["physical"] and p.get("bounds")]
    lower=np.array([p["bounds"]["min"] for p in physical]);upper=np.array([p["bounds"]["max"] for p in physical])
    spaces=sorted([p for p in audit["products"] if p["type"]=="IfcSpace" and p.get("bounds")],key=lambda p:p["step_id"])
    scenarios=[];dispositions=[]
    for space in spaces:
        lo=np.array(space["bounds"]["min"]);hi=np.array(space["bounds"]["max"])
        if min((hi-lo)[:2])<1.7 or hi[2]-lo[2]<1.1:
            dispositions.append({"space_id":space["entity_id"],"status":"HEURISTIC_SPACE_BOUNDS_TOO_SMALL"});continue
        for height_fraction in (.65,.4):
            center=(lo+hi)/2;center[2]=lo[2]+height_fraction*(hi[2]-lo[2])
            for elevation_sign in (1,-1):
                first=[(center+[-.6,0,0]).tolist(),(center+[.6,0,0]).tolist()]
                crossing=[(center+[0,-.6,0]).tolist(),(center+[0,.6,0]).tolist()]
                separated=[(np.array(p)+[0,0,elevation_sign*.35]).tolist() for p in crossing]
                all_points=np.array(first+crossing+separated)
                zone_lo=all_points.min(axis=0)-.2;zone_hi=all_points.max(axis=0)+.2
                identity={"source_sha256":audit["source_sha256"],"space_id":space["entity_id"],"height_fraction":height_fraction,
                          "elevation_sign":elevation_sign,"version":1}
                if np.any(zone_lo<lo) or np.any(zone_hi>hi):
                    dispositions.append(identity|{"status":"HEURISTIC_ZONE_OUTSIDE_SOURCE_SPACE_BOUNDS"});continue
                hits=set()
                for points in (first,crossing,separated):
                    a,b=np.array(points)
                    indices=np.flatnonzero(np.all((np.maximum(a,b)+.19>=lower)&(np.minimum(a,b)-.19<=upper),axis=1))
                    hits.update(physical[int(i)]["entity_id"] for i in indices)
                if hits:
                    dispositions.append(identity|{"status":"HEURISTIC_REFERENCE_ENVELOPE_OVERLAP","entity_ids":sorted(hits)});continue
                common={"system_type":"PRESSURE_PIPE","diameter_m":.1,"insulation_m":.02,"bend_radius_m":.3,
                        "minimum_straight_m":.05,"clearance_m":.1,"scenario_terminals":True,"max_candidates":1,
                        "source_id":audit["source_sha256"],"source_representation_policy":VERTEX_HULL_SOURCE_REPRESENTATION_POLICY,
                        "allowed_zone":{"min":zone_lo.tolist(),"max":zone_hi.tolist()},
                        "provenance":"Explicit frozen real-model simultaneous service options",
                        "source":"OMA independently checked real IFC multi-demand campaign",
                        "assumptions":["Hypothetical terminals and explicitly authorized elevation options; existing service intent is not inferred",
                                       "Fixed 100 mm service, 20 mm insulation and 100 mm clearance",
                                       "Source-space bounds only select a hypothetical zone; actual room containment and hydraulic adequacy are not asserted"]}
                first_scenario=common|{"start":first[0],"end":first[1]}
                crossing_scenario=common|{"start":crossing[0],"end":crossing[1]}
                separated_scenario=common|{"start":separated[0],"end":separated[1]}
                mission={"route_demands":[{"id":"main","alternatives":[first_scenario]},
                                          {"id":"crossing-service","alternatives":[crossing_scenario,separated_scenario]}],
                         "max_joint_candidates":2,"max_paths_per_alternative":1}
                scenarios.append({"scenario_id":digest(identity)[:20],"source_space_id":space["entity_id"],"selection":identity,
                                  "mission":mission,"reference_options":{"main":first_scenario,"crossing":crossing_scenario,"separated":separated_scenario}})
                if len(scenarios)>=max_probes:
                    return scenarios,dispositions
    return scenarios,dispositions


def run(project,max_probes=4,execute=False,budget=900):
    acquisition=json.loads((ROOT/"evidence/ifc/acquisition.json").read_text(encoding="utf-8"))
    entry=next(e for e in acquisition["files"] if e["is_ifc"] and e["project"]==project and Path(e["path"]).stem=="arc")
    source=ROOT/entry["local_path"]
    audit=json.loads((ROOT/f"evidence/ifc/audits/{project}/arc-{entry['sha256'][:12]}.audit.json").read_text(encoding="utf-8"))
    folder=ROOT/"evidence/benchmarks/real-repair"/project/"joint-demand"
    folder.mkdir(parents=True,exist_ok=True)
    frozen_path=folder/"arc.joint-frozen.json"
    if frozen_path.exists():
        frozen=json.loads(frozen_path.read_text(encoding="utf-8"))
        if digest({k:v for k,v in frozen.items() if k!="specification_root"})!=frozen["specification_root"]:
            raise ValueError("Frozen simultaneous scenario specification digest mismatch")
        if frozen["source_sha256"]!=sha256_file(source):
            raise ValueError("Frozen real source changed")
    else:
        scenarios,dispositions=select_spaces(audit,max_probes)
        frozen={"schema":"oma-real-ifc-joint-campaign/1","source":entry["path"],"source_sha256":entry["sha256"],
                "dataset_revision":acquisition["revision"],"scenarios":scenarios,"eligibility_dispositions":dispositions,
                "frozen_scenario_denominator":len(scenarios),"reference_hidden_from_optimizer":True}
        frozen["specification_root"]=digest(frozen);atomic_json(frozen_path,frozen)
    for scenario in frozen["scenarios"]:
        attempt=folder/"attempts"/uuid.uuid4().hex;attempt.mkdir(parents=True,exist_ok=False)
        record={"scenario_id":scenario["scenario_id"],"specification_root":frozen["specification_root"],"status":"ATTEMPTING"}
        atomic_json(attempt/"attempt.json",record)
        materialized={};checks={};bodies={}
        for name,mission in scenario["reference_options"].items():
            geometry=ROOT/"data/outputs/real-repair"/project/"joint"/scenario["scenario_id"]/name
            geometry.mkdir(parents=True,exist_ok=True);path=geometry/"reference.ifc"
            manifest_path=path.with_suffix(".manifest.json")
            spec={k:mission[k] for k in ("system_type","diameter_m","insulation_m","bend_radius_m","minimum_straight_m")}
            spec.update(route_id=f"joint-reference-{scenario['scenario_id']}-{name}",points_m=[mission["start"],mission["end"]],assumption_root=digest(mission))
            material=json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else export_route(source,path,spec)
            guids={p["ifc_guid"] for p in material["added_parts"]}
            checked=cad_check_routes([source],path,guids,clearance_m=.1,source_representation_policy=VERTEX_HULL_SOURCE_REPRESENTATION_POLICY,
                                     cache_directory=ROOT/".oma/cad-cache",output_path=attempt/(name+".check.json"))
            objects,errors=load_cad(path,guids=guids)
            checks[name]={"status":checked["coordination_status"],"physical_source_obstacles":checked["obstacle_count"],
                          "check_path":str((attempt/(name+".check.json")).relative_to(ROOT))}
            if errors or len(objects)!=1:
                raise ValueError("Frozen straight reference must produce exactly one native solid")
            materialized[name]=material;bodies[name]=objects[0]
        bad=check_pair(bodies["main"],bodies["crossing"],clearance_m=.1)
        good=check_pair(bodies["main"],bodies["separated"],clearance_m=.1)
        record.update(source_checks=checks,incompatible_cross_route_check=bad,feasible_cross_route_check=good)
        eligible=all(c["status"]=="PASS" for c in checks.values()) and bad["status"]=="FAIL" and good["status"]=="PASS"
        record["status"]="ELIGIBLE_INDEPENDENT_JOINT_REFERENCE" if eligible else "INELIGIBLE_REFERENCE"
        atomic_json(attempt/"result.json",record)
        print(json.dumps({"scenario_id":scenario["scenario_id"],"status":record["status"]}),flush=True)
        if not eligible or not execute:
            continue
        store=Store(ROOT/".oma")
        created=store.create_project(f"{project.replace('_',' ').title()} - simultaneous service benchmark",{"sources":[],"entities":[]})
        imported=store.create_run(created["id"],{"operation":"import","paths":[str(source.resolve())]})
        record.update(project_id=created["id"],import_run_id=imported["id"])
        atomic_json(attempt/"result.json",record)
        import_sources(store,imported,WorkerControl(store,imported["id"]))
        proposed=store.create_run(created["id"],{"operation":"optimize","mission":scenario["mission"],"budget_seconds":budget})
        record.update(run_id=proposed["id"],status="OPTIMIZING");atomic_json(attempt/"result.json",record)
        route_project_run(store,proposed,WorkerControl(store,proposed["id"]))
        candidates=store.candidates(created["id"])
        record["candidates"]=[{"id":c["id"],"status":c["status"],"report_root":c.get("report_root")} for c in candidates]
        record["status"]="JOINT_ASSIGNMENT_CHECKED" if any(c["status"]=="CHECKED" for c in candidates) else "NO_CHECKED_JOINT_ASSIGNMENT"
        atomic_json(attempt/"result.json",record);print(json.dumps(record),flush=True)
        return record


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project",required=True)
    parser.add_argument("--max-probes",type=int,default=4)
    parser.add_argument("--execute",action="store_true")
    parser.add_argument("--budget",type=int,default=900)
    args=parser.parse_args()
    run(args.project,args.max_probes,args.execute,args.budget)
