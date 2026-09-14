"""Complete composite IFC replacement bundles and fresh exported-state checks."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

from oma.build_identity import frozen_environment
from oma.ifc.audit import atomic_json, sha256_file
from oma.store import IntegrityError, utcnow


def export_joint_project(store, project, state, candidate, draft, original_report=None):
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
    runtime = frozen_environment(store.directory)
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
                process = subprocess.run([sys.executable, "-m", "oma.ifc.recheck", str(manifest_path)],
                    capture_output=True, text=True, timeout=300, env=runtime, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                if process.returncode:
                    roundtrips.append("FAIL")
                    manifest["limitations"].append(process.stderr[-3000:])
                else:
                    exported[rid] = json.loads(manifest_path.read_text(encoding="utf-8"))
                    roundtrips.append(exported[rid]["reimport"]["status"])
            atomic_json(destination.with_suffix(".manifest.json"), exported[members[0]])
            manifest["correspondences"].append({"source_id": source["id"], "replacement_path": str(destination),
                "route_ids": members, "part_guids": [p["ifc_guid"] for m in materials for p in m["added_parts"]]})
        else:
            shutil.copyfile(original, destination)
        manifest["files"].append({"path": str(destination), "source_id": source["id"], "sha256": sha256_file(destination),
            "source_sha256": source["sha256"], "schema": source["schema"], "changed": bool(members)})
    manifest["round_trip"] = "PASS" if roundtrips and all(r == "PASS" for r in roundtrips) else "FAIL"
    if not draft and manifest["round_trip"] == "PASS":
        exported_state = copy.deepcopy(state)
        for route in exported_state["routes"]:
            route["geometry_artifact"] = store.put(exported[route["id"]])
        exported_state["derived_artifacts"]["export_correspondence"] = {"input_candidate_root": root, "files": manifest["files"]}
        exported_candidate = store.add_candidate(candidate["run_id"], exported_state, {"kind": "physical_route_set", "export_recheck": True,
            "changed_ids": candidate["changed_ids"], "routes": exported_state["routes"], "objective": {}, "rationale": "Independent check of complete exported composite IFC files"})
        process = subprocess.run([sys.executable, "-m", "oma.verification", str(store.directory), exported_candidate["id"]],
            capture_output=True, text=True, timeout=600, env=runtime, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        checked = store.candidate(exported_candidate["id"])
        if process.returncode == 0 and checked["status"] == "CHECKED":
            report = store.get(checked["report_root"])
            if report["objective"] == original_report["objective"]:
                manifest.update(status="CHECKED_LOCAL_SCOPE", checked_scope=report["scope"], exported_state_root=checked["state_root"],
                    verification_root=checked["report_root"], objective=report["objective"])
                atomic_json(directory / "verification.json", report)
            else:
                manifest["round_trip"] = "FAIL_OBJECTIVE_MISMATCH"
        else:
            manifest["round_trip"] = "FAIL_INDEPENDENT_CHECK"
            manifest["limitations"].append(process.stderr[-3000:] or checked["status"])
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
