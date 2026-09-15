"""Bind the original compact/factorized full snapshot to the custom-native driver."""
import hashlib,json,shutil,sys,uuid
from pathlib import Path
STAGE=Path(__file__).resolve().parent
ROOT=STAGE.parents[2]
SOURCE='f73a8793ae0df76d9ec53400cec18b05d2731f63c735b225c2246fee62df6b21'
ORIGIN=ROOT/'.oma/development/factorized-tree-pressure/combined-validation/d6d1204384b84bc6b0a5c5e47c5540ad'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,v):Path(p).write_text(json.dumps(v,indent=2),encoding='utf-8')
r=read(ORIGIN/'result.json'); inputs=read(ORIGIN/'inputs.json')['files']; nodes=read(ORIGIN/'test-nodes.json')
assert r['checker_version']=='oma-independent-checker/2:'+SOURCE
assert len(nodes)==len(set(nodes))==r['test_node_count']==3275
assert sha(ORIGIN/'test-nodes.json')==r['exact_collected_nodes_sha256']=='d59cd1439a9fc33a60c844c8fc5e2c2d7fab4e95ddec16ca35e6926932124712'
source=Path(r['source_directory']); origin=Path(r['snapshot'])
assert {p.relative_to(source).as_posix():sha(p) for p in source.rglob('*.py')}==r['source_files']
assert len(r['source_files'])==114 and inputs==r['snapshot_files']
sys.path.insert(0,str(ROOT/'scripts'))
from native_package_evidence import verify_test_snapshot
verify_test_snapshot(origin,inputs,allow_generated_evidence=True)
target=STAGE/'prepared'/uuid.uuid4().hex;target.mkdir(parents=True)
(target/'driver-sources').mkdir()
drivers={}
for name in ('native_validate_checkpoint.py','native_package_evidence.py','native_prepare.py','native_build.py','native_checkpoint_audit.py'):
    p=ROOT/'scripts'/name;shutil.copyfile(p,target/'driver-sources'/name);drivers[name]=sha(p)
shutil.copyfile(ROOT/'.oma/development/coupled-custom-validation/run.ps1',target/'run.ps1')
shutil.copyfile(__file__,target/'executed-preparation.py')
for name in ('result.json','inputs.json','source.json','native-environment.json'):
    shutil.copyfile(ORIGIN/name,target/('original-'+name))
shutil.copyfile(ORIGIN/'test-nodes.json',target/'test-nodes.json')
write(target/'source-files.json',r['source_files']);write(target/'snapshot-files.json',inputs)
d={'status':'FROZEN_DECLARATION_NO_NEW_TEST_RESULT','checker_version':r['checker_version'],
   'source_directory':str(source),'source_files':r['source_files'],'test_snapshot':str(origin),
   'snapshot_files':inputs,'test_node_count':3275,'test_nodes_sha256':sha(ORIGIN/'test-nodes.json'),
   'original_receipt':str(ORIGIN/'result.json'),'original_receipt_sha256_at_preparation':sha(ORIGIN/'result.json'),
   'scope':'Field-name normalization; original full run may still be running. Exact source/input/node identities copied independently.'}
write(target/'full-declaration.json',d)
p={'status':'EXACT_CUSTOM_FULL_PREPARED','source_checkpoint':SOURCE,'source_directory':str(source),
   'expected_source_file_count':114,'expected_test_input_count':len(inputs),'expected_full_test_nodes':3275,
   'driver_source_files':drivers,'snapshot_record':str(target/'full-declaration.json'),
   'snapshot_record_sha256_at_preparation':sha(target/'full-declaration.json'),
   'test_nodes_sha256':sha(target/'test-nodes.json'),'test_snapshot':str(origin),'wrapper_sha256':sha(target/'run.ps1'),
   'test_input_manifest_sha256':sha(target/'snapshot-files.json'),'source_manifest_sha256':sha(target/'source-files.json'),
   'launch_condition':'Root authorized independent exact custom-native full run in parallel with original full',
   'package_build_started':False,'tests_started_by_preparation':False}
write(target/'preparation.json',p)
print(json.dumps({'directory':str(target),'sha256':sha(target/'preparation.json'),'inputs':len(inputs)}))
