"""Checked finite axis-grid search with direction, straight debt and bends.

Integration DEF-RTR39--41 / ALG-RTR15, specialized to a fixed round size.
Outer-box rejection removes an edge of this declared conservative graph; it
does not prove collision or absence of another physical route.
"""
from collections import deque
from copy import deepcopy
from fractions import Fraction as Q
from itertools import product
from math import prod

from oma.store import digest
from .rectilinear_opening import _q


SCOPE="FINITE_ORTHOGONAL_FABRICATION_GRAPH_WITH_DECLARED_OUTER_BOXES"
RULE="ADJACENT_GRID_STEPS_FIXED_ROUND_QUARTER_BENDS_STRICT_STRAIGHT_DEBT_V1"
LIMITATIONS={"source_outer_cover_authenticity_checked":False,"frame_applicability_checked":False,
    "manufacturer_catalog_or_supports_checked":False,"gravity_or_service_physics_checked":False,
    "nonadjacent_self_interference_checked":False,"continuous_route_completeness":False,
    "physical_route_infeasibility_claim":False,"length_optimality_claim":False,
    "native_IFC_candidate_acceptance_authority":False}


class _Exhausted(Exception):pass


class _Work:
    def __init__(self,limit,checkpoint):
        if type(limit) is not int or not 1<=limit<=10000000:raise ValueError("Work budget must be 1..10000000")
        self.limit,self.used,self.callback,self.callback_error=limit,0,checkpoint,None
        self.pulse("fabrication_graph_start")

    def pulse(self,stage):
        if self.callback is not None:
            try:self.callback(stage)
            except Exception as exc:
                self.callback_error=exc
                raise

    def tick(self,amount=1):
        self.used+=amount
        if self.used>self.limit:raise _Exhausted("WORK_BUDGET")
        if self.used%128==0:self.pulse("fabrication_graph_work")


def _rational(value):
    if isinstance(value,str) and len(value)>256:raise ValueError("Coordinate rational encoding exceeds 256 characters")
    if isinstance(value,int) and value.bit_length()>4096:raise ValueError("Coordinate integer exceeds 4096 bits")
    value=_q(value)
    if max(value.numerator.bit_length(),value.denominator.bit_length())>4096:raise ValueError("Coordinate rational exceeds 4096 bits")
    return value


def _point(value):
    if not isinstance(value,(list,tuple)) or len(value)!=3:raise ValueError("Three rational coordinates required")
    return tuple(map(_rational,value))


def _box(value):
    if not isinstance(value,(list,tuple)) or len(value)!=2:raise ValueError("Two box endpoints required")
    a,b=map(_point,value)
    if any(x>y for x,y in zip(a,b)):raise ValueError("Reversed box")
    return a,b


