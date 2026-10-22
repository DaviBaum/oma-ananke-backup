"""One bounded proposal-enumeration round in a checked residual graph language.

Already generated complete words are excluded only at termination. Their native
feasibility and compatibility with other routes are never assumed by this phase.
"""
from copy import deepcopy
import time

from oma.optimization.fabrication import compile_orthogonal_fabrication, verify_orthogonal_fabrication
from oma.optimization.fabrication_alternatives import compile_fabrication_alternatives, verify_fabrication_alternatives
from oma.optimization.rectilinear_opening import _q
from oma.store import digest


class ResidualDeadline(Exception):
    pass


def residual_proposals(problem, objective, maximum, scenario, coverage, original_certificate,
        original_proposals, *, check, caller_check, deadline, seconds, max_states, max_work, maximum_outputs):
    """Consume an already independently checked original exact-count frontier."""
    started = time.monotonic()
    stop = started + (min(seconds, max(0., deadline-started)*.5) if deadline is not None else seconds)
    result = {"schema":"oma.fabrication-residual-proposals/1", "status":"UNKNOWN", "proposals":[],
        "policy":{"maximum_rounds":1, "maximum_outputs":maximum_outputs, "maximum_seconds":seconds,
            "order":"INCREASING_EXACT_FITTING_COUNT", "exclusion_meaning":"ALREADY_GENERATED_COMPLETE_GRAPH_WORDS",
            "native_rejections_used_as_exclusions":False, "physical_unique_path_completeness":False,
            "physical_infeasibility_claim":False, "sequential_rank_claim":False,
            "candidate_acceptance_authority":False},
        "original_certificate_root":digest(original_certificate), "attempts":[]}
    def pulse(stage):
        check(stage)
        if time.monotonic() >= stop:
            raise ResidualDeadline()
    try:
        pulse("fabrication_residual_seed")
        entries = {row["fittings"]:row for row in original_certificate["frontier"]}
        words, provenance = [], []
        for proposal in original_proposals:
            pulse("fabrication_residual_seed_word")
            row = entries[proposal["exact_fittings"]]
            if (row["status"] != "OPTIMAL_PATH" or proposal["frontier_entry_root"] != digest(row)
                    or proposal["frontier_certificate_root"] != digest(original_certificate)):
                raise ValueError("Generated proposal differs from its checked original frontier entry")
            words.append(deepcopy(row["path_states"]))
            provenance.append({"word_root":digest(row["path_states"]), "original_entry_root":digest(row),
                "binary64_fabrication_certificate_root":proposal["binary64_fabrication_certificate_root"]})
        result["generation_ledger"] = {"original_certificate_root":digest(original_certificate),
            "generated_words":provenance, "excluded_words":deepcopy(words)}
        result["generation_ledger_root"] = digest(result["generation_ledger"])
        if not words:
            result.update(status="NOT_RUN", reason="NO_GENERATED_ORIGINAL_WORDS")
            return result
        proof = compile_fabrication_alternatives(problem,objective,maximum,words,
            max_states=max_states,max_work=max_work,checkpoint=pulse)
        result["certificate"] = proof
        pulse("fabrication_residual_independent_replay")
        checked = verify_fabrication_alternatives(problem,objective,maximum,words,proof,
            max_states=max_states,max_work=max_work,checkpoint=pulse)
        result["independent_check"] = checked
        if checked["status"] != "PASS":
            result.update(status=checked["status"],reason=checked.get("reason","RESIDUAL_PROOF_NOT_CHECKED"))
            return result
        proof_root = digest(proof)
        represented = {tuple(map(tuple,p["points_m"])) for p in original_proposals}
        attempts = 0
        for row in proof["frontier"]:
            pulse("fabrication_residual_conversion")
            count = row["fittings"]
            item = {"exact_fittings":count,"entry_root":digest(row)}
            result["attempts"].append(item)
            if row["status"] != "RESIDUAL_OPTIMAL_PATH":
                item["status"] = "NO_PATH_IN_DECLARED_RESIDUAL_LANGUAGE_AT_EXACT_COUNT"
                continue
            if attempts >= maximum_outputs:
                item["status"] = "OUTPUT_LIMIT_NOT_CONVERTED"
                continue
            attempts += 1
            try:
                points = [[float(_q(x)) for x in point] for point in row["points_m"]]
                context = digest({"model_root":digest(problem), "residual_certificate_root":proof_root,
                    "entry_root":digest(row), "generation_ledger_root":result["generation_ledger_root"],
                    "exact_fittings":count,"points_m":points})
                body = compile_orthogonal_fabrication(scenario,points,context_root=context,
                    outer_obstacles=coverage["outer_obstacles"],outer_model_root=digest(coverage))
                replay = verify_orthogonal_fabrication(scenario,points,body,context_root=context,
                    outer_obstacles=coverage["outer_obstacles"],outer_model_root=digest(coverage))
                item.update(binary64_context_root=context,binary64_fabrication_certificate=body,
                    binary64_fabrication_check=replay)
                pulse("fabrication_residual_conversion_checked")
                if (replay["status"] != "PASS" or replay.get("fabrication_status") != "PASS"
                        or replay.get("transitions_checked") != count or len(points) != count+2):
                    item["status"] = "BINARY64_FABRICATION_UNRESOLVED"
                    continue
                key = tuple(map(tuple,points))
                if key in represented:
                    item["status"] = "DUPLICATE_MATERIALIZATION_PROPOSAL"
                    continue
                represented.add(key)
                item["status"] = "BINARY64_FABRICATION_CHECKED"
                result["proposals"].append({"points_m":points,
                    "rationale":"Additional checked fabrication path after complete generated-word exclusions; actual IFC and joint compatibility remain unchecked",
                    "geometry_scope":"EXACT_NOMINAL_ORTHOGONAL_BODY_IN_DECLARED_SOURCE_OUTER_MODEL",
                    "path_certificate_kind":"FABRICATION_RESIDUAL_FRONTIER", "path_certificate_root":proof_root,
                    "binary64_fabrication_certificate_root":digest(body), "nominal_graph_optimality":False,
                    "binary64_objective_optimality":False, "candidate_acceptance_authority":False,
                    "physical_infeasibility_claim":False, "exact_fittings":count,
                    "residual_certificate_root":proof_root, "residual_entry_root":digest(row),
                    "residual_count_domain_root":proof["count_domain_root"],
                    "residual_exclusion_root":proof["exclusion_root"], "residual_model_root":proof["residual_model_root"],
                    "generation_ledger_root":result["generation_ledger_root"],
                    "nominal_exact_count_residual_optimality":True, "nominal_exact_count_optimality":False,
                    "binary64_exact_fittings":count, "shared_native_budget_feasibility":"NOT_CHECKED"})
            except (ValueError,OverflowError) as error:
                if caller_check.failure is error:
                    raise
                item.update(status="BINARY64_FABRICATION_UNRESOLVED",reason=str(error))
        pulse("fabrication_residual_complete")
        result["status"] = "CHECKED_RESIDUAL_PROPOSALS"
    except ResidualDeadline as error:
        if caller_check.failure is error:
            raise
        result.update(status="UNKNOWN",reason="FABRICATION_RESIDUAL_DEADLINE",proposals=[])
    finally:
        result["timing"] = {"total_seconds":time.monotonic()-started}
    return result
