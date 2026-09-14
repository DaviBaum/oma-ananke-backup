"""Actual process creation race; run with the recorded immutable PYTHONPATH.

The only control action releases the child after the supervisor has observed
its current descendants. No supervisor/process APIs are mocked. Every spawned
process exits naturally within about one second; it only writes local markers.
"""
from pathlib import Path
import json
import os
import sys
import time
import uuid

from oma.build_identity import checker_version
from oma.export_checks import supervise_check
from oma.ifc.audit import atomic_json, sha256_file


def main():
    directory = Path(__file__).resolve().parent/"attempts"/uuid.uuid4().hex
    directory.mkdir(parents=True)
    ready, go, late, identity = (directory/name for name in ("ready","go","late","identity.json"))
    child = ("import time,json,psutil; p=psutil.Process(); "
        + f"open({str(identity)!r},'w').write(json.dumps(dict(pid=p.pid,created=p.create_time()))); "
        + f"time.sleep(.8); open({str(late)!r},'w').write('descendant completed after its parent')")
    program = ("import pathlib,time,subprocess,sys,os; "
        + f"pathlib.Path({str(ready)!r}).write_text('ready'); go=pathlib.Path({str(go)!r}); "
        + "exec('while not go.exists(): time.sleep(.002)'); "
        + f"subprocess.Popen([sys.executable,'-c',{child!r}],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,"
        + "close_fds=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)); os._exit(0)")
    def control():
        if ready.exists():
            go.write_text("release immediately after current descendant observation")
        return False
    version = checker_version()
    result = supervise_check([sys.executable,"-c",program],
        environment={**os.environ,"OMA_EXECUTABLE_BUILD":version},directory=directory/"supervision",
        deadline=time.monotonic()+5,reserve_bytes=0,cancellation_requested=control)
    at_return = late.exists()
    time.sleep(1.1)
    summary = {"scope":"ACTUAL_PROCESS_CONTAINMENT_BOUNDARY_ONLY; NO PHYSICAL VERDICT",
        "executable_version":version,"script_sha256":sha256_file(Path(__file__)),
        "supervisor_status":result["status"],"supervisor_elapsed_seconds":result["elapsed_seconds"],
        "late_marker_at_return":at_return,"late_marker_after_return":late.exists(),
        "descendant_identity":json.loads(identity.read_text()) if identity.exists() else None,
        "completion_gap_reproduced":result["status"] == "COMPLETED" and not at_return and late.exists(),
        "attempt":str(directory),"all_children_intended_to_exit_naturally":True}
    atomic_json(directory/"observation.json",summary)
    atomic_json(Path(__file__).resolve().parent/"latest.json",summary)
    print(json.dumps(summary),flush=True)


if __name__ == "__main__":
    main()
