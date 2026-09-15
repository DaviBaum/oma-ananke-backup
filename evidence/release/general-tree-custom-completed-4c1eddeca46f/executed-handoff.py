"""Retain exact completed custom EDF evidence without rerunning any check."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
FULL=ROOT/'evidence/dependencies/native-build/checkpoint-validation/edf555760245-4c1eddeca46f'
ORIGINAL=ROOT/'.oma/development/general-shared-tree-native/combined-validation/a29404ec828e4919b8968959019b8eb8'
PREP=ROOT/'.oma/development/general-tree-custom/prepared/2ac8b31cd0884aa6a2822419efd18288'
SUPPLEMENT=ROOT/'evidence/release/general-tree-package-harness/431a2bdce9c64ca0a9b8d5ba572d6a32'
OUT=ROOT/'evidence/release/general-tree-custom-completed-4c1eddeca46f'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def identity(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
r=read(FULL/'result.json');audit=read(FULL/'post-run-exact-audit.json');o=read(ORIGINAL/'result.json')
assert r['status']=='CUSTOM_NATIVE_NEW_CHECKPOINT_FULL_SUITE_PASS' and r['passed']==3012
assert audit['result_sha256']==sha(FULL/'result.json') and audit['test_input_files']==264
assert o['status']=='PASS' and o['test_node_count']==3012
assert read(PREP/'exit.json')['exit_code']==0 and read(SUPPLEMENT/'result.json')['status']=='PASS'
candidate=read(FULL/'identity-comparison.json')['candidate']
direct=Path(r['kernel_direct_load']['path'])
assert direct.resolve()==(Path(r['runtime']['PYTHONPATH'])/'oma/optimization/shared_tree_synthesis.py').resolve()
assert sha(direct)==r['kernel_direct_load']['sha256']==candidate['source_files']['optimization/shared_tree_synthesis.py']
assert r['driver_bytes_unchanged'] is True
OUT.mkdir(exist_ok=False)
for p in FULL.rglob('*'):
    if p.is_file():
        target=OUT/'custom-full'/p.relative_to(FULL);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
for name in ('preparation.json','launch-provenance.json','launcher.json','exit.json','stdout.log','stderr.log','run.ps1','executed-preparation.py'):
    shutil.copyfile(PREP/name,OUT/name)
shutil.copyfile(ORIGINAL/'result.json',OUT/'original-full-pass.json')
shutil.copyfile(__file__,OUT/'executed-handoff.py')
commands={}
for key in ('test_collection_record','test_suite_record'):
    directory=Path(r[key]).parent
    assert read(directory/'record.json')['status']=='PASS'
    assert sha(directory/'output.log')==read(directory/'record.json')['log_sha256']
    commands[key]=identity(directory/'record.json')
    shutil.copytree(directory,OUT/'commands'/directory.name)
result={'status':'EXACT_EDF_CUSTOM_NATIVE_3012_PASS_AND_CURRENT_DRIVER_SUPPLEMENT_PASS',
    'source_checkpoint':r['source_checkpoint'],'checker_version':r['runtime']['OMA_EXECUTABLE_BUILD'],
    'native_extension_sha256':r['native_extension_sha256'],'original_full':identity(ORIGINAL/'result.json'),
    'custom_full':identity(FULL/'result.json'),'custom_audit':identity(FULL/'post-run-exact-audit.json'),
    'test_nodes':3012,'test_input_files':264,'source_files':112,'failed':0,'skipped':0,
    'kernel_direct_load':r['kernel_direct_load'],'commands':commands,
    'current_driver_supplement':identity(SUPPLEMENT/'result.json'),'supplement_cases':121,
    'scope':'Original and custom exact3012 inventories match. Separate121 package-harness supplement uses2 finaldriver support-file replacements; not an additional3012 native run or a new unique-case union.',
    'package_status':'Preparation/build managed separately; this is not a bundled PASS or seal claim.',
    'original_inputs_modified':False,'active_runtime_modified':False,'tests_rerun_for_audit':False}
files={p.relative_to(OUT).as_posix():sha(p) for p in OUT.rglob('*') if p.is_file()}
result['retained_files']=files
(OUT/'handoff.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({'directory':str(OUT),'handoff_sha256':sha(OUT/'handoff.json'),'files':len(files)}))
