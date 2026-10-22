"""Read-only, isolated eligibility inspection of an imported wall or slab."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from .ifc.audit import sha256_file
from .store import IntegrityError


def inspect_selected_host(store, project, entity_id):
    state = store.get(project["state_root"])
    entities = [e for e in state.get("entities", []) if e["id"] == entity_id]
    if len(entities) != 1:
        raise ValueError("Select one imported host entity in this exact project state")
    entity = entities[0]
    source = next((s for s in state["sources"] if s["id"] == entity["provenance"]["source_id"]), None)
    if source is None:
        raise IntegrityError("Host provenance does not identify an imported source")
    identity = {"project_id": project["id"], "state_root": project["state_root"], "entity_id": entity_id,
        "source_id": source["id"], "source_sha256": source["sha256"], "opening_permission": "NOT_INFERRED",
        "requires_explicit_permission": True, "engineering_scope": "SCENARIO_GEOMETRY_ONLY"}
    if state.get("routes") or state.get("physical_networks") or state.get("mission") or state.get("derived_artifacts", {}).get("opening_edit"):
        return {**identity, "status": "INELIGIBLE", "reason": "The first opening contract requires an imported baseline without prior engineering edits"}
    if source.get("transform_m") is None:
        return {**identity, "status": "INELIGIBLE", "reason": "Source datum must be resolved before an opening can be proposed"}
    path = store.resolve_path(source["immutable_path"])
    if sha256_file(path) != source["sha256"]:
        raise IntegrityError("Immutable source changed before host inspection")
    provenance = entity["provenance"]
    if provenance.get("content_hash") != source["sha256"] or entity_id != f"{source['id']}:{provenance['step_id']}" or not provenance.get("guid"):
        raise IntegrityError("Host identity is not completely bound to immutable source facts")
    from .build_identity import frozen_environment
    try:
        completed = subprocess.run([sys.executable, "-m", "oma.opening_inspection", str(path), provenance["guid"],
            str(provenance["step_id"]), source["sha256"]], capture_output=True, text=True, timeout=75,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), env=frozen_environment(store.directory))
    except subprocess.TimeoutExpired:
        return {**identity, "status": "UNKNOWN", "reason": "Native host inspection exceeded its time budget"}
    if completed.returncode:
        return {**identity, "status": "UNKNOWN", "reason": "Native inspection did not complete within its process/resource contract"}
    result = json.loads(completed.stdout)
    if result["status"] == "ELIGIBLE":
        host = result["host"]
        if host["source_sha256"] != source["sha256"] or host["host_guid"] != provenance["guid"] or host["host_step_id"] != provenance["step_id"]:
            raise IntegrityError("Native inspection returned a different host identity")
    return {**identity, **result, "source_to_federation_matrix": source["transform_m"]}


def _native_probe(path, guid, step, expected_source):
    import psutil
    stopped = threading.Event()
    deadline = time.monotonic() + 60
    process = psutil.Process()

    def watchdog():
        while not stopped.wait(.2):
            if time.monotonic() > deadline or process.memory_info().rss > 8 * 1024**3 or psutil.virtual_memory().available < 2 * 1024**3:
                os._exit(3)

    monitor = threading.Thread(target=watchdog, daemon=True)
    monitor.start()
    try:
        from .ifc.openings import inspect_host
        if sha256_file(path) != expected_source:
            raise ValueError("Source hash changed before native inspection")
        host = inspect_host(Path(path), guid, int(step))
        if sha256_file(path) != expected_source:
            raise ValueError("Source hash changed during native inspection")
        result = {"status": "ELIGIBLE", "host": host, "reason": "Actual rectangular host representation and native support agree"}
    except (ValueError, RuntimeError) as exc:
        result = {"status": "INELIGIBLE", "reason": str(exc)}
    finally:
        stopped.set()
        monitor.join(timeout=1)
    print(json.dumps(result, allow_nan=False))


if __name__ == "__main__":
    _native_probe(*sys.argv[1:])
