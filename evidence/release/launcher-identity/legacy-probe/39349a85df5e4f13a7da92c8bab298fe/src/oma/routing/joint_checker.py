"""Independent composite-state verification, without importing its producer."""
from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import ExitStack
import itertools
import math

from oma.ifc.cad import check_pair
from oma.ifc.audit import sha256_file
from oma.models import CheckResult, VerificationReport, Verdict
from oma.store import digest, utcnow
from oma.verification import CHECKER_VERSION
from .checker import prepare_route_state
from .joint_scenario import parse_joint_request
from .scenario import RoutingScenario
from .fitting_budget import check_joint_fitting_budget, joint_rule_hash


def verify_joint_candidate(store, candidate_id):
    candidate = store.candidate(candidate_id)
    state = store.get(candidate["state_root"])
    run = store.run(candidate["run_id"])
    baseline = store.get(run["base_root"])
    request = parse_joint_request(run["request"]["mission"])
    from oma.verification import candidate_control
    control = candidate_control(store, candidate)
    contracts = state.get("derived_artifacts", {}).get("routing_contracts", {})
    routes = {r["id"]: r for r in state.get("routes", [])}
    old = {r["id"]: r for r in baseline.get("routes", [])}
    previous = baseline.get("derived_artifacts", {}).get("routing_contracts", {})
    if not previous and len(old) == 1:
        rid = next(iter(old))
        derived = baseline["derived_artifacts"]
        previous = {rid: {"scenario": derived["routing_scenario"], "mission": baseline["mission"],
            "source_id": derived["route_materialization"]["source_id"], "request_demand_id": "prior-route"}}
    results = []
    def add(identity, status, reason, witness=None):
        results.append(CheckResult(id=identity, status=Verdict(status), reason=reason,
            scope="Complete proposed route set and protected previous route obligations", witness=witness or {}))
    new = set(routes) - set(old)
    required = {d.id: d for d in request.route_demands}
    covered = Counter(contracts.get(r, {}).get("request_demand_id") for r in new)
    complete = (len(routes) == len(state.get("routes", [])) and set(contracts) == set(routes) and set(old) <= set(routes)
        and len(candidate.get("changed_ids", [])) == len(new)
        and set(candidate.get("changed_ids", [])) == new and covered == Counter({d: 1 for d in required}))
    add("joint-demand-coverage", "PASS" if complete else "FAIL", "Every new demand and prior route has exactly one explicit mission and physical route")
    if not complete:
        return _publish(store, candidate, state, results, {})
    preserved = True
    for rid, route in old.items():
        preserved &= {k: v for k, v in route.items() if k != "geometry_artifact"} == {k: v for k, v in routes[rid].items() if k != "geometry_artifact"}
        preserved &= contracts[rid] == previous.get(rid)
    add("protected-prior-missions", "PASS" if preserved else "FAIL", "Prior route definitions and engineering mission contents are unchanged")
    per_source = defaultdict(set)
    source_files = defaultdict(set)
    materializations = {}
    for rid, route in routes.items():
        material = store.get(route["geometry_artifact"])
        materializations[rid] = material
        source_id = contracts[rid]["source_id"]
        guids = [part["ifc_guid"] for part in material["added_parts"]]
        if len(set(guids)) != len(guids) or per_source[source_id].intersection(guids):
            add("physical-part-ownership", "FAIL", "A physical part was duplicated or assigned to multiple independent routes")
        per_source[source_id].update(guids)
        source_files[source_id].add((str(store.resolve_path(material["export_path"])), material["export_sha256"]))
    add("joint-replacement-coverage", "PASS" if all(len(files) == 1 for files in source_files.values()) else "FAIL",
        "Each edited source has one complete physical replacement containing all its routes")
    # Reopen prior materializations and compare every STEP record, including
    # geometry, ports and relationships. An old passing flag is never reused.
    import ifcopenshell
    preservation_pairs = set()
    for rid in old:
        before = store.get(old[rid]["geometry_artifact"])
        after = materializations[rid]
        intact = sha256_file(store.resolve_path(before["export_path"])) == before["export_sha256"]
        add(f"prior-artifact-integrity:{rid}", "PASS" if intact else "FAIL", "Prior physical artifact still matches its immutable byte identity")
        pair = (str(store.resolve_path(before["export_path"])), str(store.resolve_path(after["export_path"])))
        if pair in preservation_pairs:
            continue
        preservation_pairs.add(pair)
        first, second = (ifcopenshell.open(p) for p in pair)
        changed = []
        original_ids = set()
        for record in first:
            if len(original_ids) % 256 == 0:
                control.checkpoint("joint_prior_record_preservation")
            original_ids.add(record.id())
            try:
                if str(record) != str(second.by_id(record.id())):
                    changed.append(record.id())
            except RuntimeError:
                changed.append(record.id())
        # Appended IFC relationships can change an old object's inverse facts
        # while every old STEP string remains identical. Apply the same inverse
        # rule to the entire previously accepted materialization, including its
        # added route parts, ports and systems, before any negative hint gate.
        from oma.ifc.protected_semantics import added_relationship_effects
        new_part_ids = {entity.id() for entity in second.by_type("IfcElement") if entity.id() not in original_ids}
        inverse_errors = added_relationship_effects(second, original_ids, new_part_ids,
            separately_checked_original_ports=True)
        control.checkpoint("joint_prior_inverse_preservation")
        add(f"prior-physical-preservation:{rid}", "FAIL" if changed or inverse_errors else "PASS",
            "Every prior STEP record and protected inverse relationship is preserved; new containment and separately checked terminal links have explicit scope",
            {"changed_step_ids": changed[:100], "records_checked": len(original_ids), "inverse_effect_errors": inverse_errors})
    missions = [contracts[r]["mission"] for r in sorted(contracts)]
    aggregate = state["mission"]
    aggregate_valid = (aggregate["demands"] == [d for m in missions for d in m["demands"]]
        and aggregate["rule_hash"] == joint_rule_hash(missions, request.max_new_fittings)
        and aggregate["catalog_hash"] == digest([m["catalog_hash"] for m in missions])
        and aggregate["scenario_hash"] == digest([m["scenario_hash"] for m in missions])
        and aggregate["objective_weights"] == request.route_demands[0].alternatives[0].objective_weights
        and set(aggregate["protected_ids"]) == {e["id"] for e in baseline.get("entities", [])})
    add("joint-mission-binding", "PASS" if aggregate_valid else "FAIL", "Composite mission, catalog, rules, protected state and objective bind all individual obligations")
    with ExitStack() as cleanup:
        return _check_prepared_routes(store, candidate, state, baseline, run, control, contracts, routes,
            old, previous, required, per_source, materializations, results, add, cleanup)


