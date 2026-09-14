"""Source-bound finite fabrication search with independently checked coverage.

All source support comes from a freshly produced cell-adapter inventory. Its
ball-path omissions are deliberately not transferred: fabrication omissions
must separate obstacles from the entire permitted body region. Numerical IFC
support assumptions remain explicit, and every output still needs native DRC.
"""
from copy import deepcopy
from fractions import Fraction as Q
from hashlib import sha256
from pathlib import Path
import time

from oma.build_identity import checker_version
from oma.optimization.fabrication import compile_orthogonal_fabrication, verify_orthogonal_fabrication
from oma.optimization.rectilinear_opening import _q
from oma.store import digest
from . import certified_cells
from .scenario import RoutingScenario


def verify_body_outer_coverage(source_coverage, coverage, *, checkpoint=None):
    """Check every support box, union group and whole-body-region omission."""
    check = certified_cells._CoverageCheckpoints(checkpoint)
    try:
        check("fabrication_coverage_source_root")
        if source_coverage["blockers"] or coverage["source_coverage_root"] != digest(source_coverage):
            raise ValueError("Source support is blocked or the original coverage identity changed")
        originals = {o["id"]:o for o in check.items(source_coverage["objects"], "fabrication_coverage_originals")}
        entries = {o["id"]:o for o in check.items(coverage["entries"], "fabrication_coverage_entries")}
        groups = {g["id"]:certified_cells._box(g["bounds"]) for g in check.items(coverage["outer_obstacles"], "fabrication_coverage_groups")}
        if (len(originals) != len(source_coverage["objects"]) or len(entries) != len(coverage["entries"])
                or set(entries) != set(originals) or len(groups) != len(coverage["outer_obstacles"])):
            raise ValueError("Complete unique source support and group inventories required")
        allowed = certified_cells._box(coverage["allowed_bounds"])
        clearance = _q(coverage["clearance_m"])
        if clearance < 0:
            raise ValueError("Negative declared clearance")
        used, omitted = set(), 0
        for rid, item in check.items(entries.items(), "fabrication_coverage_support_replay"):
            box = certified_cells._box(originals[rid]["bounds_m"])
            if item["disposition"] == "GROUPED":
                if set(item) != {"id","disposition","group_id"}:
                    raise ValueError("Unexpected grouped support fields")
                parent = groups[item["group_id"]]
                if not all(a <= c <= d <= b for a,b,c,d in zip(*parent,*box)):
                    raise ValueError("Fabrication group omits original physical support")
                used.add(item["group_id"])
            elif item["disposition"] == "OUTSIDE_FULL_ALLOWED_BODY_REGION":
                if set(item) != {"id","disposition","normal"} or len(item["normal"]) != 3:
                    raise ValueError("Unexpected exclusion plane fields")
                n = tuple(map(_q,item["normal"]))
                upper = sum((x*allowed[1 if x >= 0 else 0][i] for i,x in enumerate(n)),Q(0))
                lower = sum((x*box[0 if x >= 0 else 1][i] for i,x in enumerate(n)),Q(0))
                norm = sum(x*x for x in n)
                if norm <= 0 or lower <= upper or (lower-upper)**2 <= clearance**2*norm:
                    raise ValueError("Omission does not separate the entire allowed body region with clearance")
                omitted += 1
            else:
                raise ValueError("Unknown physical support disposition")
        if used != set(groups):
            raise ValueError("Unreferenced fabrication support group")
        check("fabrication_coverage_complete")
        return {"status":"PASS", "loaded_obstacles":len(originals), "outer_groups":len(groups),
            "omitted_with_full_body_region_proof":omitted,
            "scope":"EXACT_COMPLETE_BOUNDING_BOX_ACCOUNTING; SOURCE_SUPPORT_AUTHENTICITY_EXTERNAL"}
    except (ValueError,KeyError,TypeError,IndexError,OverflowError) as error:
        if check.failure is error:
            raise
        return {"status":"FAIL", "reason":str(error)}


