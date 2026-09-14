"""Fresh process boundary for parsers, optimizers and independent checks."""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
import traceback
import subprocess
import threading
from pathlib import Path

from .models import EngineeringState, Entity, Geometry, Provenance
from .store import Store, digest, TERMINAL_RUN_STATUSES


class Cancelled(Exception):
    pass


class WorkerControl:
    def __init__(self, store: Store, run_id: str):
        self.store, self.run_id = store, run_id
        self.active = store.run(run_id)["status"] not in TERMINAL_RUN_STATUSES

    def checkpoint(self, stage: str = "compute"):
        if not self.active:
            return  # Explicit fresh recheck of a historical candidate.
        while True:
            run = self.store.run(self.run_id)
            action = run["desired_action"]
            if action == "cancel" or run["status"] in {"CANCELLED", "CRASHED", "TIMED_OUT", "FAILED"}:
                raise Cancelled()
            if action == "pause" or (action == "step" and not self.store.consume_step(self.run_id)):
                if run["status"] != "PAUSED":
                    self.store.update_run(self.run_id, "PAUSED", "Worker paused at a consistent checkpoint", stage)
                time.sleep(.1)
                continue
            if run["status"] == "PAUSED":
                self.store.update_run(self.run_id, "RUNNING", "Worker resumed", stage)
            return


