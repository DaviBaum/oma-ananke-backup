"""Certified residual-to-error bounds on bounded grounded passive graphs.

Original P6 PO14/PO7 and P5 ER22. Conductance/path stability is checked;
residuals alone never constitute a pressure error or physical validity proof.
"""
from copy import deepcopy
from fractions import Fraction as Q

from . import passive_pressure as p

SCHEMA = "oma.passive-residual-error-certificate/1"
SCOPE = "UNIFORM_BOUNDED_PASSIVE_GRAPH_RESIDUAL_TO_PRESSURE_AND_FLOW_FAMILY_ERROR"
ASSUMPTIONS = {
    "comparison_internal_heads": "FIXED_SUPPLIED_RATIONAL_VECTOR_WITHIN_COMPONENT_BOUNDARY_HULL",
    "comparison_boundary_heads": "SAME_ACTUAL_DIRICHLET_PARAMETER_TUPLE_AS_THE_EQUILIBRIUM",
    "approximate_flows": "PARAMETERIZED_SIGNED_ROOT_FAMILY_AT_COMPARISON_HEADS",
    "stability": "BOUNDED_DROP_CONDUCTANCES_AND_COMPLETE_GROUNDING_PATHS",
    "flow_error": "SIGNED_SQRT_HOLDER_WITH_ZERO_CROSSING_FACTOR_TWO",
}
LIMITATIONS = {"native_or_physical_model_authority": False, "pure_numerical_solver_error_isolated": False,
    "one_numeric_approximate_flow_for_all_parameters": False, "global_unbounded_domain_strong_monotonicity": False,
    "tight_solution_hull": False, "full_source_algorithm_implemented": False}


def _raw(model, heads, target):
    return {"model": model, "internal_heads": heads, "pressure_error_target": target}


def _path_limit(value):
    if type(value) is not int or not 0 <= value <= 1_000_000:
        raise p._Invalid("Invalid total path-step budget")
    return value


def _input_shape(raw, b):
    if type(raw) is not dict or set(raw) != {"model", "internal_heads", "pressure_error_target"}:
        raise p._Invalid("Complete residual query required")
    p._model_shape(raw["model"], b)
    if type(raw["internal_heads"]) is not dict:
        raise p._Invalid("Exact complete internal approximation map required")
    if len(raw["internal_heads"]) > b.nodes:
        raise p._Limit("NODE_BUDGET")


def _normalize(raw, b):
    _input_shape(raw,b)
    m=p._normalize(raw["model"],None,b)
    if set(raw["internal_heads"]) != set(m["internal"]):
        raise p._Invalid("Approximation must cover every internal node exactly")
    x={v:p._q(raw["internal_heads"][v],b) for v in m["internal"]}
    for v,value in x.items():
        if not m["spans"][v][0] <= value <= m["spans"][v][1]:
            raise p._Invalid("Approximation outside component boundary hull")
    target=None if raw["pressure_error_target"] is None else p._q(raw["pressure_error_target"],b)
    if target is not None and target < 0:
        raise p._Invalid("Negative pressure-error target")
    header={"schema":SCHEMA,"status":"CERTIFIED_BOUND","scope":SCOPE,
        **{key:deepcopy(m["header"][key]) for key in ("model_root","topology_root","domain_root","context_root","physical_model_root","counts","components")},
        "approximation":{v:str(value) for v,value in x.items()},"pressure_error_target":None if target is None else str(target),
        "assumptions":deepcopy(ASSUMPTIONS),"limitations":deepcopy(LIMITATIONS)}
    header["query_root"]=p._hash(header,b)
    return m,x,target,header


