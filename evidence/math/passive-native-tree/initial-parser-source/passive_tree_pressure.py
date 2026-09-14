"""Checked native-metric specialization of the explicit common-outlet tree law.

P6 nonlinear port relation P16069--16077/P16836--16853; DEF-RTR56 and
ALG-RTR19/20. Supplied native measurements are an external prerequisite.
This module never changes or interprets an existing fixed-flow/unequal-tee mission.
"""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction as Q
import hashlib
import json
import math
import re

from oma.optimization import passive_pressure as kernel
from oma.optimization.physical import Interval, pi_interval
from .network_scenario import NetworkDesign
from .passive_tree_scenario import PassiveTreeBoundary

METRIC_SCHEMA = "oma.passive-tree-native-metrics/1"
CERTIFICATE_SCHEMA = "oma.passive-tree-native-envelope/1"
SCOPE = "SUPPLIED_NATIVE_METRICS_COMMON_TEE_OUTLET_PASSIVE_TREE"
LIMITATIONS = {
    "native_geometry_and_metric_authenticity_proved": False,
    "actual_inner_bore_or_wall_measured": False,
    "physical_loss_or_boundary_applicability_proved": False,
    "existing_unequal_tee_model_reinterpreted": False,
    "native_geometry_acceptance_authority": False,
    "tight_correlated_solution_hull": False,
    "duplicate_boundary_quotient_nodes_supported": False,
    "static_pressure_reported": False,
}


class _BudgetExceeded(RuntimeError):
    pass


class _Control:
    def __init__(self, checkpoint, maximum, byte_limit):
        if type(maximum) is not int or not 1 <= maximum <= 10_000_000:
            raise ValueError("Invalid adapter work budget")
        if type(byte_limit) is not int or not 1024 <= byte_limit <= 33_554_432:
            raise ValueError("Invalid adapter byte budget")
        if checkpoint is not None and not callable(checkpoint):
            raise ValueError("Invalid checkpoint")
        self.maximum, self.byte_limit = maximum, byte_limit
        self.used, self.callback, self.external = 0, checkpoint, None

    def tick(self, stage="passive_tree_arithmetic"):
        self.used += 1
        if self.callback is not None:
            try:
                self.callback(stage)
            except BaseException as exc:
                self.external = exc
                raise
        if self.used > self.maximum:
            raise _BudgetExceeded("ADAPTER_WORK_BUDGET")


def _dump(value):
    return value.model_dump(mode="json", by_alias=True) if isinstance(value, (NetworkDesign, PassiveTreeBoundary)) else value


def _snapshot(raw, c, stage):
    pending, count = [(raw, 0)], 0
    while pending:
        value, depth = pending.pop()
        c.tick(stage + "_shape")
        count += 1
        if depth > 24 or count > 500_000:
            raise _BudgetExceeded("STRUCTURE_BUDGET")
        if type(value) in (list, dict):
            if len(value) > 8192:
                raise _BudgetExceeded("CONTAINER_BUDGET")
            if type(value) is dict:
                if any(type(k) is not str for k in value):
                    raise ValueError("Only string keys are supported")
                pending.extend((x, depth+1) for pair in value.items() for x in pair)
            else:
                pending.extend((x, depth+1) for x in value)
        elif type(value) is str:
            if len(value) > 4096:
                raise _BudgetExceeded("TOKEN_BUDGET")
        elif type(value) is int:
            if value.bit_length() > 4096:
                raise _BudgetExceeded("INTEGER_BUDGET")
        elif type(value) is float:
            if not math.isfinite(value):
                raise ValueError("Nonfinite numerical geometry or context")
        elif value is not None and type(value) is not bool:
            raise ValueError("Only bounded JSON values are supported")
    parts, total, h = [], 0, hashlib.sha256()
    for part in json.JSONEncoder(sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).iterencode(raw):
        c.tick(stage + "_stream")
        data = part.encode("utf-8")
        total += len(data)
        if total > c.byte_limit:
            raise _BudgetExceeded("ADAPTER_BYTE_BUDGET")
        h.update(data); parts.append(data)
    c.tick(stage + "_complete")
    return h.hexdigest(), json.loads(b"".join(parts))


def _hash(raw, c):
    return _snapshot(raw, c, "passive_tree_binding")[0]


