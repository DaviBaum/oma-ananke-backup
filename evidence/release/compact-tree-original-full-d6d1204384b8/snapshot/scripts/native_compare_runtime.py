"""Compare original and candidate checker identities on identical pinned source."""
import json
import os
from pathlib import Path
import subprocess

from native_prepare import ROOT, DEST, EVIDENCE, sha, json_write

SOURCE_BUILD="94e74251a39d1f0d8cc77feb9d2df686e3927eb49473b67d09d8bdf66843c93f"


def main():
    source=ROOT / ".oma/runtimes" / SOURCE_BUILD / "src"
    assert (source / "oma/build_identity.py").is_file()
    env=os.environ.copy()
    env["PYTHONPATH"]=str(source)
    env.pop("OMA_EXECUTABLE_BUILD",None)
    probe="""import hashlib,importlib.metadata,json,sys
from pathlib import Path
import ifcopenshell._ifcopenshell_wrapper as extension
from oma.build_identity import checker_version
import oma
root=Path(oma.__file__).parent
files={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*.py'))}
print(json.dumps({'checker_version':checker_version(),'python':sys.executable,'python_version':sys.version,
 'source_files':files,'packages':{p:importlib.metadata.version(p) for p in ('ifcopenshell','cadquery-ocp','numpy','scipy','pydantic','cupy-cuda12x')},
 'extension_path':extension.__file__,'extension_sha256':hashlib.sha256(Path(extension.__file__).read_bytes()).hexdigest()}))
"""
    original=json.loads(subprocess.check_output([str(ROOT / ".venv/Scripts/python.exe"),"-c",probe],env=env,text=True))
    candidate=json.loads(subprocess.check_output([str(DEST / "test-venv/Scripts/python.exe"),"-c",probe],env=env,text=True))
    wheel=json.loads((EVIDENCE / "candidate-wheel.json").read_text())
    assert original["checker_version"].endswith(SOURCE_BUILD)
    assert original["source_files"]==candidate["source_files"]
    assert original["python_version"]==candidate["python_version"]
    assert original["packages"]["ifcopenshell"]=="0.8.5"
    assert candidate["packages"]["ifcopenshell"]==wheel["version"]
    assert candidate["extension_sha256"]==wheel["variant"]["native_extension_sha256"]
    assert candidate["packages"]["ifcopenshell"].endswith(".b"+candidate["extension_sha256"])
    assert {k:v for k,v in original["packages"].items() if k!="ifcopenshell"}=={k:v for k,v in candidate["packages"].items() if k!="ifcopenshell"}
    assert original["checker_version"]!=candidate["checker_version"]
    assert original["extension_sha256"]!=candidate["extension_sha256"]
    result={"status":"CHECKER_IDENTITY_CHANGED_FOR_DISTINCT_NATIVE_BUILD","original":original,"candidate":candidate,
        "same_python_source":True,"same_python_version":True,"all_other_fingerprinted_dependency_versions_identical":True,
        "candidate_distribution_version_binds_full_extension_sha256":True,"active_runtime_modified":False}
    json_write(EVIDENCE / "runtime-identity-comparison.json",result)
    print(json.dumps({"status":result["status"],"original":original["checker_version"],"candidate":candidate["checker_version"]}),flush=True)


if __name__=="__main__":
    main()
