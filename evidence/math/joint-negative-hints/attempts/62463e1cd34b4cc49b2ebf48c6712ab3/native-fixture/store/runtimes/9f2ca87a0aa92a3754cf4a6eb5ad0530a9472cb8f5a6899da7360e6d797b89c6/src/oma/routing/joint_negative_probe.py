"""Previous conflicts schedule fresh native checks; they confer no verdict.

Only the current pair can establish a numerical counterexample. No assignment
is skipped, no old scalar is reused, and inconclusive probes resume full checks.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys
import time
import uuid

import numpy as np

from oma.build_identity import checker_version, frozen_environment
from oma.export_checks import supervise_check
from oma.ifc.audit import atomic_json
from oma.models import VerificationReport
from oma.store import Store, digest
from .scenario import RoutingScenario

SCHEMA = "oma.joint-native-counterexample/1"
MAX_HINTS = 16
PROBE_SECONDS = 10.


def _route_keys(store, candidate, state):
    """Map exact current menu definitions, never route IDs from another attempt."""
    run = store.run(candidate["run_id"])
    baseline = store.get(run["base_root"])
    frozen_root = candidate.get("physical_menu_root")
    if not frozen_root:
        return {}
    menu = store.get(frozen_root)
    context = store.get(menu["context_root"])
    if (menu["run_id"] != run["id"] or context["base_root"] != run["base_root"]
            or context["request_root"] != digest(run["request"])
            or context["checker_version"] != checker_version()
            or context["sources"] != baseline["sources"]):
        return {}
    assignment = candidate.get("physical_menu_assignment")
    if not isinstance(assignment, list) or len(assignment) != len(menu["demands"]):
        return {}
    old = {r["id"]: r for r in baseline.get("routes", [])}
    contracts = state["derived_artifacts"]["routing_contracts"]
    keys = {}
    for route in state["routes"]:
        rid = route["id"]
        if rid in old:
            keys[rid] = {"kind": "prior", "route_id": rid, "base_root": run["base_root"],
                "geometry_artifact": old[rid]["geometry_artifact"]}
            continue
        contract = contracts[rid]
        matches = [(domain, label) for domain, label in zip(menu["demands"], assignment)
                   if domain["id"] == contract["request_demand_id"]]
        if len(matches) != 1:
            return {}
        domain, label = matches[0]
        choices = [c for c in domain["choices"] if c["id"] == label]
        if len(choices) != 1:
            return {}
        definition = store.get(choices[0]["definition_root"])
        material = store.get(route["geometry_artifact"])
        if (definition["scenario"] != contract["scenario"] or definition["source_id"] != contract["source_id"]
                or definition["source_sha256"] != material["source_sha256"]
                or definition["route_spec"] != {k: v for k, v in material["route_spec"].items() if k != "route_id"}):
            return {}
        keys[rid] = {"kind": "choice", "demand_id": domain["id"], "choice_id": label,
            "definition_root": choices[0]["definition_root"]}
    return keys


def learn_pair_hints(store, candidate):
    """Extract at most 16 locations; the old result only orders future work."""
    try:
        state = store.get(candidate["state_root"])
        report = VerificationReport.model_validate(store.get(candidate["report_root"]))
        if (report.candidate_root != candidate["state_root"] or report.checker_version != checker_version()
                or report.mission_hash != digest(state["mission"]) or report.rule_hash != state["mission"]["rule_hash"]):
            return []
        keys = _route_keys(store, candidate, state)
        owners = {}
        for route in state["routes"]:
            if route["id"] not in keys:
                continue
            material = store.get(route["geometry_artifact"])
            for part in material["added_parts"]:
                identity = (material["export_sha256"] + ":" + str(part["step_id"]), part["ifc_guid"])
                if identity in owners:
                    return []
                owners[identity] = {"route": keys[route["id"]], "part_index": part["part_index"], "part_kind": part["kind"]}
        hints = []
        for check in report.results:
            if check.id != "cross-route-interference":
                continue
            for pair in check.witness.get("findings", []):
                if pair.get("status") != "FAIL":
                    continue
                identities = list(zip(pair.get("participants", []), pair.get("participant_guids", [])))
                if len(identities) != 2 or any(k not in owners for k in identities):
                    continue
                hints.append({"origin_candidate_id": candidate["id"], "origin_report_root": candidate["report_root"],
                    "frozen_menu_root": candidate["physical_menu_root"], "members": [owners[k] for k in identities],
                    "authority": "SCHEDULING_HINT_ONLY"})
                if len(hints) == MAX_HINTS:
                    return hints
        return hints
    except (KeyError, ValueError, TypeError, OSError):
        return []


def _mapped_pairs(store, candidate, state, hints):
    keys = _route_keys(store, candidate, state)
    routes = {r["id"]: r for r in state["routes"]}
    pairs, seen = [], set()
    for hint in hints[:MAX_HINTS]:
        try:
            if hint["frozen_menu_root"] != candidate.get("physical_menu_root") or len(hint["members"]) != 2:
                continue
            members = []
            for member in hint["members"]:
                matches = [rid for rid, key in keys.items() if key == member["route"]]
                if len(matches) != 1 or type(member["part_index"]) is not int or member["part_index"] < 0:
                    break
                rid = matches[0]
                material = store.get(routes[rid]["geometry_artifact"])
                part = material["added_parts"][member["part_index"]]
                if part["kind"] != member["part_kind"] or part["part_index"] != member["part_index"]:
                    break
                members.append({"route_id": rid, "part_index": part["part_index"], "ifc_guid": part["ifc_guid"],
                    "step_id": part["step_id"], "materialization_root": routes[rid]["geometry_artifact"]})
            if len(members) != 2 or members[0]["route_id"] == members[1]["route_id"]:
                continue
            key = tuple(sorted((m["route_id"], m["part_index"]) for m in members))
            if key not in seen:
                seen.add(key)
                # Retain bounded scheduling provenance, never arbitrary stored
                # scalar claims or unbounded ancillary hint payloads.
                provenance = {name: hint.get(name) if isinstance(hint.get(name), str) and len(hint[name]) <= 64 else None
                              for name in ("origin_candidate_id", "origin_report_root")}
                provenance.update(frozen_menu_root=candidate["physical_menu_root"], authority="SCHEDULING_HINT_ONLY")
                pairs.append({"members": members, "hint": provenance})
        except (KeyError, TypeError, IndexError, ValueError):
            continue
    return pairs


def _file_inventory(store, state):
    files = {(str(store.resolve_path(s["immutable_path"])), s["sha256"]) for s in state["sources"]}
    for route in state["routes"]:
        material = store.get(route["geometry_artifact"])
        files.add((str(store.resolve_path(material["export_path"])), material["export_sha256"]))
    if len({path for path, _ in files}) != len(files):
        raise ValueError("One current path declares contradictory byte identities")
    return [list(pair) for pair in sorted(files)]


def inputs_unchanged(store, candidate, state, *, checkpoint=None):
    """Final current-byte guard; caller cancellation is never converted to FAIL."""
    if store.candidate(candidate["id"])["state_root"] != candidate["state_root"] or digest(state) != candidate["state_root"]:
        return False
    baseline = store.get(store.run(candidate["run_id"])["base_root"])
    # Prior accepted exports supplied the STEP/inverse preservation comparison.
    # They remain inputs even when the current composite lives at a new path.
    files = {tuple(pair) for pair in _file_inventory(store, state) + _file_inventory(store, baseline)}
    if len({path for path, _ in files}) != len(files):
        return False
    for path, expected in sorted(files):
        if checkpoint:
            checkpoint("joint_hint_input_hash")
        actual = hashlib.sha256()
        try:
            with open(path, "rb") as stream:
                while block := stream.read(8 * 1024 * 1024):
                    actual.update(block)
                    if checkpoint:
                        checkpoint("joint_hint_input_hash_chunk")
        except OSError:
            return False
        if actual.hexdigest() != expected:
            return False
    return True


def _empty(request=None):
    return {"schema": SCHEMA, "status": "NO_COUNTEREXAMPLE_FOUND", "scope": "ONE_COUNTEREXAMPLE",
        "full_source_denominator": "NOT_RUN", "full_cross_route_denominator": "NOT_RUN",
        "feasibility_verdict": "NOT_RUN", "acceptance_authority": "NONE", "objective_authority": "NONE",
        "continue_full_check": True, "old_verdict_reused": False, "new_native_verification_performed": False,
        "proof_level": "Fresh numerical native solid pair only; no interval geometry or whole-building proof",
        "request_root": digest(request) if request else None, "checker_version": checker_version(),
        "probes": [], "probe_count": 0}


def _run_request(store, request):
    """Child entry: reload current actual bodies and current rule parameters."""
    import ifcopenshell
    import ifcopenshell.util.unit
    from oma.ifc.cad import _revalidate_federation, _transform_object, check_pair, _has_native_geometry
    from oma.ifc.negative_witness import _native_member, _unique_member
    from oma.verification import candidate_control

    result = _empty(request)
    candidate = store.candidate(request["candidate_id"])
    state = store.get(candidate["state_root"])
    control = candidate_control(store, candidate)
    if (request["schema"] != SCHEMA or request["state_root"] != candidate["state_root"]
            or request["run_id"] != candidate["run_id"] or request["checker_version"] != checker_version()
            or request["files"] != _file_inventory(store, state)
            or not inputs_unchanged(store, candidate, state, checkpoint=control.checkpoint)):
        result["stop_reason"] = "CURRENT_INPUT_BINDING_FAILED"
        return result
    sources = state["sources"]
    paths = [store.resolve_path(s["immutable_path"]) for s in sources]
    if len(sources) == 1:
        transforms = {sources[0]["sha256"]: np.eye(4).tolist()}
    else:
        federation = _revalidate_federation(paths, state.get("derived_artifacts", {}).get("local_coordinate_evidence"))
        if federation is None:
            result["stop_reason"] = "CURRENT_DATUM_UNRESOLVED"
            return result
        transforms = {s["source_sha256"]: s["transform"] for s in federation["sources"]}
    if any(s.get("transform_m") != transforms.get(s["sha256"]) for s in sources):
        result["stop_reason"] = "CURRENT_SOURCE_FRAME_MISMATCH"
        return result
    routes = {r["id"]: r for r in state["routes"]}
    contracts = state["derived_artifacts"]["routing_contracts"]
    models, bodies = {}, {}
    for proposed in request["pairs"][:MAX_HINTS]:
        control.checkpoint("joint_hint_pair")
        probe = {"members": proposed["members"], "hint": proposed["hint"], "status": "NO_WITNESS"}
        result["probes"].append(probe)
        result["probe_count"] += 1
        try:
            members = proposed["members"]
            if len(members) != 2 or members[0]["route_id"] == members[1]["route_id"]:
                raise ValueError("A counterexample requires two distinct independent current routes")
            solids, scenarios = [], []
            for member in members:
                rid = member["route_id"]
                route = routes[rid]
                material = store.get(route["geometry_artifact"])
                part = material["added_parts"][member["part_index"]]
                if (member["materialization_root"] != route["geometry_artifact"] or type(member["part_index"]) is not int
                        or part["part_index"] != member["part_index"] or part["ifc_guid"] != member["ifc_guid"]
                        or part["step_id"] != member["step_id"]):
                    raise ValueError("Current part identity differs")
                scenario = RoutingScenario.model_validate(contracts[rid]["scenario"])
                if scenario.authorized_opening:
                    raise ValueError("Joint contact/subtraction authorization is unsupported")
                scenarios.append(scenario)
                key = (material["export_sha256"], part["ifc_guid"])
                if key not in bodies:
                    path = str(store.resolve_path(material["export_path"]))
                    if path not in models:
                        model = ifcopenshell.open(path)
                        units = [u for a in model.by_type("IfcUnitAssignment") for u in a.Units if getattr(u, "UnitType", None) == "LENGTHUNIT"]
                        scale = ifcopenshell.util.unit.calculate_unit_scale(model)
                        if len(units) != 1 or not math.isfinite(scale) or scale <= 0:
                            raise ValueError("Ambiguous or invalid current length unit")
                        models[path] = model
                    model = models[path]
                    entity = _unique_member(model, part["ifc_guid"])
                    if entity.id() != part["step_id"]:
                        raise ValueError("Current native GUID/STEP mismatch")
                    body, error = _native_member(model, entity, material["export_sha256"])
                    if error or body is None or not _has_native_geometry(body):
                        raise ValueError("Current complete native body unavailable: " + str(error))
                    bodies[key] = _transform_object(body, transforms[material["source_sha256"]])
                solids.append(bodies[key])
            probe["native_members"] = [{"entity_id": body.entity_id, "ifc_guid": body.guid,
                "source_sha256": body.source_sha256, "kernel_tolerance_m": body.kernel_tolerance_m,
                "support_kind": body.support_kind, "support_evidence": body.support_evidence} for body in solids]
            if solids[0].entity_id == solids[1].entity_id:
                raise ValueError("The same native part cannot witness an independent-route pair")
            clearance = max(s.clearance_m for s in scenarios)
            pair = check_pair(*solids, clearance_m=clearance, numerical_tolerance_m=1e-6)
            probe["native_pair_result"] = pair
            result["new_native_verification_performed"] = True
            failed = (all(_has_native_geometry(s) for s in solids) and pair["status"] == "FAIL"
                and pair.get("reason") in {"POSITIVE_COMMON_SOLID_VOLUME", "CLEARANCE_VIOLATION"})
        except (ValueError, KeyError, IndexError, TypeError, RuntimeError, OSError) as exc:
            probe.update(status="SKIPPED_UNRESOLVED", reason=f"{type(exc).__name__}: {exc}")
            continue
        control.checkpoint("joint_hint_pair_complete")
        if failed:
            if not inputs_unchanged(store, candidate, state, checkpoint=control.checkpoint):
                result["stop_reason"] = "CURRENT_INPUT_CHANGED_DURING_PROBE"
                return result
            control.checkpoint("joint_hint_child_publish")
            probe["status"] = "FRESH_NATIVE_COUNTEREXAMPLE"
            result.update(status="FAIL", continue_full_check=False, witness=probe,
                candidate_root=candidate["state_root"], mission_hash=digest(state["mission"]),
                rule_hash=state["mission"]["rule_hash"], stop_reason="ONE_CURRENT_COUNTEREXAMPLE_ESTABLISHED")
            return result
    result["stop_reason"] = "BOUNDED_HINTS_EXHAUSTED"
    return result


def probe_joint_failure(store, candidate, state, control, *, max_seconds=PROBE_SECONDS):
    """Bounded frozen child; timeout/abnormal exit discards even a partial FAIL."""
    result = _empty()
    hints = candidate.get("joint_pair_hints", [])
    if not isinstance(hints, list) or not hints:
        result["stop_reason"] = "NO_HINTS"
        return result
    if type(max_seconds) not in (int, float) or not math.isfinite(max_seconds) or not 0 < max_seconds <= PROBE_SECONDS:
        raise ValueError("Joint hint budget must be in (0,10] seconds")
    try:
        pairs = _mapped_pairs(store, candidate, state, hints)
    except (KeyError, TypeError, ValueError, OSError):
        pairs = []
    if not pairs:
        result["stop_reason"] = "NO_CURRENT_HINT_MAPPING"
        return result
    control.checkpoint("joint_hint_start")
    request = {"schema": SCHEMA, "candidate_id": candidate["id"], "state_root": candidate["state_root"],
        "run_id": candidate["run_id"], "checker_version": checker_version(), "files": _file_inventory(store, state), "pairs": pairs}
    result = _empty(request)
    directory = store.directory / "checks" / "joint-hints" / candidate["id"] / uuid.uuid4().hex
    directory.mkdir(parents=True)
    input_path, output_path = directory / "request.json", directory / "result.json"
    atomic_json(input_path, request)
    deadline = time.monotonic() + max_seconds
    execution = supervise_check([sys.executable, "-m", "oma.routing.joint_negative_probe", str(store.directory), str(input_path), str(output_path)],
        environment=frozen_environment(store.directory), directory=directory, deadline=deadline)
    control.checkpoint("joint_hint_completed")
    try:
        observed = json.loads(output_path.read_text(encoding="utf-8")) if output_path.is_file() else None
        bound = (isinstance(observed, dict) and observed.get("schema") == SCHEMA
            and observed.get("request_root") == digest(request) and observed.get("checker_version") == checker_version())
        if bound and observed.get("status") == "FAIL":
            bound = (observed.get("candidate_root") == candidate["state_root"]
                and observed.get("mission_hash") == digest(state["mission"])
                and observed.get("rule_hash") == state["mission"]["rule_hash"]
                and observed.get("new_native_verification_performed") is True
                and observed.get("old_verdict_reused") is False
                and isinstance(observed.get("witness", {}).get("native_pair_result"), dict))
        if execution["status"] == "COMPLETED" and bound:
            result = observed
        else:
            result["stop_reason"] = execution["status"] if execution["status"] != "COMPLETED" else "CHILD_RESULT_BINDING_FAILED"
    except (OSError, ValueError, TypeError):
        result["stop_reason"] = "INVALID_CHILD_RESULT"
    result["supervision"] = execution
    result["evidence_directory"] = str(directory)
    result["observed_child_status"] = observed.get("status") if isinstance(locals().get("observed"), dict) else None
    if result["status"] == "FAIL" and not inputs_unchanged(store, candidate, state, checkpoint=control.checkpoint):
        result.pop("witness", None)
        result.update(status="NO_COUNTEREXAMPLE_FOUND", continue_full_check=True, stop_reason="CURRENT_INPUT_CHANGED_AFTER_CHILD")
    control.checkpoint("joint_hint_result")
    atomic_json(directory / "parent-result.json", result)
    return result


if __name__ == "__main__":
    store = Store(sys.argv[1])
    request = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    atomic_json(Path(sys.argv[3]), _run_request(store, request))
