import threading
import time

from oma.store import Store
from oma.worker import Cancelled, WorkerControl


def wait_for(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.02)
    raise AssertionError("Worker did not acknowledge within timeout")


def test_repeated_step_consumed_once_across_independent_controls(tmp_path):
    store = Store(tmp_path)
    project = store.create_project("step", {})
    run = store.create_run(project["id"], {"operation": "route"})
    store.update_run(run["id"], "RUNNING")
    store.control(run["id"], "pause")
    reached = []
    cancelled = []
    def work():
        try:
            for i in range(4):
                # New controller models a fresh independent child at every stage.
                WorkerControl(store, run["id"]).checkpoint(f"stage{i}")
                reached.append(i)
        except Cancelled:
            cancelled.append(True)
    thread = threading.Thread(target=work)
    thread.start()
    wait_for(lambda: store.run(run["id"])["status"] == "PAUSED")
    store.control(run["id"], "step")
    wait_for(lambda: reached == [0] and store.run(run["id"])["status"] == "PAUSED")
    store.control(run["id"], "step")
    wait_for(lambda: reached == [0, 1] and store.run(run["id"])["status"] == "PAUSED")
    store.control(run["id"], "cancel")
    thread.join(3)
    assert not thread.is_alive()
    assert cancelled == [True]
    assert reached == [0, 1]
