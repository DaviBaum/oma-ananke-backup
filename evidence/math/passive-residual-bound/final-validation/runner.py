from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,time,uuid
import xml.etree.ElementTree as ET

STAGE=Path(__file__).resolve().parents[1]
BUILD="123f1fe4133e0d988eed185303364e7c9ab05b43fd08e6f70011c9a4be0ddf7a"
SOURCE=STAGE/"runtimes"/BUILD/"src"


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    attempt=STAGE/"validation"/uuid.uuid4().hex;attempt.mkdir(parents=True)
    for rel in ["tests/test_passive_residual.py","tests/fixtures/passive-residual/coupled-loop-result.json"]:
        target=attempt/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(STAGE/rel,target)
    shutil.copyfile(__file__,attempt/"runner.py")
    inputs={p.relative_to(attempt).as_posix():sha(p) for p in attempt.rglob("*") if p.is_file()}
    sources={p.relative_to(SOURCE).as_posix():sha(p) for p in SOURCE.rglob("*.py")}
    env=os.environ.copy();env["PYTHONPATH"]=str(SOURCE);env["OMA_EXECUTABLE_BUILD"]="oma-independent-checker/2:"+BUILD
    start=time.perf_counter()
    p=subprocess.run([sys.executable,"-m","pytest",str(attempt/"tests/test_passive_residual.py"),"-q",
        "-o","pythonpath="+str(SOURCE),"--junitxml="+str(attempt/"tests.xml")],env=env,capture_output=True,text=True)
    (attempt/"pytest.log").write_text(p.stdout+p.stderr,encoding="utf-8")
    cases=ET.parse(attempt/"tests.xml").getroot().findall(".//testcase")
    count=len(cases);identities={(x.attrib.get("classname"),x.attrib.get("name")) for x in cases}
    failures=sum(x.find("failure") is not None or x.find("error") is not None for x in cases);skips=sum(x.find("skipped") is not None for x in cases)
    same=all(sha(attempt/k)==v for k,v in inputs.items());source_same=all(sha(SOURCE/k)==v for k,v in sources.items())
    ok=p.returncode==0 and count==len(identities)==86 and failures==skips==0 and same and source_same
    result={"status":"PASS" if ok else "FAIL","build":BUILD,"tests":count,"unique_test_ids":len(identities),"failures":failures,"skips":skips,
        "seconds":time.perf_counter()-start,"test_fixture_hashes":inputs,"source_hashes":sources,"test_fixture_unchanged":same,"source_unchanged":source_same,
        "xml_sha256":sha(attempt/"tests.xml"),"validation_directory":attempt.relative_to(STAGE).as_posix(),
        "scope":"Standalone bounded graph residual/stability certificate and pinned independent finite reference; no native or managed application claim"}
    data=json.dumps(result,indent=2)+"\n";(attempt/"result.json").write_text(data,encoding="utf-8")
    (STAGE/"evidence/final-checkpoint.json").write_text(data,encoding="utf-8")
    print(json.dumps({k:result[k] for k in ("status","build","tests","failures","skips","seconds","validation_directory")}))
    if not ok:raise SystemExit(1)


if __name__=="__main__":main()
