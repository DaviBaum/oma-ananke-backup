"""Source-bound outer geometry and independently checked route proposals.

Only a translating-ball model is certified. Native bounds retain numerical
conversion/cache assumptions. No occupied inner geometry or physical
infeasibility is inferred; every emitted route still needs materialization and
the complete independent physical checker.
"""
from copy import deepcopy
from fractions import Fraction as Q
from hashlib import sha256
from itertools import permutations, product
from pathlib import Path
import time

import numpy as np

from oma.exact import capsule_box_clearance, capsule_within_box
from oma.ifc import cad
from oma.ifc.federation import audited_local_federation
from oma.optimization import route_cells
from oma.optimization.rectilinear_opening import _q
from oma.store import digest
from .scenario import RoutingScenario


CODE_SHA256 = sha256(Path(__file__).read_bytes()).hexdigest()
_DEPENDENCY_PATHS = [Path(route_cells.__file__), Path(cad.__file__),
    Path(cad.__file__).with_name("enclosure.py"), Path(cad.__file__).with_name("cad_cache.py"),
    Path(cad.__file__).with_name("federation.py"), Path(route_cells.__file__).parents[1]/"exact.py",
    *[Path(route_cells.__file__).with_name(name) for name in ("physical.py","rectilinear_opening.py","finite.py","fdqa.py")],
    Path(__file__)]
if Path(cad.__file__).with_name("inventory.py").exists():
    _DEPENDENCY_PATHS.append(Path(cad.__file__).with_name("inventory.py"))
_DEPENDENCY_HASHES = {str(p):sha256(p.read_bytes()).hexdigest() for p in _DEPENDENCY_PATHS}
ASSUMPTIONS = {
    "geometry": "COMPLETE_REPRESENTED_IFC_SUPPORT; UNDOCUMENTED_REAL_WORLD_EXTENT_NOT_CHECKED",
    "native_outer_bounds": "NUMERICAL_IFCOPENSHELL_OPENCASCADE_CONVERSION_AND_BREP_BOUND_ENCLOSURE_ASSUMED",
    "native_error": "SOURCE_NATIVE_BOX_EXPANDED_BY_KERNEL_TOLERANCE_PLUS_DECLARED_NUMERICAL_ALLOWANCE",
    "native_cache": cad.CACHE_TRUST,
    "frames": "AUDITED_LOCAL_ENGINEERING_ANCHORS; EXACT_AFFINE_IMAGE_AT_DECLARED_BINARY64_MATRIX; NOT_SURVEY_CERTIFICATION",
    "inner_occupancy": "EMPTY; NO_IFC_PHYSICAL_INFEASIBILITY_TRANSFER",
    "body": "CLOSED_TRANSLATING_BALL; FABRICATED_ELBOW_CONTAINMENT_NOT_CHECKED",
    "acceptance": "PROPOSAL_ONLY; FRESH_FULL_NATIVE_ROUTE_AND_SERVICE_CHECKS_REQUIRED",
}


class _Deadline(Exception):
    pass


class _ProposalBudget(Exception):
    pass


class _CoverageCheckpoints:
    """Cooperative traversal checks which preserve caller exception identity."""

    def __init__(self, callback):
        self.callback = callback
        self.failure = None
        self.counts = {}

    def __call__(self, stage):
        if self.callback is not None:
            try:
                self.callback(stage)
            except BaseException as exc:
                self.failure = exc
                raise

    def tick(self, stage):
        count = self.counts.get(stage, 0)
        if count % 64 == 0:
            self(stage)
        self.counts[stage] = count + 1

    def items(self, values, stage):
        for value in values:
            self.tick(stage)
            yield value
        self(stage)


def _box(value):
    result = tuple(tuple(_q(v) for v in row) for row in value)
    if len(result) != 2 or any(len(row) != 3 for row in result) or any(a > b for a, b in zip(*result)):
        raise ValueError("Invalid finite rational bounds")
    return result


def _json_box(value):
    return [[str(v) for v in row] for row in value]


def _affine_box(box, matrix):
    lo, hi = box
    lower, upper = [], []
    for row in matrix[:3]:
        a = b = _q(float(row[3]))
        for coefficient, left, right in zip(row[:3], lo, hi):
            c = _q(float(coefficient))
            a += min(c * left, c * right)
            b += max(c * left, c * right)
        lower.append(a)
        upper.append(b)
    return tuple(lower), tuple(upper)