def _certificate_shape(c,b,max_steps):
    if type(c) is not dict:
        raise p._Invalid("Explicit residual certificate required")
    for key,limit in (("conductances",b.edges),("grounding_paths",b.nodes),("approximate_flow_edges",b.edges),
        ("residuals",b.nodes),("pressure_bounds",b.nodes),("solution_flow_edges",b.edges),("flow_error_bounds",b.edges),("components",b.nodes)):
        rows=c.get(key)
        if type(rows) is not list:
            raise p._Invalid("Complete certificate array required: "+key)
        if len(rows)>limit:
            raise p._Limit("CERTIFICATE_COUNT_BUDGET")
    total=0
    for row in c["grounding_paths"]:
        if type(row) is not dict or type(row.get("edges")) is not list or type(row.get("nodes")) is not list:
            raise p._Invalid("Explicit path node and edge lists required")
        if len(row["nodes"])>b.nodes or len(row["edges"])>b.nodes:
            raise p._Limit("PATH_LENGTH_BUDGET")
        total+=len(row["edges"])
        if total>max_steps:
            raise p._Limit("PATH_STEP_BUDGET")


def _make_conductances(m,bits,b):
    rows,values=[],{}
    for name,u,v,k in m["edges"]:
        b.tick("residual_producer_conductance")
        span=b.sub(*reversed(m["spans"][u]))
        if span==0:
            value=None
        else:
            root=p._sqrt(b.mul(k[1],span),bits,b)
            value=b.div(Q(1),b.mul(Q(2),root[1]))
        rows.append({"edge":name,"span":str(span),"lower":None if value is None else str(value)})
        values[name]=value
    return rows,values


def _check_conductances(m,rows,b):
    if len(rows)!=len(m["edges"]):
        raise p._Invalid("Incomplete conductance denominator")
    values={}
    for (name,u,v,k),row in zip(m["edges"],rows):
        b.tick("residual_check_conductance")
        if type(row) is not dict or set(row)!={"edge","span","lower"} or row["edge"]!=name:
            raise p._Invalid("Conductance edge identity mismatch")
        span=b.sub(m["spans"][u][1],m["spans"][u][0])
        if p._q(row["span"],b)!=span:
            raise p._Invalid("Forged component head span")
        if span==0:
            if row["lower"] is not None:
                raise p._Invalid("Constant component requires its exact-zero branch")
            values[name]=None
        else:
            value=p._q(row["lower"],b)
            product=b.mul(b.mul(b.mul(Q(4),b.mul(value,value)),k[1]),span)
            if value<=0 or product>1:
                raise p._Invalid("Unproved bounded-domain conductance")
            values[name]=value
    return values


def _make_paths(m,conductance,max_steps,b):
    rows,total=[],0
    for start in m["internal"]:
        if m["spans"][start][0]==m["spans"][start][1]:
            nodes,edges,mode=[start],[],"EXACT_CONSTANT_COMPONENT"
        else:
            todo=[start];previous={start:None};goal=None
            while todo:
                b.tick("residual_producer_path_search")
                current=todo.pop(0)
                if current in m["boundary"]:
                    goal=current;break
                for edge,nxt in sorted(m["adjacency"][current]):
                    if nxt not in previous:
                        previous[nxt]=(current,edge);todo.append(nxt)
            if goal is None:
                raise p._Invalid("No grounding path")
            nodes,edges=[goal],[]
            while nodes[-1]!=start:
                current,edge=previous[nodes[-1]]
                nodes.append(current);edges.append(edge)
            nodes.reverse();edges.reverse();mode="GROUNDED_POSITIVE_CONDUCTANCE"
        total+=len(edges)
        if total>max_steps:
            raise p._Limit("PATH_STEP_BUDGET")
        resistance=Q(0)
        for edge in edges:
            resistance=b.add(resistance,b.div(Q(1),conductance[edge]))
        rows.append({"node":start,"mode":mode,"nodes":nodes,"edges":edges,"resistance_sum":str(resistance)})
    return rows


