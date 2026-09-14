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
import hashlib
import shutil
import sqlite3
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

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "AGENTS.md").is_file())
STAGE = ROOT / ".oma/development/next-best-fabrication"
RETAINED_SPEC = ROOT / "evidence/benchmarks/joint-fitting-budget/office/111d3376fd4d4537887a0e63d1f80894/specification.json"
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
    is_residual = reference["path_certificate_kind"] == "FABRICATION_RESIDUAL_FRONTIER"
    assert reference["model_root"] == report["model_root"] == digest(model)
    if not is_residual:
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
    original_certificate = certificate
    residual_check = None
    if is_residual:
        from oma.optimization.fabrication_alternatives import verify_fabrication_alternatives
        residual = report["residual_round"]
        assert residual["status"] == "CHECKED_RESIDUAL_PROPOSALS"
        original_entries = {digest(entry): entry for entry in original_certificate["frontier"]}
        conversions = report["frontier_conversions"]
        assert len(conversions) == len(original_entries) and {c["frontier_entry_root"] for c in conversions} == set(original_entries)
        generated_words, provenance = [], []
        for c in conversions:
            if c["status"] != "BINARY64_FABRICATION_CHECKED":
                continue
            e = original_entries[c["frontier_entry_root"]]
            assert e["status"] == "OPTIMAL_PATH"
            pts = [[float(Fraction(x)) for x in p] for p in e["points_m"]]
            ctx = digest({"problem_root": digest(model), "frontier_certificate_root": digest(original_certificate),
                "frontier_entry_root": digest(e), "exact_fittings": e["fittings"], "points_m": pts})
            assert c["binary64_context_root"] == ctx
            checked = verify_orthogonal_fabrication(scenario, pts, c["binary64_fabrication_certificate"], context_root=ctx,
                outer_obstacles=report["coverage"]["outer_obstacles"], outer_model_root=digest(report["coverage"]))
            assert checked["status"] == checked["fabrication_status"] == "PASS" and checked["transitions_checked"] == e["fittings"]
            generated_words.append(e["path_states"])
            provenance.append({"word_root": digest(e["path_states"]), "original_entry_root": digest(e),
                "binary64_fabrication_certificate_root": digest(c["binary64_fabrication_certificate"])})
            checkpoint("residual_original_word_replay")
        ledger = {"original_certificate_root": digest(original_certificate), "generated_words": provenance,
            "excluded_words": generated_words}
        assert ledger == residual["generation_ledger"] and digest(ledger) == residual["generation_ledger_root"] == reference["generation_ledger_root"]
        certificate = residual["certificate"]
        assert reference["path_certificate_root"] == reference["residual_certificate_root"] == digest(certificate)
        for refkey, certkey in (("residual_count_domain_root", "count_domain_root"), ("residual_exclusion_root", "exclusion_root"), ("residual_model_root", "residual_model_root")):
            assert reference[refkey] == certificate[certkey]
        residual_check = verify_fabrication_alternatives(model, objective, cap, generated_words, certificate, checkpoint=checkpoint)
        assert residual_check["status"] == "PASS", residual_check
        row = next(e for e in certificate["frontier"] if digest(e) == reference["residual_entry_root"])
        assert row["status"] == "RESIDUAL_OPTIMAL_PATH" and [s[:7] for s in row["path_states"]] not in generated_words
        conversion = next(c for c in residual["attempts"] if c["entry_root"] == digest(row))
        converted = [[float(Fraction(v)) for v in point] for point in row["points_m"]]
        converted_context = digest({"model_root": digest(model), "residual_certificate_root": digest(certificate),
            "entry_root": digest(row), "generation_ledger_root": digest(ledger), "exact_fittings": 2, "points_m": converted})
    else:
        row = next(row for row in certificate["frontier"] if digest(row) == reference["frontier_entry_root"])
        assert row["status"] == "OPTIMAL_PATH"
        conversion = next(c for c in report["frontier_conversions"] if c["frontier_entry_root"] == reference["frontier_entry_root"])
        converted = [[float(Fraction(v)) for v in point] for point in row["points_m"]]
        converted_context = digest({"problem_root": digest(model), "frontier_certificate_root": digest(certificate),
            "frontier_entry_root": digest(row), "exact_fittings": 2, "points_m": converted})
    assert row["fittings"] == reference["exact_fittings"] == reference["binary64_exact_fittings"] == 2
    assert converted == route["points_m"]
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
        "frontier_check": frontier_check, "residual_check": residual_check, "selected_certificate_kind": reference["path_certificate_kind"],
        "original_frontier_certificate_root": digest(original_certificate), "binary64_fabrication_check": body_check,
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
        assert proof["path_certificate_kind"] in {"FABRICATION_FRONTIER", "FABRICATION_RESIDUAL_FRONTIER"}, proof
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
        exported_candidate = store.candidate(manifest["checking"]["exported_candidate_id"])
        result["exported_candidate"] = retain_candidate(store, exported_candidate, directory)
        assert result["exported_candidate"]["status"] == "CHECKED"
        result["status"] = "FRONTIER_NATIVE_BUDGET_CHECKED_SELECTED_ACCEPTED_EXPORTED_RECHECKED"
    except Exception as error:
        result.update(status="INCOMPLETE", error=f"{type(error).__name__}: {error}")
    finally:
        result["elapsed_seconds"] = time.monotonic() - started
        atomic_json(directory / "result.json", result)
        print(json.dumps({"budget": budget, "status": result["status"], "elapsed_seconds": result["elapsed_seconds"]}), flush=True)
    return result


