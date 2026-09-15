"""Freeze only this new component/test/support files and run the exact test set."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

STAGE=Path(__file__).resolve().parents[1]
def sha(data):return hashlib.sha256(data).hexdigest()
def dump(path,value):path.write_text(json.dumps(value,indent=2)+"\n",encoding="utf-8")
module="src/oma/optimization/shared_tree_synthesis.py"
test="tests/test_shared_tree_synthesis.py"
paths=[module,test]+[str(p.relative_to(STAGE)).replace('\\','/') for p in sorted((STAGE/'tests/fixtures/shared-tree-synthesis').glob('*.json'))]
records=[{"path":p,"sha256":sha((STAGE/p).read_bytes())} for p in paths]
source_root=sha(json.dumps([records[0]],sort_keys=True,separators=(',',':')).encode())
runtime=STAGE/'runtimes'/source_root
for record in records:
 target=runtime/record['path'];target.parent.mkdir(parents=True,exist_ok=True)
 data=(STAGE/record['path']).read_bytes()
 if target.exists():assert target.read_bytes()==data,"Existing frozen path differs"
 else:target.write_bytes(data)
receipt=STAGE/'validation'/uuid.uuid4().hex;receipt.mkdir(parents=True)
(receipt/'freeze_test.py').write_bytes(Path(__file__).read_bytes())
env=os.environ.copy();env['OMA_SHARED_TREE_SOURCE']=str(runtime/module);env['PYTHONIOENCODING']='utf-8'
base=[sys.executable,'-m','pytest',str(runtime/test),'-q','-o','addopts=']
start=time.monotonic()
collected=subprocess.run(base+['--collect-only'],env=env,capture_output=True,text=True,encoding='utf-8',timeout=60)
(receipt/'collection.txt').write_text(collected.stdout+collected.stderr,encoding='utf-8')
assert collected.returncode==0
nodes=[line for line in collected.stdout.splitlines() if '::test_' in line]
assert nodes and len(nodes)==len(set(nodes))
dump(receipt/'collected-nodes.json',nodes)
run=subprocess.run(base+['--junitxml',str(receipt/'tests.xml'),'--tb=short'],env=env,capture_output=True,text=True,encoding='utf-8',timeout=60)
(receipt/'pytest.txt').write_text(run.stdout+run.stderr,encoding='utf-8')
xml=ET.parse(receipt/'tests.xml').getroot();cases=xml.findall('.//testcase')
counts={k:len(xml.findall('.//'+k)) for k in ('failure','error','skipped')}
unchanged=all(sha((runtime/r['path']).read_bytes())==r['sha256'] for r in records)
result={'schema':'oma.private-component-test-receipt/1','component_source_root':source_root,
        'component_source_root_is_full_oma_build':False,'module_sha256':records[0]['sha256'],
        'status':'PASS' if run.returncode==0 and len(cases)==len(nodes) and not any(counts.values()) and unchanged else 'FAIL',
        'collected':len(nodes),'testcases':len(cases),**counts,'exit_code':run.returncode,
        'elapsed_seconds':time.monotonic()-start,'files':records,'snapshot_unchanged':unchanged,
        'command':base,'executed_script_sha256':sha(Path(__file__).read_bytes()),
        'scope':'New pure synthesis kernel and portable independently authored catalogue/oracle fixtures; no native rerun'}
dump(receipt/'result.json',result)
print(json.dumps({'receipt':str(receipt),'runtime':str(runtime),'result':result}))
assert result['status']=='PASS'
