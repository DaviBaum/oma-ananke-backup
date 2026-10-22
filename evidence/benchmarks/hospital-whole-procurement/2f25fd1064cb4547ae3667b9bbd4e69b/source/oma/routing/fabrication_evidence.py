"""Persist and independently replay the nominal fabrication model of a proposal.

The source-world construction and all actual IFC checks remain separate. A
valid certificate can prove a bounded-model FAIL or UNKNOWN disposition.
"""
import json

from oma.build_identity import checker_version
from oma.optimization.fabrication import compile_orthogonal_fabrication, verify_orthogonal_fabrication
from oma.store import digest
from .scenario import RoutingScenario


SCHEMA = "oma.persisted-fabrication-proposal/1"
REFERENCE_SCHEMA = "oma.fabrication-proposal-reference/1"


def _publication_events(store, project_id, run_id):
    # Query the full origin-run event set, rather than a UI pagination window.
    # This anchors attribution in the same local persistence trust boundary as
    # the original run. It is not a signature against arbitrary database edits.
    with store.connect() as db:
        rows = db.execute("SELECT payload FROM events WHERE project_id=? "
            "AND json_extract(payload,'$.run_id')=? AND json_extract(payload,'$.stage')='fabrication_model'",
            (project_id, run_id)).fetchall()
    return [json.loads(row[0]) for row in rows]


def persist_fabrication_proposal(store, run, scenario, proposal, *, checkpoint, request_demand_id=None):
    checkpoint("fabrication_model")
    context = {"run_id":run["id"], "project_id":run["project_id"], "base_root":run["base_root"],
        "request_root":digest(run["request"]), "scenario_root":digest(scenario.model_dump(mode="json")),
        "proposal_points_root":digest(proposal["points_m"]), "request_demand_id":request_demand_id,
        "coordinate_frame":"FEDERATION_SCENARIO_POINTS", "producer_version":checker_version()}
    certificate = compile_orthogonal_fabrication(scenario, proposal["points_m"], context_root=digest(context))
    checked = verify_orthogonal_fabrication(scenario, proposal["points_m"], certificate, context_root=digest(context))
    if checked["status"] != "PASS":
        raise ValueError("Independent nominal fabrication certificate verification failed")
    checkpoint("fabrication_model_publish")
    artifact = store.put({"schema":SCHEMA, "context":context, "certificate":certificate,
        "producer_check":checked, "candidate_acceptance_authority":False,
        "automatic_numerical_writer_pruning_authority":False})
    reference = {"schema":REFERENCE_SCHEMA, "artifact_root":artifact,
        "fabrication_status":checked["fabrication_status"], "certificate_root":checked["certificate_root"],
        "candidate_acceptance_authority":False}
    store.append_event(run["project_id"], run_id=run["id"], state_root=run["base_root"],
        stage="fabrication_model", status=checked["fabrication_status"], artifacts=[artifact],
        message="Exact nominal fabrication model evaluated; actual IFC construction and physical checks remain separate",
        payload={"request_demand_id":request_demand_id, "disposition":checked["disposition"],
            "components_checked":checked["components_checked"], "transitions_checked":checked["transitions_checked"],
            "candidate_acceptance_authority":False, "automatic_numerical_writer_pruning_authority":False})
    return {**proposal, "fabrication_evidence":reference}


