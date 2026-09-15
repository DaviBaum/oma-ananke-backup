from copy import deepcopy
from fractions import Fraction as Q
from pathlib import Path
import hashlib,json

import pytest
from pydantic import ValidationError

from oma.routing import coupled_tree_pressure as a
from oma.routing.coupled_tree_scenario import CoupledTreeBoundary
from oma.routing.network_scenario import NetworkDesign

FIXTURES=Path(__file__).parent/"fixtures/coupled-native-tree"


def load(name):return json.loads((FIXTURES/(name+".json")).read_text(encoding="utf-8"))
def inputs():return load("boundary"),load("specification"),load("native-metrics"),load("context")
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def reseal(packet):packet["certificate_root"]=digest({k:v for k,v in packet.items() if k!="certificate_root"});return packet
def bound(lo,hi=None):return {"lower":str(lo),"upper":str(lo if hi is None else hi)}
def inside(value,span):return Q(span["lower"])<=Q(value)<=Q(span["upper"])


@pytest.fixture(scope="module")
def result():
    b,n,m,c=inputs();r=a.evaluate_coupled_tree(b,n,m,context=c)
    assert r["status"]=="CERTIFIED_ENVELOPE",r
    assert r["verdict"]=="PASS"
    return r


def test_actual_native_seven_body_full_mapping_and_two_proofs(result):
    proof=result["independent_check"];certificate=result["certificate"];service=proof["service"]
    assert proof["local_check"]["status"]==proof["global_check"]["status"]=="PASS"
    assert proof["local_check"]["model_root"]==proof["global_check"]["model_root"]==proof["model_root"]
    assert certificate["local_certificate"]["parameter_root"]==proof["global_check"]["parameter_root"]
    assert proof["counts"]=={"components":7,"physical_ports":16,"connections":6,"tees":2,"terms":9,"leaves":3,"boundaries":4}
    assert service["counts"]=={"physical_ports":16,"deliveries":3,"conservation_identities":17,"head_path_identities":19}
    assert all(row["difference"]=={} for row in service["conservation_identities"])
    assert len({(x["component"],x["port"]) for x in service["physical_ports"]})==16
    oracle=load("independent-nominal-oracle")["ports"]
    for row in service["physical_ports"]:
        ref=oracle[row["component"]+"."+row["port"]]
        for key,refkey in (("flow_m3_s","forward_flow_m3_s"),("velocity_m_s","velocity_m_s"),
                           ("total_head_pa","total_head_pa"),("total_pressure_pa","total_pressure_pa")):
            assert inside(ref[refkey],row[key]),(row["component"],row["port"],key)
        assert row["forward_status"]==row["maximum_velocity_status"]=="PASS"
    assert inside("11/2000",service["source_flow_m3_s"])
    assert proof["native_geometry_acceptance_authority"] is False


def test_derive_api_and_independent_physical_path_reconstruction(result,monkeypatch):
    b,n,m,c=inputs();model,box,derivation=a.derive_coupled_tree_model(b,n,m,context=c)
    assert model==result["certificate"]["model"] and box==result["certificate"]["flow_box"]
    assert derivation==result["certificate"]["derivation"]
    old_path=a._path_inventory;old_coeff=a._coefficients
    def paths(n,c,checked=False):
        assert checked,"Checker must not use producer descendants"
        return old_path(n,c,checked)
    def coefficients(n,c,checked=False):
        assert checked,"Checker must use direct dimensional extrema"
        return old_coeff(n,c,checked)
    def never(*args,**kwargs):raise AssertionError("Producer invoked by independent checker")
    monkeypatch.setattr(a,"_path_inventory",paths);monkeypatch.setattr(a,"_coefficients",coefficients)
    monkeypatch.setattr(a.local,"compile_coupled_tree_pressure",never)
    monkeypatch.setattr(a.local,"_inverse",never)
    monkeypatch.setattr(a.global_proof,"compile_coupled_tree_univalence",never)
    checked=a.verify_coupled_tree_envelope(b,n,m,result["certificate"],context=c)
    assert checked["status"]==checked["verdict"]=="PASS"


