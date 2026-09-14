"""Bounded orthogonal constant-section fabrication transitions (ALG-RTR15).

Exact tangent quarter bends and flat-cap cylinders only. This is not a full
fabrication graph, manufacturer approval, obstacle authenticity or native IFC
equality proof. Fixed-polyline rejection does not reject all physical routes.
"""
from copy import deepcopy
from fractions import Fraction as Q
from itertools import product

from oma.routing.scenario import RoutingScenario
from oma.store import digest
from .rectilinear_opening import _q


SCOPE = "EXACT_FIXED_ORTHOGONAL_POLYLINE_CONSTANT_ROUND_FILLET_REALIZATION"
LIMITATIONS = {
    "full_fabrication_graph_or_homotopy_complete":False,
    "manufacturer_catalog_or_supports_checked":False,
    "nonadjacent_component_self_interference_checked":False,
    "gravity_slope_or_service_physics_checked":False,
    "obstacle_outer_cover_authenticity_checked":False,
    "native_IFC_geometry_equality_checked":False,
    "candidate_acceptance_authority":False,
    "automatic_numerical_writer_pruning_authority":False,
    "physical_route_universe_infeasibility_claim":False,
}


def _point(value):
    if not isinstance(value,(list,tuple)) or len(value) != 3:
        raise ValueError("Three finite rational coordinates required")
    return tuple(map(_q,value))


def _box(value):
    if not isinstance(value,(list,tuple)) or len(value) != 2:
        raise ValueError("Two box endpoints required")
    box = tuple(map(_point,value))
    if any(a > b for a,b in zip(*box)):
        raise ValueError("Reversed obstacle or allowed bounds")
    return box


def _plus(a,b,scale=1): return tuple(x+scale*y for x,y in zip(a,b))
def _dot(a,b): return sum((x*y for x,y in zip(a,b)),Q(0))
def _cross(a,b): return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def _json_point(p): return [str(v) for v in p]
def _json_box(b): return list(map(_json_point,b))


def _prepare(scenario,points_m,context_root,outer_obstacles,outer_model_root,max_points):
    if not isinstance(context_root,str) or not context_root:
        raise ValueError("Immutable applicability context required")
    if type(max_points) is not int or not 2 <= max_points <= 1024:
        raise ValueError("Point budget must be an integer from 2 to 1024")
    if not isinstance(points_m,(list,tuple)) or len(points_m) < 2:
        raise ValueError("At least two route points required")
    if len(points_m) > max_points:
        # A non-proof budget result must not traverse, hash or parse a potentially
        # unbounded input. Its context is caller-bound; coordinates, scenario and
        # obstacles are explicitly uninspected, rather than falsely hash-bound.
        manifest = {"schema":"oma.orthogonal-fabrication-budget-input/1",
            "context_root":context_root,"point_count":len(points_m),"max_points":max_points,
            "input_binding":"COUNT_AND_EXTERNAL_CONTEXT_ONLY; GEOMETRY_INPUTS_UNINSPECTED"}
        return {"manifest":manifest,"root":digest(manifest),
            "early":{"status":"UNKNOWN","code":"POINT_BUDGET"}}
    raw = scenario.model_dump(mode="json") if isinstance(scenario,RoutingScenario) else scenario
    scenario = RoutingScenario.model_validate(raw)
    points = list(map(_point,points_m))
    outer = []
    if outer_obstacles is not None:
        if not isinstance(outer_model_root,str) or not outer_model_root or not isinstance(outer_obstacles,list) or len(outer_obstacles)>256:
            raise ValueError("A bounded explicit outer model and its root are required")
        seen = set()
        for item in outer_obstacles:
            if set(item) != {"id","bounds"} or not isinstance(item["id"],str) or not item["id"] or item["id"] in seen:
                raise ValueError("Distinct complete outer obstacle identities required")
            seen.add(item["id"])
            outer.append({"id":item["id"],"bounds":_json_box(_box(item["bounds"]))})
    elif outer_model_root is not None:
        raise ValueError("Outer model root without its explicit obstacle family")
    radius = _q(scenario.diameter_m)/2+_q(scenario.insulation_m)
    bend = _q(scenario.bend_radius_m)
    required = max(_q(scenario.minimum_straight_m),_q(1e-9))
    manifest = {"schema":"oma.orthogonal-fabrication-input/1","scenario":scenario.model_dump(mode="json"),
        "points_m":[_json_point(p) for p in points],"context_root":context_root,
        "point_count":len(points),"max_points":max_points,"input_binding":"COMPLETE_NORMALIZED_INPUT",
        "outer_obstacles":sorted(outer,key=lambda o:o["id"]),"outer_model_root":outer_model_root,
        "outer_model_supplied":outer_obstacles is not None,"outer_radius_m":str(radius),
        "bend_radius_m":str(bend),"strict_minimum_remaining_straight_m":str(required),
        "size_transition":"FIXED_DIAMETER_INSULATION_AND_CLEARANCE; NO_REDUCERS",
        "arithmetic":"EXACT_BINARY_INPUT_VALUES_AND_RATIONAL_DERIVED_SUMS; ANGLE_IS_SYMBOLIC_PI_OVER_TWO"}
    early = None
    if points[0] != _point(scenario.start) or points[-1] != _point(scenario.end): early = {"status":"FAIL","code":"FIXED_ENDPOINT_MISMATCH"}
    elif scenario.system_type == "GRAVITY_DRAINAGE": early = {"status":"UNKNOWN","code":"GRAVITY_SLOPE_STATE_UNSUPPORTED"}
    elif radius <= 0 or bend <= radius: early = {"status":"FAIL","code":"BEND_RADIUS_NOT_GREATER_THAN_FULL_BODY_RADIUS"}
    directions,lengths = [],[]
    for index,(a,b) in enumerate(zip(points,points[1:])):
        delta = _plus(b,a,-1)
        axes = [i for i,x in enumerate(delta) if x]
        if len(axes) != 1:
            if early is None: early = {"status":"FAIL" if not axes else "UNKNOWN","code":"ZERO_SEGMENT" if not axes else "NONORTHOGONAL_SEGMENT","segment":index}
            directions.append(None); lengths.append(None)
        else:
            length = abs(delta[axes[0]])
            directions.append(tuple(x/length for x in delta)); lengths.append(length)
    if early is None:
        for index,(u,v) in enumerate(zip(directions,directions[1:]),1):
            if _dot(u,v) == -1:
                early = {"status":"FAIL","code":"NO_TANGENT_QUARTER_BEND_FOR_UTURN","corner":index}; break
    trims = [Q(0)]*len(points)
    if early is None:
        for i,(u,v) in enumerate(zip(directions,directions[1:]),1):
            trims[i] = bend if _dot(u,v)==0 else Q(0)
        for i,length in enumerate(lengths):
            available = length-trims[i]-trims[i+1]
            if available <= required:
                early = {"status":"FAIL","code":"INSUFFICIENT_REMAINING_STRAIGHT","segment":i,
                    "available_m":str(available),"strict_required_m":str(required)}; break
    return {"manifest":manifest,"root":digest(manifest),"scenario":scenario,"points":points,"u":directions,
            "lengths":lengths,"trims":trims,"radius":radius,"bend":bend,"early":early}


