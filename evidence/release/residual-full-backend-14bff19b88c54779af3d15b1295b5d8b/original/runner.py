"""Full private backend suite, with exact source, test and XML identity checks."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

STAGE = Path(__file__).resolve().parents[1]
ROOT = next(p for p in STAGE.parents if (p/"AGENTS.md").is_file())
sys.path.insert(0,str(STAGE/"src"))
from oma.build_identity import checker_version, frozen_environment
from oma.ifc.audit import atomic_json


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    identity = uuid.uuid4().hex
    out = STAGE/"evidence"/("full-backend-"+identity)
    snapshot = STAGE/"validation"/identity
    out.mkdir(parents=True)
    snapshot.mkdir(parents=True)
    base_record = ROOT/"evidence/release/pressure-admission-complete-c2250254bc084d14abb63f6bf6237c8d/result.json"
    base = json.loads(base_record.read_text())
    files = {}
    for relative,value in base["snapshot_files"].items():
        source = Path(base["test_snapshot"])/relative
        assert sha(source) == value
        target = snapshot/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
        assert sha(target) == value
        files[relative] = value
    for name in ("test_optimization_fabrication_alternatives.py","test_certified_fabrication_residual.py","test_joint_residual_fabrication.py"):
        source = STAGE/"tests"/name
        value = sha(source)
        target = snapshot/"tests"/name
        shutil.copyfile(source,target)
        assert sha(source) == sha(target) == value
        files["tests/"+name] = value
    env = frozen_environment(STAGE)
    prefix = [sys.executable,"-m","pytest","-o","pythonpath="+env["PYTHONPATH"]]
    collected = subprocess.run([*prefix,"tests","--collect-only","-q"],cwd=snapshot,env=env,text=True,
        encoding="utf8",stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
    (out/"collection.log").write_text(collected.stdout,encoding="utf8")
    assert collected.returncode == 0,collected.stdout
    nodes = [line.strip() for line in collected.stdout.splitlines() if line.startswith("tests/") and "::" in line]
    assert nodes and len(nodes) == len(set(nodes))
    atomic_json(out/"test-nodes.json",nodes)
    shutil.copyfile(Path(__file__),out/"runner.py")
    result = {"status":"RUNNING","checker_version":env["OMA_EXECUTABLE_BUILD"],"snapshot_files":files,
        "test_snapshot":str(snapshot),"test_node_count":len(nodes),"test_nodes_sha256":sha(out/"test-nodes.json"),
        "runner_sha256":sha(out/"runner.py"),"source_base_snapshot":str(base_record)}
    atomic_json(out/"result.json",result)
    print(json.dumps({k:result[k] for k in ("status","checker_version","test_node_count","test_snapshot")}),flush=True)
    started = time.perf_counter()
    command = [*prefix,"tests","-q","--junitxml="+str(out/"tests.xml")]
    with (out/"pytest.log").open("w",encoding="utf8") as stream:
        completed = subprocess.run(command,cwd=snapshot,env=env,stdout=stream,stderr=subprocess.STDOUT)
    result.update(returncode=completed.returncode,seconds=time.perf_counter()-started,command=command)
    try:
        actual = {p.relative_to(snapshot).as_posix():sha(p) for p in snapshot.rglob("*") if p.is_file()
            and not {"__pycache__",".pytest_cache"}.intersection(p.relative_to(snapshot).parts)}
        assert all(actual.get(p)==value for p,value in files.items()),"Frozen test/support bytes changed"
        extra = set(actual)-set(files)
        groups = {str(Path(p).parent) for p in extra}
        assert len(groups)==1 and len(extra)==3,"Unexpected files outside declared test inputs"
        parent = Path(next(iter(groups)))
        assert parent.parent.as_posix()=="evidence/release/joint-fitting-budget-audit"
        assert len(parent.name)==32 and all(c in "0123456789abcdef" for c in parent.name)
        assert {Path(p).name for p in extra}=={"declared-source.ifc","source-after-pause.ifc","result.json"}
        derived = json.loads((snapshot/parent/"result.json").read_text())
        assert derived["case"]=="SOURCE_MUTATION_AT_FINAL_FITTING_PAUSE" and derived["original_restored"] is True
        assert sha(snapshot/parent/"declared-source.ifc")==derived["declared_source_sha256"]
        assert sha(snapshot/parent/"source-after-pause.ifc")==derived["current_source_sha256_at_publication"]
        result["derived_test_outputs"]={p:actual[p] for p in sorted(extra)}
        xml=ET.parse(out/"tests.xml").getroot()
        expected=[]
        for node in nodes:
            pieces=node.split("::")
            expected.append((pieces[0][:-3].replace("/",".")+("."+".".join(pieces[1:-1]) if len(pieces)>2 else ""),pieces[-1]))
        cases=xml.findall(".//testcase")
        assert Counter((c.get("classname"),c.get("name")) for c in cases)==Counter(expected),"XML case identities differ"
        assert not any(xml.findall(".//"+tag) for tag in ("failure","error","skipped"))
        assert completed.returncode==0
        result.update(status="PASS",passed=len(cases),snapshot_unchanged=True,exact_case_identities_checked=True,
            current_source_unchanged=checker_version()==env["OMA_EXECUTABLE_BUILD"],test_xml_sha256=sha(out/"tests.xml"))
    except BaseException as exc:
        result.update(status="FAIL",error=repr(exc))
    atomic_json(out/"result.json",result)
    print((out/"pytest.log").read_text(),flush=True)
    print(json.dumps({k:v for k,v in result.items() if k not in {"snapshot_files","command"}}),flush=True)
    return 0 if result["status"]=="PASS" else 1


if __name__=="__main__":
    raise SystemExit(main())
