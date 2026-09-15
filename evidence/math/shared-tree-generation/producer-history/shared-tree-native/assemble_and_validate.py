"""Exact frozen integration from the prior full suite and pinned new components."""
from pathlib import Path
import hashlib,importlib.util,json,shutil,subprocess,sys,time,uuid

p=Path(__file__).resolve().parent
root=next(x for x in p.parents if (x/'AGENTS.md').is_file())
sys.path.insert(0,str(p/'src'))
from oma.build_identity import frozen_environment
phase=sys.argv[1] if len(sys.argv)>1 else 'focused'
assert phase in ('focused','full')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
out=p/'integration-validation'/uuid.uuid4().hex;out.mkdir(parents=True)
snapshot=out/'snapshot';snapshot.mkdir()
base=root/'evidence/release/coupled-tree-full-17ea63bc503a4b78bb572ffee1dce06f/result.json'
prior=json.loads(base.read_text(encoding='utf8'))
assert prior['status']=='PASS' and prior['passed']==2467 and len(prior['snapshot_files'])==131
inputs={};origins={}
def copy_input(source,relative,expected):
    assert source.is_file() and sha(source)==expected,source
    target=snapshot/relative
    assert not target.exists(),target
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    assert sha(target)==expected
    inputs[relative]=expected;origins[relative]=str(source)
for relative,expected in prior['snapshot_files'].items():copy_input(Path(prior['test_snapshot'])/relative,relative,expected)
for source in sorted((p/'tests').glob('*.py')):copy_input(source,'tests/'+source.name,sha(source))
kernel=p.parent/'shared-tree-synthesis'
handoff_path=kernel/'evidence/math/shared-tree-synthesis/handoff.json'
handoff=json.loads(handoff_path.read_text(encoding='utf8'))
assert handoff['module_sha256']=='0034130d057fbb012d031fb31a69ce89aac857ce6aeaf4d8a73f55c2d1a23d43'
assert sha(p/'src/oma/optimization/shared_tree_synthesis.py')==handoff['module_sha256']
for item in handoff['merge_files']:
    if item['path'].startswith('tests/'):
        copy_input(kernel/'runtimes'/handoff['component_source_root']/item['path'],item['path'],item['sha256'])
verifier=p.parent/'shared-tree-native-checker'
checked_path=verifier/'validation/6ee4dfcb1f67409baee0be07f8a986cd/result.json'
checked=json.loads(checked_path.read_text(encoding='utf8'))
assert checked['status']=='PASS' and checked['testcases']==94
assert sha(p/'src/oma/routing/shared_tree_catalogue_check.py')==checked['module_sha256']=='688cb03a0c75f23ee07e3e4b668980ec7d94267337b6c0f9b7ac4e5309045f7b'
for item in checked['files']:
    if item['path'].startswith('tests/'):
        copy_input(verifier/'runtimes'/checked['source_root']/item['path'],item['path'],item['sha256'])
assert len(inputs)==145,len(inputs)
env=frozen_environment(p)
source_dir=Path(env['PYTHONPATH'])
sources={x.relative_to(source_dir).as_posix():sha(x) for x in source_dir.rglob('*.py')}
assert len(sources)==112
prior_sources={'oma/'+k:v for k,v in prior['source_files'].items()}
source_changes={k:sources[k] for k in sources if sources[k]!=prior_sources.get(k)}
assert set(source_changes)=={
    'oma/api.py','oma/worker.py','oma/optimization/shared_tree_synthesis.py',
    'oma/routing/shared_tree_requirements.py','oma/routing/shared_tree_proposals.py',
    'oma/routing/shared_tree_catalogue_check.py','oma/routing/shared_tree_job.py'}
assert set(prior_sources)<=set(sources)
if phase=='full':
    focused_path=p/'integration-validation/ed63904f61f6439e9f68c488e44d7b70/result.json'
    focused=json.loads(focused_path.read_text(encoding='utf8'))
    assert focused['status']=='PASS' and focused['passed']==268
    assert focused['source_files']==sources and focused['snapshot_files']==inputs
