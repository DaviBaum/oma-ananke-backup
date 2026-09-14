"""Current physical evidence admission and interruption-safe incumbent retention.

Finite solvers prove arithmetic over their supplied tables. This boundary checks
that each table row still names a complete, applicable physical PASS. It reuses
the prior physical report only after checking its input/evidence applicability;
it does not rerun CAD or claim continuous/global optimality.
"""
from fractions import Fraction
from dataclasses import replace
import json

from oma.build_identity import checker_version
from oma.ifc.audit import sha256_file
from oma.models import VerificationReport
from oma.store import IntegrityError, digest
from .objectives import reported_route_cost


def _route_obligations(state, scenario, route_id):
    expected = dict.fromkeys(("fixed-request-assumptions", "protected-source-preservation", "materialized-input-integrity",
        "materialization-source-frame", "route-materialization-correspondence", "nominal-fabrication-witness-integrity",
        "fixed-service-obligations", "declared-terminal-state", "exported-physical-semantics",
        "physical-interference-and-clearance", "physical-self-interference", "physical-port-body-attachment",
        "permitted-zone-containment", "independent-objective-recomputation", "gravity-slope", "engineering-service"), "PASS")
    if not state.get("derived_artifacts", {}).get("fabrication_evidence_by_route", {}).get(route_id):
        expected["nominal-fabrication-witness-integrity"] = "NOT_APPLICABLE"
    if scenario["system_type"] != "GRAVITY_DRAINAGE":
        expected["gravity-slope"] = "NOT_APPLICABLE"
    if scenario["target_modality"] != "ENGINEERING_SERVICE":
        expected["engineering-service"] = "NOT_APPLICABLE"
    if scenario.get("source_port_guid") is not None or scenario.get("sink_port_guid") is not None:
        expected["original-terminal-body-attachment"] = "PASS"
    if scenario.get("authorized_opening"):
        expected["authorized-host-subtraction"] = "PASS"
    if state.get("derived_artifacts", {}).get("export_correspondence"):
        expected["export-federation-correspondence"] = "PASS"
    return expected


def _complete_check_obligations(store, state, baseline, kind):
    """All checks a successful current checker must emit, including NA states."""
    if kind == "physical_route":
        if len(state["routes"]) != 1 or state.get("physical_networks"):
            raise IntegrityError("Standalone selection requires exactly its complete route")
        return _route_obligations(state, state["derived_artifacts"]["routing_scenario"], state["routes"][0]["id"])
    if kind == "physical_network":
        if len(state["physical_networks"]) != 1 or state.get("routes"):
            raise IntegrityError("Network selection requires exactly its complete component tree")
        expected = dict.fromkeys(("fixed-network-requirements", "unique-network-demand-coverage", "protected-network-baseline",
            "network-source-and-datum-binding", "network-artifact-integrity", "network-native-semantics", "network-objective",
            "network-all-source-clearance", "network-all-component-pairs", "network-permitted-zone", "network-demand-conditioned-service"), "PASS")
        if state["derived_artifacts"]["network_contract"]["scenario"]["target_modality"] != "ENGINEERING_SERVICE":
            expected["network-demand-conditioned-service"] = "NOT_APPLICABLE"
        if state["derived_artifacts"]["network_contract"]["scenario"].get("pressure_driven") is not None:
            expected["network-pressure-operating-point"] = "PASS"
        if state["derived_artifacts"].get("export_correspondence"):
            expected["network-export-federation-correspondence"] = "PASS"
        return expected
    expected = dict.fromkeys(("joint-demand-coverage", "protected-prior-missions", "joint-replacement-coverage",
        "cross-route-interference", "joint-mission-binding", "joint-objective"), "PASS")
    routes = {r["id"]: r for r in state["routes"]}
    if state.get("physical_networks"):
        raise IntegrityError("Joint routes cannot omit an unrelated physical network")
    for route_id in routes:
        expected[f"route-source-binding:{route_id}"] = "PASS"
        scenario = state["derived_artifacts"]["routing_contracts"][route_id]["scenario"]
        expected.update({route_id + ":" + name: status for name, status in _route_obligations(state, scenario, route_id).items()})
    preserved_pairs = set()
    for route in baseline.get("routes", []):
        route_id = route["id"]
        before, after = (store.get(r["geometry_artifact"]) for r in (route, routes[route_id]))
        expected[f"prior-artifact-integrity:{route_id}"] = "PASS"
        pair = (str(store.resolve_path(before["export_path"])), str(store.resolve_path(after["export_path"])))
        if pair not in preserved_pairs:
            expected[f"prior-physical-preservation:{route_id}"] = "PASS"
            preserved_pairs.add(pair)
    return expected


