"""Native-metric specialization of unequal, total-inlet-flow tee losses.

No native authenticity or existing mission interpretation is conferred here.
Complete physical path reconstruction feeds separate local and global proofs.
"""
from copy import deepcopy
from fractions import Fraction as Q
import hashlib
import json

from oma.optimization import coupled_tree_pressure as local
from oma.optimization import coupled_tree_univalence as global_proof
from oma.optimization.physical import Interval, pi_interval
from .network_scenario import NetworkDesign
from .coupled_tree_scenario import CoupledTreeBoundary
from . import passive_tree_pressure as bounded

METRIC_SCHEMA = "oma.coupled-tree-native-metrics/1"
CERTIFICATE_SCHEMA = "oma.coupled-tree-native-envelope/1"
SCOPE = "SUPPLIED_NATIVE_METRICS_UNEQUAL_INLET_FLOW_TEE_TREE_UNIQUE_NONNEGATIVE_EQUILIBRIUM"
LIMITATIONS = {
    "native_geometry_and_metric_authenticity_proved": False,
    "actual_inner_bore_or_wall_measured": False,
    "physical_loss_or_boundary_applicability_proved": False,
    "old_common_tee_or_fixed_flow_mission_reinterpreted": False,
    "native_geometry_acceptance_authority": False,
    "negative_flow_regimes_or_other_loss_laws_covered": False,
    "tight_correlated_solution_hull": False,
    "static_pressure_reported": False,
    "flow_search_box_alone_excludes_other_equilibria": False,
}

_enc, _interval, _q = bounded._enc, bounded._interval, bounded._q


class _Control(bounded._Control):
    def tick(self, stage="coupled_tree_arithmetic"):
        super().tick(stage.replace("passive_tree_", "coupled_tree_"))


def _hash(raw, c):
    return bounded._snapshot(raw, c, "coupled_tree_binding")[0]


def _raw(boundary, network, metrics, context):
    def dump(x):
        return x.model_dump(mode="json", by_alias=True) if isinstance(x, (CoupledTreeBoundary, NetworkDesign)) else x
    return {"boundary": dump(boundary), "network": dump(network), "native_metrics": metrics, "context": context}


def _shape(raw, maximum):
    if type(maximum) is not int or not 1 <= maximum <= 512:
        raise ValueError("Invalid component budget")
    if type(raw) is not dict or type(raw.get("network")) is not dict:
        raise ValueError("Explicit NetworkDesign required")
    network = raw["network"]
    for key, limit in (("components", maximum), ("connections", max(0, maximum-1)), ("sinks", 32), ("demand_paths", 32)):
        if type(network.get(key)) is not list:
            raise ValueError("Explicit physical inventory required: " + key)
        if len(network[key]) > limit:
            raise bounded._BudgetExceeded("COMPONENT_OR_PATH_BUDGET")
    if type(raw.get("boundary")) is not dict:
        raise ValueError("Explicit unequal tree boundary required")
    for key, limit in (("sink_total_pressures_pa", 32), ("minimum_sink_flows_m3_s", 32),
                       ("flow_search_box_m3_s", 32), ("tee_outlet_loss_coefficients", min(maximum,31))):
        if type(raw["boundary"].get(key)) is not dict:
            raise ValueError("Explicit boundary inventory required: " + key)
        if len(raw["boundary"][key]) > limit:
            raise bounded._BudgetExceeded("BOUNDARY_INVENTORY_BUDGET")
    for path in network["demand_paths"]:
        if type(path) is not dict or type(path.get("steps")) is not list:
            raise ValueError("Explicit complete physical path required")
        if len(path["steps"]) > maximum:
            raise bounded._BudgetExceeded("COMPONENT_OR_PATH_BUDGET")
    metric=raw.get("native_metrics")
    if type(metric) is not dict or type(metric.get("components")) is not dict:
        raise ValueError("Complete native metric inventory required")
    if len(metric["components"])>maximum:
        raise bounded._BudgetExceeded("COMPONENT_OR_PATH_BUDGET")
    for row in metric["components"].values():
        if type(row) is not dict or type(row.get("ports")) is not dict:
            raise ValueError("Complete native cap inventory required")
        if len(row["ports"])>3:
            raise bounded._BudgetExceeded("PHYSICAL_PORT_BUDGET")


