"""Two explicit Office missions differing only in an optional new-elbow budget.

The original obstructed service and a separately frozen straight service keep
their exact requirements and all original IFC obstacles. Every candidate and
inconclusive search outcome is retained; bounded failures are not infeasibility.
"""
import argparse
from copy import deepcopy
from fractions import Fraction
import json
import os
from pathlib import Path
import sys
import time
import uuid

from oma.build_identity import checker_version, frozen_environment
from oma.export_checks import supervise_check
from oma.exporting import export_project
from oma.ifc.audit import atomic_json, sha256_file
from oma.optimization.checker import verify_master_result
from oma.optimization.codesign import _decode_master
from oma.optimization.master import MasterProblem, RouteColumn
from oma.routing.selection import current_selection_evidence
from oma.store import Store, digest, utcnow

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_CANDIDATE = "f23ca52d9caf4b0ca8d2e123bc7fc011"
SOURCE_SPEC = ROOT / "evidence/benchmarks/real-repair/wbdg_office/source-vertex-hull/bounds-screened-v2/arc.frozen.json"
STRAIGHT_SPEC = ROOT / "evidence/benchmarks/real-repair/wbdg_office/joint-demand/arc.joint-frozen.json"


def specification(store):
    source = json.loads(SOURCE_SPEC.read_text(encoding="utf-8"))
    selected = next(s for s in source["scenarios"] if s["scenario_id"] == "b185aad281acfe439d15")
    straight = json.loads(STRAIGHT_SPEC.read_text(encoding="utf-8"))
    separate = straight["scenarios"][0]["mission"]["route_demands"][0]["alternatives"][0]
    original = store.candidate(HISTORICAL_CANDIDATE)
    origin = store.run(original["run_id"])
    baseline = store.get(origin["base_root"])
    assert selected["mission"] == origin["request"]["mission"]
    assert not baseline.get("routes") and not baseline.get("physical_networks")
    assert selected["mission"]["source_id"] == separate["source_id"]
    result = {"schema": "oma.office-joint-fitting-budget-campaign/1",
        "historical_candidate_id": HISTORICAL_CANDIDATE, "historical_run_id": origin["id"],
        "historical_baseline_root": origin["base_root"], "scenario_id": selected["scenario_id"],
        "original_obstructed_mission_unchanged": True, "separate_straight_mission_unchanged": True,
        "source_specification": {"path": str(SOURCE_SPEC), "sha256": sha256_file(SOURCE_SPEC), "root": source["specification_root"]},
        "straight_specification": {"path": str(STRAIGHT_SPEC), "sha256": sha256_file(STRAIGHT_SPEC)},
        "original_source_hashes": [s["sha256"] for s in baseline["sources"]],
        "mission": {"route_demands": [
            {"id": "obstructed-service", "alternatives": [deepcopy(selected["mission"])]},
            {"id": "separate-straight-service", "alternatives": [deepcopy(separate)]}],
            "max_joint_candidates": 4, "max_paths_per_alternative": 4},
        "resource_budgets": [2, 0], "resource": "New independent round90-degree elbows; prior routes excluded",
        "scope": "Explicit hypothetical services against all original Office obstacles under the unchanged native/source-vertex-hull representation policy; no whole-building or continuous optimum claim"}
    result["specification_root"] = digest(result)
    return result, baseline, origin


def all_events(store, project_id):
    events, cursor = [], 0
    while batch := store.events(project_id, cursor, 1000):
        events.extend(batch)
        cursor = batch[-1]["seq"]
    return events