def _check_paths(m,conductance,rows,b):
    if len(rows)!=len(m["internal"]):
        raise p._Invalid("Incomplete internal grounding-path denominator")
    endpoints={name:{u,v} for name,u,v,_ in m["edges"]}
    sigma=Q(0)
    for start,row in zip(m["internal"],rows):
        b.tick("residual_check_grounding_path")
        if type(row) is not dict or set(row)!={"node","mode","nodes","edges","resistance_sum"} or row["node"]!=start:
            raise p._Invalid("Grounding path identity mismatch")
        vertices,edges=row["nodes"],row["edges"]
        if m["spans"][start][0]==m["spans"][start][1]:
            if row["mode"]!="EXACT_CONSTANT_COMPONENT" or vertices!=[start] or edges:
                raise p._Invalid("Wrong constant-component path branch")
            resistance=Q(0)
        else:
            if row["mode"]!="GROUNDED_POSITIVE_CONDUCTANCE" or not vertices or vertices[0]!=start or vertices[-1] not in m["boundary"]:
                raise p._Invalid("Path does not ground its internal node")
            if any(type(v) is not str for v in vertices) or len(set(vertices))!=len(vertices) or len(vertices)!=len(edges)+1:
                raise p._Invalid("Grounding path must be simple and complete")
            resistance=Q(0)
            for u,v,edge in zip(vertices,vertices[1:],edges):
                b.tick("residual_check_path_edge")
                if type(edge) is not str or endpoints.get(edge)!={u,v} or conductance[edge] is None:
                    raise p._Invalid("Grounding step is not a positive actual edge")
                resistance=b.add(resistance,b.div(Q(1),conductance[edge]))
        if p._q(row["resistance_sum"],b)!=resistance:
            raise p._Invalid("Forged path resistance sum")
        sigma=b.add(sigma,resistance)
    return sigma


def _residual_rows(m,flows,b,checked=False):
    sums=p._checked_divergences(m,flows,b) if checked else {v:p._producer_residual(m,flows,v,b) for v in m["internal"]}
    rows,squared=[],Q(0)
    for v in m["internal"]:
        interval=sums[v];absolute=max(abs(interval[0]),abs(interval[1]))
        squared=b.add(squared,b.mul(absolute,absolute))
        rows.append({"node":v,"residual":p._enc(interval),"absolute_upper":str(absolute)})
    return rows,squared


def _pressure_bounds(m,x,error,b):
    bounds,errors={},{}
    for v in m["nodes"]:
        b.tick("residual_pressure_error")
        if v in m["boundary"]:
            bounds[v],errors[v]=m["boundary"][v],Q(0)
        elif m["spans"][v][0]==m["spans"][v][1]:
            bounds[v],errors[v]=m["spans"][v],Q(0)
        else:
            errors[v]=error
            bounds[v]=(max(m["spans"][v][0],b.sub(x[v],error)),min(m["spans"][v][1],b.add(x[v],error)))
    rows=[{"node":v,**p._enc(bounds[v]),"coordinate_error_upper":str(errors[v])} for v in m["nodes"]]
    return rows,bounds,errors


def _flow_rows(m,hat,solution,errors,sqrt_rows,b,bits=None):
    rows=[]
    if sqrt_rows is not None and len(sqrt_rows)!=len(m["edges"]):
        raise p._Invalid("Incomplete flow-error denominator")
    for i,(name,u,v,k) in enumerate(m["edges"]):
        b.tick("residual_flow_family_error")
        drop_error=b.add(errors[u],errors[v])
        radicand=b.div(b.mul(Q(2),drop_error),k[0])
        if sqrt_rows is None:
            root=p._sqrt(radicand,bits,b)
        else:
            row=sqrt_rows[i]
            if type(row) is not dict or set(row)!={"edge","drop_error_upper","sqrt_error","flow_error_upper","flow_enclosure"} or row["edge"]!=name:
                raise p._Invalid("Flow-error edge identity mismatch")
            root=p._check_sqrt(row["sqrt_error"],radicand,b)
        widened=(b.sub(hat[name][0],root[1]),b.add(hat[name][1],root[1]))
        interval=(max(widened[0],solution[name][0]),min(widened[1],solution[name][1]))
        if interval[0]>interval[1]:
            raise p._Invalid("Inconsistent flow enclosures")
        rows.append({"edge":name,"drop_error_upper":str(drop_error),"sqrt_error":p._enc(root),
            "flow_error_upper":str(root[1]),"flow_enclosure":p._enc(interval)})
    return rows


