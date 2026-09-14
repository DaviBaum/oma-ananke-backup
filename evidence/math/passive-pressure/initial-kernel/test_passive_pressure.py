from copy import deepcopy
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path

import pytest

from oma.optimization import passive_pressure as p

STAGE = Path(__file__).resolve().parents[1]


def interval(a, b=None):
    return {"lower": str(a), "upper": str(a if b is None else b)}


def model(nodes, internal, boundary, edges):
    return {"schema": p.MODEL_SCHEMA, "nodes": list(nodes), "internal_nodes": list(internal),
        "boundary_heads": {v: interval(*x) if type(x) is tuple else interval(x) for v, x in boundary.items()},
        "edges": [{"id": n, "source": u, "target": v,
            "resistance": interval(*r) if type(r) is tuple else interval(r)} for n, u, v, r in edges],
        "context_root": "0"*64, "physical_model_root": "1"*64, "assumptions": deepcopy(p.MODEL_ASSUMPTIONS)}


def tree():
    return model(["S","J","T1","T2","T3"],["J"],{"S":10,"T1":0,"T2":0,"T3":0},
        [("SJ","S","J",1), *[("J"+v,"J",v,1) for v in ("T1","T2","T3")]])


def binary_tree():
    return model(["S","J1","J2","T1","T2","T3"],["J1","J2"],{"S":14,"T1":4,"T2":0,"T3":0},
        [("SJ1","S","J1",1),("J1T1","J1","T1",1),("J1J2","J1","J2",1),
         ("J2T2","J2","T2",1),("J2T3","J2","T3",1)])


def diamond(reverse=False):
    cross = ("BA","B","A",2) if reverse else ("AB","A","B",2)
    return model(["S","A","B","T"],["A","B"],{"S":10,"T":0},
        [("SA","S","A","4/9"),("AT","A","T","3/2"),("SB","S","B",6),("BT","B","T",1),cross])


