"""Run all-schema native smoke and the exact frozen 916-test application suite."""
import json
import os
from pathlib import Path
import subprocess
import time

from native_prepare import ROOT, DEST, EVIDENCE, sha, json_write
from native_build import run


def main():
    python=DEST / "test-venv/Scripts/python.exe"
    selection=json.loads((EVIDENCE / "test-selection.json").read_text())
    assert sha(Path(selection["node_manifest"]))==selection["node_manifest_sha256"] and selection["node_count"]==916
    env=os.environ.copy()
    env["PYTHONPATH"]=str(ROOT / ".oma/runtimes" / selection["source_runtime"] / "src")
    env.pop("OMA_EXECUTABLE_BUILD",None)
    snapshot_code="from oma.build_identity import frozen_environment; import json; e=frozen_environment(r'"+str(DEST / "application-runtimes")+"'); print(json.dumps({k:e[k] for k in ['PYTHONPATH','OMA_EXECUTABLE_BUILD']}))"
    snapshot=json.loads(subprocess.check_output([str(python),"-c",snapshot_code],env=env,text=True))
    env.update(snapshot)
    json_write(EVIDENCE / "candidate-application-runtime.json",snapshot)
    start=time.perf_counter()
    result={"status":"RUNNING","python":str(python),"runtime":snapshot,"source_checkpoint":selection["source_runtime"],
        "test_commit":selection["git_commit"],"test_node_count":916,"test_node_manifest_sha256":selection["node_manifest_sha256"],
        "candidate_wheel_manifest_sha256":sha(EVIDENCE / "candidate-wheel.json"),"active_runtime_modified":False,
        "smoke_script_sha256":sha(ROOT / "scripts/native_candidate_smoke.py")}
    json_write(EVIDENCE / "application-validation.json",result)
    try:
        smoke=run("all-schema-smoke",[python,ROOT / "scripts/native_candidate_smoke.py"],cwd=ROOT,env=env,budget=300)
        result["smoke_record"]=str(smoke / "record.json")
        suite=run("application-916-tests",[python,"-m","pytest","-q","-o","pythonpath=",
            "-c",Path(selection["destination"]) / "pyproject.toml","@"+selection["node_manifest"],
            "--junitxml="+str(EVIDENCE / "application-916-tests.xml")],cwd=ROOT,env=env,budget=1800)
        result["suite_record"]=str(suite / "record.json")
        import xml.etree.ElementTree as ET
        xml=ET.parse(EVIDENCE / "application-916-tests.xml").getroot()
        assert len(xml.findall(".//testcase"))==916 and not xml.findall(".//failure") and not xml.findall(".//error") and not xml.findall(".//skipped")
        result.update(status="ALL_SCHEMA_SMOKE_AND_EXACT_916_TEST_BASELINE_PASS",test_xml_sha256=sha(EVIDENCE / "application-916-tests.xml"))
    except BaseException as error:
        result.update(status="VALIDATION_INCOMPLETE_OR_FAILED",error=repr(error))
        raise
    finally:
        result["seconds"]=time.perf_counter()-start
        json_write(EVIDENCE / "application-validation.json",result)
        print(json.dumps({k:result[k] for k in ["status","seconds","runtime"]}),flush=True)


if __name__=="__main__":
    main()
