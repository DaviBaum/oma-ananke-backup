"""Freeze focused test/fixture bytes and validate the already frozen adapter."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

STAGE=Path(__file__).resolve().parents[1]
BUILD="f606e781935fa758da335c0519b84cc5df4461c8fc7a3a87154cf1d945469188"
SOURCE=STAGE/"runtimes"/BUILD/"src"


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    attempt=STAGE/"validation"/uuid.uuid4().hex
    (attempt/"tests").mkdir(parents=True)
    for rel in ["tests/test_passive_tree_pressure.py",*[str(p.relative_to(STAGE)) for p in sorted((STAGE/"tests/fixtures/passive-native-tree").glob("*.json"))]]:
        target=attempt/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(STAGE/rel,target)
    shutil.copyfile(__file__,attempt/"runner.py")
    files={p.relative_to(attempt).as_posix():sha(p) for p in attempt.rglob("*") if p.is_file()}
    sources={p.relative_to(SOURCE).as_posix():sha(p) for p in SOURCE.rglob("*.py")}
    env=os.environ.copy();env["PYTHONPATH"]=str(SOURCE);env["OMA_EXECUTABLE_BUILD"]="oma-independent-checker/2:"+BUILD
    started=time.perf_counter()
    result=subprocess.run([sys.executable,"-m","pytest",str(attempt/"tests/test_passive_tree_pressure.py"),"-q",
        "-o","pythonpath="+str(SOURCE),"--junitxml="+str(attempt/"tests.xml")],env=env,capture_output=True,text=True)
    (attempt/"pytest.log").write_text(result.stdout+result.stderr,encoding="utf-8")
    xml=ET.parse(attempt/"tests.xml").getroot();cases=xml.findall(".//testcase")
    identities={(x.attrib.get("classname"),x.attrib.get("name")) for x in cases}
    failures=sum(x.find("failure") is not None or x.find("error") is not None for x in cases)
    skipped=sum(x.find("skipped") is not None for x in cases)
    unchanged=all(sha(attempt/rel)==value for rel,value in files.items())
    source_unchanged=all(sha(SOURCE/rel)==value for rel,value in sources.items())
    valid=result.returncode==0 and len(cases)==len(identities)==65 and failures==skipped==0 and unchanged and source_unchanged
    receipt={"status":"PASS" if valid else "FAIL","build":BUILD,"tests":len(cases),"unique_test_ids":len(identities),
        "failures":failures,"skips":skipped,"seconds":time.perf_counter()-started,"source_unchanged":source_unchanged,
        "test_fixture_unchanged":unchanged,"test_fixture_hashes":files,"source_hashes":sources,"xml_sha256":sha(attempt/"tests.xml"),
        "validation_directory":attempt.relative_to(STAGE).as_posix(),"scope":"New adapter focused tests and retained actual-native metric inputs; root managed integration is separate"}
    data=json.dumps(receipt,indent=2)+"\n";(attempt/"result.json").write_text(data,encoding="utf-8")
    (STAGE/"evidence/adapter-final-checkpoint.json").write_text(data,encoding="utf-8")
    print(json.dumps({k:receipt[k] for k in ("status","build","tests","failures","skips","seconds","validation_directory")}))
    if not valid:raise SystemExit(1)


if __name__=="__main__":main()
