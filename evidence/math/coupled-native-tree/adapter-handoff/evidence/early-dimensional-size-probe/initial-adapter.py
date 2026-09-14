"""Native-metric specialization of unequal, total-inlet-flow tee losses.

No native authenticity or existing mission interpretation is conferred here.
Complete physical path reconstruction feeds separate local and global proofs.
"""
from copy import deepcopy
from fractions import Fraction as Q
import hashlib
import json

from oma.optimization import coupled_tree_pressure as local
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
                      else rho*factor/(2*area.square()))
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
            coefficients[aid]=_enc(losses[(cid,outlet)])
            term_physics.append({"term_id":tid,"coefficient_id":aid,"component":cid,"outlet":outlet,
                "flow_reference":"COMPLETE_COMPONENT_INLET_DESCENDANTS","applies_to_leaves":sorted(applied),
                "descendant_leaves":sorted(desc[cid]),"tee_darcy_charged":False})
    boundary,net=n["boundary"],n["network"]
    rho,g=Q(boundary.density_kg_m3),Q(boundary.gravity_m_s2)
    source_pressure=_interval(boundary.source_total_pressure_pa.model_dump())
    source_head=source_pressure+rho*g*n["positions"][net.source.key()][2]
    heads={sid:_enc(source_head-_interval(boundary.sink_total_pressures_pa[sid].model_dump())-rho*g*n["positions"][sink.endpoint.key()][2])
           for sid,sink in sorted(n["sinks"].items())}
    box={sid:interval.model_dump() for sid,interval in sorted(boundary.flow_search_box_m3_s.items())}
    port_paths=[{"component":cid,"port":port,"descendant_leaves":sorted(desc[cid] if port=="a" else outlets[(cid,port)]),
                 "loss_terms":prefixes[(cid,port)]} for cid,port in sorted(prefixes)]
    derivation={"schema":"oma.coupled-tree-native-derivation/1","network_root":n["raw"]["native_metrics"]["network_root"],
        "native_evidence_root":n["raw"]["native_metrics"]["native_evidence_root"],"metric_root":_hash(n["raw"]["native_metrics"],c),
        "boundary_root":_hash(boundary.model_dump(mode="json",by_alias=True),c),
        "component_sections":sections,"term_physics":term_physics,"port_paths":port_paths,
        "sink_paths":paths,"component_descendants":{cid:sorted(v) for cid,v in sorted(desc.items())},
        "source_total_head_pa":_enc(source_head),"available_heads_pa":heads,
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
