"""Independent finite graph oracle and proof/control attacks; no native claim."""
import copy
import builtins
from fractions import Fraction as Q
import hashlib
import importlib.util
import itertools
import json
import os
from pathlib import Path
import random

import pytest

if os.environ.get("OMA_SHARED_TREE_SOURCE"):
    spec = importlib.util.spec_from_file_location("shared_tree_under_test", os.environ["OMA_SHARED_TREE_SOURCE"])
    s = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(s)
else:
    try:
        from oma.optimization import shared_tree_synthesis as s
    except ImportError:
        spec = importlib.util.spec_from_file_location("shared_tree_under_test", Path(__file__).parents[1]/"src/oma/optimization/shared_tree_synthesis.py")
        s = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(s)

ROOT = "1"*64


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def reseal(certificate):
    certificate["certificate_root"] = digest({k:v for k,v in certificate.items() if k != "certificate_root"})
    return certificate


def make_catalogue(sinks=2, tees=2):
    section = {"diameter_m":"1/8", "insulation_m":"1/32"}
    cap = lambda point, axis: {"position_m":list(map(str, point)), "flow_direction":list(axis)}
    result = {"schema":s.MODEL_SCHEMA, "context_root":ROOT, "source_roots":{"source_ifc":ROOT},
              "cost_policy_root":ROOT, "section":section,
              "source":{"id":"source", "cap":cap([-2,0,3], [1,0,0])},
              "sinks":[{"id":f"sink-{i}", "demand_id":f"demand-{i}", "cap":cap([i+1,3,3], [0,1,0])} for i in range(sinks)],
              "tee_instances":[], "connectors":[]}
    caps = {("source","out"):result["source"]["cap"]}
    for sink in result["sinks"]:
        caps[sink["id"],"in"] = sink["cap"]
    for i in range(tees):
        tee = {"id":f"tee-{i}", "catalogue_root":ROOT, "loss_contract_root":ROOT,
               "center_m":[str(2*i),"0","3"], "axis_x":[1,0,0], "axis_y":[0,1,0],
               "trunk_takeout_m":"1/4", "branch_takeout_m":"1/4", "nominal_cost":["1","0"]}
        result["tee_instances"].append(tee)
        caps[tee["id"],"a"] = cap([Q(2*i)-Q(1,4),0,3], [1,0,0])
        caps[tee["id"],"b"] = cap([Q(2*i)+Q(1,4),0,3], [1,0,0])
        caps[tee["id"],"branch"] = cap([2*i,Q(1,4),3], [0,1,0])
    pairs = []
    for tee in result["tee_instances"]:
        pairs.append((("source","out"),(tee["id"],"a")))
        for port in ("b","branch"):
            pairs.extend(((tee["id"],port),(sink["id"],"in")) for sink in result["sinks"])
            if sinks == 3:
                pairs.extend(((tee["id"],port),(other["id"],"a")) for other in result["tee_instances"] if other != tee)
    for i,(start,end) in enumerate(pairs):
        result["connectors"].append({"id":f"connector-{i:03d}",
            "from":{"node":start[0],"port":start[1]}, "to":{"node":end[0],"port":end[1]},
            "start_cap":copy.deepcopy(caps[start]), "end_cap":copy.deepcopy(caps[end]),
            "section":copy.deepcopy(section), "geometry_root":ROOT,"fabrication_root":ROOT,
            "nominal_cost":[str(1+i%4), str(i%3)]})
    return result


def oracle(problem):
    """Independent choose-edges oracle, not either module enumeration routine."""
    sinks = {x["id"] for x in problem["sinks"]}
    tees = {x["id"]:x for x in problem["tee_instances"]}
    source = problem["source"]["id"]
    answer = {}
    for chosen in itertools.combinations(problem["connectors"], 2*len(sinks)-1):
        incoming, outgoing = {}, {}
        for edge in chosen:
            incoming.setdefault(edge["to"]["node"],[]).append(edge)
            outgoing.setdefault(edge["from"]["node"],[]).append(edge)
        if len(outgoing.get(source,[])) != 1 or incoming.get(source): continue
        if any(len(incoming.get(x,[])) != 1 or outgoing.get(x) for x in sinks):continue
        active = {x for x in tees if incoming.get(x) or outgoing.get(x)}
        if len(active) != len(sinks)-1:continue
        if any(len(incoming.get(x,[])) != 1 or incoming[x][0]["to"]["port"] != "a"
               or len(outgoing.get(x,[])) != 2
               or {e["from"]["port"] for e in outgoing[x]} != {"b","branch"} for x in active):continue
        seen, stack = set(), [source]
        while stack:
            node = stack.pop()
            if node in seen:break
            seen.add(node)
            stack.extend(e["to"]["node"] for e in outgoing.get(node,[]))
        else:
            if seen != {source}|sinks|active:continue
            ids = tuple(sorted(e["id"] for e in chosen))
            entries = [tees[x] for x in active]+list(chosen)
            cost = tuple(sum((Q(e["nominal_cost"][i]) for e in entries),Q()) for i in range(2))
            answer[ids] = (tuple(sorted(active)),tuple(map(str,cost)))
    return answer


