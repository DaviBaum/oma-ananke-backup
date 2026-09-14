"""Package launch reuses only the same immutable build and canonical store."""
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import venv

from fastapi.testclient import TestClient
import pytest

import oma
from oma import api
from oma.build_identity import checker_version


def test_health_retains_startup_identity_and_exposes_later_source_change(tmp_path,monkeypatch):
    monkeypatch.setattr(api,"diagnose",lambda directory:{"test":"health identity only"})
    app=api.create_app(tmp_path/"parent"/".."/"store",recover=False)
    with TestClient(app) as client:
        initial=client.get("/api/health").json()["server_identity"]
        assert initial["schema"]=="oma.server-identity/1"
        assert initial["data_directory"]==str((tmp_path/"store").resolve())
        assert initial["checker_version"]==checker_version()
        assert initial["startup_environment_matches"] and not initial["source_changed"]
        monkeypatch.setattr(api,"checker_version",lambda:"different-on-disk-source")
        changed=client.get("/api/health").json()["server_identity"]
        assert changed["checker_version"]==initial["checker_version"]
        assert changed["source_changed"] and changed["current_disk_checker_version"]=="different-on-disk-source"


@pytest.fixture(scope="module")
def launcher_package(tmp_path_factory):
    package=tmp_path_factory.mktemp("launcher-identity")
    source=Path(oma.__file__).parent
    shutil.copytree(source,package/"src/oma",ignore=shutil.ignore_patterns("__pycache__"))
    # The test snapshot can live away from the workspace. This environment is
    # explicitly passed by the frozen test launcher below when needed.
    workspace=Path(os.environ.get("OMA_LAUNCHER_SOURCE_ROOT",Path(__file__).resolve().parents[1]))
    shutil.copyfile(workspace/"Start-OMA.ps1",package/"Start-OMA.ps1")
    (package/"ui/dist").mkdir(parents=True)
    (package/"ui/dist/index.html").write_text("<title>controlled launcher fixture</title>")
    venv.EnvBuilder(with_pip=False,symlinks=False).create(package/".venv")
    (package/".venv/Lib/site-packages/oma-original.pth").write_text(
        "import site; site.addsitedir("+repr(str(Path(sys.prefix)/"Lib/site-packages"))+")\n")
    return package


@pytest.mark.parametrize("fault",[None,"other_build","other_store","legacy","source_changed","startup_mismatch","not_oma","http_error","slow_health"])
def test_powershell_reuse_requires_exact_identity_without_stopping_server(launcher_package,fault):
    package=launcher_package
    identity={"schema":"oma.server-identity/1","checker_version":checker_version(),
        "data_directory":str((package/".oma").resolve()),"source_changed":False,"startup_environment_matches":True}
    health={"application":"oma-ananke","server_identity":deepcopy(identity)}
    if fault=="other_build": health["server_identity"]["checker_version"]="oma-independent-checker/2:other"
    if fault=="other_store": health["server_identity"]["data_directory"]=str(package/"another-store")
    if fault=="legacy": del health["server_identity"]
    if fault=="source_changed": health["server_identity"]["source_changed"]=True
    if fault=="startup_mismatch": health["server_identity"]["startup_environment_matches"]=False
    if fault=="not_oma": health["application"]="another-application"
    requests=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            if fault=="slow_health": time.sleep(4)
            try:
                self.send_response(503 if fault=="http_error" else 200)
                self.send_header("Content-Type","application/json");self.end_headers()
                self.wfile.write(json.dumps(health).encode())
            except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError): pass
        def log_message(self,*args): pass
    server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        # A hostile inherited source path must not determine package identity.
        env={**os.environ,"PYTHONPATH":str(package/"wrong-source"),"OMA_EXECUTABLE_BUILD":"stale-inherited-build"}
        result=subprocess.run(["powershell.exe","-NoLogo","-NoProfile","-ExecutionPolicy","Bypass","-File",
            str(package/"Start-OMA.ps1"),"-Port",str(server.server_port),"-NoBrowser"],env=env,
            text=True,capture_output=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
        assert requests==["/api/health"],(result.stdout,result.stderr)
        assert thread.is_alive()  # No existing server/process is terminated.
        assert not (package/".oma/logs/service.json").exists()
        assert not (package/".oma/service.json").exists()
        if fault is None:
            assert result.returncode==0,(result.stdout,result.stderr)
            assert "available" in result.stdout
        else:
            assert result.returncode!=0,(result.stdout,result.stderr)
            assert "Choose an unused port with -Port" in result.stderr
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)


def test_startup_environment_mismatch_is_exposed_by_fresh_api(launcher_package):
    package=launcher_package
    env={**os.environ,"PYTHONPATH":str(package/"src"),"OMA_EXECUTABLE_BUILD":"wrong-frozen-build"}
    program=("import json; import oma.api as a; from fastapi.testclient import TestClient; "
        +"a.diagnose=lambda p:{}; "
        +f"app=a.create_app({str(package/'mismatched-env-store')!r},recover=False); "
        +"print(json.dumps(TestClient(app).get('/api/health').json()['server_identity']))")
    result=subprocess.run([sys.executable,"-c",program],env=env,text=True,capture_output=True,
        timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode==0,result.stderr
    identity=json.loads(result.stdout)
    assert identity["checker_version"]==checker_version()
    assert identity["declared_checker_version"]=="wrong-frozen-build"
    assert not identity["startup_environment_matches"]
    assert not identity["source_changed"]