def test_total_tee_inlet_flow_applies_to_separate_outlet_subtrees(result):
    rows=result["certificate"]["derivation"]["term_physics"]
    lookup={(r["component"],r["outlet"]):r for r in rows}
    assert lookup[("tee-1","b")]["descendant_leaves"]==["sink-a","sink-b","sink-c"]
    assert lookup[("tee-1","b")]["applies_to_leaves"]==["sink-b","sink-c"]
    assert lookup[("tee-1","branch")]["applies_to_leaves"]==["sink-a"]
    assert lookup[("tee-2","b")]["descendant_leaves"]==["sink-b","sink-c"]
    assert lookup[("tee-2","branch")]["applies_to_leaves"]==["sink-c"]
    assert all(not r["tee_darcy_charged"] for r in rows)
    ports={(p["component"],p["port"]):p for p in result["service"]["physical_ports"]}
    assert ports[("tee-1","a")]["flow_expression"]=={"sink-a":1,"sink-b":1,"sink-c":1}
    assert ports[("tee-1","branch")]["flow_expression"]=={"sink-a":1}
    assert ports[("tee-1","b")]["total_head_pa"]!=ports[("tee-1","branch")]["total_head_pa"]


def test_native_dimensional_extrema_and_outward_parameter_containment(result):
    b,_,m,_=inputs();d=result["certificate"]["derivation"];model=result["certificate"]["model"]
    pi=a.pi_interval();rho=Q(b["density_kg_m3"]);f=Q(b["darcy_friction"])
    for cid,section in d["component_sections"].items():
        radius=m["components"][cid]["outer_radius_m"];diameter=section["diameter_m"]
        assert Q(diameter["lower"])==2*(Q(radius["lower"])-Q(1,50))
        assert Q(diameter["upper"])==2*(Q(radius["upper"])-Q(1,50))
        dl,dh=Q(diameter["lower"]),Q(diameter["upper"])
        for outlet,loss in section["loss_coefficients_pa_s2_m6"].items():
            if outlet=="body":
                length=m["components"][cid]["length_m"]
                low=8*rho*f*Q(length["lower"])/(pi.hi**2*dh**5)
                high=8*rho*f*Q(length["upper"])/(pi.lo**2*dl**5)
            else:
                k=Q(b["tee_outlet_loss_coefficients"][cid][outlet])
                low=8*rho*k/(pi.hi**2*dh**4);high=8*rho*k/(pi.lo**2*dl**4)
            assert loss==bound(low,high)
            record=next(r for r in d["term_physics"] if (r["component"],r["outlet"])==(cid,outlet))
            rounded=model["coefficients"][record["coefficient_id"]]
            assert Q(rounded["lower"])<=low<=high<=Q(rounded["upper"])
            assert low-Q(rounded["lower"])<Q(1,2**40) and Q(rounded["upper"])-high<Q(1,2**40)
    for leaf,raw in d["available_heads_pa"].items():
        outer=model["available_heads"][leaf]
        assert Q(outer["lower"])<=Q(raw["lower"])<=Q(raw["upper"])<=Q(outer["upper"])


@pytest.mark.parametrize("lo,hi",[(Q(-7,3),Q(-2,3)),(Q(-1,10**20),Q(1,10**20)),(Q(0),Q(0)),(Q(1,3),Q(7,3))])
def test_outward_parameter_rounding_signed_zero(lo,hi):
    for checked in (False,True):
        x=a._parameter_enclosure(a.Interval(lo,hi),checked)
        assert x.lo<=lo<=hi<=x.hi and lo-x.lo<Q(1,2**40) and x.hi-hi<Q(1,2**40)