def check(problem, **kw):
    produced = s.compile_shared_tree_catalogue(problem, **kw)
    assert produced["status"] == "CERTIFIED", produced
    verified = s.verify_shared_tree_catalogue(problem, produced["certificate"], **kw)
    assert verified["status"] == "PASS", verified
    assert produced["proposals"] == verified["proposals"]
    return produced, verified


@pytest.mark.parametrize("sinks,tees", [(2,1),(2,2),(2,3),(3,1),(3,2)])
def test_complete_graph_oracle(sinks,tees):
    p = make_catalogue(sinks,tees)
    result,_ = check(p)
    rows = result["certificate"]["assignments"]
    assert {tuple(r["connector_ids"]):(tuple(r["tee_ids"]),tuple(r["nominal_cost"])) for r in rows} == oracle(p)
    assert len(rows) == (2*tees if sinks == 2 else 12*tees*(tees-1))
    for proposal in result["proposals"]:
        assert len(proposal["connections"]) == 2*sinks-1
        assert len(proposal["sinks"]) == sinks
        assert {x["id"] for x in proposal["sinks"]} == {x["id"] for x in p["sinks"]}


@pytest.mark.parametrize("seed", range(12))
def test_random_sparse_oracle(seed):
    p = make_catalogue(3,2)
    rng = random.Random(seed)
    p["connectors"] = [e for e in p["connectors"] if rng.random() > .3]
    for e in p["connectors"]:
        e["nominal_cost"] = [str(Q(rng.randrange(6),rng.randrange(1,8))),"0"]
    result,_ = check(p,max_results=1)
    reference = oracle(p)
    assert {tuple(r["connector_ids"]):(tuple(r["tee_ids"]),tuple(r["nominal_cost"])) for r in result["certificate"]["assignments"]} == reference
    if reference:
        best = min(reference,key=lambda k:(Q(reference[k][1][0]),k))
        assert tuple(result["proposals"][0]["connector_ids"]) == best


def test_multiple_connector_options_unique_component_cost():
    p = make_catalogue(3,2)
    extra = copy.deepcopy(p["connectors"][0]);extra["id"]="extra-source";extra["nominal_cost"]=["0","0"]
    p["connectors"].append(extra)
    result,_ = check(p,max_results=1)
    assert result["counts"]["complete_assignments"] == 36
    assert len(result["certificate"]["assignments"]) == 36
    row = result["proposals"][0]
    all_edges={x["id"]:x for x in p["connectors"]}
    assert sum(row["connector_ids"].count(x) for x in row["connector_ids"]) == 5
    assert any(sum(e in q["connector_path"] for q in row["sinks"]) == 3 for e in all_edges if e in row["connector_ids"])


def test_empty_finite_catalogue_is_only_discrete_absence():
    p=make_catalogue();p["connectors"]=[]
    r,v=check(p)
    assert r["proposals"] == [] and v["counts"]["complete_assignments"] == 0
    assert "No physical infeasibility" in r["certificate"]["limitations"][-1]


def test_all_24_proper_axis_frames():
    for x in itertools.product((-1,0,1),repeat=3):
        if sum(map(abs,x)) != 1:continue
        for y in itertools.product((-1,0,1),repeat=3):
            if sum(map(abs,y)) != 1 or sum(a*b for a,b in zip(x,y)):continue
            p=make_catalogue(2,1);t=p["tee_instances"][0];t["axis_x"]=list(x);t["axis_y"]=list(y)
            caps={}
            for port,axis,offset in [("a",x,-Q(1,4)),("b",x,Q(1,4)),("branch",y,Q(1,4))]:
                caps[port]={"position_m":[str(Q(c)+offset*d) for c,d in zip(t["center_m"],axis)],"flow_direction":list(axis)}
            for edge in p["connectors"]:
                if edge["from"]["node"] == t["id"]:edge["start_cap"]=caps[edge["from"]["port"]]
                if edge["to"]["node"] == t["id"]:edge["end_cap"]=caps[edge["to"]["port"]]
            check(p)


