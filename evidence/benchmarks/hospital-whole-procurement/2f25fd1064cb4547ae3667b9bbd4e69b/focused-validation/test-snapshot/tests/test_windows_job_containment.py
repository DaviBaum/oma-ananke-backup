"""Actual Win32 containment, including the Microsoft Store venv launch path."""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

import psutil
import pytest

from oma import export_checks, windows_job


def run(tmp_path, program, **kwargs):
    return export_checks.supervise_check([sys.executable,"-c",program],
        environment={**os.environ,"OMA_EXECUTABLE_BUILD":"job-containment-test"},
        directory=tmp_path,deadline=time.monotonic()+kwargs.pop("seconds",6),reserve_bytes=0,**kwargs)


def test_real_recursive_python_membership_and_native_runtime_identity(tmp_path):
    from oma.build_identity import checker_version, frozen_environment
    import ifcopenshell
    env = frozen_environment(tmp_path/"snapshot")
    output = tmp_path/"identity.json"
    program = ("import json,os,sys,ifcopenshell,OCP,sqlite3,ssl,unicodedata; from oma.build_identity import checker_version; "
        + f"open({str(output)!r},'w').write(json.dumps(dict(pid=os.getpid(),prefix=sys.prefix,exe=sys.executable,"
        + "ifc=ifcopenshell.__file__,version=checker_version())))")
    result = export_checks.supervise_check([sys.executable,"-c",program],environment=env,
        directory=tmp_path/"check",deadline=time.monotonic()+15,reserve_bytes=0)
    assert result["status"] == "COMPLETED",result
    identity = json.loads(output.read_text())
    assert identity["pid"] == result["pid"]  # Actual Python, not a broker/launcher acknowledgement.
    assert Path(identity["ifc"]).resolve() == Path(ifcopenshell.__file__).resolve()
    assert identity["version"] == env["OMA_EXECUTABLE_BUILD"] == checker_version()
    assert Path(identity["exe"]).resolve() == Path(result["launched_command"][0]).resolve()
    assert result["containment"]["assigned_before_resume"]
    assert result["containment"]["active_processes"] == 0


@pytest.mark.parametrize("delay,expected",[(.35,"COMPLETED"),(20.,"UNKNOWN_PROCESS_TREE")])
def test_quick_parent_detached_grandchild_cannot_hide_from_kernel(tmp_path,delay,expected):
    ready,go,marker = (tmp_path/name for name in ("ready","go","late"))
    child = f"import time; time.sleep({delay}); open({str(marker)!r},'w').write('done')"
    program = ("import pathlib,subprocess,sys,time,os; "
        + f"pathlib.Path({str(ready)!r}).write_text('ready'); go=pathlib.Path({str(go)!r}); "
        + "exec('while not go.exists(): time.sleep(.002)'); "
        + f"subprocess.Popen([sys.executable,'-c',{child!r}],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,"
        + "close_fds=True,creationflags=subprocess.CREATE_NO_WINDOW); os._exit(0)")
    def release():
        if ready.exists(): go.write_text("go")
        return False
    result = run(tmp_path/"check",program,cancellation_requested=release)
    assert result["status"] == expected,result
    assert result["containment"]["total_processes"] >= 2
    if expected == "COMPLETED":
        assert marker.exists()
        assert result["containment"]["active_processes"] == 0
    else:
        assert not marker.exists()
        assert result["termination"]["active_processes_after"] == 0


def test_explicit_breakaway_attempt_is_denied(tmp_path):
    marker,outcome = tmp_path/"escaped",tmp_path/"outcome.json"
    child = f"open({str(marker)!r},'w').write('escaped')"
    program = ("import subprocess,sys,json\ntry:\n"
        + f" p=subprocess.Popen([sys.executable,'-c', {child!r}],creationflags=subprocess.CREATE_BREAKAWAY_FROM_JOB|subprocess.CREATE_NO_WINDOW)\n"
        + " p.wait()\n result='escaped'\nexcept OSError as e:\n result=e.winerror\n"
        + f"open({str(outcome)!r},'w').write(json.dumps(result))")
    result = run(tmp_path/"check",program)
    assert result["status"] == "COMPLETED",result
    assert json.loads(outcome.read_text()) == 5
    assert not marker.exists()


