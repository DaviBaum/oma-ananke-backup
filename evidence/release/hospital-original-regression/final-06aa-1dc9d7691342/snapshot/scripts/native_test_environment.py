"""Prepare an isolated application test interpreter for the native candidate."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import venv

from packaging.utils import canonicalize_name, parse_wheel_filename
from native_prepare import ROOT, DEST, EVIDENCE, sha, json_write
from native_build import developer_environment, run


def main(stage):
    target = DEST / "test-venv"
    assert target.resolve().is_relative_to(DEST.resolve())
    python = target / "Scripts/python.exe"
    env = developer_environment()
    if not python.exists():
        venv.EnvBuilder(with_pip=True).create(target)
    assert Path(subprocess.check_output([str(python),"-c","import sys; print(sys.prefix)"],text=True).strip()).resolve() == target.resolve()
    lock = ROOT / "requirements.lock"
    requirements = [line.strip() for line in lock.read_text(encoding="utf-8-sig").splitlines()
                    if line.strip() and not line.startswith("#") and not line.lower().startswith("ifcopenshell==")]
    test_lock = DEST / "test-requirements.lock"
    test_lock.write_text("\n".join(requirements)+"\n",encoding="utf-8")
    extra = DEST / "test-wheels"
    extra.mkdir(exist_ok=True)
    wheelhouses = [ROOT / ".release/wheelhouse", extra]
    available = {(canonicalize_name(parse_wheel_filename(p.name)[0]),str(parse_wheel_filename(p.name)[1]))
                 for directory in wheelhouses for p in directory.glob("*.whl")}
    missing = [line for line in requirements if tuple([canonicalize_name(line.split("==")[0]),line.split("==")[1]]) not in available]
    if missing:
        run("test-dependency-download",[sys.executable,"-m","pip","download","--only-binary=:all:","--no-deps",
            "--dest",extra,*missing],env=env,budget=1200)
    run("test-dependency-install",[python,"-m","pip","install","--no-index",
        *[arg for directory in wheelhouses for arg in ["--find-links",directory]],"-r",test_lock],env=env,budget=1800)
    record = {"status":"ISOLATED_DEPENDENCIES_READY","test_python":str(python),"test_prefix":str(target),
        "active_runtime_modified":False,"original_lock_sha256":sha(lock),"test_lock_sha256":sha(test_lock),
        "only_dependency_override":"IfcOpenShell installed separately from the source-built candidate wheel",
        "additional_wheels":[{"path":str(p),"sha256":sha(p),"bytes":p.stat().st_size} for p in extra.glob("*.whl")]}
    if stage == "install-candidate":
        candidate = json.loads((EVIDENCE / "candidate-wheel.json").read_text())
        wheel = Path(candidate["wheel"])
        assert sha(wheel) == candidate["sha256"]
        run("test-candidate-install",[python,"-m","pip","install","--no-index","--no-deps",wheel],env=env,budget=600)
        probe = "import ifcopenshell,json,sys; from pathlib import Path; import ifcopenshell._ifcopenshell_wrapper as w; print(json.dumps({'version':ifcopenshell.version,'module':ifcopenshell.__file__,'extension':w.__file__,'prefix':sys.prefix}))"
        identity = json.loads(subprocess.check_output([str(python),"-c",probe],env=env,text=True))
        assert identity["version"] == candidate["version"]
        for field in ("module","extension"):
            assert Path(identity[field]).resolve().is_relative_to(target.resolve())
        assert sha(Path(identity["extension"])) == candidate["variant"]["native_extension_sha256"]
        record.update(status="ISOLATED_CANDIDATE_INSTALLED_NOT_APPLICATION_VALIDATED",candidate=candidate,identity=identity)
    json_write(EVIDENCE / "test-environment.json",record)
    print(json.dumps({k:record[k] for k in ["status","test_python","active_runtime_modified"]}),flush=True)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage",choices=["prepare","install-candidate"],default="prepare")
    main(parser.parse_args().stage)