@pytest.mark.parametrize("path,value",[
    (("derivation","counts","physical_ports"),15),
    (("derivation","term_physics",0,"descendant_leaves"),["sink-b"]),
    (("derivation","term_physics",0,"tee_darcy_charged"),True),
    (("derivation","port_paths",0,"loss_terms"),[]),
    (("derivation","component_sections","tee-1","diameter_m","lower"),"1/10"),
    (("derivation","parameter_rounding","step"),"1/100"),
    (("service","physical_ports",0,"flow_expression"),{"sink-c":1}),
    (("service","physical_ports",0,"flow_m3_s","upper"),"1"),
    (("service","physical_ports",0,"total_head_pa","lower"),"1"),
    (("service","physical_ports",0,"total_pressure_pa","lower"),"1"),
    (("service","physical_ports",0,"velocity_m_s","upper"),"0"),
    (("service","deliveries",0,"minimum_m3_s"),"0"),
    (("service","conservation_identities",0,"difference"),{"sink-a":1}),
    (("service","head_path_identities",0,"loss_terms"),[]),
    (("service","verdict"),"FAIL"),
    (("service","limitations","static_pressure_reported"),True),
    (("flow_box","sink-a","upper"),"1/100"),
    (("model","physical_model_root"),"f"*64),
])
def test_resealed_semantic_attacks(result,path,value):
    b,n,m,c=inputs();packet=deepcopy(result["certificate"]);obj=packet
    for key in path[:-1]:obj=obj[key]
    assert obj[path[-1]]!=value
    obj[path[-1]]=value
    assert a.verify_coupled_tree_envelope(b,n,m,reseal(packet),context=c)["status"]=="FAIL"


@pytest.mark.parametrize("kind",["missing_port","duplicate_port","missing_term","duplicate_term","missing_global","missing_local","false_global","false_local","model_coefficient_narrowed","raw_coefficient_omitted"])
def test_no_omitted_denominators_or_proofs(result,kind):
    b,n,m,c=inputs();p=deepcopy(result["certificate"])
    if kind=="missing_port":p["service"]["physical_ports"].pop()
    elif kind=="duplicate_port":p["service"]["physical_ports"][1]=p["service"]["physical_ports"][0]
    elif kind=="missing_term":p["derivation"]["term_physics"].pop()
    elif kind=="duplicate_term":p["derivation"]["term_physics"][1]=p["derivation"]["term_physics"][0]
    elif kind=="missing_global":p.pop("univalence_certificate")
    elif kind=="missing_local":p.pop("local_certificate")
    elif kind=="false_global":p["univalence_certificate"]["model_root"]="e"*64;reseal(p["univalence_certificate"])
    elif kind=="false_local":p["local_certificate"]["contraction_norm_upper"]="0";reseal(p["local_certificate"])
    elif kind=="model_coefficient_narrowed":p["model"]["coefficients"][next(iter(p["model"]["coefficients"]))]=bound(1)
    else:p["derivation"]["component_sections"]["arm-a"].pop("loss_coefficients_pa_s2_m6")
    assert a.verify_coupled_tree_envelope(b,n,m,reseal(p),context=c)["status"]!="PASS"


@pytest.mark.parametrize("kind",["pressure_point_scalar","common_outlet_law","old_schema","missing_tee","extra_tee","zero_tee","negative_f","zero_f","negative_gravity","missing_sink","point_box","zero_box","extra_boundary"])
def test_new_contract_rejects_unsupported_fields(kind):
    b,n,m,c=inputs()
    if kind=="pressure_point_scalar":b["source_total_pressure_pa"]="200"
    elif kind=="common_outlet_law":b["tee_loss_reference"]="IDENTICAL_OUTLET_TOTAL_LOSS_AT_INLET_FLOW_COMMON_HEAD"
    elif kind=="old_schema":b["schema"]="oma.passive-tree-boundary/1"
    elif kind=="missing_tee":b["tee_outlet_loss_coefficients"].pop("tee-2")
    elif kind=="extra_tee":b["tee_outlet_loss_coefficients"]["unmodeled"]={"b":"1","branch":"1"}
    elif kind=="zero_tee":b["tee_outlet_loss_coefficients"]["tee-1"]["b"]="0"
    elif kind=="negative_f":b["darcy_friction"]="-1"
    elif kind=="zero_f":b["darcy_friction"]="0"
    elif kind=="negative_gravity":b["gravity_m_s2"]="-1"
    elif kind=="missing_sink":b["minimum_sink_flows_m3_s"].pop("sink-a")
    elif kind=="point_box":b["flow_search_box_m3_s"]["sink-a"]=bound("3/1000")
    elif kind=="zero_box":b["flow_search_box_m3_s"]["sink-a"]=bound(0,"1/100")
    else:b["available_static_pressure_pa"]="200"
    assert a.evaluate_coupled_tree(b,n,m,context=c)["status"]=="BLOCKED"


