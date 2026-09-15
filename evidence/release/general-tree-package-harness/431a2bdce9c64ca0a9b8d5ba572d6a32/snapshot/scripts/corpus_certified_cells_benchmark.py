"""Retain actual IFC evidence for the bounded source-bound route-cell adapter."""
from pathlib import Path
import argparse
import json
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT/"tests"))

from oma.ifc.audit import atomic_json, sha256_file
from oma.ifc.cad import cad_check_routes
from oma.ifc.export import export_route
from oma.routing.certified_cells import build_certified_cell_proposals
from oma.store import Store, digest
from test_certified_cells import _scenario, _sources
from test_ifc_openings import host_fixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--office-candidate",default="f583693cce4644ad8306b31d51c8540f")
    parser.add_argument("--budget",type=float,default=300.)
    parser.add_argument("--skip-office",action="store_true")
    args = parser.parse_args()
    evidence_root = ROOT/"evidence/math/certified-cells"
    out = evidence_root/"attempts"/uuid.uuid4().hex
    out.mkdir(parents=True,exist_ok=True)
    source,_ = host_fixture(out/"analytic-wall.ifc")
    scenario = _scenario()
    synthetic = build_certified_cell_proposals(_sources(source),scenario,context_root=digest({"source":sha256_file(source),"scenario":scenario.model_dump(mode="json")}),
        grid_divisions=6,deadline=time.monotonic()+args.budget)
    atomic_json(out/"analytic-wall.cell-report.json",synthetic)
    native_attempts = []
    for index,proposal in enumerate(synthetic["proposals"]):
        destination = out/f"analytic-detour-{index}.ifc"
        try:
            manifest = export_route(source,destination,{"route_id":f"certified-cell-analytic-{index}","system_type":scenario.system_type,
                "points_m":proposal["points_m"],"diameter_m":scenario.diameter_m,"insulation_m":scenario.insulation_m,
                "bend_radius_m":scenario.bend_radius_m,"minimum_straight_m":scenario.minimum_straight_m},fresh_recheck=False)
            native = cad_check_routes([source],destination,{p["ifc_guid"] for p in manifest["added_parts"]},clearance_m=scenario.clearance_m)
            atomic_json(out/f"analytic-detour-{index}.native-check.json",native)
            native_attempts.append({"proposal_index":index,"status":native["status"],"pairs_accounted":native["pairs_accounted"],
                "obstacle_count":native["obstacle_count"],"ifc_sha256":sha256_file(destination)})
            if native["status"] == "PASS": break
        except (ValueError,RuntimeError) as error:
            native_attempts.append({"proposal_index":index,"status":"MATERIALIZATION_REJECTED","reason":str(error)})
    summary = {"scope":"FRESH_SOURCE_BOUND_BALL_MODEL_PROPOSALS; SEPARATE_ACTUAL_NATIVE_DETOUR_CHECK; NO_ROUTE_ACCEPTANCE",
        "analytic":{"cell_status":synthetic["status"],"cell_report_root":synthetic["report_root"],"coverage":synthetic.get("coverage_check"),
                    "native_attempts":native_attempts}}
    atomic_json(out/"benchmark.json",summary)
    atomic_json(evidence_root/"latest.json",{"attempt":str(out.relative_to(ROOT)),"summary":str((out/"benchmark.json").relative_to(ROOT))})
    print(json.dumps(summary),flush=True)
    if args.skip_office: return
    store = Store(ROOT/".oma")
    historical = store.candidate(args.office_candidate)
    run = store.run(historical["run_id"])
    baseline = store.get(run["base_root"])
    if baseline.get("routes") or baseline.get("mission") or baseline.get("physical_networks"):
        raise ValueError("Office input must be an unchanged imported baseline")
    raw = run["request"]["mission"]
    if "route_demands" in raw:
        raw = raw["route_demands"][0]["alternatives"][0]
    specs = [{"path":store.resolve_path(s["immutable_path"]),"sha256":s["sha256"],"transform_m":s["transform_m"]} for s in baseline["sources"]]
    context = digest({"base_root":run["base_root"],"scenario":raw,"scope":"ONE_RECOMPUTED_SCENARIO_FROM_HISTORICAL_OFFICE_MENU"})
    last = [0.]
    def progress(stage):
        if time.monotonic()-last[0] >= 10:
            print(stage,flush=True); last[0] = time.monotonic()
    office = build_certified_cell_proposals(specs,raw,context_root=context,grid_divisions=4,
        cache_directory=store.directory/"cad-cache",deadline=time.monotonic()+args.budget,checkpoint=progress)
    atomic_json(out/"office.cell-report.json",office)
    summary["office"] = {"status":office["status"],"reason":office.get("reason"),"report_root":office["report_root"],
        "coverage":office.get("coverage_check"),"sources":[s["sha256"] for s in specs],"base_root":run["base_root"],
        "scenario":raw,"scenario_origin":"First declared alternative of the historical original-baseline menu, freshly recomputed as one scenario",
        "prior_acceptance_reused":False,"proposals":len(office["proposals"]),"timing":office["timing"],
        "blocked_products":len(office["coverage"]["blockers"])}
    atomic_json(out/"benchmark.json",summary)
    print(json.dumps(summary["office"]),flush=True)


if __name__ == "__main__": main()
