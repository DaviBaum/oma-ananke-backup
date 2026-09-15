"""Persistent original-native focused/full runner over the exact frozen inventory."""
from pathlib import Path
import hashlib,importlib.util,json,os,shutil,subprocess,sys,time,traceback,uuid
import xml.etree.ElementTree as ET

STAGE=Path(__file__).resolve().parent
phase=sys.argv[1] if len(sys.argv)>1 else 'focused';assert phase in ('focused','full')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
frozen=read(STAGE/'frozen-inputs.json');assert frozen['status']=='FROZEN'
out=STAGE/'validation'/uuid.uuid4().hex;out.mkdir(parents=True)
result={'schema':'oma.exact-combined-shared-tree-native-validation/1','status':'PREPARING','phase':phase,
 'checker_version':frozen['checker_version'],'source_directory':frozen['source_directory'],
 'source_files':frozen['source_files'],'snapshot_files':frozen['snapshot_files'],
 'source_count':112,'input_count':162,'frozen_input_receipt_sha256':sha(STAGE/'frozen-inputs.json'),
 'runner_pid':os.getpid(),'started_unix':time.time()}
write(out/'result.json',result);write(STAGE/(phase+'-active.json'),{'directory':str(out),'pid':os.getpid(),'phase':phase})
shutil.copyfile(__file__,out/'runner.py');shutil.copyfile(STAGE/'inventory-helper.py',out/'inventory-helper.py')
start=time.perf_counter()
try:
 source_directory=Path(frozen['source_directory']);master=Path(frozen['input_snapshot']);inputs=frozen['snapshot_files']
 assert len(inputs)==162 and len(frozen['source_files'])==112
 assert {p.relative_to(source_directory).as_posix():sha(p) for p in source_directory.rglob('*.py')}==frozen['source_files']
 assert all(sha(master/key)==value for key,value in inputs.items())
 assert sha(STAGE/'inventory-helper.py')==frozen['inventory_helper_sha256']
 assert sha(STAGE/'input-manifest.json')==frozen['input_manifest_sha256']
 assert sha(STAGE/'source-manifest.json')==frozen['source_manifest_sha256']
 if phase=='full':
  focus=read(STAGE/'focused-complete.json');focused=read(Path(focus['directory'])/'result.json')
  assert focused['status']=='PASS' and focused['passed']==360
  assert focused['source_files']==frozen['source_files'] and focused['snapshot_files']==inputs
 snapshot=out/'snapshot';snapshot.mkdir()
 for key,value in inputs.items():
  target=snapshot/key;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(master/key,target)
  assert sha(target)==value
 nodes=read(STAGE/frozen['collection'][phase]['node_manifest'])
 assert sha(STAGE/frozen['collection'][phase]['node_manifest'])==frozen['collection'][phase]['node_manifest_sha256']
 assert len(nodes)==len(set(nodes))==(360 if phase=='focused' else 2788)
 write(out/'test-nodes.json',nodes)
 shutil.copyfile(STAGE/'input-manifest.json',out/'input-manifest.json');shutil.copyfile(STAGE/'source-manifest.json',out/'source-manifest.json')
 sys.path.insert(0,str(source_directory))
 from oma.build_identity import checker_version
 assert checker_version()==frozen['checker_version']
 env=os.environ.copy();env['PYTHONPATH']=str(source_directory);env['OMA_EXECUTABLE_BUILD']=frozen['checker_version'];env['PYTHONUNBUFFERED']='1';env['PYTHONIOENCODING']='utf-8'
 # This is the same original interpreter/native environment as the retained33a
 # run, not the peer's custom native build. Retain loaded extension identities.
 import ifcopenshell,OCP
 native_files={name:{'path':module.__file__,'sha256':sha(Path(module.__file__))}
  for name,module in sorted(sys.modules.items()) if (name.startswith('ifcopenshell') or name.startswith('OCP'))
  and getattr(module,'__file__',None) and str(module.__file__).lower().endswith(('.pyd','.dll'))}
 write(out/'native-environment.json',{'python':sys.executable,'python_sha256':sha(Path(sys.executable)),
  'python_version':sys.version,'native_extensions':native_files,'checker_version':checker_version()})
 selected=frozen['collection'][phase]['selection']
 prefix=[sys.executable,'-m','pytest','-q','-o','pythonpath='+source_directory.as_posix()]
 collect=subprocess.run([*prefix,*selected,'--collect-only'],cwd=snapshot,env=env,capture_output=True,text=True,encoding='utf-8',timeout=120)
 (out/'collection.log').write_text(collect.stdout+collect.stderr,encoding='utf-8')
 assert collect.returncode==0
 observed=[line.strip() for line in collect.stdout.splitlines() if line.startswith('tests/') and '::' in line]
 assert observed==nodes,'Collected node sequence differs from frozen manifest'
 command=[*prefix,*selected,'--junitxml='+str(out/'tests.xml'),'--basetemp='+str(out/'native-stores')]
 result.update(status='RUNNING',test_snapshot=str(snapshot),test_node_count=len(nodes),command=command,
  exact_collection_verified=True,runner_sha256=sha(out/'runner.py'),inventory_helper_sha256=sha(out/'inventory-helper.py'),
  node_manifest_sha256=sha(out/'test-nodes.json'),native_environment_sha256=sha(out/'native-environment.json'))
 write(out/'result.json',result)
 print(json.dumps({'status':'RUNNING','phase':phase,'tests':len(nodes),'directory':str(out),'source':frozen['checker_version']}),flush=True)
 test_start=time.perf_counter()
 with (out/'pytest.log').open('w',encoding='utf-8') as log:
  run=subprocess.run(command,cwd=snapshot,env=env,stdout=log,stderr=subprocess.STDOUT)
 result.update(returncode=run.returncode,test_seconds=time.perf_counter()-test_start)
 spec=importlib.util.spec_from_file_location('exact_inventory',out/'inventory-helper.py')
 audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
 if (out/'tests.xml').exists():
  xml=ET.parse(out/'tests.xml').getroot()
  result['observed_xml_counts']={name:len(xml.findall('.//'+name)) for name in ('testcase','failure','error','skipped')}
 assert run.returncode==0,'pytest returned nonzero'
 exact=audit.account_xml(out/'tests.xml',nodes)
 assert all(sha(snapshot/key)==value for key,value in inputs.items())
 assert all(sha(master/key)==value for key,value in inputs.items())
 assert {p.relative_to(source_directory).as_posix():sha(p) for p in source_directory.rglob('*.py')}==frozen['source_files']
 if phase=='full':
  inventory=audit.snapshot(snapshot,inputs);write(out/'completed-inventory.json',inventory)
  result.update(completed_inventory_sha256=sha(out/'completed-inventory.json'),derived_test_outputs=inventory['derived_output_sha256'])
 else:
  unexpected=[p.relative_to(snapshot).as_posix() for p in snapshot.rglob('*') if p.is_file()
   and p.relative_to(snapshot).as_posix() not in inputs and not {'__pycache__','.pytest_cache'}.intersection(p.relative_to(snapshot).parts)]
  assert not unexpected,unexpected
 result.update(status='PASS',passed=exact['passed'],failures=0,errors=0,skipped=0,
  exact_case_identities_checked=True,snapshot_unchanged=True,master_unchanged=True,frozen_source_unchanged=True,test_xml_sha256=exact['xml_sha256'])
except BaseException as error:
 result.update(status='FAIL',error=repr(error),traceback=traceback.format_exc())
finally:
 result.update(seconds=time.perf_counter()-start,completed_unix=time.time())
 write(out/'result.json',result)
 write(STAGE/(phase+'-complete.json'),{'directory':str(out),'status':result['status'],'result_sha256':sha(out/'result.json')})
 print(json.dumps({key:value for key,value in result.items() if key in ('status','phase','passed','error','seconds','test_seconds','observed_xml_counts')}),flush=True)
raise SystemExit(0 if result['status']=='PASS' else 1)