def body_outer_coverage(source_coverage, scenario, maximum, *, checkpoint=None):
    check = certified_cells._CoverageCheckpoints(checkpoint)
    check("fabrication_body_coverage_start")
    if type(maximum) is not int or not 1 <= maximum <= 256:
        raise ValueError("Finite outer group budget required")
    allowed = certified_cells._box([scenario.allowed_zone.min,scenario.allowed_zone.max])
    clearance = _q(scenario.clearance_m)
    entries, near = [], []
    for obj in check.items(source_coverage["objects"], "fabrication_body_coverage_dispositions"):
        bounds = certified_cells._box(obj["bounds_m"])
        normal = certified_cells._plane(allowed,bounds,clearance)
        if normal is not None:
            entries.append({"id":obj["id"], "disposition":"OUTSIDE_FULL_ALLOWED_BODY_REGION", "normal":[str(x) for x in normal]})
        else:
            near.append({"id":obj["id"], "_bounds":bounds})
    groups = certified_cells._group_boxes(near,maximum,checkpoint=check)
    entries.extend({"id":o["id"],"disposition":"GROUPED","group_id":o["group_id"]}
        for o in check.items(near, "fabrication_body_coverage_entries"))
    def entry_key(entry):
        check.tick("fabrication_body_coverage_sort_keys")
        return entry["id"]
    result = {"source_coverage_root":digest(source_coverage),
        "allowed_bounds":certified_cells._json_box(allowed), "clearance_m":str(clearance),
        "entries":sorted(entries,key=entry_key), "outer_obstacles":groups}
    check("fabrication_body_coverage_complete")
    return result


class _Deadline(Exception):
    pass


