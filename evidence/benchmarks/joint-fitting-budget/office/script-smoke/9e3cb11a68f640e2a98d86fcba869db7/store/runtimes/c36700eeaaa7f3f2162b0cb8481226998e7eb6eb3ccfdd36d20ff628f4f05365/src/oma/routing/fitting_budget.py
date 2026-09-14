"""Current numerical IFC evidence for one exact integer resource constraint.

The resource is newly authored independent round 90-degree elbows. It neither
counts prior protected routes nor authorizes a shared tree/tee/corridor model.
"""
from collections import Counter
import hashlib
import math
from pathlib import Path
import tempfile

from oma.build_identity import checker_version
from oma.ifc.audit import sha256_file
from oma.models import CheckResult, Verdict
from oma.store import digest
from .joint_scenario import parse_joint_request

SCHEMA = "oma.joint-new-fitting-budget/1"
RESOURCE = {"schema": SCHEMA, "resource": "NEW_INDEPENDENT_ROUND_90_DEGREE_ELBOWS",
    "unit": "one currently materialized unique elbow", "prior_routes": "EXCLUDED_PROTECTED_BASELINE",
    "scope": "Independent round routes only; no shared network, tee, or corridor resource"}
ANGLE_TOLERANCE_RAD = 1e-7
_REQUIRED = ("fixed-request-assumptions", "protected-source-preservation", "materialized-input-integrity",
    "materialization-source-frame", "route-materialization-correspondence", "fixed-service-obligations",
    "declared-terminal-state", "exported-physical-semantics", "physical-interference-and-clearance",
    "physical-self-interference", "physical-port-body-attachment", "permitted-zone-containment",
    "independent-objective-recomputation")


def _budget(value):
    if value is not None and (type(value) is not int or not 0 <= value <= 1024):
        raise ValueError("max_new_fittings must be a strict integer in [0,1024]")
    return value


def joint_rule_hash(missions, max_new_fittings=None):
    """Omitted resources preserve the exact historical ordered rule digest."""
    hashes = [m["rule_hash"] if isinstance(m, dict) else m.rule_hash for m in missions]
    budget = _budget(max_new_fittings)
    return digest(hashes) if budget is None else digest({"route_rule_hashes": hashes,
        "resource_definition": RESOURCE, "max_new_fittings": budget})


class _EvidenceError(Exception):
    def __init__(self, status, reason):
        self.status, self.reason = status, reason


def _require(condition, reason, status="FAIL"):
    if not condition:
        raise _EvidenceError(status, reason)


def _checks(records, rid):
    result = {}
    _require(isinstance(records, (list, tuple)), "Current per-route evidence is missing or malformed", "NOT_RUN")
    for record in records:
        _require(isinstance(record, (CheckResult, dict)), "Current check record is malformed", "NOT_RUN")
        raw = record.model_dump(mode="json") if isinstance(record, CheckResult) else dict(record)
        identity = raw["id"]
        _require(isinstance(identity, str) and isinstance(raw.get("witness"), dict), "Current check identity/witness is malformed", "NOT_RUN")
        if identity.startswith(rid + ":"):
            identity = identity[len(rid) + 1:]
        _require(identity not in result, "Duplicate per-route check identity")
        result[identity] = raw
    _require(set(_REQUIRED) <= set(result), "Required current count evidence is missing", "NOT_RUN")
    for identity in _REQUIRED:
        status = result[identity]["status"]
        _require(status == "PASS", "Current count prerequisite is not passing: " + identity,
            "UNKNOWN" if status == "UNKNOWN" else "NOT_RUN")
    return result