@pytest.mark.parametrize("bad",[True,1.0,float("nan"),float("inf"),"1/0","NaN","1e-3",None])
def test_boundary_bad_rational(bad):
    b,_,_,_=inputs();b["density_kg_m3"]=bad
    with pytest.raises(ValidationError):CoupledTreeBoundary.model_validate(b)


@pytest.mark.parametrize("kind",["missing_component","extra_component","missing_cap","extra_cap","nan","zero_denominator","negative_length","zero_bore","disjoint_caps","wrong_network","old_schema","wrong_demand_path","duplicate_connection"])
def test_native_model_guards(kind):
    b,n,m,c=inputs()
    if kind=="missing_component":m["components"].pop("arm-a")
    elif kind=="extra_component":m["components"]["extra"]=deepcopy(m["components"]["arm-a"])
    elif kind=="missing_cap":m["components"]["tee-2"]["ports"].pop("branch")
    elif kind=="extra_cap":m["components"]["tee-2"]["ports"]["fourth"]=deepcopy(m["components"]["tee-2"]["ports"]["b"])
    elif kind=="nan":m["components"]["arm-a"]["outer_radius_m"]["lower"]=float("nan")
    elif kind=="zero_denominator":m["components"]["arm-a"]["outer_radius_m"]["lower"]="1/0"
    elif kind=="negative_length":m["components"]["arm-a"]["length_m"]=bound(-1)
    elif kind=="zero_bore":m["components"]["arm-a"]["outer_radius_m"]=bound("1/50")
    elif kind=="disjoint_caps":m["components"]["arm-a"]["ports"]["a"]["position_m"][0]=bound(100)
    elif kind=="wrong_network":m["network_root"]="a"*64
    elif kind=="old_schema":m["schema"]="oma.passive-tree-native-metrics/1"
    elif kind=="wrong_demand_path":n["demand_paths"][0]["steps"].pop()
    else:n["connections"].append(n["connections"][0])
    assert a.evaluate_coupled_tree(b,n,m,context=c)["status"] in ("BLOCKED","UNKNOWN")


@pytest.mark.parametrize("kind",["delivery_fail","velocity_fail","delivery_unresolved","velocity_unresolved"])
def test_valid_equilibrium_can_fail_or_leave_service_unknown(result,kind):
    b,n,m,c=inputs();service=result["service"]
    if kind=="delivery_fail":b["minimum_sink_flows_m3_s"]["sink-a"]="1/100"
    elif kind=="velocity_fail":b["maximum_velocity_m_s"]="69/100"
    elif kind=="delivery_unresolved":
        span=service["deliveries"][0]["flow_m3_s"];b["minimum_sink_flows_m3_s"]["sink-a"]=str((Q(span["lower"])+Q(span["upper"]))/2)
    else:
        span=next(x for x in service["physical_ports"] if x["component"]=="trunk")["speed_m_s"]
        # Keep this boundary value under its separate 512-bit encoding limit.
        b["maximum_velocity_m_s"]=str(Q(round(float((Q(span["lower"])+Q(span["upper"]))/2)*10**8),10**8))
    r=a.evaluate_coupled_tree(b,n,m,context=c)
    assert r["status"]=="CERTIFIED_ENVELOPE",r
    assert r["verdict"]==("FAIL" if kind.endswith("fail") else "UNKNOWN")
    assert r["independent_check"]["local_check"]["status"]==r["independent_check"]["global_check"]["status"]=="PASS"