def _normalize(raw, c, maximum):
    _shape(raw, maximum)
    network = NetworkDesign.model_validate(raw["network"])
    boundary = CoupledTreeBoundary.model_validate(raw["boundary"])
    if network.system_type != "PRESSURE_PIPE":
        raise ValueError("Unequal coupled tree law requires pressure pipes")
    components = {comp.id: comp for comp in network.components}
    sinks = {sink.id: sink for sink in network.sinks}
    tees = {cid for cid,comp in components.items() if comp.kind == "tee"}
    if set(boundary.tee_outlet_loss_coefficients) != tees or set(boundary.sink_total_pressures_pa) != set(sinks):
        raise ValueError("Every physical tee and sink needs its exact new boundary entries")
    metric = raw["native_metrics"]
    if type(metric) is not dict or set(metric) != {"schema", "network_root", "native_evidence_root", "components"}:
        raise ValueError("Complete unequal tree native metric schema required")
    if metric["schema"] != METRIC_SCHEMA or metric["network_root"] != _hash(network.model_dump(mode="json",by_alias=True),c):
        raise ValueError("Native metrics belong to another network or model")
    bounded._root(metric["native_evidence_root"])
    if type(metric["components"]) is not dict or set(metric["components"]) != set(components):
        raise ValueError("Native metric component denominator differs")
    lengths, radii, positions = {}, {}, {}
    for cid,comp in sorted(components.items()):
        c.tick("coupled_tree_native_metric_inventory")
        row = metric["components"][cid]
        if type(row) is not dict or set(row) != {"length_m", "outer_radius_m", "ports"}:
            raise ValueError("Every component needs whole length, radius and all caps")
        lengths[cid],radii[cid] = _interval(row["length_m"]),_interval(row["outer_radius_m"])
        if lengths[cid].lo <= 0 or radii[cid].lo <= Q(str(comp.insulation_m)):
            raise ValueError("Native whole length and ideal inferred bore must be strictly positive")
        if type(row["ports"]) is not dict or set(row["ports"]) != set(comp.ports):
            raise ValueError("Every physical cap needs a native coordinate enclosure")
        for slot,point in row["ports"].items():
            if type(point) is not dict or set(point) != {"position_m"} or type(point["position_m"]) is not list or len(point["position_m"]) != 3:
                raise ValueError("Each physical cap needs three exact SI coordinate intervals")
            positions[(cid,slot)] = tuple(_interval(v) for v in point["position_m"])
    for link in network.connections:
        c.tick("coupled_tree_cap_compatibility")
        if any(a.hi < b.lo or b.hi < a.lo for a,b in zip(positions[link.source.key()],positions[link.sink.key()])):
            raise ValueError("Connected physical cap coordinate enclosures are disjoint")
    if type(raw["context"]) is not dict or not raw["context"]:
        raise ValueError("Complete current native/check context must be explicitly bound")
    return {"raw":raw,"network":network,"boundary":boundary,"components":components,"sinks":sinks,
            "lengths":lengths,"radii":radii,"positions":positions}


def _name(cid, outlet):
    # Physical IDs may already occupy all 120 characters of their allowed field.
    return hashlib.sha256(json.dumps([cid,outlet],separators=(",",":"),ensure_ascii=False).encode("utf-8")).hexdigest()


def _term(cid, outlet, comp):
    return "t/"+_name(cid, outlet if comp.kind=="tee" else "body")