shutil.copyfile(__file__,out/'runner.py')
helper=root/'evidence/release/pressure-package-harness-peer-review/audit_completed_suites.py'
shutil.copyfile(helper,out/'inventory-helper.py')
spec=importlib.util.spec_from_file_location('exact_inventory',out/'inventory-helper.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
write(out/'input-manifest.json',{'files':inputs,'origins':origins})
write(out/'source-manifest.json',sources)
selected=['tests'] if phase=='full' else ['tests/'+x for x in (
    'test_shared_tree_synthesis.py','test_shared_tree_catalogue_check.py','test_shared_tree_proposals.py',
    'test_shared_tree_job.py','test_shared_tree_generated_workflow.py','test_api.py',
    'test_worker_control.py','test_worker_control_polling.py','test_service_contained_workers.py',
    'test_service_start_shutdown.py','test_coupled_tree_integration.py')]
prefix=[sys.executable,'-m','pytest','-q','-o','pythonpath='+str(source_dir)]
collection=subprocess.run([*prefix,*selected,'--collect-only'],cwd=snapshot,env=env,text=True,encoding='utf8',
    stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
(out/'collection.log').write_text(collection.stdout,encoding='utf8')
assert collection.returncode==0,collection.stdout
nodes=[s.strip() for s in collection.stdout.splitlines() if s.startswith('tests/') and '::' in s]
assert len(nodes)==len(set(nodes)) and len(nodes)>229,len(nodes)
if phase=='full':assert len(nodes)==2696,len(nodes)
write(out/'test-nodes.json',nodes)
command=[*prefix,*selected,'--junitxml='+str(out/'tests.xml'),'--basetemp='+str(out/'native-stores')]
result={'status':'RUNNING','phase':phase,'checker_version':env['OMA_EXECUTABLE_BUILD'],'source_directory':str(source_dir),
    'source_files':sources,'snapshot_files':inputs,'test_snapshot':str(snapshot),'test_node_count':len(nodes),'command':command,
    'source_changes_from_prior_full':source_changes,
    'runner_sha256':sha(out/'runner.py'),'inventory_helper_sha256':sha(out/'inventory-helper.py'),
    'input_manifest_sha256':sha(out/'input-manifest.json'),'source_manifest_sha256':sha(out/'source-manifest.json'),
    'test_nodes_sha256':sha(out/'test-nodes.json'),'prior_full_receipt_sha256':sha(base),
    'kernel_handoff_sha256':sha(handoff_path),'verifier_receipt_sha256':sha(checked_path)}
write(out/'result.json',result)
print(json.dumps({k:result[k] for k in ('status','phase','checker_version','test_node_count','test_snapshot')}),flush=True)
start=time.perf_counter()
with (out/'pytest.log').open('w',encoding='utf8') as log:
    completed=subprocess.run(command,cwd=snapshot,env=env,stdout=log,stderr=subprocess.STDOUT)
result.update(returncode=completed.returncode,seconds=time.perf_counter()-start)
try:
    assert completed.returncode==0
    exact=audit.account_xml(out/'tests.xml',nodes)
    assert all(sha(snapshot/k)==h for k,h in inputs.items())
    assert {x.relative_to(source_dir).as_posix():sha(x) for x in source_dir.rglob('*.py')}==sources
    result.update(status='PASS',passed=exact['passed'],failures=0,skipped=0,
        exact_case_identities_checked=True,snapshot_unchanged=True,frozen_source_unchanged=True,test_xml_sha256=exact['xml_sha256'])
    if phase=='full':
        inventory=audit.snapshot(snapshot,inputs)
        write(out/'completed-inventory.json',inventory)
        result['completed_inventory_sha256']=sha(out/'completed-inventory.json')
        result['derived_test_outputs']=inventory['derived_output_sha256']
except BaseException as exc:result.update(status='FAIL',error=repr(exc))
write(out/'result.json',result)
print(json.dumps({k:v for k,v in result.items() if k not in ('source_files','snapshot_files','command')}),flush=True)
raise SystemExit(0 if result['status']=='PASS' else 1)
