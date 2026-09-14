"""Physical proposals → IFC materialization → independent check → finite master.

This implements a bounded finite route-family slice of the source integration.
It does not assert complete continuous routing or full ANANKE implementation.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import time
from pathlib import Path

from pydantic import ValidationError

from oma.ifc.export import export_route
from oma.models import Demand, Mission, Port, Provenance, Route, Section
from oma.optimization.master import MasterProblem, RouteColumn, solve_master
from oma.optimization.checker import verify_master_result
from oma.store import Store, digest
from .generator import proposal_paths
from .scenario import RoutingScenario


def route_project_run(store: Store, run: dict, control):
    began = time.monotonic()
    deadline = began + run["request"].get("budget_seconds", 300)
    raw = run["request"].get("mission")
    if not raw:
        store.update_run(run["id"], "MISSING_INPUTS", "Explicit routing mission is required", "mission")
        return
    if "route_demands" in raw or store.get(run["base_root"]).get("routes"):
        from .joint import joint_project_run
        return joint_project_run(store, run, control)
    try:
        scenario = RoutingScenario.model_validate(raw)
    except ValidationError as exc:
        errors = [{"field": ".".join(map(str, e["loc"])), "reason": e["msg"]} for e in exc.errors()]
        store.update_run(run["id"], "MISSING_INPUTS", "Routing mission is incomplete or inconsistent", "mission", payload={"missing_inputs": errors})
        return
    state = store.get(run["base_root"])
    sources = state.get("sources", [])
    if not sources:
        store.update_run(run["id"], "MISSING_INPUTS", "No completed IFC sources", "mission")
        return
    if scenario.target_modality == "ENGINEERING_SERVICE" and not scenario.physics:
        store.update_run(run["id"], "MISSING_INPUTS", "Service adequacy requires explicit flow, material and boundary-condition inputs", "mission")
        return
    source = next((s for s in sources if s["id"] == scenario.source_id), sources[0] if scenario.source_id is None else None)
    if source is None:
        raise ValueError("Selected route source discipline is not part of this federation")
    scenario_data = scenario.model_dump(mode="json")
    scenario_hash = digest(scenario_data)
    section = Section(shape="circular", diameter_m=scenario.diameter_m, insulation_m=scenario.insulation_m)
    provenance = Provenance(source_id=f"scenario:{scenario_hash}", content_hash=scenario_hash, kind="scenario", description="Explicit versioned routing scenario; no imported metadata inferred")
    net_id = f"net:{scenario_hash[:20]}"
    port_ids = [f"{net_id}:source", f"{net_id}:sink"]
    ports = [Port(id=port_ids[0], entity_id=port_ids[0], position_m=scenario.start, direction="SOURCE", service=scenario.system_type, section=section, connection_evidence="scenario", provenance=provenance),
             Port(id=port_ids[1], entity_id=port_ids[1], position_m=scenario.end, direction="SINK", service=scenario.system_type, section=section, connection_evidence="scenario", provenance=provenance)]
    demand = Demand(id=net_id, source_port=port_ids[0], sink_ports=(port_ids[1],), service=scenario.system_type, section=section,
                    min_slope=scenario.min_slope, clearance_m=scenario.clearance_m, provenance=provenance)
    rule = {"clearance_m": scenario.clearance_m, "zone": scenario.allowed_zone.model_dump(), "numerical_tolerance_m": 1e-6,
            "contact": "explicit local interfaces only", "modality": scenario.target_modality}
    mission = Mission(id=f"mission:{scenario_hash}", demands=(demand,), protected_ids=tuple(e["id"] for e in state.get("entities", [])),
                      allowed_zones=(scenario.allowed_zone,), rule_hash=digest(rule), catalog_hash=digest({"section": section.model_dump(mode="json"), "bend_radius_m": scenario.bend_radius_m, "minimum_straight_m": scenario.minimum_straight_m}),
                      scenario_hash=scenario_hash, objective_weights=scenario.objective_weights, assumptions=tuple(scenario.assumptions))
    obstacles = [e["geometry"]["bounds"]["min"] + e["geometry"]["bounds"]["max"] for e in state.get("entities", []) if e.get("geometry", {}).get("bounds")]
    store.append_event(run["project_id"], run_id=run["id"], state_root=run["base_root"], stage="mission", status="RUNNING",
                       message="Fixed terminals, physical section, permitted zone and protected sources bound to scenario", artifacts=[store.put(scenario_data)],
                       payload={"mission": mission.model_dump(mode="json"), "search_scope": "finite heuristic candidates; no continuous optimality claim"})
    columns, feasible_ids = [], []
    attempted = 0
    last_search_emit = 0.
    def search_event(payload):
        nonlocal last_search_emit
        if time.monotonic() - last_search_emit >= .25:
            store.append_event(run["project_id"], run_id=run["id"], state_root=run["base_root"], stage="route_search", status="RUNNING", message="Exploring physical route proposals", payload=payload)
            last_search_emit = time.monotonic()
    for proposal in proposal_paths(scenario, obstacles, deadline=deadline, checkpoint=lambda: control.checkpoint("route_search"), on_search=search_event):
        if attempted >= scenario.max_candidates or time.monotonic() >= deadline:
            break
        control.checkpoint("materialize")
        attempted += 1
        route_id = f"oma-{run['id'][:12]}-{attempted:03d}"
        route_spec = {"route_id": route_id, "points_m": proposal["points_m"], "diameter_m": scenario.diameter_m,
                      "insulation_m": scenario.insulation_m, "bend_radius_m": scenario.bend_radius_m,
                      "minimum_straight_m": scenario.minimum_straight_m, "system_type": scenario.system_type,
                      "assumption_root": scenario_hash}
        for key in ("source_port_guid", "sink_port_guid"):
            if getattr(scenario, key):
                route_spec[key] = getattr(scenario, key)
        if source.get("transform_m") is not None:
            route_spec["source_to_federation_matrix"] = source["transform_m"]
        directory = store.directory / "candidates" / run["id"] / route_id
        directory.mkdir(parents=True, exist_ok=True)
        try:
            materialized = export_route(store.resolve_path(source["immutable_path"]), directory / "route.ifc", route_spec, fresh_recheck=True)
        except (ValueError, RuntimeError) as exc:
            artifact = store.put({"route_id": route_id, "proposal": proposal, "route_spec": route_spec, "rejection": str(exc)})
            store.append_event(run["project_id"], run_id=run["id"], state_root=run["base_root"], candidate_id=route_id,
                               stage="materialization", status="REJECTED", message=f"Physical fitting/materialization rejected: {exc}", artifacts=[artifact], payload={"points_m": proposal["points_m"]})
            continue
        materialized_root = store.put(materialized)
        route = Route(id=route_id, demand_ids=(net_id,), service=scenario.system_type, points_m=tuple(tuple(p) for p in proposal["points_m"]),
                      section=section, port_ids=tuple(port_ids), geometry_artifact=materialized_root, status="MATERIALIZED")
        candidate_state = copy.deepcopy(state)
        candidate_state["mission"] = mission.model_dump(mode="json")
        candidate_state["ports"] = state.get("ports", []) + [p.model_dump(mode="json") for p in ports]
        candidate_state["routes"] = state.get("routes", []) + [route.model_dump(mode="json")]
        candidate_state.setdefault("assumptions", []).append({"kind": "explicit_scenario", "root": scenario_hash, "data": scenario_data})
        candidate_state.setdefault("derived_artifacts", {}).update({"routing_scenario": scenario_data, "route_rule": rule,
            "route_materialization": {"root": materialized_root, "source_id": source["id"], "path": str(directory / "route.ifc")},
            "route_exports": [{"source_id": source["id"], "route_spec": route_spec}]})
        candidate = store.add_candidate(run["id"], candidate_state, {"kind": "physical_route", "routes": [route.model_dump(mode="json")],
                   "changed_ids": [route_id], "objective": {}, "rationale": proposal["rationale"], "target_modality": scenario.target_modality})
        store.update_run(run["id"], "CHECKING", "Independent checker is reloading physical solids, mission and protected sources", "verification", payload={"candidate_id": candidate["id"]})
        remaining = deadline - time.monotonic()
        if remaining < 1:
            break
        try:
            from oma.build_identity import frozen_environment
            result = subprocess.run([sys.executable, "-m", "oma.verification", str(store.directory), candidate["id"]],
                                    capture_output=True, text=True, timeout=remaining, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                                    env=frozen_environment(store.directory))
        except subprocess.TimeoutExpired:
            store.append_event(run["project_id"], run_id=run["id"], state_root=candidate["state_root"], candidate_id=candidate["id"], stage="verification", status="TIMED_OUT", message="Independent check budget exhausted; candidate cannot be accepted")
            break
        if result.returncode:
            raise RuntimeError(f"Independent route checker failed: {result.stderr[-3000:]}")
        control.checkpoint("selection")
        checked = store.candidate(candidate["id"])
        if checked["status"] == "CHECKED":
            report = store.get(checked["report_root"])
            cost = sum(scenario.objective_weights.get(k, 0) * v for k, v in report["objective"].items())
            columns.append(RouteColumn(checked["id"], net_id, cost, artifact_ref=checked["report_root"]))
            feasible_ids.append(checked["id"])
        store.update_run(run["id"], "RUNNING", f"Candidate {attempted}: {checked['status']}; {len(feasible_ids)} checked alternatives", "selection")
    if columns:
        problem = MasterProblem(net_ids=(net_id,), columns=tuple(columns), state_root=run["base_root"],
                                objective_policy=json.dumps(scenario.objective_weights, sort_keys=True), declared_universe_complete=False)
        result = solve_master(problem, time_limit_seconds=max(.1, deadline - time.monotonic()), on_candidate=lambda e: store.append_event(run["project_id"], run_id=run["id"], state_root=run["base_root"], stage="master", status="INCUMBENT", message="Finite master selected a checked physical alternative", payload=e))
        independent = verify_master_result(problem, result)
        if independent["verdict"] != "PASS":
            raise RuntimeError(f"Independent finite-master verification did not pass: {independent}")
        artifact = store.put({"problem": problem.payload(), "result": result.to_dict(), "independent_check": independent})
        store.update_run(run["id"], "COMPLETED", "Checked feasible incumbent available; continuous routing optimality is not established", "complete", artifacts=[artifact], payload={"selected_candidate_ids": list(result.selected), "attempted": attempted, "checked_feasible": len(feasible_ids), "global_lower_bound": None, "global_gap": None})
    else:
        status = "BUDGET_EXHAUSTED" if time.monotonic() >= deadline else "NO_INCUMBENT_FOUND"
        store.update_run(run["id"], status, "No independently checked candidate found in the attempted finite search; this is not proof of infeasibility", "complete", payload={"attempted": attempted, "checked_feasible": 0})