def current_selection_evidence(store, run, candidate_id, kind, weights, *, checked_files=None, expected_report_root=None):
    """Read a current complete report and verify applicability and actual bytes."""
    candidate = store.candidate(candidate_id)
    if (candidate["project_id"] != run["project_id"] or candidate["run_id"] != run["id"]
            or candidate.get("kind") != kind or candidate["base_revision"] != run["base_revision"]
            or candidate["status"] != "CHECKED" or not candidate.get("report_root")):
        raise IntegrityError("Candidate is not a currently checked member of this run and physical scope")
    if expected_report_root is not None and candidate["report_root"] != expected_report_root:
        raise IntegrityError("Candidate evidence changed during selection")
    state = store.get(candidate["state_root"])
    baseline = store.get(run["base_root"])
    report = VerificationReport.model_validate(store.get(candidate["report_root"])).model_dump(mode="json")
    mission = state["mission"]
    if (report["status"] != "PASS" or report["candidate_root"] != candidate["state_root"]
            or report["checker_version"] != checker_version()
            or report["mission_hash"] != digest(mission) or report["rule_hash"] != mission["rule_hash"]
            or digest(mission["objective_weights"]) != digest(weights)):
        raise IntegrityError("Physical report root, executable, mission, rules or objective policy is stale or misbound")
    expected_checks = _complete_check_obligations(store, state, baseline, kind)
    if kind == "physical_route_set":
        requested_budget = run["request"]["mission"].get("max_new_fittings")
        recorded_budget = state.get("derived_artifacts", {}).get("joint_fitting_budget")
        if requested_budget is not None:
            if recorded_budget != {"schema": "oma.joint-new-fitting-budget/1", "max_new_fittings": requested_budget}:
                raise IntegrityError("Current fitting budget does not bind the requested increment")
            expected_checks["joint-new-fitting-budget"] = "PASS"
        elif recorded_budget is not None:
            raise IntegrityError("Unrequested fitting budget was retained from a different increment")
    actual_checks = {r["id"]: r["status"] for r in report["results"]}
    if len(actual_checks) != len(report["results"]) or actual_checks != expected_checks:
        raise IntegrityError("Physical report omits, duplicates, adds or weakens a mandatory check obligation")
    fitting_budget = None
    if kind == "physical_route_set" and requested_budget is not None:
        witness = next(r["witness"] for r in report["results"] if r["id"] == "joint-new-fitting-budget")
        new_ids = {r["id"] for r in state["routes"]} - {r["id"] for r in baseline.get("routes", [])}
        counts = witness.get("per_new_route", {})
        if (type(requested_budget) is not int or requested_budget < 0
                or witness.get("count_complete") is not True or set(counts) != new_ids
                or any(type(value) is not int or value < 0 for value in counts.values())
                or witness.get("count") != sum(counts.values()) or sum(counts.values()) > requested_budget):
            raise IntegrityError("Joint resource evidence does not contain a complete feasible current increment count")
        fitting_budget = {"max_new_fittings": requested_budget, "per_new_route": counts}
    records = state.get("physical_networks", []) if kind == "physical_network" else state.get("routes", [])
    if not records or len({r["id"] for r in records}) != len(records):
        raise IntegrityError("Complete unique physical route/network inventory required")
    per_route_costs = None
    if kind == "physical_route_set":
        scope = "SIMULTANEOUS_ROUTE_SET: all declared routes and source obstacles; numerical CAD contract; whole-building adequacy not certified"
        values = next(r["witness"]["per_route"] for r in report["results"] if r["id"] == "joint-objective")
        if set(values) != {r["id"] for r in records}:
            raise IntegrityError("Joint objective omits or invents a physical route")
        per_route_costs = {rid: str(reported_route_cost(value, weights)) for rid, value in values.items()}
        cost = sum((Fraction(value) for value in per_route_costs.values()), Fraction(0))
    elif kind == "physical_network":
        scope = "SHARED_PHYSICAL_NETWORK: complete local component tree, fixed demands and all source obstacles; whole-building adequacy not certified"
        cost = reported_route_cost(report["objective"], weights)
    elif kind == "physical_route":
        scenario = state["derived_artifacts"]["routing_scenario"]
        scope = f"{scenario['target_modality']}: proposed route{' and one explicitly authorized host opening' if scenario.get('authorized_opening') else ' only'}; numerical CAD contract, not whole-building approval"
        cost = reported_route_cost(report["objective"], weights)
    else:
        raise IntegrityError("Unsupported physical selection scope")
    if report["scope"] != scope:
        raise IntegrityError("Physical report omits the complete required selection scope")
    files = [(store.resolve_path(s["immutable_path"]), s["sha256"]) for s in state["sources"]]
    for record in records:
        material = store.get(record["geometry_artifact"])
        files.append((store.resolve_path(material["export_path"]), material["export_sha256"]))
    if kind == "physical_route_set":
        for previous in baseline.get("routes", []):
            material = store.get(previous["geometry_artifact"])
            files.append((store.resolve_path(material["export_path"]), material["export_sha256"]))
    if not state["sources"]:
        raise IntegrityError("Physical selection has no original IFC denominator")
    checked_files = checked_files if checked_files is not None else set()
    for path, expected in files:
        key = (str(path), expected)
        if key not in checked_files:
            if not path.is_file() or sha256_file(path) != expected:
                raise IntegrityError("Original IFC or checked candidate bytes changed before selection")
            checked_files.add(key)
    current = store.candidate(candidate_id)
    if any(current[key] != candidate[key] for key in ("status", "state_root", "report_root")):
        raise IntegrityError("Candidate verification changed while checking selection applicability")
    return {"candidate_id": candidate_id, "candidate_root": candidate["state_root"], "report_root": candidate["report_root"],
        "checker_version": report["checker_version"], "mission_hash": report["mission_hash"], "rule_hash": report["rule_hash"],
        "scope": report["scope"], "objective": report["objective"], "objective_weights": weights,
        "cost": str(cost), "per_route_costs": per_route_costs, "fitting_budget": fitting_budget,
        "files_checked": len(set((str(p), h) for p, h in files)),
        "required_check_inventory_root": digest(expected_checks),
        "physical_evidence_use": "Prior complete native/numerical report reused only under matching persisted state, rules, mission, executable and current input bytes; CAD is not rerun"}


