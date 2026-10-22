"""Bounded source-face and first-turn coordinate proposals, not free-space proof."""
from copy import deepcopy
from math import prod

from oma.optimization import fabrication_search as graph
from oma.store import digest


SCOPE = "HEURISTIC_SOURCE_FACE_AND_FABRICATION_THRESHOLD_GRID_ENRICHMENT"
LIMITATIONS = {"source_support_authenticity_checked": False, "free_space_or_route_certificate": False,
              "continuous_completeness": False, "native_acceptance_authority": False,
              "guard_is_certified_numeric_error_bound": False, "canonical_ranking_verified": False}


def _prepare(base_axes, start, goal, allowed_bounds, outer_obstacles, radius_m, clearance_m,
             guard_m, bend_radius_m, minimum_straight_m, max_vertices, max_axis_values, work):
    if type(max_vertices) is not int or not 8 <= max_vertices <= 1024:
        raise ValueError("Vertex budget must be 8..1024")
    if type(max_axis_values) is not int or not 2 <= max_axis_values <= 32:
        raise ValueError("Axis budget must be 2..32")
    if (not isinstance(base_axes, (list, tuple)) or len(base_axes) != 3
            or any(not isinstance(a, (list, tuple)) or len(a) < 2 for a in base_axes)):
        raise ValueError("Three nontrivial complete baseline axes required")
    if prod(map(len, base_axes)) > max_vertices or any(len(a) > max_axis_values for a in base_axes):
        raise graph._Exhausted("BASE_GRID_BUDGET; BASELINE_NOT_DROPPED")
    axes = tuple(tuple(map(graph._rational, a)) for a in base_axes)
    if any(any(a >= b for a, b in zip(axis, axis[1:])) for axis in axes):
        raise ValueError("Baseline axes must be strictly increasing")
    start, goal, allowed = graph._point(start), graph._point(goal), graph._box(allowed_bounds)
    radius, clearance, guard = map(graph._rational, (radius_m, clearance_m, guard_m))
    if radius <= 0 or clearance < 0 or guard <= 0:
        raise ValueError("Positive body radius and search guard, nonnegative clearance required")
    inner = tuple(tuple(row[i] + (radius if side == 0 else -radius) for i in range(3)) for side, row in enumerate(allowed))
    if any(axis[0] < inner[0][i] or axis[-1] > inner[1][i] for i, axis in enumerate(axes)):
        raise ValueError("Complete baseline must fit the ball-eroded allowed bounds")
    if start == goal or any(point[i] not in axes[i] for point in (start, goal) for i in range(3)):
        raise ValueError("Distinct exact terminals must already belong to the baseline grid")
    if (bend_radius_m is None) != (minimum_straight_m is None):
        raise ValueError("First-turn seeds require both bend radius and minimum straight")
    bend = minimum = None
    if bend_radius_m is not None:
        bend, minimum = map(graph._rational, (bend_radius_m, minimum_straight_m))
        if bend <= radius or minimum < 0:
            raise ValueError("Bend exceeds body radius and minimum straight is nonnegative")
        minimum = max(minimum, graph._rational(1e-9))
    if not isinstance(outer_obstacles, list):
        raise ValueError("Complete explicit outer obstacle list required")
    if len(outer_obstacles) > 256:
        raise graph._Exhausted("OUTER_BOX_BUDGET")
    boxes, seen = [], set()
    for item in outer_obstacles:
        work.tick()
        if (not isinstance(item, dict) or set(item) != {"id", "bounds"} or not isinstance(item["id"], str)
                or not 1 <= len(item["id"]) <= 256 or item["id"] in seen):
            raise ValueError("Unique complete source outer-box identities required")
        seen.add(item["id"])
        boxes.append((item["id"], graph._box(item["bounds"])))
    normalized = {"base_axes": [graph._pj(a) for a in axes], "start": graph._pj(start), "goal": graph._pj(goal),
        "allowed_bounds": graph._bj(allowed), "outer_obstacles": [{"id": name, "bounds": graph._bj(b)} for name,b in sorted(boxes)],
        "radius_m": str(radius), "clearance_m": str(clearance), "guard_m": str(guard),
        "bend_radius_m": str(bend) if bend is not None else None, "minimum_straight_m": str(minimum) if minimum is not None else None,
        "max_vertices": max_vertices, "max_axis_values": max_axis_values}
    return {"input": normalized, "root": digest(normalized), "axes": axes, "start": start, "goal": goal,
            "inner": inner, "boxes": sorted(boxes), "radius": radius, "clearance": clearance, "guard": guard,
            "bend": bend, "minimum": minimum, "max_vertices": max_vertices, "max_axis_values": max_axis_values}


