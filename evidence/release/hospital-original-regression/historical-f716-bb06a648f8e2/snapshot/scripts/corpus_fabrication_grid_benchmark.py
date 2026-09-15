"""Source-derived Office grid enrichment, finite pricing and fresh native checks.

Historical support reports supply an explicitly scoped model; original IFC is
freshly hashed and the new route is independently checked against all native
physical source objects. No old geometric PASS or candidate acceptance is reused.
"""
from copy import deepcopy
from fractions import Fraction as Q
from pathlib import Path
import sys
import uuid
import json
import math
import argparse
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT/"tests"))

from oma.ifc.audit import atomic_json,sha256_file
from oma.ifc.cad import cad_check_routes,load_cad
from oma.ifc.export import export_route
from oma.optimization.fabrication import compile_orthogonal_fabrication,verify_orthogonal_fabrication
from oma.optimization.fabrication_pricing import compile_fabrication_pricing,verify_fabrication_pricing
from oma.routing.fabrication_grid import enrich_fabrication_grid,verify_fabrication_grid_enrichment
from oma.routing.native_zone import check_native_zone
from oma.routing.scenario import RoutingScenario
from oma.routing.checker import _semantics
from oma.store import digest
from test_optimization_fabrication import actual_ifc_correspondence


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--max-axis-values",type=int,default=8)
    options=parser.parse_args()
    history=ROOT/"evidence/benchmarks/fabrication-graph/office/21e3d70a85934079b508ff2d48d074e5"
    graph_path=next(history.glob("fabrication_graph-*.json"))
    source_path=next(history.glob("route_geometry_model-*.json"))
    old=json.loads(graph_path.read_text())["report"]
    source_report=json.loads(source_path.read_text())["report"]
    source=Path(source_report["sources"][0]["path"])
    source_hash=sha256_file(source)
    assert len(source_report["sources"])==1 and source_hash==source_report["sources"][0]["sha256"]
    out=ROOT/"evidence/math/fabrication-grid/attempts"/uuid.uuid4().hex
    out.mkdir(parents=True)
    names=("src/oma/routing/fabrication_grid.py","src/oma/optimization/fabrication_pricing.py",
           "src/oma/optimization/fabrication_search.py","src/oma/optimization/fabrication.py",
           "src/oma/routing/native_zone.py","src/oma/ifc/export.py","src/oma/ifc/orthogonal_fillet.py",
           "src/oma/ifc/cad.py","src/oma/routing/checker.py")
    hashes={name:sha256_file(ROOT/name) for name in names}
    model=deepcopy(old["model"])
    original_allowed=deepcopy(model["allowed_bounds"])
    body_guard=Q(1,10000)
    guarded=[[str(Q(x)+(body_guard if side==0 else -body_guard)) for x in row] for side,row in enumerate(original_allowed)]
    model["allowed_bounds"]=guarded
    radius=Q(model["diameter_m"])/2+Q(model["insulation_m"])
    baseline=[]
    for i in range(3):
        lo,hi=Q(guarded[0][i])+radius,Q(guarded[1][i])-radius
        baseline.append([str(x) for x in sorted({lo+(hi-lo)*j/4 for j in range(5)}|{Q(model["start"][i]),Q(model["goal"][i])})])
    model["grid_axes"]=baseline
    model["context_root"]=digest({"historical_report_sha256":sha256_file(graph_path),"body_guard":str(body_guard),"purpose":"NEW_PROPOSAL_ONLY"})
    objective={"schema":"oma.fabrication-grid-cost/1","length_weight":"1","fitting_weight":"0"}
    phase_started=time.perf_counter()
    base_certificate=compile_fabrication_pricing(model,objective,max_work=500000)
    base_check=verify_fabrication_pricing(model,objective,base_certificate,max_work=500000)
    timing={"baseline_pricing_and_verification_seconds":time.perf_counter()-phase_started}
    assert base_check["status"]=="PASS"
    args=(baseline,model["start"],model["goal"],guarded,model["outer_obstacles"],radius,model["clearance_m"])
    kw={"bend_radius_m":model["bend_radius_m"],"minimum_straight_m":model["minimum_straight_m"],"max_axis_values":options.max_axis_values}
    phase_started=time.perf_counter()
    grid=enrich_fabrication_grid(*args,**kw)
    grid_check=verify_fabrication_grid_enrichment(*args,grid,**kw)
    assert grid_check["status"]=="PASS"
    timing["grid_proposal_and_verification_seconds"]=time.perf_counter()-phase_started
    atomic_json(out/"baseline-pricing.json",{"model":model,"objective":objective,"certificate":base_certificate,"independent_check":base_check})
    model["grid_axes"]=grid["grid_axes"]
    model["source_roots"]["grid_enrichment"]=grid["result_root"]
    phase_started=time.perf_counter()
    certificate=compile_fabrication_pricing(model,objective,max_work=500000)
    timing["enriched_pricing_seconds"]=time.perf_counter()-phase_started
    phase_started=time.perf_counter()
    checked=verify_fabrication_pricing(model,objective,certificate,max_work=500000)
    timing["enriched_verification_seconds"]=time.perf_counter()-phase_started
    assert checked["status"]=="PASS" and checked["geometry_outcome"]=="PATH"
    points=[[float(Q(x)) for x in point] for point in certificate["points_m"]]
    scenario=RoutingScenario(start=model["start"],end=model["goal"],diameter_m=model["diameter_m"],
        insulation_m=model["insulation_m"],bend_radius_m=model["bend_radius_m"],minimum_straight_m=model["minimum_straight_m"],
        clearance_m=model["clearance_m"],system_type="PRESSURE_PIPE",scenario_terminals=True,
        allowed_zone={"min":[float(Q(x)) for x in original_allowed[0]],"max":[float(Q(x)) for x in original_allowed[1]]},
        source_representation_policy="NATIVE_CAD_WITH_SOURCE_VERTEX_HULL_ENCLOSURES")
    nominal_kw={"context_root":digest(certificate),"outer_obstacles":model["outer_obstacles"],"outer_model_root":digest(model)}
    nominal=compile_orthogonal_fabrication(scenario,points,**nominal_kw)
    nominal_check=verify_orthogonal_fabrication(scenario,points,nominal,**nominal_kw)
    assert nominal_check["status"]=="PASS" and nominal_check["fabrication_status"]=="PASS"
    spec={"route_id":"source-enriched-office-probe","points_m":points,"system_type":scenario.system_type,
          "diameter_m":scenario.diameter_m,"insulation_m":scenario.insulation_m,"bend_radius_m":scenario.bend_radius_m,
          "minimum_straight_m":scenario.minimum_straight_m,"assumption_root":digest(scenario.model_dump(mode="json"))}
    output=out/"route.ifc"
    manifest=export_route(source,output,spec,fresh_recheck=False)
    guids={p["ifc_guid"] for p in manifest["added_parts"]}
    correspondence=actual_ifc_correspondence(output,manifest,nominal)
    physical=cad_check_routes([source],output,guids,clearance_m=scenario.clearance_m,
        source_representation_policy=scenario.source_representation_policy,cache_directory=ROOT/".oma/native-geometry-cache")
    actual,errors=load_cad(output,guids=guids)
    zone=check_native_zone(actual,scenario.allowed_zone,expected_count=len(guids),errors=errors)
    semantics=_semantics(output,source,manifest,scenario)
    after={name:sha256_file(ROOT/name) for name in names}
    assert hashes==after,"Relevant code changed during retained check"
    assert source_hash==sha256_file(source),"Original source changed"
    a,b=map(Q,certificate["cost"]);x,y=map(Q,base_certificate["cost"])
    result={"scope":"HISTORICAL_SOURCE_MODEL_ENRICHMENT_AND_FRESH_NATIVE_PROPOSAL_CHECK; NO_ACCEPTANCE_AUTHORITY",
        "historical_graph_artifact":str(graph_path.relative_to(ROOT)),"historical_graph_sha256":sha256_file(graph_path),
        "source_report_sha256":sha256_file(source_path),"source_sha256":source_hash,"export_sha256":sha256_file(output),
        "body_search_guard_m":str(body_guard),"guard_is_numeric_error_certificate":False,
        "grid":grid,"grid_check":grid_check,"model":model,"objective":objective,"certificate":certificate,"independent_check":checked,
        "binary64_fabrication_certificate":nominal,"binary64_fabrication_check":nominal_check,
        "manifest":manifest,"actual_correspondence":correspondence,"actual_native":physical,"actual_zone":zone,"actual_semantics":semantics,
        "baseline_nominal_length_approx_m":float(x)+float(y)*math.pi,"enriched_nominal_length_approx_m":float(a)+float(b)*math.pi,
        "code_sha256":hashes,"timing":timing,"pricing_work_budget":500000,"pricing_state_budget":12000,
        "original_source_unchanged":True,"candidate_accepted":False,"continuous_optimality":False}
    atomic_json(out/"checked-result.json",result)
    atomic_json(ROOT/"evidence/math/fabrication-grid/latest.json",{"attempt":str(out.relative_to(ROOT)),"result":str((out/"checked-result.json").relative_to(ROOT))})
    print({"attempt":str(out),"axis_counts":list(map(len,grid["grid_axes"])),"nominal_length":result["enriched_nominal_length_approx_m"],
           "baseline_nominal_length":result["baseline_nominal_length_approx_m"],"native":physical["coordination_status"],
           "self":physical["self_interference_status"],"zone":zone["status"],"pairs":physical["pairs_accounted"],"semantics_errors":semantics["errors"]})


if __name__=="__main__":main()
