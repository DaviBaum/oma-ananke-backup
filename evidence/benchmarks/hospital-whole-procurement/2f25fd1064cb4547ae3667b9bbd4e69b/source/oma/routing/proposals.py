"""Combine bounded proposal methods without transferring acceptance authority."""
from __future__ import annotations

from itertools import islice
import time

from oma.build_identity import checker_version
from oma.store import digest
from .generator import proposal_paths


def project_proposals(store, run, state, scenario, obstacles, *, deadline, checkpoint, on_search,
                      request_demand_id=None, max_fittings=None, search_checkpoint=None):
    """Keep the direct baseline first, then source-checked cells and heuristics.

    The cell model covers translating balls. Every yielded path still requires
    fabrication, independent complete native checking, and service checking.
    An exhausted or inapplicable cell model never rules out physical routes.
    """
    if max_fittings is not None:
        if type(max_fittings) is not int or not 0 <= max_fittings <= 1024:
            raise ValueError("Declared new-fitting budget must be an integer in [0,1024]")
        if run.get("request",{}).get("mission",{}).get("max_new_fittings") != max_fittings:
            raise ValueError("Proposal fitting budget differs from the immutable joint mission")
    def search_pulse(stage):
        # The adapters' inner loops may coalesce control I/O. Their explicit
        # proposal publication boundaries and every persistence call below
        # retain a forced control check, including under single-step control.
        if search_checkpoint is None or stage in {
                "cell_proposal_publish", "fabrication_graph_publish", "fabrication_proposal_publish"}:
            checkpoint(stage)
        else:
            search_checkpoint(stage)
    heuristic = proposal_paths(scenario, obstacles, deadline=deadline,
        checkpoint=lambda: search_pulse("route_search"), on_search=on_search)
    seen = set()

    def unseen(proposal):
        key = tuple(tuple(point) for point in proposal["points_m"])
        if key in seen:
            return False
        seen.add(key)
        return True

    def combined():
        direct = next(heuristic, None)
        if direct is not None and unseen(direct):
            yield direct
        remaining = deadline - time.monotonic()
        # Original-host support cannot justify edited-host paths. The opening
        # workflow independently checks the actual modified IFC instead.
        if scenario.authorized_opening is None and remaining > 1:
            checkpoint("route_geometry_model")
            from .certified_cells import build_certified_cell_proposals
            context = {"base_root": run["base_root"],
                "scenario_root": digest(scenario.model_dump(mode="json")),
                "executable_version": checker_version()}
            if request_demand_id is not None:
                context["request_demand_id"] = request_demand_id
                context["request_root"] = digest(run["request"])
            if max_fittings is not None:
                context["max_new_fittings"] = max_fittings
                context["request_root"] = digest(run["request"])
            store.append_event(run["project_id"], run_id=run["id"], state_root=run["base_root"],
                stage="route_geometry_model", status="RUNNING",
                message="Checking complete source support and a bounded exact route-cell model",
                payload={"context": context, "route_acceptance": False,
                         "physical_infeasibility_claim": False})
            specs = [{"path": store.resolve_path(s["immutable_path"]),
                      "sha256": s["sha256"], "transform_m": s.get("transform_m")}
                     for s in state["sources"]]
            report = build_certified_cell_proposals(specs, scenario,
                context_root=digest(context),
                coordinate_evidence=state.get("derived_artifacts", {}).get("local_coordinate_evidence"),
                cache_directory=store.directory / "cad-cache", grid_divisions=6,
                deadline=min(deadline, time.monotonic() + min(20., remaining * .2)),
                checkpoint=search_pulse)
            checkpoint("route_geometry_model_publish")
            artifact = store.put({"context": context, "report": report,
                "route_acceptance": False, "physical_infeasibility_claim": False})
            store.append_event(run["project_id"], run_id=run["id"], state_root=run["base_root"],
                stage="route_geometry_model", status=report["status"], artifacts=[artifact],
                message="Source-bound route-cell model evaluated; every physical proposal requires a fresh full check",
                payload={"reason": report.get("reason"), "proposal_count": len(report["proposals"]),
                    "request_demand_id": request_demand_id,
                    "coverage": report.get("coverage_check"), "timing": report["timing"],
                    "route_acceptance": False, "physical_infeasibility_claim": False})
            remaining = deadline-time.monotonic()
            if report.get("coverage_check",{}).get("status") == "PASS" and remaining > 1:
                from .certified_fabrication import build_certified_fabrication_proposals
                checkpoint("fabrication_graph_search")
                lifted = build_certified_fabrication_proposals(specs,scenario,report,context_root=digest(context),
                    deadline=min(deadline,time.monotonic()+min(10.,remaining*.15)),checkpoint=search_pulse,
                    **({"max_fittings":max_fittings,"residual_rounds":1} if max_fittings is not None else {}))
                checkpoint("fabrication_graph_result")
                lifted_root = store.put({"context":context,"report":lifted,
                    "route_acceptance":False,"physical_infeasibility_claim":False})
                store.append_event(run["project_id"],run_id=run["id"],state_root=run["base_root"],
                    stage="fabrication_graph",status=lifted["status"],artifacts=[lifted_root],
                    message="Finite fabrication route and bounded nominal cost pricing evaluated; native checks remain required",
                    payload={"proposal_count":len(lifted["proposals"]),"reason":lifted.get("reason"),
                        "request_demand_id":request_demand_id,"coverage":lifted.get("coverage_check"),
                        "pricing":lifted.get("pricing_check"),
                        **({"frontier":lifted.get("frontier_check"),"fitting_budget":lifted.get("fitting_budget"),
                            "residual":{k:v for k,v in lifted.get("residual_round",{}).items()
                                if k in {"status","reason","independent_check","policy","timing"}}}
                           if max_fittings is not None else {}),
                        "timing":lifted["timing"],"route_acceptance":False,"physical_infeasibility_claim":False})
                for proposal in lifted["proposals"]:
                    if time.monotonic() >= deadline:
                        return
                    if unseen(proposal):
                        yield {**proposal,"geometry_evidence":{
                            "method":"SOURCE_BOUND_FABRICATION_GRAPH","report_root":lifted_root,
                            "context_root":digest(context),"model_root":lifted["model_root"],
                            "path_certificate_kind":proposal["path_certificate_kind"],
                            "path_certificate_root":proposal["path_certificate_root"],
                            "binary64_fabrication_certificate_root":proposal["binary64_fabrication_certificate_root"],
                            "nominal_graph_optimality":proposal["nominal_graph_optimality"],
                            **({key:proposal[key] for key in ("exact_fittings","frontier_certificate_root","frontier_entry_root",
                                "frontier_count_domain_root","nominal_exact_count_optimality","binary64_exact_fittings",
                                "shared_native_budget_feasibility")} if proposal["path_certificate_kind"] == "FABRICATION_FRONTIER" else {}),
                            **({key:proposal[key] for key in ("exact_fittings","residual_certificate_root","residual_entry_root",
                                "residual_count_domain_root","residual_exclusion_root","residual_model_root",
                                "generation_ledger_root","nominal_exact_count_residual_optimality","nominal_exact_count_optimality",
                                "binary64_exact_fittings","shared_native_budget_feasibility")}
                                if proposal["path_certificate_kind"] == "FABRICATION_RESIDUAL_FRONTIER" else {}),
                            "binary64_objective_optimality":False,
                            "coverage_root":digest(lifted["coverage"]),"scope":proposal["geometry_scope"],
                            "route_acceptance":False,"physical_infeasibility_claim":False}}
            for proposal in report["proposals"]:
                checkpoint("route_cell_proposal")
                if time.monotonic() >= deadline:
                    return
                if unseen(proposal):
                    yield {**proposal, "geometry_evidence": {
                        "method":"SOURCE_BOUND_ROUTE_CELLS",
                        "report_root": artifact, "context_root": digest(context),
                        "model_root": report["model_root"],
                        "cell_certificate_root": proposal["cell_certificate_root"],
                        "coverage_root": proposal["coverage_root"],
                        "scope": proposal["geometry_scope"], "route_acceptance": False,
                        "physical_infeasibility_claim": False}}
        for proposal in heuristic:
            if time.monotonic() >= deadline:
                return
            if unseen(proposal):
                yield proposal

    # Bound consumption itself: max_candidates=1 must not start another model
    # merely to discover that the candidate limit has already been reached.
    from .fabrication_evidence import persist_fabrication_proposal
    for proposal in islice(combined(), scenario.max_candidates):
        yield persist_fabrication_proposal(store, run, scenario, proposal,
            checkpoint=checkpoint, request_demand_id=request_demand_id)
