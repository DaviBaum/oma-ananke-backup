"""Loopback-only API and durable SSE; no runtime cloud services."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.gzip import GZipMiddleware

from . import __version__
from .build_identity import checker_version
from .hardware import diagnose
from .service import EngineService
from .store import Conflict, IntegrityError


# Identify the source/runtime observed when this API module started. Health
# never relabels already loaded code with a later on-disk source fingerprint.
_SERVED_CHECKER_VERSION = checker_version()
_DECLARED_CHECKER_VERSION = os.environ.get("OMA_EXECUTABLE_BUILD")
_STARTUP_ENVIRONMENT_MATCHES = _DECLARED_CHECKER_VERSION in (None, _SERVED_CHECKER_VERSION)


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ImportRequest(Input):
    paths: list[str] = Field(min_length=1, max_length=64)
    name: str = Field(default="Untitled federation", max_length=200)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=256)


class RunRequest(Input):
    operation: Literal["check", "route", "optimize", "normalize", "propose_network"] = "check"
    scope: list[str] = Field(default_factory=list, max_length=100000)
    mission: dict[str, Any] | None = None
    budget_seconds: float = Field(default=300, ge=1, le=3600, allow_inf_nan=False)
    seed: int = Field(default=0, ge=0, le=2**32 - 1)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=256)


class ControlRequest(Input):
    action: Literal["pause", "resume", "cancel", "step"]


class CommitRequest(Input):
    expected_revision: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=256)


class RevertRequest(CommitRequest):
    revision: int = Field(ge=0)


class ExportRequest(Input):
    candidate_id: str | None = None
    draft: bool = True
    budget_seconds: float = Field(default=3600, ge=1, le=7200, allow_inf_nan=False)


class RecheckRequest(Input):
    budget_seconds: float = Field(default=300, ge=1, le=3600, allow_inf_nan=False)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=256)


def create_app(directory: str | Path | None = None, *, recover: bool = True) -> FastAPI:
    service = EngineService(directory or os.environ.get("OMA_DATA_DIR", ".oma"))

    @asynccontextmanager
    async def lifespan(app):
        if recover:
            service.store.recover()
        yield
        await asyncio.to_thread(service.shutdown)

    app = FastAPI(title="OMA + ANANKE local engine", version=__version__, lifespan=lifespan)
    app.state.engine = service
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"])
    app.add_middleware(GZipMiddleware, minimum_size=2000, compresslevel=2)

    @app.middleware("http")
    async def local_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin:
            from urllib.parse import urlsplit
            parsed = urlsplit(origin)
            if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
                return JSONResponse({"detail": "This local engine only accepts browser requests from loopback origins"}, status_code=403)
        return await call_next(request)

    @app.exception_handler(Conflict)
    async def conflict(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(IntegrityError)
    async def integrity(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({"detail": f"Record not found: {exc}"}, status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.get("/api/health")
    def health():
        register = Path(__file__).resolve().parents[2] / "docs" / "capabilities.json"
        caps = json.loads(register.read_text(encoding="utf-8"))["capabilities"] if register.exists() else []
        try:
            disk_version, identity_error = checker_version(), None
        except (OSError, RuntimeError) as exc:
            disk_version, identity_error = None, f"{type(exc).__name__}: {exc}"
        identity = {"schema": "oma.server-identity/1", "checker_version": _SERVED_CHECKER_VERSION,
            "data_directory": str(service.store.directory.resolve()), "python_executable": sys.executable,
            "source_changed": disk_version != _SERVED_CHECKER_VERSION,
            "current_disk_checker_version": disk_version, "startup_environment_matches": _STARTUP_ENVIRONMENT_MATCHES,
            "declared_checker_version": _DECLARED_CHECKER_VERSION, "identity_error": identity_error}
        return {"status": "ok", "application": "oma-ananke", "version": __version__, "hardware": diagnose(service.store.directory),
                "server_identity": identity,
                "capabilities": [{**c, "label": c["id"].replace("_", " ")} for c in caps]}

    @app.get("/api/projects")
    def projects():
        return service.store.projects()

    @app.post("/api/projects/import", status_code=202)
    def import_project(body: ImportRequest):
        try:
            return service.import_project(body.paths, body.name, body.idempotency_key)
        except OSError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/projects/{project_id}/snapshot")
    def snapshot(project_id: str, revision: int | None = None, candidate_id: str | None = None):
        import orjson
        return Response(orjson.dumps(service.snapshot(project_id, revision, candidate_id)), media_type="application/json")

    @app.get("/api/projects/{project_id}/geometry")
    def geometry(project_id: str, revision: int | None = None, candidate_id: str | None = None):
        import gzip
        import orjson
        import uuid
        project = service.selected_project(project_id, revision, candidate_id)
        cache = service.store.directory / "geometry" / "views" / f"v4-{project['state_root']}.json.gz"
        if not cache.exists():
            payload = service.geometry_at(project)
            payload.pop("revision", None)  # Geometry belongs to a root; undo may reuse it at a newer revision.
            cache.parent.mkdir(parents=True, exist_ok=True)
            temporary = cache.with_suffix(f".{uuid.uuid4().hex}.pending")
            temporary.write_bytes(gzip.compress(orjson.dumps(payload), compresslevel=2, mtime=0))
            os.replace(temporary, cache)
        return Response(cache.read_bytes(), media_type="application/json", headers={"Content-Encoding": "gzip", "ETag": f'"geometry-v4-{project["state_root"]}"', "Cache-Control": "private, max-age=3600"})

    @app.get("/api/projects/{project_id}/geometry-stream")
    def geometry_stream(project_id: str, revision: int | None = None, candidate_id: str | None = None):
        from .geometry_stream import compressed_stream
        project = service.selected_project(project_id, revision, candidate_id)
        return StreamingResponse(compressed_stream(service.store, project), media_type="application/x-ndjson",
                                 headers={"Content-Encoding": "gzip", "ETag": f'"geometry-stream-v3-{project["state_root"]}"',
                                          "Cache-Control": "private, max-age=3600", "X-OMA-State-Root": project["state_root"]})

    @app.get("/api/projects/{project_id}/ports")
    def ports(project_id: str, entity_id: str | None = None, offset: int = 0, limit: int = 100, revision: int | None = None):
        project = service.selected_project(project_id, revision)
        state = service.store.get(project["state_root"])
        records = [p for p in state.get("ports", []) if entity_id is None or p["entity_id"] == entity_id or p["id"] == entity_id]
        begin, count = max(0, offset), min(max(1, limit), 1000)
        return {"state_root": project["state_root"], "ports": records[begin:begin+count], "total": len(records), "offset": begin,
                "next_offset": begin+count if begin+count < len(records) else None}

    @app.get("/api/projects/{project_id}/opening-host")
    def opening_host(project_id: str, entity_id: str, revision: int | None = None, candidate_id: str | None = None):
        from .opening_inspection import inspect_selected_host
        project = service.selected_project(project_id, revision, candidate_id)
        return inspect_selected_host(service.store, project, entity_id)

    @app.get("/api/projects/{project_id}/candidates/{candidate_id}/assurance")
    def assurance(project_id: str, candidate_id: str):
        from .project_assurance import candidate_assurance
        candidate = service.store.candidate(candidate_id)
        if candidate["project_id"] != project_id:
            raise IntegrityError("Candidate belongs to another project")
        return candidate_assurance(service.store, candidate_id)

    @app.get("/api/projects/{project_id}/dependencies")
    def dependencies(project_id: str, revision: int | None = None, candidate_id: str | None = None):
        from .project_dependencies import derive_transition
        from .build_identity import checker_version
        project = service.selected_project(project_id, revision, candidate_id)
        selected = service.store.get(project["state_root"])
        report = None
        if candidate_id:
            candidate = service.store.candidate(candidate_id)
            prior = service.store.get(service.store.run(candidate["run_id"])["base_root"])
            report = service.store.get(candidate["report_root"]) if candidate.get("report_root") else None
        else:
            record = next(row for row in service.store.history(project_id) if row["revision"] == project["revision"])
            prior = service.store.get(record["parent_root"]) if record.get("parent_root") else selected
            if record.get("candidate_id"):
                candidate = service.store.candidate(record["candidate_id"])
                report = service.store.get(candidate["report_root"]) if candidate.get("report_root") else None
        return derive_transition(prior, selected, executable=checker_version(), after_report=report)

    @app.get("/api/projects/{project_id}/events")
    def events(project_id: str, after: int = 0, limit: int = 200):
        service.store.project(project_id)
        return service.store.events(project_id, after, limit)

    @app.get("/api/projects/{project_id}/stream")
    async def stream(project_id: str, request: Request, after: int = 0):
        service.store.project(project_id)
        try:
            cursor = max(after, int(request.headers.get("Last-Event-ID", "0")))
        except ValueError:
            raise HTTPException(422, "Last-Event-ID must be an integer")
        async def generate():
            nonlocal cursor
            while not await request.is_disconnected():
                batch = await asyncio.to_thread(service.store.events, project_id, cursor, 200)
                if batch:
                    for event in batch:
                        cursor = event["seq"]
                        yield f"id: {cursor}\ndata: {json.dumps(event, separators=(',', ':'))}\n\n"
                    await asyncio.sleep(.05)  # Backpressure and bounded UI batch rate.
                else:
                    yield ": heartbeat\n\n"
                    await asyncio.sleep(.5)
        return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.post("/api/projects/{project_id}/runs", status_code=202)
    def start_run(project_id: str, body: RunRequest):
        return service.start_run(project_id, body.model_dump(mode="json"))

    @app.get("/api/runs/{run_id}")
    def run(run_id: str):
        return service.store.run(run_id)

    @app.post("/api/runs/{run_id}/control")
    def control(run_id: str, body: ControlRequest):
        return service.store.control(run_id, body.action)

    @app.post("/api/projects/{project_id}/candidates/{candidate_id}/accept")
    def accept(project_id: str, candidate_id: str, body: CommitRequest):
        from .verification import CHECKER_VERSION
        return service.store.accept(project_id, candidate_id, body.expected_revision, body.idempotency_key, checker_version=CHECKER_VERSION)

    @app.post("/api/projects/{project_id}/candidates/{candidate_id}/recheck", status_code=202)
    def recheck(project_id: str, candidate_id: str, body: RecheckRequest):
        candidate = service.store.candidate(candidate_id)
        if candidate["project_id"] != project_id:
            raise ValueError("Candidate belongs to another project")
        return service.start_run(project_id, {"operation": "recheck", "candidate_id": candidate_id, **body.model_dump(mode="json")})

    @app.post("/api/projects/{project_id}/revert")
    def revert(project_id: str, body: RevertRequest):
        return service.store.revert(project_id, body.revision, body.expected_revision, body.idempotency_key)

    @app.post("/api/projects/{project_id}/export")
    def export(project_id: str, body: ExportRequest):
        from .exporting import export_project
        return export_project(service.store, project_id, body.candidate_id, body.draft, budget_seconds=body.budget_seconds)

    @app.get("/api/artifacts/{root}")
    def artifact(root: str):
        return service.store.get(root)

    from .uploads import register_upload
    register_upload(app, service)

    static = Path(__file__).resolve().parents[2] / "ui" / "dist"
    if static.exists():
        app.mount("/", StaticFiles(directory=static, html=True), name="workbench")
    else:
        @app.get("/")
        def not_built():
            return {"message": "Workbench build missing; run npm ci and npm run build in ui/", "api": "/docs"}
    return app
