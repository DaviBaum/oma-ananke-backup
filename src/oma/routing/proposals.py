"""Combine bounded proposal methods without transferring acceptance authority."""
from __future__ import annotations

from itertools import islice
import time

from oma.build_identity import checker_version
from oma.store import digest
from .generator import proposal_paths


def project_proposals(store, run, state, scenario, obstacles, *, deadline, checkpoint, on_search,
                      request_demand_id=None):
    """Keep the direct baseline first, then source-checked cells and heuristics.

    The cell model covers translating balls. Every yielded path still requires
    fabrication, independent complete native checking, and service checking.
    An exhausted or inapplicable cell model never rules out physical routes.
    """
    heuristic = proposal_paths(scenario, obstacles, deadline=deadline,
        checkpoint=lambda: checkpoint("route_search"), on_search=on_search)
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
                checkpoint=checkpoint)
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
            for proposal in report["proposals"]:
                checkpoint("route_cell_proposal")
                if time.monotonic() >= deadline:
                    return
                if unseen(proposal):
                    yield {**proposal, "geometry_evidence": {
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