def _path_inventory(n, c, checked=False):
    net,components=n["network"],n["components"]
    links={link.source.key():link.sink.key() for link in net.connections}
    incoming={link.sink.component:link.source.key() for link in net.connections}
    terminals={sink.endpoint.key():sid for sid,sink in n["sinks"].items()}
    desc={cid:set() for cid in components};outlets={};prefixes={};paths={}
    if not checked:
        # Producer descends once, then propagates path prefixes forward.
        postorder=[];todo=[net.source.component];seen=set()
        while todo:
            c.tick("coupled_tree_producer_descendants")
            cid=todo.pop()
            if cid in seen:raise ValueError("Repeated component in physical tree traversal")
            seen.add(cid);postorder.append(cid)
            todo.extend(target[0] for slot,target in links.items() if slot[0]==cid)
        if seen!=set(components):raise ValueError("Physical component tree is incomplete")
        for cid in reversed(postorder):
            for port in sorted(set(components[cid].ports)-{"a"}):
                slot=(cid,port)
                leaves={terminals[slot]} if slot in terminals else set(desc[links[slot][0]]) if slot in links else set()
                if not leaves:raise ValueError("Physical outlet has no accounted sink")
                outlets[slot]=leaves;desc[cid].update(leaves)
        prefixes[net.source.key()]=[]
        for cid in postorder:
            parent=prefixes[(cid,"a")]
            for port in sorted(set(components[cid].ports)-{"a"}):
                slot=(cid,port);prefixes[slot]=parent+[_term(cid,port,components[cid])]
                if slot in links:prefixes[links[slot]]=list(prefixes[slot])
        # Paths are physical steps, independent from the caller's stored order.
        for sid,sink in sorted(n["sinks"].items()):
            endpoint=sink.endpoint.key();back=[]
            while True:
                back.append([endpoint[0],"a",endpoint[1]])
                if endpoint[0]==net.source.component:break
                endpoint=incoming[endpoint[0]]
            paths[sid]=list(reversed(back))
    else:
        # Checker works backward from every actual terminal and accumulates
        # incidence and prefixes; no producer subtree traversal is called.
        for sid,sink in sorted(n["sinks"].items()):
            endpoint=sink.endpoint.key();back=[];seen=set()
            while True:
                c.tick("coupled_tree_check_physical_path")
                cid,port=endpoint
                if cid in seen:raise ValueError("Cycle in independently reconstructed sink path")
                seen.add(cid);back.append([cid,"a",port])
                desc[cid].add(sid);outlets.setdefault(endpoint,set()).add(sid)
                if cid==net.source.component:break
                if cid not in incoming:raise ValueError("Sink path does not reach physical source")
                endpoint=incoming[cid]
            paths[sid]=list(reversed(back));prefix=[]
            for cid,entry,outlet in paths[sid]:
                for slot,value in (((cid,entry),list(prefix)),((cid,outlet),prefix+[_term(cid,outlet,components[cid])])):
                    if slot in prefixes and prefixes[slot]!=value:raise ValueError("Inconsistent shared physical prefix")
                    prefixes[slot]=value
                prefix=prefixes[(cid,outlet)]
    if set(prefixes)!=set(n["positions"]) or set(outlets)!={slot for slot in n["positions"] if slot[1]!="a"}:
        raise ValueError("Physical port or outlet path denominator is incomplete")
    expected_paths={p.sink_id:[[s.component,s.entry_port,s.exit_port] for s in p.steps] for p in net.demand_paths}
    if paths!=expected_paths or desc[net.source.component]!=set(n["sinks"]):
        raise ValueError("Declared demand paths differ from complete physical reconstruction")
    for cid,comp in components.items():
        pieces=[outlets[(cid,port)] for port in sorted(set(comp.ports)-{"a"})]
        if not desc[cid] or set.union(*pieces)!=desc[cid] or sum(map(len,pieces))!=len(desc[cid]):
            raise ValueError("Component outlets do not partition its complete descendants")
    return desc,outlets,prefixes,paths


def _coefficients(n, c, checked=False):
    boundary=n["boundary"];rho,f,excess=map(Q,(boundary.density_kg_m3,boundary.darcy_friction,boundary.elbow_loss_coefficient))
    pi=pi_interval();sections={};losses={}
    for cid,comp in sorted(n["components"].items()):
        c.tick("coupled_tree_check_dimensional_extrema" if checked else "coupled_tree_dimensional_losses")
        radius,length,insulation=n["radii"][cid],n["lengths"][cid],Q(str(comp.insulation_m))
        diameter=Interval(2*(radius.lo-insulation),2*(radius.hi-insulation))
        area=Interval(pi.lo*diameter.lo**2/4,pi.hi*diameter.hi**2/4)
        components={}
        for outlet in ("b","branch") if comp.kind=="tee" else ("body",):
            if comp.kind=="tee":
                factor=Q(getattr(boundary.tee_outlet_loss_coefficients[cid],outlet))
                loss=(Interval(rho*factor/(2*area.hi**2),rho*factor/(2*area.lo**2)) if checked
                      else Interval.point(rho*factor)/(2*area.square()))
            else:
                local_excess=excess if comp.kind=="elbow" else Q(0)
                loss=(Interval(rho*(f*length.lo/diameter.hi+local_excess)/(2*area.hi**2),
                               rho*(f*length.hi/diameter.lo+local_excess)/(2*area.lo**2)) if checked
                      else rho*(f*length/diameter+local_excess)/(2*area.square()))
            if loss.lo<=0:raise ValueError("All modeled body/outlet loss intervals must be strictly positive")
            for bound in (diameter,area,loss):
                if any(max(abs(v.numerator).bit_length(),v.denominator.bit_length())>4096 for v in (bound.lo,bound.hi)):
                    raise bounded._BudgetExceeded("DERIVED_RATIONAL_BUDGET")
            losses[(cid,outlet)]=loss;components[outlet]=_enc(loss)
        sections[cid]={"diameter_m":_enc(diameter),"area_m2":_enc(area),"loss_coefficients_pa_s2_m6":components,
                       "tee_darcy_charged":False}
    return sections,losses


