"""Reproduce the service's thread publication/start shutdown race.

Only the exact Thread.start scheduling boundary is delayed. Store, shutdown,
thread joining and the service supervisor remain real. No worker is launched:
shutdown cancels the queued run before its supervisor gets the broker.
"""
from pathlib import Path
import json
import threading
import time
import uuid
from unittest.mock import patch

from oma.build_identity import checker_version
from oma.ifc.audit import atomic_json, sha256_file
from oma.service import EngineService


def main():
    directory = Path(__file__).resolve().parent/'service-race-attempts'/uuid.uuid4().hex
    service = EngineService(directory/'store')
    project = service.store.create_project('Isolated service startup race',{})
    run = service.store.create_run(project['id'],{'operation':'recheck','candidate_id':'unused','budget_seconds':1})
    announced, release = threading.Event(), threading.Event()
    original_start = threading.Thread.start
    observed = {}
    def delayed_start(thread):
        if thread.name == 'oma-'+run['id'][:8]:
            announced.set()
            if not release.wait(4):
                raise RuntimeError('Controlled startup boundary was not released')
        return original_start(thread)
    def schedule():
        try:
            service.schedule(run['id'])
        except BaseException as exc:
            observed['scheduler_error'] = f'{type(exc).__name__}: {exc}'
    with patch.object(threading.Thread,'start',delayed_start):
        scheduler = threading.Thread(target=schedule,name='external-request-thread')
        scheduler.start()
        assert announced.wait(2)
        try:
            service.shutdown()
            observed['shutdown_returned'] = True
        except BaseException as exc:
            observed['shutdown_error'] = f'{type(exc).__name__}: {exc}'
        finally:
            release.set()
            scheduler.join(5)
    expiry = time.monotonic()+5
    while service.threads and time.monotonic()<expiry:
        time.sleep(.02)
    observed.update(scope='THREAD LIFECYCLE ONLY; NO IFC OR PHYSICAL VERDICT',
        build=checker_version(), script_sha256=sha256_file(Path(__file__)),
        run=service.store.run(run['id']),remaining_service_threads=list(service.threads),
        race_reproduced='cannot join thread before it is started' in observed.get('shutdown_error',''),
        attempt=str(directory))
    atomic_json(directory/'observation.json',observed)
    print(json.dumps(observed))


if __name__=='__main__':
    main()