def retain_candidate(store, candidate, directory):
    atomic_json(directory / (candidate["id"] + ".candidate.json"), candidate)
    state = store.get(candidate["state_root"])
    atomic_json(directory / (candidate["id"] + ".state.json"), state)
    report = store.get(candidate["report_root"]) if candidate.get("report_root") else None
    result = {"id": candidate["id"], "state_root": candidate["state_root"], "status": candidate["status"],
        "report_root": candidate.get("report_root"), "assignment": candidate.get("physical_menu_assignment"),
        "objective": report["objective"] if report else None,
        "proposal_evidence": candidate.get("proposal_evidence"), "checks": [], "native": []}
    if report is None:
        return result
    atomic_json(directory / (candidate["id"] + ".verification.json"), report)
    for row in report["results"]:
        result["checks"].append({"id": row["id"], "status": row["status"], "reason": row["reason"]})
        if row["id"] == "joint-new-fitting-budget":
            result["fitting_budget"] = row
        if row["id"] == "cross-route-interference":
            result["cross_route"] = row
        if row["id"].endswith(":physical-interference-and-clearance") and row["witness"].get("artifact"):
            artifact = store.get(row["witness"]["artifact"])
            atomic_json(directory / (row["witness"]["artifact"] + ".native.json"), artifact)
            result["native"].append({"route_id": row["id"].split(":")[0], "status": row["status"],
                "artifact_root": row["witness"]["artifact"],
                **{key: artifact.get(key) for key in ("sources", "route_count", "obstacle_count", "pairs_accounted",
                    "failed_pairs", "unknown_pairs", "blocked_pairs", "coordination_status", "self_interference_status")}})
    return result


def exact_capacity_replay(store, run, selected, events, directory):
    """Reconstruct the actual native row and match the original solved master hash."""
    state = store.get(selected["state_root"])
    weights = state["mission"]["objective_weights"]
    evidence = current_selection_evidence(store, run, selected["id"], "physical_route_set", weights)
    counts = evidence["fitting_budget"]["per_new_route"]
    budget = evidence["fitting_budget"]["max_new_fittings"]
    costs = evidence["per_route_costs"]
    problem = MasterProblem(net_ids=tuple(costs), columns=tuple(RouteColumn(rid, rid, cost,
        resource_use=(("new-fabricated-elbows", Fraction(counts[rid])),), artifact_ref=evidence["report_root"])
        for rid, cost in costs.items()), capacities=(("new-fabricated-elbows", Fraction(budget)),),
        state_root=evidence["candidate_root"], objective_policy=json.dumps(weights, sort_keys=True), declared_universe_complete=True)
    original = None
    for event in events:
        if event["stage"] == "complete":
            for root in event["artifacts"]:
                artifact = store.get(root)
                if "result" in artifact and "case_results" in artifact["result"]:
                    original = artifact
                    atomic_json(directory / "original-finite-codesign.json", artifact)
    assert original is not None
    raw = original["result"]["case_results"][selected["id"]]
    assert raw is not None and raw["problem_hash"] == problem.fingerprint
    independent = verify_master_result(problem, _decode_master(raw))
    assert independent["verdict"] == "PASS", independent
    result = {"schema": "oma.office-current-fitting-capacity-replay/1", "candidate_id": selected["id"],
        "state_root": evidence["candidate_root"], "report_root": evidence["report_root"],
        "checker_version": checker_version(), "capacities": {"new-fabricated-elbows": budget},
        "integer_use": counts, "per_route_exact_report_cost": costs, "total_exact_report_cost": evidence["cost"],
        "actual_original_master_problem_hash": raw["problem_hash"], "independent_current_problem_hash": problem.fingerprint,
        "independent_check": independent, "source": "Current independently checked numerical IFC report values",
        "continuous_optimality_claim": False, "nominal_to_native_cost_bound_claim": False}
    atomic_json(directory / "exact-capacity-replay.json", result)
    return result


