from copy import deepcopy
from fractions import Fraction as Q
import hashlib
import json

import pytest

from oma.optimization import coupled_tree_pressure as c


def interval(lo, hi=None):
    return {"lower": str(lo), "upper": str(lo if hi is None else hi)}


def example(uncertain=False):
    leaves = ["A", "B", "C"]
    rows = [
        ("trunk", "1/10", "ABC", "ABC"),
        ("tee1-straight", "1/5", "ABC", "BC"),
        ("tee1-branch", "3/10", "ABC", "A"),
        ("connector", "3/20", "BC", "BC"),
        ("tee2-straight", "1/4", "BC", "B"),
        ("tee2-branch", "2/5", "BC", "C"),
        ("leaf-A", "1/2", "A", "A"),
        ("leaf-B", "3/5", "B", "B"),
        ("leaf-C", "7/10", "C", "C"),
    ]
    coeff = {name: interval(Q(a)*Q(999,1000), Q(a)*Q(1001,1000)) if uncertain else interval(a)
             for name,a,_,_ in rows}
    heads = {"A": Q(149,10), "B": Q(116,5), "C": Q(617,20)}
    model = {"schema": c.MODEL_SCHEMA, "leaves": leaves, "coefficients": coeff,
             "terms": [{"id": name, "coefficient_id": name, "descendant_leaves": list(d), "applies_to_leaves": list(a)}
                       for name,_,d,a in rows],
             "available_heads": {k: interval(v-Q(1,1000),v+Q(1,1000)) if uncertain else interval(v) for k,v in heads.items()},
             "context_root": "1"*64, "physical_model_root": "2"*64, "assumptions": deepcopy(c.MODEL_ASSUMPTIONS)}
    box = {k: interval(Q(i)-Q(1,10),Q(i)+Q(1,10)) for i,k in enumerate(leaves,1)}
    return model,box


