"""Normalize the exact immutable combined declaration for the existing driver."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import uuid

STAGE=Path(__file__).resolve().parent
ROOT=STAGE.parents[2]
SOURCE='33a20d125bba02a298d12048a5b6227e51a98d8a043b999097d94a8d88b67b95'
MASTER=ROOT/'.oma/development/shared-tree-combined-validation/frozen-inputs.json'
FOCUS=ROOT/'.oma/development/shared-tree-combined-validation/validation/4b9305c8b5a14093ad7c5a7540f09fa8/result.json'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def write(path,value):Path(path).write_text(json.dumps(value,indent=2),encoding='utf-8')
assert sha(MASTER)=='d974f896a9d0f2d78ac9b03af3d91bed4419e4996417eecbbcae8d94263c3b9b'
assert sha(FOCUS)=='5e32bc947f1ad7cf3490ee5a60912a7e81d49d519b965e19ebc6bda3fbe335bb'
master=read(MASTER);focus=read(FOCUS)
assert master['checker_version']=='oma-independent-checker/2:'+SOURCE
assert focus['status']=='PASS' and focus['passed']==360
source=Path(master['source_directory'])
actual={p.relative_to(source).as_posix():sha(p) for p in source.rglob('*.py')}
assert actual==master['source_files'] and len(actual)==112
sys.path.insert(0,str(ROOT/'scripts'))
from native_package_evidence import verify_test_snapshot
inputs=verify_test_snapshot(master['input_snapshot'],master['snapshot_files'],allow_generated_evidence=True)
assert len(inputs['inputs'])==162
nodes_path=MASTER.parent/master['collection']['full']['node_manifest']
assert sha(nodes_path)==master['collection']['full']['node_manifest_sha256']
nodes=read(nodes_path)
assert len(nodes)==len(set(nodes))==2788
target=STAGE/'prepared'/uuid.uuid4().hex
target.mkdir(parents=True)
drivers={}
for name in ('native_validate_checkpoint.py','native_package_evidence.py','native_prepare.py','native_build.py','native_checkpoint_audit.py'):
    path=ROOT/'scripts'/name
    (target/'driver-sources').mkdir(exist_ok=True)
    shutil.copyfile(path,target/'driver-sources'/name)
    drivers[name]=sha(path)
shutil.copyfile(ROOT/'.oma/development/coupled-custom-validation/run.ps1',target/'run.ps1')
shutil.copyfile(__file__,target/'executed-preparation.py')
shutil.copyfile(MASTER,target/'original-frozen-inputs.json')
shutil.copyfile(FOCUS,target/'focused-pass.json')
shutil.copyfile(nodes_path,target/'test-nodes.json')
write(target/'source-files.json',actual)
write(target/'snapshot-files.json',inputs['inputs'])
declaration={'status':'FROZEN_DECLARATION_NO_NEW_TEST_RESULT','checker_version':master['checker_version'],
    'source_directory':str(source),'source_files':actual,'test_snapshot':master['input_snapshot'],
    'snapshot_files':inputs['inputs'],'test_node_count':2788,'test_nodes_sha256':sha(nodes_path),
    'original_frozen_declaration':str(MASTER),'original_frozen_declaration_sha256':sha(MASTER),
    'focused_pass_receipt':str(FOCUS),'focused_pass_receipt_sha256':sha(FOCUS),
    'scope':'Field-name normalization only from exact root-owned frozen source/input/full-node declaration; no new validation claim'}
write(target/'full-declaration.json',declaration)
wheel=read(ROOT/'evidence/dependencies/native-build/candidate-wheel.json')
preparation={'status':'FOCUSED_PASS_EXACT_CUSTOM_FULL_PREPARED','source_checkpoint':SOURCE,'source_directory':str(source),
    'expected_source_file_count':112,'expected_test_input_count':162,'expected_full_test_nodes':2788,
    'driver_source_files':drivers,'snapshot_record':str(target/'full-declaration.json'),
    'snapshot_record_sha256_at_preparation':sha(target/'full-declaration.json'),'test_nodes_sha256':sha(nodes_path),
    'test_snapshot':master['input_snapshot'],'wrapper_sha256':sha(target/'run.ps1'),
    'native_extension_sha256':wheel['variant']['native_extension_sha256'],
    'test_input_manifest_sha256':sha(target/'snapshot-files.json'),'source_manifest_sha256':sha(target/'source-files.json'),
    'launch_condition':'Root authorized launch after exact360 focusedPASS; same master source/input manifest verified',
    'package_build_started':False,'tests_started_by_preparation':False}
write(target/'preparation.json',preparation)
print(json.dumps({'directory':str(target),'sha256':sha(target/'preparation.json')}))