@pytest.mark.parametrize("attack", ["missing","duplicate","wrong_cost","wrong_tee","wrong_connector","wrong_assignment_root",
                                    "prefix_reverse","prefix_missing","prefix_duplicate","scope","count_bool","max_bool",
                                    "input_root","problem_root","limit","extra_row_field"])
def test_resealed_certificate_attacks(attack):
    p=make_catalogue();r,_=check(p);c=copy.deepcopy(r["certificate"])
    if attack=="missing":c["assignments"].pop();c["assignment_count"]-=1
    elif attack=="duplicate":c["assignments"].append(copy.deepcopy(c["assignments"][0]));c["assignment_count"]+=1
    elif attack=="wrong_cost":c["assignments"][0]["nominal_cost"][0]="0"
    elif attack=="wrong_tee":c["assignments"][0]["tee_ids"][0]="tee-other"
    elif attack=="wrong_connector":c["assignments"][0]["connector_ids"][0]="missing"
    elif attack=="wrong_assignment_root":c["assignments"][0]["assignment_root"]="2"*64
    elif attack=="prefix_reverse":c["ranked_prefix"].reverse()
    elif attack=="prefix_missing":c["ranked_prefix"].pop()
    elif attack=="prefix_duplicate":c["ranked_prefix"][1]=c["ranked_prefix"][0]
    elif attack=="scope":c["scope"]="PHYSICALLY_OPTIMAL"
    elif attack=="count_bool":c["assignment_count"]=True
    elif attack=="max_bool":c["max_results"]=True
    elif attack=="input_root":c["input_root"]="2"*64
    elif attack=="problem_root":c["problem_root"]="2"*64
    elif attack=="limit":c["max_results"]=1;c["ranked_prefix"]=c["ranked_prefix"][:1]
    elif attack=="extra_row_field":c["assignments"][0]["native_pass"]=True
    assert s.verify_shared_tree_catalogue(p,reseal(c))["status"] == "FAIL"


@pytest.mark.parametrize("attack", ["position","direction","section","duplicate_connector","duplicate_tee","duplicate_sink","duplicate_demand",
                                    "axis_bool","axis_nonorthogonal","zero_diameter","negative_cost","nan_cost","float_position",
                                    "takeout","bad_root","wrong_port","self_connector","unknown_endpoint","unknown_field"])
def test_input_schema_and_cap_attacks(attack):
    p=make_catalogue()
    if attack=="position":p["connectors"][0]["end_cap"]["position_m"][0]="0"
    elif attack=="direction":p["connectors"][0]["end_cap"]["flow_direction"]=[-1,0,0]
    elif attack=="section":p["connectors"][0]["section"]["diameter_m"]="1/4"
    elif attack=="duplicate_connector":p["connectors"].append(copy.deepcopy(p["connectors"][0]))
    elif attack=="duplicate_tee":p["tee_instances"][1]["id"]=p["tee_instances"][0]["id"]
    elif attack=="duplicate_sink":p["sinks"][1]["id"]=p["sinks"][0]["id"]
    elif attack=="duplicate_demand":p["sinks"][1]["demand_id"]=p["sinks"][0]["demand_id"]
    elif attack=="axis_bool":p["tee_instances"][0]["axis_x"]=[True,0,0]
    elif attack=="axis_nonorthogonal":p["tee_instances"][0]["axis_y"]=[1,0,0]
    elif attack=="zero_diameter":p["section"]["diameter_m"]="0"
    elif attack=="negative_cost":p["connectors"][0]["nominal_cost"]=["-1","0"]
    elif attack=="nan_cost":p["connectors"][0]["nominal_cost"]=[float('nan'),"0"]
    elif attack=="float_position":p["source"]["cap"]["position_m"][0]=2.0
    elif attack=="takeout":p["tee_instances"][0]["trunk_takeout_m"]="1/16"
    elif attack=="bad_root":p["source_roots"]["source_ifc"]="not-a-root"
    elif attack=="wrong_port":p["connectors"][0]["to"]["port"]="branch"
    elif attack=="self_connector":p["connectors"][0]["from"]={"node":"tee-0","port":"b"}
    elif attack=="unknown_endpoint":p["connectors"][0]["to"]["node"]="absent"
    elif attack=="unknown_field":p["native_pass"]=True
    assert s.compile_shared_tree_catalogue(p)["status"] == "INVALID_INPUT"