class ReadOnlyOriginal(Store):
    def __init__(self):
        self.directory = (ROOT / '.oma').resolve()
        self.database = self.directory / 'oma.sqlite3'
        self.blobs = self.directory / 'blobs'

    def connect(self):
        from oma.store import _Connection
        db = sqlite3.connect(self.database.as_uri() + '?mode=ro', uri=True, factory=_Connection)
        db.row_factory = sqlite3.Row
        return db

    def put(self, value):
        raise RuntimeError('Original input Store is read-only')


def copy_baseline(original, target, baseline_root):
    from oma.backup import _asset_references, _content_roots
    store = Store(target)
    pending, copied, references = {baseline_root}, set(), set()
    while pending:
        root = pending.pop()
        if root in copied:
            continue
        value = original.get(root)
        shutil.copyfile(original.blobs / (root + '.json.z'), store.blobs / (root + '.json.z'))
        assert store.get(root) == value
        copied.add(root)
        references.update(_asset_references(value))
        pending.update(r for r in _content_roots(value) if r not in copied and (original.blobs / (r + '.json.z')).is_file())
    assets, aliases = [], []
    for reference in sorted(references):
        source = original.resolve_path(reference).resolve()
        assert source.is_file(), source
        hashed = sha256_file(source)
        relative = Path('copied-baseline-inputs') / hashed / source.name
        destination = store.directory / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copyfile(source, destination)
        assert sha256_file(source) == sha256_file(destination) == hashed
        aliases.append((str(Path(reference).expanduser()), str(relative), hashed))
        assets.append({'reference': reference, 'source': str(source), 'copy': str(destination), 'sha256': hashed})
    with store.transaction() as db:
        db.executemany('INSERT INTO asset_aliases VALUES(?,?,?)', aliases)
    record = {'status': 'BASELINE_CLOSURE_COPIED', 'baseline_root': baseline_root,
        'artifact_roots': sorted(copied), 'assets': assets, 'original_database_access': 'READ_ONLY'}
    atomic_json(store.directory / 'baseline-input-copy.json', record)
    return store, record


