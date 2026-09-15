"""Frozen scoped kernel, dependency, legacy and adversarial test validation."""
from pathlib import Path
from collections import Counter
import hashlib,json,os,shutil,subprocess,sys,time,uuid
from xml.etree import ElementTree as E

S=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
out=S/'validation'/uuid.uuid4().hex;out.mkdir(parents=True);snap=out/'snapshot';snap.mkdir()
source={p.relative_to(S).as_posix():sha(p) for p in sorted((S/'src').rglob('*.py'))}
inputs={p.relative_to(S).as_posix():sha(p) for p in sorted((S/'tests').rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
inputs['pytest.ini']=sha(S/'pytest.ini')
for name,value in {**source,**inputs}.items():
 q=snap/name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(S/name,q);assert sha(q)==value
shutil.copyfile(__file__,out/'runner.py')
write(out/'manifest.json',{'source_files':source,'input_files':inputs,'snapshot':str(snap),'runner_sha256':sha(out/'runner.py')})
env=os.environ.copy();env['PYTHONPATH']=str(snap/'src');env['OMA_SHARED_TREE_SOURCE']=str(snap/'src/oma/optimization/shared_tree_synthesis.py');env['PYTHONIOENCODING']='utf-8'
cmd=[sys.executable,'-m','pytest','-c',str(snap/'pytest.ini'),'-q','tests/test_shared_tree_synthesis.py','tests/test_general_shared_tree_synthesis.py','tests/test_shared_tree_topk.py','tests/test_shared_tree_topk_grouped.py']
collect=subprocess.run(cmd+['--collect-only'],cwd=snap,env=env,text=True,encoding='utf-8',capture_output=True)
(out/'collection.log').write_text(collect.stdout+collect.stderr,encoding='utf-8');assert collect.returncode==0
nodes=[line.strip() for line in collect.stdout.splitlines() if line.startswith('tests/') and '::' in line]
assert nodes and len(nodes)==len(set(nodes));write(out/'nodes.json',nodes)
start=time.perf_counter()
with (out/'pytest.log').open('w',encoding='utf-8') as log:
 run=subprocess.run(cmd+['--junitxml='+str(out/'tests.xml'),'--basetemp='+str(out/'temp')],cwd=snap,env=env,stdout=log,stderr=subprocess.STDOUT)
seconds=time.perf_counter()-start
xml=E.parse(out/'tests.xml').getroot();cases=xml.findall('.//testcase')
counts={name:len(xml.findall('.//'+name)) for name in ('testcase','failure','error','skipped')}
exact=Counter(x.attrib['classname'].replace('.','/')+'.py::'+x.attrib['name'] for x in cases)==Counter(nodes)
unchanged=all(sha(S/k)==v==sha(snap/k) for k,v in {**source,**inputs}.items())
passed=run.returncode==0 and exact and unchanged and all(counts[x]==0 for x in ('failure','error','skipped'))
result={'status':'PASS' if passed else 'FAIL','counts':counts,'seconds':seconds,'returncode':run.returncode,
 'source_files':source,'input_count':len(inputs),'source_count':len(source),'snapshot':str(snap),
 'exact_node_multiset':exact,'all_files_unchanged':unchanged,'manifest_sha256':sha(out/'manifest.json'),
 'node_manifest_sha256':sha(out/'nodes.json'),'xml_sha256':sha(out/'tests.xml'),'runner_sha256':sha(out/'runner.py'),
 'scope':'Private pure nominal top-K recurrence and unchanged full-ledger dependency; no native acceptance or full original algorithm claim'}
write(out/'result.json',result);write(S/'latest-validation.json',{'directory':str(out),'receipt_sha256':sha(out/'result.json'),**result})
print(json.dumps({'directory':str(out),**result}),flush=True)
raise SystemExit(0 if passed else 1)