def _pj(value):return [str(x) for x in value]
def _bj(value):return list(map(_pj,value))
def _add(a,b,t=1):return tuple(x+t*y for x,y in zip(a,b))
def _direction(d):return tuple(Q((-1 if d%2==0 else 1)*int(i==d//2)) for i in range(3))


def _prepare(problem,max_states,work):
    fields={"schema","context_root","source_roots","allowed_bounds","grid_axes","start","goal",
        "diameter_m","insulation_m","bend_radius_m","minimum_straight_m","clearance_m","outer_obstacles"}
    if not isinstance(problem,dict) or set(problem)!=fields or problem["schema"]!="oma.fabrication-grid-problem/1":
        raise ValueError("Complete fabrication-grid problem schema required")
    if type(max_states) is not int or not 1<=max_states<=100000:raise ValueError("State budget must be 1..100000")
    if not isinstance(problem["context_root"],str) or not 1<=len(problem["context_root"])<=1024:raise ValueError("Bounded applicability context root required")
    roots=problem["source_roots"]
    if not isinstance(roots,dict) or not 1<=len(roots)<=64 or any(not isinstance(k,str) or not 1<=len(k)<=128 or not isinstance(v,str) or not 1<=len(v)<=1024 for k,v in roots.items()):
        raise ValueError("Explicit nonempty source identity roots required")
    axes=problem["grid_axes"];outer=problem["outer_obstacles"]
    if not isinstance(axes,(list,tuple)) or len(axes)!=3 or any(not isinstance(a,(list,tuple)) or len(a)<2 for a in axes):
        raise ValueError("Three strictly increasing nontrivial grid axes required")
    if prod(map(len,axes))>1024:raise _Exhausted("GRID_VERTEX_BUDGET")
    if not isinstance(outer,list):raise ValueError("Complete explicit outer obstacle list required")
    if len(outer)>256:raise _Exhausted("OUTER_BOX_BUDGET")
    axes=tuple(tuple(map(_rational,a)) for a in axes)
    if any(any(a>=b for a,b in zip(axis,axis[1:])) for axis in axes):raise ValueError("Grid axes must be strictly increasing")
    allowed=_box(problem["allowed_bounds"])
    dimensions={k:_rational(problem[k]) for k in ("diameter_m","insulation_m","bend_radius_m","minimum_straight_m","clearance_m")}
    r=dimensions["diameter_m"]/2+dimensions["insulation_m"];R=dimensions["bend_radius_m"]
    if dimensions["diameter_m"]<=0 or dimensions["insulation_m"]<0 or R<=r or min(dimensions["minimum_straight_m"],dimensions["clearance_m"])<0:
        raise ValueError("Positive fixed round section, bend greater than full radius, nonnegative minimum and clearance required")
    if any(axis[0]<allowed[0][i]+r or axis[-1]>allowed[1][i]-r for i,axis in enumerate(axes)):
        raise ValueError("Grid vertices must stay inside the full-ball-eroded allowed box")
    start,goal=_point(problem["start"]),_point(problem["goal"])
    if start==goal:raise ValueError("Distinct route terminals required")
    try:start_index=tuple(axes[i].index(x) for i,x in enumerate(start));goal_index=tuple(axes[i].index(x) for i,x in enumerate(goal))
    except ValueError as exc:raise ValueError("Both terminals must be exact declared grid vertices") from exc
    boxes=[];seen=set()
    for item in outer:
        work.tick()
        if not isinstance(item,dict) or set(item)!={"id","bounds"} or not isinstance(item["id"],str) or not 1<=len(item["id"])<=256 or item["id"] in seen:
            raise ValueError("Unique complete outer box identities required")
        seen.add(item["id"]);boxes.append((item["id"],_box(item["bounds"])))
    work.tick(prod(map(len,axes)))
    normalized={"schema":problem["schema"],"context_root":problem["context_root"],"source_roots":dict(roots),
        "allowed_bounds":_bj(allowed),"grid_axes":[_pj(a) for a in axes],"start":_pj(start),"goal":_pj(goal),
        **{k:str(v) for k,v in dimensions.items()},"outer_obstacles":[{"id":name,"bounds":_bj(bounds)} for name,bounds in sorted(boxes)]}
    root=digest(normalized)
    return {"input":normalized,"root":root,"graph_root":digest({"rule":RULE,"input_root":root}),"axes":axes,
        "allowed":allowed,"r":r,"R":R,"minimum":max(dimensions["minimum_straight_m"],_q(1e-9)),
        "clearance":dimensions["clearance_m"],"boxes":sorted(boxes),"start":start_index,"goal":goal_index,
        "initial":(*start_index,-1,-1,0),"vertex_count":prod(map(len,axes))}


def _position(m,index):return tuple(m["axes"][i][index[i]] for i in range(3))


def _run_length(m,state):
    axis=state[3]//2
    return abs(m["axes"][axis][state[axis]]-m["axes"][axis][state[4]])


def _goal(m,state):
    return state[:3]==m["goal"] and state[3]>=0 and _run_length(m,state)>state[5]*m["R"]+m["minimum"]


def _valid_state(m,value):
    if not isinstance(value,(tuple,list)) or len(value)!=6 or any(type(x) is not int for x in value):raise ValueError("Six integer state coordinates required")
    state=tuple(value)
    if state==m["initial"]:return state
    if any(not 0<=state[i]<len(m["axes"][i]) for i in range(3)) or not 0<=state[3]<6 or state[5] not in (0,1):
        raise ValueError("State outside finite grid and direction/debt domain")
    axis=state[3]//2;sign=-1 if state[3]%2==0 else 1
    if not 0<=state[4]<len(m["axes"][axis]) or sign*(state[axis]-state[4])<=0:
        raise ValueError("Run origin is not behind the current directed state")
    if state[5]==0 and (state[4]!=m["start"][axis] or any(state[i]!=m["start"][i] for i in range(3) if i!=axis)):
        raise ValueError("Debt-free initial run must start at the actual source")
    return state


def _clear(m,bounds,work):
    work.tick()
    if any(lo>a or b>hi for lo,hi,a,b in zip(*m["allowed"],*bounds)):return False
    for _,obstacle in m["boxes"]:
        work.tick()
        gaps=[max(Q(0),obstacle[0][i]-bounds[1][i],bounds[0][i]-obstacle[1][i]) for i in range(3)]
        if sum(g*g for g in gaps)<=m["clearance"]**2:return False
    return True


def _producer_straight_bounds(a,b,r):
    axis=next(i for i in range(3) if a[i]!=b[i])
    return (tuple(min(a[i],b[i])-(r if i!=axis else 0) for i in range(3)),
        tuple(max(a[i],b[i])+(r if i!=axis else 0) for i in range(3)))


def _producer_bend_bounds(p,incoming,outgoing,R,r):
    u,v=_direction(incoming),_direction(outgoing)
    center=_add(_add(p,u,-R),v,R)
    intervals=[]
    for i in range(3):
        offsets=(0,u[i]*(R+r)) if u[i] else (0,-v[i]*(R+r)) if v[i] else (-r,r)
        intervals.append((center[i]+min(offsets),center[i]+max(offsets)))
    return tuple(x[0] for x in intervals),tuple(x[1] for x in intervals)


def _checker_support_bounds(points):
    return tuple(min(p[i] for p in points) for i in range(3)),tuple(max(p[i] for p in points) for i in range(3))


def _checker_straight_bounds(a,b,r):
    transverse=[_direction(2*i+1) for i in range(3) if a[i]==b[i]]
    return _checker_support_bounds([_add(p,d,sign*r) for p,d,sign in product((a,b),transverse,(-1,1))])


def _checker_bend_bounds(p,incoming,outgoing,R,r):
    u,v=_direction(incoming),_direction(outgoing)
    a,b=_add(p,u,-R),_add(p,v,R)
    n=tuple(u[(i+1)%3]*v[(i+2)%3]-u[(i+2)%3]*v[(i+1)%3] for i in range(3))
    return _checker_support_bounds([_add(cap,d,sign*r) for cap,ds in ((a,(v,n)),(b,(u,n))) for d in ds for sign in (-1,1)])


def _producer_successors(m,state,work,cache):
    point=_position(m,state)
    for direction in range(6):
        work.tick();axis=direction//2;step=-1 if direction%2==0 else 1
        target=list(state[:3]);target[axis]+=step
        if not 0<=target[axis]<len(m["axes"][axis]):continue
        if state[3]>=0 and direction!=state[3]:
            if axis==state[3]//2 or _run_length(m,state)-state[5]*m["R"]-m["R"]<=m["minimum"]:continue
            key=("bend",state[:3],state[3],direction)
            if key not in cache:cache[key]=_clear(m,_producer_bend_bounds(point,state[3],direction,m["R"],m["r"]),work)
            if not cache[key]:continue
        key=("line",tuple(sorted((state[:3],tuple(target)))))
        if key not in cache:cache[key]=_clear(m,_producer_straight_bounds(point,_position(m,target),m["r"]),work)
        if not cache[key]:continue
        same=direction==state[3]
        yield (*target,direction,state[4] if same else state[axis],state[5] if same else int(state[3]>=0))


def _checked_successors(m,state,work,cache):
    """Independently reconstruct every admitted outgoing edge and its state."""
    here=_position(m,state);old=state[3]
    for axis,sign in product(range(3),(-1,1)):
        work.tick();direction=2*axis+int(sign>0)
        vertex=tuple(state[i]+(sign if i==axis else 0) for i in range(3))
        if any(not 0<=vertex[i]<len(m["axes"][i]) for i in range(3)):continue
        if old==direction:
            next_state=(*vertex,old,state[4],state[5])
        elif old<0:
            next_state=(*vertex,direction,state[axis],0)
        else:
            if old//2==axis:continue
            run_origin=list(here);run_origin[old//2]=m["axes"][old//2][state[4]]
            travel=sum(abs(a-b) for a,b in zip(here,run_origin))
            if travel<=m["minimum"]+m["R"]*(state[5]+1):continue
            corner_key=("bend",state[:3],old,direction)
            if corner_key not in cache:cache[corner_key]=_clear(m,_checker_bend_bounds(here,old,direction,m["R"],m["r"]),work)
            if not cache[corner_key]:continue
            next_state=(*vertex,direction,state[axis],1)
        edge_key=("line",tuple(sorted((state[:3],vertex))))
        if edge_key not in cache:cache[edge_key]=_clear(m,_checker_straight_bounds(here,_position(m,vertex),m["r"]),work)
        if cache[edge_key]:yield next_state


def _path_points(m,path):
    corners=[m["start"]]
    for a,b in zip(path,path[1:]):
        if a[3]>=0 and a[3]!=b[3]:corners.append(a[:3])
    corners.append(m["goal"])
    return [_pj(_position(m,index)) for index in corners]


def _certificate(m,outcome,path,closed,work):
    result={"schema":"oma.fabrication-grid-certificate/1","status":"CERTIFIED","geometry_outcome":outcome,
        "input_root":m["root"],"graph_root":m["graph_root"],"rule":RULE,"scope":SCOPE,"limitations":deepcopy(LIMITATIONS),
        "path_states":[list(s) for s in path],"points_m":_path_points(m,path) if path else [],
        "closed_states":[list(s) for s in sorted(closed)],"vertex_count":m["vertex_count"],"producer_work":work.used}
    result["certificate_root"]=digest(result)
    return result


def compile_fabrication_search(problem,*,max_states=12000,max_work=500000,checkpoint=None):
    """Find a checked-family path or finite reachable cut, never a physical cut."""
    work=_Work(max_work,checkpoint);m=None
    try:
        m=_prepare(problem,max_states,work)
        initial=m["initial"];parents={initial:None};todo=deque([initial]);cache={}
        while todo:
            work.pulse("fabrication_graph_expand")
            current=todo.popleft()
            if _goal(m,current):
                path=[]
                while current is not None:path.append(current);current=parents[current]
                return _certificate(m,"PATH",list(reversed(path)),[],work)
            for successor in _producer_successors(m,current,work,cache):
                if successor not in parents:
                    if len(parents)>=max_states:raise _Exhausted("STATE_BUDGET")
                    parents[successor]=current;todo.append(successor)
        return _certificate(m,"NO_PATH_IN_DECLARED_GRAPH",[],parents,work)
    except _Exhausted as exc:
        if work.callback_error is exc:raise
        return {"status":"UNKNOWN","reason":str(exc),"input_root":m["root"] if m else None,
            "scope":SCOPE,"limitations":deepcopy(LIMITATIONS),"proof_complete":False,"work":work.used}


def verify_fabrication_search(problem,certificate,*,max_states=12000,max_work=500000,checkpoint=None):
    """Rebuild transition predicates and check a path or complete reachable cut."""
    work=_Work(max_work,checkpoint)
    try:
        m=_prepare(problem,max_states,work)
        if not isinstance(certificate,dict):raise ValueError("Certificate object required")
        if certificate.get("status")=="UNKNOWN":return {"status":"UNKNOWN","reason":"NO_COMPLETE_CERTIFICATE","scope":SCOPE}
        expected={"schema","status","geometry_outcome","input_root","graph_root","rule","scope","limitations",
            "path_states","points_m","closed_states","vertex_count","producer_work","certificate_root"}
        if set(certificate)!=expected:raise ValueError("Complete finite-graph certificate required")
        for field in ("path_states","closed_states","points_m"):
            if not isinstance(certificate[field],list):raise ValueError("Finite certificate lists required")
            if len(certificate[field])>max_states:raise _Exhausted("CERTIFICATE_STATE_BUDGET")
        for field in ("path_states","closed_states"):
            for state in certificate[field]:work.tick();_valid_state(m,state)
        for point in certificate["points_m"]:
            work.tick()
            if not isinstance(point,list) or len(point)!=3 or any(not isinstance(x,str) or len(x)>2500 for x in point):
                raise ValueError("Bounded normalized path coordinates required")
        c={k:v for k,v in certificate.items() if k!="certificate_root"}
        if (digest(c)!=certificate["certificate_root"] or c["schema"]!="oma.fabrication-grid-certificate/1"
                or c["status"]!="CERTIFIED" or c["input_root"]!=m["root"] or c["graph_root"]!=m["graph_root"]
                or c["rule"]!=RULE or c["scope"]!=SCOPE or digest(c["limitations"])!=digest(LIMITATIONS)
                or type(c["vertex_count"]) is not int or c["vertex_count"]!=m["vertex_count"]
                or type(c["producer_work"]) is not int or c["producer_work"]<0):raise ValueError("Input, graph, certificate root or declared scope differs")
        cache={};transitions=0
        if c["geometry_outcome"]=="PATH":
            path=[_valid_state(m,s) for s in c["path_states"]]
            if c["closed_states"] or not path or path[0]!=m["initial"] or not _goal(m,path[-1]):raise ValueError("Path does not discharge the exact source/goal and final straight obligations")
            for before,after in zip(path,path[1:]):
                work.pulse("fabrication_path_verify")
                successors=list(_checked_successors(m,before,work,cache));transitions+=len(successors)
                if after not in successors:raise ValueError("Path uses an inadmissible fabrication-state transition")
            if c["points_m"]!=_path_points(m,path):raise ValueError("Returned polyline differs from the checked state path")
            count=len(path)
        elif c["geometry_outcome"]=="NO_PATH_IN_DECLARED_GRAPH":
            closed=[_valid_state(m,s) for s in c["closed_states"]];states=set(closed)
            if c["path_states"] or c["points_m"] or len(states)!=len(closed) or m["initial"] not in states:
                raise ValueError("Complete unique cut set containing the source required")
            for state in states:
                work.pulse("fabrication_cut_verify")
                if _goal(m,state):raise ValueError("Cut contains a valid goal state")
                successors=set(_checked_successors(m,state,work,cache));transitions+=len(successors)
                if not successors<=states:raise ValueError("Reachable set omits an admissible successor")
            count=len(states)
        else:raise ValueError("Unknown geometric outcome")
        return {"status":"PASS","geometry_outcome":c["geometry_outcome"],"scope":SCOPE,"input_root":m["root"],
            "graph_root":m["graph_root"],"certificate_root":certificate["certificate_root"],"states_checked":count,
            "transitions_reconstructed":transitions,"work":work.used,"limitations":deepcopy(LIMITATIONS)}
    except _Exhausted as exc:
        if work.callback_error is exc:raise
        return {"status":"UNKNOWN","reason":str(exc),"scope":SCOPE,"work":work.used}
    except (ValueError,TypeError,KeyError,IndexError,OverflowError,ZeroDivisionError) as exc:
        if work.callback_error is exc:raise
        return {"status":"FAIL","reason":str(exc),"scope":SCOPE}