def _plane(domain, obstacle, threshold):
    normal = tuple(obstacle[0][i] - domain[1][i] if domain[1][i] < obstacle[0][i]
                   else obstacle[1][i] - domain[0][i] if obstacle[1][i] < domain[0][i] else Q(0) for i in range(3))
    return normal if sum(n*n for n in normal) > threshold*threshold else None


def verify_cell_coverage(coverage, problem, *, checkpoint=None):
    """Independent exact check of complete grouping and out-of-zone omissions.

    This verifies the finite coverage algebra, not IFC/native authenticity.
    The caller binds the inventory to freshly loaded and hashed source bytes.
    """
    check = _CoverageCheckpoints(checkpoint)
    try:
        check("cell_coverage_inventory")
        if coverage["blockers"] or problem["inner_obstacles"]:
            raise ValueError("Blocked coverage or unsupported inner occupancy")
        objects = {o["id"]: o for o in check.items(coverage["objects"], "cell_coverage_objects")}
        if len(objects) != len(coverage["objects"]):
            raise ValueError("Duplicate loaded physical identity")
        expected = set(check.items(coverage["physical_ids"], "cell_coverage_physical_ids"))
        if len(expected) != len(coverage["physical_ids"]):
            raise ValueError("Duplicate original physical identity")
        assemblies = {o["id"]: o["children"] for o in check.items(coverage["assemblies"], "cell_coverage_assemblies")}
        if len(assemblies) != len(coverage["assemblies"]) or set(objects) & set(assemblies) or set(objects) | set(assemblies) != expected:
            raise ValueError("Original physical denominator does not equal objects plus assemblies")
        def grounded(key, active):
            check.tick("cell_coverage_assembly_traversal")
            if key in objects:
                return True
            children = assemblies.get(key, [])
            return (bool(children) and key not in active
                and len(children) == len(set(check.items(children, "cell_coverage_assembly_children")))
                and all(grounded(c, active | {key}) for c in children))
        if not all(grounded(a, set()) for a in check.items(assemblies, "cell_coverage_assembly_roots")):
            raise ValueError("Uncovered or cyclic representation-free assembly")
        groups = {o["id"]: _box(o["bounds"]) for o in check.items(problem["outer_obstacles"], "cell_coverage_groups")}
        if len(groups) != len(problem["outer_obstacles"]):
            raise ValueError("Duplicate grouped obstacle")
        allowed = _box(problem["allowed_bounds"])
        radius, clearance = _q(problem["body_radius"]), _q(problem["clearance"])
        domain = (tuple(v+radius for v in allowed[0]), tuple(v-radius for v in allowed[1]))
        seen = set()
        for obj in check.items(coverage["objects"], "cell_coverage_support_replay"):
            bounds = _box(obj["bounds_m"])
            source = _box(obj["source_bounds_m"])
            matrix = obj["source_to_common_matrix"]
            for corner in product(*zip(*source)):
                image = [sum((_q(float(row[i]))*corner[i] for i in range(3)), _q(float(row[3]))) for row in matrix[:3]]
                if len(image) != 3 or not all(a <= v <= b for a,v,b in zip(bounds[0],image,bounds[1])):
                    raise ValueError("Outer bound omits a declared transformed support corner")
            if obj["disposition"] == "GROUPED_OUTER_COVER":
                parent = groups[obj["group_id"]]
                if not all(a <= c <= d <= b for a, b, c, d in zip(*parent, *bounds)):
                    raise ValueError("Grouped cover omits original obstacle support")
                seen.add(obj["group_id"])
            elif obj["disposition"] == "CERTIFIED_OUTSIDE_COMPLETE_CENTRE_DOMAIN":
                n = tuple(_q(v) for v in obj["separating_normal"])
                if len(n) != 3:
                    raise ValueError("Invalid exclusion plane")
                upper = sum((v*(domain[1][i] if v >= 0 else domain[0][i]) for i,v in enumerate(n)), Q(0))
                lower = sum((v*(bounds[0][i] if v >= 0 else bounds[1][i]) for i,v in enumerate(n)), Q(0))
                norm = sum(v*v for v in n)
                if norm <= 0 or lower <= upper or (lower-upper)**2 <= (radius+clearance)**2*norm:
                    raise ValueError("Omitted obstacle is not separated from the complete allowed model")
            else:
                raise ValueError("Unaccounted physical obstacle")
        if seen != set(groups):
            raise ValueError("Extraneous or unreferenced grouped geometry")
        check("cell_coverage_complete")
        return {"status":"PASS", "physical_elements":len(expected), "loaded_obstacles":len(objects),
                "representation_free_assemblies":len(assemblies), "model_groups":len(groups),
                "scope":"EXACT_FINITE_OUTER_COVER_ACCOUNTING; SOURCE_AUTHENTICITY_IS_EXTERNAL"}
    except (ValueError, KeyError, TypeError, IndexError, RecursionError) as exc:
        if check.failure is exc:
            raise
        return {"status":"FAIL", "reason":str(exc)}