def _candidates(m, work):
    corridor = tuple(tuple(fn(a,b) for a,b in zip(m["start"], m["goal"])) for fn in (min,max))
    candidates = []
    def add(key, axis, value, priority):
        work.tick()
        candidates.append({"key": key, "axis": axis, "value": str(value), "priority": priority})
    if m["bend"] is not None:
        for kind, trims, rank in (("TERMINAL_FIRST_TURN",1,0),("TERMINAL_TWO_TRIM",2,2)):
            distance = trims*m["bend"] + m["minimum"] + m["guard"]
            for name, point in (("start", m["start"]), ("goal", m["goal"])):
                for axis in range(3):
                    for sign in (-1,1):
                        value = point[axis] + sign*distance
                        outside = max(0,corridor[0][axis]-value,value-corridor[1][axis])
                        add([kind,name,axis,sign],axis,value,(rank,outside,abs(value-point[axis]),name,sign))
    margin = m["radius"] + m["clearance"] + m["guard"]
    for name, box in m["boxes"]:
        gap2 = sum(max(0,box[0][i]-corridor[1][i],corridor[0][i]-box[1][i])**2 for i in range(3))
        for axis in range(3):
            for side, sign in ((0,-1),(1,1)):
                value = box[side][axis] + sign*margin
                plane_distance = max(0,corridor[0][axis]-value,value-corridor[1][axis])
                add(["OBSTACLE_FACE",name,axis,side],axis,value,(1,gap2,plane_distance,name,side))
    return candidates


def enrich_fabrication_grid(base_axes, start, goal, allowed_bounds, outer_obstacles, radius_m, clearance_m, *,
                            guard_m="1/1000000", bend_radius_m=None, minimum_straight_m=None,
                            max_vertices=1024, max_axis_values=10, max_work=100000, checkpoint=None):
    """Propose extra exact coordinates while preserving every baseline node."""
    work = graph._Work(max_work, checkpoint)
    m = None
    try:
        m = _prepare(base_axes,start,goal,allowed_bounds,outer_obstacles,radius_m,clearance_m,
                     guard_m,bend_radius_m,minimum_straight_m,max_vertices,max_axis_values,work)
        candidates = _candidates(m,work)
        axes = [set(a) for a in m["axes"]]
        pending, records = [[],[],[]], []
        for entry in candidates:
            work.tick()
            axis, value = entry["axis"], graph._rational(entry["value"])
            row = {k:v for k,v in entry.items() if k != "priority"}
            if not m["inner"][0][axis] <= value <= m["inner"][1][axis]:
                row["disposition"] = "OUTSIDE_ERODED_ALLOWED_BOUNDS"
                records.append(row)
            elif value in axes[axis]:
                row["disposition"] = "BASELINE_COORDINATE"
                records.append(row)
            else:
                pending[axis].append((entry["priority"],row))
        for entries in pending:
            entries.sort(key=lambda x:x[0],reverse=True)
        while any(pending):
            work.pulse("fabrication_grid_allocate")
            # At most one value per least-populated available axis is chosen
            # before reconsidering counts. Default cap10 also limits the full
            # 3D product to1000 without starving another baseline axis.
            axis = min((i for i in range(3) if pending[i]),key=lambda i:(len(axes[i]),pending[i][-1][0],i))
            _, row = pending[axis].pop()
            value = graph._rational(row["value"])
            if value in axes[axis]:
                row["disposition"] = "RETAINED_COORDINATE"
            elif len(axes[axis]) >= max_axis_values:
                row["disposition"] = "AXIS_VALUE_BUDGET"
            elif (len(axes[axis])+1)*prod(len(axes[i]) for i in range(3) if i!=axis) > max_vertices:
                row["disposition"] = "GRID_VERTEX_BUDGET"
            else:
                axes[axis].add(value)
                row["disposition"] = "ADDED_COORDINATE"
            records.append(row)
            work.tick()
        result = {"schema":"oma.fabrication-grid-enrichment/1", "status":"PROPOSED_GRID", "scope":SCOPE,
                  "limitations":deepcopy(LIMITATIONS), "input_root":m["root"], "input":m["input"],
                  "grid_axes":[graph._pj(sorted(a)) for a in axes], "plane_records":sorted(records,key=lambda r:r["key"]),
                  "baseline_vertices":prod(map(len,m["axes"])), "proposed_vertices":prod(map(len,axes)), "work":work.used}
        result["result_root"] = digest(result)
        work.pulse("fabrication_grid_complete")
        return result
    except graph._Exhausted as exc:
        if work.callback_error is exc:
            raise
        return {"status":"UNKNOWN", "reason":str(exc), "scope":SCOPE, "grid_axes":[],
                "input_root":m["root"] if m else None, "limitations":deepcopy(LIMITATIONS)}


