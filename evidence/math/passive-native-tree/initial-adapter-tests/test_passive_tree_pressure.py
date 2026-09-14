from copy import deepcopy
from decimal import Decimal
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path

import pytest

from oma.routing import passive_tree_pressure as p
from oma.routing.passive_tree_scenario import PassiveTreeBoundary
from oma.routing.network_scenario import NetworkDesign
from oma.store import digest

FIXTURES = Path(__file__).parent / "fixtures/passive-native-tree"
HASHES = {
    "specification.json":"657d8865c86d9a0258fb705107f628ccb83d67e7a41034e51acd38f12ac4447c",
    "new-boundary-declaration.json":"a3d8ce70429b9f3f9ae96a10ca644a21662ddc22a6a23352e363def12fc7a0da",
    "native-metrics.json":"4080ad910d2ba165114209957a9e51a2cb97f7bed5c29f411bfdad3b4359fb18",
    "independent-nominal-reference.json":"9ef794838de481c33d2f59f411265083b95beb1e7024f9e1ea4deef90a465a9b",
}


def fixture(name):
    raw=(FIXTURES/name).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==HASHES[name]
    return json.loads(raw.decode("utf-8"))


def inputs():
    b,n,m=(fixture(x) for x in ("new-boundary-declaration.json","specification.json","native-metrics.json"))
    return b,n,m


CONTEXT={"native_artifact_root":"a"*64,"source_bytes_root":"b"*64}


def evaluate(b,n,m,**kw):
    return p.evaluate_passive_tree(b,n,m,context=CONTEXT,**kw)


def verify(b,n,m,packet,**kw):
    return p.verify_passive_tree_envelope(b,n,m,packet,context=CONTEXT,**kw)


def enclosed(value, interval):
    return Q(interval["lower"]) <= Q(value) <= Q(interval["upper"])


def rebind(n,m):
    n=NetworkDesign.model_validate(n).model_dump(mode="json",by_alias=True)
    m["network_root"]=digest(n)
    return n


@pytest.fixture(scope="module")
def original():
    b,n,m=inputs();result=evaluate(b,n,m)
    assert result["status"]=="CERTIFIED_ENVELOPE",result
    assert result["verdict"]=="PASS",result
    return b,n,m,result


def test_actual_native_fixture_and_independent_closed_form(original):
    b,n,m,result=original
    checked=result["independent_check"]
    assert checked["status"]=="PASS"
    assert checked["counts"]=={"components":7,"physical_ports":16,"connections":6,"tees":2,"graph_nodes":8,"boundaries":4}
    service=checked["service"]
    assert service["counts"]=={"physical_ports":16,"deliveries":3,"conservation_identities":17}
    ref=fixture("independent-nominal-reference.json")
    for row in service["physical_ports"]:
        assert enclosed(ref["physical_port_forward_flows_m3_s"][row["component"]][row["port"]],row["flow_m3_s"])
        assert row["forward_status"]==row["maximum_velocity_status"]=="PASS"
    assert verify(b,n,m,result["certificate"])["status"]=="PASS"
    assert not checked["native_geometry_acceptance_authority"]


def test_contract_rejects_old_unequal_tee_interpretation():
    b,_,_=inputs();b["tee_loss_reference"]="INLET_VELOCITY_TOTAL_IRREVERSIBLE_LOSS"
    with pytest.raises(ValueError):PassiveTreeBoundary.model_validate(b)
    b,_,_=inputs();b["tee_branch_loss_coefficient"]="1/3"
    with pytest.raises(ValueError):PassiveTreeBoundary.model_validate(b)


@pytest.mark.parametrize("field,value",[("darcy_friction","0"),("density_kg_m3","0"),
    ("elbow_loss_coefficient","-1"),("gravity_m_s2","-1"),("maximum_velocity_m_s",True),
    ("source_total_pressure_pa",float("nan")),("density_kg_m3","1e3"),("density_kg_m3","9"*1000)])
def test_malformed_contract(field,value):
    b,n,m=inputs();b[field]=value
    assert evaluate(b,n,m)["status"] in {"BLOCKED","UNKNOWN"}


@pytest.mark.parametrize("change",["missing_component","extra_component","missing_port","extra_port","missing_length",
    "zero_length","negative_bore","nan_metric","wrong_network","wrong_schema","missing_tee_k","zero_tee_k","missing_sink","disjoint_caps"])