def _native_evidence(store, checks, material, source_hashes):
    from oma.ifc.cad import CODE_SHA256
    guids = [p["ifc_guid"] for p in material["added_parts"]]
    correspondence = checks["route-materialization-correspondence"]["witness"]
    _require(correspondence.get("route_id") == material["route_id"]
        and correspondence.get("materialization_root") == digest(material)
        and type(correspondence.get("part_count")) is int
        and correspondence.get("part_count") == len(guids), "Current materialization correspondence differs")
    semantics = checks["exported-physical-semantics"]["witness"]["recomputed"]
    count = semantics["fitting_count"]
    _require(type(count) is int and count >= 0, "IFC fitting count must be a nonnegative exact integer")
    _require(not semantics["errors"] and not semantics["route_directrix"]["errors"]
        and type(semantics["route_directrix"]["parts_checked"]) is int
        and semantics["route_directrix"]["parts_checked"] == len(guids), "Complete directrix correspondence is missing")
    actual_guids = [p["guid"] for p in semantics["parts"]]
    _require(len(actual_guids) == len(set(actual_guids)) == len(guids) and set(actual_guids) == set(guids),
        "IFC semantics names a different or incomplete physical-part denominator")
    cad_root = checks["physical-interference-and-clearance"]["witness"]["artifact"]
    cad = store.get(cad_root)
    _require(cad.get("implementation", {}).get("cad_code_sha256") == CODE_SHA256
        and cad.get("export_sha256") == material["export_sha256"], "Native correspondence is stale or belongs to other bytes")
    _require(cad["coordination_status"] == cad["self_interference_status"] == "PASS"
        and type(cad["route_count"]) is int
        and cad["route_count"] == len(guids) and cad["route_guids"] == sorted(guids)
        and len(cad["sources"]) == len(source_hashes) and {s["sha256"] for s in cad["sources"]} == source_hashes,
        "Native source/route evidence omits or changes the current denominator")
    _require(checks["physical-self-interference"]["witness"]["artifact"] == cad_root,
        "Self and source geometry checks disagree about their native artifact")
    zone = checks["permitted-zone-containment"]["witness"]
    native_guids = [part["ifc_guid"] for part in zone["parts"]]
    _require(type(zone["expected_parts"]) is int and type(zone["loaded_parts"]) is int
        and zone["expected_parts"] == zone["loaded_parts"] == len(guids) and not zone["geometry_errors"]
        and len(native_guids) == len(set(native_guids)) == len(guids) and set(native_guids) == set(guids)
        and all(p["status"] == "PASS" for p in zone["parts"]), "Current complete native bodies are unresolved", "UNKNOWN")
    return count, semantics, cad_root


def _read_bound_model(path, expected, directory, index, checkpoint):
    import ifcopenshell
    copied = Path(directory) / f"{index:03d}.ifc"
    actual = hashlib.sha256()
    with open(path, "rb") as source, copied.open("xb") as target:
        while block := source.read(8 * 1024 * 1024):
            actual.update(block)
            target.write(block)
            if checkpoint:
                checkpoint("joint_fitting_input_copy")
    _require(actual.hexdigest() == expected, "Current IFC copied bytes changed before fitting interpretation")
    try:
        model = ifcopenshell.open(str(copied))
    except (RuntimeError, ValueError) as exc:
        raise _EvidenceError("UNKNOWN", "Actual IFC interpretation unavailable: " + str(exc)) from exc
    return model


def _element_index(model, checkpoint):
    """One bounded complete GUID inventory per replacement, including duplicates."""
    result = {}
    for index, element in enumerate(model.by_type("IfcElement")):
        if checkpoint and index % 128 == 0:
            checkpoint("joint_fitting_element_inventory")
        result.setdefault(element.GlobalId, []).append(element)
    if checkpoint:
        checkpoint("joint_fitting_element_inventory_complete")
    return result