def build_certified_fabrication_proposals(source_specs, scenario, source_report, *, context_root,
        grid_divisions=4, max_outer_boxes=128, max_states=12000, max_work=150000, deadline=None, checkpoint=None):
    """Create bounded fabrication-aware proposals from complete source support.

    The source report must come from the current source-bound adapter invocation.
    Its content identity, executable dependencies, full coverage and actual input
    files are checked again. A self-authored replacement report is not assumed
    authentic merely because it can be hashed.
    """
    started = time.monotonic()
    result = {"schema":"oma.ifc-fabrication-search-proposals/1", "status":"UNKNOWN", "proposals":[],
        "context_root":context_root, "candidate_acceptance_authority":False,
        "physical_infeasibility_claim":False, "source_assumptions":deepcopy(source_report.get("assumptions",{})),
        "source_report_root":source_report.get("report_root"), "executable_version":checker_version()}

    caller_check = certified_cells._CoverageCheckpoints(checkpoint)
    def check(stage="fabrication_graph"):
        caller_check(stage)
        if deadline is not None and time.monotonic() >= deadline:
            raise _Deadline()

    def source_hash(path):
        h = sha256()
        with Path(path).open("rb") as stream:
            while block := stream.read(8*1024*1024):
                check("fabrication_source_hash")
                h.update(block)
        return h.hexdigest()

    def finish(status, reason=None):
        result["status"] = status
        if reason:
            result["reason"] = reason
        result["report_root"] = digest(result)
        result["timing"] = {"total_seconds":time.monotonic()-started}
        return result

    try:
        check()
        scenario = RoutingScenario.model_validate(scenario) if isinstance(scenario,dict) else scenario
        if scenario.authorized_opening is not None or scenario.system_type == "GRAVITY_DRAINAGE":
            return finish("BLOCKED_NOT_APPLICABLE","Edited hosts and gravity slope states need their separate physical models")
        if type(grid_divisions) is not int or not 1 <= grid_divisions <= 6:
            raise ValueError("Grid subdivisions must be bounded from 1 to 6")
        if not isinstance(context_root,str) or not context_root:
            raise ValueError("Immutable source and mission context required")
        if (source_report["status"] not in {"CHECKED_GEOMETRIC_PROPOSALS","UNKNOWN"}
                or source_report.get("scenario_root") != digest(scenario.model_dump(mode="json"))
                or source_report.get("dependency_code_sha256") != certified_cells._DEPENDENCY_HASHES
                or source_report.get("adapter_code_sha256") != certified_cells.CODE_SHA256):
            raise ValueError("Complete current source support for this scenario is unavailable")
        content = {k:v for k,v in source_report.items() if k not in {"report_root","timing"}}
        if digest(content) != source_report["report_root"]:
            raise ValueError("Source report content identity changed")
        claimed = source_report["sources"]
        expected = [{"path":str(Path(s["path"]).resolve()),"sha256":s["sha256"],"transform_m":s["transform_m"]} for s in source_specs]
        if not expected or digest(claimed) != digest(expected):
            raise ValueError("Complete source path/hash/frame sequence changed")
        for source in expected:
            if source_hash(source["path"]) != source["sha256"]:
                raise ValueError("Source bytes changed before fabrication model compilation")
        original = source_report["coverage"]
        source_check = certified_cells.verify_cell_coverage(original,source_report["model"],checkpoint=check)
        if source_check["status"] != "PASS":
            raise ValueError("Complete original source physical coverage replay failed")
        result["source_coverage_check"] = source_check
        coverage = body_outer_coverage(original,scenario,max_outer_boxes,checkpoint=check)
        coverage_check = verify_body_outer_coverage(original,coverage,checkpoint=check)
        result.update(coverage=coverage,coverage_check=coverage_check)
        if coverage_check["status"] != "PASS":
            raise ValueError("Independent full-body support accounting failed")
        radius = _q(scenario.diameter_m)/2 + _q(scenario.insulation_m)
        allowed = certified_cells._box(coverage["allowed_bounds"])
        axes = []
        for axis,(lo,hi) in enumerate(zip(*allowed)):
            lo,hi = lo+radius,hi-radius
            start,goal = _q(scenario.start[axis]),_q(scenario.end[axis])
            if lo > hi or not lo <= start <= hi or not lo <= goal <= hi:
                return finish("UNKNOWN","Exact nominal endpoint ball is outside the eroded allowed region")
            axes.append([str(v) for v in sorted({lo+(hi-lo)*i/grid_divisions for i in range(grid_divisions+1)} | {start,goal})])
        problem = {"schema":"oma.fabrication-grid-problem/1", "context_root":context_root,
            "source_roots":{"source_report":source_report["report_root"],"source_coverage":digest(original),
                "body_outer_coverage":digest(coverage),"executable":result["executable_version"]},
            "allowed_bounds":coverage["allowed_bounds"],"grid_axes":axes,
            "start":list(scenario.start),"goal":list(scenario.end),
            "diameter_m":scenario.diameter_m,"insulation_m":scenario.insulation_m,"bend_radius_m":scenario.bend_radius_m,
            "minimum_straight_m":scenario.minimum_straight_m,"clearance_m":scenario.clearance_m,
            "outer_obstacles":coverage["outer_obstacles"]}
        result["model"] = problem
        model_root = result["model_root"] = digest(problem)
        from oma.optimization.fabrication_search import compile_fabrication_search, verify_fabrication_search
        certificate = compile_fabrication_search(problem,max_states=max_states,max_work=max_work,checkpoint=check)
        result["certificate"] = certificate
        check("fabrication_graph_independent_replay")
        checked = verify_fabrication_search(problem,certificate,max_states=max_states,max_work=max_work,checkpoint=check)
        result["independent_check"] = checked
        if checked["status"] != "PASS" or checked.get("geometry_outcome") != "PATH":
            return finish("UNKNOWN","No checked fabrication path in the declared finite graph; no physical impossibility inferred")
        points = [[float(_q(x)) for x in p] for p in certificate["points_m"]]
        float_context = digest({"problem_root":model_root,"certificate_root":digest(certificate),"points_m":points})
        final = compile_orthogonal_fabrication(scenario,points,context_root=float_context,
            outer_obstacles=coverage["outer_obstacles"],outer_model_root=digest(coverage))
        replay = verify_orthogonal_fabrication(scenario,points,final,context_root=float_context,
            outer_obstacles=coverage["outer_obstacles"],outer_model_root=digest(coverage))
        result.update(binary64_fabrication_certificate=final,binary64_fabrication_check=replay)
        if replay["status"] != "PASS" or replay["fabrication_status"] != "PASS":
            return finish("UNKNOWN","Binary64 conversion has no passing complete nominal fabrication proof")
        check("fabrication_graph_publish")
        for source in expected:
            if source_hash(source["path"]) != source["sha256"]:
                raise ValueError("Original source bytes changed during fabrication search")
        if checker_version() != result["executable_version"]:
            raise ValueError("Source implementation changed during fabrication search")
        check("fabrication_proposal_publish")
        result["proposals"] = [{"points_m":points,
            "rationale":"Independently checked finite fabrication-state path with complete source outer coverage; actual IFC and service checks pending",
            "geometry_scope":"EXACT_NOMINAL_ORTHOGONAL_BODY_IN_DECLARED_SOURCE_OUTER_MODEL",
            "candidate_acceptance_authority":False,"physical_infeasibility_claim":False}]
        return finish("CHECKED_FABRICATION_PROPOSALS")
    except _Deadline as error:
        if caller_check.failure is error:
            raise
        result["proposals"] = []
        return finish("UNKNOWN","FABRICATION_SEARCH_DEADLINE")
    except (ValueError,KeyError,TypeError,OSError,RuntimeError,OverflowError) as error:
        if caller_check.failure is error:
            raise
        result["proposals"] = []
        return finish("BLOCKED",str(error))