def _raw(boundary, network, metrics, context, target):
    return {"boundary": _dump(boundary), "network": _dump(network), "native_metrics": metrics,
            "context": context, "pressure_width_target": target}


def _q(x):
    if type(x) not in (str, int) or type(x) is bool:
        raise ValueError("Metric bounds need exact integer/rational encodings")
    if type(x) is str and (len(x) > 640 or not re.fullmatch(r"[+-]?[0-9]+(?:/[0-9]+|\.[0-9]+)?", x)):
        raise ValueError("Malformed metric rational")
    v = Q(x)
    if max(abs(v.numerator).bit_length(), v.denominator.bit_length()) > 1024:
        raise _BudgetExceeded("METRIC_RATIONAL_BUDGET")
    return v


def _interval(raw):
    if type(raw) is not dict or set(raw) != {"lower", "upper"}:
        raise ValueError("Metric intervals require lower and upper")
    return Interval(_q(raw["lower"]), _q(raw["upper"]))


def _enc(v):
    return {"lower": str(v.lo), "upper": str(v.hi)}


def _root(value):
    if type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Explicit content root required")
    return value


def _normalize(raw, c, max_components):
    if type(max_components) is not int or not 1 <= max_components <= 512:
        raise ValueError("Invalid component budget")
    netraw = raw["network"]
    if type(netraw) is not dict or type(netraw.get("components")) is not list:
        raise ValueError("Explicit NetworkDesign required")
    if len(netraw["components"]) > max_components:
        raise _BudgetExceeded("COMPONENT_BUDGET")
    network = NetworkDesign.model_validate(netraw)
    boundary = PassiveTreeBoundary.model_validate(raw["boundary"])
    if network.system_type != "PRESSURE_PIPE":
        raise ValueError("Passive tree service is restricted to pressure pipes")
    components = {x.id: x for x in network.components}
    sinks = {x.id: x for x in network.sinks}
    tees = {x.id for x in components.values() if x.kind == "tee"}
    if set(boundary.tee_common_loss_coefficients) != tees or set(boundary.sink_total_pressures_pa) != set(sinks):
        raise ValueError("Boundary and common tee coefficients must cover the exact physical tree")
    metric = raw["native_metrics"]
    if type(metric) is not dict or set(metric) != {"schema", "network_root", "components", "native_evidence_root"}:
        raise ValueError("Complete native metric schema required")
    if metric["schema"] != METRIC_SCHEMA or metric["network_root"] != _hash(network.model_dump(mode="json", by_alias=True), c):
        raise ValueError("Native metrics are bound to another network definition")
    _root(metric["native_evidence_root"])
    if type(metric["components"]) is not dict or set(metric["components"]) != set(components):
        raise ValueError("Native metric component denominator differs")
    lengths, radii, positions = {}, {}, {}
    for cid, comp in sorted(components.items()):
        c.tick("passive_tree_metric_inventory")
        row = metric["components"][cid]
        if type(row) is not dict or set(row) != {"length_m", "outer_radius_m", "ports"}:
            raise ValueError("Each component needs length, radius and all cap positions")
        lengths[cid], radii[cid] = _interval(row["length_m"]), _interval(row["outer_radius_m"])
        if lengths[cid].lo <= 0 or radii[cid].lo <= Q(str(comp.insulation_m)):
            raise ValueError("Whole native length and inferred bore must stay strictly positive")
        if type(row["ports"]) is not dict or set(row["ports"]) != set(comp.ports):
            raise ValueError("Every physical cap must be independently represented")
        for port, value in sorted(row["ports"].items()):
            if type(value) is not dict or set(value) != {"position_m"} or type(value["position_m"]) is not list or len(value["position_m"]) != 3:
                raise ValueError("Each cap requires three SI position enclosures")
            positions[(cid, port)] = tuple(_interval(v) for v in value["position_m"])
    for link in network.connections:
        c.tick("passive_tree_connected_metric_compatibility")
        if any(a.hi < b.lo or b.hi < a.lo for a,b in zip(positions[link.source.key()],positions[link.sink.key()])):
            raise ValueError("Declared connected native cap position enclosures are disjoint")
    if type(raw["context"]) is not dict or not raw["context"]:
        raise ValueError("Current native/check context must be explicitly bound")
    return {"raw": raw, "network": network, "boundary": boundary, "components": components,
            "sinks": sinks, "lengths": lengths, "radii": radii, "positions": positions}