def selected_frontier_replay(store, run, selected, route_id, events, directory):
    """Authenticate the selected nominal proof without borrowing native authority."""
    from oma.optimization.fabrication import verify_orthogonal_fabrication
    from oma.optimization.fabrication_frontier import verify_fabrication_frontier
    from oma.optimization.master import rational
    from oma.routing import certified_cells
    from oma.routing.certified_fabrication import verify_body_outer_coverage
    from oma.routing.scenario import RoutingScenario
    state = store.get(selected["state_root"])
    source_files = [(store.resolve_path(source["immutable_path"]), source["sha256"]) for source in state["sources"]]
    assert source_files and all(sha256_file(path) == expected for path, expected in source_files)
    route = next(r for r in state["routes"] if r["id"] == route_id)
    contract = state["derived_artifacts"]["routing_contracts"][route_id]
    scenario = RoutingScenario.model_validate(contract["scenario"])
    reference = selected["proposal_evidence"][route_id]
    artifact = store.get(reference["report_root"])
    context = {"base_root": run["base_root"], "scenario_root": digest(scenario.model_dump(mode="json")),
        "executable_version": checker_version(), "request_demand_id": contract["request_demand_id"],
        "request_root": digest(run["request"]), "max_new_fittings": run["request"]["mission"]["max_new_fittings"]}
    assert artifact["context"] == context and reference["context_root"] == digest(context)
    assert any(e["run_id"] == run["id"] and e["stage"] == "fabrication_graph"
        and reference["report_root"] in e["artifacts"] for e in events)
    report = artifact["report"]
    assert report["context_root"] == digest(context) and report["executable_version"] == checker_version()
    assert digest({k: v for k, v in report.items() if k not in {"report_root", "timing"}}) == report["report_root"]
    model, certificate = report["model"], report["frontier_certificate"]
    assert reference["model_root"] == report["model_root"] == digest(model)
    assert reference["path_certificate_root"] == reference["frontier_certificate_root"] == digest(certificate)
    assert reference["frontier_count_domain_root"] == certificate["count_domain_root"]
    assert reference["coverage_root"] == digest(report["coverage"])
    assert model["context_root"] == digest(context)
    for key in ("diameter_m", "insulation_m", "bend_radius_m", "minimum_straight_m", "clearance_m"):
        assert model[key] == getattr(scenario, key)
    assert model["start"] == list(scenario.start) and model["goal"] == list(scenario.end)
    assert report["coverage"]["allowed_bounds"] == [[str(Fraction(v)) for v in point]
        for point in (scenario.allowed_zone.min, scenario.allowed_zone.max)]
    assert Fraction(report["coverage"]["clearance_m"]) == Fraction(scenario.clearance_m)
    assert model["outer_obstacles"] == report["coverage"]["outer_obstacles"]
    assert model["allowed_bounds"] == report["search_domain"]["graph_allowed_bounds"]
    for lower, inner_lower, inner_upper, upper in zip(report["coverage"]["allowed_bounds"][0],
            model["allowed_bounds"][0], model["allowed_bounds"][1], report["coverage"]["allowed_bounds"][1]):
        assert Fraction(lower) <= Fraction(inner_lower) < Fraction(inner_upper) <= Fraction(upper)
    source = None
    for event in events:
        if event["run_id"] == run["id"] and event["stage"] == "route_geometry_model":
            for root in event["artifacts"]:
                row = store.get(root)
                if row.get("context") == context:
                    source = row["report"]
    assert source is not None and report["source_report_root"] == source["report_root"]
    assert source["scenario_root"] == digest(scenario.model_dump(mode="json"))
    assert digest({k: v for k, v in source.items() if k not in {"report_root", "timing"}}) == source["report_root"]
    assert source["adapter_code_sha256"] == certified_cells.CODE_SHA256
    assert source["dependency_code_sha256"] == certified_cells._DEPENDENCY_HASHES
    assert source["sources"] == [{"path": str(store.resolve_path(s["immutable_path"]).resolve()),
        "sha256": s["sha256"], "transform_m": s.get("transform_m")} for s in state["sources"]]
    assert model["source_roots"] == {"source_report": source["report_root"], "source_coverage": digest(source["coverage"]),
        "body_outer_coverage": digest(report["coverage"]), "search_domain": digest(report["search_domain"]),
        "grid_enrichment": digest(report["grid_enrichment"]), "executable": checker_version(),
        "fitting_budget": digest(report["fitting_budget"])}
    proof_deadline = time.monotonic() + 30
    def checkpoint(stage):
        if time.monotonic() >= proof_deadline:
            raise TimeoutError("Independent campaign proof replay exceeded 30 seconds at " + stage)
    source_check = certified_cells.verify_cell_coverage(source["coverage"], source["model"], checkpoint=checkpoint)
    coverage_check = verify_body_outer_coverage(source["coverage"], report["coverage"], checkpoint=checkpoint)
    assert source_check["status"] == coverage_check["status"] == "PASS"
    objective = {"schema": "oma.fabrication-grid-cost/1",
        "length_weight": str(rational(scenario.objective_weights.get("length_m", 0))),
        "fitting_weight": str(rational(scenario.objective_weights.get("fitting_count", 0)))}
    assert report["pricing_objective"] == objective
    cap = report["fitting_budget"]["represented_count_cap"]
    assert cap == report["fitting_budget"]["declared_max_new_fittings"] == 2
    frontier_check = verify_fabrication_frontier(model, objective, cap, certificate, checkpoint=checkpoint)
    assert frontier_check["status"] == "PASS", frontier_check
    row = next(row for row in certificate["frontier"] if digest(row) == reference["frontier_entry_root"])
    assert row["fittings"] == reference["exact_fittings"] == reference["binary64_exact_fittings"] == 2
    assert row["status"] == "OPTIMAL_PATH"
    converted = [[float(Fraction(v)) for v in point] for point in row["points_m"]]
    assert converted == route["points_m"]
    conversion = next(row for row in report["frontier_conversions"] if row["frontier_entry_root"] == reference["frontier_entry_root"])
    converted_context = digest({"problem_root": digest(model), "frontier_certificate_root": digest(certificate),
        "frontier_entry_root": digest(row), "exact_fittings": 2, "points_m": converted})
    assert conversion["binary64_context_root"] == converted_context
    body = conversion["binary64_fabrication_certificate"]
    assert digest(body) == reference["binary64_fabrication_certificate_root"]
    body_check = verify_orthogonal_fabrication(scenario, converted, body, context_root=converted_context,
        outer_obstacles=report["coverage"]["outer_obstacles"], outer_model_root=digest(report["coverage"]))
    assert body_check["status"] == body_check["fabrication_status"] == "PASS" and body_check["transitions_checked"] == 2
    checkpoint("frontier_replay_complete")
    assert all(sha256_file(path) == expected for path, expected in source_files)
    result = {"status": "PASS", "candidate_id": selected["id"], "route_id": route_id,
        "context_root": digest(context), "model_root": digest(model), "frontier_certificate_root": digest(certificate),
        "frontier_entry_root": digest(row), "count_domain_root": certificate["count_domain_root"],
        "exact_fittings": row["fittings"], "nominal_cost_a_plus_b_pi": row["cost"],
        "source_coverage_check": source_check, "body_coverage_check": coverage_check,
        "frontier_check": frontier_check, "binary64_fabrication_check": body_check,
        "actual_selected_route_points_match": True, "native_acceptance_authority": False,
        "source_support_authenticity_scope": "Matching current source-adapter artifact/publication and input hashes; source numerical support assumptions remain explicit"}
    atomic_json(directory / "selected-frontier-independent-replay.json", result)
    return result


