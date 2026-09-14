"""Retain real native route metadata attacks and independently checked results."""
from copy import deepcopy
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT/"tests"))

from oma.ifc.audit import atomic_json,sha256_file
from oma.ifc.export import export_route
from oma.models import Route
from oma.routing.checker import verify_route_candidate
from oma.routing.joint import _new_obligation
from oma.routing.scenario import RoutingScenario
from oma.store import Store,digest
from oma.worker import WorkerControl,import_sources
from test_ifc_pipeline import make_fixture


def make_case(directory):
    directory.mkdir(parents=True,exist_ok=True)
    source=make_fixture(directory/"obstacle.ifc")
    store=Store(directory/"store")
    project=store.create_project("Native metadata correspondence",{"sources":[],"entities":[]})
    imp=store.create_run(project["id"],{"operation":"import","paths":[str(source)]})
    import_sources(store,imp,WorkerControl(store,imp["id"]))
    scenario=RoutingScenario(start=(-1,4,1),end=(3,4,1),system_type="PRESSURE_PIPE",
        diameter_m=.1,insulation_m=.02,bend_radius_m=.3,minimum_straight_m=.05,clearance_m=.1,
        allowed_zone={"min":[-2,-2,-2],"max":[6,6,6]},scenario_terminals=True,max_candidates=1)
    run=store.create_run(project["id"],{"operation":"route","mission":scenario.model_dump(mode="json"),"budget_seconds":90})
    state=store.get(run["base_root"])
    selected=state["sources"][0]
    rid="native-metadata-probe"
    contract,ports,section=_new_obligation(state,scenario,rid,"single",selected["id"])
    points=[list(scenario.start),list(scenario.end)]
    spec={"route_id":rid,"points_m":points,"diameter_m":scenario.diameter_m,
        "insulation_m":scenario.insulation_m,"bend_radius_m":scenario.bend_radius_m,
        "minimum_straight_m":scenario.minimum_straight_m,"system_type":scenario.system_type,
        "assumption_root":digest(scenario.model_dump(mode="json"))}
    if selected.get("transform_m") is not None:spec["source_to_federation_matrix"]=selected["transform_m"]
    material=export_route(store.resolve_path(selected["immutable_path"]),directory/"route.ifc",spec,fresh_recheck=False)
    root=store.put(material)
    route=Route(id=rid,demand_ids=(contract["mission"]["demands"][0]["id"],),service=scenario.system_type,
        points_m=points,section=section,port_ids=tuple(p.id for p in ports),geometry_artifact=root,status="MATERIALIZED")
    state["mission"]=contract["mission"]
    state["ports"] += [p.model_dump(mode="json") for p in ports]
    state["routes"]=[route.model_dump(mode="json")]
    state.setdefault("derived_artifacts",{}).update(routing_scenario=scenario.model_dump(mode="json"),
        route_materialization={"root":root,"source_id":selected["id"],"path":material["export_path"]},
        route_exports=[{"source_id":selected["id"],"route_spec":spec}])
    return store,run,state,material


def check(store,run,state,changed_ids=None):
    candidate=store.add_candidate(run["id"],state,{"kind":"physical_route","changed_ids":changed_ids or [state["routes"][0]["id"]]})
    report=verify_route_candidate(store,candidate["id"])
    return {"candidate_id":candidate["id"],"candidate_root":candidate["state_root"],"report":report.model_dump(mode="json")}


def main():
    out=ROOT/"evidence/math/route-metadata/attempts"/uuid.uuid4().hex
    store,run,state,material=make_case(out)
    cases={"baseline":check(store,run,state)}
    wrong=[[-1.,4.,1.],[1.,4.,5.],[3.,4.,1.]]
    for fault in ("route_points_only","unbound_geometry_root","extra_phantom_route","coherent_points_and_spec","duplicate_changed_ids"):
        mutated=deepcopy(state)
        ids=[state["routes"][0]["id"]]
        if fault=="route_points_only":mutated["routes"][0]["points_m"]=wrong
        elif fault=="unbound_geometry_root":mutated["routes"][0]["geometry_artifact"]=store.put({"phantom_geometry":True})
        elif fault=="extra_phantom_route":
            phantom=deepcopy(mutated["routes"][0]);phantom["id"]="unaccounted-route";phantom["points_m"]=wrong
            mutated["routes"].append(phantom)
        elif fault=="coherent_points_and_spec":
            modified=deepcopy(material);modified["route_spec"]["points_m"]=wrong
            root=store.put(modified)
            mutated["routes"][0].update(points_m=wrong,geometry_artifact=root)
            mutated["derived_artifacts"]["route_materialization"]["root"]=root
            mutated["derived_artifacts"]["route_exports"][0]["route_spec"]=modified["route_spec"]
        elif fault=="duplicate_changed_ids":ids*=2
        cases[fault]=check(store,run,mutated,ids)
    summary={"scope":"ACTUAL_NATIVE_IFC_CHECK_WITH_FORGED_ROUTE_METADATA; NO_NATIVE_INPUT_BYTES_MODIFIED",
        "code_sha256":{name:sha256_file(ROOT/name) for name in ("src/oma/routing/checker.py","src/oma/ifc/export.py")},
        "materialized_ifc_sha256":material["export_sha256"],"cases":cases}
    atomic_json(out/"probe.json",summary)
    print({"attempt":str(out),"results":{k:v["report"]["status"] for k,v in cases.items()}})


def replay(directory):
    import json
    original=json.loads((directory/"probe.json").read_text(encoding="utf-8"))
    store=Store(directory/"store")
    cases={}
    for name,record in original["cases"].items():
        prior=store.candidate(record["candidate_id"])
        cases[name]=check(store,store.run(prior["run_id"]),store.get(prior["state_root"]),prior["changed_ids"])
    output={"original_probe_sha256":sha256_file(directory/"probe.json"),"same_immutable_candidate_states":True,
        "materialized_ifc_sha256":original["materialized_ifc_sha256"],"checker_sha256":sha256_file(ROOT/"src/oma/routing/checker.py"),"cases":cases}
    destination=directory/("corrected-replay-"+uuid.uuid4().hex+".json")
    atomic_json(destination,output)
    print({"replay":str(destination),"results":{k:v["report"]["status"] for k,v in cases.items()}})


if __name__=="__main__":
    if len(sys.argv)==3 and sys.argv[1]=="--replay":replay(Path(sys.argv[2]))
    else:main()