def _groups(n, c, checked=False):
    slots = sorted(n["positions"])
    pairs = [(x.source.key(), x.sink.key(), "connected_caps") for x in n["network"].connections]
    pairs += [((cid, "b"), (cid, "branch"), "explicit_common_tee_head")
              for cid, comp in sorted(n["components"].items()) if comp.kind == "tee"]
    if not checked:
        parent = {x: x for x in slots}
        def root(x):
            while parent[x] != x:
                x = parent[x]
            return x
        for a, b, _ in pairs:
            c.tick("passive_tree_quotient_union")
            pa, pb = root(a), root(b)
            parent[max(pa, pb)] = min(pa, pb)
        partition = {}
        for slot in slots:
            partition.setdefault(root(slot), []).append(slot)
        groups = sorted(partition.values())
    else:
        adjacency = {x: [] for x in slots}
        for a, b, _ in pairs:
            adjacency[a].append(b); adjacency[b].append(a)
        unseen, groups = set(slots), []
        while unseen:
            todo, reached = [min(unseen)], set()
            while todo:
                c.tick("passive_tree_check_quotient")
                x = todo.pop()
                if x in reached:
                    continue
                reached.add(x); todo.extend(adjacency[x])
            unseen -= reached; groups.append(sorted(reached))
        groups.sort()
    slot_nodes = {slot: f"n{i}" for i, group in enumerate(groups) for slot in group}
    return groups, slot_nodes, pairs


def _coefficients(n, c, checked=False):
    b = n["boundary"]
    rho, f, elbow = map(Q, (b.density_kg_m3, b.darcy_friction, b.elbow_loss_coefficient))
    diameters, areas, resistances = {}, {}, {}
    pi = pi_interval()
    for cid, comp in sorted(n["components"].items()):
        c.tick("passive_tree_check_coefficient" if checked else "passive_tree_coefficient")
        r, length, insulation = n["radii"][cid], n["lengths"][cid], Q(str(comp.insulation_m))
        d = Interval(2*(r.lo-insulation), 2*(r.hi-insulation))
        area = Interval(pi.lo*d.lo*d.lo/4, pi.hi*d.hi*d.hi/4)
        if checked:
            # Direct extremal expression, independent of producer interval composition.
            if comp.kind == "tee":
                k = Q(b.tee_common_loss_coefficients[cid])
                low, high = rho*k/(2*area.hi**2), rho*k/(2*area.lo**2)
            else:
                local = elbow if comp.kind == "elbow" else Q(0)
                low = rho*(f*length.lo/d.hi+local)/(2*area.hi**2)
                high = rho*(f*length.hi/d.lo+local)/(2*area.lo**2)
            resistance = Interval(low, high)
        else:
            factor = (Interval.point(Q(b.tee_common_loss_coefficients[cid])) if comp.kind == "tee"
                      else f*length/d + (elbow if comp.kind == "elbow" else 0))
            resistance = rho*factor/(2*area.square())
        if resistance.lo <= 0:
            raise ValueError("Every component requires a strictly positive resistance enclosure")
        for value in (d, area, resistance):
            if any(max(abs(q.numerator).bit_length(),q.denominator.bit_length()) > 4096 for q in (value.lo,value.hi)):
                raise _BudgetExceeded("DERIVED_RATIONAL_BUDGET")
        diameters[cid], areas[cid], resistances[cid] = d, area, resistance
    return diameters, areas, resistances