def _producer_bounds(part,radius):
    start,end = _point(part["start"]),_point(part["end"])
    if part["kind"] == "segment":
        axis = next(i for i in range(3) if start[i] != end[i])
        return (tuple(min(start[i],end[i])-(radius if i!=axis else 0) for i in range(3)),
                tuple(max(start[i],end[i])+(radius if i!=axis else 0) for i in range(3)))
    center,u,v = map(_point,(part["center"],part["incoming"],part["outgoing"]))
    reach = _q(part["bend_radius_m"])+radius
    lo,hi = [],[]
    for i in range(3):
        if u[i]: offsets = (0,u[i]*reach)
        elif v[i]: offsets = (0,-v[i]*reach)
        else: offsets = (-radius,radius)
        lo.append(center[i]+min(offsets)); hi.append(center[i]+max(offsets))
    return tuple(lo),tuple(hi)


def _verify_parts(model,certificate):
    """Check tangent constraints and attained support extrema, not construction."""
    points,u,trims,r,R = (model[k] for k in ("points","u","trims","radius","bend"))
    expected = [("segment",i) for i in range(len(u))]
    expected += [("elbow",i) for i in range(1,len(points)-1) if trims[i]]
    parts = certificate["components"]
    if not isinstance(parts,list) or any(not isinstance(p,dict) or type(p.get("index")) is not int for p in parts):
        raise ValueError("Integer component identities required")
    keys = [(p["kind"],p["index"]) for p in parts]
    if len(keys) != len(set(keys)) or set(keys) != set(expected):
        raise ValueError("Complete unique segment and elbow denominator required")
    transitions = certificate["transitions"]
    if not isinstance(transitions,list) or len(transitions) != len(points)-2:
        raise ValueError("Complete fabrication transition sequence required")
    for i,state in enumerate(transitions,1):
        if not isinstance(state,dict) or type(state.get("corner")) is not int or state != {"corner":i,"incoming":_json_point(u[i-1]),"outgoing":_json_point(u[i]),
            "turn":"QUARTER_BEND" if trims[i] else "COLLINEAR", "trim_debt_m":str(trims[i]),
            "incoming_remaining_straight_m":str(model["lengths"][i-1]-trims[i-1]-trims[i]),
            "fixed_size_root":digest({k:model["manifest"][k] for k in ("outer_radius_m","bend_radius_m","size_transition")}),
            "support_phase":"NOT_MODELLED","slope_state":"NOT_MODELLED"}:
            raise ValueError("Transition direction, trim debt or fixed size state changed")
    findings,unresolved = [],[]
    zone = _box([model["scenario"].allowed_zone.min,model["scenario"].allowed_zone.max])
    clearance = _q(model["scenario"].clearance_m)
    for part in parts:
        i = part["index"]
        a,b = _point(part["start"]),_point(part["end"])
        if _q(part["outer_radius_m"]) != r:
            raise ValueError("Insulated physical radius differs")
        if part["kind"] == "segment":
            if set(part) != {"kind","index","start","end","length_m","outer_radius_m","body_bounds_m"}:
                raise ValueError("Unexpected straight component fields")
            if _plus(a,points[i],-1) != tuple(trims[i]*x for x in u[i]) or _plus(points[i+1],b,-1) != tuple(trims[i+1]*x for x in u[i]):
                raise ValueError("Straight endpoints do not pay both adjacent tangent trims")
            actual_length = _dot(_plus(b,a,-1),u[i])
            if actual_length != _q(part["length_m"]) or actual_length <= _q(model["manifest"]["strict_minimum_remaining_straight_m"]):
                raise ValueError("Wrong or insufficient remaining straight length")
            transverse = [tuple(Q(int(j==axis)) for j in range(3)) for axis in range(3) if not u[i][axis]]
            support = [_plus(p,axis,sign*r) for p,axis,sign in product((a,b),transverse,(-1,1))]
        else:
            if set(part) != {"kind","index","start","end","center","incoming","outgoing","normal","bend_radius_m","angle_pi","length_pi_m","outer_radius_m","body_bounds_m"}:
                raise ValueError("Unexpected elbow component fields")
            center,incoming,outgoing,normal = map(_point,(part["center"],part["incoming"],part["outgoing"],part["normal"]))
            if incoming != u[i-1] or outgoing != u[i] or _dot(incoming,outgoing) != 0 or normal != _cross(incoming,outgoing):
                raise ValueError("Wrong orthogonal tangent frame or bend orientation")
            if (_plus(points[i],a,-1) != tuple(R*x for x in incoming) or _plus(b,points[i],-1) != tuple(R*x for x in outgoing)
                    or _plus(center,a,-1) != tuple(R*x for x in outgoing) or _plus(b,center,-1) != tuple(R*x for x in incoming)):
                raise ValueError("Elbow tangent endpoints and centre do not match the corner")
            if _q(part["bend_radius_m"]) != R or part["angle_pi"] != "1/2" or _q(part["length_pi_m"]) != R/2:
                raise ValueError("Bend size or symbolic quarter angle changed")
            # For signed coordinate axes and R>r, every coordinate is monotone
            # in sin/cos between the caps. These cap disk extrema attain the
            # full quarter-torus AABB; arbitrary rotated frames are unsupported.
            support = [_plus(p,axis,sign*r) for p,axes in ((a,(outgoing,normal)),(b,(incoming,normal))) for axis in axes for sign in (-1,1)]
        attained = (tuple(min(p[j] for p in support) for j in range(3)),tuple(max(p[j] for p in support) for j in range(3)))
        if _box(part["body_bounds_m"]) != attained:
            raise ValueError("Body bounds omit or enlarge the independently attained extrema")
        if not all(lo <= a <= b <= hi for lo,hi,a,b in zip(*zone,*attained)):
            findings.append({"code":"FULL_BODY_OUTSIDE_ALLOWED_ZONE","component":[part["kind"],i]})
        for obstacle in model["manifest"]["outer_obstacles"]:
            bounds = _box(obstacle["bounds"])
            gaps = [max(Q(0),bounds[0][j]-attained[1][j],attained[0][j]-bounds[1][j]) for j in range(3)]
            if sum(g*g for g in gaps) <= clearance*clearance:
                unresolved.append({"code":"OUTER_BOX_CLEARANCE_NOT_PROVED","component":[part["kind"],i],"obstacle":obstacle["id"]})
    return {"status":"FAIL" if findings else "UNKNOWN" if unresolved else "PASS","failures":findings,"unresolved":unresolved}


