"""Exact resource use is counted from actual independently checked route bodies."""
from copy import deepcopy
import itertools

import pytest
from pydantic import ValidationError

from oma.models import Demand, Mission, Route
from oma.routing.fitting_budget import SCHEMA, check_joint_fitting_budget, joint_rule_hash
from oma.routing.joint import _new_obligation, baseline_contracts
from oma.routing.joint_checker import verify_joint_candidate
from oma.routing.joint_materialize import materialize_route_set
from oma.routing.joint_scenario import JointRoutingScenario
from oma.routing.scenario import RoutingScenario
from oma.store import Store, digest
from oma.worker import WorkerControl, import_sources
from test_ifc_pipeline import make_fixture


def _points(kind, z):
    if kind == "long":
        return [[-1., 1., z], [-1., 3., z], [3., 3., z], [3., 1., z]]
    if kind == "short":
        return [[-1., 1., z], [-.5, 1., z], [-.5, 2.5, z], [2.5, 2.5, z], [2.5, 1., z], [3., 1., z]]
    return [[-1., 4.5, z], [3., 4.5, z]]


def _native_budget_candidate(directory, *, kinds=("long", "short"), budget=6, parent=None):
    """Real IFC fixture reusable by independent adversarial tests; no proposal search."""
    directory.mkdir(parents=True, exist_ok=True)
    if parent is None:
        source = make_fixture(directory / "source.ifc")
        store = Store(directory / "store")
        project = store.create_project("Native fitting resource", {})
        imported = store.create_run(project["id"], {"operation": "import", "paths": [str(source)]})
        import_sources(store, imported, WorkerControl(store, imported["id"]))
    else:
        store, project = parent["store"], {"id": parent["run"]["project_id"]}
    scenarios, paths = {}, {}
    for index, kind in enumerate(kinds):
        key = "demand-" + str(index)
        paths[key] = _points(kind, 3. if parent else 1. + index * .5)
        scenarios[key] = RoutingScenario(start=paths[key][0], end=paths[key][-1], system_type="PRESSURE_PIPE",
            diameter_m=.1, insulation_m=.02, bend_radius_m=.3, minimum_straight_m=.05,
            clearance_m=.1, allowed_zone={"min": [-2., -2., -2.], "max": [6., 6., 6.]},
            scenario_terminals=True, max_candidates=1)
    raw = {"route_demands": [{"id": key, "alternatives": [s.model_dump(mode="json")]} for key, s in scenarios.items()],
        "max_joint_candidates": 1, "max_paths_per_alternative": 1}
    if budget is not None:
        raw["max_new_fittings"] = budget
    run = store.create_run(project["id"], {"operation": "route", "mission": raw, "budget_seconds": 90})
    baseline = store.get(run["base_root"])
    state = deepcopy(baseline)
    selected = state["sources"][0]
    routes, contracts = deepcopy(state.get("routes", [])), baseline_contracts(state)
    specs = {r["id"]: deepcopy(store.get(r["geometry_artifact"])["route_spec"]) for r in routes}
    new_ids = []
    for key, scenario in scenarios.items():
        rid = "budget-" + run["id"][:8] + "-" + key
        contract, ports, section = _new_obligation(baseline, scenario, rid, key, selected["id"])
        contracts[rid] = contract
        state.setdefault("ports", []).extend(p.model_dump(mode="json") for p in ports)
        state.setdefault("assumptions", []).append({"kind": "explicit_scenario", "root": digest(contract["scenario"]), "data": contract["scenario"]})
        routes.append(Route(id=rid, demand_ids=(contract["mission"]["demands"][0]["id"],), service=scenario.system_type,
            points_m=paths[key], section=section, port_ids=tuple(p.id for p in ports), status="MATERIALIZED").model_dump(mode="json"))
        spec = {"route_id": rid, "points_m": paths[key], "diameter_m": scenario.diameter_m, "insulation_m": scenario.insulation_m,
            "bend_radius_m": scenario.bend_radius_m, "minimum_straight_m": scenario.minimum_straight_m,
            "system_type": scenario.system_type, "assumption_root": digest(contract["scenario"])}
        if selected.get("transform_m") is not None:
            spec["source_to_federation_matrix"] = selected["transform_m"]
        specs[rid] = spec
        new_ids.append(rid)
    materialized = materialize_route_set(store, baseline, contracts, specs, directory / "materialized", lambda stage: None)
    for route in routes:
        route["geometry_artifact"] = store.put(materialized[route["id"]])
    missions = [contracts[rid]["mission"] for rid in sorted(contracts)]
    state["routes"] = routes
    state["mission"] = Mission(id="budget-joint:" + run["id"], demands=tuple(Demand.model_validate(d) for m in missions for d in m["demands"]),
        protected_ids=tuple(e["id"] for e in baseline.get("entities", [])), allowed_zones=tuple(z for m in missions for z in m["allowed_zones"]),
        rule_hash=joint_rule_hash(missions, budget), catalog_hash=digest([m["catalog_hash"] for m in missions]),
        scenario_hash=digest([m["scenario_hash"] for m in missions]), objective_weights=next(iter(scenarios.values())).objective_weights).model_dump(mode="json")
    state.setdefault("derived_artifacts", {}).update(routing_contracts=contracts,
        route_exports=[{"source_id": contracts[rid]["source_id"], "route_spec": specs[rid]} for rid in specs])
    state["derived_artifacts"].pop("joint_fitting_budget", None)
    if budget is not None:
        state["derived_artifacts"]["joint_fitting_budget"] = {"schema": SCHEMA, "max_new_fittings": budget}
    candidate = store.add_candidate(run["id"], state, {"kind": "physical_route_set", "changed_ids": new_ids})
    report = verify_joint_candidate(store, candidate["id"])
    per_route = {r["id"]: [] for r in routes}
    for result in report.results:
        for rid in per_route:
            if result.id.startswith(rid + ":"):
                row = result.model_dump(mode="json")
                row["id"] = row["id"][len(rid) + 1:]
                per_route[rid].append(row)
    return {"store": store, "run": run, "candidate": candidate, "state": state, "baseline": baseline,
        "materialized": materialized, "scenarios": scenarios, "report": report, "per_route_results": per_route, "new_ids": new_ids}