def _build(n, c, checked=False):
    groups, slot_nodes, pairs = _groups(n, c, checked)
    diameters, areas, resistances = _coefficients(n, c, checked)
    network, boundary = n["network"], n["boundary"]
    nodes = [f"n{i}" for i in range(len(groups))]
    terminals = {"source": network.source.key(), **{"sink/"+sid: sink.endpoint.key() for sid, sink in sorted(n["sinks"].items())}}
    terminal_nodes = {sid: slot_nodes[slot] for sid, slot in terminals.items()}
    if len(set(terminal_nodes.values())) != len(terminal_nodes):
        raise ValueError("Multiple physical boundaries share one common head: individual terminal withdrawal is not determined")
    heads, rho, g = {}, Q(boundary.density_kg_m3), Q(boundary.gravity_m_s2)
    for sid, slot in terminals.items():
        p = Q(boundary.source_total_pressure_pa if sid == "source" else boundary.sink_total_pressures_pa[sid[5:]])
        z = n["positions"][slot][2]
        heads[terminal_nodes[sid]] = Interval(p+rho*g*z.lo,p+rho*g*z.hi)
    edges = [{"id": cid, "source": slot_nodes[(cid,"a")], "target": slot_nodes[(cid,"b")],
              "resistance": _enc(resistances[cid])} for cid in sorted(n["components"])]
    if len(edges) != len(nodes)-1 or any(e["source"] == e["target"] for e in edges):
        raise ValueError("Quotient graph is not the required positive-edge tree")
    derivation = {"schema": "oma.passive-tree-native-derivation/1", "network_root": n["raw"]["native_metrics"]["network_root"],
        "native_evidence_root": n["raw"]["native_metrics"]["native_evidence_root"],
        "metric_root": _hash(n["raw"]["native_metrics"],c),
        "boundary_root": _hash(boundary.model_dump(mode="json",by_alias=True),c),
        "counts": {"components":len(edges), "physical_ports":len(slot_nodes), "connections":len(network.connections),
                   "tees":sum(x.kind=="tee" for x in n["components"].values()), "graph_nodes":len(nodes),"boundaries":len(heads)},
        "quotient_nodes": [{"node":f"n{i}","slots":[list(x) for x in group]} for i,group in enumerate(groups)],
        "unions": [{"left":list(a),"right":list(b),"reason":why} for a,b,why in sorted(pairs)],
        "terminal_nodes":terminal_nodes,
        "component_sections": {cid:{"diameter_m":_enc(diameters[cid]),"area_m2":_enc(areas[cid]),
            "resistance_pa_s2_m6":_enc(resistances[cid]),"tee_darcy_charged":False}
            for cid in sorted(n["components"])},
        "model_scope":"Each physical component once; common tee outlet total-head loss at inlet flow; Cartesian outer native-metric model",
        "limitations":deepcopy(LIMITATIONS)}
    model = {"schema":kernel.MODEL_SCHEMA,"nodes":nodes,"internal_nodes":sorted(set(nodes)-set(heads)),
        "boundary_heads":{v:_enc(value) for v,value in sorted(heads.items())},"edges":edges,
        "context_root":_hash({"context":n["raw"]["context"],"network_root":derivation["network_root"],
                              "boundary_root":derivation["boundary_root"]},c),
        "physical_model_root":_hash(derivation,c),"assumptions":deepcopy(kernel.MODEL_ASSUMPTIONS)}
    return model, derivation, slot_nodes, areas


def derive_passive_tree_model(boundary, network, native_metrics, *, context, max_components=128,
                              max_work=500_000, max_bytes=4_194_304, checkpoint=None):
    c = _Control(checkpoint,max_work,max_bytes)
    root, raw = _snapshot(_raw(boundary,network,native_metrics,context,None),c,"passive_tree_input")
    n = _normalize(raw,c,max_components)
    model, derivation, _, _ = _build(n,c)
    c.tick("passive_tree_derivation_complete")
    c.callback = None
    if _snapshot(_raw(boundary,network,native_metrics,context,None),c,"passive_tree_input")[0] != root:
        raise ValueError("Passive tree inputs changed before derivation publication")
    return model,derivation


def _linear(*terms):
    result = {}
    for factor, expression in terms:
        for edge, value in expression.items():
            result[edge] = result.get(edge,0) + factor*value
    return {edge:value for edge,value in sorted(result.items()) if value}


