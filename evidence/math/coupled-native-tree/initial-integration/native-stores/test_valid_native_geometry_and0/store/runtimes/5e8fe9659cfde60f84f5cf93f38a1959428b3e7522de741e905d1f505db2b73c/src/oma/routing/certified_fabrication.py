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


class _PricingDeadline(Exception):
    pass


class _FrontierDeadline(Exception):
    pass


def build_certified_fabrication_proposals(source_specs, scenario, source_report, *, context_root,
        grid_divisions=4, max_outer_boxes=128, max_states=12000, max_work=150000,
        max_pricing_work=500000, max_pi_terms=256, deadline=None, checkpoint=None,
        max_fittings=None, max_frontier_states=24000, max_frontier_work=1000000,
        max_frontier_seconds=3., max_frontier_proposals=8, residual_rounds=0,
        max_residual_seconds=3., max_residual_states=24000, max_residual_work=1000000,
        max_residual_proposals=8):
    """Create bounded fabrication-aware proposals from complete source support.

    The source report must come from the current source-bound adapter invocation.
    Its content identity, executable dependencies, full coverage and actual input
    files are checked again. A self-authored replacement report is not assumed
    authentic merely because it can be hashed.

    A checked feasible graph path is retained before the optional cost phase.
    Pricing proves only the exact nominal objective on this finite graph. Its
    rational coordinates are freshly fabricated after binary64 conversion;
    the converted path has no inherited exact-cost or native acceptance claim.
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

    def source_hash(path, *, callbacks=True):
        h = sha256()
        before = Path(path).stat()
        with Path(path).open("rb") as stream:
            while block := stream.read(8*1024*1024):
                if callbacks:
                    check("fabrication_source_hash")
                elif deadline is not None and time.monotonic() >= deadline:
                    raise _Deadline()
                h.update(block)
        after = Path(path).stat()
        if (before.st_size,before.st_mtime_ns) != (after.st_size,after.st_mtime_ns):
            raise ValueError("Source bytes changed during fabrication input hashing")
        return h.hexdigest()

    def finish(status, reason=None):
        result["status"] = status
        if reason:
            result["reason"] = reason
        result["report_root"] = digest(result)
        result["timing"] = {"total_seconds":time.monotonic()-started}
        return result

    try:
        supplied_scenario = scenario
        def input_binding():
            return digest({"scenario":supplied_scenario.model_dump(mode="json")
                if isinstance(supplied_scenario,RoutingScenario) else supplied_scenario,
                "sources":[{**s,"path":str(Path(s["path"]).resolve())} for s in source_specs],
                "source_report":source_report,"context_root":context_root})
        declared_input_root = input_binding()
        check()
        if type(residual_rounds) is not int or residual_rounds not in (0,1):
            raise ValueError("Residual proposal rounds must be zero or one")
        if residual_rounds and (max_fittings is None
                or type(max_residual_seconds) not in (int,float) or not 0 < max_residual_seconds <= 10
                or type(max_residual_proposals) is not int or not 1 <= max_residual_proposals <= 16):
            raise ValueError("Residual proposals require an explicit fitting count and finite phase/output budgets")
        if max_fittings is not None:
            if type(max_fittings) is not int or not 0 <= max_fittings <= 1024:
                raise ValueError("Declared new-fitting budget must be an integer in [0,1024]")
            if (type(max_frontier_seconds) not in (int,float) or not 0 < max_frontier_seconds <= 10
                    or type(max_frontier_proposals) is not int or not 1 <= max_frontier_proposals <= 33):
                raise ValueError("Finite frontier phase/output budgets required")
            result["fitting_budget"] = {"declared_max_new_fittings":max_fittings,
                "represented_count_cap":min(max_fittings,32),
                "requested_count_domain_within_kernel_cap":max_fittings <= 32,
                "scope":"INDIVIDUAL_EXACT_COUNTS_FOR_OPTIONAL_SHARED_NEW_FITTING_BUDGET",
                "shared_native_budget_feasibility":"NOT_CHECKED",
                "physical_infeasibility_claim":False}
        scenario = RoutingScenario.model_validate(deepcopy(scenario)) if isinstance(scenario,dict) else scenario.model_copy(deep=True)
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
        mission_allowed = certified_cells._box(coverage["allowed_bounds"])
        # Search inside the mission rather than placing nominal bodies exactly
        # on its boundary. This is a declared proposal restriction, not an error
        # certificate for arbitrary native shapes or an altered mission rule.
        boundary_guard = Q(1,10000)
        allowed = (tuple(x+boundary_guard for x in mission_allowed[0]),
            tuple(x-boundary_guard for x in mission_allowed[1]))
        result["search_domain"] = {"mission_allowed_bounds":coverage["allowed_bounds"],
            "graph_allowed_bounds":certified_cells._json_box(allowed),
            "inward_body_search_guard_m":str(boundary_guard),
            "native_error_bound_certified":False,"physical_infeasibility_claim":False}
        axes = []
        for axis,(lo,hi) in enumerate(zip(*allowed)):
            lo,hi = lo+radius,hi-radius
            start,goal = _q(scenario.start[axis]),_q(scenario.end[axis])
            if lo > hi or not lo <= start <= hi or not lo <= goal <= hi:
                return finish("UNKNOWN","Exact nominal endpoint ball is outside the eroded allowed region")
            axes.append([str(v) for v in sorted({lo+(hi-lo)*i/grid_divisions for i in range(grid_divisions+1)} | {start,goal})])
        from .fabrication_grid import enrich_fabrication_grid, verify_fabrication_grid_enrichment
        grid_args = (axes,scenario.start,scenario.end,certified_cells._json_box(allowed),
            coverage["outer_obstacles"],str(radius),scenario.clearance_m)
        grid_options = {"bend_radius_m":scenario.bend_radius_m,
            "minimum_straight_m":scenario.minimum_straight_m,
            "max_axis_values":max(8,max(map(len,axes))),"checkpoint":check}
        enriched = enrich_fabrication_grid(*grid_args,**grid_options)
        enrichment_check = verify_fabrication_grid_enrichment(*grid_args,enriched,**grid_options)
        result.update(grid_enrichment=enriched,grid_enrichment_check=enrichment_check)
        if enrichment_check["status"] == "PASS":
            axes = enriched["grid_axes"]
        problem = {"schema":"oma.fabrication-grid-problem/1", "context_root":context_root,
            "source_roots":{"source_report":source_report["report_root"],"source_coverage":digest(original),
                "body_outer_coverage":digest(coverage),"search_domain":digest(result["search_domain"]),
                "grid_enrichment":digest(enriched),
                "executable":result["executable_version"]},
            "allowed_bounds":certified_cells._json_box(allowed),"grid_axes":axes,
            "start":list(scenario.start),"goal":list(scenario.end),
            "diameter_m":scenario.diameter_m,"insulation_m":scenario.insulation_m,"bend_radius_m":scenario.bend_radius_m,
            "minimum_straight_m":scenario.minimum_straight_m,"clearance_m":scenario.clearance_m,
            "outer_obstacles":coverage["outer_obstacles"]}
        if max_fittings is not None:
            problem["source_roots"]["fitting_budget"] = digest(result["fitting_budget"])
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

        def proposal(path, proof, binary_proof, *, priced=False, proof_root=None):
            return {"points_m":path,
                "rationale":("Independently priced finite fabrication-state path" if priced else
                    "Independently checked feasible finite fabrication-state path") +
                    " with complete source outer coverage; actual IFC and service checks pending",
                "geometry_scope":"EXACT_NOMINAL_ORTHOGONAL_BODY_IN_DECLARED_SOURCE_OUTER_MODEL",
                "path_certificate_kind":"FABRICATION_PRICING" if priced else "FABRICATION_SEARCH",
                "path_certificate_root":proof_root if proof_root is not None else digest(proof),
                "binary64_fabrication_certificate_root":digest(binary_proof),
                "nominal_graph_optimality":priced,
                "binary64_objective_optimality":False,
                "candidate_acceptance_authority":False,"physical_infeasibility_claim":False}

        proposals = [proposal(points,certificate,final)]
        # Use the same declared decimal weight policy as checked candidate
        # selection; nominal geometry still has the graph's exact binary-input
        # interpretation. Missing dimensions have zero weight.
        from oma.optimization.master import rational
        objective = {"schema":"oma.fabrication-grid-cost/1",
            "length_weight":str(rational(scenario.objective_weights.get("length_m",0))),
            "fitting_weight":str(rational(scenario.objective_weights.get("fitting_count",0)))}
        result["pricing_objective"] = objective
        result["pricing_objective_binding"] = {
            "scenario_root":digest(scenario.model_dump(mode="json")),
            "declared_weights":dict(scenario.objective_weights),
            "weight_interpretation":"EXACT_DECLARED_DECIMAL_VALUES",
            "native_numeric_objective_lower_bound":False,
            "continuous_optimality_claim":False}
        frontier_proposals = []
        residual_options = []
        if max_fittings is not None:
            from oma.optimization.fabrication_frontier import compile_fabrication_frontier, verify_fabrication_frontier
            frontier_started = time.monotonic()
            frontier_deadline = frontier_started + (min(max_frontier_seconds,max(0.,deadline-frontier_started)*.5)
                if deadline is not None else max_frontier_seconds)
            def frontier_check(stage):
                check(stage)
                if time.monotonic() >= frontier_deadline:
                    raise _FrontierDeadline()
            result["frontier_output_policy"] = {"maximum_paths":max_frontier_proposals,
                "order":"INCREASING_EXACT_FITTING_COUNT", "one_optimum_per_exact_count":True,
                "complete_cartesian_route_universe":False,
                "fallback_shared_budget_feasibility":"NOT_CHECKED"}
            try:
                cap = result["fitting_budget"]["represented_count_cap"]
                frontier_certificate = compile_fabrication_frontier(problem,objective,cap,
                    max_states=max_frontier_states,max_work=max_frontier_work,checkpoint=frontier_check)
                result["frontier_certificate"] = frontier_certificate
                frontier_check("fabrication_frontier_independent_replay")
                count_check = verify_fabrication_frontier(problem,objective,cap,frontier_certificate,
                    max_states=max_frontier_states,max_work=max_frontier_work,checkpoint=frontier_check)
                result["frontier_check"] = count_check
                conversions = result["frontier_conversions"] = []
                if count_check["status"] == "PASS":
                    proof_root = digest(frontier_certificate)
                    for row in frontier_certificate["frontier"]:
                        frontier_check("fabrication_frontier_conversion")
                        count = row["fittings"]
                        conversion = {"exact_fittings":count,"frontier_entry_root":digest(row)}
                        conversions.append(conversion)
                        if row["status"] != "OPTIMAL_PATH":
                            conversion["status"] = "NO_PATH_AT_EXACT_COUNT"
                            continue
                        if len(frontier_proposals) >= max_frontier_proposals:
                            conversion["status"] = "OUTPUT_LIMIT_NOT_CONVERTED"
                            continue
                        try:
                            converted = [[float(_q(x)) for x in point] for point in row["points_m"]]
                            converted_context = digest({"problem_root":model_root,"frontier_certificate_root":proof_root,
                                "frontier_entry_root":digest(row),"exact_fittings":count,"points_m":converted})
                            body = compile_orthogonal_fabrication(scenario,converted,context_root=converted_context,
                                outer_obstacles=coverage["outer_obstacles"],outer_model_root=digest(coverage))
                            body_check = verify_orthogonal_fabrication(scenario,converted,body,context_root=converted_context,
                                outer_obstacles=coverage["outer_obstacles"],outer_model_root=digest(coverage))
                            conversion.update(binary64_context_root=converted_context,
                                binary64_fabrication_certificate=body,binary64_fabrication_check=body_check)
                            frontier_check("fabrication_frontier_conversion_checked")
                            if (body_check["status"] != "PASS" or body_check.get("fabrication_status") != "PASS"
                                    or body_check.get("transitions_checked") != count or len(converted) != count+2):
                                conversion["status"] = "BINARY64_FABRICATION_UNRESOLVED"
                                continue
                            conversion["status"] = "BINARY64_FABRICATION_CHECKED"
                            candidate = proposal(converted,frontier_certificate,body,proof_root=proof_root)
                            candidate.update(rationale="Independently checked exact-count fabrication frontier path; actual IFC and shared fitting budget remain unchecked",
                                path_certificate_kind="FABRICATION_FRONTIER",exact_fittings=count,
                                frontier_certificate_root=proof_root,frontier_entry_root=digest(row),
                                frontier_count_domain_root=frontier_certificate["count_domain_root"],
                                nominal_exact_count_optimality=True,binary64_exact_fittings=count,
                                shared_native_budget_feasibility="NOT_CHECKED")
                            frontier_proposals.append(candidate)
                        except (ValueError,OverflowError) as error:
                            if caller_check.failure is error:
                                raise
                            conversion.update(status="BINARY64_FABRICATION_UNRESOLVED",reason=str(error))
            except _FrontierDeadline as error:
                if caller_check.failure is error:
                    raise
                result["frontier_check"] = {"status":"UNKNOWN","reason":"FABRICATION_FRONTIER_DEADLINE",
                    "feasible_graph_fallback_retained":True}
                frontier_proposals = []
            result["frontier_timing"] = {"total_seconds":time.monotonic()-frontier_started}
        if residual_rounds:
            if frontier_proposals and result.get("frontier_check",{}).get("status") == "PASS":
                from .fabrication_residual import residual_proposals
                residual = residual_proposals(problem,objective,cap,scenario,coverage,frontier_certificate,
                    frontier_proposals,check=check,caller_check=caller_check,deadline=deadline,
                    seconds=max_residual_seconds,max_states=max_residual_states,max_work=max_residual_work,
                    maximum_outputs=max_residual_proposals)
                result["residual_round"] = residual
                residual_options = residual["proposals"]
            else:
                result["residual_round"] = {"status":"NOT_RUN","reason":"NO_CHECKED_ORIGINAL_FRONTIER_PROPOSALS",
                    "proposals":[],"physical_infeasibility_claim":False}
        pricing_started = time.monotonic()
        pricing_deadline = pricing_started + min(6., max(0.,deadline-pricing_started)*.6) if deadline is not None else pricing_started+6.
        def price_check(stage):
            check(stage)
            if time.monotonic() >= pricing_deadline:
                raise _PricingDeadline()
        try:
            from oma.optimization.fabrication_pricing import compile_fabrication_pricing, verify_fabrication_pricing
            priced = compile_fabrication_pricing(problem,objective,max_states=max_states,
                max_work=max_pricing_work,max_pi_terms=max_pi_terms,checkpoint=price_check)
            result["pricing_certificate"] = priced
            price_check("fabrication_pricing_independent_replay")
            price_replay = verify_fabrication_pricing(problem,objective,priced,max_states=max_states,
                max_work=max_pricing_work,max_pi_terms=max_pi_terms,checkpoint=price_check)
            result["pricing_check"] = price_replay
            if price_replay["status"] == "PASS" and price_replay.get("pricing_outcome") == "OPTIMAL_PATH":
                priced_points = [[float(_q(x)) for x in p] for p in priced["points_m"]]
                priced_context = digest({"problem_root":model_root,"certificate_root":digest(priced),"points_m":priced_points})
                priced_body = compile_orthogonal_fabrication(scenario,priced_points,context_root=priced_context,
                    outer_obstacles=coverage["outer_obstacles"],outer_model_root=digest(coverage))
                priced_body_check = verify_orthogonal_fabrication(scenario,priced_points,priced_body,context_root=priced_context,
                    outer_obstacles=coverage["outer_obstacles"],outer_model_root=digest(coverage))
                result.update(priced_binary64_fabrication_certificate=priced_body,priced_binary64_fabrication_check=priced_body_check)
                price_check("fabrication_pricing_conversion_checked")
                if priced_body_check["status"] == "PASS" and priced_body_check["fabrication_status"] == "PASS":
                    proposals.insert(0,proposal(priced_points,priced,priced_body,priced=True))
                    if priced_points == points:
                        proposals.pop()
        except _PricingDeadline as error:
            if caller_check.failure is error:
                raise
            result["pricing_check"] = {"status":"UNKNOWN","reason":"FABRICATION_PRICING_DEADLINE",
                "feasible_graph_fallback_retained":True}
        result["pricing_timing"] = {"total_seconds":time.monotonic()-pricing_started}
        if frontier_proposals or residual_options:
            distinct = set()
            merged = []
            for item in [*frontier_proposals,*residual_options,*proposals]:
                key = tuple(map(tuple,item["points_m"]))
                if key not in distinct:
                    distinct.add(key); merged.append(item)
            proposals = merged
        check("fabrication_graph_publish")
        check("fabrication_proposal_publish")
        # The last caller callback may change files or mutable request objects.
        # No callbacks occur after this point; reread the complete pinned inputs.
        if input_binding() != declared_input_root or digest(problem) != model_root:
            raise ValueError("Original fabrication request or model changed during search")
        for source in expected:
            if source_hash(source["path"],callbacks=False) != source["sha256"]:
                raise ValueError("Original source bytes changed during fabrication search")
        if checker_version() != result["executable_version"]:
            raise ValueError("Source implementation changed during fabrication search")
        if deadline is not None and time.monotonic() >= deadline:
            raise _Deadline()
        result["proposals"] = proposals
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
