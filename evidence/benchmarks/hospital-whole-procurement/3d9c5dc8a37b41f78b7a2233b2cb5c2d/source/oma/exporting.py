"""Immutable local export bundles, identity maps and explicit release status."""
from __future__ import annotations

import copy
import shutil
import time
import uuid
from pathlib import Path

from .ifc.audit import atomic_json, sha256_file
from .store import IntegrityError, Store, utcnow
from .export_checks import DEFAULT_EXPORT_BUDGET_SECONDS, ExportChecks, export_budget


def export_project(store: Store, project_id: str, candidate_id: str | None = None, draft: bool = True,
                   *, budget_seconds: float = DEFAULT_EXPORT_BUDGET_SECONDS) -> dict:
    started = time.monotonic()
    budget_seconds = export_budget(budget_seconds)
    project = store.project(project_id)
    candidate = store.candidate(candidate_id) if candidate_id else None
    if candidate and candidate["project_id"] != project_id:
        raise IntegrityError("Candidate belongs to a different project")
    root = candidate["state_root"] if candidate else project["state_root"]
    state = store.get(root)
    if not state.get("sources"):
        raise ValueError("Import must finish before export")
    if not draft:
        from .build_identity import checker_version
        if not candidate or candidate["status"] != "CHECKED" or not candidate.get("report_root"):
            raise IntegrityError("Checked export requires complete independent evidence for an explicit candidate")
        from .validation_advisories import candidate_advisories
        if candidate_advisories(store, candidate, state):
            raise IntegrityError("IFC-PORT-001: prior authored port semantics require regeneration and a fresh independent check")
        report = store.get(candidate["report_root"])
        if report["status"] != "PASS" or report["candidate_root"] != root or report["checker_version"] != checker_version():
            raise IntegrityError("Candidate does not have a passing root-matched report")
    if state.get("physical_networks"):
        from .routing.network_export import export_network_project
        return export_network_project(store, project, state, candidate, draft, report if not draft else None, budget_seconds=budget_seconds, started=started)
    if state.get("derived_artifacts", {}).get("routing_contracts"):
        from .routing.joint_export import export_joint_project
        return export_joint_project(store, project, state, candidate, draft, report if not draft else None, budget_seconds=budget_seconds, started=started)
    route_specs = state.get("derived_artifacts", {}).get("route_exports", [])
    if len(route_specs) > 1:
        raise ValueError("Joint multi-route export correspondence is required; cannot drop or duplicate routes")
    export_id = uuid.uuid4().hex
    directory = store.directory / "exports" / export_id
    directory.mkdir(parents=True)
    manifest = {"export_id": export_id, "project_id": project_id, "candidate_id": candidate_id, "state_root": root,
                "created_at": utcnow(), "status": "DRAFT", "files": [], "correspondences": [],
                "round_trip": "NOT_RUN", "whole_building_release": "NOT_CERTIFIED", "limitations": [], "source_redistribution": "Local user export; original project license terms retained"}
    checks = ExportChecks(store, directory, manifest, budget_seconds=budget_seconds, started=started)
    atomic_json(directory / "state.json", state)
    exported_materialization = None
    for index, source in enumerate(state["sources"]):
        original = store.resolve_path(source["immutable_path"])
        if sha256_file(original) != source["sha256"]:
            raise IntegrityError("Immutable source hash mismatch; export stopped")
        destination = directory / f"{index + 1:02d}_{source['name']}"
        spec = next((r for r in route_specs if r["source_id"] == source["id"]), None)
        if spec:
            prior = store.get(state["derived_artifacts"]["route_materialization"]["root"])
            if sha256_file(store.resolve_path(prior["export_path"])) != prior["export_sha256"] or prior["source_sha256"] != source["sha256"]:
                raise IntegrityError("Physical IFC no longer matches checked materialization")
            shutil.copyfile(store.resolve_path(prior["export_path"]), destination)
            exported_materialization = {**prior, "source_path": str(original), "export_path": str(destination), "export_sha256": sha256_file(destination), "reimport": {"status": "NOT_RUN"}}
            atomic_json(destination.with_suffix(".manifest.json"), exported_materialization)
            manifest["correspondences"].append({"source_id": source["id"], "replacement_path": str(destination), "route_id": spec["route_spec"]["route_id"], "part_guids": [p["ifc_guid"] for p in prior["added_parts"]]})
            if prior.get("authorized_opening"):
                opening = prior["authorized_opening"]
                manifest["correspondences"][-1]["authorized_opening"] = {"host_guid": opening["request"]["host_guid"],
                    "host_step_id": opening["request"]["host_step_id"], "opening_guid": opening["opening_guid"],
                    "request_root": opening["request_root"], "scope": opening["scope"]}
        else:
            shutil.copyfile(original, destination)
        manifest["files"].append({"path": str(destination), "source_id": source["id"], "sha256": sha256_file(destination),
                                  "source_sha256": source["sha256"], "schema": source["schema"], "changed": bool(spec)})
        checks.persist()
    if exported_materialization:
        exported_materialization, manifest["round_trip"] = checks.reimport("oma.ifc.recheck", Path(exported_materialization["export_path"]).with_suffix(".manifest.json"))
        if not draft and manifest["round_trip"] == "PASS":
            exported_state = copy.deepcopy(state)
            materialized_root = store.put(exported_materialization)
            exported_state["derived_artifacts"]["route_materialization"].update(root=materialized_root, path=exported_materialization["export_path"])
            for route in exported_state["routes"]:
                if route["id"] in candidate["changed_ids"]:
                    route["geometry_artifact"] = materialized_root
            exported_state["derived_artifacts"]["export_correspondence"] = {"input_candidate_root": root, "files": manifest["files"]}
            exported_candidate = store.add_candidate(candidate["run_id"], exported_state, {"kind": "physical_route", "export_recheck": True, "changed_ids": candidate["changed_ids"], "routes": exported_state["routes"], "objective": {}, "rationale": "Independent verification of exported physical IFC copy"})
            checks.verify(exported_candidate, report)
    else:
        manifest["round_trip"] = "BYTE_IDENTICAL_ORIGINALS"
        manifest["limitations"].append("No accepted route edits in this state; exported files are unchanged source copies")
    manifest["limitations"].append("Local route checks do not certify pre-existing defects or whole-building adequacy")
    atomic_json(directory / "manifest.json", manifest)
    snapshot = store.get(root)
    atomic_json(directory / "state.json", snapshot)
    events, cursor = [], 0
    while batch := store.events(project_id, cursor, 1000):
        events.extend(batch)
        cursor = batch[-1]["seq"]
    atomic_json(directory / "events.json", events)
    manifest_root = store.put(manifest)
    store.append_event(project_id, state_root=root, candidate_id=candidate_id, stage="export", status=manifest["status"], message="IFC export bundle written with replacement map and checking evidence", artifacts=[manifest_root], payload={"directory": str(directory), "round_trip": manifest["round_trip"]})
    if not draft and manifest["status"] != "CHECKED_LOCAL_SCOPE":
        raise IntegrityError(f"Export recheck failed; draft evidence preserved at {directory}")
    return {"status": manifest["status"], "export_id": export_id, "directory": str(directory), "manifest": str(directory / "manifest.json"), "artifact_root": manifest_root, "files": manifest["files"], "scope": manifest.get("checked_scope"), "round_trip": manifest["round_trip"]}