def check_joint_fitting_budget(store, state, baseline, per_route_results, *, candidate_run, checkpoint=None):
    """Count from current IFC, under full current directrix/native evidence.

    Source checks come from this checker invocation, keyed by route identity.
    A passing result certifies this integer bound only; it confers no native
    acceptance, nominal-to-native cost bound, or global optimality authority.
    """
    witness = {"schema": SCHEMA, "resource_definition": RESOURCE, "checker_version": checker_version(),
        "candidate_root": digest(state), "baseline_root": digest(baseline), "declared_budget": None,
        "per_new_route": {}, "count": None, "excess": None, "source_check_roots": {},
        "count_complete": False, "native_verification_reperformed": False,
        "candidate_acceptance_authority": False, "global_optimality_claim": False,
        "angle_classification_tolerance_rad": ANGLE_TOLERANCE_RAD}
    def result(status, reason):
        return CheckResult(id="joint-new-fitting-budget", status=Verdict(status), reason=reason,
            scope="Current newly authored independent round 90-degree elbow budget; protected prior routes excluded", witness=witness)
    try:
        run = store.run(candidate_run["id"])
        _require(run["base_root"] == digest(baseline) and run["request"] == candidate_run["request"]
            and run["project_id"] == state["project_id"] == baseline["project_id"], "Fitting count changed its immutable run or baseline")
        requested = parse_joint_request(run["request"]["mission"])
        budget = requested.max_new_fittings
        declared = state.get("derived_artifacts", {}).get("joint_fitting_budget")
        if budget is None:
            _require(declared is None, "Candidate introduced an unrequested fitting budget")
            return result("NOT_APPLICABLE", "No new fitting resource was requested")
        witness["declared_budget"] = budget
        _require(declared == {"schema": SCHEMA, "max_new_fittings": budget}
            and type(declared.get("max_new_fittings")) is int, "Candidate changed or omitted the requested fitting budget")
        routes = {r["id"]: r for r in state.get("routes", [])}
        prior = {r["id"]: r for r in baseline.get("routes", [])}
        contracts = state["derived_artifacts"]["routing_contracts"]
        _require(not state.get("physical_networks") and len(routes) == len(state.get("routes", []))
            and len(prior) == len(baseline.get("routes", [])) and set(prior) <= set(routes)
            and set(contracts) == set(routes), "Complete independent route and protected baseline inventory required")
        new = set(routes) - set(prior)
        _require(Counter(contracts[r]["request_demand_id"] for r in new) == Counter(d.id for d in requested.route_demands),
            "New route inventory does not cover exactly the requested demands")
        _require(set(per_route_results) == set(routes), "Current per-route evidence denominator is incomplete", "NOT_RUN")
        _require(state["mission"]["rule_hash"] == joint_rule_hash([contracts[r]["mission"] for r in sorted(contracts)], budget),
            "Aggregate rule hash does not bind the fitting definition and requested budget")
        for rid in prior:
            _require({k: v for k, v in routes[rid].items() if k != "geometry_artifact"}
                == {k: v for k, v in prior[rid].items() if k != "geometry_artifact"}, "Prior route identity changed to avoid new fitting use")
        witness["excluded_prior_route_ids"] = sorted(prior)
        materials, owned = {}, set()
        for rid, route in routes.items():
            material = store.get(route["geometry_artifact"])
            _require(material["route_id"] == rid and digest(material) == route["geometry_artifact"], "Materialization route identity differs")
            materials[rid] = material
            for index, part in enumerate(material["added_parts"]):
                key = (material["source_sha256"], part["ifc_guid"])
                _require(key not in owned and part["route_id"] == rid and type(part["part_index"]) is int
                    and part["part_index"] == index, "Physical fitting/part ownership is duplicated or permuted")
                owned.add(key)
        source_hashes = {s["sha256"] for s in state["sources"]}
        _require(source_hashes and len(source_hashes) == len(state["sources"]) and state["sources"] == baseline["sources"],
            "Complete immutable source denominator changed")
        models, files, indexes = {}, set(), {}
        with tempfile.TemporaryDirectory(prefix="oma-joint-fitting-count-") as directory:
            for rid in sorted(new):
                if checkpoint:
                    checkpoint("joint_fitting_route")
                checks = _checks(per_route_results[rid], rid)
                material = materials[rid]
                try:
                    checked_count, semantics, cad_root = _native_evidence(store, checks, material, source_hashes)
                except (TypeError, AttributeError, ValueError) as exc:
                    raise _EvidenceError("NOT_RUN", "Malformed current fitting/native evidence: " + str(exc)) from exc
                path = str(store.resolve_path(material["export_path"]))
                key = (path, material["export_sha256"])
                files.add(key)
                if key not in models:
                    models[key] = _read_bound_model(path, key[1], directory, len(models), checkpoint)
                    indexes[key] = _element_index(models[key], checkpoint)
                model = models[key]
                from oma.ifc.network_semantics import read_component_geometry
                rows, used = [], 0
                for part in material["added_parts"]:
                    if checkpoint:
                        checkpoint("joint_fitting_component")
                    matches = indexes[key].get(part["ifc_guid"], [])
                    _require(len(matches) == 1 and matches[0].id() == part["step_id"], "Actual IFC GUID/STEP count identity differs")
                    try:
                        actual = read_component_geometry(model, matches[0])
                    except (ValueError, RuntimeError, TypeError, KeyError) as exc:
                        raise _EvidenceError("UNKNOWN", "Actual round fitting interpretation unresolved: " + str(exc)) from exc
                    _require(actual["kind"] == part["kind"] and actual["kind"] in {"segment", "elbow"}, "Unsupported independent resource component", "UNKNOWN")
                    if actual["kind"] == "elbow":
                        _require(math.isfinite(actual["angle_rad"]) and abs(actual["angle_rad"] - math.pi / 2) <= ANGLE_TOLERANCE_RAD,
                            "New non-90-degree elbow lies outside this resource family", "UNKNOWN")
                        used += 1
                    fact = next(p for p in semantics["parts"] if p["guid"] == part["ifc_guid"])
                    _require(math.isfinite(fact["length_m"]) and abs(fact["length_m"] - actual["length_m"]) <= 1e-7
                        and abs(fact["radius_m"] - actual["radius_m"]) <= 1e-10, "Actual IFC and current checked directrix facts differ")
                    rows.append({"ifc_guid": part["ifc_guid"], "step_id": part["step_id"], "kind": actual["kind"],
                        "angle_rad": actual.get("angle_rad"), "units": int(actual["kind"] == "elbow")})
                _require(used == checked_count, "Actual unique elbow count differs from the checked integer count")
                witness["per_new_route"][rid] = used
                witness.setdefault("actual_parts", {})[rid] = rows
                witness["source_check_roots"][rid] = {name: store.put(checks[name]) for name in sorted(checks)}
                witness.setdefault("native_artifact_roots", {})[rid] = cad_root
        for source in state["sources"]:
            files.add((str(store.resolve_path(source["immutable_path"])), source["sha256"]))
        if checkpoint:
            checkpoint("joint_fitting_final_input")
            checkpoint("joint_fitting_complete")
        # These checkpoints may pause. No yielding callback follows the final
        # integrity sweep: resumption must validate every input, including
        # files counted before the pause. The owning child supervisor supplies
        # the hard deadline while this final bounded input inventory is hashed.
        for path, expected in files:
            _require(sha256_file(path) == expected, "Current fitting/native source bytes changed during counting")
        final_run = store.run(candidate_run["id"])
        _require(digest(state) == witness["candidate_root"] and digest(baseline) == witness["baseline_root"]
            and final_run["request"] == run["request"] and final_run["base_root"] == run["base_root"]
            and final_run["project_id"] == run["project_id"], "Current fitting request/state changed during counting")
        total = sum(witness["per_new_route"].values())
        witness.update(count=total, excess=max(0, total - budget), count_complete=True)
        return result("PASS" if total <= budget else "FAIL", "Actual new fitting use satisfies the declared budget" if total <= budget
            else "Actual new fitting use exceeds the declared budget")
    except _EvidenceError as exc:
        return result(exc.status, exc.reason)
    except (KeyError, IndexError, StopIteration) as exc:
        return result("NOT_RUN", "Required current fitting count evidence is missing: " + str(exc))
    except OSError as exc:
        return result("UNKNOWN", "Current fitting/source input is unavailable: " + str(exc))