def _check_prepared_routes(store, candidate, state, baseline, run, control, contracts, routes,
        old, previous, required, per_source, materializations, results, add, cleanup):
    bodies, objectives, scenarios, preflights, per_route_results = {}, {}, {}, {}, {}
    budget_requested = run["request"]["mission"].get("max_new_fittings") is not None
    budget_recorded = state.get("derived_artifacts", {}).get("joint_fitting_budget") is not None
    for rid, route in routes.items():
        control.checkpoint("joint_route_obligation")
        contract = contracts[rid]
        scenario = RoutingScenario.model_validate(contract["scenario"])
        if rid in old:
            requested = RoutingScenario.model_validate(previous[rid]["scenario"])
        else:
            matches = [s for s in required[contract["request_demand_id"]].alternatives if s.model_dump(mode="json") == scenario.model_dump(mode="json")]
            if not matches:
                add(f"authorized-design-choice:{rid}", "FAIL", "Route changed a requirement outside the original authorized finite choices")
                requested = required[contract["request_demand_id"]].alternatives[0]
            else:
                requested = matches[0]
        scenarios[rid] = scenario
        source = next((s for s in state["sources"] if s["id"] == contract["source_id"]), None)
        source_valid = source is not None and (requested.source_id is None or requested.source_id == source["id"])
        material = materializations[rid]
        source_valid &= source is not None and material["source_sha256"] == source["sha256"] and store.resolve_path(material["source_path"]) == store.resolve_path(source["immutable_path"])
        add(f"route-source-binding:{rid}", "PASS" if source_valid else "FAIL", "Route materialization belongs to its authorized immutable discipline")
        prepared = prepare_route_state(store, state, baseline, requested, scenario, contract["mission"], material, [rid], control,
            candidate_run=run,known_physical_guids=per_source[contract["source_id"]])
        cleanup.callback(prepared.close)
        preflights[rid] = prepared
    from .joint_negative_probe import probe_joint_failure, inputs_unchanged
    admissible = all(item.status in {Verdict.PASS, Verdict.NOT_APPLICABLE} for item in results)
    admissible &= all(p.ready and all(item.status in {Verdict.PASS, Verdict.NOT_APPLICABLE} for item in p.checks)
                      for p in preflights.values())
    probe = probe_joint_failure(store, candidate, state, control) if admissible else None
    probe_root = store.put(probe) if probe and probe.get("supervision") else None
    if probe and probe.get("supervision"):
        # The optional native phase introduces a wait between preparation and
        # continuation. Revalidate bytes on both the failure and fallback paths.
        intact = inputs_unchanged(store, candidate, state, checkpoint=control.checkpoint)
        if not intact or probe["status"] == "FAIL":
            for rid, prepared in preflights.items():
                results.extend(item.model_copy(update={"id": f"{rid}:{item.id}"}) for item in prepared.checks)
            artifact = probe_root
            if intact:
                add("native-cross-route-counterexample", "FAIL", "One newly reopened current native pair violates the current independent-route rule",
                    {"artifact": artifact, "scope": "ONE_COUNTEREXAMPLE", "old_verdict_reused": False,
                     "new_native_verification_performed": True, "native_pair_result": probe["witness"]["native_pair_result"]})
            else:
                add("joint-hint-input-integrity", "FAIL", "Current source or replacement bytes changed after preparation; no pair verdict retained", {"artifact": artifact})
            for rid, scenario in scenarios.items():
                obligations = ["physical-interference-and-clearance", "physical-self-interference", "physical-port-body-attachment",
                    "permitted-zone-containment", "independent-objective-recomputation", "engineering-service", "gravity-slope"]
                if scenario.source_port_guid or scenario.sink_port_guid:
                    obligations.append("original-terminal-body-attachment")
                for identity in obligations:
                    add(f"{rid}:{identity}", "NOT_RUN", "Remaining physical obligations were not evaluated after the early failure", {"artifact": artifact})
            add("cross-route-interference", "NOT_RUN", "Full cross-route Cartesian denominator was not evaluated",
                {"artifact": artifact, "pairs_accounted": 0, "findings": [], "complete_component_coverage": False})
            add("joint-objective", "NOT_RUN", "No native objective or incumbent-selection authority after an early failure", {"artifact": artifact})
            if budget_requested or budget_recorded:
                add("joint-new-fitting-budget", "NOT_RUN", "The complete current fitting resource was not counted after the earlier failure", {"artifact": artifact})
            control.checkpoint("joint_hint_publish")
            return _publish(store, candidate, state, results, {})
    for rid, prepared in preflights.items():
        control.checkpoint("joint_route_native_continuation")
        found, objective, solids = prepared.finish()
        per_route_results[rid] = found
        results.extend(item.model_copy(update={"id": f"{rid}:{item.id}"}) for item in found)
        objectives[rid], bodies[rid] = objective, solids
    if budget_requested or budget_recorded:
        results.append(check_joint_fitting_budget(store, state, baseline, per_route_results,
            candidate_run=run, checkpoint=control.checkpoint))
    # Source checks exclude proposed routes, so the cross-route Cartesian
    # product is a separate complete obligation with the stricter clearance.
    pairs, findings = 0, []
    for first, second in itertools.combinations(routes, 2):
        clearance = max(scenarios[first].clearance_m, scenarios[second].clearance_m)
        for a, b in itertools.product(bodies[first], bodies[second]):
            control.checkpoint("joint_cross_route_pair")
            pair = check_pair(a, b, clearance_m=clearance, numerical_tolerance_m=1e-6)
            pairs += 1
            if pair["status"] != "PASS":
                findings.append(pair)
    cross_status = "FAIL" if any(p["status"] == "FAIL" for p in findings) else "UNKNOWN" if findings else "PASS"
    complete_bodies = all(len(bodies[rid]) == len(materializations[rid]["added_parts"]) for rid in routes)
    if not complete_bodies and cross_status != "FAIL":
        cross_status = "NOT_RUN"
    add("cross-route-interference", cross_status, f"{pairs} physical part pairs between independent routes checked; {len(findings)} unresolved or forbidden pairs; complete component coverage: {complete_bodies}",
        {"pairs_accounted": pairs, "findings": findings, "complete_component_coverage": complete_bodies,
         **({"negative_probe_artifact": probe_root} if probe_root else {})})
    total, objective_witness, complete_objective = _aggregate_objective(routes, per_route_results, objectives)
    add("joint-objective", "PASS" if complete_objective else "NOT_RUN",
        "Objective recomputed from every actual IFC route and independently cross-checked against native solid volumes"
        if complete_objective else "Aggregate objective unavailable: every route requires fresh passing semantic and independent native objective checks, with finite totals",
        objective_witness)
    return _publish(store, candidate, state, results, total)


