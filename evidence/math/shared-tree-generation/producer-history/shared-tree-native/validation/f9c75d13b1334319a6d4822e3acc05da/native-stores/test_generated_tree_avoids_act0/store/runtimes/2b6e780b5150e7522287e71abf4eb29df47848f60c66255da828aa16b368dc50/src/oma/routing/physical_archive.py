"""Bind exact finite menu abstractions to actual immutable physical reports.

The compiler observes a named verdict/objective/scope projection. It never
merges evidence identity, reuses native PASS or accepts a physical candidate.
"""
from collections import Counter
import copy
import hashlib
import time

from oma.build_identity import checker_version
from oma.models import VerificationReport
from oma.optimization.physical_menu import compile_physical_menu, verify_physical_menu
from oma.store import IntegrityError, digest


PROJECTION = {"schema": "oma.physical-report-projection/1",
    "fields": ["status", "objective", "scope", "result_status_counts", "common_mode_risks"],
    "equivalence": "Only these report observations under this frozen menu and its single-choice replacement actions",
    "evidence_identity_equivalence": False, "native_pass_reuse": False,
    "candidate_acceptance_authority": False, "continuous_universe_complete": False}


class ArchiveBudgetExceeded(Exception):
    pass


def _checkpoint(deadline):
    if deadline is not None and time.monotonic() >= deadline:
        raise ArchiveBudgetExceeded()


def _byte_hash(path, deadline):
    result = hashlib.sha256()
    _checkpoint(deadline)
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            result.update(chunk)
            _checkpoint(deadline)
    return result.hexdigest()


def route_choice_definition(scenario, proposal, source):
    raw = scenario.model_dump(mode="json")
    spec = {"points_m": proposal["points_m"], "diameter_m": scenario.diameter_m,
        "insulation_m": scenario.insulation_m, "bend_radius_m": scenario.bend_radius_m,
        "minimum_straight_m": scenario.minimum_straight_m, "system_type": scenario.system_type,
        "assumption_root": digest(raw)}
    for key in ("source_port_guid", "sink_port_guid"):
        if getattr(scenario, key):
            spec[key] = getattr(scenario, key)
    if source.get("transform_m") is not None:
        spec["source_to_federation_matrix"] = source["transform_m"]
    return {"scenario": raw, "source_id": source["id"], "source_sha256": source["sha256"], "route_spec": spec}


def freeze_route_menu(store, run, state, request, choices):
    if len(request.route_demands) != len(choices):
        raise ValueError("Generated choices must cover every requested demand exactly")
    context = {"base_root": run["base_root"], "request_root": digest(run["request"]),
        "checker_version": checker_version(), "sources": state["sources"],
        "generation_scope": "The actual generated finite menu; generator and continuous universe remain open"}
    domains, definitions = [], {}
    for demand, options in zip(request.route_demands, choices):
        menu = []
        for label, scenario, proposal in options:
            source = next((s for s in state["sources"] if s["id"] == scenario.source_id),
                state["sources"][0] if scenario.source_id is None else None)
            if source is None:
                raise ValueError("A frozen route choice names no immutable source")
            definition = route_choice_definition(scenario, proposal, source)
            definition_root = store.put(definition)
            menu.append({"id": label, "definition_root": definition_root})
            definitions[f"{demand.id}/{label}"] = definition_root
        domains.append({"id": demand.id, "choices": menu})
    return store.put({"schema": "oma.persisted-route-menu/1", "run_id": run["id"],
        "context_root": store.put(context), "projection_contract_root": store.put(PROJECTION),
        "demands": domains, "definitions": definitions})


def _current_bytes(store, context, deadline):
    if context["checker_version"] != checker_version():
        raise IntegrityError("Frozen physical menu belongs to another executable build")
    for source in context["sources"]:
        path = store.resolve_path(source["immutable_path"])
        if not path.is_file() or _byte_hash(path, deadline) != source["sha256"]:
            raise IntegrityError("Frozen menu source bytes no longer match their immutable identities")


