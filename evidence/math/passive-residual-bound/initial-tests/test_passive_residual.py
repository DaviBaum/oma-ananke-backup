from copy import deepcopy
from decimal import Decimal,localcontext
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path

import pytest

from oma.optimization import passive_pressure as p,passive_residual as r


def interval(a,b=None):return {"lower":str(a),"upper":str(a if b is None else b)}


def model(nodes,internal,boundary,edges):
    return {"schema":p.MODEL_SCHEMA,"nodes":list(nodes),"internal_nodes":list(internal),
        "boundary_heads":{v:interval(*h) if type(h) is tuple else interval(h) for v,h in boundary.items()},
        "edges":[{"id":n,"source":u,"target":v,"resistance":interval(*k) if type(k) is tuple else interval(k)} for n,u,v,k in edges],
        "context_root":"a"*64,"physical_model_root":"b"*64,"assumptions":deepcopy(p.MODEL_ASSUMPTIONS)}


def series(k1=3,k2=1):
    return model(["S","J","T"],["J"],{"S":4,"T":0},[("a","S","J",k1),("b","J","T",k2)])


def tree():
    return model(["S","J1","J2","T1","T2","T3"],["J1","J2"],{"S":14,"T1":4,"T2":0,"T3":0},
        [("a","S","J1",1),("b","J1","T1",1),("c","J1","J2",1),("d","J2","T2",1),("e","J2","T3",1)])


def loop(reverse=False):
    return model(["S","A","B","T"],["A","B"],{"S":10,"T":0},
        [("SA","S","A","4/9"),("AT","A","T","3/2"),("SB","S","B",6),("BT","B","T",1),
         ("cross","B","A",2) if reverse else ("cross","A","B",2)])


def certify(m,x,**kw):
    c=r.compile_passive_residual(m,x,**kw)
    assert c["status"]=="CERTIFIED_BOUND",c
    vk={k:v for k,v in kw.items() if k!="sqrt_bits"}
    v=r.verify_passive_residual(m,x,c,**vk)
    assert v["status"]=="PASS",v
    return c,v


