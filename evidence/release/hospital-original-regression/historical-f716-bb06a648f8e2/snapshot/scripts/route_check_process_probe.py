"""Read-only-runtime reproduction of Windows subprocess timeout descendants.

All helpers are hidden and finite. Cleanup signals only psutil objects first
observed in this invocation's descendant tree, with their creation identities.
No API, project, imported IFC or active runtime is changed.
"""
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

import psutil


def probe(*, nested):
    directory = Path("evidence/release/route-check-execution") / uuid.uuid4().hex
    directory.mkdir(parents=True)
    identity, publication = directory.resolve()/"helper.json", directory.resolve()/"late-publication.json"
    leaf = ("import json,time,psutil; p=psutil.Process(); "
        f"open({str(identity)!r},'w').write(json.dumps(dict(pid=p.pid,ppid=p.ppid(),created=p.create_time(),executable=p.exe()))); "
        f"time.sleep(2); open({str(publication)!r},'w').write(json.dumps(dict(status='PASS',at=time.time())))")
    program = ("import subprocess,sys,time; "
        f"subprocess.Popen([sys.executable,'-c',{leaf!r}],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)); "
        "time.sleep(3)") if nested else leaf
    observed, stop = {}, threading.Event()
    parent = psutil.Process()

    def observe():
        while not stop.wait(.005):
            for process in parent.children(recursive=True):
                try:
                    observed[(process.pid,process.create_time())] = process
                except psutil.NoSuchProcess:
                    pass

    watcher = threading.Thread(target=observe,daemon=True)
    watcher.start()
    start = time.monotonic()
    result = {"interpreter": sys.executable, "nested_hidden_child": nested,
        "timeout_seconds": .6, "finite_leaf_sleep_seconds": 2, "samples": []}
    try:
        try:
            subprocess.run([sys.executable,"-c",program],capture_output=True,text=True,
                timeout=.6,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            result["status"] = "RETURNED"
        except subprocess.TimeoutExpired:
            result["status"] = "TIMEOUT_EXPIRED"
        result["elapsed_at_return"] = time.monotonic()-start
        for _ in range(10):
            result["samples"].append({"elapsed":time.monotonic()-start,
                "alive":[{"pid":key[0],"created":key[1]} for key,p in observed.copy().items() if p.is_running()],
                "published":publication.exists()})
            time.sleep(.3)
        result["helper"] = json.loads(identity.read_text()) if identity.exists() else None
        result["late_publication"] = json.loads(publication.read_text()) if publication.exists() else None
    finally:
        stop.set(); watcher.join(1)
        signalled = []
        for key, process in reversed(list(observed.items())):
            try:
                if process.is_running() and process.create_time() == key[1]:
                    process.kill(); signalled.append(process.pid)
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(list(observed.values()),timeout=2)
        result["cleanup"] = {"identity_verified_signalled_pids":signalled,"remaining_pids":[p.pid for p in alive]}
        (directory/"result.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    return {"directory":str(directory),"status":result["status"],"late_publication":result["late_publication"]}


if __name__ == "__main__":
    print(json.dumps([probe(nested=False),probe(nested=True)],indent=2))
