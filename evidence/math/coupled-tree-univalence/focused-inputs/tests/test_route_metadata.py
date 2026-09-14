"""Actual native geometry cannot certify a different or incomplete route state."""
from copy import deepcopy
import math

import ifcopenshell
import numpy as np
import pytest

from scripts.corpus_route_metadata_probe import make_case,check
from oma.routing.checker import _actual_route_directrix
from oma.store import digest


@pytest.fixture(scope="module")
def native_case(tmp_path_factory):
    return make_case(tmp_path_factory.mktemp("native-route-metadata"))


@pytest.mark.parametrize("fault",[
    "points","geometry_root","extra_route","duplicate_route","extra_changed","duplicate_changed",
    "missing_changed","materialization_id","spec_id","spec_size","assumption","export_spec",
    "materialization_pointer","source_pointer","duplicate_part","part_index","part_owner",
    "unsupported_fitting","phantom_fabrication","invalid_fabrication","null_fabrication","duplicate_demand","duplicate_terminal"])
def test_metadata_identity_inventory_and_scope_attacks_fail_actual_checker(native_case,fault):
    store,run,state,material=native_case
    mutated=deepcopy(state);updated=deepcopy(material)
    route=mutated["routes"][0];rid=route["id"]
    changed=[rid]
    if fault=="points":route["points_m"]=[[-1.,4.,1.],[1.,4.,5.],[3.,4.,1.]]
    elif fault=="geometry_root":route["geometry_artifact"]=store.put({"unrelated":True})
    elif fault in ("extra_route","duplicate_route"):
        extra=deepcopy(route)
        if fault=="extra_route":extra["id"]="phantom"
        mutated["routes"].append(extra)
    elif fault=="extra_changed":changed.append("phantom")
    elif fault=="duplicate_changed":changed*=2
    elif fault=="missing_changed":changed=["not-the-route"]
    elif fault=="materialization_id":updated["route_id"]="other"
    elif fault=="spec_id":updated["route_spec"]["route_id"]="other"
    elif fault=="spec_size":updated["route_spec"]["diameter_m"]*=2
    elif fault=="assumption":updated["route_spec"]["assumption_root"]="forged"
    elif fault=="export_spec":mutated["derived_artifacts"]["route_exports"][0]["route_spec"]["diameter_m"]*=2
    elif fault=="materialization_pointer":mutated["derived_artifacts"]["route_materialization"]["path"]="missing.ifc"
    elif fault=="source_pointer":mutated["derived_artifacts"]["route_materialization"]["source_id"]="other"
    elif fault=="duplicate_part":updated["added_parts"]*=2
    elif fault=="part_index":updated["added_parts"][0]["part_index"]=True
    elif fault=="part_owner":updated["added_parts"][0]["route_id"]="other"
    elif fault=="unsupported_fitting":route["shared_trunk_id"]="phantom-trunk"
    elif fault=="phantom_fabrication":mutated["derived_artifacts"]["fabrication_evidence_by_route"]={"phantom":{}}
    elif fault=="invalid_fabrication":mutated["derived_artifacts"]["fabrication_evidence_by_route"]={rid:{}}
    elif fault=="null_fabrication":mutated["derived_artifacts"]["fabrication_evidence_by_route"]={rid:None}
    elif fault=="duplicate_demand":route["demand_ids"]*=2
    elif fault=="duplicate_terminal":route["port_ids"].append(route["port_ids"][0])
    if updated!=material:
        root=store.put(updated)
        route["geometry_artifact"]=root
        mutated["derived_artifacts"]["route_materialization"]["root"]=root
    result=check(store,run,mutated,changed)
    assert result["report"]["status"]=="FAIL",result


def test_coherent_route_and_spec_forgery_is_rejected_by_actual_ifc_directrix(native_case):
    store,run,state,material=native_case
    mutated=deepcopy(state);updated=deepcopy(material)
    wrong=[[-1.,4.,1.],[1.,4.,5.],[3.,4.,1.]]
    updated["route_spec"]["points_m"]=wrong
    root=store.put(updated)
    mutated["routes"][0].update(points_m=wrong,geometry_artifact=root)
    mutated["derived_artifacts"]["route_materialization"]["root"]=root
    mutated["derived_artifacts"]["route_exports"][0]["route_spec"]=updated["route_spec"]
    result=check(store,run,mutated)
    assert next(r for r in result["report"]["results"] if r["id"]=="route-materialization-correspondence")["status"]=="PASS"
    semantics=next(r for r in result["report"]["results"] if r["id"]=="exported-physical-semantics")
    assert semantics["status"]=="FAIL" and semantics["witness"]["recomputed"]["route_directrix"]["errors"]


