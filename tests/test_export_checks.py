"""Failure injection at real process boundaries, plus immutable export artifacts."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import psutil
import pytest

from oma.export_checks import ExportChecks, LOG_LIMIT_BYTES, supervise_check


def test_child_timeout_retains_bounded_logs_and_terminates_only_its_tree(tmp_path):
    marker = tmp_path / "descendant.pid"
    program = ("import subprocess,sys,time; "
        "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
        f"open({str(marker)!r},'w').write(str(p.pid)); "
        f"sys.stdout.write('x'*{LOG_LIMIT_BYTES + 1000}); sys.stdout.flush(); "
        "sys.stderr.write('native check started\\n'); sys.stderr.flush(); time.sleep(60)")
    unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        result = supervise_check([sys.executable, "-c", program],
            environment={**os.environ, "OMA_EXECUTABLE_BUILD": "test-process-contract"},
            directory=tmp_path / "check", deadline=time.monotonic() + 2, reserve_bytes=0)
        assert result["status"] == "UNKNOWN_TIMEOUT", result
        assert result["elapsed_seconds"] < 8
        assert result["stdout"]["truncated"]
        assert result["stdout"]["total_bytes"] == LOG_LIMIT_BYTES + 1000
        assert Path(result["stdout"]["path"]).stat().st_size == LOG_LIMIT_BYTES
        assert "native check started" in Path(result["stderr"]["path"]).read_text()
        assert marker.exists()
        assert not psutil.pid_exists(int(marker.read_text()))
        assert not result["termination"]["remaining_pids"]
        assert unrelated.poll() is None
        assert json.loads((tmp_path / "check/check.json").read_text())["status"] == "UNKNOWN_TIMEOUT"
    finally:
        unrelated.kill()
        unrelated.wait(timeout=3)


def test_child_resource_limit_is_an_unknown_not_a_failed_geometry_claim(tmp_path):
    result = supervise_check([sys.executable, "-c", "import time; data=bytearray(16000000); time.sleep(30)"],
        environment={**os.environ, "OMA_EXECUTABLE_BUILD": "test-process-contract"}, directory=tmp_path,
        deadline=time.monotonic() + 10, memory_limit_bytes=1024 * 1024, reserve_bytes=0)
    assert result["status"] == "UNKNOWN_RESOURCE_LIMIT", result
    assert result["peak_tree_rss_bytes"] > result["memory_limit_bytes"]
    assert not result["termination"]["remaining_pids"]


@pytest.mark.parametrize("child_seconds,outcome", [(.6,"COMPLETED"),(60,"UNKNOWN_PROCESS_TREE")])
def test_parent_exit_allows_only_bounded_descendant_shutdown(tmp_path,child_seconds,outcome):
    marker = tmp_path / "child.pid"
    program = ("import subprocess,sys,time; "
        f"p=subprocess.Popen([sys.executable,'-c','import time; time.sleep({child_seconds})']); "
        f"open({str(marker)!r},'w').write(str(p.pid)); time.sleep(.3)")
    result = supervise_check([sys.executable,"-c",program],
        environment={**os.environ,"OMA_EXECUTABLE_BUILD":"test-shutdown-grace"},
        directory=tmp_path/"check",deadline=time.monotonic()+5,reserve_bytes=0)
    assert result["status"] == outcome, result
    assert result["elapsed_seconds"] < 4
    assert not psutil.pid_exists(int(marker.read_text()))
    if outcome == "COMPLETED":
        assert "termination" not in result
    else:
        assert not result["termination"]["remaining_pids"]


def test_multiple_child_checks_share_one_deadline(tmp_path):
    from oma.store import Store
    manifest = {"status": "DRAFT", "limitations": [], "files": []}
    checks = ExportChecks(Store(tmp_path / "store"), tmp_path / "export", manifest, budget_seconds=2)
    first = checks.run("timeit", ["--number", "1", "--repeat", "1", "import time; time.sleep(.6)"], "first")
    second = checks.run("timeit", ["--number", "1", "--repeat", "1", "import time; time.sleep(10)"], "second")
    assert first["status"] == "COMPLETED", first
    assert second["status"] == "UNKNOWN_TIMEOUT", second
    assert second["elapsed_seconds"] < 2
    assert {c["checker_version"] for c in manifest["checking"]["checks"]} == {checks.version}
    retained = json.loads((tmp_path / "export/manifest.json").read_text())
    assert retained["status"] == "DRAFT" and retained["checking"]["status"] == "UNKNOWN_TIMEOUT"


def test_checked_export_timeout_preserves_the_actual_draft_and_original_bytes(tmp_path, monkeypatch):
    from oma.exporting import export_project
    from oma.routing.engine import route_project_run
    from oma.store import IntegrityError, Store
    from oma.worker import WorkerControl, import_sources
    from test_ifc_pipeline import make_fixture

    source = make_fixture(tmp_path / "source.ifc")
    original = source.read_bytes()
    store = Store(tmp_path / "store")
    project = store.create_project("Export timeout", {})
    imported = store.create_run(project["id"], {"operation": "import", "paths": [str(source)]})
    import_sources(store, imported, WorkerControl(store, imported["id"]))
    scenario = {"start": [-1., -1., 1.], "end": [3., -1., 1.], "system_type": "PRESSURE_PIPE",
        "diameter_m": .1, "insulation_m": .02, "bend_radius_m": .3, "minimum_straight_m": .05,
        "clearance_m": .1, "allowed_zone": {"min": [-2., -2., -2.], "max": [4., 4., 4.]},
        "scenario_terminals": True, "max_candidates": 1}
    run = store.create_run(project["id"], {"operation": "route", "mission": scenario, "budget_seconds": 90})
    route_project_run(store, run, WorkerControl(store, run["id"]))
    candidate = store.candidates(project["id"])[0]
    assert candidate["status"] == "CHECKED", store.get(candidate["report_root"])
    head = store.project(project["id"])
    original_run = ExportChecks.run

    def delayed_real_checker(self, module, arguments, stage):
        if module != "oma.verification":
            return original_run(self, module, arguments, stage)
        # The IFC round trip is real. The full-check subprocess stalls before
        # producing evidence, reproducing a native-kernel timeout at its boundary.
        self.deadline = time.monotonic() + .3
        return original_run(self, "timeit", ["--number", "1", "import time; time.sleep(30)"], stage)

    monkeypatch.setattr(ExportChecks, "run", delayed_real_checker)
    with pytest.raises(IntegrityError, match="draft evidence preserved"):
        export_project(store, project["id"], candidate["id"], draft=False, budget_seconds=30)
    directories = list((store.directory / "exports").iterdir())
    assert len(directories) == 1
    directory = directories[0]
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["status"] == "DRAFT"
    assert manifest["round_trip"] == "UNKNOWN_TIMEOUT"
    assert [c["status"] for c in manifest["checking"]["checks"]] == ["COMPLETED", "UNKNOWN_TIMEOUT"]
    assert not manifest.get("verification_root")
    assert manifest["checking"]["candidate_status"] != "CHECKED"
    assert (directory / "state.json").is_file() and (directory / "events.json").is_file()
    assert Path(manifest["files"][0]["path"]).is_file()
    assert source.read_bytes() == original and store.project(project["id"]) == head
    event = next(e for e in reversed(store.events(project["id"])) if e["stage"] == "export")
    assert event["status"] == "DRAFT" and store.get(event["artifacts"][0]) == manifest


@pytest.mark.parametrize("field", ["candidate_root", "checker_version", "mission_hash", "rule_hash", "objective", "scope", "check_set", "exported_bytes"])
def test_release_gate_rejects_stale_or_narrowed_passing_report(tmp_path, monkeypatch, field):
    from oma.build_identity import checker_version
    from oma.store import Store, digest
    from oma.ifc.audit import sha256_file

    store = Store(tmp_path / "store")
    state = {"mission": {"rule_hash": "rules"}}
    root = store.put(state)
    report = {"schema_version": 1, "candidate_root": root, "checker_version": checker_version(),
        "mission_hash": digest(state["mission"]), "rule_hash": "rules", "status": "PASS", "scope": "All original obstacles",
        "objective": {"length_m": 4.}, "results": [{"id": "all-obstacles", "status": "PASS", "reason": "checked", "scope": "all", "participants": [], "witness": {}}],
        "common_mode_risks": [], "created_at": "2026-09-14T00:00:00Z"}
    original = copy.deepcopy(report)
    report["results"].append({**report["results"][0], "id": "export-federation-correspondence"})
    file = tmp_path / "export.ifc"
    file.write_text("immutable IFC export", encoding="utf-8")
    file_hash = sha256_file(file)
    if field == "check_set":
        report["results"][0]["id"] = "one-convenient-obstacle"
    elif field == "objective":
        report[field] = {"length_m": 3.}
    elif field == "exported_bytes":
        file.write_text("changed after the check", encoding="utf-8")
    else:
        report[field] = "different"
    candidate = {"id": "copy", "state_root": root, "status": "CHECKED", "report_root": store.put(report)}
    monkeypatch.setattr(store, "candidate", lambda _id: candidate)
    manifest = {"status": "DRAFT", "limitations": [], "round_trip": "PASS", "files": [{"path": str(file), "sha256": file_hash}]}
    checks = ExportChecks(store, tmp_path / "export", manifest)
    monkeypatch.setattr(checks, "run", lambda *args: {"status": "COMPLETED"})
    checks.verify(candidate, original)
    assert manifest["status"] == "DRAFT"
    assert manifest["round_trip"] == "FAIL_EVIDENCE_BINDING"
    assert not manifest["checking"]["release_bindings"][field]


def test_export_budget_api_and_cli_are_bounded_and_forwarded(tmp_path, monkeypatch):
    from oma.api import ExportRequest, create_app
    from oma.cli import app
    from oma.export_checks import export_budget
    from pydantic import ValidationError
    from typer.testing import CliRunner
    from fastapi.testclient import TestClient
    import oma.exporting

    assert ExportRequest().budget_seconds == 3600
    for value in (0, 7201, float("nan"), float("inf")):
        with pytest.raises(ValidationError):
            ExportRequest(budget_seconds=value)
        with pytest.raises(ValueError):
            export_budget(value)
    received = []
    monkeypatch.setattr(oma.exporting, "export_project", lambda *args, **kwargs: received.append(kwargs) or {"status": "DRAFT"})
    result = CliRunner().invoke(app, ["export", "example", "--data-dir", str(tmp_path), "--budget-seconds", "6500"])
    assert result.exit_code == 0, result.output
    assert received == [{"budget_seconds": 6500.}]
    with TestClient(create_app(tmp_path / "api")) as client:
        response = client.post("/api/projects/example/export", json={"budget_seconds": 7200})
        assert response.status_code == 200, response.text
        assert received[-1] == {"budget_seconds": 7200.}
        assert client.post("/api/projects/example/export", json={"budget_seconds": 7201}).status_code == 422