def test_complete_metric_and_model_inventory(change):
    b,n,m=inputs()
    if change=="missing_component":del m["components"]["arm-a"]
    if change=="extra_component":m["components"]["phantom"]=deepcopy(m["components"]["arm-a"])
    if change=="missing_port":del m["components"]["tee-1"]["ports"]["branch"]
    if change=="extra_port":m["components"]["arm-a"]["ports"]["branch"]=deepcopy(m["components"]["arm-a"]["ports"]["b"])
    if change=="missing_length":del m["components"]["tee-1"]["length_m"]
    if change=="zero_length":m["components"]["tee-1"]["length_m"]={"lower":"0","upper":"1"}
    if change=="negative_bore":m["components"]["arm-a"]["outer_radius_m"]={"lower":"1/1000","upper":"1/1000"}
    if change=="nan_metric":m["components"]["arm-a"]["length_m"]["lower"]=float("nan")
    if change=="wrong_network":m["network_root"]="f"*64
    if change=="wrong_schema":m["schema"]="something_else"
    if change=="missing_tee_k":del b["tee_common_loss_coefficients"]["tee-2"]
    if change=="zero_tee_k":b["tee_common_loss_coefficients"]["tee-2"]="0"
    if change=="missing_sink":del b["minimum_sink_flows_m3_s"]["sink-c"]
    if change=="disjoint_caps":m["components"]["inter-tee"]["ports"]["a"]["position_m"][0]={"lower":"100","upper":"100"}
    result=evaluate(b,n,m)
    assert result["status"] in {"BLOCKED","UNKNOWN"},result
    assert not result["proof_complete"]


def test_native_tee_length_not_darcy_charged(original):
    b,n,m,_=deepcopy(original)
    model,derivation=p.derive_passive_tree_model(b,n,m,context=CONTEXT)
    for cid in ("tee-1","tee-2"):m["components"][cid]["length_m"]={"lower":"1000","upper":"1001"}
    changed,other=p.derive_passive_tree_model(b,n,m,context=CONTEXT)
    assert changed["edges"]==model["edges"]
    assert changed["physical_model_root"]!=model["physical_model_root"]


def test_actual_area_uncertainty_affects_loss_and_velocity(original):
    b,n,m,_=deepcopy(original)
    first=evaluate(b,n,m)
    m["components"]["arm-a"]["outer_radius_m"]={"lower":"699/10000","upper":"701/10000"}
    second=evaluate(b,n,m)
    a=first["certificate"]["derivation"]["component_sections"]["arm-a"]
    d=second["certificate"]["derivation"]["component_sections"]["arm-a"]
    assert Q(d["resistance_pa_s2_m6"]["lower"]) < Q(a["resistance_pa_s2_m6"]["lower"])
    assert Q(d["resistance_pa_s2_m6"]["upper"]) > Q(a["resistance_pa_s2_m6"]["upper"])


@pytest.mark.parametrize("kind",["delivery","velocity","reverse","zero","uncertain_sign"])
def test_model_proof_separate_from_service_requirements(kind):
    b,n,m=inputs()
    if kind=="delivery":b["minimum_sink_flows_m3_s"]["sink-b"]="1"
    if kind=="velocity":b["maximum_velocity_m_s"]="1/10000"
    if kind=="reverse":b["source_total_pressure_pa"]="-100"
    if kind=="zero":b["source_total_pressure_pa"]="0";b["gravity_m_s2"]="0"
    if kind=="uncertain_sign":
        b["source_total_pressure_pa"]="0"
        # All terminal elevation intervals overlap; no uniform sign is established.
    result=evaluate(b,n,m)
    assert result["status"]=="CERTIFIED_ENVELOPE",result
    assert result["verdict"]==("UNKNOWN" if kind=="uncertain_sign" else "FAIL")
    assert result["independent_check"]["status"]=="PASS"


def remove_arm(n,m,cid):
    link=next(x for x in n["connections"] if x["sink"]["component"]==cid)
    endpoint=deepcopy(link["source"])
    n["connections"].remove(link)
    n["components"]=[x for x in n["components"] if x["id"]!=cid]
    for sink in n["sinks"]:
        if sink["endpoint"]["component"]==cid:sink["endpoint"]=endpoint
    for path in n["demand_paths"]:path["steps"]=[x for x in path["steps"] if x["component"]!=cid]
    del m["components"][cid]
    return rebind(n,m)


def test_single_terminal_on_tee_uses_complete_boundary_withdrawal():
    b,n,m=inputs();n=remove_arm(n,m,"arm-a")
    result=evaluate(b,n,m)
    assert result["status"]=="CERTIFIED_ENVELOPE",result
    port=next(x for x in result["certificate"]["service"]["physical_ports"] if (x["component"],x["port"])==("tee-1","branch"))
    assert port["flow_expression"]=={"tee-1":1,"inter-tee":-1}
    assert port["forward_status"]=="PASS"


def test_two_terminal_outlets_sharing_head_never_fabricate_split():
    b,n,m=inputs();n=remove_arm(n,m,"arm-b");n=remove_arm(n,m,"arm-c")
    result=evaluate(b,n,m)
    assert result["status"]=="BLOCKED"
    assert "Multiple physical boundaries" in result["reason"]