def seed_native_cache(original, store, baseline, policy):
    """Copy exact-key native conversion artifacts; the checker revalidates them."""
    from oma.ifc.cad_cache import _key
    records = []
    for source in baseline['sources']:
        path = store.resolve_path(source['immutable_path'])
        key = _key(path, None, policy)
        root = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()
        origin = original.directory / 'cad-cache' / 'entries' / root
        if not (origin / 'manifest.json').is_file():
            records.append({'source_sha256': source['sha256'], 'cache_key': root, 'status': 'NO_EXACT_PRIOR_ENTRY'})
            continue
        raw = (origin / 'manifest.json').read_bytes()
        assert hashlib.sha256(raw).hexdigest() == (origin / 'manifest.sha256').read_text().strip()
        manifest = json.loads(raw)
        assert manifest['key'] == key
        destination = store.directory / 'cad-cache' / 'entries' / root
        destination.mkdir(parents=True)
        files = []
        for name in ('manifest.json', 'manifest.sha256'):
            shutil.copyfile(origin / name, destination / name)
            assert sha256_file(origin / name) == sha256_file(destination / name)
        for item in manifest['objects']:
            name = item['brep_sha256'] + '.brep.gz'
            asset = original.directory / 'cad-cache' / 'objects' / name
            target = store.directory / 'cad-cache' / 'objects' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(asset, target)
            assert sha256_file(asset) == sha256_file(target) == item['compressed_sha256']
            files.append({'name': name, 'sha256': item['compressed_sha256']})
        records.append({'source_sha256': source['sha256'], 'cache_key': root, 'status': 'EXACT_KEY_ARTIFACTS_COPIED',
            'manifest_sha256': hashlib.sha256(raw).hexdigest(), 'objects': files,
            'authority': 'Locally trusted checker conversion provenance only; source coverage and native topology rechecked, no pair verdict reuse'})
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', required=True)
    parser.add_argument('--budget-seconds', type=float, default=1200.)
    args = parser.parse_args()
    assert checker_version().rsplit(':', 1)[-1] == args.build
    assert os.environ.get('OMA_EXECUTABLE_BUILD', '').rsplit(':', 1)[-1] == args.build
    assert 60 <= args.budget_seconds <= 3600
    original = ReadOnlyOriginal()
    spec, baseline, origin = specification(original)
    retained = json.loads(RETAINED_SPEC.read_text())
    assert spec == retained and digest({k:v for k,v in spec.items() if k != 'specification_root'}) == spec['specification_root']
    old_candidate = original.candidate(HISTORICAL_CANDIDATE)
    old_head = original.project(origin['project_id'])
    originals = [{'path': str(original.resolve_path(s['immutable_path']).resolve()), 'sha256': s['sha256']} for s in baseline['sources']]
    assert [s['sha256'] for s in originals] == spec['original_source_hashes']
    assert all(sha256_file(s['path']) == s['sha256'] for s in originals)
    identifier = uuid.uuid4().hex
    out = STAGE / 'evidence/benchmarks/office-budgets' / identifier
    out.mkdir(parents=True)
    import oma
    source_directory = Path(oma.__file__).resolve().parent
    declaration = {'schema': 'oma.private-office-residual-budget-rerun/1', 'started_at': utcnow(),
        'checker_version': checker_version(), 'script_sha256': sha256_file(__file__),
        'loaded_oma': str(oma.__file__), 'python_executable': sys.executable,
        'application_source_sha256': {p.relative_to(source_directory).as_posix(): sha256_file(p) for p in source_directory.rglob('*.py')},
        'historical_specification_path': str(RETAINED_SPEC), 'historical_specification_sha256': sha256_file(RETAINED_SPEC),
        'specification_root': spec['specification_root'], 'historical_baseline_root': origin['base_root'],
        'original_sources': originals, 'original_head': old_head, 'original_candidate': old_candidate, 'original_run': origin,
        'cases': [{'max_new_fittings': b, 'mission_root': digest({**deepcopy(spec['mission']), 'max_new_fittings': b})} for b in spec['resource_budgets']],
        'worker_budget_seconds_per_case': args.budget_seconds, 'export_budget_seconds': args.budget_seconds,
        'original_store_access': 'READ_ONLY', 'live_project_writes': False,
        'scope': 'Unchanged hypothetical Office B2/B0 missions under residual-enabled frozen source. Native IFC checks retain complete original obstacles. No physical global optimum, hydraulic adequacy or whole-building claim.'}
    atomic_json(out / 'predeclaration.json', declaration)
    shutil.copyfile(RETAINED_SPEC, out / 'specification.json')
    shutil.copyfile(__file__, out / 'executed-campaign.py')
    result = {'status': 'RUNNING', 'checker_version': checker_version(), 'declaration_root': digest(declaration),
        'predeclaration_sha256': sha256_file(out / 'predeclaration.json'), 'cases': [], 'directory': str(out)}
    atomic_json(out / 'result.json', result)
    print(json.dumps({'directory': str(out), 'checker_version': checker_version(), 'declaration_root': digest(declaration)}), flush=True)
    started = time.monotonic()
    try:
        store, copied = copy_baseline(original, STAGE / 'bench-stores' / identifier, origin['base_root'])
        result['isolated_store'] = str(store.directory)
        result['copied_input_root'] = digest(copied)
        policy = spec['mission']['route_demands'][0]['alternatives'][0]['source_representation_policy']
        result['native_cache_preseed'] = seed_native_cache(original, store, baseline, policy)
        atomic_json(out / 'result.json', result)
        for budget in spec['resource_budgets']:
            result['cases'].append(run_case(store, baseline, spec, budget, out / ('budget-' + str(budget)), args.budget_seconds))
            atomic_json(out / 'result.json', result)
        result['status'] = 'BUDGET_TWO_CHECKED_AND_ZERO_BOUNDED_NO_INCUMBENT' if all(c['status'] != 'INCOMPLETE' for c in result['cases']) else 'INCOMPLETE'
        assert all(sha256_file(a['source']) == sha256_file(a['copy']) == a['sha256'] for a in copied['assets'])
    except Exception as error:
        result.update(status='INCOMPLETE', error=f'{type(error).__name__}: {error}')
    finally:
        result['elapsed_seconds'] = time.monotonic() - started
        result['original_project_unchanged'] = original.project(origin['project_id']) == old_head
        result['original_candidate_and_run_unchanged'] = original.candidate(HISTORICAL_CANDIDATE) == old_candidate and original.run(origin['id']) == origin
        result['original_sources_unchanged'] = all(sha256_file(s['path']) == s['sha256'] for s in originals)
        result['original_specification_unchanged'] = sha256_file(RETAINED_SPEC) == declaration['historical_specification_sha256']
        result['script_unchanged'] = sha256_file(__file__) == declaration['script_sha256']
        result['source_unchanged'] = checker_version() == declaration['checker_version']
        if not all(result[k] for k in ('original_project_unchanged', 'original_candidate_and_run_unchanged', 'original_sources_unchanged', 'original_specification_unchanged', 'script_unchanged', 'source_unchanged')):
            result['status'] = 'FAIL_PRESERVATION_OR_BUILD_CHANGED'
        atomic_json(out / 'result.json', result)
        print(json.dumps({'directory': str(out), 'status': result['status'], 'elapsed_seconds': result['elapsed_seconds']}), flush=True)
    return 0 if result['status'] == 'BUDGET_TWO_CHECKED_AND_ZERO_BOUNDED_NO_INCUMBENT' else 1


if __name__ == '__main__':
    raise SystemExit(main())