def _parameter_enclosure(value, checked=False):
    """Conservative rational representation budget, never a parameter midpoint."""
    scale=1 << 40
    if checked:
        lower,_=divmod(value.lo.numerator*scale,value.lo.denominator)
        upper,remainder=divmod(value.hi.numerator*scale,value.hi.denominator)
        upper+=bool(remainder)
    else:
        lower=(value.lo*scale).__floor__();upper=(value.hi*scale).__ceil__()
    result=Interval(Q(lower,scale),Q(upper,scale))
    if not result.lo<=value.lo<=value.hi<=result.hi:
        raise ValueError("Outward model parameter enclosure failed")
    return result


def _build(n, c, checked=False):
    desc,outlets,prefixes,paths=_path_inventory(n,c,checked)
    sections,losses=_coefficients(n,c,checked)
    terms,coefficients,term_physics=[],{},[]
    for cid,comp in sorted(n["components"].items()):
        for outlet in ("b","branch") if comp.kind=="tee" else ("body",):
            c.tick("coupled_tree_complete_term_inventory")
            tid="t/"+_name(cid,outlet);aid="k/"+_name(cid,outlet)
            applied=outlets[(cid,outlet)] if comp.kind=="tee" else desc[cid]
            terms.append({"id":tid,"coefficient_id":aid,"descendant_leaves":sorted(desc[cid]),"applies_to_leaves":sorted(applied)})
            outer=_parameter_enclosure(losses[(cid,outlet)],checked)
            if outer.lo<=0:
                raise bounded._BudgetExceeded("POSITIVE_COEFFICIENT_NOT_RESOLVED_ON_PARAMETER_GRID")
            coefficients[aid]=_enc(outer)
            term_physics.append({"term_id":tid,"coefficient_id":aid,"component":cid,"outlet":outlet,
                "flow_reference":"COMPLETE_COMPONENT_INLET_DESCENDANTS","applies_to_leaves":sorted(applied),
                "descendant_leaves":sorted(desc[cid]),"tee_darcy_charged":False})
    boundary,net=n["boundary"],n["network"]
    rho,g=Q(boundary.density_kg_m3),Q(boundary.gravity_m_s2)
    source_pressure=_interval(boundary.source_total_pressure_pa.model_dump())
    source_head=source_pressure+rho*g*n["positions"][net.source.key()][2]
    raw_heads={sid:source_head-_interval(boundary.sink_total_pressures_pa[sid].model_dump())-rho*g*n["positions"][sink.endpoint.key()][2]
               for sid,sink in sorted(n["sinks"].items())}
    heads={sid:_enc(_parameter_enclosure(value,checked)) for sid,value in raw_heads.items()}
    box={sid:interval.model_dump() for sid,interval in sorted(boundary.flow_search_box_m3_s.items())}
    port_paths=[{"component":cid,"port":port,"descendant_leaves":sorted(desc[cid] if port=="a" else outlets[(cid,port)]),
                 "loss_terms":prefixes[(cid,port)]} for cid,port in sorted(prefixes)]
    derivation={"schema":"oma.coupled-tree-native-derivation/1","network_root":n["raw"]["native_metrics"]["network_root"],
        "native_evidence_root":n["raw"]["native_metrics"]["native_evidence_root"],"metric_root":_hash(n["raw"]["native_metrics"],c),
        "boundary_root":_hash(boundary.model_dump(mode="json",by_alias=True),c),
        "component_sections":sections,"term_physics":term_physics,"port_paths":port_paths,
        "sink_paths":paths,"component_descendants":{cid:sorted(v) for cid,v in sorted(desc.items())},
        "source_total_head_pa":_enc(source_head),"available_heads_pa":{sid:_enc(v) for sid,v in raw_heads.items()},
        "polynomial_parameter_enclosures":{"coefficients":coefficients,"available_heads":heads},
        "parameter_rounding":{"method":"OUTWARD_DYADIC_ENCLOSURE","step":"1/1099511627776",
                              "coefficient_units":"Pa*s^2/m^6","head_units":"Pa","substitutes_midpoint":False},
        "counts":{"components":len(n["components"]),"physical_ports":len(prefixes),"connections":len(net.connections),
                  "tees":len(boundary.tee_outlet_loss_coefficients),"terms":len(terms),"leaves":len(n["sinks"]),"boundaries":len(n["sinks"])+1},
        "model_scope":"Complete directed tree; each body loss once per containing path; each tee outlet uses full inlet flow and its own total coefficient; no tee Darcy",
        "limitations":deepcopy(LIMITATIONS)}
    model={"schema":local.MODEL_SCHEMA,"leaves":sorted(n["sinks"]),"coefficients":dict(sorted(coefficients.items())),
        "terms":sorted(terms,key=lambda t:t["id"]),"available_heads":heads,
        "context_root":_hash({"context":n["raw"]["context"],"network_root":derivation["network_root"],"boundary_root":derivation["boundary_root"]},c),
        "physical_model_root":_hash(derivation,c),"assumptions":deepcopy(local.MODEL_ASSUMPTIONS)}
    return model,box,derivation