def try_selection_evidence(store, run, candidate_id, kind, weights, **kwargs):
    try:
        return current_selection_evidence(store, run, candidate_id, kind, weights, **kwargs), None
    except (ValueError, KeyError, TypeError, StopIteration, OSError) as exc:
        return None, {"candidate_id": candidate_id, "reason": str(exc)}


def refresh_selection_cases(store, run, cases, kind, weights):
    """Rebuild arithmetic rows after later candidate checks may have intervened."""
    from oma.optimization.finite import FiniteOutcome
    from oma.optimization.master import MasterProblem, RouteColumn
    refreshed, checked_files = [], set()
    for case in cases:
        evidence, _ = try_selection_evidence(store, run, case.id, kind, weights, checked_files=checked_files)
        if not evidence:
            # This final selection table admits current complete PASS only.
            # Its excluded cases remain unresolved here; the separate physical
            # archive retains the actual negative checks and their witnesses.
            refreshed.append(replace(case, materialization=FiniteOutcome(case.id, "UNKNOWN"), routing=None))
            continue
        costs = evidence["per_route_costs"] or {"physical-network": evidence["cost"]}
        budget = evidence["fitting_budget"]
        capacities = (("new-fabricated-elbows", Fraction(budget["max_new_fittings"])),) if budget else ()
        resource_use = budget["per_new_route"] if budget else {}
        master = MasterProblem(net_ids=tuple(costs), columns=tuple(RouteColumn(rid, rid, cost,
            resource_use=(("new-fabricated-elbows", Fraction(resource_use[rid])),) if rid in resource_use else (),
            artifact_ref=evidence["report_root"]) for rid, cost in costs.items()), capacities=capacities,
            state_root=evidence["candidate_root"], objective_policy=json.dumps(weights, sort_keys=True), declared_universe_complete=True)
        refreshed.append(replace(case, design_root=evidence["candidate_root"], routing=master,
            materialization=FiniteOutcome(case.id, "PASS", Fraction(0), evidence_root=evidence["report_root"])))
    return refreshed


def retain_current_incumbent(store, run, candidate_ids, kind, weights, *, arithmetic_selected=()):
    """Retain a feasible complete candidate even if finite arithmetic stopped.

    A second fresh read checks the chosen evidence after the other rows. An
    intervening recheck invalidates that row instead of inheriting its old PASS.
    This is a feasible-incumbent disposition, never a master optimum certificate.
    """
    checked_files, rows, excluded = set(), [], []
    for candidate_id in dict.fromkeys(candidate_ids):
        row, failure = try_selection_evidence(store, run, candidate_id, kind, weights, checked_files=checked_files)
        if row:
            rows.append(row)
        else:
            excluded.append(failure)
    rows.sort(key=lambda row: (Fraction(row["cost"]), row["candidate_id"]))
    chosen = None
    for row in rows:
        current, failure = try_selection_evidence(store, run, row["candidate_id"], kind, weights,
            expected_report_root=row["report_root"])
        if current:
            chosen = current
            break
        excluded.append(failure)
    rejected = {row["candidate_id"] for row in excluded}
    artifact = store.put({"schema": "oma.current-checked-incumbent/1", "run_id": run["id"], "base_root": run["base_root"],
        "request_root": digest(run["request"]), "status": "FEASIBLE_CURRENT_CHECKED_INCUMBENT" if chosen else "NO_CURRENT_CHECKED_INCUMBENT",
        "selected": chosen, "examined_current_reports": rows, "excluded": excluded,
        "arithmetic_selected_candidate_ids": list(arithmetic_selected),
        "selection_basis": "Exact declared weighted report values among currently applicable complete physical candidates",
        "master_optimality_claim": False, "continuous_global_optimality_claim": False,
        "new_native_verification_performed": False, "selected_source_and_candidate_bytes_freshly_checked": chosen is not None})
    return {"selected_candidate_ids": [chosen["candidate_id"]] if chosen else [], "artifact_root": artifact,
        "checked_feasible": len([row for row in rows if row["candidate_id"] not in rejected])}
