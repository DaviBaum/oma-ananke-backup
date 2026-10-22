"""Complete composite IFC replacement bundles and fresh exported-state checks."""
import copy
import shutil
import uuid

from oma.export_checks import DEFAULT_EXPORT_BUDGET_SECONDS, ExportChecks
from oma.ifc.audit import atomic_json, sha256_file
from oma.store import IntegrityError, utcnow


def export_joint_project(store, project, state, candidate, draft, original_report=None, *, budget_seconds=DEFAULT_EXPORT_BUDGET_SECONDS, started=None):
    root = candidate["state_root"] if candidate else project["state_root"]
    export_id = uuid.uuid4().hex
    directory = store.directory / "exports" / export_id
    directory.mkdir(parents=True)
    manifest = {"export_id": export_id, "project_id": project["id"], "candidate_id": candidate["id"] if candidate else None,
        "state_root": root, "created_at": utcnow(), "status": "DRAFT", "files": [], "correspondences": [],
        "round_trip": "NOT_RUN", "whole_building_release": "NOT_CERTIFIED", "limitations": [],
        "source_redistribution": "Local user export; original project license terms retained"}
    contracts = state["derived_artifacts"]["routing_contracts"]
    routes = {r["id"]: r for r in state["routes"]}
    exported = {}
    checks = ExportChecks(store, directory, manifest, budget_seconds=budget_seconds, started=started)
    atomic_json(directory / "state.json", state)
    roundtrips = []
    for index, source in enumerate(state["sources"]):
        original = store.resolve_path(source["immutable_path"])
        if sha256_file(original) != source["sha256"]:
            raise IntegrityError("Original source bytes changed; joint export stopped")
        destination = directory / f"{index+1:02d}_{source['name']}"
        members = [r for r in routes if contracts[r]["source_id"] == source["id"]]
        if members:
            materials = [store.get(routes[r]["geometry_artifact"]) for r in members]
            files = {(str(store.resolve_path(m["export_path"])), m["export_sha256"]) for m in materials}
            if len(files) != 1 or any(m["source_sha256"] != source["sha256"] for m in materials):
                raise IntegrityError("Routes lack one complete source replacement")
            physical_path, physical_hash = files.pop()
            if sha256_file(physical_path) != physical_hash:
                raise IntegrityError("Composite physical IFC bytes changed")
            shutil.copyfile(physical_path, destination)
            for rid, material in zip(members, materials):
                exported[rid] = {**material, "source_path": str(original), "export_path": str(destination),
                    "export_sha256": sha256_file(destination), "reimport": {"status": "NOT_RUN"}}
                manifest_path = directory / f"route-{rid}.manifest.json"
                atomic_json(manifest_path, exported[rid])
                exported[rid], status = checks.reimport("oma.ifc.recheck", manifest_path)
                roundtrips.append(status)
            atomic_json(destination.with_suffix(".manifest.json"), exported[members[0]])
            manifest["correspondences"].append({"source_id": source["id"], "replacement_path": str(destination),
                "route_ids": members, "part_guids": [p["ifc_guid"] for m in materials for p in m["added_parts"]]})
        else:
            shutil.copyfile(original, destination)
        manifest["files"].append({"path": str(destination), "source_id": source["id"], "sha256": sha256_file(destination),
            "source_sha256": source["sha256"], "schema": source["schema"], "changed": bool(members)})
        checks.persist()
    manifest["round_trip"] = "PASS" if roundtrips and all(r == "PASS" for r in roundtrips) else next((r for r in roundtrips if r != "PASS"), "NOT_RUN")
    if not draft and manifest["round_trip"] == "PASS":
        exported_state = copy.deepcopy(state)
        for route in exported_state["routes"]:
            route["geometry_artifact"] = store.put(exported[route["id"]])
        exported_state["derived_artifacts"]["export_correspondence"] = {"input_candidate_root": root, "files": manifest["files"]}
        exported_candidate = store.add_candidate(candidate["run_id"], exported_state, {"kind": "physical_route_set", "export_recheck": True,
            "changed_ids": candidate["changed_ids"], "routes": exported_state["routes"], "objective": {}, "rationale": "Independent check of complete exported composite IFC files"})
        checks.verify(exported_candidate, original_report)
    manifest["limitations"].append("Local route-set checks do not certify pre-existing defects or complete whole-building engineering adequacy")
    atomic_json(directory / "manifest.json", manifest)
    atomic_json(directory / "state.json", state)
    events, cursor = [], 0
    while batch := store.events(project["id"], cursor, 1000):
        events.extend(batch)
        cursor = batch[-1]["seq"]
    atomic_json(directory / "events.json", events)
    manifest_root = store.put(manifest)
    store.append_event(project["id"], state_root=root, candidate_id=candidate["id"] if candidate else None, stage="export", status=manifest["status"],
        message="Complete simultaneous route IFC replacements exported and independently rechecked", artifacts=[manifest_root],
        payload={"directory": str(directory), "round_trip": manifest["round_trip"]})
    if not draft and manifest["status"] != "CHECKED_LOCAL_SCOPE":
        raise IntegrityError(f"Joint export failed fresh checking; evidence retained at {directory}")
    return {"status": manifest["status"], "export_id": export_id, "directory": str(directory), "manifest": str(directory / "manifest.json"),
        "artifact_root": manifest_root, "files": manifest["files"], "scope": manifest.get("checked_scope"), "round_trip": manifest["round_trip"]}
