"""Root-bound assurance cases for actual independently recorded project checks.

This is an evidence derivation, not a fresh geometry/simulation invocation.
Conditional support is deliberately separate from engineering PASS and from
authenticity of the stored bytes. No whole-building claim is inferred.
"""
from __future__ import annotations

from dataclasses import asdict
import json

from .assurance import Claim, Foundation, Inference, Theory, solve_assurance, verify_assurance, evidence_cuts
from .models import VerificationReport
from .store import digest


def report_context(state, state_root, executable):
    mission = state.get("mission") or {}
    return {"state_root": state_root, "mission_hash": digest(state.get("mission")),
            "rule_hash": mission.get("rule_hash", "baseline-unapproved-contact-policy"),
            "scenario_hash": mission.get("scenario_hash", "NO_MISSION"),
            "catalog_hash": mission.get("catalog_hash", "NO_CATALOG"),
            "numerical_policy_hash": digest(state.get("numerical_policy")),
            "source_manifest_hash": digest(state.get("sources", [])), "checker_version": executable}


def build_report_assurance(store, candidate, report_root, *, executable, assessment_time):
    report = VerificationReport.model_validate(store.get(report_root)).model_dump(mode="json")
    state = store.get(candidate["state_root"])
    context = report_context(state, candidate["state_root"], executable)
    # Recorded values, not requested values, determine each atom's applicability.
    recorded = {**context, "state_root": report["candidate_root"], "mission_hash": report["mission_hash"],
                "rule_hash": report["rule_hash"], "checker_version": report["checker_version"]}
    claims, foundations, premises, dispositions, assumptions = [], [], [], [], []
    scope = report["scope"]
    from .validation_advisories import candidate_advisories
    advisories = candidate_advisories(store, candidate, state)

    def foundation(identifier, statement, kind, supported, *, claim_scope=scope):
        claim = "claim:" + identifier
        claims.append(Claim(claim, statement, claim_scope))
        premises.append(claim)
        if supported:
            foundations.append(Foundation(identifier, (claim,), kind, recorded, statement,
                time_basis="OBSERVATION_TIME", observed_at=report["created_at"]))
        return claim

    foundation("report-verdict", "The recorded report has a complete PASS disposition", "EVIDENCE", report["status"] == "PASS")
    foundation("known-validation-advisories", "No known unresolved validation advisory invalidates this report's engineering claim", "TCB", not advisories)
    for index, result in enumerate(report["results"]):
        claim = foundation(f"result:{index}", f"{result['id']}: {result['status']} — {result['reason']}",
            "EVIDENCE", result["status"] in {"PASS", "NOT_APPLICABLE"}, claim_scope=result["scope"])
        dispositions.append({"claim": claim, **result, "report_root": report_root,
            "truth_basis": "Independent checker's recorded numerical/model-conditional disposition"})

    trusted = ["The recorded independent checker and its declared inference policy correctly implement the stated checking contract",
               "The enumerated checker obligations cover this report's expressly limited scope",
               *report["common_mode_risks"]]
    declared = [*(state.get("assumptions") or []), *((state.get("mission") or {}).get("assumptions") or [])]
    # Route scenario annotations can add an explicitly declared source model.
    derived = state.get("derived_artifacts", {})
    scenarios = [derived["routing_scenario"]] if derived.get("routing_scenario") else []
    scenarios.extend(contract.get("scenario", {}) for contract in derived.get("routing_contracts", {}).values())
    if derived.get("network_contract"):
        scenarios.append(derived["network_contract"]["scenario"])
    for scenario in scenarios:
        declared.extend(scenario.get("assumptions", []))
        if scenario.get("source_representation_policy"):
            declared.append({"source_representation_policy": scenario["source_representation_policy"]})
        if scenario.get("scenario_terminals"):
            declared.append("Terminal locations and demand are explicitly supplied scenario inputs, not surveyed/as-built facts")
        if scenario.get("passive_tree") is not None:
            declared.append({"passive_tree_network_boundary_inputs": scenario["passive_tree"],
                "source_position_m": scenario["start_m"], "sinks": scenario["sinks"],
                "flow_interpretation": "The exact boundary minima are authoritative; Demand float values are descriptive projections. Every physical port requires positive forward flow and bounded absolute velocity from the independently checked passive envelope",
                "boundary_interpretation": "Explicit total pressure excludes elevation; every actual cap elevation enters total head separately. Each tee has the same positive inlet-referenced total loss at both outlets; actual catalog applicability remains supplied",
                "section_interpretation": "Ideal bore from every native outer-radius enclosure minus declared insulation; actual inner bore and wall thickness are not measured",
                "connection_interpretation": "Native checked matching connected caps have no additional declared junction loss; the bounded tree quotient covers every physical port and connection"})
        if scenario.get("pressure_driven") is not None:
            declared.append({"pressure_driven_network_boundary_inputs": scenario["pressure_driven"],
                "source_position_m": scenario["start_m"], "sinks": scenario["sinks"],
                "flow_interpretation": "Minimum deliveries are requirements; operating flow bounds are independently certified for the declared fixed-loss two-outlet forward model only",
                "boundary_interpretation": "Supplied total pressures include kinetic pressure and exclude elevation; measured port elevation enclosures enter the energy relation separately",
                "section_interpretation": "Ideal hydraulic bore inferred from each native outer-envelope radius enclosure minus declared insulation; native IFC solids do not measure inner bore or wall thickness; section correspondence and supplied loss applicability remain prerequisites"})
        if scenario.get("physics"):
            declared.append({"physical_model_inputs": scenario["physics"], "source": scenario.get("provenance", "declared scenario")})
            if scenario.get("mission_type") == "shared_network":
                declared.append({"fixed_network_boundary_inputs": {"source_position_m": scenario["start_m"], "sinks": scenario["sinks"]},
                    "flow_interpretation": "Simultaneous prescribed demands under the explicit external-control assumption; actual operating flows are not established"})
    for kind, values in (("TCB", trusted), ("ASSUMPTION", declared)):
        seen = set()
        for value in values:
            key = digest(value)
            if key in seen:
                continue
            seen.add(key)
            statement = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
            identifier = f"{kind.lower()}:{key[:20]}"
            claim = foundation(identifier, statement, kind, True)
            assumptions.append({"id": identifier, "claim": claim, "kind": kind, "statement": statement,
                                "status": "DECLARED_CONDITION", "technical_truth": "NOT_ESTABLISHED_BY_AUTHENTICITY"})
    target = "recorded-scope-support"
    claims.append(Claim(target, "All recorded obligations for this exact declared report scope are supported, conditional on the listed trust and model assumptions", scope))
    theory = Theory(tuple(claims), tuple(foundations),
        (Inference("report-conjunction", target, tuple(premises),
                   "Conjunction of every recorded disposition and all explicit trust/model conditions; no omitted claim is introduced"),), (target,))
    authenticated = {f.id for f in foundations}
    certificate = solve_assurance(theory, [context], authenticated, assessment_time)
    verification = verify_assurance(theory, [context], authenticated, assessment_time, certificate)
    cuts = evidence_cuts(theory, certificate) if verification["status"] == "PASS" else {"status": "UNKNOWN", "cuts": []}
    return {"schema": "oma-assurance/1", "candidate_id": candidate["id"], "candidate_root": candidate["state_root"],
            "report_root": report_root, "recorded_engineering_status": report["status"],
            "assessment_context": context, "recorded_context": recorded, "scope": scope,
            "support_status": certificate["status"] if verification["status"] == "PASS" else "UNKNOWN",
            "independent_assurance_check": verification, "theory": asdict(theory), "certificate": certificate,
            "assumption_ledger": assumptions, "dispositions": dispositions, "external_evidence_cuts": cuts,
            "validation_advisories": advisories,
            "fresh_physical_recheck": "NOT_RUN", "current_external_file_bytes": "NOT_REHASHED_BY_THIS_EVIDENCE_QUERY",
            "whole_building_certification": "NOT_ESTABLISHED", "global_optimality": "NOT_ESTABLISHED"}


def candidate_assurance(store, candidate_id):
    from .build_identity import checker_version
    from .store import utcnow
    candidate = store.candidate(candidate_id)
    if not candidate.get("report_root"):
        return {"candidate_id": candidate_id, "candidate_root": candidate["state_root"], "support_status": "NOT_RUN",
                "reason": "No recorded independent verification report"}
    return build_report_assurance(store, candidate, candidate["report_root"], executable=checker_version(), assessment_time=utcnow())
