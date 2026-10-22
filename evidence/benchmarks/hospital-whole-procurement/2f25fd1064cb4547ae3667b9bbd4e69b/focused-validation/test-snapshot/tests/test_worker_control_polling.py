"""Hot math polling saves I/O without lending authority to cached control state."""
import queue
import threading
import time

import pytest

from oma.store import Store
from oma.worker import Cancelled, WorkerControl


def _running(directory):
    store = Store(directory)
    project = store.create_project("Bounded search control polling", {})
    run = store.create_run(project["id"], {"operation": "optimize", "budget_seconds": 60})
    store.update_run(run["id"], "RUNNING")
    return store, run, WorkerControl(store, run["id"])


def test_actual_sqlite_cancel_is_observed_with_bounded_hot_loop_latency(tmp_path):
    store, run, control = _running(tmp_path / "store")
    control.search_checkpoint("initial_search")
    store.control(run["id"], "cancel")
    started = time.monotonic()
    with pytest.raises(Cancelled):
        while time.monotonic() - started < 1.:
            control.search_checkpoint("hot_search")
    #25ms is the cache window; leave explicit room for Windows scheduling and
    #the SQLite read itself, which a Python callback cannot bound in isolation.
    assert time.monotonic() - started < .25


def test_forced_publication_check_bypasses_a_fresh_running_search_cache(tmp_path):
    store, run, control = _running(tmp_path / "store")
    control.search_checkpoint("search")
    store.control(run["id"], "cancel")
    with pytest.raises(Cancelled):
        control.checkpoint("publication")
    with pytest.raises(Cancelled):
        control.search_checkpoint("after_rejected_publication")


def test_step_tokens_allow_exactly_one_checkpoint_each_and_are_never_cached(tmp_path):
    store, run, control = _running(tmp_path / "store")
    store.control(run["id"], "step")
    passed = queue.Queue()
    errors = []
    def search():
        try:
            for index in range(3):
                control.search_checkpoint("one_math_transition")
                passed.put(index)
        except Cancelled:
            pass
        except BaseException as exc:
            errors.append(exc)
    thread = threading.Thread(target=search)
    thread.start()
    try:
        assert passed.get(timeout=2) == 0
        with pytest.raises(queue.Empty):
            passed.get(timeout=.15)
        with store.connect() as db:
            first = dict(db.execute("SELECT sequence,consumed FROM run_controls WHERE run_id=?", (run["id"],)).fetchone())
        assert first == {"sequence": 1, "consumed": 1}
        assert store.run(run["id"])["status"] == "PAUSED"
        store.control(run["id"], "step")
        assert passed.get(timeout=2) == 1
        with pytest.raises(queue.Empty):
            passed.get(timeout=.15)
        with store.connect() as db:
            second = dict(db.execute("SELECT sequence,consumed FROM run_controls WHERE run_id=?", (run["id"],)).fetchone())
        assert second == {"sequence": 2, "consumed": 2}
    finally:
        store.control(run["id"], "cancel")
        thread.join(timeout=2)
    assert not thread.is_alive() and not errors and passed.empty()


def test_pause_observation_stops_work_until_actual_resume(tmp_path):
    store, run, control = _running(tmp_path / "store")
    control.search_checkpoint("initial_search")
    store.control(run["id"], "pause")
    progressed, errors = [], []
    def search():
        try:
            while True:
                control.search_checkpoint("bounded_math_work")
                progressed.append(time.monotonic())
                time.sleep(.001)
        except Cancelled:
            pass
        except BaseException as exc:
            errors.append(exc)
    thread = threading.Thread(target=search)
    thread.start()
    try:
        deadline = time.monotonic() + 2
        while store.run(run["id"])["status"] != "PAUSED" and time.monotonic() < deadline:
            time.sleep(.005)
        assert store.run(run["id"])["status"] == "PAUSED"
        before = len(progressed)
        time.sleep(.15)
        assert len(progressed) == before
        store.control(run["id"], "resume")
        deadline = time.monotonic() + 2
        while len(progressed) == before and time.monotonic() < deadline:
            time.sleep(.005)
        assert len(progressed) > before
    finally:
        store.control(run["id"], "cancel")
        thread.join(timeout=2)
    assert not thread.is_alive() and not errors


def test_slow_control_read_cannot_extend_the_lifetime_of_a_stale_running_observation(tmp_path, monkeypatch):
    store, run, control = _running(tmp_path / "store")
    original = store.run
    calls = []
    def delayed(identity):
        result = original(identity)
        calls.append(identity)
        if len(calls) == 1:
            with store.transaction() as db:
                db.execute("UPDATE runs SET desired_action='cancel' WHERE id=?", (identity,))
            time.sleep(.04)
        return result
    monkeypatch.setattr(store, "run", delayed)
    control.search_checkpoint("slow_read")
    with pytest.raises(Cancelled):
        control.search_checkpoint("first_work_after_slow_read")
    assert len(calls) == 2


@pytest.mark.parametrize("status", ["COMPLETED", "NO_INCUMBENT_FOUND", "BUDGET_EXHAUSTED"])
def test_forced_terminal_observation_invalidates_running_cache_without_changing_legacy_semantics(tmp_path, monkeypatch, status):
    store, run, control = _running(tmp_path / "store")
    control.search_checkpoint("ordinary_search")
    store.update_run(run["id"], status)
    original, calls = store.run, []
    def counted(identity):
        calls.append(identity)
        return original(identity)
    monkeypatch.setattr(store, "run", counted)
    control.checkpoint("forced_terminal_observation")
    control.search_checkpoint("terminal_search_one")
    control.search_checkpoint("terminal_search_two")
    assert len(calls) == 3


def test_failed_forced_read_removes_earlier_search_permission(tmp_path, monkeypatch):
    store, _, control = _running(tmp_path / "store")
    control.search_checkpoint()
    failure = OSError("control database unavailable")
    def failed(identity):
        raise failure
    monkeypatch.setattr(store, "run", failed)
    for callback in (control.checkpoint, control.search_checkpoint):
        with pytest.raises(OSError) as raised:
            callback("control_unavailable")
        assert raised.value is failure


def test_exact_frontier_proof_and_work_are_identical_with_far_fewer_real_sqlite_polls(tmp_path, monkeypatch):
    from oma.ifc.audit import atomic_json
    from oma.optimization.fabrication_frontier import compile_fabrication_frontier, verify_fabrication_frontier
    from test_optimization_fabrication_search import problem
    from test_optimization_fabrication_pricing import objective
    store, _, control = _running(tmp_path / "store")
    original, calls = store.run, []
    def counted(identity):
        calls.append(identity)
        return original(identity)
    monkeypatch.setattr(store, "run", counted)
    runs = []
    for name, callback in (("forced", control.checkpoint), ("coalesced", control.search_checkpoint)):
        calls.clear()
        started = time.monotonic()
        proof = compile_fabrication_frontier(problem(), objective(), 2, checkpoint=callback)
        check = verify_fabrication_frontier(problem(), objective(), 2, proof, checkpoint=callback)
        assert proof["status"] == "CERTIFIED" and check["status"] == "PASS"
        runs.append({"method": name, "proof": proof, "check": check, "queries": len(calls), "seconds": time.monotonic() - started})
    assert runs[0]["proof"] == runs[1]["proof"]
    assert runs[0]["check"] == runs[1]["check"]
    assert runs[0]["queries"] > 100 and runs[1]["queries"] < runs[0]["queries"] / 4
    atomic_json(tmp_path / "exact-frontier-control-polling.json", runs)