def import_sources(store: Store, run: dict, control: WorkerControl):
    from .ifc.audit import audit_file, federation_manifest, sha256_file
    from .service import validate_ifc_paths
    paths = validate_ifc_paths(run["request"]["paths"])
    audits = []
    sources = []
    entities = []
    for index, filename in enumerate(paths):
        control.checkpoint("import")
        path = Path(filename)
        store.append_event(run["project_id"], run_id=run["id"], state_root=run["base_root"], stage="import", status="RUNNING", message=f"Auditing {path.name}", payload={"file_index": index + 1, "file_count": len(paths), "source": str(path)})
        source_hash = sha256_file(path)
        immutable = store.directory / "imports" / source_hash / path.name
        immutable.parent.mkdir(parents=True, exist_ok=True)
        if not immutable.exists():
            temp = immutable.with_suffix(".pending")
            shutil.copyfile(path, temp)
            if sha256_file(temp) != source_hash:
                raise ValueError("Input changed while making immutable import; retry after source export finishes")
            os.replace(temp, immutable)
        elif sha256_file(immutable) != source_hash:
            raise ValueError("Immutable import content is corrupt")
        out = store.directory / "geometry" / source_hash
        existing = list(out.glob("*.audit.json")) if out.exists() else []
        audit = None
        for cache in existing:
            candidate = json.loads(cache.read_text(encoding="utf-8"))
            if candidate.get("source_sha256") == source_hash and candidate.get("audit_version") == "oma-ifc-audit/1" and all(Path(p).exists() for p in candidate.get("artifacts", {}).values()):
                audit = candidate
                break
        if audit is None:
            audit = audit_file(immutable, out, geometry=True, mesh=True, threads=4)
        audit_root = store.put(audit)
        discipline = path.stem  # Source label, not evidence that a discipline is present.
        source = {"id": source_hash, "name": path.name, "original_path": str(path), "immutable_path": str(immutable),
                  "sha256": source_hash, "audit_root": audit_root, "schema": audit["schema"],
                  "discipline": discipline, "bounds": audit.get("bounds"), "artifacts": audit.get("artifacts", {}),
                  "blockers": audit["blockers"], "product_count": audit["product_count"],
                  "geometry_counts": audit["geometry_counts"], "units": audit["units"], "performance": audit["performance"]}
        sources.append(source)
        audits.append(audit)
        for record_index, record in enumerate(audit["products"]):
            if record_index % 512 == 0:
                control.checkpoint("import_entity_batch")
            geometry_status = record["geometry_status"]
            if geometry_status == "explicitly_non_geometric":
                geometry_status = "non_geometric"
            entity = Entity(id=record["entity_id"], name=record.get("name") or "", ifc_type=record["type"],
                            provenance=Provenance(source_id=source_hash, content_hash=source_hash, step_id=record["step_id"], guid=record.get("ifc_guid")),
                            geometry=Geometry(status=geometry_status, representation="ifc_brep" if geometry_status == "represented" else "none",
                                              artifact=audit_root, bounds=record.get("bounds"), reason=record.get("geometry_reason", "")),
                            discipline=discipline, storey=record.get("container_name"),
                            system_ids=tuple(f"{source_hash}:{s}" for s in record.get("system_ids", [])), properties=record.get("properties", {}))
            entities.append(entity)
        store.append_event(run["project_id"], run_id=run["id"], stage="import", status="IMPORTED", message=f"{path.name}: {audit['represented_count']} represented / {audit['product_count']} products accounted", artifacts=[audit_root], payload={"source": source, "performance": audit["performance"]})
    control.checkpoint("federation")
    from .ifc.federation import audited_local_federation
    import numpy as np
    def source_progress(stage, message, payload):
        store.append_event(run["project_id"], run_id=run["id"], state_root=run["base_root"],
                           stage=stage, status="RUNNING", message=message, payload=payload)

    local_coordinates = audited_local_federation(audits, checkpoint=control.checkpoint,
        on_source=lambda payload: source_progress("federation", "Rechecking source coordinate anchors", payload))
    federation = federation_manifest(audits, run["project_id"], local_coordinates["transforms"])
    for source in sources:
        transform = local_coordinates["transforms"].get(source["id"], {}).get("matrix")
        # One source already defines its own metre-valued local frame. It needs
        # no cross-file anchor to express new geometry in that same frame.
        # This does not establish site coordinates or resolve a federation.
        if len(sources) == 1 and source["units"]["status"] == "KNOWN":
            source["transform_m"] = np.eye(4).tolist()
            source["coordinate_scope"] = "SINGLE_SOURCE_LOCAL_IDENTITY"
        if transform is not None and local_coordinates["status"] == "VERIFIED":
            source["transform_m"] = transform
            source["coordinate_scope"] = "VERIFIED_LOCAL_FEDERATION"
            if source["bounds"]:
                lo, hi = source["bounds"]["min"], source["bounds"]["max"]
                import itertools
                corners = np.array(list(itertools.product(*zip(lo, hi))))
                matrix = np.array(transform)
                corners = corners @ matrix[:3,:3].T + matrix[:3,3]
                source["bounds"] = {"min": corners.min(axis=0).tolist(), "max": corners.max(axis=0).tolist()}
    transformed_entities = []
    source_frames = {source["id"]: source.get("transform_m") for source in sources}
    for entity_index, entity in enumerate(entities):
        if entity_index % 512 == 0:
            control.checkpoint("federation_entity_batch")
        transform = source_frames.get(entity.provenance.source_id)
        if transform is not None and entity.geometry.bounds:
            import itertools
            bounds = entity.geometry.bounds
            corners = np.array(list(itertools.product(*zip(bounds.min, bounds.max))))
            matrix = np.array(transform)
            corners = corners @ matrix[:3,:3].T + matrix[:3,3]
            entity = entity.model_copy(update={"geometry": entity.geometry.model_copy(update={"bounds": type(bounds)(min=tuple(corners.min(axis=0)), max=tuple(corners.max(axis=0)))})})
        transformed_entities.append(entity)
    from .normalization import normalize_connectivity, refresh_ownership
    refreshed = []
    for index, (audit, source) in enumerate(zip(audits, sources)):
        control.checkpoint("connectivity_ownership_source")
        source_progress("connectivity_ownership", "Rechecking explicit source port ownership", {
            "source": source["name"], "source_sha256": source["sha256"], "file_index": index + 1,
            "file_count": len(sources), "port_count": len(audit.get("ports", []))})
        refreshed.append(refresh_ownership(store, audit, source, checkpoint=control.checkpoint))
    audits = refreshed
    ports, connections, connectivity = normalize_connectivity(audits, sources, checkpoint=control.checkpoint,
        on_source=lambda payload: source_progress("connectivity", "Normalizing explicit source ports and connections", payload))
    control.checkpoint("import_state_serialization")
    source_progress("import_state", "Serializing complete source and connectivity inventory", {
        "source_count": len(sources), "entity_count": len(transformed_entities), "port_count": len(ports),
        "connection_count": len(connections), "alignment_status": federation.get("alignment_status")})
    state = EngineeringState(project_id=run["project_id"], sources=tuple(sources), entities=tuple(transformed_entities),
                             ports=ports, explicit_connections=connections,
                             derived_artifacts={"federation": federation, "local_coordinate_evidence": local_coordinates,
                                                "connectivity_normalization": connectivity,
                                                "source_port_audits": {s["id"]: s["audit_root"] for s in sources}}).model_dump(mode="json")
    control.checkpoint("import_publish")
    store.publish(run["project_id"], state, run["base_revision"], f"import:{run['id']}", status="BASELINE", changed_ids=[e.id for e in entities])
    store.update_run(run["id"], "COMPLETED", "IFC import complete; engineering checks have not yet run", "import")