def compile_orthogonal_fabrication(scenario,points_m,*,context_root,outer_obstacles=None,outer_model_root=None,max_points=256):
    """Propose exact parts and transitions; malformed typed inputs raise ValueError."""
    m = _prepare(scenario,points_m,context_root,outer_obstacles,outer_model_root,max_points)
    cert = {"schema":"oma.orthogonal-fabrication-certificate/1","root":m["root"],"manifest":m["manifest"],
        "scope":SCOPE,"limitations":deepcopy(LIMITATIONS),"components":[],"transitions":[],"disposition":None}
    if m["early"]:
        cert["disposition"] = {"status":m["early"]["status"],"early":m["early"]}
    else:
        p,u,t,r,R = (m[k] for k in ("points","u","trims","radius","bend"))
        size_root = digest({k:m["manifest"][k] for k in ("outer_radius_m","bend_radius_m","size_transition")})
        for i in range(len(u)):
            a,b = _plus(p[i],u[i],t[i]),_plus(p[i+1],u[i],-t[i+1])
            part = {"kind":"segment","index":i,"start":_json_point(a),"end":_json_point(b),
                "length_m":str(m["lengths"][i]-t[i]-t[i+1]),"outer_radius_m":str(r)}
            part["body_bounds_m"] = _json_box(_producer_bounds(part,r)); cert["components"].append(part)
            if i+1 >= len(u): continue
            corner = i+1
            cert["transitions"].append({"corner":corner,"incoming":_json_point(u[i]),"outgoing":_json_point(u[i+1]),
                "turn":"QUARTER_BEND" if t[corner] else "COLLINEAR","trim_debt_m":str(t[corner]),
                "incoming_remaining_straight_m":part["length_m"],"fixed_size_root":size_root,"support_phase":"NOT_MODELLED","slope_state":"NOT_MODELLED"})
            if t[corner]:
                a,b = _plus(p[corner],u[i],-R),_plus(p[corner],u[i+1],R)
                center = _plus(a,u[i+1],R)
                elbow = {"kind":"elbow","index":corner,"start":_json_point(a),"end":_json_point(b),"center":_json_point(center),
                    "incoming":_json_point(u[i]),"outgoing":_json_point(u[i+1]),"normal":_json_point(_cross(u[i],u[i+1])),
                    "bend_radius_m":str(R),"angle_pi":"1/2","length_pi_m":str(R/2),"outer_radius_m":str(r)}
                elbow["body_bounds_m"] = _json_box(_producer_bounds(elbow,r)); cert["components"].append(elbow)
        cert["disposition"] = _verify_parts(m,cert)
    cert["status"] = cert["disposition"]["status"]
    cert["certificate_root"] = digest(cert)
    return cert