def run_case(store, baseline, spec, budget, directory, seconds):
    directory.mkdir(parents=True)
    project = store.create_project("Office fixed services; new elbow budget " + str(budget), baseline)
    mission = deepcopy(spec["mission"])
    mission["max_new_fittings"] = budget
    run = store.create_run(project["id"], {"operation": "optimize", "mission": mission, "budget_seconds": seconds})
    atomic_json(directory / "mission.json", mission)
    started = time.monotonic()
    result = {"status": "RUNNING", "max_new_fittings": budget, "project_id": project["id"], "run_id": run["id"],
        "baseline_root": run["base_root"], "mission_root": digest(mission), "worker_budget_seconds": seconds,
        "export_budget_seconds": seconds, "prior_native_verdict_reused": False}
    atomic_json(directory / "result.json", result)
    print(json.dumps({"phase": "worker", "budget": budget, "run_id": run["id"], "directory": str(directory)}), flush=True)
    try:
        result["worker"] = supervise_check([sys.executable, "-m", "oma.worker", str(store.directory), run["id"]],
            environment=frozen_environment(store.directory), directory=directory / "worker", deadline=started + seconds + 30)
        result["run"] = store.run(run["id"])
        candidates = [c for c in store.candidates(project["id"]) if c["run_id"] == run["id"] and not c.get("export_recheck")]
        result["candidates"] = [retain_candidate(store, c, directory) for c in candidates]
        events = all_events(store, project["id"])
        atomic_json(directory / "events.json", events)
        for event in events:
            if event["stage"] in ("fabrication_graph", "route_geometry_model", "physical_menu", "physical_menu_compilation"):
                for root in event["artifacts"]:
                    atomic_json(directory / (event["stage"] + "-" + root + ".json"), store.get(root))
        result["frontier_phases"] = [e for e in events if e["stage"] == "fabrication_graph"]
        completion = next((e for e in reversed(events) if e["stage"] == "complete"), None)
        result["completion"] = completion
        atomic_json(directory / "result.json", result)
        assert result["worker"]["status"] == "COMPLETED", result["worker"]
        if budget == 0:
            assert not any(c["status"] == "CHECKED" for c in candidates), result["candidates"]
            assert completion and not completion["payload"]["selected_candidate_ids"]
            assert completion["payload"]["global_lower_bound"] is None
            result.update(status="NO_CHECKED_INCUMBENT_IN_BOUNDED_ZERO_BUDGET_SEARCH", physical_infeasibility_claim=False)
            return result
        assert completion and len(completion["payload"]["selected_candidate_ids"]) == 1
        selected = next(c for c in candidates if c["id"] == completion["payload"]["selected_candidate_ids"][0])
        state = store.get(selected["state_root"])
        contracts = state["derived_artifacts"]["routing_contracts"]
        obstructed_id = next(r for r, c in contracts.items() if c["request_demand_id"] == "obstructed-service")
        proof = selected["proposal_evidence"][obstructed_id]
        assert proof["path_certificate_kind"] == "FABRICATION_FRONTIER", proof
        assert proof["exact_fittings"] == proof["binary64_exact_fittings"] == 2
        summary = next(c for c in result["candidates"] if c["id"] == selected["id"])
        resource = summary["fitting_budget"]
        assert selected["status"] == "CHECKED" and resource["status"] == "PASS"
        assert resource["witness"]["count_complete"] and resource["witness"]["count"] == 2
        assert sorted(resource["witness"]["per_new_route"].values()) == [0, 2]
        assert summary["cross_route"]["status"] == "PASS" and summary["cross_route"]["witness"]["complete_component_coverage"]
        assert len(summary["native"]) == len(contracts) and {n["route_id"] for n in summary["native"]} == set(contracts)
        assert all(n["status"] == "PASS" and n["pairs_accounted"] == n["route_count"] * n["obstacle_count"] for n in summary["native"])
        result["selected_candidate_id"] = selected["id"]
        result["selected_frontier_proof"] = proof
        result["selected_frontier_independent_replay"] = selected_frontier_replay(store, run, selected, obstructed_id, events, directory)
        result["exact_capacity_replay"] = exact_capacity_replay(store, run, selected, events, directory)
        print(json.dumps({"phase": "accept-export", "budget": budget, "candidate_id": selected["id"]}), flush=True)
        result["acceptance"] = store.accept(project["id"], selected["id"], project["revision"],
            "office-joint-fitting-budget", checker_version=checker_version())
        result["export"] = export_project(store, project["id"], selected["id"], draft=False, budget_seconds=seconds)
        manifest = store.get(result["export"]["artifact_root"])
        exported = store.get(manifest["verification_root"])
        atomic_json(directory / "export.manifest.json", manifest)
        atomic_json(directory / "export.verification.json", exported)
        exported_budget = next(r for r in exported["results"] if r["id"] == "joint-new-fitting-budget")
        assert exported["status"] == "PASS" and exported["checker_version"] == checker_version()
        assert exported["candidate_root"] == manifest["exported_state_root"] != selected["state_root"]
        assert exported_budget["status"] == "PASS" and exported_budget["witness"]["count"] == 2
        assert all(manifest["checking"]["release_bindings"].values())
        assert all(sha256_file(f["path"]) == f["sha256"] for f in manifest["files"])
        result["status"] = "FRONTIER_NATIVE_BUDGET_CHECKED_SELECTED_ACCEPTED_EXPORTED_RECHECKED"
    except Exception as error:
        result.update(status="INCOMPLETE", error=f"{type(error).__name__}: {error}")
    finally:
        result["elapsed_seconds"] = time.monotonic() - started
        atomic_json(directory / "result.json", result)
        print(json.dumps({"budget": budget, "status": result["status"], "elapsed_seconds": result["elapsed_seconds"]}), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True)
    parser.add_argument("--budget-seconds", type=float, default=1200.)
    args = parser.parse_args()
    assert checker_version().rsplit(":", 1)[-1] == args.build
    assert os.environ.get("OMA_EXECUTABLE_BUILD", "").rsplit(":", 1)[-1] == args.build
    assert 60 <= args.budget_seconds <= 3600
    store = Store(ROOT / ".oma")
    spec, baseline, origin = specification(store)
    original_head = store.project(origin["project_id"])
    assert all(sha256_file(store.resolve_path(s["immutable_path"])) == s["sha256"] for s in baseline["sources"])
    out = ROOT / "evidence/benchmarks/joint-fitting-budget/office" / uuid.uuid4().hex
    out.mkdir(parents=True)
    atomic_json(out / "specification.json", spec)
    start = time.monotonic()
    result = {"status": "RUNNING", "started_at": utcnow(), "checker_version": checker_version(),
        "script_sha256": sha256_file(__file__), "specification_root": spec["specification_root"], "cases": []}
    print(json.dumps({"directory": str(out), "checker_version": checker_version()}), flush=True)
    try:
        for budget in spec["resource_budgets"]:
            result["cases"].append(run_case(store, baseline, spec, budget, out / ("budget-" + str(budget)), args.budget_seconds))
            atomic_json(out / "result.json", result)
        result["status"] = "BUDGET_TWO_CHECKED_AND_ZERO_BOUNDED_NO_INCUMBENT" if all(c["status"] != "INCOMPLETE" for c in result["cases"]) else "INCOMPLETE"
    finally:
        result["elapsed_seconds"] = time.monotonic() - start
        result["original_project_unchanged"] = store.project(origin["project_id"]) == original_head
        result["original_source_bytes_unchanged"] = all(sha256_file(store.resolve_path(s["immutable_path"])) == s["sha256"] for s in baseline["sources"])
        if not result["original_project_unchanged"] or not result["original_source_bytes_unchanged"]:
            result["status"] = "FAIL_ORIGINAL_PRESERVATION"
        atomic_json(out / "result.json", result)
        print(json.dumps({"directory": str(out), "status": result["status"], "elapsed_seconds": result["elapsed_seconds"]}), flush=True)
    return 0 if result["status"] == "BUDGET_TWO_CHECKED_AND_ZERO_BOUNDED_NO_INCUMBENT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