def replay_fabrication_proposal(store, reference, scenario, points_m, *, project_id):
    """Recheck proof inputs and immutable origin; never reuse producer's PASS.

    The origin may be an earlier run retained during a joint revision. This
    exact model depends on equal scenario/points, not subsequent obstacles.
    """
    try:
        if set(reference) != {"schema","artifact_root","fabrication_status","certificate_root","candidate_acceptance_authority"}:
            raise ValueError("Complete fabrication reference required")
        if reference["schema"] != REFERENCE_SCHEMA or reference["candidate_acceptance_authority"] is not False:
            raise ValueError("Fabrication reference scope changed")
        artifact = store.get(reference["artifact_root"])
        if (set(artifact) != {"schema","context","certificate","producer_check","candidate_acceptance_authority","automatic_numerical_writer_pruning_authority"}
                or artifact["schema"] != SCHEMA or artifact["candidate_acceptance_authority"] is not False
                or artifact["automatic_numerical_writer_pruning_authority"] is not False):
            raise ValueError("Fabrication artifact scope changed")
        context = artifact["context"]
        if (set(context) != {"run_id","project_id","base_root","request_root","scenario_root","proposal_points_root","request_demand_id","coordinate_frame","producer_version"}
                or not isinstance(context["producer_version"],str) or not context["producer_version"]):
            raise ValueError("Complete fabrication origin context required")
        origin = store.run(context["run_id"])
        if (context["project_id"] != project_id or origin["project_id"] != project_id
                or context["base_root"] != origin["base_root"] or context["request_root"] != digest(origin["request"])
                or context["coordinate_frame"] != "FEDERATION_SCENARIO_POINTS"
                or context["scenario_root"] != digest(scenario.model_dump(mode="json"))
                or context["proposal_points_root"] != digest(points_m)):
            raise ValueError("Fabrication proposal inputs or immutable origin changed")
        raw = origin["request"]["mission"]
        if "route_demands" in raw:
            demand = next(d for d in raw["route_demands"] if d["id"] == context["request_demand_id"])
            alternatives = demand["alternatives"]
        else:
            if context["request_demand_id"] not in (None,"additional-route"):
                raise ValueError("Unknown single-route demand provenance")
            alternatives = [raw]
        if not any(RoutingScenario.model_validate(s).model_dump(mode="json") == scenario.model_dump(mode="json") for s in alternatives):
            raise ValueError("Fabrication model is not an originally authorized scenario")
        checked = verify_orthogonal_fabrication(scenario, points_m, artifact["certificate"], context_root=digest(context))
        if (checked["status"] != "PASS" or reference["fabrication_status"] != checked["fabrication_status"]
                or reference["certificate_root"] != checked["certificate_root"]
                or digest(artifact["producer_check"]) != digest(checked)):
            raise ValueError("Nominal fabrication certificate or declared disposition failed current replay")
        if not any(event["state_root"] == origin["base_root"]
                and event["artifacts"] == [reference["artifact_root"]]
                and event["status"] == checked["fabrication_status"]
                for event in _publication_events(store, project_id, origin["id"])):
            raise ValueError("Fabrication artifact was not published by its attributed origin run")
        return {**checked, "artifact_root":reference["artifact_root"], "origin_run_id":origin["id"],
                "origin_publication_checked":True, "producer_check_reused":False, "candidate_acceptance_authority":False}
    except (ValueError,KeyError,TypeError,StopIteration) as error:
        return {"status":"FAIL", "reason":str(error), "candidate_acceptance_authority":False}


def check_route_fabrication_evidence(store, state, baseline, scenario, route, candidate_run):
    """Bind fresh replay to this route's origin or its exact preserved evidence.

    New witnesses come from the candidate's immutable original run. Existing
    witnesses must be preserved byte-for-byte from the baseline, even when the
    composite IFC geometry artifact is rebuilt. A historical absent witness has
    no mathematical authority and remains explicitly NOT_APPLICABLE.
    """
    try:
        rid = route["id"]
        reference = state.get("derived_artifacts", {}).get("fabrication_evidence_by_route", {}).get(rid)
        previous = baseline.get("derived_artifacts", {}).get("fabrication_evidence_by_route", {}).get(rid)
        old_route = next((r for r in baseline.get("routes", []) if r["id"] == rid), None)
        if old_route is not None:
            if reference != previous:
                raise ValueError("Previously recorded route fabrication evidence was removed or replaced")
        elif reference is None and _publication_events(store, candidate_run["project_id"], candidate_run["id"]):
            raise ValueError("New route omitted fabrication evidence published during its origin run")
        if reference is None:
            return {"status":"NOT_APPLICABLE", "reason":"Historical route has no nominal fabrication witness",
                "candidate_acceptance_authority":False}
        artifact = store.get(reference["artifact_root"])
        if old_route is None:
            contracts = state.get("derived_artifacts", {}).get("routing_contracts", {})
            expected_demand = contracts.get(rid, {}).get("request_demand_id")
            if (artifact["context"]["run_id"] != candidate_run["id"]
                    or artifact["context"]["request_demand_id"] != expected_demand):
                raise ValueError("New route's fabrication evidence belongs to another run or demand")
        return replay_fabrication_proposal(store, reference, scenario, route["points_m"], project_id=state["project_id"])
    except (ValueError,KeyError,TypeError) as error:
        return {"status":"FAIL", "reason":str(error), "candidate_acceptance_authority":False}