@pytest.fixture(scope="module")
def native_budget_cases(tmp_path_factory):
    directory = tmp_path_factory.mktemp("actual-fitting-budgets")
    return {kinds: _native_budget_candidate(directory / "-".join(kinds), kinds=kinds)
        for kinds in itertools.product(("long", "short"), repeat=2)}


def _check(case, *, state=None, evidence=None, checkpoint=None):
    return check_joint_fitting_budget(case["store"], state or case["state"], case["baseline"],
        evidence if evidence is not None else case["per_route_results"], candidate_run=case["run"], checkpoint=checkpoint)


def test_actual_two_route_tradeoff_enforces_total_budget_after_native_checks(native_budget_cases):
    objectives = {}
    for kinds, case in native_budget_cases.items():
        checks = {r.id: r for r in case["report"].results}
        resource = checks["joint-new-fitting-budget"]
        expected = sum(2 if kind == "long" else 4 for kind in kinds)
        assert resource.witness["count_complete"], resource.model_dump(mode="json")
        assert resource.witness["count"] == expected
        assert resource.witness["per_new_route"] == dict(zip(case["new_ids"], (2 if k == "long" else 4 for k in kinds)))
        assert resource.witness["excess"] == max(0, expected - 6)
        assert resource.status == ("PASS" if expected <= 6 else "FAIL")
        assert case["report"].status == resource.status, case["report"].model_dump(mode="json")
        assert checks["cross-route-interference"].status == "PASS"
        objectives[kinds] = case["report"].objective["length_m"]
        assert not resource.witness["global_optimality_claim"]
    assert objectives[("short", "short")] < objectives[("long", "short")] < objectives[("long", "long")]
    assert objectives[("long", "short")] == pytest.approx(objectives[("short", "long")])


@pytest.mark.parametrize("value", [-1, 1025, True, False, 1., "1"])
def test_fitting_budget_requires_bounded_strict_integer(native_budget_cases, value):
    raw = deepcopy(next(iter(native_budget_cases.values()))["run"]["request"]["mission"])
    raw["max_new_fittings"] = value
    with pytest.raises(ValidationError):
        JointRoutingScenario.model_validate(raw)