def assemble_route_menu_problem(store, frozen_root, candidate_ids, *, deadline=None):
    _checkpoint(deadline)
    frozen = store.get(frozen_root)
    context = store.get(frozen["context_root"])
    run = store.run(frozen["run_id"])
    if run["base_root"] != context["base_root"] or digest(run["request"]) != context["request_root"]:
        raise IntegrityError("Frozen menu does not bind the original request and base state")
    if frozen["projection_contract_root"] != digest(PROJECTION) or digest(store.get(frozen["projection_contract_root"])) != digest(PROJECTION):
        raise IntegrityError("Unsupported report projection contract")
    baseline = store.get(run["base_root"])
    if context["sources"] != baseline["sources"]:
        raise IntegrityError("Frozen source denominator differs from the complete original baseline")
    from .joint_scenario import parse_joint_request
    request = parse_joint_request(run["request"]["mission"])
    if [d["id"] for d in frozen["demands"]] != [d.id for d in request.route_demands]:
        raise IntegrityError("Frozen menu changes the ordered requested demand coverage")
    for domain, requested in zip(frozen["demands"], request.route_demands):
        for choice in domain["choices"]:
            _checkpoint(deadline)
            definition = store.get(choice["definition_root"])
            matches = [s for s in requested.alternatives if s.model_dump(mode="json") == definition["scenario"]]
            if not matches:
                raise IntegrityError("Frozen choice changes an authorized scenario")
            scenario = matches[0]
            source = next((s for s in baseline["sources"] if s["id"] == scenario.source_id),
                baseline["sources"][0] if scenario.source_id is None else None)
            if source is None or route_choice_definition(scenario, definition["route_spec"], source) != definition:
                raise IntegrityError("Frozen choice omits fixed physical inputs or the resolved source datum")
    _current_bytes(store, context, deadline)
    previous_ids = {r["id"] for r in baseline.get("routes", [])}
    examined, checked_bytes = [], set()
    for candidate_id in candidate_ids:
        _checkpoint(deadline)
        candidate = store.candidate(candidate_id)
        if candidate["run_id"] != run["id"] or candidate.get("physical_menu_root") != frozen_root:
            raise IntegrityError("Candidate does not belong to the frozen physical menu")
        assignment = candidate.get("physical_menu_assignment")
        if not isinstance(assignment, list) or len(assignment) != len(frozen["demands"]):
            raise IntegrityError("Candidate lacks its complete frozen assignment")
        state = store.get(candidate["state_root"])
        report = VerificationReport.model_validate(store.get(candidate["report_root"])).model_dump(mode="json")
        if (report["candidate_root"] != candidate["state_root"] or report["checker_version"] != context["checker_version"]
                or report["mission_hash"] != digest(state["mission"]) or report["rule_hash"] != state["mission"]["rule_hash"]
                or not report["scope"].startswith("SIMULTANEOUS_ROUTE_SET:")):
            raise IntegrityError("Physical report is stale, misbound or outside the declared route-set scope")
        verdict = "PASS" if report["status"] == "PASS" else "FAIL" if report["status"] == "FAIL" else "UNKNOWN"
        expected_status = "CHECKED" if verdict == "PASS" else "REJECTED" if verdict == "FAIL" else report["status"]
        if candidate["status"] != expected_status:
            raise IntegrityError("Candidate flag and independently checked report disagree")
        contracts = state["derived_artifacts"]["routing_contracts"]
        new = [r for r in state["routes"] if r["id"] not in previous_ids]
        if Counter(contracts[r["id"]]["request_demand_id"] for r in new) != Counter(d["id"] for d in frozen["demands"]):
            raise IntegrityError("Physical candidate does not cover the complete ordered demand menu")
        for demand, label in zip(frozen["demands"], assignment):
            choice = next((c for c in demand["choices"] if c["id"] == label), None)
            if choice is None:
                raise IntegrityError("Physical candidate lies outside the frozen finite menu")
            definition = store.get(choice["definition_root"])
            route = next(r for r in new if contracts[r["id"]]["request_demand_id"] == demand["id"])
            contract = contracts[route["id"]]
            material = store.get(route["geometry_artifact"])
            actual_spec = {k: v for k, v in material["route_spec"].items() if k != "route_id"}
            if (contract["scenario"] != definition["scenario"] or contract["source_id"] != definition["source_id"]
                    or material["source_sha256"] != definition["source_sha256"] or actual_spec != definition["route_spec"]):
                raise IntegrityError("Actual physical realization differs from its frozen choice definition")
        for route in state["routes"]:
            material = store.get(route["geometry_artifact"])
            pair = (str(store.resolve_path(material["export_path"])), material["export_sha256"])
            if pair not in checked_bytes:
                path = store.resolve_path(pair[0])
                if not path.is_file() or _byte_hash(path, deadline) != pair[1]:
                    raise IntegrityError("Checked physical candidate bytes changed")
                checked_bytes.add(pair)
        projection = {k: copy.deepcopy(report[k]) for k in ("status", "objective", "scope", "common_mode_risks")}
        projection["result_status_counts"] = dict(sorted(Counter(r["status"] for r in report["results"]).items()))
        examined.append({"assignment": assignment, "candidate_id": candidate_id, "state_root": candidate["state_root"],
            "report_root": candidate["report_root"], "verdict": verdict, "projection": projection})
    return {"schema": "oma.physical-menu/1", "context_root": frozen["context_root"],
        "projection_contract_root": frozen["projection_contract_root"], "demands": frozen["demands"], "examined": examined}


def compile_route_archive(store, frozen_root, candidate_ids, *, deadline):
    began = time.monotonic()
    frozen = store.get(frozen_root)
    if any(not d["choices"] for d in frozen["demands"]):
        return store.put({"status": "UNKNOWN", "reason": "EMPTY_GENERATED_MENU", "frozen_menu_root": frozen_root})
    if began >= deadline:
        return store.put({"status": "UNKNOWN", "reason": "RUN_TIME_BUDGET", "frozen_menu_root": frozen_root})
    try:
        problem = assemble_route_menu_problem(store, frozen_root, candidate_ids, deadline=deadline)
        _checkpoint(deadline)
        certificate = compile_physical_menu(problem, max_assignments=256, max_work=300_000)
        _checkpoint(deadline)
        if certificate["status"] == "UNKNOWN":
            check = {"status": "NOT_RUN", "reason": certificate["reason"]}
        else:
            check = verify_physical_menu(problem, certificate, max_assignments=256, max_work=300_000)
            _checkpoint(deadline)
            if check["status"] == "FAIL":
                raise IntegrityError(f"Physical menu certificate failed independent replay: {check}")
    except ArchiveBudgetExceeded:
        return store.put({"status": "UNKNOWN", "reason": "RUN_TIME_BUDGET", "frozen_menu_root": frozen_root,
            "candidate_acceptance_authority": False})
    return store.put({"schema": "oma.checked-route-menu-archive/1", "frozen_menu_root": frozen_root,
        "problem_root": store.put(problem), "certificate_root": store.put(certificate), "independent_check": check,
        "summary": certificate.get("summary") if check["status"] == "PASS" else None,
        "status": certificate["status"] if check["status"] == "PASS" else "UNKNOWN",
        "elapsed_seconds": time.monotonic() - began, "candidate_acceptance_authority": False})
