"""Assemble exact immutable 33a source and combined original-native test inventory."""
from pathlib import Path
import difflib,hashlib,json,shutil,subprocess,sys

STAGE=Path(__file__).resolve().parent;ROOT=STAGE.parents[2]
BASE=ROOT/'.oma/development/shared-tree-native/integration-validation/0c61106b1aba4f8b81552bd5e201b9a9'
NATIVE=ROOT/'.oma/development/shared-tree-coupled/validation/0b39284a65564d34b94af6500453051b'
EXT=ROOT/'.oma/development/shared-tree-coupled-checker'
VERSION='oma-independent-checker/2:33a20d125bba02a298d12048a5b6227e51a98d8a043b999097d94a8d88b67b95'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
base=read(BASE/'result.json');native=read(NATIVE/'result.json');extension=read(EXT/'validation/54efc47c0e9243fda34e92526cda3f9c/result.json')
assert base['status']=='PASS' and base['passed']==2696 and len(base['snapshot_files'])==145
assert native['status']=='PASS' and native['checker_version']==VERSION and len(native['source_files'])==112
assert extension['status']=='PASS' and extension['testcases']==164 and extension['module_sha256']=='c800938e03909fcbe8a014e21b46c9640ddf5736fe3684f345bdd57a5bfb7fd4'
for relative,expected in native['source_files'].items():
 source=Path(native['source_directory'])/relative;target=STAGE/'src'/relative
 assert sha(source)==expected
 target.parent.mkdir(parents=True,exist_ok=True)
 if target.exists():assert sha(target)==expected
 else:shutil.copyfile(source,target)
inputs={};origins={};master=STAGE/'input-snapshot';master.mkdir(exist_ok=True)
def copy_input(source,relative,expected,replace=False):
 assert sha(source)==expected,source
 target=master/relative;target.parent.mkdir(parents=True,exist_ok=True)
 if relative in inputs and not replace:
  assert inputs[relative]==expected and sha(target)==expected,(relative,'conflicting input')
  return
 if target.exists() and not replace:assert sha(target)==expected
 else:shutil.copyfile(source,target)
 inputs[relative]=expected;origins[relative]=str(source)
for relative,expected in base['snapshot_files'].items():copy_input(Path(base['test_snapshot'])/relative,relative,expected)
changes=[]
for relative in ('tests/test_shared_tree_proposals.py',):
 source=NATIVE/relative;expected=native['input_files'][relative]
 original=(master/relative).read_bytes();changed=source.read_bytes()
 retained=STAGE/'retained-adjustments'/Path(relative).name;retained.mkdir(parents=True,exist_ok=True)
 (retained/'original.py').write_bytes(original);(retained/'replacement.py').write_bytes(changed)
 (retained/'change.diff').write_text(''.join(difflib.unified_diff(original.decode('utf-8').splitlines(True),changed.decode('utf-8').splitlines(True),fromfile='base145/'+relative,tofile='frozen33a/'+relative)),encoding='utf-8')
 copy_input(source,relative,expected,replace=True)
 changes.append({'path':relative,'before':hashlib.sha256(original).hexdigest(),'after':expected,'reason':'Exact frozen33a test replacement; unsupported-profile fixture now refers to still-unsupported passive mode'})
relative='tests/test_shared_tree_job.py';original=(master/relative).read_bytes()
old=b"if fault=='pressure_identity':query['requirements']['coupled_tree']={'not':'implemented'}"
new=b"if fault=='pressure_identity':query['requirements']['passive_tree']={'not':'implemented'}"
assert original.count(old)==1
changed=original.replace(old,new)
retained=STAGE/'retained-adjustments'/Path(relative).name;retained.mkdir(parents=True,exist_ok=True)
(retained/'original.py').write_bytes(original);(retained/'replacement.py').write_bytes(changed)
(retained/'change.diff').write_text(''.join(difflib.unified_diff(original.decode('utf-8').splitlines(True),changed.decode('utf-8').splitlines(True),fromfile='base145/'+relative,tofile='combined/'+relative)),encoding='utf-8')
(master/relative).write_bytes(changed);inputs[relative]=sha(master/relative);origins[relative]=str(retained/'replacement.py')
changes.append({'path':relative,'before':hashlib.sha256(original).hexdigest(),'after':inputs[relative],'reason':'Only unsupported pressure_identity fixture discriminator coupled_tree -> passive_tree; coupled mode is now implemented'})
for relative in ('tests/shared_tree_coupled_fixture.py','tests/test_shared_tree_coupled_proposals.py','tests/test_shared_tree_coupled_workflow.py',
                 'tests/native_shared_tree_reference.py','tests/fixtures/coupled-native-tree/boundary.json'):
 copy_input(NATIVE/relative,relative,native['input_files'][relative])