def _port_expressions(n, model, slot_nodes, c):
    """Reconstruct flows and exact continuity identities for all physical slots."""
    incidence = {v:{} for v in model["nodes"]}
    for edge in model["edges"]:
        incidence[edge["source"]][edge["id"]] = 1
        incidence[edge["target"]][edge["id"]] = -1
    outgoing = {link.source.key():link.sink.key() for link in n["network"].connections}
    terminal_slots = {s.endpoint.key() for s in n["sinks"].values()}
    expressions = {}
    for cid, comp in sorted(n["components"].items()):
        for port in sorted(comp.ports):
            c.tick("passive_tree_port_flow_mapping")
            slot = cid,port
            if port == "a" or comp.kind != "tee":
                expressions[slot] = {cid:1}
            elif slot in outgoing:
                expressions[slot] = {outgoing[slot][0]:1}
            elif slot in terminal_slots:
                # Unique physical outlet at this boundary. Negative net outgoing
                # graph flow is withdrawal; no arbitrary split is invented.
                expressions[slot] = _linear((-1,incidence[slot_nodes[slot]]))
            else:
                raise ValueError("Unaccounted physical tee outlet")
    proofs = []
    internal = set(model["internal_nodes"])
    def establish(identifier, expression, node):
        if not expression:
            reason = "EXACT_LINEAR_IDENTITY"
        elif node in internal and (expression == incidence[node] or expression == _linear((-1,incidence[node]))):
            reason = "COMPLETE_INTERNAL_NODE_CONTINUITY"
        else:
            raise ValueError("Physical flow identity is not implied by complete graph continuity")
        proofs.append({"id":identifier,"difference":expression,"node":node,"reason":reason})
    for cid, comp in sorted(n["components"].items()):
        terms = [(1,expressions[(cid,"a")]),(-1,expressions[(cid,"b")])]
        if comp.kind == "tee":
            terms.append((-1,expressions[(cid,"branch")]))
        establish("component/"+cid,_linear(*terms),slot_nodes[(cid,"b")])
    for i,link in enumerate(n["network"].connections):
        establish("connection/"+str(i),_linear((1,expressions[link.source.key()]),(-1,expressions[link.sink.key()])),slot_nodes[link.source.key()])
    source = n["network"].source.key()
    establish("source",_linear((1,expressions[source]),(-1,incidence[slot_nodes[source]])),slot_nodes[source])
    for sid,sink in sorted(n["sinks"].items()):
        slot = sink.endpoint.key()
        establish("sink/"+sid,_linear((1,expressions[slot]),(1,incidence[slot_nodes[slot]])),slot_nodes[slot])
    return expressions,proofs


def _evaluate_linear(expression, flows):
    result = Interval.point(0)
    for cid,coefficient in expression.items():
        result += coefficient*flows[cid]
    return result


def _forward(flow):
    return "PASS" if flow.lo > 0 else "FAIL" if flow.hi <= 0 else "UNKNOWN"


def _minimum(flow, minimum):
    return "PASS" if flow.lo >= minimum else "FAIL" if flow.hi < minimum else "UNKNOWN"


def _maximum(value, maximum):
    return "PASS" if value.hi <= maximum else "FAIL" if value.lo > maximum else "UNKNOWN"


def _verdict(values):
    return "FAIL" if "FAIL" in values else "PASS" if values and all(x=="PASS" for x in values) else "UNKNOWN"