def _finish(boundary,network,metrics,context,input_root,c,certificate=None,certificate_root=None):
    c.callback=None
    if bounded._snapshot(_raw(boundary,network,metrics,context),c,"coupled_tree_input")[0]!=input_root:
        raise ValueError("Coupled tree caller inputs changed before completion")
    if certificate is not None and bounded._snapshot(certificate,c,"coupled_tree_certificate")[0]!=certificate_root:
        raise ValueError("Coupled tree caller certificate changed before completion")


def derive_coupled_tree_model(boundary,network,native_metrics,*,context,max_components=128,max_work=500_000,max_bytes=4_194_304,checkpoint=None):
    c=_Control(checkpoint,max_work,max_bytes);original=_raw(boundary,network,native_metrics,context);_shape(original,max_components)
    root,raw=bounded._snapshot(original,c,"coupled_tree_input")
    n=_normalize(raw,c,max_components);model,box,derivation=_build(n,c)
    c.tick("coupled_tree_derivation_complete");_finish(boundary,network,native_metrics,context,root,c)
    return model,box,derivation


def _intersect(first, second):
    return Interval(max(first.lo,second.lo),min(first.hi,second.hi))


def _bounded_interval(value):
    if any(max(abs(v.numerator).bit_length(),v.denominator.bit_length())>4096 for v in (value.lo,value.hi)):
        raise bounded._BudgetExceeded("SERVICE_RATIONAL_BUDGET")
    return value