def test_sink_named_source_does_not_overwrite_actual_source():
    b,n,m=inputs()
    for sink in n["sinks"]:
        if sink["id"]=="sink-a":sink["id"]="source"
    for path in n["demand_paths"]:
        if path["sink_id"]=="sink-a":path["sink_id"]="source"
    for key in ("sink_total_pressures_pa","minimum_sink_flows_m3_s"):b[key]["source"]=b[key].pop("sink-a")
    n=rebind(n,m);r=evaluate(b,n,m)
    assert r["status"]=="CERTIFIED_ENVELOPE"
    assert set(r["certificate"]["derivation"]["terminal_nodes"])=={"source","sink/source","sink/sink-b","sink/sink-c"}


@pytest.mark.parametrize("target",["model","derivation","service","pressure_certificate","input_root","certificate_root"])
def test_resealed_false_certificate_sections_rejected(original,target):
    b,n,m,r=deepcopy(original);packet=r["certificate"]
    if target=="model":packet[target]["edges"][0]["resistance"]["lower"]="0"
    if target=="derivation":packet[target]["counts"]["physical_ports"]-=1
    if target=="service":packet[target]["physical_ports"][0]["flow_expression"]={"tee-2":1}
    if target=="pressure_certificate":packet[target]["pressure_bounds"][0]["upper"]="999999999"
    if target=="input_root":packet[target]="d"*64
    packet["certificate_root"]=digest({k:v for k,v in packet.items() if k!="certificate_root"}) if target!="certificate_root" else "d"*64
    assert verify(b,n,m,packet)["status"]=="FAIL"


@pytest.mark.parametrize("field",["physical_ports","deliveries","conservation_identities"])
def test_complete_physical_service_denominators(original,field):
    b,n,m,r=deepcopy(original);packet=r["certificate"]
    packet["service"][field].pop()
    packet["certificate_root"]=digest({k:v for k,v in packet.items() if k!="certificate_root"})
    assert verify(b,n,m,packet)["status"]=="FAIL"


def test_verifier_does_not_call_producer(original,monkeypatch):
    b,n,m,r=original
    def forbidden(*a,**k):raise AssertionError("Producer called")
    monkeypatch.setattr(p,"derive_passive_tree_model",forbidden)
    monkeypatch.setattr(p,"evaluate_passive_tree",forbidden)
    monkeypatch.setattr(p.kernel,"compile_passive_pressure",forbidden)
    assert verify(b,n,m,r["certificate"])["status"]=="PASS"


@pytest.mark.parametrize("kwargs",[{"max_components":2},{"max_work":1},{"max_bytes":1024}])
def test_budgets_unknown_no_partial_claim(kwargs):
    r=evaluate(*inputs(),**kwargs)
    assert r["status"]=="UNKNOWN" and not r["proof_complete"]


@pytest.mark.parametrize("stage",["passive_tree_input_shape","passive_tree_quotient_union","passive_tree_producer_complete"])
@pytest.mark.parametrize("exception",[ValueError,TimeoutError,p._BudgetExceeded])
def test_exact_caller_exception_identity(stage,exception):
    exc=exception("caller")
    def stop(s):
        if s==stage:raise exc
    with pytest.raises(exception) as caught:evaluate(*inputs(),checkpoint=stop)
    assert caught.value is exc


@pytest.mark.parametrize("operation",["derive","evaluate","verify"])
def test_final_callback_input_mutation_fails_closed(original,operation):
    b,n,m,r=deepcopy(original)
    final={"derive":"passive_tree_derivation_complete","evaluate":"passive_tree_producer_complete","verify":"passive_tree_verifier_complete"}[operation]
    calls=[]
    def mutate(stage):
        calls.append(stage)
        if stage==final:b["source_total_pressure_pa"]="1000000"
    if operation=="derive":
        with pytest.raises(ValueError):p.derive_passive_tree_model(b,n,m,context=CONTEXT,checkpoint=mutate)
    elif operation=="evaluate":assert evaluate(b,n,m,checkpoint=mutate)["status"]!="CERTIFIED_ENVELOPE"
    else:assert verify(b,n,m,r["certificate"],checkpoint=mutate)["status"]!="PASS"
    assert calls[-1]==final


def test_final_certificate_mutation_fails_closed(original):
    b,n,m,r=deepcopy(original);packet=r["certificate"]
    def mutate(stage):
        if stage=="passive_tree_verifier_complete":packet["service"]["verdict"]="UNKNOWN"
    assert verify(b,n,m,packet,checkpoint=mutate)["status"]=="FAIL"


def test_requested_width_bound_and_honest_coarse_enclosure(original):
    b,n,m,_=original
    r=evaluate(b,n,m,pressure_width_target="0",max_refinement_passes=0)
    assert r["status"]=="CERTIFIED_ENVELOPE"
    assert r["certificate"]["pressure_certificate"]["widths"]["target_accuracy_met"] is False
    assert verify(b,n,m,r["certificate"],pressure_width_target="0")["status"]=="PASS"
    assert verify(b,n,m,r["certificate"],pressure_width_target=None)["status"]=="FAIL"