def _equal(left,right,b,message):
    if p._hash(left,b)!=p._hash(right,b):
        raise p._Invalid(message)


def _final_guard(model,heads,target,input_root,b,certificate=None,certificate_hash=None):
    b.callback=None
    if p._snapshot(_raw(model,heads,target),b.input_bytes,b,"passive_input",retain=False)[0]!=input_root:
        raise p._Invalid("Caller model/approximation/target changed before completion")
    if certificate is not None and p._snapshot(certificate,b.certificate_bytes,b,"residual_certificate",retain=False)[0]!=certificate_hash:
        raise p._Invalid("Caller residual certificate changed before completion")


def _fail(exc,b,verify=False):
    if b is not None and exc is b.external_error:
        raise exc
    return {"status":"UNKNOWN" if isinstance(exc,p._Limit) else "FAIL" if verify else "INVALID_INPUT",
        "reason":str(exc),"scope":SCOPE,"proof_complete":False,"work":0 if b is None else b.used,"limitations":deepcopy(LIMITATIONS)}


def compile_passive_residual(model,internal_heads,*,pressure_error_target=None,max_nodes=64,max_edges=128,
        max_path_steps=4096,max_work=2_000_000,sqrt_bits=96,max_rational_bits=4096,
        max_input_bytes=1_048_576,max_certificate_bytes=16_777_216,checkpoint=None):
    b=None
    try:
        b=p._Budget(max_nodes,max_edges,max_work,max_rational_bits,max_input_bytes,max_certificate_bytes,checkpoint)
        _path_limit(max_path_steps)
        if type(sqrt_bits) is not int or not 8<=sqrt_bits<=512 or 2*sqrt_bits>max_rational_bits:
            raise p._Invalid("Invalid radical precision")
        raw=_raw(model,internal_heads,pressure_error_target);_input_shape(raw,b)
        input_root,frozen=p._snapshot(raw,b.input_bytes,b,"passive_input")
        m,x,target,header=_normalize(frozen,b)
        conductance_rows,conductance=_make_conductances(m,sqrt_bits,b)
        paths=_make_paths(m,conductance,max_path_steps,b)
        sigma=_check_paths(m,conductance,paths,b)
        hat_rows,hat=p._producer_edges(m,p._pressures(m,x),sqrt_bits,b)
        residuals,squared=_residual_rows(m,hat,b)
        norm=p._sqrt(squared,sqrt_bits,b)
        error=b.mul(sigma,norm[1])
        pressure_rows,pressure,errors=_pressure_bounds(m,x,error,b)
        solution_rows,solution=p._producer_edges(m,pressure,sqrt_bits,b)
        flow_rows=_flow_rows(m,hat,solution,errors,None,b,sqrt_bits)
        packet={**header,"conductances":conductance_rows,"grounding_paths":paths,"sigma_head_per_flow":str(sigma),
            "approximate_flow_edges":hat_rows,"residuals":residuals,"residual_squared_norm_upper":str(squared),
            "residual_norm":p._enc(norm),"pressure_l2_error_upper":str(error),"pressure_bounds":pressure_rows,
            "solution_flow_edges":solution_rows,"flow_error_bounds":flow_rows,
            "target_accuracy_met":None if target is None else error<=target}
        packet["certificate_root"]=p._hash(packet,b)
        _certificate_shape(packet,b,max_path_steps)
        b.tick("residual_producer_complete")
        _final_guard(model,internal_heads,pressure_error_target,input_root,b)
        return packet
    except (p._Invalid,p._Limit,ValueError,TypeError,KeyError,OverflowError) as exc:
        return _fail(exc,b)