def _aggregate_objective(routes, per_route_results, objectives):
    """Only complete same-invocation objective checks authorize a finite total."""
    objective_checks = {}
    for rid in routes:
        checks = per_route_results.get(rid, [])
        authority = {identity: [item.status.value for item in checks if item.id == identity]
            for identity in ("exported-physical-semantics", "independent-objective-recomputation")}
        value = objectives.get(rid, {})
        try:
            fields_valid = isinstance(value, dict) and all(
                type(value.get(key)) in (int, float) and math.isfinite(value[key]) and value[key] >= 0
                for key in ("length_m", "fitting_count"))
            fields_valid = fields_valid and value["fitting_count"] == int(value["fitting_count"])
        except (OverflowError, ValueError):
            fields_valid = False
        objective_checks[rid] = {"checks": authority, "fields_valid": fields_valid,
            "status": "PASS" if fields_valid and all(statuses == ["PASS"] for statuses in authority.values()) else "NOT_RUN"}
    complete_objective = (bool(routes) and set(objectives) == set(routes)
        and all(item["status"] == "PASS" for item in objective_checks.values()))
    total = {}
    if complete_objective:
        try:
            total = {key: sum(objectives[rid][key] for rid in routes) for key in ("length_m", "fitting_count")}
            complete_objective = all(math.isfinite(value) for value in total.values())
        except (OverflowError, ValueError):
            complete_objective = False
        if not complete_objective:
            total = {}
    return total, {"per_route": objectives if complete_objective else {},
        "per_route_authority": objective_checks, "finite_complete_aggregate": complete_objective}, complete_objective


def _publish(store, candidate, state, results, objective):
    status = next((v for v in (Verdict.FAIL, Verdict.BLOCKED, Verdict.UNKNOWN, Verdict.NOT_RUN) if any(r.status == v for r in results)), Verdict.PASS)
    report = VerificationReport(candidate_root=candidate["state_root"], mission_hash=digest(state.get("mission")), rule_hash=state["mission"]["rule_hash"],
        checker_version=CHECKER_VERSION, status=status, scope="SIMULTANEOUS_ROUTE_SET: all declared routes and source obstacles; numerical CAD contract; whole-building adequacy not certified",
        results=tuple(results), objective=objective, created_at=utcnow(), common_mode_risks=("Shared IFC parser and numerical OCP kernel", "Finite physical route/design alternatives do not establish complete continuous optimality"))
    store.record_verification(candidate["id"], report)
    return report