def _service(n, model, slot_nodes, areas, verified, c):
    flows = {row["edge"]:_interval({k:row[k] for k in ("lower","upper")}) for row in verified["flow_bounds"]}
    heads = {row["node"]:_interval({k:row[k] for k in ("lower","upper")}) for row in verified["pressure_bounds"]}
    if set(flows) != set(n["components"]) or set(heads) != set(model["nodes"]):
        raise ValueError("Pressure proof returned incomplete physical graph denominator")
    expressions,conservation = _port_expressions(n,model,slot_nodes,c)
    rho,g,vmax = map(Q,(n["boundary"].density_kg_m3,n["boundary"].gravity_m_s2,n["boundary"].maximum_velocity_m_s))
    ports,port_flows,verdicts = [],{},[]
    for slot,expr in sorted(expressions.items()):
        c.tick("passive_tree_port_enclosure")
        cid,port = slot
        flow = _evaluate_linear(expr,flows)
        port_flows[slot] = flow
        velocity = flow/areas[cid]
        speed = Interval(0 if velocity.lo <= 0 <= velocity.hi else min(abs(velocity.lo),abs(velocity.hi)),max(abs(velocity.lo),abs(velocity.hi)))
        forward,velocity_status = _forward(flow),_maximum(speed,vmax)
        head = heads[slot_nodes[slot]]
        total_pressure = head-rho*g*n["positions"][slot][2]
        ports.append({"component":cid,"port":port,"node":slot_nodes[slot],"flow_expression":expr,
            "flow_m3_s":_enc(flow),"forward_status":forward,"velocity_m_s":_enc(velocity),
            "speed_m_s":_enc(speed),"maximum_velocity_status":velocity_status,
            "total_head_pa":_enc(head),"total_pressure_pa":_enc(total_pressure)})
        verdicts.extend((forward,velocity_status))
    deliveries = []
    for sid,sink in sorted(n["sinks"].items()):
        minimum = Q(n["boundary"].minimum_sink_flows_m3_s[sid])
        flow = port_flows[sink.endpoint.key()]
        status = _minimum(flow,minimum)
        verdicts.append(status)
        deliveries.append({"sink":sid,"minimum_m3_s":str(minimum),"flow_m3_s":_enc(flow),"status":status})
    return {"verdict":_verdict(verdicts),"physical_ports":ports,"deliveries":deliveries,
        "source_flow_m3_s":_enc(port_flows[n["network"].source.key()]),"conservation_identities":conservation,
        "counts":{"physical_ports":len(ports),"deliveries":len(deliveries),"conservation_identities":len(conservation)},
        "scope":SCOPE,"limitations":deepcopy(LIMITATIONS)}


def _failure(exc,c):
    if c is not None and exc is c.external:
        raise exc
    return {"status":"UNKNOWN" if isinstance(exc,_BudgetExceeded) else "BLOCKED", "verdict":"UNKNOWN",
        "reason":str(exc),"scope":SCOPE,"proof_complete":False,"work":0 if c is None else c.used,
        "limitations":deepcopy(LIMITATIONS)}


def _finish_input_guard(boundary,network,metrics,context,target,root,c):
    c.callback = None
    if _snapshot(_raw(boundary,network,metrics,context,target),c,"passive_tree_input")[0] != root:
        raise ValueError("Passive tree inputs changed before publication")


def verify_passive_tree_envelope(boundary, network, native_metrics, certificate, *, context,
        pressure_width_target=None, max_components=128, max_work=2_000_000,
        max_bytes=16_777_216, checkpoint=None):
    """Independently replay cap quotient, dimensional extrema and pressure proof."""
    c = None
    try:
        c = _Control(checkpoint,max_work,max_bytes)
        root,raw = _snapshot(_raw(boundary,network,native_metrics,context,pressure_width_target),c,"passive_tree_input")
        cert_root,packet = _snapshot(certificate,c,"passive_tree_certificate")
        n = _normalize(raw,c,max_components)
        # Distinct adjacency-component reconstruction and direct dimensional
        # extrema; neither producer derivation nor producer envelope is trusted.
        model,derivation,slot_nodes,areas = _build(n,c,checked=True)
        if type(packet) is not dict or set(packet) != {"schema","input_root","model","derivation","pressure_certificate","service","certificate_root"}:
            raise ValueError("Complete passive tree certificate required")
        if packet["schema"] != CERTIFICATE_SCHEMA or packet["input_root"] != root:
            raise ValueError("Passive tree certificate input identity differs")
        if _hash(packet["model"],c) != _hash(model,c) or _hash(packet["derivation"],c) != _hash(derivation,c):
            raise ValueError("Forged graph quotient, native metric coefficient or physical inventory")
        if _root(packet["certificate_root"]) != _hash({k:v for k,v in packet.items() if k!="certificate_root"},c):
            raise ValueError("Passive tree certificate content root differs")
        verified = kernel.verify_passive_pressure(model,packet["pressure_certificate"],
            pressure_width_target=raw["pressure_width_target"],max_nodes=max_components+1,max_edges=max_components,
            max_work=max_work,max_certificate_bytes=max_bytes,checkpoint=c.tick)
        if verified["status"] != "PASS":
            return {"status":"UNKNOWN" if verified["status"]=="UNKNOWN" else "FAIL","verdict":"UNKNOWN", "proof_complete":False,
                "scope":SCOPE,"reason":"Independent passive pressure certificate did not pass","pressure_check":verified,"limitations":deepcopy(LIMITATIONS)}
        service = _service(n,model,slot_nodes,areas,verified,c)
        if _hash(packet["service"],c) != _hash(service,c):
            raise ValueError("Forged per-port pressure/flow/velocity/delivery or continuity report")
        c.tick("passive_tree_verifier_complete")
        _finish_input_guard(boundary,network,native_metrics,context,pressure_width_target,root,c)
        if _snapshot(certificate,c,"passive_tree_certificate")[0] != cert_root:
            raise ValueError("Caller passive tree certificate changed during verification")
        return {"status":"PASS","verdict":service["verdict"],"scope":SCOPE,"proof_complete":True,
            "input_root":root,"certificate_root":packet["certificate_root"],"model_root":verified["model_root"],
            "pressure_check":verified,"service":service,"counts":derivation["counts"],"work":c.used,
            "native_geometry_acceptance_authority":False,"limitations":deepcopy(LIMITATIONS)}
    except (ValueError,TypeError,KeyError,OverflowError,_BudgetExceeded) as exc:
        result = _failure(exc,c)
        if result["status"]=="BLOCKED":
            result["status"]="FAIL"
        return result


