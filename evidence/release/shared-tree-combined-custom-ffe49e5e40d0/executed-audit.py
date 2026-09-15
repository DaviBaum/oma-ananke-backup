"""Finish the retained exact native run without rerunning any test."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
PREP=ROOT/'.oma/development/shared-tree-combined-custom/prepared/bdbb3f67a9784151aa726593deaaf8aa'
RESULT=ROOT/'evidence/dependencies/native-build/checkpoint-validation/33a20d125bba-ffe49e5e40d0/result.json'
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def identity(path):return {'path':str(Path(path).resolve()),'sha256':sha(path)}
prepared=read(PREP/'preparation.json');result=read(RESULT);exit_record=read(PREP/'exit.json')
assert exit_record['status']=='WRAPPER_EXIT_OBSERVED' and exit_record['exit_code']==0
assert result['status']=='CUSTOM_NATIVE_NEW_CHECKPOINT_FULL_SUITE_PASS'
assert result['source_checkpoint']==prepared['source_checkpoint']
assert result['passed']==result['test_node_count']==prepared['expected_full_test_nodes']==2788
assert result['failed']==result['skipped']==0 and result['driver_bytes_unchanged'] is True
for name,value in prepared['driver_source_files'].items():
    assert sha(ROOT/'scripts'/name)==sha(PREP/'driver-sources'/name)==value
source=Path(prepared['source_directory'])
files={p.relative_to(source).as_posix():sha(p) for p in source.rglob('*.py')}
assert files==read(PREP/'source-files.json') and len(files)==112
master=read(PREP/'original-frozen-inputs.json')
assert sha(master['base_full_receipt'])==master['base_full_receipt_sha256']
assert sha(ROOT/'.oma/development/shared-tree-combined-validation/frozen-inputs.json')==sha(PREP/'original-frozen-inputs.json')
assert master['source_files']==files and master['snapshot_files']==read(PREP/'snapshot-files.json')
declaration=read(RESULT.parent/'declared-test-snapshot.json')
assert declaration==read(PREP/'full-declaration.json')
assert read(RESULT.parent/'declared-test-nodes.json')==read(PREP/'test-nodes.json')
audit=RESULT.parent/'post-run-exact-audit.json'
if not audit.exists():
    command=[str(ROOT/'.venv/Scripts/python.exe'),str(ROOT/'scripts/native_checkpoint_audit.py'),'--result',str(RESULT)]
    completed=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=120)
    (PREP/'audit-output.log').write_text(completed.stdout+completed.stderr,encoding='utf-8')
    assert completed.returncode==0,completed.stdout+completed.stderr
exact=read(audit)
assert exact['status']=='EXISTING_NATIVE_RUN_EXACT_INPUT_NODE_XML_IDENTITY_AUDIT_PASS'
assert exact['result_sha256']==sha(RESULT) and exact['tests_rerun'] is False
assert (exact['test_node_count'],exact['test_input_files'],exact['source_python_files'])==(2788,162,112)
assert len(exact['copied_snapshot']['generated_evidence'])==6
identity_record=read(RESULT.parent/'identity-comparison.json')
bare={k.removeprefix('oma/'):v for k,v in files.items()}
assert identity_record['original']['source_files']==identity_record['candidate']['source_files']==bare
assert identity_record['original']['checker_version']=='oma-independent-checker/2:'+prepared['source_checkpoint']
assert identity_record['candidate']['checker_version']==result['runtime']['OMA_EXECUTABLE_BUILD']
assert result['native_extension_sha256']==prepared['native_extension_sha256']
completion={'status':'CUSTOM_NATIVE_EXACT_2788_CASE_COMPLETION_AUDIT_PASS',
    'source_checkpoint':prepared['source_checkpoint'],'custom_checker_version':result['runtime']['OMA_EXECUTABLE_BUILD'],
    'source_files':112,'test_input_files':162,'passed':2788,'failed':0,'skipped':0,'generated_output_files':6,
    'result':identity(RESULT),'post_run_audit':identity(audit),'preparation':identity(PREP/'preparation.json'),
    'master_declaration':identity(PREP/'original-frozen-inputs.json'),'focused_pass':identity(PREP/'focused-pass.json'),
    'wrapper_exit':identity(PREP/'exit.json'),'xml_sha256':result['test_xml_sha256'],
    'native_extension_sha256':result['native_extension_sha256'],'seconds':result['seconds'],
    'tests_rerun':False,'package_built':False,'live_backend_changed':False,
    'scope':'Exact declared application source and full test inventory in a separate custom-native runtime; original and copied input identity checks; no whole-building or global physical optimality claim'}
assert not (PREP/'completion.json').exists()
(PREP/'completion.json').write_text(json.dumps(completion,indent=2),encoding='utf-8')
target=ROOT/'evidence/release/shared-tree-combined-custom-ffe49e5e40d0'
target.mkdir(exist_ok=False)
shutil.copytree(PREP,target/'supervision')
shutil.copyfile(__file__,target/'executed-audit.py')
commands=[]
for key,value in result.items():
    if isinstance(value,str) and value.endswith('record.json') and 'commands' in value:
        commands.append(Path(value).parent)
if not commands:
    commands=[ROOT/'evidence/dependencies/native-build/commands/checkpoint-test-collection-a25dcc1e72']
    full=[p for p in (ROOT/'evidence/dependencies/native-build/commands').glob('checkpoint-full-suite-*/record.json')
          if str(result['destination']) in p.read_text()]
    assert len(full)==1
    commands.append(full[0].parent)
manifest={}
for directory in [RESULT.parent,*commands]:
    for p in directory.rglob('*'):
        if p.is_file():manifest[str(p.relative_to(ROOT))]=sha(p)
(target/'completed-handoff.json').write_text(json.dumps({**completion,'immutable_public_evidence_files':manifest},indent=2),encoding='utf-8')
print(json.dumps({'handoff':str(target/'completed-handoff.json'),'sha256':sha(target/'completed-handoff.json')}))
