"""Independent composite-state verification, without importing its producer."""
from __future__ import annotations

from collections import Counter, defaultdict
import itertools

from oma.ifc.cad import check_pair
from oma.ifc.audit import sha256_file
from oma.models import CheckResult, VerificationReport, Verdict
from oma.store import digest, utcnow
from oma.verification import CHECKER_VERSION
from .checker import evaluate_route_state
from .joint_scenario import parse_joint_request
from .scenario import RoutingScenario


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
        for record in first:
            try:
                if str(record) != str(second.by_id(record.id())):
                    changed.append(record.id())
            except RuntimeError:
                changed.append(record.id())
        add(f"prior-physical-preservation:{rid}", "FAIL" if changed else "PASS", "Every STEP record of the previously accepted physical routes is preserved", {"changed_step_ids": changed[:100], "records_checked": len(list(first))})
    bodies, objectives, scenarios = {}, {}, {}
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
        found, objective, solids = evaluate_route_state(store, state, baseline, requested, scenario, contract["mission"], material, [rid], control,
            known_physical_guids=per_source[contract["source_id"]])
        results.extend(item.model_copy(update={"id": f"{rid}:{item.id}"}) for item in found)
        objectives[rid], bodies[rid] = objective, solids
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
        {"pairs_accounted": pairs, "findings": findings, "complete_component_coverage": complete_bodies})
    missions = [contracts[r]["mission"] for r in sorted(contracts)]
    aggregate = state["mission"]
    aggregate_valid = (aggregate["demands"] == [d for m in missions for d in m["demands"]]
        and aggregate["rule_hash"] == digest([m["rule_hash"] for m in missions])
        and aggregate["catalog_hash"] == digest([m["catalog_hash"] for m in missions])
        and aggregate["scenario_hash"] == digest([m["scenario_hash"] for m in missions])
        and aggregate["objective_weights"] == request.route_demands[0].alternatives[0].objective_weights
        and set(aggregate["protected_ids"]) == {e["id"] for e in baseline.get("entities", [])})
    add("joint-mission-binding", "PASS" if aggregate_valid else "FAIL", "Composite mission, catalog, rules, protected state and objective bind all individual obligations")
    total = {k: sum(v.get(k, 0.) for v in objectives.values()) for k in ("length_m", "fitting_count")}
    add("joint-objective", "PASS" if all(objectives.values()) else "BLOCKED", "Objective recomputed from every actual IFC route and independently cross-checked against native solid volumes", {"per_route": objectives})
    return _publish(store, candidate, state, results, total)


def _publish(store, candidate, state, results, objective):
    status = next((v for v in (Verdict.FAIL, Verdict.BLOCKED, Verdict.UNKNOWN, Verdict.NOT_RUN) if any(r.status == v for r in results)), Verdict.PASS)
    report = VerificationReport(candidate_root=candidate["state_root"], mission_hash=digest(state.get("mission")), rule_hash=state["mission"]["rule_hash"],
        checker_version=CHECKER_VERSION, status=status, scope="SIMULTANEOUS_ROUTE_SET: all declared routes and source obstacles; numerical CAD contract; whole-building adequacy not certified",
        results=tuple(results), objective=objective, created_at=utcnow(), common_mode_risks=("Shared IFC parser and numerical OCP kernel", "Finite physical route/design alternatives do not establish complete continuous optimality"))
    store.record_verification(candidate["id"], report)
    return report
