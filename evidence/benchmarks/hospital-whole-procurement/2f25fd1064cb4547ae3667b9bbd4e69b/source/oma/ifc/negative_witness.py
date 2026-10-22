"""Bounded, checker-owned search for one native forbidden-volume witness.

This phase has no PASS outcome and cannot certify feasibility. Hints only choose
which original members to reopen. A subprocess wall limit also bounds individual
native operations; unsupported solids receive no promotion/enclosure fallback.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from typing import Callable

import numpy as np

from .audit import atomic_json, sha256_file
from .cad import (CODE_SHA256 as CAD_CODE_SHA256, CadObject,
                  _complete_representation_support, _inspect_shape,
                  _revalidate_federation, _source_conversion_diagnostics,
                  _transform_object, check_pair)

CODE_SHA256 = sha256_file(__file__)
SCHEMA = "oma-native-negative-witness/1"


def _root(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _base(request):
    return {"schema": SCHEMA, "status": "NO_COUNTEREXAMPLE_FOUND",
            "scope": "ONE_COUNTEREXAMPLE", "full_source_denominator": "NOT_RUN",
            "feasibility_verdict": "NOT_RUN", "acceptance_authority": "NONE",
            "continue_full_check": True, "request_root": _root(request),
            "code_sha256": CODE_SHA256, "cad_code_sha256": CAD_CODE_SHA256,
            "source_sha256s": request["expected_source_sha256s"],
            "export_sha256": request["expected_export_sha256"],
            "max_probes": request["max_probes"], "max_seconds": request["max_seconds"],
            "probes": [], "probe_count": 0, "errors": [],
            "proof_level": "Numerical native CAD common-volume witness; no interval or whole-building proof"}


def _native_member(model, entity, source_hash):
    """A fresh complete native solid only; no expensive support reconstruction."""
    import ifcopenshell
    import ifcopenshell.geom
    from OCP.BRep import BRep_Builder
    from OCP.BRepTools import BRepTools
    from OCP.TopoDS import TopoDS_Shape

    support = _complete_representation_support(model, entity)
    bodies = [r for r in entity.Representation.Representations
              if r.RepresentationIdentifier in ("Body", "Facetation", None)] if entity.Representation else []
    if len(bodies) != 1 or not support["complete_supported_body_representation"]:
        return None, {"reason": "MISSING_AMBIGUOUS_OR_UNSUPPORTED_BODY", "support": support}
    ifcopenshell.get_log()
    ifcopenshell.ifcopenshell_wrapper.set_log_format_json()
    settings = ifcopenshell.geom.settings()
    settings.set("iterator-output", ifcopenshell.ifcopenshell_wrapper.SERIALIZED)
    settings.set("use-world-coords", True)
    iterator = ifcopenshell.geom.iterator(settings, model, 1, include=[entity])
    objects = []
    if iterator.initialize():
        while True:
            item = iterator.get()
            if item.id != entity.id():
                return None, {"reason": "NATIVE_SELECTION_IDENTITY_MISMATCH"}
            shape = TopoDS_Shape()
            BRepTools.Read_s(shape, io.BytesIO(item.geometry.brep_data.encode()), BRep_Builder())
            bounds, volume, tolerance, valid, reason = _inspect_shape(shape)
            valid = valid and bounds is not None and bool(np.isfinite(bounds).all()) and math.isfinite(tolerance)
            objects.append(CadObject(f"{source_hash}:{entity.id()}", entity.GlobalId,
                                     entity.id(), source_hash, entity.is_a(), shape, bounds,
                                     volume, tolerance, valid, reason, "native_solid", support))
            if not iterator.next():
                break
    diagnostics, unscoped = _source_conversion_diagnostics(model, {entity.id(): entity}, ifcopenshell.get_log())
    records = diagnostics.get(entity.id(), [])
    if unscoped or any(r["scope"] == "GEOMETRY_CONVERSION_FAILURE" for r in records):
        return None, {"reason": "PARTIAL_OR_FAILED_NATIVE_CONVERSION", "diagnostics": records, "unscoped": unscoped}
    if len(objects) != 1 or not objects[0].valid:
        return None, {"reason": objects[0].reason if len(objects) == 1 else "MISSING_OR_MULTIPLE_NATIVE_MEMBERS"}
    objects[0].support_evidence = {**support, "native_conversion_diagnostics": records,
        "native_shape_validity": "RECHECKED", "promotion": "NOT_RUN", "source_enclosure": "NOT_RUN"}
    return objects[0], None


def _unique_member(model, guid):
    found = [e for e in model.by_type("IfcElement") if e.GlobalId == guid
             and not e.is_a("IfcFeatureElementSubtraction")]
    if len(found) != 1:
        raise ValueError("Missing, ambiguous or non-obstacle physical member GUID: " + str(guid))
    return found[0]


def _run(request, output):
    import ifcopenshell
    import ifcopenshell.util.unit

    started = time.perf_counter()
    result = _base(request)
    result["native_versions"] = {name: importlib.metadata.version(name) for name in ("ifcopenshell", "cadquery-ocp", "numpy")}
    paths = [Path(p) for p in request["original_paths"]]
    exported = Path(request["export_path"])
    hashes = request["expected_source_sha256s"]
    def persist():
        result["seconds"] = time.perf_counter() - started
        atomic_json(output, result)
    def unchanged():
        return [sha256_file(p) for p in paths] == hashes and sha256_file(exported) == request["expected_export_sha256"]
    try:
        if not unchanged():
            raise ValueError("SOURCE_OR_EXPORT_HASH_MISMATCH")
        if len(set(hashes)) != len(hashes) or request["authoring_source_sha256"] not in hashes:
            raise ValueError("AMBIGUOUS_OR_ABSENT_AUTHORING_SOURCE")
        models = {sha: ifcopenshell.open(str(path)) for sha, path in zip(hashes, paths)}
        route_model = ifcopenshell.open(str(exported))
        for model in [*models.values(), route_model]:
            units = [u for a in model.by_type("IfcUnitAssignment") for u in a.Units if getattr(u, "UnitType", None) == "LENGTHUNIT"]
            if len(units) != 1 or not math.isfinite(ifcopenshell.util.unit.calculate_unit_scale(model)) or ifcopenshell.util.unit.calculate_unit_scale(model) <= 0:
                raise ValueError("AMBIGUOUS_OR_INVALID_LENGTH_UNIT")
        author = models[request["authoring_source_sha256"]]
        original_ids = set()
        for entity in author:
            original_ids.add(entity.id())
            if str(entity) != str(route_model.by_id(entity.id())):
                raise ValueError("ORIGINAL_STEP_RECORD_CHANGED")
        result["source_preservation"] = {"method": "ALL_ORIGINAL_STEP_RECORDS_REOPENED_AND_COMPARED",
            "authoring_source_sha256": request["authoring_source_sha256"], "records_checked": len(original_ids)}
        evidence = request.get("coordinate_evidence")
        if len(paths) == 1 and evidence is None:
            transforms = {hashes[0]: np.eye(4).tolist()}
            result["coordinate_status"] = "VERIFIED_SAME_SOURCE_RECORDS"
        else:
            derived = _revalidate_federation(paths, evidence)
            if derived is None:
                raise ValueError("SOURCE_DATUM_NOT_INDEPENDENTLY_VERIFIED")
            transforms = {s["source_sha256"]: s["transform"] for s in derived["sources"]}
            result["coordinate_status"] = "VERIFIED_REDERIVED_LOCAL_FEDERATION"
            result["coordinate_evidence_root"] = _root(derived)
        result["source_transforms"] = transforms
        route_entities = {}
        for guid in request["route_guids"]:
            entity = _unique_member(route_model, guid)
            if entity.id() in original_ids:
                raise ValueError("REQUESTED_ROUTE_IS_ORIGINAL_SOURCE_OBJECT")
            route_entities[guid] = entity
        hints = request.get("obstacle_hints")
        if hints is None:
            hints = [{"source_sha256": sha, "ifc_guid": e.GlobalId} for sha, model in models.items()
                     for e in model.by_type("IfcElement") if not e.is_a("IfcFeatureElementSubtraction")]
        route_cache, source_cache, visited = {}, {}, set()
        persist()
        for hint in hints:
            sha, guid = hint.get("source_sha256"), hint.get("ifc_guid")
            choices = [hint["route_guid"]] if hint.get("route_guid") else request["route_guids"]
            for route_guid in choices:
                key = (sha, guid, route_guid)
                if key in visited:
                    continue
                visited.add(key)
                if result["probe_count"] >= request["max_probes"]:
                    result["stop_reason"] = "PROBE_LIMIT"
                    persist()
                    return result
                if time.perf_counter() - started >= request["max_seconds"]:
                    result["stop_reason"] = "WALL_LIMIT"
                    persist()
                    return result
                probe = {"source_sha256": sha, "obstacle_guid": guid, "route_guid": route_guid, "status": "NO_WITNESS"}
                result["probe_count"] += 1
                result["probes"].append(probe)
                persist()
                try:
                    if sha not in models or route_guid not in route_entities:
                        raise ValueError("HINT_OUTSIDE_BOUND_SOURCE_OR_ROUTE_SET")
                    if (sha, guid) not in source_cache:
                        member = _unique_member(models[sha], guid)
                        source_cache[(sha, guid)] = _native_member(models[sha], member, sha)
                    obstacle, source_error = source_cache[(sha, guid)]
                    if source_error:
                        probe.update(status="SKIPPED_UNRESOLVED_NATIVE_SOURCE", details=source_error)
                        continue
                    if route_guid not in route_cache:
                        route_cache[route_guid] = _native_member(route_model, route_entities[route_guid], request["expected_export_sha256"])
                    route, route_error = route_cache[route_guid]
                    if route_error:
                        probe.update(status="SKIPPED_UNRESOLVED_NATIVE_ROUTE", details=route_error)
                        continue
                    transformed_route = _transform_object(route, transforms[request["authoring_source_sha256"]])
                    transformed_obstacle = _transform_object(obstacle, transforms[sha])
                    pair = check_pair(transformed_route, transformed_obstacle, clearance_m=0.)
                    # Separation, contact, unknowns and clearance-only failures do not prove this rule.
                    probe["native_pair_result"] = pair
                    if (transformed_route.valid and transformed_obstacle.valid and pair["status"] == "FAIL"
                            and pair.get("reason") == "POSITIVE_COMMON_SOLID_VOLUME" and pair.get("common_volume_m3", 0) > 0):
                        if not unchanged():
                            raise ValueError("SOURCE_OR_EXPORT_CHANGED_DURING_PROBE")
                        probe.update(status="FORBIDDEN_VOLUME_WITNESS", route_support=route.support_evidence,
                                     obstacle_support=obstacle.support_evidence)
                        result.update(status="FAIL", continue_full_check=False, witness=probe,
                                      stop_reason="ONE_COUNTEREXAMPLE_ESTABLISHED")
                        persist()
                        return result
                except Exception as exc:
                    probe.update(status="SKIPPED_PROBE_ERROR", error=f"{type(exc).__name__}: {exc}")
                finally:
                    persist()
        result["stop_reason"] = "PROPOSED_PROBES_EXHAUSTED"
    except Exception as exc:
        result["errors"].append(f"{type(exc).__name__}: {exc}")
        result["stop_reason"] = "INPUT_OR_DATUM_UNRESOLVED"
    persist()
    return result


def find_forbidden_volume_witness(original_paths, export_path, route_guids, *,
        expected_source_sha256s, expected_export_sha256, authoring_source_sha256,
        coordinate_evidence=None, obstacle_hints=None, max_probes=16, max_seconds=30.,
        checkpoint: Callable[[str], None] | None = None):
    """Return FAIL for one checked volume overlap, otherwise continue full checking.

    Hashes are mandatory and ordered like original_paths. Hints are dictionaries
    {source_sha256, ifc_guid, route_guid?}; their boxes/flags are never consumed.
    The caller owns route membership, system/service and final all-source checks.
    This helper only considers forbidden route-versus-original occupied solids.
    """
    if isinstance(max_probes, bool) or not isinstance(max_probes, int) or not 1 <= max_probes <= 256:
        raise ValueError("max_probes must be an integer in [1,256]")
    if not math.isfinite(max_seconds) or not 0 < max_seconds <= 120:
        raise ValueError("max_seconds must be in (0,120]")
    paths = [str(Path(p).resolve()) for p in original_paths]
    hashes = list(expected_source_sha256s)
    routes = list(route_guids)
    if not paths or len(paths) != len(hashes) or not routes or len(routes) != len(set(routes)):
        raise ValueError("Nonempty, unambiguous source hashes and route GUIDs required")
    request = {"original_paths": paths, "export_path": str(Path(export_path).resolve()),
        "route_guids": routes, "expected_source_sha256s": hashes,
        "expected_export_sha256": expected_export_sha256, "authoring_source_sha256": authoring_source_sha256,
        "coordinate_evidence": coordinate_evidence, "obstacle_hints": obstacle_hints,
        "max_probes": max_probes, "max_seconds": float(max_seconds)}
    result = _base(request)
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="oma-negative-witness-") as directory:
        root = Path(directory)
        input_path, output_path = root / "request.json", root / "result.json"
        atomic_json(input_path, request)
        process = subprocess.Popen([sys.executable, "-m", "oma.ifc.negative_witness", str(input_path), str(output_path)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        timed_out = threading.Event()
        def expire():
            if process.poll() is None:
                timed_out.set()
                try:
                    process.kill()
                except OSError:
                    pass
        timer = threading.Timer(max(0., max_seconds - (time.perf_counter() - started)), expire)
        timer.daemon = True
        timer.start()
        try:
            while process.poll() is None:
                if checkpoint:
                    checkpoint("native_negative_witness_wait")
                if time.perf_counter() - started >= max_seconds:
                    expire()
                    break
                time.sleep(min(.05, max_seconds))
        finally:
            timer.cancel()
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
        if output_path.exists():
            child = json.loads(output_path.read_text(encoding="utf-8"))
            if (child.get("schema") == SCHEMA and child.get("request_root") == result["request_root"]
                    and child.get("code_sha256") == CODE_SHA256 and child.get("cad_code_sha256") == CAD_CODE_SHA256):
                result = child
            else:
                result["stop_reason"] = "CHILD_IMPLEMENTATION_OR_REQUEST_MISMATCH"
        if timed_out.is_set() or process.returncode != 0:
            result.pop("witness", None)
            result.update(status="NO_COUNTEREXAMPLE_FOUND", continue_full_check=True,
                          stop_reason="HARD_WALL_LIMIT" if timed_out.is_set() else "CHILD_CHECKER_FAILED")
        result["wall_seconds"] = time.perf_counter() - started
        result["child_exit_code"] = process.returncode
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    _run(json.loads(arguments.request.read_text(encoding="utf-8")), arguments.output)