@pytest.mark.parametrize("failure",["AssignProcessToJobObject","QueryInformationJobObject","ResumeThread"])
def test_preexecution_failure_never_runs_python(tmp_path,monkeypatch,failure):
    marker = tmp_path/"ran"
    command,env,_ = windows_job.prepare_python_command([sys.executable,"-c",f"open({str(marker)!r},'w').write('ran')"],dict(os.environ))
    real = windows_job._kernel
    captures = {"resume_calls":0,"pid":None}
    class FaultAPI:
        def __init__(self): self.api=real()
        def __getattr__(self,name):
            native=getattr(self.api,name)
            if name=="CreateProcessW":
                def create(*args):
                    ok=native(*args)
                    if ok: captures["pid"]=ctypes.cast(args[-1],ctypes.POINTER(windows_job._PROCESS_INFORMATION)).contents.dwProcessId
                    return ok
                return create
            if name=="ResumeThread":
                def resume(*args):
                    captures["resume_calls"]+=1
                    return 0xFFFFFFFF if failure==name else native(*args)
                return resume
            if name==failure:
                def failed(*args):
                    ctypes.set_last_error(5)
                    return 0
                return failed
            return native
    monkeypatch.setattr(windows_job,"_kernel",FaultAPI)
    with pytest.raises(windows_job.ContainmentError):
        windows_job.WindowsJobProcess(command,environment=env)
    assert captures["pid"]
    assert captures["resume_calls"] == (1 if failure=="ResumeThread" else 0)
    assert not psutil.pid_exists(captures["pid"])
    assert not marker.exists()


def test_postresume_query_failure_never_becomes_completed(tmp_path,monkeypatch):
    original = windows_job.WindowsJobProcess.accounting
    def fail_after_resume(self):
        if self.resumed: raise windows_job.ContainmentError("injected kernel accounting failure")
        return original(self)
    monkeypatch.setattr(windows_job.WindowsJobProcess,"accounting",fail_after_resume)
    result = run(tmp_path,"import time; time.sleep(20)")
    assert result["status"] == "UNKNOWN_CONTAINMENT_ERROR",result
    assert not psutil.pid_exists(result["pid"])
    assert result["elapsed_seconds"] < 6


def test_job_handle_close_kills_known_and_unobserved_members(tmp_path):
    ready = tmp_path/"ready"
    child = "import time; time.sleep(20)"
    program = ("import subprocess,sys,time; "
        + f"p=subprocess.Popen([sys.executable,'-c',{child!r}],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
        + f"open({str(ready)!r},'w').write(str(p.pid)); time.sleep(20)")
    command,env,_=windows_job.prepare_python_command([sys.executable,"-c",program],dict(os.environ))
    process=windows_job.WindowsJobProcess(command,environment=env)
    try:
        end=time.monotonic()+4
        while not ready.exists() and time.monotonic()<end: time.sleep(.02)
        assert ready.exists()
        descendants=process.process_ids()
        assert int(ready.read_text()) in descendants
    finally:
        process.close()
    end=time.monotonic()+2
    while any(psutil.pid_exists(pid) for pid in descendants) and time.monotonic()<end: time.sleep(.01)
    assert not any(psutil.pid_exists(pid) for pid in descendants)


def test_nonwindows_is_explicitly_unsupported_without_launch(tmp_path,monkeypatch):
    monkeypatch.setattr(export_checks,"os",SimpleNamespace(name="posix"))
    monkeypatch.setattr(export_checks,"prepare_python_command",lambda *a:pytest.fail("must not launch"))
    result=run(tmp_path,"raise RuntimeError('must not run')")
    assert result["status"] == "UNKNOWN_CONTAINMENT_UNSUPPORTED"
    assert "pid" not in result