def reseal(c):
    c["certificate_root"] = hashlib.sha256(json.dumps({k:v for k,v in c.items() if k!="certificate_root"},
        sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    return c


def bounds(rows, key):
    return {r[key]:(Q(r["lower"]),Q(r["upper"])) for r in rows}


def certify(m, target="1/1000000", **kw):
    c = p.compile_passive_pressure(m,pressure_width_target=target,**kw)
    assert c["status"] == "CERTIFIED_ENCLOSURE", c
    v = p.verify_passive_pressure(m,c,pressure_width_target=target)
    assert v["status"] == "PASS", v
    return c,v


@pytest.mark.parametrize("kind",["tree","binary_tree","loop","reversed_loop","zero_bridge"])
def test_exact_manufactured_tree_and_coupled_loop(kind):
    if kind=="tree":
        m=tree(); pressures={"J":1}; flows={"SJ":3,"JT1":1,"JT2":1,"JT3":1}
    elif kind=="binary_tree":
        m=binary_tree();pressures={"J1":5,"J2":1};flows={"SJ1":3,"J1T1":1,"J1J2":2,"J2T2":1,"J2T3":1}
    elif kind=="zero_bridge":
        m=diamond();m["boundary_heads"]["S"]=interval(8)
        for e in m["edges"]:e["resistance"]=interval(1)
        pressures={"A":4,"B":4};flows={"SA":2,"AT":2,"SB":2,"BT":2,"AB":0}
    else:
        reverse=kind=="reversed_loop";m=diamond(reverse)
        pressures={"A":6,"B":4};flows={"SA":3,"AT":2,"SB":1,"BT":2,"BA" if reverse else "AB":-1 if reverse else 1}
    original=deepcopy(m)
    c,v=certify(m)
    pb,fb=bounds(v["pressure_bounds"],"node"),bounds(v["flow_bounds"],"edge")
    for n,x in pressures.items():assert pb[n][0]<=x<=pb[n][1]
    for n,x in flows.items():assert fb[n][0]<=x<=fb[n][1]
    assert v["counts"]["edges"]==len(m["edges"])
    assert v["edge_enclosures_checked"]==3*len(m["edges"])
    assert v["internal_barriers_checked"]==2*len(m["internal_nodes"])
    assert Q(c["widths"]["maximum_internal_width"]) < Q(1,10000)
    assert m==original


@pytest.mark.parametrize("head",[0,3,-5])
def test_constant_uncertain_resistance_plateau_is_exact(head):
    m=diamond()
    m["boundary_heads"]={v:interval(head) for v in m["boundary_heads"]}
    for e in m["edges"]:e["resistance"]=interval("1/100",100)
    c,v=certify(m,target=0)
    assert c["widths"]["target_accuracy_met"] is True
    assert all(a==b==head for a,b in bounds(v["pressure_bounds"],"node").values())
    assert all(a==b==0 for a,b in bounds(v["flow_bounds"],"edge").values())


def test_boundary_only_parallel_edges_and_isolated_boundary():
    m=model(["S","T","ISOLATED"],[],{"S":4,"T":0,"ISOLATED":99},
        [("a","S","T",1),("b","S","T",4),("reverse","T","S",1)])
    c,v=certify(m,target=0)
    assert v["counts"]=={"nodes":3,"edges":3,"internal_nodes":0,"boundary_nodes":3,"components":2}
    assert bounds(v["flow_bounds"],"edge")=={"a":(2,2),"b":(1,1),"reverse":(-2,-2)}
    assert c["barrier_residuals"]==[]
    assert next(x for x in v["boundary_net_injections"] if x["node"]=="ISOLATED")["net_outgoing_flow"]==interval(0)


def test_multiple_grounded_components_with_no_edges():
    c,v=certify(model(["A","B"],[],{"A":1,"B":(2,3)},[]),target=0)
    assert c["flow_edges"]==[] and v["counts"]["components"]==2
    assert c["widths"]["maximum_internal_width"]=="0"


def test_reversal_box_is_unique_but_not_positive_delivery():
    m=model(["S","T"],[],{"S":("-1/1000000","1/1000000"),"T":0},[("e","S","T",1)])
    c,v=certify(m)
    lo,hi=bounds(v["flow_bounds"],"edge")["e"]
    assert lo<=Q(-1,1000)<0<Q(1,1000)<=hi
    assert v["limitations"]["minimum_delivery_or_velocity_requirements_checked"] is False


@pytest.mark.parametrize("name",["three_sink_tree","triangle_loop"])
def test_independent_retained_corner_and_interior_oracles(name):
    data=json.loads((STAGE/"evidence/reference-results.json").read_text())["cases"][name]
    source=data["model"]
    m=model(sorted(set(source["internal"])|set(source["boundary"])),source["internal"],
        {v:tuple(x) for v,x in source["boundary"].items()},[(n,u,v,tuple(r)) for n,u,v,r in source["edges"]])
    c,v=certify(m,target="1/100000000")
    assert c["widths"]["target_accuracy_met"] is False
    assert Q(c["widths"]["maximum_internal_width"])<Q(1,5)
    pb,fb=bounds(v["pressure_bounds"],"node"),bounds(v["flow_bounds"],"edge")
    eps=Q(1,10**60)
    for sample in data["independent_reference"]["records"]:
        for n,x in sample["pressure"].items():assert pb[n][0]-eps<=Q(x)<=pb[n][1]+eps
        for n,x in sample["flow"].items():assert fb[n][0]-eps<=Q(x)<=fb[n][1]+eps


def test_independent_coupled_loop_all_retained_parameter_cases():
    data=json.loads((STAGE/"evidence/independent-design-review/coupled-loop-result.json").read_text())
    m=model(["S","A","B","T"],["A","B"],{v:tuple(x) for v,x in data["boundary"].items()},
        [(n,u,v,tuple(r)) for n,u,v,r in data["edges"]])
    c,v=certify(m,target="1/100000000")
    assert c["widths"]["target_accuracy_met"] is False
    assert Q(c["widths"]["maximum_internal_width"])<1
    # Fixed nominal exact solution is independent of producer transition logic.
    pb,fb=bounds(v["pressure_bounds"],"node"),bounds(v["flow_bounds"],"edge")
    for n,x in {"A":6,"B":4}.items():assert pb[n][0]<=x<=pb[n][1]
    for n,x in {"SA":3,"AT":2,"SB":1,"BT":2,"BA":-1}.items():assert fb[n][0]<=x<=fb[n][1]
    samples=data.get("samples",data.get("records",[]))
    assert len(samples)==144
    eps=Q(1,10**55)
    for row in samples:
        for n,x in row["pressure"].items():assert pb[n][0]-eps<=Q(x)<=pb[n][1]+eps
        for n,x in row["flow"].items():assert fb[n][0]-eps<=Q(x)<=fb[n][1]+eps


def test_zero_refinement_is_complete_coarse_proof():
    c,v=certify(tree(),max_refinement_passes=0)
    assert bounds(v["pressure_bounds"],"node")["J"]==(0,10)
    assert c["widths"]["target_accuracy_met"] is False
    assert v["proof_complete"] is True


def test_verifier_never_invokes_producer_or_square_root_search(monkeypatch):
    m=diamond();c,_=certify(m)
    def forbidden(*a,**k):raise AssertionError("Producer called by verifier")
    for name in ("compile_passive_pressure","_sqrt","_producer_flow","_producer_edges","_producer_residual","_coordinate_residual","_refine"):
        monkeypatch.setattr(p,name,forbidden)
    assert p.verify_passive_pressure(m,c,pressure_width_target="1/1000000")["status"]=="PASS"


@pytest.mark.parametrize("mutation",[
    lambda m:m.pop("assumptions"),
    lambda m:m["assumptions"].update(junction_law="UPSTREAM_Q_TEE_LOSS"),
    lambda m:m["assumptions"]["units"].update(head="bar"),
    lambda m:m.update(context_root="not-a-root"),
    lambda m:m.update(physical_model_root="F"*64),
    lambda m:m["nodes"].append("J"),
    lambda m:m["internal_nodes"].append("J"),
    lambda m:m["internal_nodes"].append("S"),
    lambda m:m["internal_nodes"].clear(),
    lambda m:m["nodes"].append("MISSING"),
    lambda m:m["boundary_heads"].update(MISSING=interval(0)),
    lambda m:m["edges"].append(deepcopy(m["edges"][0])),
    lambda m:m["edges"][0].update(source="ABSENT"),
    lambda m:m["edges"][0].update(target="S"),
    lambda m:m["edges"][0].update(resistance=interval(0,1)),
    lambda m:m["edges"][0].update(resistance=interval(-1,1)),
    lambda m:m["edges"][0].update(resistance=interval(2,1)),
    lambda m:m["boundary_heads"]["S"].update(lower=True),
    lambda m:m["edges"][0]["resistance"].update(lower=float("nan")),
    lambda m:m["edges"][0]["resistance"].update(lower=float("inf")),
    lambda m:m["edges"][0]["resistance"].update(lower=1.0),
    lambda m:m["edges"][0]["resistance"].update(lower="1/0"),
    lambda m:m["edges"][0]["resistance"].update(lower="1e6"),
])
def test_invalid_graph_domain_units_and_loss_laws_fail_closed(mutation):
    m=tree();mutation(m)
    r=p.compile_passive_pressure(m)
    assert r["status"]=="INVALID_INPUT",r
    assert r["proof_complete"] is False


def test_ungrounded_component_is_rejected_even_if_zero_flow_would_solve():
    m=model(["S","A","B"],["A","B"],{"S":0},[("e","A","B",1)])
    r=p.compile_passive_pressure(m)
    assert r["status"]=="INVALID_INPUT" and "Dirichlet" in r["reason"]


@pytest.mark.parametrize("field",["lower_barrier_edges","upper_barrier_edges","flow_edges","pressure_bounds","barrier_residuals","boundary_net_injections","components"])
@pytest.mark.parametrize("action",["omit","duplicate"])
def test_exact_complete_certificate_denominators(field,action):
    m=tree();c,_=certify(m)
    if action=="omit":c[field].pop()
    else:c[field].append(deepcopy(c[field][0]))
    reseal(c)
    assert p.verify_passive_pressure(m,c,pressure_width_target="1/1000000")["status"]=="FAIL"


@pytest.mark.parametrize("mutation",[
    lambda c:c.update(model_root="f"*64),
    lambda c:c.update(domain_root="f"*64),
    lambda c:c.update(query_root="f"*64),
    lambda c:c.update(topology_root="f"*64),
    lambda c:c.update(context_root="f"*64),
    lambda c:c.update(physical_model_root="f"*64),
    lambda c:c.update(certificate_root="f"*64),
    lambda c:c["counts"].update(internal_nodes=True),
    lambda c:c["limitations"].update(native_geometry_or_interface_authority=True),
    lambda c:c["widths"].update(target_accuracy_met=False),
    lambda c:c["widths"].update(maximum_internal_width="0"),
    lambda c:c["flow_edges"][0]["flow"].update(lower="999"),
    lambda c:c["lower_barrier_edges"][0]["lower_endpoint_sqrt"].update(lower="-1"),
    lambda c:c["upper_barrier_edges"][0]["upper_endpoint_sqrt"].update(upper="0"),
    lambda c:c["barrier_residuals"][0]["lower_barrier"].update(upper="0"),
    lambda c:c["boundary_net_injections"][0].update(net_outgoing_flow=interval(0)),
    lambda c:c["producer_diagnostics"].update(sqrt_bits=True),
])
def test_coherently_resealed_false_proofs_rejected(mutation):
    m=tree();c,_=certify(m);mutation(c)
    if c["certificate_root"]!="f"*64:reseal(c)
    r=p.verify_passive_pressure(m,c,pressure_width_target="1/1000000")
    assert r["status"]=="FAIL",r


def test_changed_request_target_model_direction_resistance_and_boundary_rejected():
    original=tree();c,_=certify(original)
    assert p.verify_passive_pressure(original,c,pressure_width_target=None)["status"]=="FAIL"
    for kind in ("resistance","boundary","orientation"):
        m=deepcopy(original)
        if kind=="resistance":m["edges"][0]["resistance"]=interval(2)
        elif kind=="boundary":m["boundary_heads"]["S"]=interval(11)
        else:m["edges"][0]["source"],m["edges"][0]["target"]=m["edges"][0]["target"],m["edges"][0]["source"]
        assert p.verify_passive_pressure(m,c,pressure_width_target="1/1000000")["status"]=="FAIL"


@pytest.mark.parametrize("kwargs,reason",[
    ({"max_nodes":1},"NODE_BUDGET"),({"max_edges":1},"EDGE_BUDGET"),
    ({"max_work":1},"WORK_BUDGET"),({"max_input_bytes":256},"INPUT_BYTE_BUDGET"),
    ({"max_certificate_bytes":256},"CERTIFICATE_BYTE_BUDGET"),
])
def test_producer_budgets_never_publish_partial_proof(kwargs,reason):
    r=p.compile_passive_pressure(tree(),**kwargs)
    assert r["status"]=="UNKNOWN" and r["reason"]==reason and r["proof_complete"] is False,r


@pytest.mark.parametrize("kwargs",[{"max_work":1},{"max_nodes":1},{"max_edges":1},{"max_certificate_bytes":256}])
def test_checker_independent_budgets(kwargs):
    m=tree();c,_=certify(m)
    r=p.verify_passive_pressure(m,c,pressure_width_target="1/1000000",**kwargs)
    assert r["status"]=="UNKNOWN" and r["proof_complete"] is False


@pytest.mark.parametrize("kwargs",[{"max_nodes":True},{"max_edges":-1},{"max_work":0},{"sqrt_bits":0},
    {"max_refinement_passes":-1},{"pressure_width_target":True},{"pressure_width_target":"-1"},{"checkpoint":3}])
def test_invalid_controls(kwargs):
    assert p.compile_passive_pressure(tree(),**kwargs)["status"]=="INVALID_INPUT"


@pytest.mark.parametrize("bad",["1"*3000,1<<5000])
def test_oversized_rational_encoding_before_arithmetic(bad):
    m=tree();m["edges"][0]["resistance"]["upper"]=bad
    assert p.compile_passive_pressure(m)["status"]=="UNKNOWN"


@pytest.mark.parametrize("error",[ValueError("caller"),TimeoutError("caller"),p._Limit("caller"),p._RefinementLimit("caller")])
@pytest.mark.parametrize("stage",["passive_input_shape","passive_refinement_pass","passive_producer_complete","passive_verifier_complete"])
def test_caller_exception_identity(error,stage):
    m=tree();c,_=certify(m);before=deepcopy(m);prior=deepcopy(c)
    def check(current):
        if current==stage:raise error
    with pytest.raises(type(error)) as caught:
        if stage=="passive_verifier_complete":p.verify_passive_pressure(m,c,pressure_width_target="1/1000000",checkpoint=check)
        else:p.compile_passive_pressure(m,pressure_width_target="1/1000000",checkpoint=check)
    assert caught.value is error and m==before and c==prior


@pytest.mark.parametrize("method,target",[("producer","model"),("verifier","model"),("verifier","certificate")])
def test_final_callback_mutation_never_relabels_success(method,target):
    m=tree();c,_=certify(m);seen=[]
    def check(stage):
        seen.append(stage)
        if stage=="passive_"+method+"_complete":
            if target=="model":m["boundary_heads"]["S"]=interval(1000000)
            else:c["counts"]["edges"]=0
    if method=="producer":r=p.compile_passive_pressure(m,pressure_width_target="1/1000000",checkpoint=check)
    else:r=p.verify_passive_pressure(m,c,pressure_width_target="1/1000000",checkpoint=check)
    assert r["status"] in {"FAIL","INVALID_INPUT"},r
    assert seen[-1]=="passive_"+method+"_complete"


def test_frozen_copy_rechecks_node_budget_after_early_callback_mutation():
    small=model(["S"],[],{"S":0},[]);large=model(["S","T"],[],{"S":0,"T":1},[])
    fired=False
    def check(stage):
        nonlocal fired
        if stage=="passive_input_shape" and not fired:
            fired=True;small.clear();small.update(deepcopy(large))
    r=p.compile_passive_pressure(small,max_nodes=1,checkpoint=check)
    assert r["status"]=="UNKNOWN" and r["reason"]=="NODE_BUDGET"


def test_no_callbacks_after_final_success_pulse():
    m=tree();seen=[]
    c=p.compile_passive_pressure(m,checkpoint=seen.append)
    assert c["status"]=="CERTIFIED_ENCLOSURE" and seen[-1]=="passive_producer_complete"
    seen=[];r=p.verify_passive_pressure(m,c,checkpoint=seen.append)
    assert r["status"]=="PASS" and seen[-1]=="passive_verifier_complete"
