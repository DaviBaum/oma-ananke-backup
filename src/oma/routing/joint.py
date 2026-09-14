"""Simultaneous physical route choices with root-bound finite co-design replay.

Each complete assignment is independently checked after IFC materialization.
No unexamined continuous family is declared infeasible or globally optimal.
"""
from __future__ import annotations

import copy
from fractions import Fraction
import itertools
import json
import subprocess
import sys
import time

from pydantic import ValidationError

from oma.models import Demand, Mission, Port, Provenance, Route, Section
from oma.optimization.codesign import DesignCase, FiniteCoDesignProblem, solve_finite_codesign, verify_finite_codesign_result
from oma.optimization.finite import FiniteOutcome
from oma.optimization.master import MasterProblem, RouteColumn
from oma.store import digest
from .generator import proposal_paths
from .joint_materialize import materialize_route_set
from .joint_scenario import parse_joint_request


def baseline_contracts(state):
    contracts = copy.deepcopy(state.get("derived_artifacts", {}).get("routing_contracts", {}))
    if not contracts and state.get("routes"):
        if len(state["routes"]) != 1:
            raise ValueError("Existing routes have no complete immutable mission mapping")
        route = state["routes"][0]
        derived = state["derived_artifacts"]
        contracts[route["id"]] = {"scenario": derived["routing_scenario"], "mission": state["mission"],
            "source_id": derived["route_materialization"]["source_id"], "request_demand_id": "prior-route"}
    if set(contracts) != {r["id"] for r in state.get("routes", [])}:
        raise ValueError("Existing route mission coverage is incomplete")
    return contracts


def _new_obligation(state, scenario, route_id, demand_key, source_id):
    data = scenario.model_dump(mode="json")
    root = digest(data)
    section = Section(shape="circular", diameter_m=scenario.diameter_m, insulation_m=scenario.insulation_m)
    provenance = Provenance(source_id=f"scenario:{root}", content_hash=root, kind="scenario", description="Explicit simultaneous routing requirement")
    net = f"net:{route_id}"
    ports = [Port(id=f"{net}:{kind}", entity_id=f"{net}:{kind}", position_m=point, direction=kind.upper(),
             service=scenario.system_type, section=section, connection_evidence="scenario", provenance=provenance)
             for kind, point in (("source", scenario.start), ("sink", scenario.end))]
    demand = Demand(id=net, source_port=ports[0].id, sink_ports=(ports[1].id,), service=scenario.system_type,
        section=section, min_slope=scenario.min_slope, clearance_m=scenario.clearance_m, provenance=provenance)
    rule = {"clearance_m": scenario.clearance_m, "zone": scenario.allowed_zone.model_dump(), "numerical_tolerance_m": 1e-6,
            "contact": "explicit local interfaces only", "modality": scenario.target_modality}
    mission = Mission(id=f"mission:{route_id}", demands=(demand,), protected_ids=tuple(e["id"] for e in state.get("entities", [])),
        allowed_zones=(scenario.allowed_zone,), rule_hash=digest(rule),
        catalog_hash=digest({"section": section.model_dump(mode="json"), "bend_radius_m": scenario.bend_radius_m, "minimum_straight_m": scenario.minimum_straight_m}),
        scenario_hash=root, objective_weights=scenario.objective_weights, assumptions=tuple(scenario.assumptions))
    return {"scenario": data, "mission": mission.model_dump(mode="json"), "source_id": source_id, "request_demand_id": demand_key}, ports, section