def pi_competition():
    p=make_catalogue(2,1)
    p["tee_instances"][0]["nominal_cost"]=["0","0"]
    for edge in p["connectors"]:edge["nominal_cost"]=["0","0"]
    for edge in p["connectors"]:
        if edge["from"]=={"node":"tee-0","port":"b"}:
            edge["nominal_cost"]=["3141592653589793/1000000000000000","0"] if edge["to"]["node"]=="sink-0" else ["0","1"]
    return p


def test_certified_pi_comparison_and_precision_unknown():
    p=pi_competition();r,_=check(p)
    assert r["proposals"][0]["nominal_cost"] == ["3141592653589793/1000000000000000","0"]
    assert s.compile_shared_tree_catalogue(p,max_pi_terms=1)["status"]=="UNKNOWN"
    assert s.verify_shared_tree_catalogue(p,r["certificate"],max_pi_terms=1)["status"]=="UNKNOWN"


def test_exact_zero_cost_ties_are_canonical():
    p=make_catalogue(3,2)
    for item in p["tee_instances"]+p["connectors"]:item["nominal_cost"]=["0","0"]
    r,_=check(p,max_results=2)
    assert r["certificate"]["ranked_prefix"] == [a["assignment_root"] for a in r["certificate"]["assignments"][:2]]


@pytest.mark.parametrize("kwargs", [{"max_work":1},{"max_bytes":256},{"max_assignments":1},{"max_connectors":1},{"max_tee_instances":1}])
def test_supported_budget_exhaustions(kwargs):
    p=make_catalogue();r,_=check(p)
    assert s.compile_shared_tree_catalogue(p,**kwargs)["status"]=="UNKNOWN"
    assert s.verify_shared_tree_catalogue(p,r["certificate"],**kwargs)["status"]=="UNKNOWN"


def test_rational_budget_before_fraction_conversion():
    p=make_catalogue();p["connectors"][0]["nominal_cost"][0]="1"+"0"*100
    assert s.compile_shared_tree_catalogue(p,max_rational_bits=32)["status"]=="UNKNOWN"


@pytest.mark.parametrize("name,value", [("max_results",True),("max_assignments",0),("max_pi_terms",0),("max_bytes",255)])
def test_invalid_budgets(name,value):
    assert s.compile_shared_tree_catalogue(make_catalogue(),**{name:value})["status"]=="INVALID_INPUT"


@pytest.mark.parametrize("mode", ["producer","verifier"])
@pytest.mark.parametrize("error_type", [ValueError,TimeoutError,s._Exhausted])
def test_caller_exception_identity(mode,error_type):
    p=make_catalogue();r,_=check(p);marker=error_type("caller identity")
    def callback(stage):
        if stage==f"shared_tree_{mode}_complete":raise marker
    with pytest.raises(error_type) as caught:
        if mode=="producer":s.compile_shared_tree_catalogue(p,checkpoint=callback)
        else:s.verify_shared_tree_catalogue(p,r["certificate"],checkpoint=callback)
    assert caught.value is marker


@pytest.mark.parametrize("mode,target", [("producer","input"),("verifier","input"),("verifier","certificate")])
def test_final_callback_mutation_guard(mode,target):
    p=make_catalogue();r,_=check(p);c=r["certificate"];final=[False]
    def callback(stage):
        assert not final[0], "callback after final guard"
        if stage==f"shared_tree_{mode}_complete":
            final[0]=True
            if target=="input":p["cost_policy_root"]="2"*64
            else:c["ranked_prefix"].reverse()
    result=s.compile_shared_tree_catalogue(p,checkpoint=callback) if mode=="producer" else s.verify_shared_tree_catalogue(p,c,checkpoint=callback)
    assert result["status"] not in {"CERTIFIED","PASS"}
    assert result["proposals"]==[] and final[0]


def test_mutated_shape_rechecked_after_callback():
    p=make_catalogue(2,1)
    def callback(stage):
        if stage=="shared_tree_input":p["tee_instances"].append(copy.deepcopy(p["tee_instances"][0]))
    r=s.compile_shared_tree_catalogue(p,max_tee_instances=1,checkpoint=callback)
    assert r["status"]=="UNKNOWN" and r["reason"]=="TEE_BUDGET"