def test_missing_terminal_pipe_singleton_never_hides_other_equilibria():
    b,n,m,c=inputs();n["components"]=[x for x in n["components"] if x["id"]!="arm-a"]
    n["connections"]=[x for x in n["connections"] if x["sink"]["component"]!="arm-a"]
    next(x for x in n["sinks"] if x["id"]=="sink-a")["endpoint"]={"component":"tee-1","port":"branch"}
    next(x for x in n["demand_paths"] if x["sink_id"]=="sink-a")["steps"].pop()
    m["components"].pop("arm-a");m["network_root"]=digest(NetworkDesign.model_validate(n).model_dump(mode="json",by_alias=True))
    r=a.evaluate_coupled_tree(b,n,m,context=c)
    assert r["status"]=="UNKNOWN" and r["verdict"]=="UNKNOWN" and r["proof_complete"] is False
    assert "singleton" in r["global_producer"]["reason"].lower()
    assert "service" not in r


def test_uniform_narrow_query_and_reversed_pressure_are_unknown():
    for reverse in (False,True):
        b,n,m,c=inputs()
        if reverse:b["source_total_pressure_pa"]=bound(-1000)
        else:
            for v in b["flow_search_box_m3_s"].values():
                center=(Q(v["lower"])+Q(v["upper"]))/2;v.update(bound(center-Q(1,100000),center+Q(1,100000)))
        r=a.evaluate_coupled_tree(b,n,m,context=c)
        assert r["status"]=="UNKNOWN" and "service" not in r


def test_interval_source_boundary_supported():
    b,n,m,c=inputs();b["source_total_pressure_pa"]=bound(Q(200)-Q(1,10**6),Q(200)+Q(1,10**6))
    r=a.evaluate_coupled_tree(b,n,m,context=c)
    assert r["status"]=="CERTIFIED_ENVELOPE" and r["verdict"]=="PASS"


@pytest.mark.parametrize("kind",["radius","length","elevation","boundary","context","box"])
def test_fresh_inputs_do_not_reuse_stale_certificate(result,kind):
    b,n,m,c=inputs()
    if kind=="radius":m["components"]["arm-b"]["outer_radius_m"]["lower"]="69998/1000000"
    elif kind=="length":m["components"]["arm-b"]["length_m"]["upper"]="800002/1000000"
    elif kind=="elevation":m["components"]["arm-b"]["ports"]["b"]["position_m"][2]["upper"]="3000002/1000000"
    elif kind=="boundary":b["sink_total_pressures_pa"]["sink-b"]["upper"]="100"
    elif kind=="context":c["different_context"]="f"*64
    else:b["flow_search_box_m3_s"]["sink-a"]["lower"]="2996/1000000"
    assert a.verify_coupled_tree_envelope(b,n,m,result["certificate"],context=c)["status"]=="FAIL"


@pytest.mark.parametrize("kwargs",[{"max_components":6},{"max_work":1},{"max_bytes":1024}])
def test_budget_nonproof(result,kwargs):
    b,n,m,c=inputs()
    assert a.evaluate_coupled_tree(b,n,m,context=c,**kwargs)["status"]=="UNKNOWN"
    assert a.verify_coupled_tree_envelope(b,n,m,result["certificate"],context=c,**kwargs)["status"]=="UNKNOWN"


@pytest.mark.parametrize("which",["derive","producer","verifier"])
@pytest.mark.parametrize("kind",["boundary","metric","context","network"])
def test_final_mutation_no_late_callbacks(result,which,kind):
    b,n,m,c=inputs();seen=[]
    end={"derive":"coupled_tree_derivation_complete","producer":"coupled_tree_producer_complete","verifier":"coupled_tree_verifier_complete"}[which]
    def callback(stage):
        if seen:raise AssertionError("Callback after final completion")
        if stage==end:
            seen.append(stage)
            if kind=="boundary":b["source_total_pressure_pa"]=bound(1000)
            elif kind=="metric":m["components"]["trunk"]["outer_radius_m"]=bound("1/10")
            elif kind=="context":c["mutated"]=True
            else:n["network_id"]="changed"
    if which=="derive":
        with pytest.raises(ValueError):a.derive_coupled_tree_model(b,n,m,context=c,checkpoint=callback)
    else:
        r=(a.evaluate_coupled_tree(b,n,m,context=c,checkpoint=callback) if which=="producer"
           else a.verify_coupled_tree_envelope(b,n,m,result["certificate"],context=c,checkpoint=callback))
        assert r["status"]==("BLOCKED" if which=="producer" else "FAIL")
    assert seen


