"""Separate current packaging harness on the completed, frozen custom native app."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
CHECKPOINT = ROOT/'evidence/dependencies/native-build/checkpoint-validation/33a20d125bba-ffe49e5e40d0/result.json'
TARGET = ROOT/'evidence/release/shared-tree-package-supplement'/uuid.uuid4().hex
TESTS = ['test_native_command_evidence.py', 'test_native_package_evidence.py', 'test_native_package_three_roles.py', 'test_native_coupled_package_adversarial.py', 'test_physical_report_admission.py', 'test_native_real_model_validation_script.py']
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,v): Path(p).write_text(json.dumps(v,indent=2),encoding='utf-8')
def files(p): return {x.relative_to(p).as_posix():sha(x) for x in p.rglob('*.py')}

cp = read(CHECKPOINT)
assert cp['status']=='CUSTOM_NATIVE_NEW_CHECKPOINT_FULL_SUITE_PASS' and cp['passed']==2788
assert cp['failed']==cp['skipped']==0
TARGET.mkdir(parents=True)
snapshot = TARGET/'snapshot'
original = Path(cp['destination'])/'test-suite'
inputs = read(CHECKPOINT.parent/'test-source-manifest.json')['files']
for relative,value in inputs.items():
    p=original/relative; assert sha(p)==value
    q=snapshot/relative; q.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(p,q)
for p in (ROOT/'scripts').glob('native_*.py'):
    shutil.copyfile(p,snapshot/'scripts'/p.name)
for name in TESTS: shutil.copyfile(ROOT/'tests'/name,snapshot/'tests'/name)
manifest={p.relative_to(snapshot).as_posix():sha(p) for p in snapshot.rglob('*') if p.is_file()}
write(TARGET/'input-manifest.json',manifest)
shutil.copyfile(__file__,TARGET/'executed-driver.py')
identity=read(CHECKPOINT.parent/'identity-comparison.json')
source=Path(cp['runtime']['PYTHONPATH'])
assert files(source/'oma')==identity['candidate']['source_files']==identity['original']['source_files']
assert len(files(source/'oma'))==112
assert sha(identity['candidate']['extension_path'])==cp['native_extension_sha256']
env=os.environ.copy(); env.update(cp['runtime'])
for key in ('OMA_COUPLED_PACKAGE_STORE','OMA_COUPLED_PACKAGE_CANDIDATE'): env.pop(key,None)
python=ROOT/'.release/native-build/test-venv/Scripts/python.exe'
result={'status':'RUNNING','checkpoint':str(CHECKPOINT),'checkpoint_sha256':sha(CHECKPOINT),
    'runtime':cp['runtime'],'native_extension_sha256':cp['native_extension_sha256'],
    'source_files':identity['candidate']['source_files'],'inputs':manifest,'selected_files':TESTS,
    'driver_sha256':sha(__file__),'fixture':'Fresh analytic native default; no saved Office override',
    'scope':'Separate 196-case current packaging and changed-input supplement: 121 additional unique cases plus 75 current-byte reruns overlapping the declared 2788; union 2909 unique cases'}
write(TARGET/'result.json',result)
def run(name,command):
    start=time.monotonic()
    with (TARGET/(name+'.log')).open('w',encoding='utf-8') as log:
        completed=subprocess.run(command,cwd=snapshot,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180)
    record={'command':command,'cwd':str(snapshot),'environment':cp['runtime'],
            'exit_code':completed.returncode,'seconds':time.monotonic()-start,'log_sha256':sha(TARGET/(name+'.log'))}
    write(TARGET/(name+'.json'),record)
    assert completed.returncode==0, name+' failed'
    return record
try:
    probe="import json,oma,hashlib;import ifcopenshell._ifcopenshell_wrapper as extension;from pathlib import Path;from oma.build_identity import checker_version;print(json.dumps({'checker_version':checker_version(),'oma_path':oma.__file__,'extension_sha256':hashlib.sha256(Path(extension.__file__).read_bytes()).hexdigest()}))"
    run('identity',[str(python),'-c',probe])
    observed=read(TARGET/'identity.log')
    assert observed['checker_version']==cp['runtime']['OMA_EXECUTABLE_BUILD']
    assert Path(observed['oma_path']).resolve()==(source/'oma/__init__.py').resolve()
    assert observed['extension_sha256']==cp['native_extension_sha256']
    selection=['tests/'+name for name in TESTS]
    run('collection',[str(python),'-m','pytest','-q','--collect-only','-o','pythonpath=',*selection])
    nodes=[line.strip() for line in (TARGET/'collection.log').read_text().splitlines() if line.startswith('tests/') and '::' in line]
    assert len(nodes)==len(set(nodes))==196
    write(TARGET/'test-nodes.json',nodes)
    (TARGET/'selected-tests.args').write_text('\n'.join(nodes)+'\n',encoding='utf-8')
    full=run('tests',[str(python),'-m','pytest','-q','-o','pythonpath=','@'+str(TARGET/'selected-tests.args'),'--junitxml='+str(TARGET/'tests.xml')])
    sys.path.insert(0,str(snapshot/'scripts'))
    from native_package_evidence import verify_suite_xml,verify_test_snapshot
    accounting=verify_suite_xml(TARGET/'tests.xml',nodes,direct_interpreter=False)
    assert accounting['passed']==196
    inventory=verify_test_snapshot(snapshot,manifest,allow_generated_evidence=False)
    assert files(source/'oma')==identity['candidate']['source_files']
    assert sha(identity['candidate']['extension_path'])==cp['native_extension_sha256']
    assert sha(CHECKPOINT)==result['checkpoint_sha256'] and sha(__file__)==result['driver_sha256']
    result.update(status='EXACT_196_CURRENT_PACKAGE_SUPPLEMENT_PASS',passed=196,failed=0,skipped=0,
        seconds=full['seconds'],xml_sha256=sha(TARGET/'tests.xml'),nodes_sha256=sha(TARGET/'test-nodes.json'),
        input_inventory=inventory,source_unchanged=True,observed_identity=observed)
except BaseException as exc:
    result.update(status='FAILED',error=repr(exc))
    raise
finally:
    write(TARGET/'result.json',result)
    print(json.dumps({'result':str(TARGET/'result.json'),'status':result['status']}),flush=True)