def test_running_cancellation_terminates_the_whole_job(tmp_path):
    ready=tmp_path/"ready"
    program=("import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time; time.sleep(20)']); "
        +f"open({str(ready)!r},'w').write('ready'); time.sleep(20)")
    result=run(tmp_path/"check",program,cancellation_requested=lambda:ready.exists())
    assert result["status"] == "CANCELLED",result
    assert result["termination"]["active_processes_after"] == 0


@pytest.mark.parametrize("fault",["binary","configuration","extra_startup"])
def test_private_bridge_corruption_is_not_reused(tmp_path,monkeypatch,fault):
    monkeypatch.setattr(windows_job.tempfile,"gettempdir",lambda:str(tmp_path))
    command=[sys.executable,"-c","print('must not run corrupt bridge')"]
    _,_,binding=windows_job.prepare_python_command(command,dict(os.environ))
    if binding["method"] != "BYTE_IDENTICAL_DIRECT_PYTHON_BRIDGE":
        pytest.skip("Current Python is a direct interpreter and needs no bridge")
    root=Path(binding["directory"])
    if fault=="binary":
        with (root/"Scripts/python.exe").open("ab") as stream: stream.write(b"changed")
    elif fault=="configuration":
        (root/"pyvenv.cfg").write_text("home = missing\n")
    else:
        (root/"Lib/site-packages/extra.pth").write_text("import sys\n")
    with pytest.raises(windows_job.ContainmentError):
        windows_job.prepare_python_command(command,dict(os.environ))


def test_nested_frozen_environment_rederives_private_dll_startup(tmp_path):
    """A worker resets PYTHONPATH before launching its independent checker."""
    from oma.build_identity import frozen_environment
    import ifcopenshell
    outer_env=frozen_environment(tmp_path/"outer-snapshot")
    identity=tmp_path/"inner-identity.json"
    inner_result=tmp_path/"inner-result.json"
    inner=("import _socket,ssl,sqlite3,unicodedata,ifcopenshell,OCP,sys,os,json; "
        +"from oma.build_identity import checker_version; "
        +f"open({str(identity)!r},'w').write(json.dumps(dict(pid=os.getpid(),prefix=sys.prefix,exe=sys.executable,"
        +"ifc=ifcopenshell.__file__,version=checker_version())))")
    outer=("from pathlib import Path\nimport sys,time,json\n"
        +"from oma.build_identity import frozen_environment\nfrom oma.export_checks import supervise_check\n"
        +f"env=frozen_environment(Path({str(tmp_path/'inner-snapshot')!r}))\n"
        +"assert str(Path(sys.prefix)/'DLLs') not in env['PYTHONPATH']\n"
        +f"result=supervise_check([sys.executable,'-c',{inner!r}],environment=env,directory=Path({str(tmp_path/'inner-check')!r}),deadline=time.monotonic()+12,reserve_bytes=0)\n"
        +f"Path({str(inner_result)!r}).write_text(json.dumps(result))\n"
        +"raise SystemExit(0 if result['status']=='COMPLETED' else 23)\n")
    result=export_checks.supervise_check([sys.executable,"-c",outer],environment=outer_env,
        directory=tmp_path/"outer-check",deadline=time.monotonic()+20,reserve_bytes=0)
    nested=json.loads(inner_result.read_text()) if inner_result.exists() else None
    assert result["status"] == "COMPLETED",(result,nested)
    assert nested["status"] == "COMPLETED" and nested["containment"]["active_processes"] == 0
    info=json.loads(identity.read_text())
    assert info["pid"] == nested["pid"]
    assert Path(info["ifc"]).resolve() == Path(ifcopenshell.__file__).resolve()
    assert info["version"] == outer_env["OMA_EXECUTABLE_BUILD"]
    assert result["containment"]["total_processes"] >= 2
    assert result["containment"]["active_processes"] == 0
