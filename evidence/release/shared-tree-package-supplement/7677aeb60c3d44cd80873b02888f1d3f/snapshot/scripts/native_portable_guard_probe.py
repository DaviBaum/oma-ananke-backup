"""Confirm the offline guard runs in bundled and frozen-checker interpreters."""
import argparse
import json
import os
from pathlib import Path
import subprocess

from native_prepare import sha, json_write


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", required=True, type=Path)
    args = parser.parse_args()
    result = json.loads(args.result.read_text())
    assert result["status"] == "ISOLATED_NATIVE_PORTABLE_OFFLINE_WORKFLOW_PASS"
    package = Path(result["package"])
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("OMA_EXECUTABLE_BUILD", None)
    env.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1", OMA_OFFLINE_DENY_NETWORK="1", PIP_NO_INDEX="1")
    probe = """import json,socket,sys,sitecustomize
from oma.build_identity import checker_version
try:
    s=socket.socket(); s.connect(('127.0.0.1',9))
except RuntimeError as error:
    assert str(error)=='Offline verification denies Python network operations: socket.connect'
    print(json.dumps({'status':'PYTHON_SOCKET_CONNECT_DENIED','checker_version':checker_version(),'guard':sitecustomize.__file__,'python':sys.executable}))
else:
    raise AssertionError('Offline audit guard did not deny the connect operation')
"""
    executable = package / "runtime/python.exe"
    records = []
    for mode in ("BUNDLED", "FROZEN_CHECKER"):
        if mode == "FROZEN_CHECKER":
            runtime = package / "offline-qa/data/runtimes" / result["identity"]["checker_version"].split(":")[-1] / "src"
            assert runtime.is_dir()
            env["PYTHONPATH"] = str(runtime)
            env["OMA_EXECUTABLE_BUILD"] = result["identity"]["checker_version"]
        record = json.loads(subprocess.check_output([str(executable), "-B", "-s", "-c", probe], cwd=package, env=env, text=True, timeout=30))
        assert Path(record["guard"]).resolve().is_relative_to(package)
        assert record["checker_version"] == result["identity"]["checker_version"]
        record.update(mode=mode, guard_sha256=sha(Path(record["guard"])))
        records.append(record)
    output = {"status": "BUNDLED_AND_FROZEN_PYTHON_NETWORK_DENIAL_VERIFIED", "records": records,
              "scope": "Python socket.connect audit event denied before connection; not a machine-wide or native-library firewall claim",
              "package_validation_sha256": sha(args.result)}
    json_write(args.result.parent / "offline-guard-probe.json", output)
    print(json.dumps(output), flush=True)


if __name__ == "__main__":
    main()