def _service(n,model,derivation,local_check,global_check,c):
    if (local_check.get("status")!="PASS" or global_check.get("status")!="PASS"
            or local_check.get("proof_complete") is not True or global_check.get("proof_complete") is not True
            or local_check["model_root"]!=global_check["model_root"]):
        raise ValueError("Both independently checked local existence and global uniqueness are required")
    flows={sid:_interval(v) for sid,v in local_check["root_enclosure"].items()}
    if set(flows)!=set(n["sinks"]) or any(v.lo<=0 for v in flows.values()):
        raise ValueError("Positive solution must cover every exact leaf")
    expressions={(row["component"],row["port"]):{sid:1 for sid in row["descendant_leaves"]} for row in derivation["port_paths"]}
    prefixes={(row["component"],row["port"]):row["loss_terms"] for row in derivation["port_paths"]}
    if set(expressions)!=set(n["positions"]) or len(derivation["port_paths"])!=len(expressions):
        raise ValueError("Physical port expressions are incomplete or duplicated")
    terms={t["id"]:t for t in model["terms"]};losses={}
    for tid,t in terms.items():
        c.tick("coupled_tree_service_path_loss")
        total=bounded._evaluate_linear({sid:1 for sid in t["descendant_leaves"]},flows)
        losses[tid]=_bounded_interval(_interval(model["coefficients"][t["coefficient_id"]])*total.square())
    net,boundary=n["network"],n["boundary"]
    conservation=[];head_identities=[]
    def conserve(identifier,*parts):
        difference=bounded._linear(*parts)
        if difference:raise ValueError("Physical continuity is not an exact leaf-flow identity")
        conservation.append({"id":identifier,"difference":difference,"reason":"EXACT_COMPLETE_LEAF_FLOW_IDENTITY"})
    def head_identity(identifier,left,right):
        if left!=right:raise ValueError("Incomplete physical source-to-port head-loss path")
        head_identities.append({"id":identifier,"loss_terms":list(left),"reason":"EXACT_COMPLETE_PATH_LOSS_IDENTITY"})
    for cid,comp in sorted(n["components"].items()):
        parts=[(1,expressions[(cid,"a")]),(-1,expressions[(cid,"b")])]
        if comp.kind=="tee":parts.append((-1,expressions[(cid,"branch")]))
        conserve("component/"+cid,*parts)
        for outlet in sorted(set(comp.ports)-{"a"}):
            head_identity("component/"+cid+"/"+outlet,prefixes[(cid,outlet)],prefixes[(cid,"a")]+[_term(cid,outlet,comp)])
    for i,link in enumerate(net.connections):
        conserve("connection/"+str(i),(1,expressions[link.source.key()]),(-1,expressions[link.sink.key()]))
        head_identity("connection/"+str(i),prefixes[link.source.key()],prefixes[link.sink.key()])
    conserve("source",(1,expressions[net.source.key()]),(-1,{sid:1 for sid in n["sinks"]}))
    head_identity("source",prefixes[net.source.key()],[])
    for sid,sink in sorted(n["sinks"].items()):
        conserve("sink/"+sid,(1,expressions[sink.endpoint.key()]),(-1,{sid:1}))
        expected=sorted(t["id"] for t in model["terms"] if sid in t["applies_to_leaves"])
        head_identity("sink/"+sid,sorted(prefixes[sink.endpoint.key()]),expected)
    rho,g,vmax=map(Q,(boundary.density_kg_m3,boundary.gravity_m_s2,boundary.maximum_velocity_m_s))
    source_pressure=_interval(boundary.source_total_pressure_pa.model_dump())
    source_head=source_pressure+rho*g*n["positions"][net.source.key()][2]
    sink_slots={sink.endpoint.key():sid for sid,sink in n["sinks"].items()}
    ports=[];port_flows={};verdicts=[]
    for slot,expr in sorted(expressions.items()):
        c.tick("coupled_tree_service_physical_port")
        cid,port=slot;flow=_bounded_interval(bounded._evaluate_linear(expr,flows));port_flows[slot]=flow
        area=_interval(derivation["component_sections"][cid]["area_m2"])
        velocity=_bounded_interval(flow/area)
        speed=Interval(0 if velocity.lo<=0<=velocity.hi else min(abs(velocity.lo),abs(velocity.hi)),max(abs(velocity.lo),abs(velocity.hi)))
        head=source_head
        for tid in prefixes[slot]:head=_bounded_interval(head-losses[tid])
        if slot==net.source.key():boundary_pressure=source_pressure
        elif slot in sink_slots:boundary_pressure=_interval(boundary.sink_total_pressures_pa[sink_slots[slot]].model_dump())
        else:boundary_pressure=None
        # Actual physical parameter tuples map into the outer polynomial box.
        # At their true solution each boundary equation also holds exactly.
        if boundary_pressure is not None:
            head=_intersect(head,boundary_pressure+rho*g*n["positions"][slot][2])
        pressure=_bounded_interval(head-rho*g*n["positions"][slot][2])
        if boundary_pressure is not None:pressure=_intersect(pressure,boundary_pressure)
        forward=bounded._forward(flow);velocity_status=bounded._maximum(speed,vmax)
        verdicts.extend((forward,velocity_status))
        ports.append({"component":cid,"port":port,"flow_expression":expr,"loss_terms":prefixes[slot],
            "flow_m3_s":_enc(flow),"forward_status":forward,"velocity_m_s":_enc(velocity),"speed_m_s":_enc(speed),
            "maximum_velocity_status":velocity_status,"total_head_pa":_enc(head),"total_pressure_pa":_enc(pressure)})
    deliveries=[]
    for sid,sink in sorted(n["sinks"].items()):
        minimum=Q(boundary.minimum_sink_flows_m3_s[sid]);flow=port_flows[sink.endpoint.key()]
        status=bounded._minimum(flow,minimum);verdicts.append(status)
        deliveries.append({"sink":sid,"minimum_m3_s":str(minimum),"flow_m3_s":_enc(flow),"status":status})
    return {"verdict":bounded._verdict(verdicts),"physical_ports":ports,"deliveries":deliveries,
        "source_flow_m3_s":_enc(port_flows[net.source.key()]),"conservation_identities":conservation,"head_path_identities":head_identities,
        "counts":{"physical_ports":len(ports),"deliveries":len(deliveries),"conservation_identities":len(conservation),"head_path_identities":len(head_identities)},
        "quantifier":"EVERY_ADMITTED_PHYSICAL_PARAMETER_TUPLE_MAPPED_INTO_CERTIFIED_OUTER_POLYNOMIAL_BOX",
        "equilibrium_scope":"ONE_POSITIVE_EQUILIBRIUM_AND_NO_OTHER_NONNEGATIVE_EQUILIBRIUM_UNDER_DECLARED_FIXED_LOSS_LAW",
        "scope":SCOPE,"limitations":deepcopy(LIMITATIONS)}


