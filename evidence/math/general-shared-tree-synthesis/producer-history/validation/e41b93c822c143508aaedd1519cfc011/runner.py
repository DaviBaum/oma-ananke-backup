"""Freeze this isolated component and exact tests before a scoped execution."""
from pathlib import Path
from collections import Counter
import hashlib,json,os,shutil,subprocess,sys,time,uuid
from xml.etree import ElementTree as E

STAGE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
source=STAGE/'src/oma/optimization/shared_tree_synthesis.py'
source_sha=sha(source)
out=STAGE/'validation'/uuid.uuid4().hex;out.mkdir(parents=True)
snapshot=out/'snapshot';snapshot.mkdir()
inputs={p.relative_to(STAGE).as_posix():sha(p) for p in sorted((STAGE/'tests').rglob('*'))
        if p.is_file() and '__pycache__' not in p.parts}
inputs['pytest.ini']=sha(STAGE/'pytest.ini')
for name,value in inputs.items():
 target=snapshot/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(STAGE/name,target);assert sha(target)==value
target=snapshot/'src/oma/optimization/shared_tree_synthesis.py';target.parent.mkdir(parents=True);shutil.copyfile(source,target)
shutil.copyfile(__file__,out/'runner.py')
dump(out/'manifest.json',{'module_sha256':source_sha,'source':str(source),'inputs':inputs,
     'snapshot':str(snapshot),'runner_sha256':sha(out/'runner.py')})
env=os.environ.copy();env['OMA_SHARED_TREE_SOURCE']=str(target);env['PYTHONIOENCODING']='utf-8'
prefix=[sys.executable,'-m','pytest','-c',str(snapshot/'pytest.ini'),'-q','tests/test_shared_tree_synthesis.py','tests/test_general_shared_tree_synthesis.py']
c=subprocess.run(prefix+['--collect-only'],cwd=snapshot,env=env,text=True,encoding='utf-8',capture_output=True)
(out/'collection.log').write_text(c.stdout+c.stderr,encoding='utf-8');assert c.returncode==0
nodes=[line.strip() for line in c.stdout.splitlines() if line.startswith('tests/') and '::' in line]
assert nodes and len(nodes)==len(set(nodes));dump(out/'nodes.json',nodes)
start=time.perf_counter()
with (out/'pytest.log').open('w',encoding='utf-8') as log:
 result=subprocess.run(prefix+['--junitxml='+str(out/'tests.xml'),'--basetemp='+str(out/'temp')],cwd=snapshot,env=env,stdout=log,stderr=subprocess.STDOUT)
seconds=time.perf_counter()-start
xml=E.parse(out/'tests.xml').getroot();cases=xml.findall('.//testcase')
actual=Counter(x.attrib['classname'].replace('.','/')+'.py::'+x.attrib['name'] for x in cases)
identities=actual==Counter(nodes)
unchanged=sha(source)==source_sha==sha(target) and all(sha(STAGE/k)==v==sha(snapshot/k) for k,v in inputs.items())
counts={key:len(xml.findall('.//'+key)) for key in ('testcase','failure','error','skipped')}
passed=result.returncode==0 and identities and unchanged and all(counts[key]==0 for key in ('failure','error','skipped'))
receipt={'status':'PASS' if passed else 'FAIL','returncode':result.returncode,'counts':counts,'seconds':seconds,
    'module_sha256':source_sha,'source_snapshot':str(target),'input_count':len(inputs),'exact_node_multiset':identities,
    'inputs_unchanged':unchanged,'manifest_sha256':sha(out/'manifest.json'),'nodes_sha256':sha(out/'nodes.json'),
    'xml_sha256':sha(out/'tests.xml'),'runner_sha256':sha(out/'runner.py'),
    'scope':'Isolated pure finite-catalogue kernel; no native/app/full-algorithm claim'}
dump(out/'result.json',receipt)
dump(STAGE/'latest-validation.json',{'directory':str(out),'receipt_sha256':sha(out/'result.json'),**receipt})
print(json.dumps({'directory':str(out),**receipt}),flush=True)
raise SystemExit(0 if passed else 1)