def execute(directory: str, run_id: str):
    store = Store(directory)
    run = store.run(run_id)
    store.claim_run(run_id, "worker")
    control = WorkerControl(store, run_id)
    stopped = threading.Event()
    # This watchdog lives in the worker, so an abruptly killed API/CLI cannot
    # leave an orphan parser without its cancellation and resource budgets.
    def watchdog():
        import psutil
        from .store import TERMINAL_RUN_STATUSES
        deadline = time.monotonic() + float(run["request"].get("budget_seconds", 300)) + 5
        process = psutil.Process()
        limit = min(48 * 1024**3, int(psutil.virtual_memory().total * .375))
        while not stopped.wait(.2):
            current = store.run(run_id)
            if current["status"] in TERMINAL_RUN_STATUSES:
                return
            status, reason = None, None
            if current["desired_action"] == "cancel":
                status, reason = "CANCELLED", "Worker cancellation stopped all child computations"
            elif time.monotonic() > deadline:
                status, reason = "TIMED_OUT", "Worker wall-clock budget exhausted; no infeasibility claim"
            children = process.children(recursive=True)
            rss = process.memory_info().rss
            for child in children:
                try:
                    rss += child.memory_info().rss
                except psutil.NoSuchProcess:
                    pass
            if rss > limit or psutil.virtual_memory().available < 2 * 1024**3:
                status, reason = "FAILED", "Worker process tree exceeded the RAM budget or machine reserve"
            if status:
                for child in reversed(children):
                    try:
                        child.kill()
                    except psutil.NoSuchProcess:
                        pass
                psutil.wait_procs(children, timeout=2)
                store.update_run(run_id, status, reason, "resource_control")
                os._exit(0 if status == "CANCELLED" else 2)
    monitor = threading.Thread(target=watchdog, daemon=True, name="oma-worker-budget")
    monitor.start()
    try:
        control.checkpoint("start")
        store.update_run(run_id, "RUNNING", f"Worker started: {run['operation']}", "start", payload={"pid": os.getpid()})
        if run["operation"] == "import":
            import_sources(store, run, control)
        elif run["operation"] == "check":
            from .verification import check_project_run
            check_project_run(store, run, control)
        elif run["operation"] == "recheck":
            from .verification import recheck_candidate_run
            recheck_candidate_run(store, run, control)
        elif run["operation"] in {"route", "optimize"}:
            from .routing.engine import route_project_run
            route_project_run(store, run, control)
        elif run["operation"] == "normalize":
            from .normalization import normalize_project_run
            normalize_project_run(store, run, control)
        else:
            raise ValueError(f"Unsupported worker operation {run['operation']}")
    except Cancelled:
        store.update_run(run_id, "CANCELLED", "Worker acknowledged cancellation at a consistent checkpoint", "control")
    except subprocess.TimeoutExpired:
        store.update_run(run_id, "TIMED_OUT", "Independent subprocess budget exhausted; result remains unverified", "budget")
    except BaseException as exc:
        traceback.print_exc()
        store.update_run(run_id, "FAILED", f"{type(exc).__name__}: {exc}", "failure")
    finally:
        stopped.set()
        monitor.join(timeout=3)


if __name__ == "__main__":
    execute(sys.argv[1], sys.argv[2])