def verify_passive_residual(model,internal_heads,certificate,*,pressure_error_target=None,max_nodes=64,max_edges=128,
        max_path_steps=4096,max_work=2_000_000,max_rational_bits=4096,max_input_bytes=1_048_576,
        max_certificate_bytes=16_777_216,checkpoint=None):
    b=None
    try:
        b=p._Budget(max_nodes,max_edges,max_work,max_rational_bits,max_input_bytes,max_certificate_bytes,checkpoint)
        _path_limit(max_path_steps)
        raw=_raw(model,internal_heads,pressure_error_target);_input_shape(raw,b);_certificate_shape(certificate,b,max_path_steps)
        input_root,frozen=p._snapshot(raw,b.input_bytes,b,"passive_input")
        certificate_hash,packet=p._snapshot(certificate,b.certificate_bytes,b,"residual_certificate")
        _certificate_shape(packet,b,max_path_steps)
        m,x,target,header=_normalize(frozen,b)
        fields={"conductances","grounding_paths","sigma_head_per_flow","approximate_flow_edges","residuals",
            "residual_squared_norm_upper","residual_norm","pressure_l2_error_upper","pressure_bounds",
            "solution_flow_edges","flow_error_bounds","target_accuracy_met","certificate_root"}
        if set(packet)!=set(header)|fields:
            raise p._Invalid("Incomplete or extra residual proof fields")
        _equal({k:packet[k] for k in header},header,b,"Residual query/model/domain/header mismatch")
        if type(packet["certificate_root"]) is not str or not p._ROOT.fullmatch(packet["certificate_root"]):
            raise p._Invalid("Invalid residual content root")
        _equal(packet["certificate_root"],p._hash({k:v for k,v in packet.items() if k!="certificate_root"},b),b,"Residual content root mismatch")
        conductance=_check_conductances(m,packet["conductances"],b)
        sigma=_check_paths(m,conductance,packet["grounding_paths"],b)
        if p._q(packet["sigma_head_per_flow"],b)!=sigma:
            raise p._Invalid("Forged complete path coercivity sum")
        hat=p._checked_edges(m,p._pressures(m,x),packet["approximate_flow_edges"],b)
        residuals,squared=_residual_rows(m,hat,b,checked=True)
        _equal(packet["residuals"],residuals,b,"Residual differs from complete signed incidence")
        if p._q(packet["residual_squared_norm_upper"],b)!=squared:
            raise p._Invalid("Forged uniform squared residual norm")
        norm=p._check_sqrt(packet["residual_norm"],squared,b)
        error=b.mul(sigma,norm[1])
        if p._q(packet["pressure_l2_error_upper"],b)!=error:
            raise p._Invalid("Error not backed by residual and path stability")
        rows,pressure,errors=_pressure_bounds(m,x,error,b)
        _equal(packet["pressure_bounds"],rows,b,"Pressure box or coordinate error differs")
        solution=p._checked_edges(m,pressure,packet["solution_flow_edges"],b)
        flow_rows=_flow_rows(m,hat,solution,errors,packet["flow_error_bounds"],b)
        _equal(packet["flow_error_bounds"],flow_rows,b,"Flow family error or absolute enclosure differs")
        _equal(packet["target_accuracy_met"],None if target is None else error<=target,b,"False target accuracy")
        b.tick("residual_verifier_complete")
        _final_guard(model,internal_heads,pressure_error_target,input_root,b,certificate,certificate_hash)
        return {"status":"PASS","scope":SCOPE,"proof_complete":True,"certificate_root":packet["certificate_root"],
            "model_root":header["model_root"],"query_root":header["query_root"],"counts":deepcopy(header["counts"]),
            "pressure_l2_error_upper":str(error),"sigma_head_per_flow":str(sigma),"residual_norm":p._enc(norm),
            "pressure_bounds":deepcopy(rows),"flow_error_bounds":deepcopy(flow_rows),"target_accuracy_met":packet["target_accuracy_met"],
            "flow_reference":"PARAMETERIZED_APPROXIMATE_FAMILY_USING_ACTUAL_BOUNDARY_TUPLE","work":b.used,"limitations":deepcopy(LIMITATIONS)}
    except (p._Invalid,p._Limit,ValueError,TypeError,KeyError,OverflowError) as exc:
        return _fail(exc,b,True)
