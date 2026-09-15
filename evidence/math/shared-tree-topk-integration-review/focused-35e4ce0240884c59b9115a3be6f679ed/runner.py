"""Freeze exact owned binding code/tests with policy and legacy compatibility."""
from pathlib import Path
from collections import Counter
import hashlib,json,os,shutil,subprocess,sys,time,uuid
from xml.etree import ElementTree as E

ROOT=Path(__file__).resolve().parents[2];S=ROOT/'.oma/development/factorized-tree-pressure'
OUT=ROOT/'evidence/math/shared-tree-topk-integration-review'/('focused-'+uuid.uuid4().hex)
OUT.mkdir(parents=True);SNAP=OUT/'snapshot';SNAP.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8')
files={}
for p in sorted((S/'src').rglob('*.py')):files[p.relative_to(S).as_posix()]=p
for name in ('test_compact_binding_integrity.py','test_compact_proof_policy.py','general_tree_fixture.py','fixtures/coupled-native-tree/boundary.json'):
    files['tests/'+name]=S/'tests'/name
files['tests/test_shared_tree_proposals.py']=ROOT/'tests/test_shared_tree_proposals.py'
manifest={}
for name,p in files.items():
    q=SNAP/name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q);manifest[name]=sha(p);assert sha(q)==manifest[name]
write(OUT/'manifest.json',manifest);shutil.copyfile(__file__,OUT/'runner.py')
(SNAP/'pytest.ini').write_text('[pytest]\naddopts = -ra\n',encoding='utf-8')
env=os.environ.copy();env['PYTHONPATH']=str(SNAP/'src');env['PYTHONIOENCODING']='utf-8'
args=[sys.executable,'-m','pytest','-q','-c',str(SNAP/'pytest.ini'),
      'tests/test_compact_binding_integrity.py','tests/test_compact_proof_policy.py','tests/test_shared_tree_proposals.py']
collect=subprocess.run(args+['--collect-only'],cwd=SNAP,env=env,capture_output=True,text=True,encoding='utf-8')
(OUT/'collection.log').write_text(collect.stdout+collect.stderr,encoding='utf-8');assert collect.returncode==0
nodes=[x for x in collect.stdout.splitlines() if x.startswith('tests/') and '::' in x];write(OUT/'nodes.json',nodes)
write(OUT/'command.json',args);start=time.perf_counter()
with (OUT/'pytest.log').open('w',encoding='utf-8') as log:
    result=subprocess.run(args+['--junitxml='+str(OUT/'tests.xml'),'--basetemp='+str(OUT/'temp')],cwd=SNAP,env=env,stdout=log,stderr=subprocess.STDOUT)
elapsed=time.perf_counter()-start;xml=E.parse(OUT/'tests.xml').getroot()
counts={name:len(xml.findall('.//'+name)) for name in ('testcase','failure','error','skipped')}
exact=Counter(x.attrib['classname'].replace('.','/')+'.py::'+x.attrib['name'] for x in xml.findall('.//testcase'))==Counter(nodes)
unchanged=all(sha(SNAP/name)==value==sha(files[name]) for name,value in manifest.items())
record={'status':'PASS' if result.returncode==0 and exact and unchanged else 'FAIL','counts':counts,'seconds':elapsed,
    'exact_node_multiset':exact,'all_source_inputs_unchanged':unchanged,'manifest_sha256':sha(OUT/'manifest.json'),
    'xml_sha256':sha(OUT/'tests.xml'),'runner_sha256':sha(OUT/'runner.py'),'snapshot':str(SNAP),
    'scope':'Actual nominal producer/independent checker and isolated Store publication controls; no native rerun.'}
write(OUT/'result.json',record);write(ROOT/'evidence/math/shared-tree-topk-integration-review/latest-focused.json',{'directory':str(OUT),'receipt_sha256':sha(OUT/'result.json'),**record})
print(json.dumps({'directory':str(OUT),'receipt_sha256':sha(OUT/'result.json'),**record}),flush=True)
if result.returncode:print((OUT/'pytest.log').read_text(encoding='utf-8')[-5000:])
raise SystemExit(result.returncode)