def seal(packet):
    packet["certificate_root"] = hashlib.sha256(json.dumps({k:v for k,v in packet.items() if k != "certificate_root"},
                                    sort_keys=True,separators=(",", ":"),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    return packet


@pytest.fixture(scope="module")
def actual():
    m,b = example(True)
    packet = c.compile_coupled_tree_pressure(m,b)
    assert packet["status"] == "CERTIFIED_BOX", packet
    assert c.verify_coupled_tree_pressure(m,b,packet)["status"] == "PASS"
    return m,b,packet


def test_manufactured_nonsymmetric_exact_root():
    m,b = example()
    packet = c.compile_coupled_tree_pressure(m,b)
    assert packet["status"] == "CERTIFIED_BOX", packet
    assert c.verify_coupled_tree_pressure(m,b,packet)["status"] == "PASS"
    assert packet["inverse_witness"] == [["29/5","24/5","24/5"],["18/5","10","38/5"],["18/5","91/10","133/10"]]
    for i,k in enumerate(m["leaves"],1):
        assert packet["center_residual"][k] == interval(0)
        e = packet["root_enclosure"][k]
        assert Q(e["lower"]) <= i <= Q(e["upper"])
        assert Q(b[k]["lower"]) < Q(e["lower"]) < Q(e["upper"]) < Q(b[k]["upper"])
    assert packet["scope"] == c.SCOPE
    assert all(v is False for v in packet["limitations"].values())


def test_uniform_box_has_positive_margin(actual):
    m,b,packet = actual
    assert 0 < Q(packet["contraction_norm_upper"]) < 1
    assert all(Q(x)>0 for row in packet["inclusion_margins"].values() for x in row.values())
    assert packet["counts"] == {"variables":3,"equations":3,"terms":9,"coefficients":9,"entries_per_matrix":9}


def test_single_leaf_exact_inverse_and_zero_terms():
    m,b = example()
    m["leaves"]=["A"];m["coefficients"]={"a":interval(2),"zero":interval(0)}
    m["terms"]=[{"id":k,"coefficient_id":k,"descendant_leaves":["A"],"applies_to_leaves":["A"]} for k in m["coefficients"]]
    m["available_heads"]={"A":interval(8)};b={"A":interval("19/10","21/10")}
    packet=c.compile_coupled_tree_pressure(m,b)
    assert packet["status"]=="CERTIFIED_BOX"
    assert packet["preconditioner"]==[["1/8"]]
    assert c.verify_coupled_tree_pressure(m,b,packet)["status"]=="PASS"


def test_reused_named_coefficient_parameter_identity():
    m,b = example()
    m["coefficients"]["shared"]=interval("1/1000","1/500")
    for k in ("A","B"):
        m["terms"].append({"id":"extra-"+k,"coefficient_id":"shared","descendant_leaves":[k],"applies_to_leaves":[k]})
    packet=c.compile_coupled_tree_pressure(m,b)
    assert packet["status"]=="CERTIFIED_BOX"
    assert packet["counts"]["coefficients"]==10 and packet["counts"]["terms"]==11
    assert c.verify_coupled_tree_pressure(m,b,packet)["status"]=="PASS"


def test_checker_does_not_run_producer(monkeypatch,actual):
    def fail(*args,**kwargs):
        raise AssertionError("Producer must not run in independent checker")
    for name in ("compile_coupled_tree_pressure","_inverse","_produce_polynomial","_term_values"):
        monkeypatch.setattr(c,name,fail)
    assert c.verify_coupled_tree_pressure(*actual)["status"]=="PASS"


@pytest.mark.parametrize("field",["model_root","query_root","box_root","parameter_root","topology_root","context_root","physical_model_root"])
def test_resealed_wrong_roots(actual,field):
    m,b,p = deepcopy(actual);p[field]="f"*64
    assert c.verify_coupled_tree_pressure(m,b,seal(p))["status"]=="FAIL"


@pytest.mark.parametrize("path,value",[
    (("center","A"),"101/100"),
    (("preconditioner",0,0),"0"),
    (("inverse_witness",1,2),"1"),
    (("inverse_products","left",0,0),"0"),
    (("inverse_products","right",0,1),"1"),
    (("term_evidence",0,"subtree_at_center"),"6"),
    (("term_evidence",0,"subtree_in_box","lower"),"1"),
    (("term_evidence",0,"loss_at_center","upper"),"0"),
    (("term_evidence",0,"derivative_in_box","upper"),"0"),
    (("center_residual","A","lower"),"0"),
    (("jacobian",0,1,"lower"),"0"),
    (("derivative_map",0,1,"upper"),"0"),
    (("center_image","B","upper"),"0"),
    (("root_enclosure","C","lower"),"3"),
    (("inclusion_margins","A","lower"),"10"),
    (("row_norm_upper",0),"0"),
    (("contraction_norm_upper",),"0"),
    (("counts","terms"),8),
    (("scope",),"GLOBAL_UNIQUE"),
    (("limitations","other_equilibria_excluded"),True),
    (("assumptions","regime"),"ANY_SIGN"),
])
def test_resealed_false_semantics(actual,path,value):
    m,b,p = deepcopy(actual);obj=p
    for key in path[:-1]: obj=obj[key]
    assert obj[path[-1]] != value
    obj[path[-1]]=value
    assert c.verify_coupled_tree_pressure(m,b,seal(p))["status"]=="FAIL"


@pytest.mark.parametrize("kind",["term_missing","term_duplicate","matrix_row_missing","matrix_column_extra","equation_missing","center_missing","proof_field_extra","proof_field_missing"])
def test_complete_proof_denominators(actual,kind):
    m,b,p=deepcopy(actual)
    if kind=="term_missing":p["term_evidence"].pop()
    elif kind=="term_duplicate":p["term_evidence"][1]=p["term_evidence"][0]
    elif kind=="matrix_row_missing":p["preconditioner"].pop()
    elif kind=="matrix_column_extra":p["preconditioner"][0].append("0")
    elif kind=="equation_missing":p["inventories"]["equation_terms"].pop("B")
    elif kind=="center_missing":p["center"].pop("C")
    elif kind=="proof_field_extra":p["trust_me"]=True
    else:p.pop("row_norm_upper")
    assert c.verify_coupled_tree_pressure(m,b,seal(p))["status"]=="FAIL"


@pytest.mark.parametrize("kind",["duplicate_leaf","duplicate_term","duplicate_descendant","missing_head","missing_box","extra_head","unused_coefficient","unknown_coefficient","unused_leaf","negative_coefficient","reversed_head","nonlaminar","application_not_descendant","missing_assumption","extra_model","zero_box","negative_box","point_box"])
def test_invalid_model(kind):
    m,b=example()
    if kind=="duplicate_leaf":m["leaves"].append("A")
    elif kind=="duplicate_term":m["terms"].append(m["terms"][0])
    elif kind=="duplicate_descendant":m["terms"][0]["descendant_leaves"].append("A")
    elif kind=="missing_head":m["available_heads"].pop("A")
    elif kind=="missing_box":b.pop("A")
    elif kind=="extra_head":m["available_heads"]["D"]=interval(1)
    elif kind=="unused_coefficient":m["coefficients"]["unused"]=interval(1)
    elif kind=="unknown_coefficient":m["terms"][0]["coefficient_id"]="missing"
    elif kind=="unused_leaf":m["leaves"].append("D");m["available_heads"]["D"]=interval(1);b["D"]=interval(1,2)
    elif kind=="negative_coefficient":m["coefficients"]["trunk"]=interval(-1,1)
    elif kind=="reversed_head":m["available_heads"]["A"]=interval(10,1)
    elif kind=="nonlaminar":m["terms"][0]["descendant_leaves"]=["A","B"];m["terms"][0]["applies_to_leaves"]=["A"]
    elif kind=="application_not_descendant":m["terms"][-1]["applies_to_leaves"]=["A"]
    elif kind=="missing_assumption":m["assumptions"].pop("regime")
    elif kind=="extra_model":m["native_pass"]=True
    elif kind=="zero_box":b["A"]=interval(0,1)
    elif kind=="negative_box":b["A"]=interval(-1,1)
    else:b["A"]=interval(1)
    assert c.compile_coupled_tree_pressure(m,b)["status"]=="INVALID_INPUT"


@pytest.mark.parametrize("bad",[True,False,1.0,float("nan"),float("inf"),"NaN","Infinity","1/0","1e10",None])
def test_malformed_rationals_fail_closed(bad):
    m,b=example();m["coefficients"]["trunk"]["lower"]=bad
    assert c.compile_coupled_tree_pressure(m,b)["status"]=="INVALID_INPUT"


@pytest.mark.parametrize("kind",["singular","large_box","far_head","negative_head"])
def test_no_proof_is_unknown_not_infeasible(kind):
    m,b=example()
    if kind=="singular":m["coefficients"]={k:interval(0) for k in m["coefficients"]}
    elif kind=="large_box":b={k:interval("1/100",10) for k in b}
    elif kind=="far_head":m["available_heads"]["A"]=interval(10000)
    else:m["available_heads"]["A"]=interval(-1)
    r=c.compile_coupled_tree_pressure(m,b)
    assert r["status"]=="UNKNOWN" and r["proof_complete"] is False


@pytest.mark.parametrize("kwargs",[{"max_leaves":2},{"max_terms":8},{"max_matrix_entries":8},{"max_work":1},{"max_input_bytes":256},{"max_certificate_bytes":256},{"max_rational_bits":32}])
def test_resource_unknown(actual,kwargs):
    m,b,p=deepcopy(actual)
    if kwargs.get("max_rational_bits")==32:
        m["available_heads"]["A"]=interval("100000000000000000000000000000/7")
    assert c.compile_coupled_tree_pressure(m,b,**kwargs)["status"]=="UNKNOWN"
    assert c.verify_coupled_tree_pressure(m,b,p,**kwargs)["status"]=="UNKNOWN"


@pytest.mark.parametrize("kwargs",[{"max_leaves":True},{"max_leaves":33},{"max_terms":0},{"max_matrix_entries":1025},{"max_work":0},{"max_input_bytes":128},{"max_certificate_bytes":128},{"checkpoint":2}])
def test_invalid_budget(kwargs):
    assert c.compile_coupled_tree_pressure(*example(),**kwargs)["status"]=="INVALID_INPUT"


@pytest.mark.parametrize("verify",[False,True])
@pytest.mark.parametrize("exception",[TimeoutError("deadline"),ValueError("cancel"),c.p._Limit("external budget")])
def test_callback_exception_identity(actual,verify,exception):
    m,b,p=deepcopy(actual)
    def callback(stage):
        if stage==("coupled_verifier_complete" if verify else "coupled_producer_complete"):
            raise exception
    with pytest.raises(type(exception)) as caught:
        if verify:c.verify_coupled_tree_pressure(m,b,p,checkpoint=callback)
        else:c.compile_coupled_tree_pressure(m,b,checkpoint=callback)
    assert caught.value is exception


@pytest.mark.parametrize("verify,target",[(False,"model"),(False,"box"),(True,"model"),(True,"box"),(True,"certificate")])
def test_final_callback_mutation(actual,verify,target):
    m,b,p=deepcopy(actual);seen=[]
    def callback(stage):
        if seen:raise AssertionError("Callback after final publication checkpoint")
        if stage==("coupled_verifier_complete" if verify else "coupled_producer_complete"):
            seen.append(stage)
            if target=="model":m["available_heads"]["A"]["upper"]="1000000"
            elif target=="box":b["A"]["lower"]="1/10"
            else:p["root_enclosure"]["A"]["lower"]="0"
    r=c.verify_coupled_tree_pressure(m,b,p,checkpoint=callback) if verify else c.compile_coupled_tree_pressure(m,b,checkpoint=callback)
    assert r["status"]==( "FAIL" if verify else "INVALID_INPUT") and seen


@pytest.mark.parametrize("verify",[False,True])
def test_shape_limits_rechecked_after_callback(actual,verify):
    m,b,p=deepcopy(actual);fired=[]
    def callback(stage):
        if not fired:
            fired.append(stage);m["leaves"].extend(["X"]*20)
    r=c.verify_coupled_tree_pressure(m,b,p,checkpoint=callback) if verify else c.compile_coupled_tree_pressure(m,b,checkpoint=callback)
    assert r["status"]=="UNKNOWN" and r["reason"]=="VARIABLE_BUDGET"


@pytest.mark.parametrize("a,z",[((-2,3),(-4,5)),((0,0),(-2,3)),((-3,-1),(2,4)),((-2,3),(0,0))])
def test_signed_interval_multiplication(a,z):
    budget=c._Budget(1,1,1,1000,128,1024,1024,None)
    result=c._times(tuple(map(Q,a)),tuple(map(Q,z)),budget)
    for i in range(21):
        for j in range(21):
            value=(Q(a[0])+Q(i,20)*(a[1]-a[0]))*(Q(z[0])+Q(j,20)*(z[1]-z[0]))
            assert result[0]<=value<=result[1]
