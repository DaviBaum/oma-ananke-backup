"""Materialize and independently check explicit finite shared-network alternatives."""
from __future__ import annotations

import copy
from fractions import Fraction
import subprocess
import sys
import time

from pydantic import ValidationError

from oma.build_identity import frozen_environment
from oma.ifc.network import export_network
from oma.models import PhysicalNetwork
from oma.optimization.finite import FiniteOutcome
from oma.optimization.codesign import DesignCase, FiniteCoDesignProblem, solve_finite_codesign, verify_finite_codesign_result
from oma.optimization.master import MasterProblem, RouteColumn
from oma.store import digest
from .network_scenario import SharedNetworkScenario, network_requirements, network_baseline_context
from .objectives import reported_route_cost


def network_project_run(store, run, control):
    deadline = time.monotonic() + run["request"].get("budget_seconds", 300)
    baseline = store.get(run["base_root"])
    try:
        scenario = SharedNetworkScenario.model_validate(run["request"]["mission"])
        source, kept_ports, revision = network_baseline_context(baseline, scenario)
    except (ValidationError, ValueError) as exc:
        store.update_run(run["id"], "MISSING_INPUTS", str(exc), "network_mission")
        return
    mission, ports, section = network_requirements(baseline, scenario)
    outcomes, cases, all_candidate_ids = [], [], []
    for index, network in enumerate(scenario.network_alternatives):
        if time.monotonic() >= deadline:
            break
        control.checkpoint("network_alternative")
        spec = network.model_dump(mode="json", by_alias=True)
        if source.get("transform_m") is not None:
            spec["source_to_federation_matrix"] = source["transform_m"]
        directory = store.directory / "candidates" / run["id"] / f"network-{index:03d}"
        try:
            materialized = export_network(store.resolve_path(source["immutable_path"]), directory / "network.ifc", spec, fresh_recheck=False)
        except (ValueError, RuntimeError) as exc:
            root = store.put({"alternative": network.network_id, "status": "MATERIALIZATION_REJECTED", "reason": str(exc)})
            store.append_event(run["project_id"], run_id=run["id"], stage="network_materialization", status="REJECTED",
                message=str(exc), artifacts=[root])
            continue
        material_root = store.put(materialized)
        record = PhysicalNetwork(id=network.network_id, demand_ids=tuple(s.demand_id for s in scenario.sinks),
            component_ids=tuple(c.id for c in network.components), port_ids=tuple(p["id"] for p in ports),
            service=scenario.system_type, section=section, geometry_artifact=material_root).model_dump(mode="json")
        state = copy.deepcopy(baseline)
        state.update(mission=mission, physical_networks=[record], ports=[*kept_ports, *ports])
        state.setdefault("derived_artifacts", {}).pop("export_correspondence", None)
        state.setdefault("derived_artifacts", {})["network_contract"] = {
            "scenario": scenario.model_dump(mode="json", by_alias=True), "selected_alternative": network.network_id, "source_id": source["id"]}
        changed = [f"{record['id']}:{cid}" for cid in record["component_ids"]]
        if revision:
            state["derived_artifacts"]["network_contract"]["revision"] = {**revision, "base_root": run["base_root"]}
            changed = sorted(set(changed) | set(revision["previous_component_ids"]))
        candidate = store.add_candidate(run["id"], state, {"kind": "physical_network", "changed_ids": changed,
            "routes": [], "networks": [{**record, "spec": spec}], "objective": {},
            "rationale": "One physical component tree shared by all fixed demands; explicit authorized network alternative"})
        all_candidate_ids.append(candidate["id"])
        store.update_run(run["id"], "CHECKING", "Freshly checking shared components, actual tee ports, all obstacles and aggregate flow", "network_verification",
            payload={"candidate_id": candidate["id"], "alternative": network.network_id})
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
        verdict = "PASS" if checked["status"] == "CHECKED" else "FAIL" if checked["status"] == "REJECTED" else "UNKNOWN"
        cost = reported_route_cost(report["objective"], scenario.objective_weights) if verdict == "PASS" else None
        outcomes.append(FiniteOutcome(checked["id"], verdict, cost, evidence_root=checked["report_root"]))
        columns = MasterProblem(net_ids=("physical-network",), columns=(RouteColumn(checked["id"], "physical-network", cost,
            artifact_ref=checked["report_root"]),), state_root=checked["state_root"], declared_universe_complete=True) if verdict == "PASS" else None
        cases.append(DesignCase(checked["id"], (("network", network.network_id),), checked["state_root"], Fraction(0),
            FiniteOutcome(checked["id"], verdict, Fraction(0) if verdict == "PASS" else None, evidence_root=checked["report_root"]), columns))
        store.update_run(run["id"], "RUNNING", f"Shared network {index+1}: {checked['status']}", "network_selection")
    selected = None
    if outcomes:
        # This universe is only the checked archive. Unmaterialized, unfinished
        # and continuous alternatives remain open; finite selection cannot close them.
        problem = FiniteCoDesignProblem(tuple(cases), (("network", tuple(n.network_id for n in scenario.network_alternatives)),), (),
            run["base_root"], declared_design_universe_complete=False)
        selection = solve_finite_codesign(problem, time_limit_seconds=max(.1, deadline-time.monotonic()))
        verified = verify_finite_codesign_result(problem, selection)
        if verified["status"] != "PASS":
            raise ValueError("Independent shared-network archive selection failed")
        artifact = store.put({"result": selection, "independent_check": verified, "physical_candidates": all_candidate_ids,
                              "mission_root": digest(scenario.model_dump(mode="json", by_alias=True))})
        selected = selection.get("selected_design_id")
    else:
        artifact = None
    store.update_run(run["id"], "COMPLETED" if selected else "BUDGET_EXHAUSTED" if time.monotonic() >= deadline else "NO_INCUMBENT_FOUND",
        "Checked shared-network alternative available; unexamined topology and continuous optimality remain open" if selected else "No checked shared-network incumbent in the examined alternatives",
        "complete", artifacts=[artifact] if artifact else [], payload={"selected_candidate_ids": [selected] if selected else [],
            "attempted": len(all_candidate_ids), "checked_feasible": sum(o.verdict == "PASS" for o in outcomes), "global_lower_bound": None, "global_gap": None})