def verify_fabrication_grid_enrichment(base_axes, start, goal, allowed_bounds, outer_obstacles, radius_m, clearance_m, result, *,
                                      guard_m="1/1000000", bend_radius_m=None, minimum_straight_m=None,
                                      max_vertices=1024, max_axis_values=10, max_work=100000, checkpoint=None):
    """Check baseline retention, all plane identities, exact offsets and limits.

    Selection ranking is heuristic and is not a correctness obligation. The
    checker reconstructs formulas directly, never calls the enrichment search.
    """
    work = graph._Work(max_work,checkpoint)
    try:
        m = _prepare(base_axes,start,goal,allowed_bounds,outer_obstacles,radius_m,clearance_m,
                     guard_m,bend_radius_m,minimum_straight_m,max_vertices,max_axis_values,work)
        if not isinstance(result,dict):raise ValueError("Grid proposal object required")
        if result.get("status")=="UNKNOWN":return {"status":"UNKNOWN", "reason":"NO_COMPLETE_GRID", "scope":SCOPE}
        fields={"schema","status","scope","limitations","input_root","input","grid_axes","plane_records",
                "baseline_vertices","proposed_vertices","work","result_root"}
        if set(result)!=fields or result["schema"]!="oma.fabrication-grid-enrichment/1" or result["status"]!="PROPOSED_GRID":
            raise ValueError("Complete grid proposal schema required")
        if (result["input"]!=m["input"] or result["input_root"]!=m["root"] or result["scope"]!=SCOPE
                or digest(result["limitations"])!=digest(LIMITATIONS)):
            raise ValueError("Source model, dimensions, budget or proposal scope differs")
        raw=result["grid_axes"]
        if not isinstance(raw,list) or len(raw)!=3 or any(not isinstance(a,list) or not 2<=len(a)<=max_axis_values for a in raw):
            raise ValueError("Bounded complete output axes required")
        axes=[tuple(map(graph._rational,a)) for a in raw]
        if prod(map(len,axes))>max_vertices:raise ValueError("Output vertex product exceeds budget")
        for i,axis in enumerate(axes):
            if (any(a>=b for a,b in zip(axis,axis[1:])) or not set(m["axes"][i])<=set(axis)
                    or axis[0]<m["inner"][0][i] or axis[-1]>m["inner"][1][i]):
                raise ValueError("Output loses baseline coordinates or leaves allowed bounds")
        expected={}
        if m["bend"] is not None:
            for kind,trims in (("TERMINAL_FIRST_TURN",1),("TERMINAL_TWO_TRIM",2)):
                for name,terminal in (("start",m["start"]),("goal",m["goal"])):
                    for axis in range(3):
                        for sign in (-1,1):
                            expected[(kind,name,axis,sign)]=terminal[axis]+sign*(trims*m["bend"]+m["minimum"]+m["guard"])
        for name,(low,high) in m["boxes"]:
            for axis in range(3):
                expected[("OBSTACLE_FACE",name,axis,0)]=low[axis]-m["radius"]-m["clearance"]-m["guard"]
                expected[("OBSTACLE_FACE",name,axis,1)]=high[axis]+m["radius"]+m["clearance"]+m["guard"]
        records=result["plane_records"]
        if not isinstance(records,list) or len(records)!=len(expected):raise ValueError("Complete source-plane denominator required")
        seen,justified,added=set(),[set() for _ in range(3)],[set() for _ in range(3)]
        for row in records:
            work.tick()
            if not isinstance(row,dict) or set(row)!={"key","axis","value","disposition"}:
                raise ValueError("Complete plane provenance row required")
            key=row["key"]
            if (not isinstance(key,list) or len(key)!=4 or not isinstance(key[0],str) or not isinstance(key[1],str)
                    or type(key[2]) is not int or type(key[3]) is not int or type(row["axis"]) is not int):
                raise ValueError("Typed plane identity required")
            key=tuple(key)
            if key in seen or key not in expected or row["axis"]!=key[2]:raise ValueError("Duplicate or invented source plane")
            seen.add(key);axis=key[2];value=graph._rational(row["value"])
            if value!=expected[key]:raise ValueError("Plane coordinate differs from its exact source offset")
            disposition=row["disposition"]
            if disposition=="OUTSIDE_ERODED_ALLOWED_BOUNDS":
                if m["inner"][0][axis]<=value<=m["inner"][1][axis]:raise ValueError("False outside-plane disposition")
            elif disposition in {"BASELINE_COORDINATE","RETAINED_COORDINATE","ADDED_COORDINATE"}:
                if value not in axes[axis]:raise ValueError("Retained plane coordinate missing")
                if disposition=="BASELINE_COORDINATE" and value not in m["axes"][axis]:raise ValueError("False baseline provenance")
                if disposition!="BASELINE_COORDINATE" and value in m["axes"][axis]:raise ValueError("Baseline coordinate falsely labeled new")
                if disposition=="ADDED_COORDINATE":
                    if value in added[axis]:raise ValueError("Coordinate has duplicate addition witnesses")
                    added[axis].add(value)
                justified[axis].add(value)
            elif disposition in {"AXIS_VALUE_BUDGET","GRID_VERTEX_BUDGET"}:
                if not m["inner"][0][axis]<=value<=m["inner"][1][axis] or value in axes[axis]:raise ValueError("False omitted plane")
                if disposition=="AXIS_VALUE_BUDGET" and len(axes[axis])<max_axis_values:raise ValueError("Axis budget not exhausted")
                if disposition=="GRID_VERTEX_BUDGET" and (len(axes[axis])+1)*prod(len(axes[i]) for i in range(3) if i!=axis)<=max_vertices:
                    raise ValueError("Vertex budget not exhausted")
            else:raise ValueError("Unknown plane disposition")
        if any(set(axis)-set(m["axes"][i])!=added[i] for i,axis in enumerate(axes)):
            raise ValueError("An added coordinate has no retained source-plane witness")
        if (type(result["baseline_vertices"]) is not int or result["baseline_vertices"]!=prod(map(len,m["axes"]))
                or type(result["proposed_vertices"]) is not int or result["proposed_vertices"]!=prod(map(len,axes))
                or type(result["work"]) is not int or not 0<=result["work"]<=10000000):
            raise ValueError("Grid count or work metadata differs")
        if digest({k:v for k,v in result.items() if k!="result_root"})!=result["result_root"]:
            raise ValueError("Grid proposal content root differs")
        work.pulse("fabrication_grid_verified")
        return {"status":"PASS", "scope":SCOPE, "input_root":m["root"], "result_root":result["result_root"],
                "baseline_preserved":True, "source_planes_accounted":len(seen), "proposed_vertices":prod(map(len,axes)),
                "limitations":deepcopy(LIMITATIONS)}
    except graph._Exhausted as exc:
        if work.callback_error is exc:raise
        return {"status":"UNKNOWN", "reason":str(exc), "scope":SCOPE}
    except (ValueError,TypeError,KeyError,IndexError,OverflowError,ZeroDivisionError) as exc:
        if work.callback_error is exc:raise
        return {"status":"FAIL", "reason":str(exc), "scope":SCOPE}