def _group_boxes(objects, maximum, *, checkpoint=None):
    # Deterministic spatial splitting. Every leaf is a conservative union box;
    # no individual object is dropped when the kernel's box limit is reached.
    check = _CoverageCheckpoints(checkpoint)
    check("cell_group_start")
    def coordinate(obj, side, axis):
        check.tick("cell_group_bounds")
        return obj["_bounds"][side][axis]
    def sort_key(obj):
        check.tick("cell_group_sort_keys")
        return sum(row[axis] for row in obj["_bounds"]), obj["id"]
    groups = [objects] if objects else []
    while len(groups) < maximum:
        candidates = [(len(g), i) for i,g in enumerate(check.items(groups, "cell_group_partition")) if len(g) > 1]
        if not candidates:
            break
        _, index = max(candidates)
        group = groups.pop(index)
        axis = max(range(3), key=lambda a: max(coordinate(o,1,a) for o in group)-min(coordinate(o,0,a) for o in group))
        group.sort(key=sort_key)
        check("cell_group_sorted")
        mid = len(group)//2
        groups.extend((group[:mid], group[mid:]))
    result = []
    for i, members in enumerate(check.items(groups, "cell_group_output")):
        name = f"outer-group:{i}"
        bounds = (tuple(min(coordinate(o,0,a) for o in members) for a in range(3)),
                  tuple(max(coordinate(o,1,a) for o in members) for a in range(3)))
        result.append({"id":name, "bounds":_json_box(bounds)})
        for obj in check.items(members, "cell_group_members"):
            obj.update(disposition="GROUPED_OUTER_COVER", group_id=name)
    check("cell_group_complete")
    return result


