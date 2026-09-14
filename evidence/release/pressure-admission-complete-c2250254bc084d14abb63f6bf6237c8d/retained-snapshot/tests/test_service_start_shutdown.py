"""Real Store lifecycle regressions for thread startup and concurrent shutdown."""
import threading
import time

import pytest

from oma.service import EngineService
from oma.store import Conflict


def queued_service(directory):
    service = EngineService(directory)
    project = service.store.create_project("Service startup/shutdown ordering",{})
    run = service.store.create_run(project["id"],{"operation":"recheck","candidate_id":"unused-no-child","budget_seconds":1})
    return service,project,run


def forbid_child_launch(monkeypatch):
    from oma import export_checks
    attempted = []
    def forbidden(*args,**kwargs):
        attempted.append((args,kwargs))
        raise AssertionError("No child may launch after service shutdown begins")
    monkeypatch.setattr(export_checks,"supervise_check",forbidden)
    return attempted


def test_concurrent_shutdown_waits_for_published_thread_start_then_cleans_up(tmp_path,monkeypatch):
    service,_,run = queued_service(tmp_path/"store")
    launched = forbid_child_launch(monkeypatch)
    announced,release = threading.Event(),threading.Event()
    original_start = threading.Thread.start
    errors = {}
    def delayed_start(thread):
        if thread.name == "oma-"+run["id"][:8]:
            announced.set()
            if not release.wait(5):
                raise AssertionError("Test did not release the startup boundary")
        return original_start(thread)
    monkeypatch.setattr(threading.Thread,"start",delayed_start)
    def scheduling():
        try:
            service.schedule(run["id"])
        except BaseException as exc:
            errors["schedule"] = exc
    def stopping():
        try:
            service.shutdown()
        except BaseException as exc:
            errors["shutdown"] = exc
    scheduler = threading.Thread(target=scheduling,name="concurrent-scheduling-request")
    shutdown = threading.Thread(target=stopping,name="concurrent-shutdown-request")
    scheduler.start()
    try:
        assert announced.wait(2)
        # The owned thread is deliberately still inside its startup boundary.
        # Shutdown must wait for the same lock instead of joining it unstarted.
        shutdown.start()
        deadline = time.monotonic()+2
        while not service.closing and time.monotonic()<deadline:
            time.sleep(.005)
        assert service.closing and shutdown.is_alive()
        assert "shutdown" not in errors
    finally:
        release.set()
        scheduler.join(6)
        if shutdown.ident is not None:
            shutdown.join(10)
        service.shutdown()
    assert not scheduler.is_alive() and not shutdown.is_alive() and not errors,errors
    assert not service.threads and not launched
    assert service.store.run(run["id"])["status"] == "CANCELLED"


def test_schedule_after_shutdown_cancels_queued_run_without_starting_thread_or_job(tmp_path,monkeypatch):
    service,project,run = queued_service(tmp_path/"store")
    service.shutdown()
    launched = forbid_child_launch(monkeypatch)
    starts = []
    original_start = threading.Thread.start
    def observed_start(thread):
        starts.append(thread.name)
        return original_start(thread)
    monkeypatch.setattr(threading.Thread,"start",observed_start)
    service.schedule(run["id"])
    assert not starts and not launched and not service.threads
    assert service.store.run(run["id"])["status"] == "CANCELLED"
    before = service.store.runs(project["id"])
    with pytest.raises(Conflict,match="shutting down"):
        service.start_run(project["id"],{"operation":"check","budget_seconds":1})
    assert service.store.runs(project["id"]) == before


def test_failed_thread_start_is_removed_and_persisted_without_poisoning_shutdown(tmp_path,monkeypatch):
    service,_,run = queued_service(tmp_path/"store")
    launched = forbid_child_launch(monkeypatch)
    failure = RuntimeError("Explicit native-thread allocation failure fixture")
    def failed_start(thread):
        raise failure
    monkeypatch.setattr(threading.Thread,"start",failed_start)
    with pytest.raises(RuntimeError) as raised:
        service.schedule(run["id"])
    assert raised.value is failure
    assert not service.threads and not launched
    assert service.store.run(run["id"])["status"] == "FAILED"
    service.shutdown()
    assert not service.threads