def _failure(exc,c,verify=False):
    if c is not None and exc is c.external:raise exc
    return {"status":"UNKNOWN" if isinstance(exc,bounded._BudgetExceeded) else "FAIL" if verify else "BLOCKED",
        "verdict":"UNKNOWN","reason":str(exc),"scope":SCOPE,"proof_complete":False,"work":0 if c is None else c.used,
        "limitations":deepcopy(LIMITATIONS)}


def _limits(model,c,max_work,max_bytes):
    leaves=len(model["leaves"]);terms=len(model["terms"])
    return {"max_leaves":leaves,"max_terms":min(512,terms),"max_work":max_work,"max_input_bytes":min(max_bytes,8_388_608),
            "max_certificate_bytes":max_bytes}


def _tail_snapshot_work(values,c):
    """Exact tick denominator of the math kernels' callback-free hash tails.

    Successful producer certificates do not expose their work count. Their
    final tails are strict JSON snapshots, with one tick per structural value,
    encoder chunk and completion. Count those units; count our own traversal
    too. Inputs have already passed the strict bounded math parser.
    """
    total=0
    for value in values:
        pending=[value]
        while pending:
            item=pending.pop();c.tick("coupled_tree_tail_accounting_shape");total+=1
            if type(item) is dict:
                pending.extend(item.keys());pending.extend(item.values())
            elif type(item) is list:pending.extend(item)
        for _ in json.JSONEncoder(sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).iterencode(value):
            c.tick("coupled_tree_tail_accounting_stream");total+=1
        c.tick("coupled_tree_tail_accounting_complete");total+=1
    return total


def _invoke(c,function,*args,tail_inputs=(),**kwargs):
    remaining=c.maximum-c.used
    if remaining<=0:raise bounded._BudgetExceeded("ADAPTER_WORK_BUDGET")
    forwarded=0
    def pulse(stage):
        nonlocal forwarded
        forwarded+=1;c.tick(stage)
    kwargs["checkpoint"]=pulse;kwargs["max_work"]=min(kwargs["max_work"],remaining)
    result=function(*args,**kwargs)
    if type(result.get("work")) is int:
        missing=max(0,result["work"]-forwarded)
    elif result.get("status") in ("CERTIFIED_BOX","CERTIFIED_UNIVALENCE"):
        missing=_tail_snapshot_work(tail_inputs,c)
    else:missing=0
    c.used+=missing
    if c.used>c.maximum:raise bounded._BudgetExceeded("ADAPTER_WORK_BUDGET")
    return result


def _checked_proofs(model,box,local_certificate,univalence_certificate,c,max_work,max_bytes):
    limits=_limits(model,c,max_work,max_bytes)
    local_check=_invoke(c,local.verify_coupled_tree_pressure,model,box,local_certificate,max_matrix_entries=len(model["leaves"])**2,**limits)
    if local_check.get("status")!="PASS":return local_check,None
    global_check=_invoke(c,global_proof.verify_coupled_tree_univalence,model,univalence_certificate,**limits)
    if global_check.get("status")=="PASS":
        if local_check["model_root"]!=global_check["model_root"] or local_certificate["parameter_root"]!=global_check["parameter_root"]:
            raise ValueError("Local existence and global uniqueness refer to different full parameter models")
    return local_check,global_check


def _no_proof(reason,**checks):
    return {"status":"UNKNOWN","verdict":"UNKNOWN","proof_complete":False,"scope":SCOPE,"reason":reason,
            "limitations":deepcopy(LIMITATIONS),**checks}