def test_optional_fabrication_is_replayed_and_missing_historical_evidence_is_not_required(native_case):
    from oma.routing.fabrication_evidence import persist_fabrication_proposal
    from oma.routing.scenario import RoutingScenario
    store,run,state,material=native_case
    old=check(store,run,state)
    assert old["report"]["status"]=="PASS"
    assert next(r for r in old["report"]["results"] if r["id"]=="nominal-fabrication-witness-integrity")["status"]=="NOT_APPLICABLE"
    scenario=RoutingScenario.model_validate(run["request"]["mission"])
    proposal=persist_fabrication_proposal(store,run,scenario,{"points_m":state["routes"][0]["points_m"]},checkpoint=lambda _:None)
    mutated=deepcopy(state)
    mutated["derived_artifacts"]["fabrication_evidence_by_route"]={mutated["routes"][0]["id"]:proposal["fabrication_evidence"]}
    report=check(store,run,mutated)["report"]
    assert report["status"]=="PASS"
    proof=next(r for r in report["results"] if r["id"]=="nominal-fabrication-witness-integrity")
    assert proof["status"]=="PASS" and proof["witness"]["fabrication_status"]=="PASS"
    assert not proof["witness"]["candidate_acceptance_authority"]
    omitted=check(store,run,state)["report"]
    assert next(r for r in omitted["results"] if r["id"]=="nominal-fabrication-witness-integrity")["status"]=="FAIL"


def test_duplicate_joint_changed_identity_rejects_actual_two_route_candidate(tmp_path):
    from oma.routing.engine import route_project_run
    from oma.routing.joint_checker import verify_joint_candidate
    from oma.worker import WorkerControl
    store,prior_run,_,_=make_case(tmp_path)
    project=store.project(prior_run["project_id"])
    # The helper's unaccepted standalone draft has not changed the project.
    first=prior_run["request"]["mission"]
    second={**first,"start":[-1.,4.,3.],"end":[3.,4.,3.]}
    mission={"route_demands":[{"id":"a","alternatives":[first]},{"id":"b","alternatives":[second]}],
        "max_joint_candidates":1,"max_paths_per_alternative":1}
    run=store.create_run(project["id"],{"operation":"optimize","mission":mission,"budget_seconds":60})
    route_project_run(store,run,WorkerControl(store,run["id"]))
    candidate=next(c for c in store.candidates(project["id"]) if c["run_id"]==run["id"])
    assert candidate["status"]=="CHECKED",store.get(candidate["report_root"])
    changed=candidate["changed_ids"]+[candidate["changed_ids"][0]]
    forged=store.add_candidate(run["id"],store.get(candidate["state_root"]),{"kind":"physical_route_set","changed_ids":changed})
    result=verify_joint_candidate(store,forged["id"])
    assert result.status=="FAIL"
    assert next(r for r in result.results if r.id=="joint-demand-coverage").status=="FAIL"


@pytest.mark.parametrize("angle",[math.pi/2,math.pi/3,2*math.pi/3])
@pytest.mark.parametrize("schema",["IFC4","IFC2X3"])
def test_actual_general_circular_directrix_correspondence_and_shift_attack(tmp_path,angle,schema):
    from oma.ifc.export import export_route
    from test_ifc_openings import host_fixture
    source,_=host_fixture(tmp_path/"source.ifc",schema=schema)
    points=[[-2.,0.,0.],[0.,0.,0.],[2*math.cos(angle),2*math.sin(angle),0.]]
    spec={"route_id":"independent-directrix","points_m":points,"diameter_m":.1,
        "insulation_m":.02,"bend_radius_m":.3,"minimum_straight_m":.05,"system_type":"PRESSURE_PIPE"}
    output=tmp_path/"route.ifc"
    material=export_route(source,output,spec,fresh_recheck=False)
    model=ifcopenshell.open(str(output))
    assert not _actual_route_directrix(model,material)["errors"]
    # Same part count and endpoints; forged corner moves the nominal route.
    changed=deepcopy(material)
    changed["route_spec"]["points_m"][1][2]=.25
    assert _actual_route_directrix(model,changed)["errors"]
