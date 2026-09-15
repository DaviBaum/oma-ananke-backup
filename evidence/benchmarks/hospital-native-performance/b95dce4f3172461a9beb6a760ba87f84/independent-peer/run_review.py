from pathlib import Path
from collections import Counter
import hashlib,json,os,subprocess,sys,time,xml.etree.ElementTree as ET

root=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8')
declaration=json.loads((root/'declaration.json').read_text(encoding='utf-8'))
env=dict(os.environ);env['PYTHONPATH']=str(root/'src');env['PYTHONIOENCODING']='utf-8'
args=[sys.executable,'-m','pytest','-q','-c',str(root/'pytest.ini'),'tests/test_loader_prerequisite_authority.py']
collected=subprocess.run(args+['--collect-only'],cwd=root,env=env,capture_output=True,text=True,encoding='utf-8',timeout=30)
assert collected.returncode==0
nodes=[line for line in collected.stdout.splitlines() if line.startswith('tests/') and '::' in line]
write(root/'nodes.json',nodes);start=time.perf_counter()
with (root/'final-pytest.log').open('w',encoding='utf-8') as log:
    result=subprocess.run(args+['--junitxml='+str(root/'final-tests.xml'),'--basetemp='+str(root/'final-temp')],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=60)
cases=ET.parse(root/'final-tests.xml').findall('.//testcase')
counts={key:sum(case.find(key) is not None for case in cases) for key in ('failure','error','skipped')}
exact=Counter(case.attrib['classname'].replace('.','/')+'.py::'+case.attrib['name'] for case in cases)==Counter(nodes)
unchanged=all(sha(root/name)==value for name,value in declaration['inputs'].items())
record={'status':'PASS' if result.returncode==0 and exact and unchanged else 'FAIL','tests':len(cases),**counts,'seconds':time.perf_counter()-start,'exact_nodes':exact,'frozen_inputs_unchanged':unchanged,
        'runner_sha256':sha(Path(__file__)),'xml_sha256':sha(root/'final-tests.xml'),
        'current_cad_sha256':sha(root/'src/oma/ifc/cad.py'),'legacy_cad_sha256':sha(root/'legacy_cad.py'),
        'scope':'Independent loader-level actual three-product IFC fixture; no hospital or selected7/8 geometry rerun.'}
write(root/'result.json',record);print(json.dumps(record))
assert record['status']=='PASS'