def verify_coupled_tree_envelope(boundary,network,native_metrics,certificate,*,context,max_components=128,
        max_work=2_000_000,max_bytes=16_777_216,checkpoint=None):
    c=None
    try:
        c=_Control(checkpoint,max_work,max_bytes);original=_raw(boundary,network,native_metrics,context);_shape(original,max_components)
        root,raw=bounded._snapshot(original,c,"coupled_tree_input")
        cert_root,packet=bounded._snapshot(certificate,c,"coupled_tree_certificate")
        n=_normalize(raw,c,max_components);model,box,derivation=_build(n,c,checked=True)
        if type(packet) is not dict or set(packet)!={"schema","input_root","model","flow_box","derivation","local_certificate","univalence_certificate","service","certificate_root"}:
            raise ValueError("Complete unequal native tree certificate required")
        if packet["schema"]!=CERTIFICATE_SCHEMA or packet["input_root"]!=root:
            raise ValueError("Unequal native tree certificate identity differs")
        for key,value in (("model",model),("flow_box",box),("derivation",derivation)):
            if _hash(packet[key],c)!=_hash(value,c):raise ValueError("Forged complete physical model/metric/path/rounding field: "+key)
        if bounded._root(packet["certificate_root"])!=_hash({k:v for k,v in packet.items() if k!="certificate_root"},c):
            raise ValueError("Unequal native tree certificate content root differs")
        local_check,global_check=_checked_proofs(model,box,packet["local_certificate"],packet["univalence_certificate"],c,max_work,max_bytes)
        if local_check.get("status")!="PASS" or global_check is None or global_check.get("status")!="PASS":
            result=_no_proof("Independent local and global equilibrium proofs are both mandatory",local_check=local_check,global_check=global_check)
            if local_check.get("status")=="FAIL" or (global_check is not None and global_check.get("status")=="FAIL"):
                result["status"]="FAIL"
            return result
        service=_service(n,model,derivation,local_check,global_check,c)
        if _hash(packet["service"],c)!=_hash(service,c):raise ValueError("Forged physical port/flow/pressure/velocity/delivery/continuity report")
        c.tick("coupled_tree_verifier_complete");_finish(boundary,network,native_metrics,context,root,c,certificate,cert_root)
        return {"status":"PASS","verdict":service["verdict"],"scope":SCOPE,"proof_complete":True,"input_root":root,
            "certificate_root":packet["certificate_root"],"model_root":local_check["model_root"],"local_check":local_check,"global_check":global_check,
            "service":service,"counts":derivation["counts"],"work":c.used,"native_geometry_acceptance_authority":False,"limitations":deepcopy(LIMITATIONS)}
    except (ValueError,TypeError,KeyError,OverflowError,bounded._BudgetExceeded) as exc:
        return _failure(exc,c,True)


def evaluate_coupled_tree(boundary,network,native_metrics,*,context,max_components=128,max_work=2_000_000,max_bytes=16_777_216,checkpoint=None):
    c=None
    try:
        c=_Control(checkpoint,max_work,max_bytes);original=_raw(boundary,network,native_metrics,context);_shape(original,max_components)
        root,raw=bounded._snapshot(original,c,"coupled_tree_input")
        n=_normalize(raw,c,max_components);model,box,derivation=_build(n,c)
        limits=_limits(model,c,max_work,max_bytes)
        univalence_certificate=_invoke(c,global_proof.compile_coupled_tree_univalence,model,tail_inputs=(model,),**limits)
        if univalence_certificate.get("status")!="CERTIFIED_UNIVALENCE":
            return _no_proof("Global uniqueness premise/certificate is unavailable; box cannot hide other equilibria",global_producer=univalence_certificate)
        local_certificate=_invoke(c,local.compile_coupled_tree_pressure,model,box,tail_inputs=({"model":model,"flow_box":box},),
                                  max_matrix_entries=len(model["leaves"])**2,**limits)
        if local_certificate.get("status")!="CERTIFIED_BOX":return _no_proof("Local positive-box existence was not established",local_producer=local_certificate)
        local_check,global_check=_checked_proofs(model,box,local_certificate,univalence_certificate,c,max_work,max_bytes)
        if local_check.get("status")!="PASS" or global_check is None or global_check.get("status")!="PASS":
            return _no_proof("Independent local/global proof checks did not pass",local_check=local_check,global_check=global_check)
        service=_service(n,model,derivation,local_check,global_check,c)
        packet={"schema":CERTIFICATE_SCHEMA,"input_root":root,"model":model,"flow_box":box,"derivation":derivation,
            "local_certificate":local_certificate,"univalence_certificate":univalence_certificate,"service":service}
        packet["certificate_root"]=_hash(packet,c)
        independent=_invoke(c,verify_coupled_tree_envelope,raw["boundary"],raw["network"],raw["native_metrics"],packet,context=raw["context"],
            max_components=max_components,max_work=max_work,max_bytes=max_bytes)
        if independent.get("status")!="PASS":return _no_proof("Independent full physical derivation/service proof did not pass",independent_check=independent)
        c.tick("coupled_tree_producer_complete");_finish(boundary,network,native_metrics,context,root,c)
        return {"status":"CERTIFIED_ENVELOPE","verdict":independent["verdict"],"proof_complete":True,"scope":SCOPE,
            "certificate":packet,"independent_check":independent,"service":independent["service"],"work":c.used,"limitations":deepcopy(LIMITATIONS)}
    except (ValueError,TypeError,KeyError,OverflowError,bounded._BudgetExceeded) as exc:
        return _failure(exc,c)
