from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,time,uuid
import xml.etree.ElementTree as ET

STAGE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(STAGE/"src"))
from oma.build_identity import frozen_environment


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    env=frozen_environment(STAGE);source=Path(env["PYTHONPATH"]);build=env["OMA_EXECUTABLE_BUILD"].rsplit(":",1)[-1]
    attempt=STAGE/"validation"/uuid.uuid4().hex;attempt.mkdir(parents=True)
    test=attempt/"tests/test_coupled_tree_pressure.py";test.parent.mkdir();shutil.copyfile(STAGE/"tests/test_coupled_tree_pressure.py",test)
    shutil.copyfile(__file__,attempt/"runner.py")
    inputs={p.relative_to(attempt).as_posix():sha(p) for p in attempt.rglob("*") if p.is_file()}
    sources={p.relative_to(source).as_posix():sha(p) for p in source.rglob("*.py")}
    start=time.perf_counter()
    completed=subprocess.run([sys.executable,"-m","pytest",str(test),"-q","-o","pythonpath="+str(source),"--junitxml="+str(attempt/"tests.xml")],env=env,capture_output=True,text=True)
    (attempt/"pytest.log").write_text(completed.stdout+completed.stderr,encoding="utf-8")
    cases=ET.parse(attempt/"tests.xml").getroot().findall(".//testcase")
    identities={(x.attrib.get("classname"),x.attrib.get("name")) for x in cases}
    failures=sum(x.find("failure") is not None or x.find("error") is not None for x in cases);skips=sum(x.find("skipped") is not None for x in cases)
    same=all(sha(attempt/k)==v for k,v in inputs.items());ssame=all(sha(source/k)==v for k,v in sources.items())
    result={"status":"PASS" if completed.returncode==0 and cases and len(cases)==len(identities) and not failures and not skips and same and ssame else "FAIL",
        "build":build,"tests":len(cases),"unique_test_ids":len(identities),"failures":failures,"skips":skips,"seconds":time.perf_counter()-start,
        "source_hashes":sources,"input_hashes":inputs,"source_unchanged":ssame,"inputs_unchanged":same,"xml_sha256":sha(attempt/"tests.xml"),
        "validation_directory":attempt.relative_to(STAGE).as_posix(),"scope":"Standalone declared unequal quadratic-tree uniform positive-box certificate; no native adapter or global exclusion"}
    data=json.dumps(result,indent=2)+"\n";(attempt/"result.json").write_text(data,encoding="utf-8")
    (STAGE/"evidence/latest-checkpoint.json").write_text(data,encoding="utf-8")
    print(json.dumps({k:result[k] for k in ("status","build","tests","failures","skips","seconds","validation_directory")}))
    if result["status"]!="PASS":print(completed.stdout);raise SystemExit(1)


if __name__=="__main__":main()
