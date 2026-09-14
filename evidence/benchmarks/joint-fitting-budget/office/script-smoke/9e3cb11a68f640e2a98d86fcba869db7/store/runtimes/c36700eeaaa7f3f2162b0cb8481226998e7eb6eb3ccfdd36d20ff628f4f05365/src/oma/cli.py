from __future__ import annotations

import json
from pathlib import Path

import typer

from .hardware import diagnose
from .store import Store

app = typer.Typer(no_args_is_help=True, help="OMA + ANANKE local engineering workbench")


def output(value):
    typer.echo(json.dumps(value, indent=2, ensure_ascii=False))


@app.command()
def doctor(save: Path | None = None):
    """Measure hardware, dependency versions and resource budgets."""
    report = diagnose(refresh=True)
    if save:
        save.parent.mkdir(parents=True, exist_ok=True)
        save.write_text(json.dumps(report, indent=2), encoding="utf-8")
    output(report)


@app.command()
def serve(port: int = 8765, data_dir: Path = Path(".oma")):
    """Start the local API and built workbench on loopback."""
    import uvicorn
    from .api import create_app
    uvicorn.run(create_app(data_dir), host="127.0.0.1", port=port, log_level="info", access_log=False)


@app.command("import")
def import_model(paths: list[Path], name: str = "IFC federation", data_dir: Path = Path(".oma")):
    """Import IFC files in a fresh worker and persist complete source audits."""
    import time
    from .service import EngineService
    service = EngineService(data_dir)
    project = service.import_project([str(p) for p in paths], name)
    run_id = project["import_run_id"]
    try:
        while service.store.run(run_id)["status"] in {"QUEUED", "RUNNING", "PAUSED"}:
            time.sleep(.5)
        output({"project": service.store.project(project["id"]), "run": service.store.run(run_id)})
        if service.store.run(run_id)["status"] != "COMPLETED":
            raise typer.Exit(1)
    finally:
        service.shutdown()


@app.command()
def projects(data_dir: Path = Path(".oma")):
    """List local immutable project heads."""
    output(Store(data_dir).projects())


@app.command()
def replay(project_id: str, after: int = 0, data_dir: Path = Path(".oma")):
    """Replay persisted events in strict sequence order."""
    store = Store(data_dir)
    while batch := store.events(project_id, after, 1000):
        for event in batch:
            typer.echo(json.dumps(event, ensure_ascii=False))
        after = batch[-1]["seq"]


@app.command()
def backup(destination: Path, data_dir: Path = Path(".oma")):
    """Create a consistent database and immutable artifact backup."""
    output({"backup": str(Store(data_dir).backup(destination))})


@app.command()
def restore(backup_directory: Path, destination: Path):
    """Verify and restore all project bytes into a new local store."""
    from .backup import restore_store
    restored = restore_store(backup_directory, destination)
    output({"status": "RESTORED", "directory": str(restored.directory), "projects": restored.projects()})


@app.command()
def recover(data_dir: Path = Path(".oma")):
    """Mark interrupted jobs crashed without accepting their candidates."""
    output({"recovered_run_ids": Store(data_dir).recover()})


def run_job(project_id, operation, mission, budget_seconds, seed, data_dir):
    import time
    from .service import EngineService
    service = EngineService(data_dir)
    request = {"operation": operation, "mission": mission, "budget_seconds": budget_seconds, "seed": seed}
    run = service.start_run(project_id, request)
    cursor = 0
    try:
        while True:
            current = service.store.run(run["id"])
            events = service.store.events(project_id, cursor, 1000)
            for event in events:
                cursor = event["seq"]
                if event.get("run_id") == run["id"]:
                    typer.echo(json.dumps(event, ensure_ascii=False))
            if current["status"] not in {"QUEUED", "RUNNING", "CHECKING", "PAUSED"}:
                output({"run": current, "candidates": [c for c in service.store.candidates(project_id) if c["run_id"] == run["id"]]})
                if current["status"] != "COMPLETED":
                    raise typer.Exit(2)
                return
            time.sleep(.3)
    finally:
        service.shutdown()


@app.command()
def check(project_id: str, budget_seconds: float = 300, data_dir: Path = Path(".oma")):
    """Independently check persisted baseline IFC geometry in a fresh process."""
    run_job(project_id, "check", None, budget_seconds, 0, data_dir)


@app.command()
def normalize(project_id: str, budget_seconds: float = 300, data_dir: Path = Path(".oma")):
    """Preserve explicit source ports and ownership in a new semantic baseline."""
    run_job(project_id, "normalize", None, budget_seconds, 0, data_dir)


@app.command()
def route(project_id: str, mission: Path, budget_seconds: float = 300, seed: int = 0, data_dir: Path = Path(".oma")):
    """Generate, materialize and independently check an explicit physical route mission."""
    run_job(project_id, "route", json.loads(mission.read_text(encoding="utf-8")), budget_seconds, seed, data_dir)


@app.command()
def optimize(project_id: str, mission: Path, budget_seconds: float = 300, seed: int = 0, data_dir: Path = Path(".oma")):
    """Run the currently implemented finite checked-route optimization scope."""
    run_job(project_id, "optimize", json.loads(mission.read_text(encoding="utf-8")), budget_seconds, seed, data_dir)


@app.command()
def verify(candidate_id: str, data_dir: Path = Path(".oma")):
    """Reload persisted candidate in a fresh independent checker process."""
    import subprocess
    import sys
    result = subprocess.run([sys.executable, "-m", "oma.verification", str(data_dir.resolve()), candidate_id],
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    raise typer.Exit(result.returncode)


@app.command()
def accept(candidate_id: str, expected_revision: int, data_dir: Path = Path(".oma"), idempotency_key: str | None = None):
    """Accept a root-checked candidate with optimistic concurrency control."""
    import uuid
    from .verification import CHECKER_VERSION
    store = Store(data_dir)
    candidate = store.candidate(candidate_id)
    output(store.accept(candidate["project_id"], candidate_id, expected_revision, idempotency_key or uuid.uuid4().hex, checker_version=CHECKER_VERSION))


@app.command("export")
def export_command(project_id: str, candidate_id: str | None = None, draft: bool = True, data_dir: Path = Path(".oma"), budget_seconds: float = 3600):
    """Write immutable IFC export bundle and explicit checking disposition."""
    from .exporting import export_project
    output(export_project(Store(data_dir), project_id, candidate_id, draft, budget_seconds=budget_seconds))


@app.command()
def revert(project_id: str, revision: int, expected_revision: int, data_dir: Path = Path(".oma")):
    """Restore a historical root as a new baseline revision without reusing stale claims."""
    import uuid
    output(Store(data_dir).revert(project_id, revision, expected_revision, uuid.uuid4().hex))


if __name__ == "__main__":
    app()