def joint_project_run(store, run, control):
    deadline = time.monotonic() + run["request"].get("budget_seconds", 300)
    state = store.get(run["base_root"])
    try:
        request = parse_joint_request(run["request"]["mission"])
        existing = baseline_contracts(state)
    except (ValidationError, ValueError) as exc:
        store.update_run(run["id"], "MISSING_INPUTS", str(exc), "joint_mission")
        return
    if not state.get("sources"):
        store.update_run(run["id"], "MISSING_INPUTS", "Joint routing requires completed IFC sources", "joint_mission")
        return
    weights = request.route_demands[0].alternatives[0].objective_weights
    choices, domains = [], []
    obstacles = [e["geometry"]["bounds"]["min"] + e["geometry"]["bounds"]["max"] for e in state.get("entities", []) if e.get("geometry", {}).get("bounds")]
    for demand in request.route_demands:
        options = []
        for alternative_index, scenario in enumerate(demand.alternatives):
            for path_index, proposal in enumerate(itertools.islice(proposal_paths(scenario, obstacles, deadline=deadline,
                    checkpoint=lambda: control.checkpoint("joint_search")), min(scenario.max_candidates, request.max_paths_per_alternative))):
                options.append((f"{alternative_index}:{path_index}", scenario, proposal))
                if time.monotonic() >= deadline:
                    break
        choices.append(options)
        domains.append((demand.id, tuple(option[0] for option in options)))
    cases, checked_count, attempted = [], 0, 0
    for assignment in itertools.islice(itertools.product(*choices), request.max_joint_candidates):
        if time.monotonic() >= deadline:
            break
        control.checkpoint("joint_assignment")
        attempted += 1
        candidate_state = copy.deepcopy(state)
        contracts = copy.deepcopy(existing)
        routes = copy.deepcopy(state.get("routes", []))
        specs = {r["id"]: copy.deepcopy(store.get(r["geometry_artifact"])["route_spec"]) for r in routes}
        new_ids = []
        for demand, (option, scenario, proposal) in zip(request.route_demands, assignment):
            source = next((s for s in state["sources"] if s["id"] == scenario.source_id), state["sources"][0] if scenario.source_id is None else None)
            if source is None:
                raise ValueError("Selected joint route source is not in the federation")
            route_id = f"oma-{run['id'][:12]}-{attempted:03d}-{len(new_ids):02d}"
            contract, ports, section = _new_obligation(state, scenario, route_id, demand.id, source["id"])
            contracts[route_id] = contract
            candidate_state.setdefault("ports", []).extend(p.model_dump(mode="json") for p in ports)
            candidate_state.setdefault("assumptions", []).append({"kind": "explicit_scenario", "root": digest(contract["scenario"]), "data": contract["scenario"]})
            route = Route(id=route_id, demand_ids=(contract["mission"]["demands"][0]["id"],), service=scenario.system_type,
                points_m=tuple(tuple(p) for p in proposal["points_m"]), section=section, port_ids=tuple(p.id for p in ports), status="MATERIALIZED")
            routes.append(route.model_dump(mode="json"))
            spec = {"route_id": route_id, "points_m": proposal["points_m"], "diameter_m": scenario.diameter_m, "insulation_m": scenario.insulation_m,
                "bend_radius_m": scenario.bend_radius_m, "minimum_straight_m": scenario.minimum_straight_m,
                "system_type": scenario.system_type, "assumption_root": digest(contract["scenario"])}
            for key in ("source_port_guid", "sink_port_guid"):
                if getattr(scenario, key):
                    spec[key] = getattr(scenario, key)
            if source.get("transform_m") is not None:
                spec["source_to_federation_matrix"] = source["transform_m"]
            specs[route_id] = spec
            new_ids.append(route_id)
        directory = store.directory / "candidates" / run["id"] / f"joint-{attempted:03d}"
        try:
            materialized = materialize_route_set(store, state, contracts, specs, directory, control.checkpoint)
        except (ValueError, RuntimeError) as exc:
            artifact = store.put({"assignment": [a[0] for a in assignment], "reason": str(exc), "status": "MATERIALIZATION_REJECTED"})
            store.append_event(run["project_id"], run_id=run["id"], state_root=run["base_root"], stage="joint_materialization", status="REJECTED", message=str(exc), artifacts=[artifact])
            continue
        for route in routes:
            route["geometry_artifact"] = store.put(materialized[route["id"]])
        candidate_state["routes"] = routes
        missions = [contracts[r]["mission"] for r in sorted(contracts)]
        candidate_state["mission"] = Mission(id=f"joint:{run['id']}", demands=tuple(Demand.model_validate(d) for m in missions for d in m["demands"]),
            protected_ids=tuple(e["id"] for e in state.get("entities", [])), allowed_zones=tuple(z for m in missions for z in m["allowed_zones"]),
            rule_hash=digest([m["rule_hash"] for m in missions]), catalog_hash=digest([m["catalog_hash"] for m in missions]),
            scenario_hash=digest([m["scenario_hash"] for m in missions]), objective_weights=weights).model_dump(mode="json")
        candidate_state.setdefault("derived_artifacts", {}).update(routing_contracts=contracts,
            route_exports=[{"source_id": contracts[r]["source_id"], "route_spec": specs[r]} for r in specs])
        candidate = store.add_candidate(run["id"], candidate_state, {"kind": "physical_route_set", "changed_ids": new_ids,
            "routes": routes, "objective": {}, "rationale": "Simultaneous physical route and explicitly authorized design-option assignment"})
        store.update_run(run["id"], "CHECKING", "Independently checking every route, protected prior obligation and cross-route pair", "joint_verification", payload={"candidate_id": candidate["id"]})
        from oma.build_identity import frozen_environment
        try:
            result = subprocess.run([sys.executable, "-m", "oma.verification", str(store.directory), candidate["id"]],
                capture_output=True, text=True, timeout=max(.1, deadline-time.monotonic()), env=frozen_environment(store.directory),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except subprocess.TimeoutExpired:
            break
        if result.returncode:
            raise RuntimeError(result.stderr[-3000:])
        checked = store.candidate(candidate["id"])
        report = store.get(checked["report_root"])
        columns = None
        verdict = "PASS" if checked["status"] == "CHECKED" else "FAIL" if checked["status"] == "REJECTED" else "UNKNOWN"
        if verdict == "PASS":
            checked_count += 1
            values = next(r["witness"]["per_route"] for r in report["results"] if r["id"] == "joint-objective")
            columns = MasterProblem(net_ids=tuple(values), columns=tuple(RouteColumn(rid, rid,
                sum(Fraction(str(weights.get(k, 0))) * Fraction(str(v)) for k, v in objective.items()), artifact_ref=checked["report_root"])
                for rid, objective in values.items()), state_root=checked["state_root"], objective_policy=json.dumps(weights, sort_keys=True), declared_universe_complete=True)
        cases.append(DesignCase(checked["id"], tuple((d.id, choice[0]) for d, choice in zip(request.route_demands, assignment)),
            checked["state_root"], Fraction(0), FiniteOutcome(checked["id"], verdict, Fraction(0) if verdict == "PASS" else None, evidence_root=checked["report_root"]), columns))
        store.update_run(run["id"], "RUNNING", f"Joint assignment {attempted}: {checked['status']}; {checked_count} checked alternatives", "joint_selection")
    if cases:
        problem = FiniteCoDesignProblem(tuple(cases), tuple(domains), (), run["base_root"], declared_design_universe_complete=False)
        selected = solve_finite_codesign(problem, time_limit_seconds=max(.1, deadline-time.monotonic()))
        independent = verify_finite_codesign_result(problem, selected)
        if independent["status"] != "PASS":
            raise RuntimeError(f"Joint finite co-design replay failed: {independent}")
        artifact = store.put({"result": selected, "independent_check": independent, "context_root": run["base_root"],
            "case_roots": [c.design_root for c in cases], "physical_candidates": [c.id for c in cases], "domains": domains})
        chosen = selected["selected_design_id"]
    else:
        chosen, artifact = None, None
    store.update_run(run["id"], "COMPLETED" if chosen else "BUDGET_EXHAUSTED" if time.monotonic() >= deadline else "NO_INCUMBENT_FOUND",
        "Checked simultaneous incumbent available; no continuous global optimality claim" if chosen else "No checked simultaneous incumbent in the examined assignments; infeasibility is not established",
        "complete", artifacts=[artifact] if artifact else [], payload={"selected_candidate_ids": [chosen] if chosen else [],
            "attempted": attempted, "checked_feasible": checked_count, "global_lower_bound": None, "global_gap": None})
