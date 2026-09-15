"""Recompute one positive forbidden-volume witness for a frozen planted route.

This target-only check can establish failure, never feasibility or acceptance.
Complete independent references and candidate checks retain all source objects.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from oma.ifc.audit import atomic_json,sha256_file
from oma.ifc.cad import CODE_SHA256,load_cad,check_pair,_source_preservation_evidence,_transform_object
from oma.store import digest


def failure_witness(source_paths,planted,scenario,datum,output):
    started=time.perf_counter()
    manifest_path=Path(planted).with_suffix(".manifest.json")
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    roots={sha256_file(path):Path(path) for path in source_paths}
    target_root=scenario["target_id"].split(":")[0]
    source=roots.get(target_root)
    if source is None or manifest["source_sha256"] not in roots:
        raise ValueError("Frozen failure target or planted authoring source is outside the complete federation")
    if manifest["export_sha256"]!=sha256_file(planted):
        raise ValueError("Planted physical artifact changed")
    preservation=_source_preservation_evidence([roots[manifest["source_sha256"]]],planted)
    if preservation is None:
        raise ValueError("Planted export did not preserve its original authoring source")
    route_guids={p["ifc_guid"] for p in manifest["added_parts"]}
    routes,route_errors=load_cad(planted,guids=route_guids)
    targets,target_errors=load_cad(source,guids={scenario["target_guid"]})
    if len(targets)!=1 or targets[0].entity_id!=scenario["target_id"]:
        raise ValueError("Frozen failure target identity did not resolve uniquely")
    if datum.get("status")!="VERIFIED":
        raise ValueError("Failure witness requires verified federation coordinates")
    transforms={s["source_sha256"]:s["transform"] for s in datum["sources"]}
    routes=[_transform_object(route,transforms[manifest["source_sha256"]]) for route in routes]
    target=_transform_object(targets[0],transforms[target_root])
    pairs=[check_pair(route,target,clearance_m=0.) for route in routes]
    positive=[p for p in pairs if p["status"]=="FAIL" and p.get("reason")=="POSITIVE_COMMON_SOLID_VOLUME" and p["common_volume_m3"]>0]
    status="FAIL" if positive and not route_errors and not target_errors and all(r.valid for r in routes) and target.valid else "FAILURE_WITNESS_NOT_ESTABLISHED"
    result={"schema":"oma-targeted-forbidden-volume-witness/1","status":status,"scope":"TARGET_ONLY_FAILURE_WITNESS_NOT_FEASIBILITY",
        "source_count_in_frozen_federation":len(source_paths),"federation_source_sha256":sorted(roots),"target_id":scenario["target_id"],
        "target_guid":scenario["target_guid"],"scenario_id":scenario["scenario_id"],"scenario_root":digest(scenario),
        "planted_export_sha256":manifest["export_sha256"],"planted_manifest_sha256":sha256_file(manifest_path),
        "cad_code_sha256":CODE_SHA256,"route_parts_checked":len(routes),"source_obstacles_checked":1,"pairs_accounted":len(pairs),
        "pair_results":pairs,"failure_witnesses":positive,"source_preservation":preservation,"coordinate_evidence_root":digest(datum),
        "load_errors":route_errors+target_errors,"proof_level":"Numerical CAD positive common-volume witness; not a formal interval proof",
        "feasibility_verdict":"NOT_RUN","acceptance_authority":"NONE","full_reference_and_candidate_denominators_unchanged":True,
        "seconds":time.perf_counter()-started}
    atomic_json(Path(output),result)
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    frozen=json.loads(args.frozen.read_text(encoding="utf-8"))
    if digest({k:v for k,v in frozen.items() if k!="specification_root"})!=frozen["specification_root"]:
        raise ValueError("Frozen federation specification changed")
    from oma.ifc.federation import audited_local_federation
    paths=[ROOT/"data/ifc-bench"/s["path"] for s in frozen["sources"]]
    audits=[{"source_path":str(path.resolve()),"source_sha256":s["sha256"],"units":{"status":"KNOWN"}} for path,s in zip(paths,frozen["sources"])]
    datum=audited_local_federation(audits,frozen["sources"][0]["sha256"])
    if datum!=frozen["coordinate_evidence"]:
        raise ValueError("Frozen federation datum no longer matches actual source evidence")
    planted=ROOT/"data/outputs/real-repair"/frozen["project"]/frozen["scenario"]["scenario_id"]/"planted_direct.ifc"
    result=failure_witness(paths,planted,frozen["scenario"],datum,args.output)
    print(json.dumps({key:result[key] for key in ("status","scope","target_id","failure_witnesses","seconds")}))