for item in extension['files']:
 if item['path'].startswith('tests/'):
  copy_input(EXT/'runtimes'/extension['source_root']/item['path'],item['path'],item['sha256'])
assert len(inputs)==162,len(inputs)
assert {p.relative_to(master).as_posix():sha(p) for p in master.rglob('*') if p.is_file()}==inputs
assert inputs['tests/test_shared_tree_catalogue_check.py']==base['snapshot_files']['tests/test_shared_tree_catalogue_check.py']
shutil.copyfile(BASE/'inventory-helper.py',STAGE/'inventory-helper.py')
sys.path.insert(0,str(STAGE/'src'))
from oma.build_identity import frozen_environment
env=frozen_environment(STAGE);assert env['OMA_EXECUTABLE_BUILD']==VERSION
source_directory=Path(env['PYTHONPATH'])
sources={p.relative_to(source_directory).as_posix():sha(p) for p in source_directory.rglob('*.py')}
assert sources==native['source_files']
selected=['tests/'+name for name in ('test_shared_tree_synthesis.py','test_shared_tree_catalogue_check.py','test_shared_tree_proposals.py',
 'test_shared_tree_job.py','test_shared_tree_generated_workflow.py','test_api.py','test_worker_control.py','test_worker_control_polling.py',
 'test_service_contained_workers.py','test_service_start_shutdown.py','test_coupled_tree_integration.py',
 'test_shared_tree_coupled_proposals.py','test_shared_tree_coupled_workflow.py','test_shared_tree_coupled_catalogue_check.py')]
write(STAGE/'input-manifest.json',{'files':inputs,'origins':origins,'adjustments':changes})
write(STAGE/'source-manifest.json',sources)
collection={}
for phase,selection,expected in (('focused',selected,360),('full',['tests'],2788)):
 command=[sys.executable,'-m','pytest','-q','-o','pythonpath='+source_directory.as_posix(),*selection,'--collect-only']
 run=subprocess.run(command,cwd=master,env=env,capture_output=True,text=True,encoding='utf-8',timeout=120)
 (STAGE/(phase+'-collection.log')).write_text(run.stdout+run.stderr,encoding='utf-8')
 assert run.returncode==0,run.stdout+run.stderr
 nodes=[line.strip() for line in run.stdout.splitlines() if line.startswith('tests/') and '::' in line]
 assert len(nodes)==len(set(nodes))==expected,(phase,len(nodes),expected)
 write(STAGE/(phase+'-test-nodes.json'),nodes)
 collection[phase]={'selection':selection,'nodes':len(nodes),'node_manifest':phase+'-test-nodes.json','node_manifest_sha256':sha(STAGE/(phase+'-test-nodes.json'))}
manifest={'schema':'oma.combined-shared-tree-validation-inputs/1','status':'FROZEN','checker_version':VERSION,
 'source_directory':str(source_directory),'source_files':sources,'source_count':len(sources),
 'input_snapshot':str(master),'snapshot_files':inputs,'input_count':len(inputs),'collection':collection,
 'base_full_receipt':str(BASE/'result.json'),'base_full_receipt_sha256':sha(BASE/'result.json'),
 'native54_receipt':str(NATIVE/'result.json'),'native54_receipt_sha256':sha(NATIVE/'result.json'),
 'extension164_receipt_sha256':sha(EXT/'validation/54efc47c0e9243fda34e92526cda3f9c/result.json'),
 'input_manifest_sha256':sha(STAGE/'input-manifest.json'),'source_manifest_sha256':sha(STAGE/'source-manifest.json'),
 'inventory_helper_sha256':sha(STAGE/'inventory-helper.py'),'prepare_script_sha256':sha(Path(__file__)),
 'allowed_full_derived_outputs':6,'production_or_root_stage_modified':False}
write(STAGE/'frozen-inputs.json',manifest)
print(json.dumps({'status':'FROZEN','checker_version':VERSION,'source_count':len(sources),'input_count':len(inputs),'collection':collection,'frozen_inputs_sha256':sha(STAGE/'frozen-inputs.json')}))