def verify_orthogonal_fabrication(scenario,points_m,certificate,*,context_root,outer_obstacles=None,outer_model_root=None,max_points=256):
    """Check the complete proposed transition/body proof without calling its producer."""
    try:
        m = _prepare(scenario,points_m,context_root,outer_obstacles,outer_model_root,max_points)
        if (not isinstance(certificate,dict) or not isinstance(certificate.get("components"),list)
                or not isinstance(certificate.get("transitions"),list)
                or len(certificate["components"]) > 2*max_points
                or len(certificate["transitions"]) > max_points):
            raise ValueError("Bounded component and transition lists required")
        cert = deepcopy(certificate)
        if set(cert) != {"schema","root","manifest","scope","limitations","components","transitions","disposition","status","certificate_root"}:
            raise ValueError("Complete fabrication certificate required")
        root = cert.pop("certificate_root")
        if root != digest(cert) or cert["root"] != m["root"] or digest(cert["manifest"]) != digest(m["manifest"]) or cert["scope"] != SCOPE or digest(cert["limitations"]) != digest(LIMITATIONS):
            raise ValueError("Input, artifact root or scope changed")
        if cert["schema"] != "oma.orthogonal-fabrication-certificate/1":
            raise ValueError("Unsupported certificate schema")
        if m["early"]:
            if cert["components"] or cert["transitions"]:
                raise ValueError("Unsupported input cannot carry fabricated part claims")
            expected = {"status":m["early"]["status"],"early":m["early"]}
        else:
            expected = _verify_parts(m,cert)
        if digest(cert["disposition"]) != digest(expected) or cert["status"] != expected["status"]:
            raise ValueError("Claimed fabrication disposition differs from checked predicates")
        return {"status":"PASS","fabrication_status":expected["status"],"scope":SCOPE,"root":m["root"],
            "certificate_root":root,"components_checked":len(cert["components"]),"transitions_checked":len(cert["transitions"]),
            "disposition":expected,"limitations":deepcopy(LIMITATIONS)}
    except (ValueError,KeyError,TypeError,IndexError,AttributeError,OverflowError,ZeroDivisionError) as exc:
        return {"status":"FAIL","reason":str(exc)}
