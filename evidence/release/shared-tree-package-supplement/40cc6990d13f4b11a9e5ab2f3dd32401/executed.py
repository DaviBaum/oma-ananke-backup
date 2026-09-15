"""Current-tree package regression and complete collection reconciliation input."""
import hashlib,json,os,subprocess,sys,time,uuid,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'evidence/release/shared-tree-package-supplement'/uuid.uuid4().hex
OUT.mkdir(parents=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inventory():
 return {p.relative_to(ROOT).as_posix():sha(p) for name in ['src/oma','tests','scripts'] for p in (ROOT/name).rglob('*') if p.is_file() and p.suffix in ('.py','.json') and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts}
def write(name,d): (OUT/name).write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8',newline='\n')
env=dict(os.environ,PYTHONPATH=str(ROOT/'src'))
env.pop('OMA_COUPLED_PACKAGE_STORE',None);env.pop('OMA_COUPLED_PACKAGE_CANDIDATE',None)
before=inventory();write('inputs-before.json',before)
(OUT/'executed.py').write_bytes(Path(__file__).read_bytes())
selected=['tests/test_native_command_evidence.py','tests/test_native_package_evidence.py','tests/test_native_package_three_roles.py','tests/test_native_coupled_package_adversarial.py']
if sys.argv[1:]:
 selected=sys.argv[1:]
 assert selected==['tests/test_physical_report_admission.py','tests/test_native_real_model_validation_script.py']
expected_count=75 if sys.argv[1:] else 121
for label,args in [('complete-current-collection',[]),('supplement-collection',selected)]:
 p=subprocess.run([sys.executable,'-m','pytest',*args,'--collect-only','-q'],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8')
 (OUT/(label+'.log')).write_text(p.stdout+p.stderr,encoding='utf-8')
 assert p.returncode==0,p.stdout[-1000:]
 nodes=[x.strip() for x in p.stdout.splitlines() if x.startswith('tests/') and '::' in x]
 assert len(nodes)==len(set(nodes)) and nodes
 write(label+'.json',nodes)
 if args:assert len(nodes)==expected_count;expected_nodes=nodes
write('result.json',{'status':'RUNNING','selected_tests':selected,'expected_cases':len(expected_nodes),'source_files':{k:v for k,v in before.items() if k.startswith('src/oma/')}})
started=time.monotonic()
with (OUT/'pytest.log').open('w',encoding='utf-8') as log:
 p=subprocess.run([sys.executable,'-m','pytest',*selected,'-q','--junitxml='+str(OUT/'tests.xml'),'--basetemp='+str(OUT/'native-stores')],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
elapsed=time.monotonic()-started
after=inventory();write('inputs-after.json',after)
assert before==after,'Source/test/script mutation'
root=ET.parse(OUT/'tests.xml').getroot();cases=list(root.iter('testcase'))
actual=[c.attrib['classname'].replace('.','/')+'.py::'+c.attrib['name'] for c in cases]
assert sorted(actual)==sorted(expected_nodes)
failures=sum(c.find('failure') is not None or c.find('error') is not None for c in cases)
skipped=sum(c.find('skipped') is not None for c in cases)
write('result.json',{'status':'PASS' if p.returncode==0 and not failures and not skipped else 'FAIL','returncode':p.returncode,'passed':len(cases)-failures-skipped,'failures':failures,'skipped':skipped,'seconds':elapsed,'source_test_script_unchanged':True,'exact_node_multiset':True,'inputs_sha256':sha(OUT/'inputs-before.json'),'xml_sha256':sha(OUT/'tests.xml'),'scope':str(expected_count)+' current packaging/admission cases on integrated33a original-native runtime; separately complements frozen2788 combined suite'})
print(str(OUT));print((OUT/'result.json').read_text(encoding='utf-8'))
