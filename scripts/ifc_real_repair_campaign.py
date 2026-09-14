"""Freeze and execute independently seeded repairs on actual IFC obstacles.

The fixed mission is an explicitly hypothetical service addition. Existing IFC
terminals, loads and connectivity are never invented. Original models stay intact.
Reference routes are independent eligibility witnesses and never optimizer input.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from oma.ifc.audit import atomic_json, sha256_file
from oma.ifc.cad import cad_check_routes, DEFAULT_SOURCE_REPRESENTATION_POLICY, VERTEX_HULL_SOURCE_REPRESENTATION_POLICY
from oma.ifc.export import export_route
from oma.routing.generator import segment_hits_boxes
from oma.routing.engine import route_project_run
from oma.store import Store, digest
from oma.worker import WorkerControl, import_sources


def frozen_scenarios(audit, max_probes=12, source_representation_policy=DEFAULT_SOURCE_REPRESENTATION_POLICY):
    """Deterministic eligibility construction from classes and actual bounds."""
    physical = [r for r in audit["products"] if r["physical"] and r.get("bounds")]
    lower = np.asarray([r["bounds"]["min"] for r in physical])
    upper = np.asarray([r["bounds"]["max"] for r in physical])
    candidates = [r for r in physical if r["type"] in {"IfcColumn", "IfcBeam", "IfcWall", "IfcWallStandardCase"}]
    candidates.sort(key=lambda r: ({"IfcColumn":0,"IfcBeam":1}.get(r["type"],2), float(np.prod(np.array(r["bounds"]["max"])-r["bounds"]["min"])), r["step_id"]))
    probes, dispositions = [], []
    for target in candidates:
        lo, hi = np.array(target["bounds"]["min"]), np.array(target["bounds"]["max"])
        extent, center = hi-lo, (lo+hi)/2
        if min(extent[:2]) <= .02 or min(extent[:2]) > 1.2 or extent[2] < .15:
            dispositions.append({"target_id":target["entity_id"],"status":"INELIGIBLE_SIZE_OR_ORIENTATION"})
            continue
        for axis in np.argsort(extent[:2]):
            axis = int(axis)
            perpendicular = 1-axis
            start, end = center.copy(), center.copy()
            start[axis], end[axis] = lo[axis]-.8, hi[axis]+.8
            # Conservative preliminary endpoint exclusion is only a selection
            # heuristic; the independent full-body checker controls eligibility.
            if any(np.any(np.all((p >= lower-.08) & (p <= upper+.08), axis=1)) for p in (start,end)):
                dispositions.append({"target_id":target["entity_id"],"axis":axis,"status":"ENDPOINTS_BLOCKED_BY_REPRESENTED_BOUNDS"})
                continue
            for sign in (-1,1):
                offset = lo[perpendicular]-.9 if sign < 0 else hi[perpendicular]+.9
                first, second = start.copy(), end.copy()
                first[perpendicular] = second[perpendicular] = offset
                points = [start.tolist(),first.tolist(),second.tolist(),end.tolist()]
                zone_lo = np.minimum.reduce(np.array(points))-.5
                zone_hi = np.maximum.reduce(np.array(points))+.5
                spec = {"start":start.tolist(),"end":end.tolist(),"system_type":"PRESSURE_PIPE",
                        "diameter_m":.1,"insulation_m":.02,"bend_radius_m":.3,"minimum_straight_m":.05,
                        "clearance_m":.1,"allowed_zone":{"min":zone_lo.tolist(),"max":zone_hi.tolist()},
                        "scenario_terminals":True,"max_candidates":18,"search_step_m":.2,
                        "source_id":audit["source_sha256"],"provenance":"OMA frozen planted direct-route interference on actual immutable IFC geometry",
                        "source":"OMA-REPAIR independent real-model campaign",
                        "source_representation_policy":source_representation_policy,
                        "assumptions":["Hypothetical added service terminals, not imported existing terminals",
                                       "Fixed100mm service+20mm insulation+100mm clearance; no hydraulic adequacy claim",
                                       "Original architecture/structure protected; proposed service addition must remain"]}
                identifier = digest({"source":audit["source_sha256"],"target":target["entity_id"],"axis":axis,"side":sign,"representation_policy":source_representation_policy})[:20]
                probes.append({"scenario_id":identifier,"target_id":target["entity_id"],"target_guid":target["ifc_guid"],
                               "target_type":target["type"],"mission":spec,"reference_points_m":points})
                if len(probes) >= max_probes:
                    return probes, dispositions
    return probes, dispositions


def route_spec(mission, route_id, points):
    return {k:mission[k] for k in ("system_type","diameter_m","insulation_m","bend_radius_m","minimum_straight_m")} | {
        "route_id":route_id,"points_m":points,"assumption_root":digest(mission)}


def run_project(project, *, store_dir, max_probes=12, budget=1200, execute_optimizer=True,
                source_representation_policy=DEFAULT_SOURCE_REPRESENTATION_POLICY, source_stems=None, scenario_ids=None):
    output = ROOT / "evidence/benchmarks/real-repair" / project
    if source_representation_policy != DEFAULT_SOURCE_REPRESENTATION_POLICY:
        output = output / "source-vertex-hull"
    output.mkdir(parents=True, exist_ok=True)
    acquisition = json.loads((ROOT / "evidence/ifc/acquisition.json").read_text(encoding="utf-8"))
    sources = [r for r in acquisition["files"] if r["is_ifc"] and r["project"] == project]
    # Deterministic primary discipline and separate hospital schema tracks.
    sources.sort(key=lambda r:(Path(r["path"]).stem not in ("arc","arc_ifc2x3"),r["path"]))
    results_path=output / "results.json"
    results = json.loads(results_path.read_text(encoding="utf-8"))["records"] if results_path.exists() else []
    for entry in sources:
        stem = Path(entry["path"]).stem
        if source_stems and stem not in source_stems:
            results.append({"source":entry["path"],"status":"NOT_ATTEMPTED_EXPLICIT_CAMPAIGN_SOURCE_SELECTION"})
            continue
        source = ROOT / entry["local_path"]
        audit_path = ROOT / f"evidence/ifc/audits/{project}/{stem}-{entry['sha256'][:12]}.audit.json"
        if not audit_path.exists():
            results.append({"source":entry["path"],"status":"BLOCKED_AUDIT_NOT_AVAILABLE"})
            continue
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        frozen_path = output / f"{stem}.frozen.json"
        if frozen_path.exists():
            frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
            if frozen["source_sha256"] != sha256_file(source):
                raise ValueError("Frozen scenario source changed")
        else:
            scenarios, dispositions = frozen_scenarios(audit,max_probes,source_representation_policy)
            frozen = {"specification_version":"oma-real-repair/1","source_sha256":entry["sha256"],
                      "source":entry["path"],"dataset_revision":acquisition["revision"],
                      "source_representation_policy":source_representation_policy,
                      "scenarios":scenarios,"eligibility_dispositions":dispositions,
                      "denominator_frozen":len(scenarios),"reference_hidden_from_optimizer":True}
            frozen["specification_root"] = digest(frozen)
            atomic_json(frozen_path,frozen)
        if not frozen["scenarios"]:
            results.append({"source":entry["path"],"status":"INELIGIBLE_NO_APPROPRIATE_OBSTACLE_SCENARIO","scenario_count":0})
            continue
        for scenario in frozen["scenarios"]:
            scenario_id = scenario["scenario_id"]
            if scenario_ids and scenario_id not in scenario_ids:
                continue
            folder = ROOT / "data/outputs/real-repair" / project / scenario_id
            folder.mkdir(parents=True, exist_ok=True)
            record = {"source":entry["path"],"source_sha256":entry["sha256"],"scenario_id":scenario_id,
                      "specification_root":frozen["specification_root"],"target_id":scenario["target_id"],"status":"ATTEMPTING"}
            try:
                for name,points in (("planted_direct",[scenario["mission"]["start"],scenario["mission"]["end"]]),
                                    ("independent_reference",scenario["reference_points_m"])):
                    exported = folder / f"{name}.ifc"
                    mp = exported.with_suffix(".manifest.json")
                    materialized = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else export_route(source,exported,route_spec(scenario["mission"],name+scenario_id,points))
                    evidence_path = output / f"{scenario_id}-{name}.json"
                    checked = cad_check_routes([source],exported,{p["ifc_guid"] for p in materialized["added_parts"]},
                                               clearance_m=scenario["mission"]["clearance_m"],output_path=evidence_path,
                                               cache_directory=Path(store_dir)/"cad-cache",source_representation_policy=source_representation_policy)
                    record[name] = {"status":checked["coordination_status"],"check_path":str(evidence_path.relative_to(ROOT)),
                                    "failed_pairs":checked["failed_pairs"],"unknown_pairs":checked["unknown_pairs"],
                                    "missing_geometry_count":len(checked["missing_geometry"]),"invalid_count":len(checked["invalid_solids"]),
                                    "performance":checked["performance"]}
                if record["planted_direct"]["status"] != "FAIL":
                    record["status"] = "INELIGIBLE_PLANTED_INTERFERENCE_NOT_CONFIRMED"
                elif record["independent_reference"]["status"] != "PASS":
                    record["status"] = "INELIGIBLE_NO_CHECKED_REFERENCE"
                elif not execute_optimizer:
                    record["status"] = "ELIGIBLE_REFERENCE_CHECKED"
                else:
                    store = Store(store_dir)
                    created = store.create_project(f"{project.replace('_',' ').title()} • local repair benchmark", {"sources":[],"entities":[]})
                    imported = store.create_run(created["id"],{"operation":"import","paths":[str(source)]})
                    import_sources(store,imported,WorkerControl(store,imported["id"]))
                    run = store.create_run(created["id"],{"operation":"route","mission":scenario["mission"],"budget_seconds":budget})
                    record.update(project_id=created["id"],run_id=run["id"])
                    route_project_run(store,run,WorkerControl(store,run["id"]))
                    candidates = store.candidates(created["id"])
                    checked = [c for c in candidates if c["status"] == "CHECKED"]
                    record.update(project_id=created["id"],run_id=run["id"],run_status=store.run(run["id"])["status"],
                                  candidates=[{"id":c["id"],"status":c["status"],"report_root":c.get("report_root")} for c in candidates],
                                  status="REPAIRED_CHECKED" if checked else "NO_CHECKED_REPAIR")
                    if checked:
                        from oma.verification import CHECKER_VERSION
                        selected = min(checked,key=lambda c:store.get(c["report_root"])["objective"]["length_m"])
                        accepted = store.accept(created["id"],selected["id"],store.project(created["id"])["revision"],"real-repair:"+scenario_id,checker_version=CHECKER_VERSION)
                        record.update(accepted_candidate=selected["id"],accepted_revision=accepted["revision"],report=store.get(selected["report_root"]))
                results.append(record)
                atomic_json(output / "results.json",{"project":project,"files_discovered":len(sources),"records":results})
                print(json.dumps({k:record.get(k) for k in ("source","scenario_id","status","project_id")}),flush=True)
                if record["status"] == "REPAIRED_CHECKED":
                    return results
            except Exception as exc:
                if record.get("run_id"):
                    store.update_run(record["run_id"],"FAILED",f"Real repair campaign: {type(exc).__name__}: {exc}","campaign_failure")
                record.update(status="FAILED",error=f"{type(exc).__name__}: {exc}")
                results.append(record)
                atomic_json(output / "results.json",{"project":project,"files_discovered":len(sources),"records":results})
                print(json.dumps({k:record.get(k) for k in ("source","scenario_id","status","error")}),flush=True)
        # Record each file separately; never call architecture-only input MEP proof.
    atomic_json(output / "results.json",{"project":project,"files_discovered":len(sources),"records":results})
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project",action="append",required=True)
    parser.add_argument("--store",default=str(ROOT / ".oma"))
    parser.add_argument("--max-probes",type=int,default=12)
    parser.add_argument("--budget",type=int,default=1200)
    parser.add_argument("--probe-only",action="store_true")
    parser.add_argument("--source-stem",action="append")
    parser.add_argument("--scenario-id",action="append")
    parser.add_argument("--representation-policy",choices=[DEFAULT_SOURCE_REPRESENTATION_POLICY,VERTEX_HULL_SOURCE_REPRESENTATION_POLICY],default=DEFAULT_SOURCE_REPRESENTATION_POLICY)
    args=parser.parse_args()
    for project in args.project:
        run_project(project,store_dir=args.store,max_probes=args.max_probes,budget=args.budget,execute_optimizer=not args.probe_only,
                    source_representation_policy=args.representation_policy,source_stems=args.source_stem,scenario_ids=args.scenario_id)
