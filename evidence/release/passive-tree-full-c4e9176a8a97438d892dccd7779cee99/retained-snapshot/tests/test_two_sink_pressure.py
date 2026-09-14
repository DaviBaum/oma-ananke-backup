"""Independent equations/oracles and hostile proof boundaries for the staged kernel."""
from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction as F
from itertools import product
import hashlib
import json
import random

import pytest
from oma.optimization import two_sink_pressure as k


def model(**overrides):
    values = dict(P1=23, P2=55, beta=1, A1=2, A2=3, B1=5, B2=7)
    values.update(overrides)
    return {"schema": k.MODEL_SCHEMA, "branch_ids": ["sink-one", "sink-two"],
        "parameters": {key: {"lower": str(value[0]), "upper": str(value[1])}
            if isinstance(value, tuple) else {"lower": str(value), "upper": str(value)} for key, value in values.items()},
        "context_root": "a" * 64, "physical_model_root": "b" * 64,
        "assumptions": deepcopy(k.MODEL_ASSUMPTIONS)}


def bounds(value):
    return F(value["lower"]), F(value["upper"])


def inside(value, interval):
    lo, hi = bounds(interval)
    if isinstance(value, Decimal):
        lo, hi = Decimal(lo.numerator) / Decimal(lo.denominator), Decimal(hi.numerator) / Decimal(hi.denominator)
    assert lo <= value <= hi, (value, interval)


def certified(m, **kwargs):
    compiled = k.compile_two_sink_pressure(m, **kwargs)
    assert compiled["status"] == "CERTIFIED", compiled
    check_kwargs = {key: value for key, value in kwargs.items() if key not in {"max_refinements", "sqrt_bits"}}
    check = k.verify_two_sink_pressure(m, compiled["certificate"], **check_kwargs)
    assert check["status"] == "PASS", check
    assert check["certificate_root"] == compiled["certificate_root"]
    assert check["physical_acceptance_authority"] is False
    assert check["infeasibility_claim"] is False
    return compiled["certificate"]


def oracle(values):
    """Quadratic formula independently derived by expanding the two path equations.

    This is test ground truth, never a universal interval certificate or kernel call.
    """
    with localcontext() as ctx:
        ctx.prec = 100
        p = {key: Decimal(F(value).numerator) / Decimal(F(value).denominator) for key, value in values.items()}
        a = p["P2"] * p["B1"] - p["P1"] * p["B2"]
        b = 2 * p["P1"] * p["B2"]
        c = p["P2"] * p["A1"] - p["P1"] * (p["A2"] + p["B2"])
        if a == 0:
            t = -c / b
        else:
            disc = b * b - 4 * a * c
            candidates = [(-b + disc.sqrt()) / (2 * a), (-b - disc.sqrt()) / (2 * a)]
            valid = [t for t in candidates if 0 < t < 1]
            assert len(valid) == 1, (p, valid)
            t = valid[0]
        q = (p["P1"] / (p["beta"] * (p["A1"] + p["B1"] * t * t))).sqrt()
        return t, q, t * q, (1-t) * q