def test_verifier_does_not_use_producer_enumeration_or_pi(monkeypatch):
    p=pi_competition();r,_=check(p)
    def forbidden(*args,**kw):raise AssertionError("producer invoked by verifier")
    monkeypatch.setattr(s,"_producer_assignments",forbidden)
    monkeypatch.setattr(s,"_pi_producer",forbidden)
    monkeypatch.setattr(s,"compile_shared_tree_catalogue",forbidden)
    assert s.verify_shared_tree_catalogue(p,r["certificate"])["status"]=="PASS"


def test_complete_work_budget_includes_final_tail():
    p=make_catalogue();r,v=check(p)
    assert s.compile_shared_tree_catalogue(p,max_work=r["work"])["status"]=="CERTIFIED"
    assert s.compile_shared_tree_catalogue(p,max_work=r["work"]-1)["status"]=="UNKNOWN"
    assert s.verify_shared_tree_catalogue(p,r["certificate"],max_work=v["work"])["status"]=="PASS"
    assert s.verify_shared_tree_catalogue(p,r["certificate"],max_work=v["work"]-1)["status"]=="UNKNOWN"


def test_certificate_byte_limit_includes_digest_field():
    p=make_catalogue(3,3);r,_=check(p)
    encode=lambda x:json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    size=len(encode(r["certificate"]))
    assert size>len(encode(p))
    assert s.compile_shared_tree_catalogue(p,max_bytes=size)["status"]=="CERTIFIED"
    assert s.verify_shared_tree_catalogue(p,r["certificate"],max_bytes=size)["status"]=="PASS"
    assert s.compile_shared_tree_catalogue(p,max_bytes=size-1)["status"]=="UNKNOWN"
    assert s.verify_shared_tree_catalogue(p,r["certificate"],max_bytes=size-1)["status"]=="UNKNOWN"


def test_supplied_certificate_budget_checked_before_row_cost_parsing(monkeypatch):
    p=make_catalogue();r,_=check(p);c=r["certificate"]
    c["assignments"]=[{"nominal_cost":["9"*4000,"0"]} for _ in range(1000)]
    def forbidden(*args,**kw):raise AssertionError("parsed model before bounded proof copy")
    monkeypatch.setattr(s,"_normalize",forbidden)
    result=s.verify_shared_tree_catalogue(p,c,max_bytes=100000)
    assert result["status"]=="UNKNOWN" and result["reason"]=="BYTE_BUDGET"


def test_supplied_certificate_shape_rechecked_after_first_callback():
    small=make_catalogue(2,1)
    # One of the two labelled sink assignments lacks a required connector.
    small["connectors"]=[x for x in small["connectors"] if not (x["from"]=={"node":"tee-0","port":"b"} and x["to"]["node"]=="sink-1")]
    r,_=check(small,max_assignments=1)
    large=make_catalogue(2,1);big,_=check(large)
    c=r["certificate"]
    def callback(stage):
        if stage=="shared_tree_input":
            small.clear();small.update(copy.deepcopy(large));c.clear();c.update(copy.deepcopy(big["certificate"]))
    result=s.verify_shared_tree_catalogue(small,c,max_assignments=1,checkpoint=callback)
    assert result["status"]=="UNKNOWN" and result["reason"]=="CERTIFICATE_ASSIGNMENT_BUDGET"


def test_oversized_top_level_dict_rejected_before_key_set_allocation(monkeypatch):
    p=make_catalogue();p.update({f"extra-{i}":None for i in range(1000)})
    def guarded(value=()):
        if value is p:raise AssertionError("unbounded caller key-set allocation")
        return builtins.set(value)
    monkeypatch.setattr(s,"set",guarded,raising=False)
    assert s.compile_shared_tree_catalogue(p,max_work=1,max_bytes=256)["status"]=="INVALID_INPUT"


@pytest.mark.parametrize("sinks", [2,3])
def test_independent_native_catalogue_correspondence(sinks):
    directory=Path(__file__).parent/"fixtures/shared-tree-synthesis"
    p=json.loads((directory/f"catalogue-{sinks}.json").read_text(encoding="utf-8"))
    expected=json.loads((directory/f"oracle-{sinks}.json").read_text(encoding="utf-8"))
    r,v=check(p)
    assert len(r["certificate"]["assignments"])==len(expected)
    for got,want in zip(v["proposals"],expected):
        assert got["tee_ids"]==want["tee_ids"]
        assert got["connector_ids"]==want["connector_ids"]
        assert got["nominal_cost"]==want["nominal_cost"]
        assert {x["id"]:x["connector_path"] for x in got["sinks"]}==want["sink_connector_paths"]