def reseal(c):
    c["certificate_root"]=hashlib.sha256(json.dumps({k:v for k,v in c.items() if k!="certificate_root"},sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    return c


@pytest.mark.parametrize("m,x",[(series(),{"J":"1"}),(tree(),{"J1":"5","J2":"1"}),
    (loop(),{"A":"6","B":"4"}),(loop(True),{"A":"6","B":"4"})])
def test_exact_manufactured_equilibrium_has_zero_error(m,x):
    c,v=certify(m,x,pressure_error_target="0")
    assert v["pressure_l2_error_upper"]=="0" and v["target_accuracy_met"] is True
    assert all(row["flow_error_upper"]=="0" for row in v["flow_error_bounds"])


def test_perturbed_pressure_error_is_not_residual():
    c,v=certify(series(),{"J":"9/10"})
    assert Q(v["pressure_l2_error_upper"])>=Q(1,10)
    assert Q(v["residual_norm"]["upper"])<Q(1,10)
    assert Q(v["sigma_head_per_flow"])>1


def test_small_residual_without_stability_can_hide_large_error():
    m=model(["S","J","T"],["J"],{"S":2,"T":0},[("a","S","J",10**12),("b","J","T",10**12)])
    c,v=certify(m,{"J":"0"},pressure_error_target="1/10")
    assert Q(v["residual_norm"]["upper"])<Q(1,100000)
    assert Q(v["pressure_l2_error_upper"])>=1
    assert v["target_accuracy_met"] is False


@pytest.mark.parametrize("boundary",[{"S":0,"T":0},{"S":7,"T":7}])
def test_flat_uncertain_resistance_component_has_exact_zero(boundary):
    m=model(["S","J","T"],["J"],boundary,[("a","S","J",(1,9)),("b","J","T",(2,5))])
    c,v=certify(m,{"J":str(boundary["S"])},max_path_steps=0,pressure_error_target="0")
    assert c["sigma_head_per_flow"]=="0"
    assert all(row["lower"] is None for row in c["conductances"])
    assert v["pressure_l2_error_upper"]=="0"


def test_boundary_only_family_has_zero_error_but_nonzero_uncertainty():
    m=model(["S","T"],[],{"S":(1,4),"T":(-1,0)},[("a","S","T",(1,4))])
    c,v=certify(m,{},max_path_steps=0)
    assert c["sigma_head_per_flow"]=="0" and v["pressure_l2_error_upper"]=="0"
    row=v["flow_error_bounds"][0]
    assert row["flow_error_upper"]=="0"
    assert Q(row["flow_enclosure"]["upper"])>Q(row["flow_enclosure"]["lower"])
    assert v["flow_reference"]=="PARAMETERIZED_APPROXIMATE_FAMILY_USING_ACTUAL_BOUNDARY_TUPLE"


def test_unguarded_boundary_midpoints_cannot_replace_actual_tuple():
    m=model(["S","J","T"],["J"],{"S":(2,4),"T":0},[("a","S","J",1),("b","J","T",1)])
    c,v=certify(m,{"J":"3/2"})
    assert Q(v["pressure_l2_error_upper"])>=Q(1,2)
    assert Q(c["residual_squared_norm_upper"])>0


def test_zero_flow_bridge_and_zero_crossing_factor_two():
    m=model(["S","A","B","T"],["A","B"],{"S":1,"T":-1},
        [("SA","S","A",1),("AT","A","T",1),("SB","S","B",1),("BT","B","T",1),("AB","A","B",1)])
    c,v=certify(m,{"A":"1/100","B":"-1/100"})
    row=next(x for x in v["flow_error_bounds"] if x["edge"]=="AB")
    assert Q(row["flow_enclosure"]["lower"])<=0<=Q(row["flow_enclosure"]["upper"])
    assert Q(2)**2>Q(1)-Q(-1)  # psi(1)-psi(-1)=2; factor-one Holder bound is false.


def test_independent_coupled_loop_all_parameter_samples():
    path=Path(__file__).parent/"fixtures/passive-residual/coupled-loop-result.json"
    raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()=="9328d26b128981a7b559832d6f7cc58e2d9f5a79ecc8a11167fa0ae8f23c7333"
    ref=json.loads(raw.decode("utf-8"))
    m=model(["S","A","B","T"],["A","B"],{k:tuple(v) for k,v in ref["boundary"].items()},
        [(n,u,v,tuple(k)) for n,u,v,k in ref["edges"]])
    x={"A":"6","B":"4"};c,v=certify(m,x)
    E=Q(v["pressure_l2_error_upper"])
    bounds={row["edge"]:row for row in v["flow_error_bounds"]}
    with localcontext() as ctx:
        ctx.prec=80
        def dec(q):q=Q(q);return Decimal(q.numerator)/Decimal(q.denominator)
        for sample in ref["samples"]:
            errors=[Q(sample["pressures"][i])-Q(x[i]) for i in x]
            assert sum(z*z for z in errors)<=E*E
            for name,u,w,_ in ref["edges"]:
                hu=x[u] if u in x else sample["parameters"][u]
                hv=x[w] if w in x else sample["parameters"][w]
                drop=dec(hu)-dec(hv);k=dec(sample["parameters"][name])
                qhat=(abs(drop)/k).sqrt()*(1 if drop>=0 else -1)
                actual=Decimal(sample["flows"][name]);row=bounds[name]
                assert abs(actual-qhat)<=dec(row["flow_error_upper"])
                assert dec(row["flow_enclosure"]["lower"])<=actual<=dec(row["flow_enclosure"]["upper"])


@pytest.mark.parametrize("bad",[{}, {"J":"5"},{"J":True},{"J":float("nan")},{"J":"1/0"},{"J":"1e0"},{"J":"1","other":"1"}])
def test_invalid_approximation(bad):
    assert r.compile_passive_residual(series(),bad)["status"]!="CERTIFIED_BOUND"


@pytest.mark.parametrize("change",["ungrounded","negative_k","missing_assumption","unknown_endpoint","duplicate_edge"])
def test_invalid_graph(change):
    m=series()
    if change=="ungrounded":m["boundary_heads"]={};m["internal_nodes"]=m["nodes"]
    if change=="negative_k":m["edges"][0]["resistance"]["lower"]="-1"
    if change=="missing_assumption":del m["assumptions"]["regime"]
    if change=="unknown_endpoint":m["edges"][0]["source"]="phantom"
    if change=="duplicate_edge":m["edges"].append(deepcopy(m["edges"][0]))
    assert r.compile_passive_residual(m,{"J":"1"})["status"]!="CERTIFIED_BOUND"


@pytest.fixture(scope="module")
def checked():
    m=loop(True);x={"A":"59/10","B":"41/10"};c,v=certify(m,x)
    return m,x,c


@pytest.mark.parametrize("field",["conductances","grounding_paths","approximate_flow_edges","residuals","pressure_bounds","solution_flow_edges","flow_error_bounds"])
@pytest.mark.parametrize("mode",["missing","duplicate"])
def test_complete_denominator(checked,field,mode):
    m,x,c=deepcopy(checked)
    if mode=="missing":c[field].pop()
    else:c[field][-1]=deepcopy(c[field][0])
    assert r.verify_passive_residual(m,x,reseal(c))["status"]=="FAIL"


@pytest.mark.parametrize("attack",["huge_conductance","negative_conductance","fake_span","ungrounded_path","wrong_edge","false_sum",
    "sigma_zero","norm_zero","error_zero","false_accuracy","wrong_head","false_flow_error","omit_factor_two","wrong_context","wrong_bool_count"])
def test_coherently_resealed_false_proof(checked,attack):
    m,x,c=deepcopy(checked)
    if attack=="huge_conductance":c["conductances"][0]["lower"]="1000000000"
    if attack=="negative_conductance":c["conductances"][0]["lower"]="-1"
    if attack=="fake_span":c["conductances"][0]["span"]="0"
    if attack=="ungrounded_path":c["grounding_paths"][0]["nodes"][-1]="A"
    if attack=="wrong_edge":c["grounding_paths"][0]["edges"][0]="missing"
    if attack=="false_sum":c["grounding_paths"][0]["resistance_sum"]="0"
    if attack=="sigma_zero":c["sigma_head_per_flow"]="0"
    if attack=="norm_zero":c["residual_norm"]=interval(0)
    if attack=="error_zero":c["pressure_l2_error_upper"]="0"
    if attack=="false_accuracy":c["target_accuracy_met"]=True
    if attack=="wrong_head":c["pressure_bounds"][0]["upper"]="1000000"
    if attack=="false_flow_error":c["flow_error_bounds"][0]["flow_error_upper"]="0"
    if attack=="omit_factor_two":
        row=c["flow_error_bounds"][0]
        name=row["edge"];k=Q(next(e for e in m["edges"] if e["id"]==name)["resistance"]["lower"])
        b=p._Budget(64,128,100000,4096,1048576,16777216,None)
        row["sqrt_error"]=p._enc(p._sqrt(Q(row["drop_error_upper"])/k,96,b))
    if attack=="wrong_context":c["context_root"]="c"*64
    if attack=="wrong_bool_count":c["counts"]["components"]=True
    assert r.verify_passive_residual(m,x,reseal(c))["status"]=="FAIL"


def test_verifier_never_calls_producer(checked,monkeypatch):
    m,x,c=checked
    def forbidden(*a,**k):raise AssertionError("Producer called")
    for name in ("_make_conductances","_make_paths","compile_passive_residual"):monkeypatch.setattr(r,name,forbidden)
    for name in ("_sqrt","_producer_flow","_producer_edges","_producer_residual"):monkeypatch.setattr(p,name,forbidden)
    assert r.verify_passive_residual(m,x,c)["status"]=="PASS"


@pytest.mark.parametrize("options",[{"max_work":1},{"max_nodes":2},{"max_edges":0},{"max_path_steps":0},
    {"max_input_bytes":256},{"max_certificate_bytes":256},{"max_rational_bits":32,"sqrt_bits":8}])
def test_budget_unknown_no_partial_claim(options):
    out=r.compile_passive_residual(series(),{"J":"9/10"},**options)
    assert out["status"]=="UNKNOWN",out
    assert out["proof_complete"] is False


def test_certificate_byte_limit_before_fraction_parse(checked,monkeypatch):
    m,x,c=deepcopy(checked)
    def forbidden(*a,**k):raise AssertionError("Rational parsed before certificate byte limit")
    monkeypatch.setattr(p,"_q",forbidden)
    out=r.verify_passive_residual(m,x,c,max_certificate_bytes=1024)
    assert out["status"]=="UNKNOWN"


@pytest.mark.parametrize("exception",[ValueError,TimeoutError,p._Limit])
@pytest.mark.parametrize("phase",["passive_input_shape","residual_producer_path_search","residual_producer_complete"])
def test_caller_exception_identity(exception,phase):
    exc=exception("caller")
    def stop(stage):
        if stage==phase:raise exc
    with pytest.raises(exception) as caught:r.compile_passive_residual(series(),{"J":"9/10"},checkpoint=stop)
    assert caught.value is exc


@pytest.mark.parametrize("target",["model","approximation","certificate"])
def test_final_verifier_mutation_is_rejected(checked,target):
    m,x,c=deepcopy(checked);calls=[]
    def mutate(stage):
        calls.append(stage)
        if stage=="residual_verifier_complete":
            if target=="model":m["edges"][0]["resistance"]["upper"]="1000"
            if target=="approximation":x["A"]="0"
            if target=="certificate":c["pressure_l2_error_upper"]="0"
    assert r.verify_passive_residual(m,x,c,checkpoint=mutate)["status"]=="FAIL"
    assert calls[-1]=="residual_verifier_complete"


def test_final_producer_mutation_is_rejected():
    m=series();x={"J":"9/10"};calls=[]
    def mutate(stage):
        calls.append(stage)
        if stage=="residual_producer_complete":x["J"]="1"
    assert r.compile_passive_residual(m,x,checkpoint=mutate)["status"]=="INVALID_INPUT"
    assert calls[-1]=="residual_producer_complete"


def test_frozen_input_shape_is_rechecked_after_callback():
    m=series();x={"J":"1"}
    def mutate(stage):
        if stage=="passive_input_shape":
            m["nodes"]=["S","J","T","EXTRA"]
    out=r.compile_passive_residual(m,x,max_nodes=3,checkpoint=mutate)
    assert out["status"]=="UNKNOWN" and out["reason"]=="NODE_BUDGET"
