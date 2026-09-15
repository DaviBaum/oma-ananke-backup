"""Independent supplied-catalogue provenance check, not a native feasibility test.

Shares only field normalization and the existing independent fabrication verifier.
Never calls the catalogue producer, its template/conversion/cost helpers, or CAD.
"""
from fractions import Fraction as Q
from decimal import Decimal, InvalidOperation
import hashlib
import itertools
import json
import math
import re

from oma.routing.shared_tree_requirements import normalize_shared_tree_requirements
from oma.routing.scenario import RoutingScenario
from oma.optimization.fabrication import verify_orthogonal_fabrication

SCHEMA = "oma.shared-tree-generated-catalogue-check/1"
SEARCH_SCHEMA = "oma.shared-tree-native-search/1"
SCOPE = "SUPPLIED_CATALOGUE_CURRENT_INPUT_TEMPLATE_MEMBERSHIP_AND_NOMINAL_MACRO_PROVENANCE_ONLY"
LIMITATIONS = {
    "continuous_or_all_topologies_complete": False,
    "native_geometry_or_service_checked": False,
    "nominal_cost_is_native_lower_bound": False,
    "physical_infeasibility_from_empty_catalogue": False,
    "candidate_acceptance_authority": False,
    "coordinates": "EXACT_BINARY64_REPRESENTABLE_DYADIC_PROPOSAL_GEOMETRY",
}
_ID = re.compile(r"[A-Za-z0-9_.-]{1,100}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_RATIONAL = re.compile(r"-?[0-9]+(?:/[0-9]+)?\Z")
_RAW_RATIONAL = re.compile(r"[+-]?[0-9]+(?:/[0-9]+)?\Z")
_RAW_DECIMAL = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")


class _Limit(Exception):
    pass


class _External(BaseException):
    def __init__(self, error): self.error = error


class _Control:
    def __init__(self, maximum, callback):
        self.maximum, self.work, self.callback, self.pending = maximum, 0, callback, 0

    def pulse(self, stage):
        if self.callback is not None:
            try: self.callback(stage)
            except BaseException as error: raise _External(error) from error

    def use(self, amount=1, *, callbacks=True):
        self.work += amount
        self.pending += amount
        if self.work > self.maximum: raise _Limit("WORK_BUDGET")
        if callbacks and self.pending >= 128:
            self.pending = 0
            self.pulse("shared_tree_catalogue_check_work")


def _keys(value, expected):
    if type(value) is not dict or len(value) != len(expected) or set(value) != set(expected):
        raise ValueError("Complete exact field inventory required")


def _snapshot(value, control, maximum, *, callbacks=True):
    size = 0
    def encoded(v): return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    def charge(n):
        nonlocal size
        size += n
        if size > maximum: raise _Limit("BYTE_BUDGET")
    def walk(v, depth):
        control.use(callbacks=callbacks)
        if depth > 32: raise _Limit("STRUCTURE_BUDGET")
        if type(v) is dict:
            if len(v) > 4096: raise _Limit("STRUCTURE_BUDGET")
            if any(type(k) is not str or len(k)>256 for k in v): raise ValueError("Bounded JSON keys required")
            charge(2 + max(0, len(v)-1))
            result={}
            for key in sorted(v):
                charge(len(encoded(key))+1)
                result[key]=walk(v[key],depth+1)
            return result
        if type(v) is list:
            if len(v)>20000: raise _Limit("STRUCTURE_BUDGET")
            charge(2+max(0,len(v)-1))
            return [walk(x,depth+1) for x in v]
        if type(v) is str:
            if len(v)>65536: raise _Limit("STRING_BUDGET")
        elif type(v) is int:
            if v.bit_length()>512: raise _Limit("INTEGER_BUDGET")
        elif type(v) is float:
            if not math.isfinite(v): raise ValueError("Finite numeric fields required")
        elif type(v) is not bool and v is not None:
            raise ValueError("Strict JSON values required")
        charge(len(encoded(v)))
        return v
    result=walk(value,0)
    encoder=json.JSONEncoder(sort_keys=True,separators=(",", ":"),ensure_ascii=False,allow_nan=False)
    h=hashlib.sha256();actual=0
    for part in encoder.iterencode(result):
        control.use(callbacks=callbacks)
        raw=part.encode("utf-8");actual+=len(raw)
        if actual>maximum:raise _Limit("BYTE_BUDGET")
        h.update(raw)
    if actual!=size:raise ValueError("Canonical JSON byte accounting mismatch")
    return result,h.hexdigest()


def _digest(value, control, max_bytes): return _snapshot(value,control,max_bytes)[1]


def _identity(value):
    if type(value) is not str or not _ID.fullmatch(value): raise ValueError("Bounded identifier required")
    return value


def _root(value):
    if type(value) is not str or not _HEX.fullmatch(value): raise ValueError("Canonical SHA256 root required")
    return value


def _q(value):
    if type(value) not in (str,int,float) or (type(value) is str and len(value)>256):
        raise ValueError("Bounded rational/numeric field required")
    if type(value) is float and not math.isfinite(value): raise ValueError("Finite numeric field required")
    if type(value) is str:
        text=value.strip()
        if any(ch=='_' and (i==0 or i+1==len(text) or not text[i-1].isdigit() or not text[i+1].isdigit()) for i,ch in enumerate(text)):
            raise ValueError("Valid numeric underscore placement required")
        text=text.replace('_','')
        if _RAW_RATIONAL.fullmatch(text):
            if any(len(part.lstrip('+-'))>155 for part in text.split('/')):raise _Limit("RATIONAL_BUDGET")
            result=Q(text)
        else:
            # Decimal's compact exponent is inspected before Fraction can
            # allocate numerator/denominator powers for scientific notation.
            if not _RAW_DECIMAL.fullmatch(text):raise ValueError("Valid finite rational required")
            try:decimal=Decimal(text)
            except InvalidOperation as error:raise ValueError("Valid finite rational required") from error
            if not decimal.is_finite():raise ValueError("Finite rational required")
            parts=decimal.as_tuple()
            if len(parts.digits)>155 or abs(parts.exponent)>512:raise _Limit("RATIONAL_BUDGET")
            result=Q(decimal)
    else:result=Q(value)
    return _bounded(result)


def _bounded(value):
    if max(value.numerator.bit_length(),value.denominator.bit_length())>512:raise _Limit("RATIONAL_BUDGET")
    return value


def _binary(value):
    result=float(value)
    if not math.isfinite(result) or Q(result)!=value:raise _Limit("NONREPRESENTABLE_NATIVE_COORDINATE")
    return result


def _point(value):
    if type(value) is not list or len(value)!=3:raise ValueError("Three coordinates required")
    result=tuple(_q(x) for x in value)
    if max(map(abs,result))>1000000:raise _Limit("COORDINATE_DOMAIN")
    return result


def _axis(value):
    if type(value) is not list or len(value)!=3 or any(type(x) is not int for x in value) or sum(map(abs,value))!=1:
        raise ValueError("Exact signed unit flow direction required")
    return tuple(value)


def _plus(p,d,factor):return tuple(_bounded(x+factor*y) for x,y in zip(p,d))
def _cross(x,y):return (x[1]*y[2]-x[2]*y[1],x[2]*y[0]-x[0]*y[2],x[0]*y[1]-x[1]*y[0])
def _strings(p):return list(map(str,p))
def _floats(p):return list(map(_binary,p))
def _cap(p,u):return {"position_m":_strings(p),"flow_direction":list(u)}


def _direction(a,b):
    delta=tuple(_bounded(y-x) for x,y in zip(a,b))
    active=[i for i,x in enumerate(delta) if x]
    if len(active)!=1:raise ValueError("Nonzero orthogonal path legs required")
    axis=active[0]
    return tuple((1 if delta[axis]>0 else -1) if i==axis else 0 for i in range(3)),abs(delta[axis])


def _reduced_word(raw):
    """Independent reduction through oriented segment runs, not producer point popping."""
    runs=[]
    for a,b in zip(raw,raw[1:]):
        if a==b:continue
        direction,length=_direction(a,b)
        if runs and runs[-1][0]==direction:
            runs[-1]=(direction,_bounded(runs[-1][1]+length))
        else:runs.append((direction,length))
    if not runs:return [raw[0]]
    points=[raw[0]]
    for direction,length in runs:points.append(_plus(points[-1],direction,length))
    return points


def _template_member(points, start_axis, end_axis, stubs, planes, control):
    # Direct connector or one lead/tail stub pair, one optional plane, and one
    # permutation of coordinate replacements. This checks only this one word.
    start,end=points[0],points[-1]
    if points==[start,end]:return True
    for lead in stubs:
        for tail in stubs:
            first=_plus(start,start_axis,lead);last=_plus(end,end_axis,-tail)
            for plane in (None,*planes):
                aa,bb=list(first),list(last)
                if plane is not None:aa[plane[0]]=bb[plane[0]]=plane[1]
                aa,bb=tuple(aa),tuple(bb)
                changed=[i for i in range(3) if aa[i]!=bb[i]]
                for ordering in itertools.permutations(changed):
                    control.use(1+len(ordering))
                    chain=[start,first,aa]
                    current=list(aa)
                    for index in ordering:
                        current[index]=bb[index];chain.append(tuple(current))
                    chain.extend([last,end])
                    try:
                        if _reduced_word(chain)==points:return True
                    except ValueError:pass
    return False


def _scenario(r, start, end):
    return RoutingScenario.model_validate({
        "start":_floats(start),"end":_floats(end),"diameter_m":r["diameter_m"],
        "insulation_m":r["insulation_m"],"clearance_m":r["clearance_m"],
        "bend_radius_m":r["minimum_bend_radius_m"],"minimum_straight_m":r["minimum_straight_m"],
        "allowed_zone":r["allowed_zone"],"system_type":r["system_type"],"scenario_terminals":True,
        "target_modality":"LOCAL_GEOMETRIC_COORDINATION",
        "source_representation_policy":r["source_representation_policy"]})


def _components(points, identity, r, weights, control):
    """Reconstruct physical primitives directly from the polyline, never the certificate."""
    R=_q(r["minimum_bend_radius_m"]);radius=_bounded(_q(r["diameter_m"])/2+_q(r["insulation_m"]))
    minimum=max(_q(r["minimum_straight_m"]),Q(1e-9))
    directions=[];lengths=[]
    for a,b in zip(points,points[1:]):
        direction,length=_direction(a,b);directions.append(direction);lengths.append(length)
    if R<=radius:raise ValueError("Full insulated radius must be smaller than bend radius")
    for a,b in zip(directions,directions[1:]):
        if sum(x*y for x,y in zip(a,b))!=0:raise ValueError("Reduced quarter-turn word required")
    parts=[];straight=Q(0);elbows=0
    def part(kind,geometry):
        control.use()
        parts.append({"id":f"{identity}-p{len(parts)}","kind":kind,"system_type":r["system_type"],
            "diameter_m":r["diameter_m"],"insulation_m":r["insulation_m"],
            "ports":{"a":"SINK","b":"SOURCE"},"geometry":geometry})
    for i,u in enumerate(directions):
        before=R if i else Q(0);after=R if i+1<len(directions) else Q(0)
        remaining=_bounded(lengths[i]-before-after)
        if remaining<=minimum:raise ValueError("Strict finite straight-run fabrication debt failed")
        straight=_bounded(straight+remaining)
        a=_plus(points[i],u,before);b=_plus(points[i+1],u,-after)
        part("segment",{"start_m":_floats(a),"end_m":_floats(b)})
        if i+1<len(directions):
            v=directions[i+1];corner=points[i+1]
            a=_plus(corner,u,-R);b=_plus(corner,v,R);center=_plus(a,v,R)
            part("elbow",{"start_m":_floats(a),"end_m":_floats(b),"center_m":_floats(center),
                          "normal":_floats(_cross(u,v)),"bend_radius_m":_binary(R),"angle_rad":math.pi/2})
            elbows+=1
    cost=[str(_bounded(weights[0]*straight+weights[1]*elbows)),str(_bounded(weights[0]*R*elbows/2))]
    return parts,cost


def _fabrication_numeric_shape(certificate,control):
    """Bound rational witness fields before entering the legacy finite verifier."""
    def rational(value):
        control.use()
        if type(value) is not str or len(value)>256 or not _RATIONAL.fullmatch(value):
            raise ValueError("Canonical rational fabrication witness required")
        if str(_q(value))!=value:raise ValueError("Canonical rational fabrication witness required")
    def vector(value):
        if type(value) is not list or len(value)!=3:raise ValueError("Complete rational witness vector required")
        for item in value:rational(item)
    for part in certificate['components']:
        if type(part) is not dict or type(part.get('index')) is not int or not 0<=part['index']<16:
            raise ValueError("Bounded exact fabrication part index required")
        base={'kind','index','start','end','outer_radius_m','body_bounds_m'}
        if part.get('kind')=='segment':expected=base|{'length_m'}
        elif part.get('kind')=='elbow':expected=base|{'center','incoming','outgoing','normal','bend_radius_m','angle_pi','length_pi_m'}
        else:raise ValueError("Supported physical fabrication part required")
        _keys(part,expected)
        for name in ('start','end'):vector(part[name])
        rational(part['outer_radius_m'])
        bounds=part['body_bounds_m']
        if type(bounds) is not list or len(bounds)!=2:raise ValueError("Complete bounded body support witness required")
        for point in bounds:vector(point)
        if part['kind']=='segment':rational(part['length_m'])
        else:
            for name in ('center','incoming','outgoing','normal'):vector(part[name])
            for name in ('bend_radius_m','angle_pi','length_pi_m'):rational(part[name])
    for transition in certificate['transitions']:
        if type(transition) is not dict:raise ValueError("Complete transition witness required")
        for name in ('incoming','outgoing'):vector(transition[name])
        for name in ('trim_debt_m','incoming_remaining_straight_m'):rational(transition[name])


def _generated_shape(g,max_macros,max_attempts):
    _keys(g,{"status","input_root","catalogue","tee_components","normalized_requirements",
             "connector_macros","attempts","limitations","work"})
    if type(g["connector_macros"]) is not dict or len(g["connector_macros"])>max_macros:raise _Limit("MACRO_BUDGET")
    if type(g["tee_components"]) is not dict or len(g["tee_components"])>8:raise _Limit("TEE_BUDGET")
    if type(g["attempts"]) is not list or len(g["attempts"])>max_attempts:raise _Limit("ATTEMPT_BUDGET")


def verify_generated_catalogue(requirements, search, generated, *, context,
        max_work=2000000, max_bytes=16777216, max_macros=1024, max_attempts=20000, checkpoint=None):
    control=None
    try:
        for value,lo,hi in ((max_work,1,20000000),(max_bytes,1024,67108864),(max_macros,1,1024),(max_attempts,1,20000)):
            if type(value) is not int or not lo<=value<=hi:raise ValueError("Invalid checker resource bound")
        control=_Control(max_work,checkpoint)
        _generated_shape(generated,max_macros,max_attempts)
        originals={"requirements":requirements,"search":search,"context":context}
        control.pulse("shared_tree_catalogue_check_input")
        captured,input_root=_snapshot(originals,control,max_bytes)
        g,generated_root=_snapshot(generated,control,max_bytes)
        _generated_shape(g,max_macros,max_attempts)
        raw_r,s,c=(captured[k] for k in ("requirements","search","context"))
        if type(raw_r) is not dict or "network_alternatives" in raw_r:raise ValueError("Authored requirements cannot supply complete trees")
        r=normalize_shared_tree_requirements(raw_r)
        if any(r.get(k) is not None for k in ("pressure_driven","passive_tree")):
            raise _Limit("GENERATED_PRESSURE_TEE_IDENTITY_PROFILE_NOT_IMPLEMENTED")
        coupled=r.get("coupled_tree")
        boundary_root=None
        if coupled is not None:
            # Field normalization already applies the existing boundary parser;
            # replay it explicitly and preserve its complete canonical contract.
            from oma.routing.coupled_tree_scenario import CoupledTreeBoundary
            checked_boundary=CoupledTreeBoundary.model_validate(coupled).model_dump(mode="json",by_alias=True)
            if _digest(checked_boundary,control,max_bytes)!=_digest(coupled,control,max_bytes):
                raise ValueError("Current complete coupled boundary differs")
            if r.get("physics") is not None:
                raise ValueError("Coupled generation cannot coexist with fixed-flow physics")
            if r["system_type"]!="PRESSURE_PIPE" or r["target_modality"]!="ENGINEERING_SERVICE":
                raise ValueError("Coupled generation requires a pressure-pipe engineering-service mission")
            if any(sink.get("required_flow_m3_s") is not None or sink.get("available_static_pressure_pa") is not None for sink in r["sinks"]):
                raise ValueError("Exact coupled minimum deliveries belong only in the boundary")
            boundary_root=_digest(coupled,control,max_bytes)
        if type(c) is not dict or not c:raise ValueError("Complete current context required")
        _keys(s,{"schema","source_direction","sink_directions","tee_instances","stub_lengths_m","detour_planes"})
        if s["schema"]!=SEARCH_SCHEMA:raise ValueError("Unsupported search schema")
        if type(s["stub_lengths_m"]) is not list or not 1<=len(s["stub_lengths_m"])<=4:raise ValueError("Bounded nonempty authored stubs required")
        stubs=tuple(_q(x) for x in s["stub_lengths_m"])
        if min(stubs)<=0:raise ValueError("Positive stubs required")
        if type(s["detour_planes"]) is not list or len(s["detour_planes"])>8:raise _Limit("PLANE_BUDGET")
        planes=[]
        for plane in s["detour_planes"]:
            _keys(plane,{"axis","value_m"})
            if type(plane["axis"]) is not int or plane["axis"] not in (0,1,2):raise ValueError("Exact plane axis required")
            planes.append((plane["axis"],_q(plane["value_m"])))
        if len(r["sinks"]) not in (2,3):raise ValueError("Exactly two or three sinks required")
        sink_ids=[_identity(x["id"]) for x in r["sinks"]]
        demand_ids=[_identity(x["demand_id"]) for x in r["sinks"]]
        if len(set(sink_ids))!=len(sink_ids) or len(set(demand_ids))!=len(demand_ids) or "source" in sink_ids:
            raise ValueError("Complete distinct terminal identities required")
        if type(s["sink_directions"]) is not dict or set(s["sink_directions"])!=set(sink_ids):raise ValueError("Every sink direction must be fixed")
        weights=tuple(_q(r["objective_weights"].get(k,0)) for k in ("length_m","fitting_count"))
        if min(weights)<0 or not any(weights):raise ValueError("Nonnegative nonzero nominal objective required")
        source={"id":"source","cap":_cap(_point(r["start_m"]),_axis(s["source_direction"]))}
        terminal_rows=[{"id":x["id"],"demand_id":x["demand_id"],
            "cap":_cap(_point(x["end_m"]),_axis(s["sink_directions"][x["id"]]))} for x in r["sinks"]]
        section={"diameter_m":str(_q(r["diameter_m"])),"insulation_m":str(_q(r["insulation_m"]))}
        caps={("source","out"):source["cap"]}
        caps.update({(x["id"],"in"):x["cap"] for x in terminal_rows})
        if type(s["tee_instances"]) is not list or not 1<=len(s["tee_instances"])<=8:raise _Limit("TEE_BUDGET")
        if coupled is not None:
            if set(coupled["sink_total_pressures_pa"])!=set(sink_ids):
                raise ValueError("Every fixed sink must have the same exact coupled boundary identity")
            tee_ids=[]
            for tee in s["tee_instances"]:
                control.use()
                if type(tee) is not dict:raise ValueError("Complete fixed tee identity required")
                tee_ids.append(_identity(tee["id"]))
            if (len(tee_ids)!=len(sink_ids)-1 or len(set(tee_ids))!=len(tee_ids)
                    or set(tee_ids)!=set(coupled["tee_outlet_loss_coefficients"])):
                raise ValueError("All and only the n-1 fixed pressure tee IDs must be supplied once")
        tee_rows=[];tee_components={};node_ids={"source",*sink_ids}
        radius=_bounded(_q(r["diameter_m"])/2+_q(r["insulation_m"]))
        for tee in s["tee_instances"]:
            control.use()
            _keys(tee,{"id","center_m","axis_x","axis_y","trunk_takeout_m","branch_takeout_m"})
            identity=_identity(tee["id"])
            if identity in node_ids:raise ValueError("Unique tee/site identity required")
            node_ids.add(identity)
            center=_point(tee["center_m"]);x=_axis(tee["axis_x"]);y=_axis(tee["axis_y"])
            if sum(a*b for a,b in zip(x,y))!=0:raise ValueError("Proper signed-axis tee frame required")
            z=_cross(x,y);trunk=_q(tee["trunk_takeout_m"]);branch=_q(tee["branch_takeout_m"])
            if min(trunk,branch)<=radius:raise ValueError("Positive separate exterior tee caps required")
            frame=[[x[i],y[i],z[i],_binary(center[i])] for i in range(3)]+[[0,0,0,1]]
            component={"id":identity,"kind":"tee","system_type":r["system_type"],"diameter_m":r["diameter_m"],
                "insulation_m":r["insulation_m"],"ports":{"a":"SINK","b":"SOURCE","branch":"SOURCE"},
                "geometry":{"frame_m":frame,"trunk_takeout_m":_binary(trunk),"branch_takeout_m":_binary(branch)}}
            tee_components[identity]=component
            for port,axis,offset in (("a",x,-trunk),("b",x,trunk),("branch",y,branch)):
                position=_plus(center,axis,offset);_floats(position)
                caps[identity,port]=_cap(position,axis)
            loss_contract=(r.get("physics") if coupled is None else
                {"model":"oma.coupled-tree-boundary/1","tee_id":identity,
                 "outlet_coefficients":coupled["tee_outlet_loss_coefficients"][identity],"boundary_root":boundary_root})
            tee_rows.append({"id":identity,"center_m":_strings(center),"axis_x":list(x),"axis_y":list(y),
                "trunk_takeout_m":str(trunk),"branch_takeout_m":str(branch),
                "catalogue_root":_digest(component,control,max_bytes),"loss_contract_root":_digest(loss_contract,control,max_bytes),
                "nominal_cost":[str(_bounded(weights[0]*_bounded(2*trunk+branch)+weights[1])),"0"]})
        if g["status"]!="CATALOGUE_PROPOSED" or g["input_root"]!=input_root:raise ValueError("Current original-input provenance differs")
        if type(g["work"]) is not int or g["work"]<0:raise ValueError("Strict diagnostic work field required")
        if _digest(g["limitations"],control,max_bytes)!=_digest(LIMITATIONS,control,max_bytes):raise ValueError("Catalogue scope changed")
        if _digest(g["normalized_requirements"],control,max_bytes)!=_digest(r,control,max_bytes):raise ValueError("Normalized current requirements differ")
        if _digest(g["tee_components"],control,max_bytes)!=_digest(tee_components,control,max_bytes):raise ValueError("Complete current physical tee denominator/geometry differs")
        catalogue=g["catalogue"]
        _keys(catalogue,{"schema","context_root","source_roots","cost_policy_root","section","source","sinks","tee_instances","connectors"})
        header={"schema":"oma.shared-tree-catalogue/1","context_root":_digest(c,control,max_bytes),
            "source_roots":{"authored_requirements":_digest(raw_r,control,max_bytes),"normalized_requirements":_digest(r,control,max_bytes),"search":_digest(s,control,max_bytes)},
            "cost_policy_root":_digest({"weights":[str(w) for w in weights],"tee_length":"2*trunk_takeout+branch_takeout","fitting_count":"one_per_tee_or_elbow"},control,max_bytes),
            "section":section,"source":source,"sinks":terminal_rows,"tee_instances":tee_rows}
        if _digest({k:catalogue[k] for k in header},control,max_bytes)!=_digest(header,control,max_bytes):raise ValueError("Authored site/terminal/section/loss/context/cost inventory differs")
        if type(catalogue["connectors"]) is not list or len(catalogue["connectors"])>max_macros:raise _Limit("MACRO_BUDGET")
        rows={};definitions={};physical_ids=set(tee_components);component_count=len(physical_ids)
        for row in catalogue["connectors"]:
            control.use()
            _keys(row,{"id","from","to","start_cap","end_cap","section","geometry_root","fabrication_root","nominal_cost"})
            identity=_identity(row["id"])
            if identity in rows:raise ValueError("Duplicate connector identity")
            for endpoint in (row["from"],row["to"]):_keys(endpoint,{"node","port"})
            start=(row["from"]["node"],row["from"]["port"]);end=(row["to"]["node"],row["to"]["port"])
            if start not in caps or end not in caps or start[0]==end[0]:raise ValueError("Unknown/self cap reference")
            if not ((start==("source","out") and end[0] in tee_components and end[1]=="a") or
                    (start[0] in tee_components and start[1] in ("b","branch") and
                     ((end[0] in tee_components and end[1]=="a") or (end[0] in sink_ids and end[1]=="in")))):
                raise ValueError("Directed physical cap roles differ")
            if identity not in g["connector_macros"]:raise ValueError("Missing complete connector macro")
            macro=g["connector_macros"][identity];_keys(macro,{"geometry","certificate","independent_check"})
            geometry=macro["geometry"];_keys(geometry,{"points_m","components"})
            if type(geometry["points_m"]) is not list or not 2<=len(geometry["points_m"])<=16:raise _Limit("POINT_BUDGET")
            points=[_point(x) for x in geometry["points_m"]]
            path=[_strings(x) for x in points]
            if path!=geometry["points_m"]:raise ValueError("Canonical exact rational macro points required")
            for point in points:_floats(point)
            u,_=_direction(points[0],points[1]);v,_=_direction(points[-2],points[-1])
            if _cap(points[0],u)!=caps[start] or _cap(points[-1],v)!=caps[end]:raise ValueError("Actual macro endpoint position/direction differs")
            if _reduced_word(points)!=points:raise ValueError("Canonical reduced connector word required")
            if not _template_member(points,u,v,stubs,planes,control):raise ValueError("Connector is outside the authored finite template language")
            definition={"from":row["from"],"to":row["to"],"points_m":path}
            if identity!="connector-"+_digest(definition,control,max_bytes)[:24]:raise ValueError("Connector definition identity differs")
            certificate=macro["certificate"]
            if (type(certificate) is not dict or type(certificate.get("components")) is not list
                    or len(certificate["components"])>32 or type(certificate.get("transitions")) is not list
                    or len(certificate["transitions"])>16):raise _Limit("FABRICATION_CERTIFICATE_BUDGET")
            _fabrication_numeric_shape(certificate,control)
            control.use(1+len(certificate["components"])*64)
            control.pulse("shared_tree_catalogue_check_fabrication")
            fresh=verify_orthogonal_fabrication(_scenario(r,points[0],points[-1]),path,certificate,context_root=input_root,max_points=16)
            control.pulse("shared_tree_catalogue_check_fabrication_complete")
            if fresh.get("status")!="PASS" or fresh.get("fabrication_status")!="PASS" or certificate.get("status")!="PASS":
                raise ValueError("Current independent nominal fabrication verification did not pass")
            if _digest(fresh,control,max_bytes)!=_digest(macro["independent_check"],control,max_bytes):raise ValueError("Stored fabrication result does not match fresh replay")
            parts,cost=_components(points,identity,r,weights,control)
            if _digest(geometry["components"],control,max_bytes)!=_digest(parts,control,max_bytes):raise ValueError("Complete physical segment/elbow/profile geometry differs")
            for part in parts:
                if part["id"] in physical_ids:raise ValueError("Physical component identity reused across macro/tee inventory")
                physical_ids.add(part["id"])
            component_count+=len(parts)
            expected={"id":identity,"from":row["from"],"to":row["to"],"start_cap":caps[start],"end_cap":caps[end],
                "section":section,"geometry_root":_digest({"points_m":path,"components":parts},control,max_bytes),
                "fabrication_root":_root(certificate["certificate_root"]),"nominal_cost":cost}
            if _digest(row,control,max_bytes)!=_digest(expected,control,max_bytes):raise ValueError("Macro cap/section/geometry/fabrication/cost roots differ")
            rows[identity]=row;definitions[identity]=definition
        if set(g["connector_macros"])!=set(rows):raise ValueError("Extra or omitted macro denominator")
        admitted=set();attempt_definitions=set();diagnostics=0
        for attempt in g["attempts"]:
            control.use()
            if type(attempt) is not dict:raise ValueError("Attempt definition object required")
            status=attempt.get("status")
            fields={"from","to","points_m","status"}
            if status=="NOMINAL_MACRO_ADMITTED":fields|={"connector_id"}
            elif status=="NOMINAL_TEMPLATE_NOT_ADMITTED":fields|={"certificate","check"}
            elif status=="UNSUPPORTED_TEMPLATE":fields|={"reason"}
            else:raise ValueError("Unknown attempt diagnostic status")
            _keys(attempt,fields)
            definition={k:attempt[k] for k in ("from","to","points_m")}
            definition_root=_digest(definition,control,max_bytes)
            if definition_root in attempt_definitions:raise ValueError("Duplicate template attempt definition")
            attempt_definitions.add(definition_root)
            if status=="NOMINAL_MACRO_ADMITTED":
                identity=attempt["connector_id"]
                if identity in admitted or identity not in definitions or _digest(definition,control,max_bytes)!=_digest(definitions[identity],control,max_bytes):
                    raise ValueError("Admitted-attempt/macro denominator differs")
                admitted.add(identity)
            else:
                # Failure payloads are retained diagnostics, not independently
                # certified rejection or claims that all templates were covered.
                for endpoint in (attempt["from"],attempt["to"]):_keys(endpoint,{"node","port"})
                start=(attempt["from"]["node"],attempt["from"]["port"]);end=(attempt["to"]["node"],attempt["to"]["port"])
                if start not in caps or end not in caps:raise ValueError("Diagnostic references missing caps")
                if type(attempt["points_m"]) is not list or not 2<=len(attempt["points_m"])<=16:raise _Limit("POINT_BUDGET")
                pts=[_point(x) for x in attempt["points_m"]]
                u,_=_direction(pts[0],pts[1]);v,_=_direction(pts[-2],pts[-1])
                if _cap(pts[0],u)!=caps[start] or _cap(pts[-1],v)!=caps[end] or not _template_member(pts,u,v,stubs,planes,control):
                    raise ValueError("Diagnostic definition is outside current cap/template inputs")
                if status=="UNSUPPORTED_TEMPLATE" and (type(attempt["reason"]) is not str or not attempt["reason"]):raise ValueError("Diagnostic reason required")
                diagnostics+=1
        if admitted!=set(rows):raise ValueError("Missing admitted macro-attempt incidence")
        catalogue_root=_digest(catalogue,control,max_bytes)
        result={"schema":SCHEMA,"status":"PASS","proof_complete":True,"scope":SCOPE,
            "input_root":input_root,"generated_root":generated_root,"catalogue_root":catalogue_root,
            "normalized_requirements_root":_digest(r,control,max_bytes),"context_root":_digest(c,control,max_bytes),
            "counts":{"tees":len(tee_components),"terminals":len(terminal_rows)+1,"connector_macros":len(rows),
                      "physical_components_in_catalogue":component_count,"admitted_attempts":len(admitted),"untrusted_diagnostic_attempts":diagnostics},
            "limitations":{"native_acceptance_authority":False,"all_templates_enumerated":False,
                "diagnostic_rejections_certified":False,"geometry_source_authenticity_external":True}}
        control.pulse("shared_tree_catalogue_check_complete")
        _generated_shape(generated,max_macros,max_attempts)
        if _snapshot(originals,control,max_bytes,callbacks=False)[1]!=input_root:raise ValueError("Caller inputs changed during verification")
        if _snapshot(generated,control,max_bytes,callbacks=False)[1]!=generated_root:raise ValueError("Caller catalogue changed during verification")
        result["work"]=control.work
        return result
    except _External as error:raise error.error
    except _Limit as error:
        return {"schema":SCHEMA,"status":"UNKNOWN","reason":str(error),"proof_complete":False,"scope":SCOPE,"work":control.work if control else 0}
    except (ValueError,TypeError,KeyError,IndexError,ZeroDivisionError,OverflowError,RuntimeError,RecursionError) as error:
        return {"schema":SCHEMA,"status":"FAIL","reason":str(error),"proof_complete":False,"scope":SCOPE,"work":control.work if control else 0}
