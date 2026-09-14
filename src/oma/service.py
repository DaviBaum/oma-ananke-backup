"""Local project orchestration; all expensive parsing runs in isolated processes."""
from __future__ import annotations

import gzip
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from .hardware import ResourceBroker
from .store import Conflict, IntegrityError, Store


def validate_ifc_paths(paths: list[str]) -> list[str]:
    if not paths or len(paths) > 64:
        raise ValueError("Select between 1 and 64 IFC discipline files")
    resolved = []
    for value in paths:
        path = Path(value).expanduser().resolve(strict=True)
        if path.suffix.lower() != ".ifc" or not path.is_file():
            raise ValueError(f"Expected a regular .ifc file: {path.name}")
        if path.stat().st_size > 4 * 1024 ** 3:
            raise ValueError(f"IFC exceeds the 4 GiB per-file parser budget: {path.name}")
        with path.open("rb") as stream:
            if not stream.read(4096).lstrip(b"\xef\xbb\xbf \r\n\t").startswith(b"ISO-10303-21;"):
                raise ValueError(f"Not actual IFC STEP bytes: {path.name}")
        resolved.append(str(path))
    if len(set(resolved)) != len(resolved):
        raise ValueError("The same file was selected more than once")
    return resolved


class EngineService:
    def __init__(self, directory: str | Path):
        self.store = Store(directory)
        self.broker = ResourceBroker(directory)
        self.processes: dict[str, subprocess.Popen] = {}
        self.threads: dict[str, threading.Thread] = {}
        self.lock = threading.Lock()
        self.closing = False

    def import_project(self, paths: list[str], name: str, idempotency_key: str | None = None) -> dict:
        paths = validate_ifc_paths(paths)
        project = self.store.create_import(name.strip() or "Untitled federation", {
            "schema_version": 1, "sources": [], "entities": [], "ports": [], "routes": [],
            "explicit_connections": [], "inferred_connections": [], "mission": None,
            "assumptions": [], "dependencies": {}, "derived_artifacts": {}, "units": "m"}, paths, idempotency_key)
        self.schedule(project["import_run_id"])
        return project

    def start_run(self, project_id: str, request: dict) -> dict:
        if self.closing:
            raise Conflict("Service is shutting down")
        if any(r["status"] in {"QUEUED", "RUNNING", "CHECKING", "PAUSED"} and r["operation"] == "import" for r in self.store.runs(project_id)):
            raise Conflict("Wait for source import to finish")
        run = self.store.create_run(project_id, request)
        self.schedule(run["id"])
        return run

    def schedule(self, run_id: str):
        thread = threading.Thread(target=self._supervise, args=(run_id,), daemon=True, name=f"oma-{run_id[:8]}")
        with self.lock:
            if run_id in self.threads or self.store.run(run_id)["status"] != "QUEUED":
                return
            self.store.claim_run(run_id, "supervisor")
            self.threads[run_id] = thread
        thread.start()

    def _supervise(self, run_id: str):
        try:
            with self.broker.admit():
                if self.closing or self.store.run(run_id)["desired_action"] == "cancel":
                    self.store.update_run(run_id, "CANCELLED", "Cancelled before worker start", "control")
                    return
                logs = self.store.directory / "logs"
                logs.mkdir(exist_ok=True)
                with (logs / f"{run_id}.log").open("wb") as log:
                    process = subprocess.Popen([sys.executable, "-m", "oma.worker", str(self.store.directory), run_id],
                                               stdout=log, stderr=subprocess.STDOUT,
                                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    with self.lock:
                        self.processes[run_id] = process
                    budget = float(self.store.run(run_id)["request"].get("budget_seconds", 300))
                    deadline = time.monotonic() + max(30, budget + 30)
                    while process.poll() is None:
                        if self.closing or self.store.run(run_id)["desired_action"] == "cancel":
                            self._terminate_tree(process)
                            self.store.update_run(run_id, "CANCELLED", "Worker and child processes stopped; no candidate published", "control")
                            return
                        if time.monotonic() > deadline:
                            self._terminate_tree(process)
                            self.store.update_run(run_id, "TIMED_OUT", "Worker wall-clock budget exhausted; no infeasibility claim", "budget")
                            return
                        time.sleep(.15)
                    code = process.returncode
                    run = self.store.run(run_id)
                    if code != 0 or run["status"] in {"QUEUED", "RUNNING", "CHECKING", "PAUSED"}:
                        self.store.update_run(run_id, "CRASHED", f"Worker exited with code {code}; see local diagnostic log", "recovery")
        except BaseException as exc:
            self.store.update_run(run_id, "FAILED", f"{type(exc).__name__}: {exc}", "supervisor")
        finally:
            with self.lock:
                self.processes.pop(run_id, None)
                self.threads.pop(run_id, None)

    def selected_project(self, project_id: str, revision: int | None = None, candidate_id: str | None = None) -> dict:
        project = self.store.project(project_id)
        if revision is not None and candidate_id is not None:
            raise ValueError("Select either a historical revision or a candidate")
        project["current_revision"] = project["revision"]
        project["current_state_root"] = project["state_root"]
        if candidate_id:
            candidate = self.store.candidate(candidate_id)
            if candidate["project_id"] != project_id:
                raise IntegrityError("Candidate belongs to another project")
            project.update(state_root=candidate["state_root"], revision=candidate["base_revision"], status=candidate["status"], selected_candidate_id=candidate_id)
        elif revision is not None:
            historical = next((r for r in self.store.history(project_id) if r["revision"] == revision), None)
            if not historical:
                raise KeyError(f"Revision {revision}")
            project.update(state_root=historical["root"], revision=revision, status=historical["status"])
        return project

    def snapshot(self, project_id: str, revision: int | None = None, candidate_id: str | None = None) -> dict:
        project = self.selected_project(project_id, revision, candidate_id)
        state = self.store.get(project["state_root"])
        candidates = self.store.candidates(project_id)
        from .build_identity import checker_version
        current_checker = checker_version()
        issues = []
        checks = []
        for candidate in candidates:
            if candidate.get("report_root"):
                report = self.store.get(candidate["report_root"])
                from collections import Counter
                reasons = Counter(r["reason"] for r in report["results"] if r["status"] not in {"PASS", "NOT_APPLICABLE"})
                summary = "; ".join(f"{reason} ({count})" if count > 1 else reason for reason, count in reasons.most_common(8))
                applicability = "WRONG_ROOT" if report["candidate_root"] != candidate["state_root"] else "STALE_EXECUTABLE" if report["checker_version"] != current_checker else "CURRENT"
                candidate["check"] = {"status": report["status"], "reason": summary or "Declared check set passed", "scope": report["scope"], "result_count": len(report["results"]), "reason_counts": dict(reasons),
                    "applicability": applicability, "checker_version": report["checker_version"], "current_checker_version": current_checker}
                candidate["objective"] = report["objective"]
                for result in report["results"]:
                    checks.append({**result, "candidate_id": candidate["id"], "report_root": candidate["report_root"]})
                    if result["status"] in {"FAIL", "UNKNOWN", "BLOCKED"}:
                        issues.append({"id": f"{candidate['id']}:{result['id']}", "rule": result["id"],
                                       "status": result["status"], "severity": "error" if result["status"] == "FAIL" else "warning",
                                       "participants": result.get("participants", []), "message": result["reason"],
                                       "scope": result["scope"], "witness": result.get("witness", {}), "artifact": candidate["report_root"]})
            candidate.setdefault("objective", {})
            candidate.setdefault("changed_ids", [])
            candidate.setdefault("routes", [])
            candidate.setdefault("networks", [])
            if candidate.get("kind") in {"physical_route", "physical_route_set", "physical_network"}:
                candidate_state = self.store.get(candidate["state_root"])
                from .validation_advisories import candidate_advisories
                candidate["validation_advisories"] = candidate_advisories(self.store, candidate, candidate_state)
                contracts = candidate_state.get("derived_artifacts", {}).get("routing_contracts", {})
                candidate["routes"] = [{**route, "request_demand_id": contracts.get(route["id"], {}).get("request_demand_id")}
                    for route in (candidate["routes"] or candidate_state.get("routes", []))]
                candidate["networks"] = self.network_views(candidate_state)
        sources = state.get("sources", [])
        missing = []
        if not sources:
            missing.append("Source IFC import has not finished")
        for source in sources:
            for blocker in source.get("blockers", []):
                missing.append({"source": source.get("name"), **blocker})
        if state.get("mission") is None:
            missing.append("Routing requires an explicit mission: ports, service demands, sections, constraints and permitted changes")
        federation = state.get("derived_artifacts", {}).get("federation", {})
        if federation.get("status") not in {None, "VERIFIED"}:
            missing.append({"code": "FEDERATION_DATUM_REVIEW", "reason": "Cross-file coordinate agreement requires checked datum evidence", "details": federation})
        entities = []
        for entity in state.get("entities", []):
            geometry = entity.get("geometry", {})
            provenance = entity.get("provenance", {})
            entities.append({**entity, "guid": provenance.get("guid"), "step_id": provenance.get("step_id"),
                             "source_file": next((s.get("name") for s in sources if s.get("id") == provenance.get("source_id")), None),
                             "geometry_status": geometry.get("status"), "bounds": geometry.get("bounds"),
                             "locked": entity.get("protected", True), "system": ", ".join(entity.get("system_ids", []))})
        for route in state.get("routes", []):
            entities.append({"id": route["id"], "name": route["id"], "ifc_type": "PhysicalRoute", "discipline": route["service"],
                             "geometry_status": "represented" if route.get("geometry_artifact") else "unresolved", "locked": False,
                             "properties": {"section": route["section"], "demand_ids": route["demand_ids"], "ports": route["port_ids"]}})
        networks = self.network_views(state)
        for network in networks:
            spec = network["network_spec"]
            parts = {part["component_id"]: part for part in network["added_parts"]}
            for component in spec["components"]:
                cid = component["id"]
                part = parts.get(cid, {})
                demand_ids = [path["demand_id"] for path in spec["demand_paths"]
                              if any(step["component"] == cid for step in path["steps"])]
                entities.append({"id": f"{network['id']}:{cid}", "name": f"{spec['network_id']} / {cid}",
                    "ifc_type": "PhysicalNetworkComponent", "discipline": network["service"],
                    "system": spec["network_id"], "guid": part.get("ifc_guid"), "step_id": part.get("step_id"),
                    "source_file": network["source_file"],
                    "network_id": network["id"], "component_id": cid, "demand_ids": demand_ids,
                    "geometry_status": "represented" if part.get("ifc_guid") else "unresolved", "locked": False,
                    "properties": {"kind": component["kind"], "section": network["section"],
                        "demand_ids": demand_ids, "shared_component": len(demand_ids) > 1,
                        "ports": part.get("ports", {}), "component": component}})
        history = [{**r, "state_root": r["root"]} for r in self.store.history(project_id)]
        with self.store.connect() as db:
            seq = db.execute("SELECT COALESCE(MAX(seq),0) FROM events WHERE project_id=?", (project_id,)).fetchone()[0]
        return {"project": project, "entities": entities, "sources": sources, "issues": issues, "checks": checks,
                "candidates": candidates, "runs": self.store.runs(project_id), "history": history,
                "networks": networks, "constraints": [state["mission"]] if state.get("mission") else [], "missing_inputs": missing, "events_seq": seq}

    def network_views(self, state: dict) -> list[dict]:
        views = []
        for network in state.get("physical_networks", []):
            if not network.get("geometry_artifact"):
                continue
            materialized = self.store.get(network["geometry_artifact"])
            views.append({**network, "source_file": Path(materialized["export_path"]).name, "network_spec": materialized["network_spec"],
                          "added_parts": materialized["added_parts"]})
        return views

    def geometry(self, project_id: str, revision: int | None = None, candidate_id: str | None = None) -> dict:
        project = self.selected_project(project_id, revision, candidate_id)
        return self.geometry_at(project)

    def geometry_at(self, project: dict) -> dict:
        """Render the already selected immutable root, even if the head changes."""
        project_id = project["id"]
        state = self.store.get(project["state_root"])
        meshes, minimum, maximum = [], None, None
        for source in state.get("sources", []):
            path = source.get("artifacts", {}).get("mesh_json_gz")
            if not path:
                continue
            with gzip.open(self.store.resolve_path(path), "rt", encoding="utf-8") as stream:
                payload = json.load(stream)
            if source.get("transform_m"):
                from .ifc.federation import transform_mesh_payload
                payload = transform_mesh_payload(payload, source["transform_m"])
            for mesh in payload["meshes"]:
                mesh["discipline"] = source.get("discipline", "unclassified")
                meshes.append(mesh)
            if source.get("bounds"):
                bounds = source["bounds"]
                minimum = bounds["min"] if minimum is None else [min(a, b) for a, b in zip(minimum, bounds["min"])]
                maximum = bounds["max"] if maximum is None else [max(a, b) for a, b in zip(maximum, bounds["max"])]
        for route in state.get("routes", []):
            if not route.get("geometry_artifact"):
                continue
            materialized = self.store.get(route["geometry_artifact"])
            cache = self.store.directory / "geometry" / "routes" / f"{route['geometry_artifact']}.json.gz"
            if cache.exists():
                with gzip.open(cache, "rt", encoding="utf-8") as stream:
                    route_meshes = json.load(stream)
            else:
                import ifcopenshell
                import ifcopenshell.geom
                model = ifcopenshell.open(str(self.store.resolve_path(materialized["export_path"])))
                settings = ifcopenshell.geom.settings()
                settings.set("use-world-coords", True)
                route_meshes = []
                for part in materialized["added_parts"]:
                    shape = ifcopenshell.geom.create_shape(settings, model.by_guid(part["ifc_guid"]))
                    route_meshes.append({"entity_id": route["id"], "vertices": list(shape.geometry.verts), "faces": list(shape.geometry.faces), "discipline": route["service"], "color": [.1, .72, .5]})
                matrix = materialized.get("route_spec", {}).get("source_to_federation_matrix")
                if matrix:
                    from .ifc.federation import transform_mesh_payload
                    route_meshes = transform_mesh_payload({"meshes": route_meshes}, matrix)["meshes"]
                cache.parent.mkdir(parents=True, exist_ok=True)
                temp = cache.with_suffix(f".{uuid.uuid4().hex}.tmp")
                with gzip.open(temp, "wt", encoding="utf-8", compresslevel=3) as stream:
                    json.dump(route_meshes, stream, separators=(",", ":"))
                os.replace(temp, cache)
            meshes.extend(route_meshes)
        from .geometry_stream import iter_network_meshes
        meshes.extend(iter_network_meshes(self.store, state))
        return {"project_id": project_id, "state_root": project["state_root"], "revision": project["revision"],
                "units": "m", "coordinate_system": "world", "meshes": meshes,
                "bounds": {"min": minimum, "max": maximum} if minimum else None}

    @staticmethod
    def _terminate_tree(process):
        import psutil
        try:
            children = psutil.Process(process.pid).children(recursive=True)
        except psutil.NoSuchProcess:
            children = []
        for child in reversed(children):
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        if process.poll() is None:
            process.terminate()
        _, alive = psutil.wait_procs(children, timeout=3)
        for child in alive:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        process.wait(timeout=10)

    def shutdown(self):
        self.closing = True
        with self.lock:
            processes = list(self.processes.items())
        for run_id, process in processes:
            try:
                self.store.control(run_id, "cancel")
                process.wait(timeout=3)
            except (subprocess.TimeoutExpired, Conflict):
                if process.poll() is None:
                    self._terminate_tree(process)
                    self.store.update_run(run_id, "CANCELLED", "Worker terminated during clean shutdown; candidate not published", "control")