def _checked_float_paths(problem, certificate, checkpoint, max_work):
    exact = certificate.get("inner_path")
    if exact is None:
        return []
    radius, clearance = _q(problem["body_radius"]), _q(problem["clearance"])
    allowed = _box(problem["allowed_bounds"])
    obstacles = [_box(o["bounds"]) for o in problem["outer_obstacles"]]
    used = 0
    def clear(a, b):
        nonlocal used
        checkpoint("cell_proposal_embedding")
        used += 1+len(obstacles)
        if used > max_work:
            raise _ProposalBudget()
        return (capsule_within_box(a,b,radius,*allowed)["verdict"] == "PASS"
            and all(capsule_box_clearance(a,b,radius,*box,required_clearance=clearance)["verdict"] == "PASS" for box in obstacles))
    original = [[float(_q(v)) for v in p] for p in exact]
    if not all(clear(a,b) for a,b in zip(original, original[1:])):
        return []  # Binary64 conversion is another geometry change and is checked.
    # A checked cell path can contain short portal steps that do not admit a
    # fabrication fillet. Propose simple side detours at its witnessed offsets,
    # checking their entire capsule afresh rather than trusting the old path.
    simple = []
    start,goal = original[0],original[-1]
    main = [i for i in range(3) if start[i] != goal[i]]
    if len(main) == 1:
        for axis in (i for i in range(3) if i != main[0]):
            offsets = sorted({p[axis] for p in original if p[axis] != start[axis]},key=lambda v:(abs(v-start[axis]),v))[:24]
            for offset in offsets:
                first,second = list(start),list(goal)
                first[axis] = second[axis] = offset
                path = [start,first,second,goal]
                if all(clear(a,b) for a,b in zip(path,path[1:])):
                    simple.append(path)
        simple.sort(key=lambda path:sum(abs(a[i]-b[i]) for a,b in zip(path,path[1:]) for i in range(3)))
    orthogonal = [original[0]]
    for a,b in zip(original, original[1:]):
        found = None
        for order in permutations(range(3)):
            path = [a]
            for axis in order:
                point = list(path[-1]); point[axis] = b[axis]
                if point != path[-1]:
                    path.append(point)
            if all(clear(x,y) for x,y in zip(path,path[1:])):
                found = path
                break
        if found is None:
            orthogonal = None
            break
        orthogonal.extend(found[1:])
    if orthogonal:
        simplified = []
        for point in orthogonal:
            if len(simplified) > 1:
                a,b = simplified[-2:]
                da = [b[i]-a[i] for i in range(3)]
                db = [point[i]-b[i] for i in range(3)]
                if sum(x != 0 for x in da) == sum(x != 0 for x in db) == 1 and any(x*y > 0 for x,y in zip(da,db)):
                    simplified.pop()
            simplified.append(point)
        orthogonal = simplified
    paths = simple[:2]
    if orthogonal and orthogonal not in paths:
        paths.append(orthogonal)
    if original not in paths:
        paths.append(original)
    return [{"points_m":p, "rationale":"Independently checked translating-ball path from complete IFC outer support; physical fitting and service checks pending",
             "geometry_scope":"EXACT_BINARY64_PATH_IN_DECLARED_OUTER_MODEL", "route_acceptance":False,
             "embedding_check":{"status":"PASS","method":"FRESH_EXACT_CAPSULE_TO_EVERY_OUTER_GROUP_AND_ALLOWED_ZONE","segments":len(p)-1,"outer_groups":len(obstacles)},
             "physical_infeasibility_claim":False} for p in paths]