def test_final_certificate_mutation(result):
    b,n,m,c=inputs();packet=deepcopy(result["certificate"])
    def callback(stage):
        if stage=="coupled_tree_verifier_complete":packet["service"]["verdict"]="FAIL"
    assert a.verify_coupled_tree_envelope(b,n,m,packet,context=c,checkpoint=callback)["status"]=="FAIL"


@pytest.mark.parametrize("which",["derive","producer","verifier"])
@pytest.mark.parametrize("exception",[TimeoutError("deadline"),ValueError("cancel"),a.bounded._BudgetExceeded("caller budget")])
def test_caller_exception_identity(result,which,exception):
    b,n,m,c=inputs();ending={"derive":"coupled_tree_derivation_complete","producer":"coupled_tree_producer_complete","verifier":"coupled_tree_verifier_complete"}[which]
    def callback(stage):
        if stage==ending:raise exception
    with pytest.raises(type(exception)) as caught:
        if which=="derive":a.derive_coupled_tree_model(b,n,m,context=c,checkpoint=callback)
        elif which=="producer":a.evaluate_coupled_tree(b,n,m,context=c,checkpoint=callback)
        else:a.verify_coupled_tree_envelope(b,n,m,result["certificate"],context=c,checkpoint=callback)
    assert caught.value is exception


def test_metric_inventory_rechecked_after_callback():
    b,n,m,c=inputs();fired=[]
    def callback(stage):
        if not fired:
            fired.append(stage)
            m["components"].update({"fake-"+str(i):deepcopy(m["components"]["trunk"]) for i in range(129)})
    r=a.evaluate_coupled_tree(b,n,m,context=c,checkpoint=callback)
    assert r["status"]=="UNKNOWN" and r["proof_complete"] is False


@pytest.mark.parametrize("which",["producer","verifier"])
def test_exact_shared_work_includes_all_noncallback_tails(result,which):
    b,n,m,c=inputs()
    call=(lambda budget,callback=None:a.evaluate_coupled_tree(b,n,m,context=c,max_work=budget,checkpoint=callback)) if which=="producer" else (
         lambda budget,callback=None:a.verify_coupled_tree_envelope(b,n,m,result["certificate"],context=c,max_work=budget,checkpoint=callback))
    callbacks=[]
    high=call(2_000_000,lambda stage:callbacks.append(stage))
    assert high["status"]==("CERTIFIED_ENVELOPE" if which=="producer" else "PASS")
    exact=high["work"]
    assert exact>len(callbacks),"Final no-callback hash work must still be charged"
    assert call(exact)["status"]==high["status"]
    low=call(exact-1)
    assert low["status"]=="UNKNOWN" and low["proof_complete"] is False


def test_no_positive_rounding_floor_no_service():
    b,n,m,c=inputs();b["density_kg_m3"]="1/100000000000000000000000000000000000000000000000000"
    r=a.evaluate_coupled_tree(b,n,m,context=c)
    assert r["status"]=="UNKNOWN" and r["reason"]=="POSITIVE_COEFFICIENT_NOT_RESOLVED_ON_PARAMETER_GRID"


def test_distinct_native_component_sections_drive_each_loss():
    b,n,m,c=inputs();m["components"]["arm-b"]["outer_radius_m"]=bound("69/1000","691/10000")
    _,_,d=a.derive_coupled_tree_model(b,n,m,context=c)
    assert d["component_sections"]["arm-b"]["diameter_m"]==bound("49/500","491/5000")
    assert Q(d["component_sections"]["arm-b"]["loss_coefficients_pa_s2_m6"]["body"]["lower"])>Q(d["component_sections"]["arm-c"]["loss_coefficients_pa_s2_m6"]["body"]["upper"])
