"""Independent persisted shared-network checker. No search/producer imports."""
from __future__ import annotations

from fractions import Fraction
import math

import numpy as np

from oma.ifc.audit import sha256_file
from oma.ifc.cad import cad_check_routes, load_cad, _transform_object
from oma.ifc.network_semantics import check_network_semantics
from oma.models import CheckResult, PhysicalNetwork, VerificationReport, Verdict
from oma.optimization.physical import Interval
from oma.store import digest, utcnow
from oma.verification import CHECKER_VERSION, candidate_control
from .network_flow import evaluate_network_flow
from .network_scenario import SharedNetworkScenario, network_requirements, network_baseline_context


def verify_network_candidate(store, candidate_id):
    candidate = store.candidate(candidate_id)
    state = store.get(candidate["state_root"])
    run = store.run(candidate["run_id"])
    baseline = store.get(run["base_root"])
    control = candidate_control(store, candidate)
    results, objective = [], {}
    def add(identity, status, reason, witness=None, participants=()):
        results.append(CheckResult(id=identity, status=Verdict(status), reason=reason,
            scope="One complete shared physical network and every imported source obstacle", witness=witness or {}, participants=tuple(participants)))
    def finish():
        status = next((v for v in (Verdict.FAIL, Verdict.BLOCKED, Verdict.UNKNOWN, Verdict.NOT_RUN)
                       if any(r.status == v for r in results)), Verdict.PASS)
        boundary_scope = ("fixed total-pressure boundaries and minimum deliveries"
            if any(run.get("request", {}).get("mission", {}).get(k) is not None for k in ("pressure_driven", "passive_tree", "coupled_tree")) else "fixed demands")
        report = VerificationReport(candidate_root=candidate["state_root"], mission_hash=digest(state.get("mission")),
            rule_hash=(state.get("mission") or {}).get("rule_hash", "missing-network-mission"), checker_version=CHECKER_VERSION,
            status=status, scope=f"SHARED_PHYSICAL_NETWORK: complete local component tree, {boundary_scope} and all source obstacles; whole-building adequacy not certified",
            results=tuple(results), objective=objective, created_at=utcnow(), common_mode_risks=(
                "Shared IFC parser and numerical OCP kernel; analytic component reconstruction independently cross-checks native volumes",
                "Length and coordinate arithmetic uses the explicit engineering tolerance; this is not a formally interval-certified CAD kernel",
                "Supplied pressure or flow boundary controls, Darcy friction and fitting loss applicability are engineering assumptions; certified operating bounds apply only to their declared model",
                "Finite topology alternatives do not establish global continuous or unrestricted topology optimality"))
        store.record_verification(candidate_id, report)
        return report
    try:
        request = SharedNetworkScenario.model_validate(run["request"]["mission"])
        contract = state.get("derived_artifacts", {})["network_contract"]
        mission, ports, section = network_requirements(baseline, request)
        selected = next(n for n in request.network_alternatives if n.network_id == contract["selected_alternative"])
        sources = baseline.get("sources", [])
        source, kept_ports, revision = network_baseline_context(baseline, request)
        if source is None or source.get("transform_m") is None or contract["source_id"] != source["id"]:
            raise ValueError("Selected source does not belong to the fixed requested federation")
        network_records = state.get("physical_networks", [])
        if len(network_records) != 1:
            raise ValueError("Exactly one complete shared physical network is required")
        record = PhysicalNetwork.model_validate(network_records[0])
        materialized = store.get(record.geometry_artifact)
    except (ValueError, KeyError, StopIteration, TypeError) as exc:
        add("network-contract", "FAIL", f"Missing or invalid persisted network contract: {exc}")
        return finish()
    expected_contract = {"scenario": request.model_dump(mode="json", by_alias=True),
        "selected_alternative": selected.network_id, "source_id": source["id"]}
    if revision:
        expected_contract["revision"] = {**revision, "base_root": run["base_root"]}
    fixed = contract == expected_contract and state.get("mission") == mission
    add("fixed-network-requirements", "PASS" if fixed else "FAIL", "Full scenario, demands, constraints, component alternatives and objective policy bind the original immutable run request")
    expected_record = PhysicalNetwork(id=selected.network_id, demand_ids=tuple(s.demand_id for s in request.sinks),
        component_ids=tuple(c.id for c in selected.components), port_ids=tuple(p["id"] for p in ports), service=request.system_type,
        section=section, geometry_artifact=record.geometry_artifact).model_dump(mode="json")
    expected_changes = {f"{record.id}:{c.id}" for c in selected.components}
    if revision:
        expected_changes.update(revision["previous_component_ids"])
    coverage = (network_records == [expected_record] and set(candidate.get("changed_ids", [])) == expected_changes
                and len(candidate.get("changed_ids", [])) == len(expected_changes))
    add("unique-network-demand-coverage", "PASS" if coverage else "FAIL", "Every fixed demand shares one uniquely inventoried component tree; no duplicated trunk or missing branch")
    allowed_changes = {"mission", "ports", "physical_networks", "derived_artifacts"}
    preserved = all(state.get(k) == v for k, v in baseline.items() if k not in allowed_changes)
    preserved &= set(state) <= set(baseline) | allowed_changes
    preserved &= state.get("ports") == [*kept_ports, *ports]
    derived = state.get("derived_artifacts", {})
    preserved &= all(derived.get(k) == v for k, v in baseline.get("derived_artifacts", {}).items()
                     if k not in {"network_contract", "export_correspondence"})
    preserved &= set(derived) <= set(baseline.get("derived_artifacts", {})) | {"network_contract", "export_correspondence"}
    add("protected-network-baseline", "PASS" if preserved else "FAIL", "All original source, entity, connectivity, policy and previous obligation content is preserved")
    expected_spec = selected.model_dump(mode="json", by_alias=True)
    matrix = source.get("transform_m")
    if matrix is not None:
        expected_spec["source_to_federation_matrix"] = matrix
    spec_bound = (materialized.get("network_spec") == expected_spec and materialized.get("source_sha256") == source["sha256"]
        and store.resolve_path(materialized.get("source_path", "")) == store.resolve_path(source["immutable_path"])
        and materialized.get("port_axis_convention") == "IFC_FLOW_AXIS_V1")
    add("network-source-and-datum-binding", "PASS" if spec_bound else "FAIL", "Actual materialization uses the selected full graph and the immutable source's declared federation transform")
    original_paths = [store.resolve_path(s["immutable_path"]) for s in sources]
    path = store.resolve_path(materialized["export_path"])
    integrity = (path.is_file() and sha256_file(path) == materialized["export_sha256"]
        and all(p.is_file() and sha256_file(p) == s["sha256"] for p, s in zip(original_paths, sources)))
    add("network-artifact-integrity", "PASS" if integrity else "FAIL", "Every original source and complete physical replacement was freshly hash checked")
    correspondence = derived.get("export_correspondence")
    if correspondence:
        files = correspondence.get("files", [])
        matched = len(files) == len(sources) and {f["source_id"] for f in files} == {s["id"] for s in sources}
        source_map = {s["id"]: s for s in sources}
        for f in files:
            file = store.resolve_path(f["path"])
            matched &= file.is_file() and sha256_file(file) == f["sha256"]
            original = source_map.get(f["source_id"], {})
            matched &= f.get("source_sha256") == original.get("sha256")
            changed = f["source_id"] == source["id"]
            matched &= bool(f["changed"]) == changed
            matched &= f["sha256"] == (materialized["export_sha256"] if changed else original.get("sha256"))
        add("network-export-federation-correspondence", "PASS" if matched else "FAIL", "Every exported discipline and the complete network replacement correspond to the pinned originals")
    if not all((fixed, coverage, preserved, spec_bound, integrity)):
        add("network-native-check", "BLOCKED", "A failed immutable requirement or byte binding prevents authoritative native checking")
        return finish()
    control.checkpoint("network_native_semantics")
    semantics = check_network_semantics(path, store.resolve_path(source["immutable_path"]), materialized)
    semantic_root = store.put(semantics)
    add("network-native-semantics", semantics["status"], "Fresh IFC parts, complete Body items, actual cap ports, flow roles, directed tree, system membership and analytic/native volumes checked",
        {"artifact": semantic_root, "errors": semantics["errors"], "physical_components": semantics.get("physical_components"),
         "physical_ports": semantics.get("physical_ports"), "connections": semantics.get("connections")})
    if semantics["status"] != "PASS":
        return finish()
    objective.update(length_m=semantics["unique_length_m"], fitting_count=float(semantics["fitting_count"]))
    add("network-objective", "PASS", "Length and fitting count sum each unique physical component once; demand-path lengths are separate",
        {"unique_length_m": objective["length_m"], "fitting_count": objective["fitting_count"], "demand_path_lengths_m": semantics["demand_path_lengths_m"], "artifact": semantic_root})
    guids = {p["ifc_guid"] for p in semantics["parts"]}
    from .negative_probe import probe_candidate_failure
    probe = probe_candidate_failure(store, state, materialized, guids, control)
    probe_root = store.put(probe)
    if probe["status"] == "FAIL":
        pair = probe["witness"]["native_pair_result"]
        add("network-native-counterexample", "FAIL", "One freshly reopened original obstacle has positive native common volume with a new component",
            {"artifact": probe_root, "point": pair.get("witness", {}).get("p1"), "other_point": pair.get("witness", {}).get("p2")}, pair["participants"])
        add("network-all-source-clearance", "NOT_RUN", "Full source denominator not checked after a conclusive forbidden-volume counterexample", {"artifact": probe_root})
        for identity in ("network-all-component-pairs", "network-permitted-zone", "network-demand-conditioned-service"):
            add(identity, "NOT_RUN", "Stopped after a conclusive physical counterexample; no remaining feasibility claim")
        if request.pressure_driven is not None or request.passive_tree is not None or request.coupled_tree is not None:
            add("network-pressure-operating-point", "NOT_RUN", "Operating relation was not evaluated after the physical counterexample")
        return finish()
    cad = cad_check_routes(original_paths, path, guids, clearance_m=request.clearance_m, numerical_tolerance_m=1e-6,
        coordinate_evidence=derived.get("local_coordinate_evidence"), cache_directory=store.directory / "cad-cache",
        source_representation_policy=request.source_representation_policy, checkpoint=control.checkpoint)
    cad_root = store.put(cad)
    add("network-all-source-clearance", cad["coordination_status"], f"All {cad['pairs_accounted']} component/obstacle pairs accounted; {cad['failed_pairs']} failed and {cad['unknown_pairs']} ambiguous", {"artifact": cad_root, "negative_probe_artifact": probe_root})
    add("network-all-component-pairs", cad["self_interference_status"], "Every distinct component pair checked; exact local cap contact requires independently reconstructed interface evidence", {"artifact": cad_root})
    for index, pair in enumerate(cad["pair_results"] + cad.get("self_pair_results", [])):
        if pair["status"] != "PASS":
            witness = pair.get("witness", {})
            add(f"network-physical-witness:{index}", pair["status"], pair["reason"],
                {"artifact": cad_root, "point": witness.get("p1"), "other_point": witness.get("p2"),
                 "margin_m": pair.get("clearance_margin_m"), "required_clearance_m": pair["required_clearance_m"]}, pair["participants"])
    actual, errors = load_cad(path, guids=guids, checkpoint=control.checkpoint)
    if matrix is not None:
        actual = [_transform_object(s, matrix) for s in actual]
    enclosed = not errors and len(actual) == len(guids)
    ambiguous = False
    for solid in actual:
        if not solid.valid or solid.bounds is None:
            enclosed = False
            continue
        margin = min(*(solid.bounds[i] - request.allowed_zone.min[i] for i in range(3)),
                     *(request.allowed_zone.max[i] - solid.bounds[i+3] for i in range(3)))
        enclosed &= margin >= 0
        ambiguous |= margin <= 1e-6 + solid.kernel_tolerance_m
    add("network-permitted-zone", "FAIL" if not enclosed else "UNKNOWN" if ambiguous else "PASS", "Full native envelopes of every trunk, branch and fitting checked against the fixed permitted zone")
    if request.target_modality == "ENGINEERING_SERVICE":
        budget = Fraction(str(max(1e-6, state.get("numerical_policy", {}).get("absolute_tolerance_m", 1e-6))))
        lengths = {p["component_id"]: Interval(max(Fraction(0), Fraction(str(p["length_m"])) - budget), Fraction(str(p["length_m"])) + budget) for p in semantics["parts"]}
        measured_ports = {(p["component_id"], p["slot"]): p for p in semantics["ports"]}
        transform = np.asarray(matrix if matrix is not None else np.eye(4))
        def slot_position(key):
            p = transform[:3, :3] @ measured_ports[key]["position_m"] + transform[:3, 3]
            return [Interval(Fraction(str(float(v))) - budget, Fraction(str(float(v))) + budget) for v in p]
        def position(endpoint):
            return slot_position(endpoint.key())
        positions = {"source": position(selected.source), "sinks": {s.id: position(s.endpoint) for s in selected.sinks}}
        radii = {p["component_id"]: Interval(Fraction(str(p["radius_m"])) - budget, Fraction(str(p["radius_m"])) + budget) for p in semantics["parts"]}
        if request.coupled_tree is not None:
            from .coupled_tree_pressure import evaluate_coupled_tree, METRIC_SCHEMA
            def bounds(value):
                return {"lower": str(value.lo), "upper": str(value.hi)}
            metrics = {"schema": METRIC_SCHEMA, "network_root": digest(selected.model_dump(mode="json", by_alias=True)),
                "native_evidence_root": semantic_root,
                "components": {c.id: {"length_m": bounds(lengths[c.id]), "outer_radius_m": bounds(radii[c.id]),
                    "ports": {p: {"position_m": [bounds(v) for v in slot_position((c.id, p))]} for p in c.ports}}
                    for c in selected.components}}
            metrics_root = store.put(metrics)
            control.checkpoint("network_coupled_envelope_start")
            calculation = evaluate_coupled_tree(request.coupled_tree, selected, metrics,
                context={"candidate_root": candidate["state_root"], "baseline_root": run["base_root"],
                    "source_sha256": source["sha256"], "export_sha256": materialized["export_sha256"],
                    "native_semantics_root": semantic_root, "native_metrics_root": metrics_root,
                    "native_cad_root": cad_root, "checker_version": CHECKER_VERSION,
                    "mission_hash": digest(state["mission"]), "rule_hash": state["mission"]["rule_hash"],
                    "native_metric_absolute_tolerance_m": str(budget)}, checkpoint=control.search_checkpoint)
            # Hot arithmetic may reuse only a recent ordinary Run observation.
            # Step/pause/cancel remain explicit, and this forced boundary cannot
            # reuse that observation before persisting a calculated result.
            control.checkpoint("network_coupled_envelope_complete")
            calculation_root = store.put(calculation)
            checked = calculation.get("independent_check", {})
            operating = ("PASS" if calculation.get("proof_complete") is True and checked.get("status") == "PASS"
                and checked.get("local_check", {}).get("status") == "PASS" and checked.get("global_check", {}).get("status") == "PASS"
                else "BLOCKED" if calculation.get("status") == "BLOCKED" else "UNKNOWN")
            add("network-pressure-operating-point", operating,
                "Independent local pressure enclosure and global nonnegative uniqueness, complete native path terms and outlet-specific inlet-flow losses checked",
                {"artifact": calculation_root, "native_metrics_artifact": metrics_root, "model_root": checked.get("model_root")})
            reason = "Every physical port's forward flow and speed, all exact minimum deliveries and complete continuity identities checked under the explicit coupled tree model"
        elif request.passive_tree is not None:
            from .passive_tree_pressure import evaluate_passive_tree, METRIC_SCHEMA
            def bounds(value):
                return {"lower": str(value.lo), "upper": str(value.hi)}
            metrics = {"schema": METRIC_SCHEMA, "network_root": digest(selected.model_dump(mode="json", by_alias=True)),
                "native_evidence_root": semantic_root,
                "components": {c.id: {"length_m": bounds(lengths[c.id]), "outer_radius_m": bounds(radii[c.id]),
                    "ports": {p: {"position_m": [bounds(v) for v in slot_position((c.id, p))]} for p in c.ports}}
                    for c in selected.components}}
            metrics_root = store.put(metrics)
            control.checkpoint("network_passive_envelope_start")
            calculation = evaluate_passive_tree(request.passive_tree, selected, metrics,
                context={"candidate_root": candidate["state_root"], "baseline_root": run["base_root"],
                    "source_sha256": source["sha256"], "export_sha256": materialized["export_sha256"],
                    "native_semantics_root": semantic_root, "native_metrics_root": metrics_root,
                    "native_cad_root": cad_root, "checker_version": CHECKER_VERSION,
                    "mission_hash": digest(state["mission"]), "rule_hash": state["mission"]["rule_hash"],
                    "native_metric_absolute_tolerance_m": str(budget)}, checkpoint=control.search_checkpoint)
            # Hot arithmetic may reuse only a recent ordinary Run observation.
            # Step/pause/cancel remain explicit, and this forced boundary cannot
            # reuse that observation before persisting a calculated result.
            control.checkpoint("network_passive_envelope_complete")
            calculation_root = store.put(calculation)
            checked = calculation.get("independent_check", {})
            operating = ("PASS" if calculation.get("proof_complete") is True and checked.get("status") == "PASS"
                else "BLOCKED" if calculation.get("status") == "BLOCKED" else "UNKNOWN")
            add("network-pressure-operating-point", operating,
                "Independent pressure envelope, complete native cap quotient and every component's dimensional resistance checked under the explicit common-outlet tee law",
                {"artifact": calculation_root, "native_metrics_artifact": metrics_root, "model_root": checked.get("model_root")})
            reason = "Every physical port's forward flow and speed, all exact minimum deliveries and complete continuity identities checked under the explicit passive tree model"
        elif request.pressure_driven is not None:
            from .network_pressure import evaluate_pressure_network
            calculation = evaluate_pressure_network(request, selected, lengths, positions,
                component_outer_radii=radii,
                context={"candidate_root": candidate["state_root"], "baseline_root": run["base_root"],
                    "source_sha256": source["sha256"], "export_sha256": materialized["export_sha256"],
                    "native_semantics_root": semantic_root, "checker_version": CHECKER_VERSION,
                    "mission_hash": digest(state["mission"]), "native_metric_absolute_tolerance_m": str(budget)}, checkpoint=control.checkpoint)
            calculation_root = store.put(calculation)
            operating = "PASS" if calculation["operating_point_status"] == "PASS" else "BLOCKED" if calculation["verdict"] == "BLOCKED" else "UNKNOWN"
            add("network-pressure-operating-point", operating,
                "Independent rational certificate for the complete two-outlet forward operating relation under supplied total-pressure boundaries and native metric enclosures",
                {"artifact": calculation_root, "model_root": calculation.get("independent_check", {}).get("model_root") if calculation.get("independent_check") else None})
            reason = "Every minimum outlet delivery and every component port velocity checked using independently certified pressure-driven flow enclosures"
        else:
            calculation = evaluate_network_flow(request, selected, lengths, positions, component_outer_radii=radii)
            reason = "Aggregate trunk flow, every component port velocity and each demand's static pressure requirement checked with current native section enclosures under explicit fixed-flow control and loss assumptions"
        add("network-demand-conditioned-service", calculation["verdict"], reason, {"calculation": calculation, "metric_tolerance_m": str(budget)})
    else:
        add("network-demand-conditioned-service", "NOT_APPLICABLE", "Requested scope is local physical coordination; no hydraulic operating point or service capacity claim")
    return finish()