def test_manufactured_exact_solution_and_canonical_root():
    m = model()
    proof = certified(m)
    e = proof["enclosures"]
    for value, field in ((F(1, 3), "split_fraction"), (F(9), "total_flow_squared_m6_s2"), (F(3), "total_flow_m3_s")):
        inside(value, e[field])
    inside(F(1), e["branch_flows_m3_s"]["sink-one"])
    inside(F(2), e["branch_flows_m3_s"]["sink-two"])
    assert proof["accuracy"]["target_split_width_met"] is True
    digest = hashlib.sha256(json.dumps(proof, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    assert k.verify_two_sink_pressure(m, proof)["certificate_root"] == digest


def test_symmetric_and_original_series_inverse_reference():
    # Original P6's K=5, pressure [20,45] gives flow [2,3]. In the symmetric
    # two-branch model A=0,B=5,beta=1 and each delivered flow obeys that law.
    proof = certified(model(P1=(20,45), P2=(20,45), A1=0, A2=0, B1=5, B2=5))
    for branch in proof["enclosures"]["branch_flows_m3_s"].values():
        inside(F(2), branch)
        inside(F(3), branch)
    exact = certified(model(P1=20, P2=20, A1=0, A2=0, B1=5, B2=5))
    assert bounds(exact["enclosures"]["split_fraction"]) == (F(1,2), F(1,2))
    assert bounds(exact["enclosures"]["total_flow_m3_s"]) == (F(4), F(4))


@pytest.mark.parametrize("seed", range(24))
def test_independently_derived_quadratic_root(seed):
    rng = random.Random(seed)
    t = F(rng.randint(1, 8), 9)
    q = F(rng.randint(1, 20), rng.randint(1, 5))
    values = dict(beta=F(rng.randint(1, 7),3), A1=F(rng.randint(0, 5),2), A2=F(rng.randint(0,5),3),
        B1=F(rng.randint(1,9),2), B2=F(rng.randint(1,9),3))
    values["P1"] = values["beta"] * q*q * (values["A1"] + values["B1"]*t*t)
    values["P2"] = values["beta"] * q*q * (values["A2"] + values["B2"]*(1-t)*(1-t))
    proof = certified(model(**values))
    expected = oracle(values)
    e = proof["enclosures"]
    with localcontext() as ctx:
        ctx.prec = 90
        for actual, interval in zip(expected, [e["split_fraction"], e["total_flow_m3_s"], *e["branch_flows_m3_s"].values()]):
            inside(actual, interval)
    inside(t, e["split_fraction"])
    inside(q, e["total_flow_m3_s"])


def test_all_interval_corners_and_interior_reference_solutions():
    m = model(P1=(22,24), P2=(54,56), beta=(F(9,10), F(11,10)), A1=(F(19,10),F(21,10)),
        A2=(F(29,10),F(31,10)), B1=(F(49,10),F(51,10)), B2=(F(69,10),F(71,10)))
    proof = certified(m)
    e = proof["enclosures"]
    assert proof["accuracy"]["target_split_width_met"] is False
    assert F(proof["accuracy"]["achieved_split_width"]) > F(1,100)
    # All 128 corners and center separately check actual model equations;
    # the universal guarantee itself comes from independently checked inequalities.
    axes = [bounds(m["parameters"][key]) for key in k.PARAMETERS]
    cases = list(product(*axes)) + [tuple((a+b)/2 for a,b in axes)]
    with localcontext() as ctx:
        ctx.prec = 90
        for case in cases:
            expected = oracle(dict(zip(k.PARAMETERS, case)))
            for actual, interval in zip(expected, [e["split_fraction"], e["total_flow_m3_s"], *e["branch_flows_m3_s"].values()]):
                inside(actual, interval)


def test_zero_common_resistance_coarse_but_valid_enclosure():
    proof = certified(model(P1=1,P2=9,A1=0,A2=0,B1=1,B2=1), max_refinements=0, sqrt_bits=0)
    assert bounds(proof["enclosures"]["split_fraction"]) == (0,1)
    assert proof["accuracy"]["target_split_width_met"] is False
    inside(4, proof["enclosures"]["total_flow_m3_s"])
    inside(1, proof["enclosures"]["branch_flows_m3_s"]["sink-one"])
    inside(3, proof["enclosures"]["branch_flows_m3_s"]["sink-two"])
    assert proof["correlation"]["conservation"] == "Q=q1+q2"
    assert proof["correlation"]["marginal_intervals_are_independent"] is False


@pytest.mark.parametrize("overrides", [dict(P1=1,P2=1,A1=5,A2=0,B1=1,B2=1),
    dict(P1=1,P2=1,A1=0,A2=5,B1=1,B2=1), dict(P1=(1,100),P2=1,A1=1,A2=1,B1=1,B2=1),
    dict(P1=1,P2=1,A1=1,A2=0,B1=1,B2=1)])
def test_missing_uniform_forward_regime_is_unknown_not_infeasible(overrides):
    result = k.compile_two_sink_pressure(model(**overrides))
    assert result["status"] == "UNKNOWN"
    assert result["reason"] == "FORWARD_REGIME_NOT_UNIFORMLY_ESTABLISHED"
    assert result["infeasibility_claim"] is False
    assert "certificate" not in result


@pytest.mark.parametrize("key", ["P1","P2","beta","B1","B2"])
@pytest.mark.parametrize("bad", [0,-1,(0,2)])
def test_zero_or_negative_required_positive_parameter_rejected(key,bad):
    assert k.compile_two_sink_pressure(model(**{key:bad}))["status"] == "INVALID_INPUT"


@pytest.mark.parametrize("key", ["A1","A2"])
def test_negative_common_loss_rejected(key):
    assert k.compile_two_sink_pressure(model(**{key:-1}))["status"] == "INVALID_INPUT"


@pytest.mark.parametrize("bad", [float("nan"),float("inf"),1.0,True,"NaN","1e90000000","1/0","--1"])
def test_malformed_rational_input_fails_closed(bad):
    m=model()
    m["parameters"]["P1"]["lower"] = bad
    assert k.compile_two_sink_pressure(m)["status"] == "INVALID_INPUT"


@pytest.mark.parametrize("change", [lambda m:m.pop("physical_model_root"), lambda m:m.pop("assumptions"),
    lambda m:m["assumptions"].pop("regime"), lambda m:m["assumptions"].update(parameter_domain="CORRELATED_UNKNOWN"),
    lambda m:m.update(branch_ids=["x","x"]), lambda m:m.update(branch_ids=["x"]),
    lambda m:m["parameters"].pop("B2"), lambda m:m["parameters"]["P1"].update(lower="100"),
    lambda m:m.update(context_root="not-a-root")])
def test_missing_model_premises(change):
    m=model(); change(m)
    assert k.compile_two_sink_pressure(m)["status"] == "INVALID_INPUT"


def mutate_path(value, path, replacement):
    for key in path[:-1]: value=value[key]
    value[path[-1]]=replacement


@pytest.mark.parametrize("path,replacement", [
    (("model_root",),"c"*64), (("query_root",),"c"*64), (("branch_ids",),["sink-two","sink-one"]),
    (("scope",),"ALL_PHYSICAL_NETWORKS"), (("physical_acceptance_authority",),True),
    (("regime_proof","g_at_zero","upper"),"-1"), (("regime_proof","strict_derivative_lower_bound"),"999"),
    (("enclosures","split_fraction"),{"lower":"0","upper":"1/4"}),
    (("enclosures","split_fraction"),{"lower":"1/2","upper":"3/4"}),
    (("enclosures","total_flow_squared_m6_s2"),{"lower":"0","upper":"8"}),
    (("enclosures","total_flow_squared_m6_s2"),{"lower":"10","upper":"11"}),
    (("enclosures","total_flow_m3_s"),{"lower":"0","upper":"2"}),
    (("enclosures","total_flow_m3_s"),{"lower":"4","upper":"5"}),
    (("enclosures","total_flow_m3_s","lower"),"-1"),
    (("enclosures","branch_flows_m3_s","sink-one"),{"lower":"0","upper":"1/2"}),
    (("enclosures","branch_flows_m3_s","sink-two"),{"lower":"3","upper":"4"}),
    (("accuracy","achieved_split_width"),"0"), (("accuracy","target_split_width_met"),False),
    (("correlation","conservation"),"Q=q1-q2"), (("correlation","marginal_intervals_are_independent"),True),
])
def test_forged_certificate_rejected(path,replacement):
    m=model(); proof=certified(m); mutate_path(proof,path,replacement)
    check=k.verify_two_sink_pressure(m,proof)
    assert check["status"] == "FAIL", check


def test_cross_model_and_query_replay_rejected():
    m=model(); proof=certified(m)
    other=deepcopy(m); other["parameters"]["beta"]={"lower":"2","upper":"2"}
    assert k.verify_two_sink_pressure(other,proof)["status"] == "FAIL"
    assert k.verify_two_sink_pressure(m,proof,target_split_width="1/1000")["status"] == "FAIL"


def test_checker_does_not_invoke_producer_search_bounds_or_sqrt(monkeypatch):
    m=model(); proof=certified(m)
    def forbidden(*args,**kwargs): raise AssertionError("Producer helper used by independent checker")
    for name in ("compile_two_sink_pressure","_g_extrema","_producer_squared_flow","_sqrt_bounds"):
        monkeypatch.setattr(k,name,forbidden)
    assert k.verify_two_sink_pressure(m,proof)["status"] == "PASS"


def test_wider_valid_enclosure_accepted_only_with_correct_accuracy():
    m=model(); proof=certified(m)
    proof["enclosures"].update(split_fraction={"lower":"0","upper":"1"},
        total_flow_squared_m6_s2={"lower":"0","upper":"100"}, total_flow_m3_s={"lower":"0","upper":"10"},
        branch_flows_m3_s={key:{"lower":"0","upper":"10"} for key in m["branch_ids"]})
    assert k.verify_two_sink_pressure(m,proof)["status"] == "FAIL"
    proof["accuracy"].update(achieved_split_width="1",target_split_width_met=False,total_flow_width_m3_s="10",
        branch_flow_widths_m3_s={key:"10" for key in m["branch_ids"]})
    assert k.verify_two_sink_pressure(m,proof)["status"] == "PASS"


@pytest.mark.parametrize("kwargs,reason", [({"max_work":10},"WORK_BUDGET"),({"max_input_bytes":256},"ENCODING_BYTE_BUDGET"),
    ({"max_certificate_bytes":256},"ENCODING_BYTE_BUDGET"),({"max_rational_bits":32},"RATIONAL_BIT_BUDGET")])
def test_hard_budgets_return_unknown_without_certificate(kwargs,reason):
    result=k.compile_two_sink_pressure(model(),**kwargs)
    assert result["status"] == "UNKNOWN",result
    assert result["reason"] == reason
    assert "certificate" not in result


@pytest.mark.parametrize("kwargs", [{"max_work":0},{"max_work":True},{"max_refinements":513},
    {"sqrt_bits":-1},{"max_rational_bits":31},{"max_certificate_bytes":99999999}])
def test_invalid_budget_configuration(kwargs):
    assert k.compile_two_sink_pressure(model(),**kwargs)["status"] == "INVALID_INPUT"


def test_certificate_byte_budget_precedes_certificate_fraction_decoding(monkeypatch):
    m=model(); proof=certified(m)
    proof["enclosures"]["total_flow_m3_s"]["lower"]="2"*3000
    original=k._fraction
    def inspect(value,budget):
        assert value != "2"*3000, "Oversized certificate rational decoded before byte bound"
        return original(value,budget)
    monkeypatch.setattr(k,"_fraction",inspect)
    check=k.verify_two_sink_pressure(m,proof,max_certificate_bytes=2048)
    assert check["status"] == "UNKNOWN"
    assert check["reason"] == "ENCODING_BYTE_BUDGET"


@pytest.mark.parametrize("error", [TimeoutError("caller deadline"),ValueError("caller cancellation"),KeyboardInterrupt()])
@pytest.mark.parametrize("stage", ["pressure_model","pressure_refine_extreme_root","pressure_hash_complete","pressure_producer_complete"])
def test_producer_callback_exception_identity(error,stage):
    m=model(); before=deepcopy(m)
    def checkpoint(name):
        if name==stage: raise error
    with pytest.raises(type(error)) as caught:
        k.compile_two_sink_pressure(m,checkpoint=checkpoint)
    assert caught.value is error
    assert m == before


@pytest.mark.parametrize("error", [TimeoutError("caller deadline"),ValueError("caller cancellation"),KeyboardInterrupt()])
def test_verifier_final_callback_exception_identity(error):
    m=model(); proof=certified(m); before=deepcopy(proof)
    def checkpoint(name):
        if name=="pressure_verifier_complete": raise error
    with pytest.raises(type(error)) as caught:
        k.verify_two_sink_pressure(m,proof,checkpoint=checkpoint)
    assert caught.value is error
    assert proof == before


@pytest.mark.parametrize("mode",["producer","verifier"])
def test_input_model_change_at_final_checkpoint_rejected(mode):
    m=model(); proof=certified(m)
    def checkpoint(name):
        if name==f"pressure_{mode}_complete": m["context_root"]="c"*64
    result=(k.compile_two_sink_pressure(m,checkpoint=checkpoint) if mode=="producer"
        else k.verify_two_sink_pressure(m,proof,checkpoint=checkpoint))
    assert result["status"] in {"FAIL","INVALID_INPUT"},result


def test_verifier_retains_exact_checked_snapshot_when_caller_changes_proof_late():
    m=model(); proof=certified(m); original=deepcopy(proof)
    def checkpoint(name):
        if name=="pressure_verifier_complete": proof["enclosures"]["total_flow_m3_s"]["upper"]="999"
    result=k.verify_two_sink_pressure(m,proof,checkpoint=checkpoint)
    assert result["status"] == "PASS"
    assert result["enclosures"] == original["enclosures"]
    assert result["certificate_root"] == k.verify_two_sink_pressure(m,original)["certificate_root"]


@pytest.mark.parametrize("mode", ["producer", "verifier"])
def test_no_mutating_callback_after_final_model_binding_begins(mode):
    m=model(); proof=certified(m); final_seen=False; late_calls=[]
    def checkpoint(name):
        nonlocal final_seen
        if final_seen:
            late_calls.append(name)
            m["parameters"]["P1"]["upper"]="1000000"
        if name==f"pressure_{mode}_complete": final_seen=True
    result=(k.compile_two_sink_pressure(m,checkpoint=checkpoint) if mode=="producer"
        else k.verify_two_sink_pressure(m,proof,checkpoint=checkpoint))
    assert result["status"] in {"CERTIFIED", "PASS"}
    assert not late_calls
    assert m["parameters"]["P1"]["upper"] == "23"
    assert k.compile_two_sink_pressure(m)["status"] == "CERTIFIED"


def test_root_arbitrarily_near_boundary_remains_valid_with_coarse_width():
    # All actual roots are strictly interior even though the finite enclosure
    # starts at zero. No positive marginal lower delivery is fabricated.
    epsilon=F(1,2**100)
    proof=certified(model(P1=epsilon*epsilon,P2=(1-epsilon)**2,A1=0,A2=0,B1=1,B2=1),
        max_refinements=4,sqrt_bits=8)
    assert bounds(proof["enclosures"]["split_fraction"])[0] == 0
    inside(epsilon,proof["enclosures"]["split_fraction"])
    assert bounds(proof["enclosures"]["branch_flows_m3_s"]["sink-one"])[0] == 0


def test_missing_branch_output_and_unknown_fields_rejected():
    m=model(); original=certified(m)
    omitted=deepcopy(original)
    omitted["enclosures"]["branch_flows_m3_s"].pop("sink-two")
    assert k.verify_two_sink_pressure(m,omitted)["status"] == "FAIL"
    extra=deepcopy(original); extra["unchecked_physical_pass"]=True
    assert k.verify_two_sink_pressure(m,extra)["status"] == "FAIL"


def test_verifier_work_and_bit_exhaustion_remain_unknown():
    m=model(); proof=certified(m)
    assert k.verify_two_sink_pressure(m,proof,max_work=10)["status"] == "UNKNOWN"
    assert k.verify_two_sink_pressure(m,proof,max_rational_bits=32)["status"] == "UNKNOWN"