def test_omitted_budget_preserves_historical_request_and_rule_digest(native_budget_cases):
    case = native_budget_cases[("long", "long")]
    raw = deepcopy(case["run"]["request"]["mission"])
    raw.pop("max_new_fittings")
    request = JointRoutingScenario.model_validate(raw)
    assert "max_new_fittings" not in request.model_dump(mode="json")
    assert request.model_dump(mode="json") == raw
    missions = [c["mission"] for c in case["state"]["derived_artifacts"]["routing_contracts"].values()]
    assert joint_rule_hash(missions) == digest([m["rule_hash"] for m in missions])
    assert len({joint_rule_hash(missions), joint_rule_hash(missions, 0), joint_rule_hash(missions, 1)}) == 3


def test_zero_budget_accepts_new_straights_and_excludes_real_prior_elbows(tmp_path):
    from oma.build_identity import checker_version
    from oma.exporting import export_project
    old = _native_budget_candidate(tmp_path / "prior", kinds=("long", "long"), budget=4)
    assert old["report"].status == "PASS", old["report"].model_dump(mode="json")
    old["store"].accept(old["run"]["project_id"], old["candidate"]["id"], 1, "prior-fitting-use", checker_version=checker_version())
    new = _native_budget_candidate(tmp_path / "new", kinds=("straight",), budget=0, parent=old)
    assert new["report"].status == "PASS", new["report"].model_dump(mode="json")
    resource = next(r for r in new["report"].results if r.id == "joint-new-fitting-budget")
    assert resource.witness["per_new_route"] == {new["new_ids"][0]: 0}
    assert resource.witness["count"] == 0 and resource.witness["count_complete"]
    assert resource.witness["excluded_prior_route_ids"] == sorted(old["new_ids"])
    assert new["report"].objective["fitting_count"] == 4
    new["store"].accept(new["run"]["project_id"], new["candidate"]["id"], 2, "zero-new-fitting-use", checker_version=checker_version())
    bundle = export_project(new["store"], new["run"]["project_id"], new["candidate"]["id"], draft=False, budget_seconds=90)
    assert bundle["status"] == "CHECKED_LOCAL_SCOPE", bundle
    manifest = new["store"].get(bundle["artifact_root"])
    exported_report = new["store"].get(manifest["verification_root"])
    assert exported_report["candidate_root"] != new["candidate"]["state_root"]
    exported_budget = next(r for r in exported_report["results"] if r["id"] == "joint-new-fitting-budget")
    assert exported_budget["status"] == "PASS" and exported_budget["witness"]["count"] == 0
    assert exported_report["objective"]["fitting_count"] == 4


@pytest.mark.parametrize("fault", ["omitted_route", "omitted_check", "unknown", "forged_count", "boolean_count", "duplicate_check", "permuted_route", "omitted_part"])
def test_missing_or_forged_count_evidence_never_becomes_zero_or_pass(native_budget_cases, fault):
    case = native_budget_cases[("long", "short")]
    evidence = deepcopy(case["per_route_results"])
    first, second = case["new_ids"]
    checks = {r["id"]: r for r in evidence[first]}
    if fault == "omitted_route": evidence.pop(first)
    elif fault == "omitted_check": evidence[first].remove(checks["physical-interference-and-clearance"])
    elif fault == "unknown": checks["physical-interference-and-clearance"]["status"] = "UNKNOWN"
    elif fault == "forged_count": checks["exported-physical-semantics"]["witness"]["recomputed"]["fitting_count"] = 0
    elif fault == "boolean_count": checks["exported-physical-semantics"]["witness"]["recomputed"]["fitting_count"] = True
    elif fault == "duplicate_check": evidence[first].append(deepcopy(checks["physical-interference-and-clearance"]))
    elif fault == "permuted_route": evidence[first], evidence[second] = evidence[second], evidence[first]
    else: checks["exported-physical-semantics"]["witness"]["recomputed"]["parts"].pop()
    result = _check(case, evidence=evidence)
    assert result.status != "PASS", result.model_dump(mode="json")
    assert not result.witness["count_complete"] and result.witness["count"] is None