def build_certified_cell_proposals(source_specs, scenario, *, context_root, coordinate_evidence=None,
        cache_directory=None, grid_divisions=4, max_cells=256, max_work=500_000, max_outer_boxes=128,
        numerical_allowance_m=1e-6, deadline=None, checkpoint=None):
    """Fresh source coverage -> exact cell certificate -> checked proposals.

    source_specs is the complete sequence of {path, sha256, transform_m} in the
    calling baseline. A context root must bind that baseline and fixed scenario.
    Native conversion calls are cooperative; a containing worker supplies hard
    wall-time termination. This function returns UNKNOWN after budget expiry.
    """
    started = time.monotonic()
    result = {"schema":"oma.ifc-certified-cell-proposals/1", "status":"UNKNOWN", "proposals":[],
              "certificate":None, "independent_check":None, "model":None,
              "coverage":{"physical_ids":[], "objects":[], "assemblies":[], "blockers":[]},
              "assumptions":deepcopy(ASSUMPTIONS), "context_root":context_root, "adapter_code_sha256":CODE_SHA256,
              "dependency_code_sha256":deepcopy(_DEPENDENCY_HASHES)}
    coverage = result["coverage"]
    caller_check = _CoverageCheckpoints(checkpoint)
    def check(stage):
        caller_check(stage)
        if deadline is not None and time.monotonic() >= deadline:
            raise _Deadline()
    traversal = _CoverageCheckpoints(check)
    def finish(status, reason=None):
        result["status"] = status
        if reason: result["reason"] = reason
        result["coverage_root"] = digest(coverage)
        result["model_root"] = digest(result["model"]) if result["model"] else None
        result["report_root"] = digest(result)
        result["timing"] = {"total_seconds":time.monotonic()-started}
        return result
    try:
        check("cell_source_start")
        if any(sha256(p.read_bytes()).hexdigest() != _DEPENDENCY_HASHES[str(p)] for p in _DEPENDENCY_PATHS):
            return finish("BLOCKED", "Loaded geometry implementation differs from current source files")
        scenario = RoutingScenario.model_validate(scenario) if isinstance(scenario,dict) else scenario
        if not isinstance(scenario, RoutingScenario) or not isinstance(context_root,str) or not context_root:
            raise ValueError("Typed scenario and immutable context root required")
        result["scenario_root"] = digest(scenario.model_dump(mode="json"))
        if scenario.authorized_opening is not None:
            return finish("BLOCKED_NOT_APPLICABLE", "Original host support cannot certify a requested edited-host model")
        if (type(grid_divisions) is not int or not 1 <= grid_divisions <= 16 or type(max_outer_boxes) is not int
                or not 1 <= max_outer_boxes <= 256 or type(max_cells) is not int or max_cells < 1
                or type(max_work) is not int or not 1 <= max_work <= 5_000_000):
            raise ValueError("Invalid bounded cell/group/work budget")
        allowance = _q(numerical_allowance_m)
        if allowance <= 0:
            raise ValueError("Positive finite native numerical allowance required")
        result["numerical_allowance_m"] = str(allowance)
        specs, hashes = [], set()
        def file_hash(path):
            h = sha256()
            with Path(path).open("rb") as stream:
                while chunk := stream.read(8*1024*1024):
                    check("cell_source_hash")
                    h.update(chunk)
            return h.hexdigest()
        if not isinstance(source_specs,(list,tuple)) or not source_specs:
            raise ValueError("Complete nonempty immutable source specifications required")
        for item in source_specs:
            check("cell_source_identity")
            if not isinstance(item,dict) or set(item) != {"path","sha256","transform_m"}:
                raise ValueError("Exact source path/hash/frame schema required")
            source_hash = file_hash(item["path"])
            if source_hash != item["sha256"] or source_hash in hashes:
                raise ValueError("Source hash mismatch or duplicate source bytes")
            matrix = np.asarray(item["transform_m"],dtype=float)
            if (matrix.shape != (4,4) or not np.isfinite(matrix).all() or not np.array_equal(matrix[3],[0.,0.,0.,1.])
                    or not np.allclose(matrix[:3,:3].T@matrix[:3,:3],np.eye(3),rtol=0,atol=1e-9) or np.linalg.det(matrix[:3,:3]) <= 0):
                raise ValueError("Missing or unsupported proper rigid source frame")
            specs.append({"path":str(Path(item["path"]).resolve()),"sha256":source_hash,"transform_m":matrix.tolist()})
            hashes.add(source_hash)
        if len(specs) == 1:
            if not np.array_equal(specs[0]["transform_m"],np.eye(4)):
                raise ValueError("Single-source local proposal requires the unchanged identity frame")
            frame = {"status":"VERIFIED_SOURCE_LOCAL_IDENTITY", "sources":specs, "global_survey_claim":False}
        else:
            if not coordinate_evidence or coordinate_evidence.get("status") != "VERIFIED":
                raise ValueError("Multiple sources require an audited common frame")
            frame = audited_local_federation([{"source_path":s["path"],"source_sha256":s["sha256"],"units":{"status":"KNOWN"}} for s in specs],
                coordinate_evidence.get("reference_source_sha256"), checkpoint=check)
            if frame["status"] != "VERIFIED":
                raise ValueError("Source common-frame audit is unresolved")
            derived = {s["source_sha256"]:s["transform"] for s in frame["sources"]}
            claimed = coordinate_evidence.get("sources",[])
            if len(claimed) != len(specs) or {s["source_sha256"] for s in claimed} != hashes:
                raise ValueError("Claimed frame source denominator differs")
            if any(not np.array_equal(s["transform_m"],derived[s["sha256"]]) for s in specs) or any(not np.array_equal(s["transform"],derived[s["source_sha256"]]) for s in claimed):
                raise ValueError("Claimed source frame differs from the fresh anchor audit")
        result["sources"], result["frame_evidence"] = specs, frame
        import ifcopenshell
        for spec in specs:
            check("cell_source_inventory")
            source_model = ifcopenshell.open(spec["path"])
            physical = {e.id():e for e in traversal.items(source_model.by_type("IfcElement"), "cell_source_physical_inventory")
                if not e.is_a("IfcFeatureElementSubtraction")}
            ids = {i:f"{spec['sha256']}:{i}" for i in traversal.items(physical, "cell_source_physical_ids")}
            coverage["physical_ids"].extend(ids.values())
            cache_report = {}
            loaded, failures = cad.load_cad(spec["path"], cache_directory=cache_directory, cache_report=cache_report,
                source_representation_policy=scenario.source_representation_policy, checkpoint=check)
            coverage.setdefault("source_loads",[]).append({"source_sha256":spec["sha256"], "cache":cache_report,
                "physical_elements":len(physical), "loaded_objects":len(loaded), "failures":failures})
            coverage["blockers"].extend(failures)
            loaded_ids = set()
            for obj in loaded:
                check("cell_source_outer_support")
                if (obj.step_id not in physical or obj.step_id in loaded_ids or obj.source_sha256 != spec["sha256"]
                        or obj.entity_id != ids.get(obj.step_id) or obj.guid != physical[obj.step_id].GlobalId):
                    coverage["blockers"].append({"reason":"INVALID_OR_DUPLICATE_LOADED_SOURCE_IDENTITY", "id":obj.entity_id})
                    continue
                loaded_ids.add(obj.step_id)
                support = obj.support_evidence or {}
                if cad._has_native_geometry(obj) and cad._valid_bounds(obj.bounds) and support.get("complete_supported_body_representation"):
                    padding = _q(obj.kernel_tolerance_m)+allowance
                    bounds = (tuple(_q(v)-padding for v in obj.bounds[:3]), tuple(_q(v)+padding for v in obj.bounds[3:]))
                    authority = "NUMERICAL_COMPLETE_NATIVE_SUPPORT_OUTER_BOUND"
                elif not obj.valid and obj.support_kind == "exact_source_support_enclosure":
                    proof = support.get("exact_source_enclosure",{})
                    if (proof.get("status") != "ENCLOSURE_CHECKED" or proof.get("source_sha256") != spec["sha256"]
                            or proof.get("product_step_id") != obj.step_id or proof.get("frame") != "IFC_LOCAL_ENGINEERING_METRES"):
                        coverage["blockers"].append({"reason":"INVALID_SOURCE_ENCLOSURE_BINDING", "id":obj.entity_id}); continue
                    bounds = _box(proof["bounds_m"])
                    authority = "CHECKED_EXACT_SUPPORTED_SOURCE_OUTER_ENCLOSURE"
                else:
                    coverage["blockers"].append({"reason":"UNRESOLVED_PHYSICAL_SUPPORT", "id":obj.entity_id,"native_reason":obj.reason}); continue
                source_bounds = bounds
                bounds = _affine_box(bounds, spec["transform_m"])
                coverage["objects"].append({"id":obj.entity_id,"guid":obj.guid,"ifc_type":obj.ifc_type,
                    "bounds_m":_json_box(bounds),"support_authority":authority,"support_evidence":support,
                    "source_bounds_m":_json_box(source_bounds),"source_to_common_matrix":spec["transform_m"],
                    "source_native_valid":bool(obj.valid),"source_native_reason":obj.reason,"_bounds":bounds})
            for step, entity in traversal.items(physical.items(), "cell_source_assemblies"):
                if step in loaded_ids: continue
                relations = list(getattr(entity,"IsDecomposedBy",())) + list(getattr(entity,"IsNestedBy",()))
                children = [c for rel in traversal.items(relations, "cell_source_assembly_relations")
                    for c in traversal.items(rel.RelatedObjects, "cell_source_assembly_children")]
                if entity.Representation is None and children and all(c.id() in ids for c in traversal.items(children, "cell_source_assembly_identity")):
                    coverage["assemblies"].append({"id":ids[step],"children":[ids[c.id()] for c in traversal.items(children, "cell_source_assembly_ledger")],"scope":"NO_OWN_REPRESENTATION; COMPLETE_PHYSICAL_CHILDREN_REQUIRED"})
                else:
                    coverage["blockers"].append({"reason":"MISSING_PHYSICAL_SOURCE_SUPPORT","id":ids[step]})
            if file_hash(spec["path"]) != spec["sha256"]:
                raise ValueError("Immutable source changed during support loading")
        if coverage["blockers"]:
            for obj in coverage["objects"]: obj.pop("_bounds",None)
            return finish("BLOCKED", "Complete source physical support is unresolved")
        allowed = _box([scenario.allowed_zone.min,scenario.allowed_zone.max])
        radius, clearance = _q(scenario.outer_radius), _q(scenario.clearance_m)
        domain = (tuple(v+radius for v in allowed[0]),tuple(v-radius for v in allowed[1]))
        near = []
        for obj in traversal.items(coverage["objects"], "cell_source_dispositions"):
            normal = _plane(domain,obj["_bounds"],radius+clearance)
            if normal is not None:
                obj.update(disposition="CERTIFIED_OUTSIDE_COMPLETE_CENTRE_DOMAIN",separating_normal=[str(v) for v in normal])
            else:
                near.append(obj)
        outer = _group_boxes(near,max_outer_boxes,checkpoint=check)
        for obj in traversal.items(coverage["objects"], "cell_source_coverage_ledger"): obj.pop("_bounds",None)
        problem = {"allowed_bounds":_json_box(allowed),"body_radius":str(radius),"clearance":str(clearance),
            "outer_obstacles":outer,"inner_obstacles":[],"start":list(scenario.start),"goal":list(scenario.end),
            "grid_axes":[[str(lo+(hi-lo)*i/grid_divisions) for i in range(grid_divisions+1)] for lo,hi in zip(*domain)],
            "context_root":context_root,"source_roots":{"outer_cover":digest(coverage),"inner_occupancy":digest([]),
                "frame":digest(frame),"body_model":digest({"kind":"TRANSLATING_CLOSED_BALL","radius":str(radius),"scenario":result["scenario_root"]})}}
        result["model"] = problem
        coverage_check = verify_cell_coverage(coverage,problem,checkpoint=check)
        result["coverage_check"] = coverage_check
        if coverage_check["status"] != "PASS":
            return finish("BLOCKED", "Independent complete-support accounting failed")
        check("cell_compile")
        certificate = route_cells.compile_route_cells(problem,max_cells=max_cells,max_work=max_work)
        result["certificate"] = certificate
        check("cell_independent_check")
        if certificate["status"] == "UNKNOWN":
            return finish("UNKNOWN",certificate["reason"])
        independent = route_cells.verify_route_cells(problem,certificate,max_cells=max_cells,max_work=max_work)
        result["independent_check"] = independent
        check("cell_checked_proposal")
        if independent["status"] != "PASS":
            return finish("UNKNOWN","Independent cell certificate did not pass within budget")
        if independent["geometry_outcome"] == "OUTER_INFEASIBLE":
            return finish("BLOCKED","Unexpected outer obstruction with empty occupied inner family; no physical claim permitted")
        result["proposals"] = _checked_float_paths(problem,certificate,check,max_work)
        for spec in specs:
            if file_hash(spec["path"]) != spec["sha256"]:
                raise ValueError("Immutable source changed before proposal publication")
        if any(sha256(p.read_bytes()).hexdigest() != _DEPENDENCY_HASHES[str(p)] for p in _DEPENDENCY_PATHS):
            raise ValueError("Geometry implementation changed during proposal checking")
        check("cell_proposal_publish")
        for proposal in result["proposals"]:
            proposal.update(cell_certificate_root=certificate["root"],coverage_root=digest(coverage))
        return finish("CHECKED_GEOMETRIC_PROPOSALS" if result["proposals"] else "UNKNOWN",
                      None if result["proposals"] else "No checked path in the bounded conservative inner graph")
    except _Deadline as exc:
        if caller_check.failure is exc:
            raise
        for obj in coverage["objects"]: obj.pop("_bounds",None)
        result["proposals"] = []
        return finish("UNKNOWN","CERTIFIED_CELL_DEADLINE")
    except _ProposalBudget as exc:
        if caller_check.failure is exc:
            raise
        result["proposals"] = []
        return finish("UNKNOWN","CERTIFIED_CELL_PROPOSAL_EMBEDDING_BUDGET")
    except (ValueError, OSError, KeyError, TypeError, RuntimeError, OverflowError) as exc:
        if caller_check.failure is exc:
            raise
        for obj in coverage["objects"]: obj.pop("_bounds",None)
        result["proposals"] = []
        coverage["blockers"].append({"reason":"SOURCE_MODEL_NOT_APPLICABLE", "detail":str(exc)})
        return finish("BLOCKED",str(exc))