def evaluate_passive_tree(boundary, network, native_metrics, *, context,
        pressure_width_target=None, max_components=128, max_work=2_000_000,
        max_bytes=16_777_216, max_refinement_passes=128, checkpoint=None):
    """Produce and independently verify a complete model and service envelope."""
    c = None
    try:
        c = _Control(checkpoint,max_work,max_bytes)
        root,raw = _snapshot(_raw(boundary,network,native_metrics,context,pressure_width_target),c,"passive_tree_input")
        n = _normalize(raw,c,max_components)
        model,derivation,slot_nodes,areas = _build(n,c)
        result = kernel.compile_passive_pressure(model,pressure_width_target=raw["pressure_width_target"],
            max_nodes=max_components+1,max_edges=max_components,max_work=max_work,max_certificate_bytes=max_bytes,
            max_refinement_passes=max_refinement_passes,checkpoint=c.tick)
        if result.get("status") != "CERTIFIED_ENCLOSURE":
            return {"status":"UNKNOWN","verdict":"UNKNOWN","proof_complete":False,"scope":SCOPE,
                "reason":"Pressure kernel did not produce a complete envelope","producer":result,"limitations":deepcopy(LIMITATIONS)}
        verified = kernel.verify_passive_pressure(model,result,pressure_width_target=raw["pressure_width_target"],
            max_nodes=max_components+1,max_edges=max_components,max_work=max_work,max_certificate_bytes=max_bytes,checkpoint=c.tick)
        if verified.get("status") != "PASS":
            return {"status":"UNKNOWN","verdict":"UNKNOWN","proof_complete":False,"scope":SCOPE,
                "reason":"Pressure kernel independent verification did not pass","pressure_check":verified,"limitations":deepcopy(LIMITATIONS)}
        service = _service(n,model,slot_nodes,areas,verified,c)
        packet = {"schema":CERTIFICATE_SCHEMA,"input_root":root,"model":model,"derivation":derivation,
                  "pressure_certificate":result,"service":service}
        packet["certificate_root"] = _hash(packet,c)
        independent = verify_passive_tree_envelope(raw["boundary"],raw["network"],raw["native_metrics"],packet,
            context=raw["context"],pressure_width_target=raw["pressure_width_target"],max_components=max_components,
            max_work=max_work,max_bytes=max_bytes,checkpoint=c.tick)
        if independent.get("status") != "PASS":
            return {"status":"UNKNOWN","verdict":"UNKNOWN","proof_complete":False,"scope":SCOPE,
                "reason":"Independent native-metric derivation check did not pass","independent_check":independent,"limitations":deepcopy(LIMITATIONS)}
        c.tick("passive_tree_producer_complete")
        _finish_input_guard(boundary,network,native_metrics,context,pressure_width_target,root,c)
        return {"status":"CERTIFIED_ENVELOPE","verdict":independent["verdict"],"scope":SCOPE,"proof_complete":True,
                "certificate":packet,"independent_check":independent,"work":c.used,"limitations":deepcopy(LIMITATIONS)}
    except (ValueError,TypeError,KeyError,OverflowError,_BudgetExceeded) as exc:
        return _failure(exc,c)