def test_reordered_proof_rows_preserve_exact_current_count(native_budget_cases):
    case = native_budget_cases[("long", "short")]
    evidence = {rid: list(reversed(rows)) for rid, rows in case["per_route_results"].items()}
    assert _check(case, evidence=evidence).status == "PASS"


def test_candidate_cannot_coherently_replace_requested_budget(native_budget_cases):
    case = native_budget_cases[("short", "short")]
    state = deepcopy(case["state"])
    state["derived_artifacts"]["joint_fitting_budget"]["max_new_fittings"] = 8
    missions = [state["derived_artifacts"]["routing_contracts"][r]["mission"] for r in sorted(case["new_ids"])]
    state["mission"]["rule_hash"] = joint_rule_hash(missions, 8)
    result = _check(case, state=state)
    assert result.status == "FAIL" and not result.witness["count_complete"]


def test_late_checkpoint_cancellation_retains_exception_identity(native_budget_cases):
    case = native_budget_cases[("long", "short")]
    error = ValueError("cancel after exact recount")
    def cancel(stage):
        if stage == "joint_fitting_complete":
            raise error
    with pytest.raises(ValueError) as raised:
        _check(case, checkpoint=cancel)
    assert raised.value is error


def test_joint_engine_selects_checked_mixed_routes_with_exact_capacity_row(tmp_path, monkeypatch):
    """Control only the finite menu; actual materialization, child checks and master run."""
    import oma.routing.joint as joint
    from oma.routing.fabrication_evidence import persist_fabrication_proposal
    source = make_fixture(tmp_path / "source.ifc")
    store = Store(tmp_path / "store")
    project = store.create_project("Exact fitting budget engine tradeoff", {})
    imported = store.create_run(project["id"], {"operation": "import", "paths": [str(source)]})
    import_sources(store, imported, WorkerControl(store, imported["id"]))
    demands = []
    for index in range(2):
        path = _points("long", 1. + index * .5)
        scenario = RoutingScenario(start=path[0], end=path[-1], system_type="PRESSURE_PIPE",
            diameter_m=.1, insulation_m=.02, bend_radius_m=.3, minimum_straight_m=.05,
            clearance_m=.1, allowed_zone={"min": [-2., -2., -2.], "max": [6., 6., 6.]},
            scenario_terminals=True, max_candidates=2, objective_weights={"length_m": 1., "fitting_count": 0.})
        demands.append({"id": "service-" + str(index), "alternatives": [scenario.model_dump(mode="json")]})
    raw = {"route_demands": demands, "max_joint_candidates": 4, "max_paths_per_alternative": 2, "max_new_fittings": 6}
    run = store.create_run(project["id"], {"operation": "route", "mission": raw, "budget_seconds": 120})
    def finite_menu(store, run, state, scenario, obstacles, *, checkpoint, request_demand_id, max_fittings, **kwargs):
        assert max_fittings == 6
        for kind in ("long", "short"):
            yield persist_fabrication_proposal(store, run, scenario, {"points_m": _points(kind, scenario.start[2])},
                checkpoint=checkpoint, request_demand_id=request_demand_id)
    original_solve = joint.solve_finite_codesign
    captured = []
    def capture(problem, **kwargs):
        captured.append(problem)
        return original_solve(problem, **kwargs)
    monkeypatch.setattr(joint, "project_proposals", finite_menu)
    monkeypatch.setattr(joint, "solve_finite_codesign", capture)
    joint.joint_project_run(store, run, WorkerControl(store, run["id"]))
    candidates = [c for c in store.candidates(project["id"]) if c["run_id"] == run["id"]]
    assert [c["status"] for c in candidates] == ["CHECKED", "CHECKED", "CHECKED", "REJECTED"]
    event = next(e for e in reversed(store.events(project["id"], limit=1000)) if e["stage"] == "complete")
    assert event["payload"]["selected_candidate_ids"][0] in {candidates[1]["id"], candidates[2]["id"]}
    assert event["payload"]["global_lower_bound"] is None
    assert len(captured) == 1
    for case in captured[0].cases:
        if case.routing is not None:
            assert dict(case.routing.capacities) == {"new-fabricated-elbows": 6}
            uses = [dict(column.resource_use)["new-fabricated-elbows"] for column in case.routing.columns]
            assert all(value in (2, 4) for value in uses) and sum(uses) <= 6
