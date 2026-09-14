"""Export the complete shared physical network and independently recheck copies."""
import copy
import shutil
import uuid

from oma.export_checks import DEFAULT_EXPORT_BUDGET_SECONDS, ExportChecks
from oma.ifc.audit import atomic_json, sha256_file
from oma.store import IntegrityError, utcnow


def export_network_project(store, project, state, candidate, draft, original_report=None, *, budget_seconds=DEFAULT_EXPORT_BUDGET_SECONDS, started=None):
    records = state.get("physical_networks", [])
    if len(records) != 1 or state.get("routes"):
        raise IntegrityError("Export requires one complete supported network and preserved source set")
    record = records[0]
    materialized = store.get(record["geometry_artifact"])
    source_id = state["derived_artifacts"]["network_contract"]["source_id"]
    root = candidate["state_root"] if candidate else project["state_root"]
    export_id = uuid.uuid4().hex
    directory = store.directory / "exports" / export_id
    directory.mkdir(parents=True)
    manifest = {"export_id": export_id, "project_id": project["id"], "candidate_id": candidate["id"] if candidate else None,
        "state_root": root, "created_at": utcnow(), "status": "DRAFT", "round_trip": "NOT_RUN", "files": [],
        "whole_building_release": "NOT_CERTIFIED", "limitations": [], "correspondences": [],
        "source_redistribution": "Local user export; original project license terms retained"}
    checks = ExportChecks(store, directory, manifest, budget_seconds=budget_seconds, started=started)
    atomic_json(directory / "state.json", state)
    exported = None
    for index, source in enumerate(state["sources"]):
        original = store.resolve_path(source["immutable_path"])
        if not original.is_file() or sha256_file(original) != source["sha256"]:
            raise IntegrityError("Original source bytes changed; network export stopped")
        destination = directory / f"{index+1:02d}_{source['name']}"
        changed = source["id"] == source_id
        if changed:
            physical = store.resolve_path(materialized["export_path"])
            if sha256_file(physical) != materialized["export_sha256"] or materialized["source_sha256"] != source["sha256"]:
                raise IntegrityError("Complete physical network no longer matches its immutable artifact")
            shutil.copyfile(physical, destination)
            exported = {**materialized, "source_path": str(original), "export_path": str(destination),
                        "export_sha256": sha256_file(destination), "reimport": {"status": "NOT_RUN"}}
            sidecar = destination.with_suffix(".manifest.json")
            atomic_json(sidecar, exported)
            exported, manifest["round_trip"] = checks.reimport("oma.ifc.network_semantics", sidecar)
            manifest["correspondences"].append({"source_id": source_id, "network_id": record["id"],
                "replacement_path": str(destination), "part_guids": [p["ifc_guid"] for p in materialized["added_parts"]],
                "demand_ids": record["demand_ids"], "component_ids": record["component_ids"]})
        else:
            shutil.copyfile(original, destination)
        manifest["files"].append({"path": str(destination), "source_id": source["id"], "sha256": sha256_file(destination),
            "source_sha256": source["sha256"], "schema": source["schema"], "changed": changed})
        checks.persist()
    if exported is None:
        raise IntegrityError("Physical network source is absent from exported federation")
    if not draft and manifest["round_trip"] == "PASS":
        copied_state = copy.deepcopy(state)
        copied_state["physical_networks"][0]["geometry_artifact"] = store.put(exported)
        copied_state["derived_artifacts"]["export_correspondence"] = {"input_candidate_root": root, "files": manifest["files"]}
        checked_copy = store.add_candidate(candidate["run_id"], copied_state, {"kind": "physical_network", "export_recheck": True,
            "changed_ids": candidate["changed_ids"], "routes": [], "networks": copied_state["physical_networks"], "objective": {},
            "rationale": "Fresh independent check of the entire exported shared network and all federation files"})
        checks.verify(checked_copy, original_report)
    service_scope = ("declared fixed-loss pressure-driven operating model"
        if any(state.get("derived_artifacts", {}).get("network_contract", {}).get("scenario", {}).get(k) is not None for k in ("pressure_driven", "passive_tree"))
        else "supplied-flow checks")
    manifest["limitations"].append(f"Local shared-network coordination and {service_scope} do not certify pre-existing defects or whole-building engineering adequacy")
    atomic_json(directory / "manifest.json", manifest)
    atomic_json(directory / "state.json", state)
    events, cursor = [], 0
    while batch := store.events(project["id"], cursor, 1000):
        events.extend(batch)
        cursor = batch[-1]["seq"]
    atomic_json(directory / "events.json", events)
    manifest_root = store.put(manifest)
    store.append_event(project["id"], state_root=root, candidate_id=candidate["id"] if candidate else None, stage="export",
        status=manifest["status"], message="Complete shared-network IFC exported and independently rechecked", artifacts=[manifest_root],
        payload={"directory": str(directory), "round_trip": manifest["round_trip"]})
    if not draft and manifest["status"] != "CHECKED_LOCAL_SCOPE":
        raise IntegrityError(f"Network export failed fresh checking; evidence retained at {directory}")
    return {"status": manifest["status"], "export_id": export_id, "directory": str(directory), "manifest": str(directory / "manifest.json"),
        "artifact_root": manifest_root, "files": manifest["files"], "scope": manifest.get("checked_scope"), "round_trip": manifest["round_trip"]}
