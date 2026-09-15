"""Separate current-driver package regression; never relabel the3012 input set."""
import hashlib,json,os,shutil,subprocess,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
from native_package_evidence import verify_test_snapshot,verify_suite_xml
from native_prepare import sha,json_write
from native_build import run
CUSTOM=ROOT/'evidence/dependencies/native-build/checkpoint-validation/edf555760245-4c1eddeca46f'
record=json.loads((CUSTOM/'result.json').read_text())
declaration=json.loads((CUSTOM/'declared-test-snapshot.json').read_text())
target=ROOT/'evidence/release/general-tree-package-harness'/uuid.uuid4().hex;target.mkdir(parents=True)
snapshot=target/'snapshot';snapshot.mkdir()
inputs={}
for name,digest in declaration['snapshot_files'].items():
    source=Path(declaration['test_snapshot'])/name
    if name in {'scripts/native_validate_checkpoint.py','scripts/native_portable_full_suite.py'}:source=ROOT/name
    path=snapshot/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,path);inputs[name]=sha(path)
verify_test_snapshot(snapshot,inputs)
files=['tests/test_native_command_evidence.py','tests/test_native_package_evidence.py','tests/test_native_package_three_roles.py','tests/test_native_coupled_package_adversarial.py']
env=os.environ.copy();env.update(record['runtime']);env['PYTHONDONTWRITEBYTECODE']='1';env.pop('OMA_COUPLED_PACKAGE_STORE',None);env.pop('OMA_COUPLED_PACKAGE_CANDIDATE',None)
env['OMA_SHARED_TREE_SOURCE']=record['kernel_direct_load']['path']
python=ROOT/'.release/native-build/test-venv/Scripts/python.exe'
started=time.monotonic();result={'status':'RUNNING','source_checkpoint':record['source_checkpoint'],'runtime':record['runtime'],'input_files':inputs,'driver_deltas':{k:{'original':declaration['snapshot_files'][k],'current':v} for k,v in inputs.items() if v!=declaration['snapshot_files'][k]},'scope':'121 separate package-harness cases with current2 driver bytes; no new3012 suite claim; fresh default analytic coupled fixture'}
json_write(target/'result.json',result)
try:
    collection=run('general-driver-supplement-collection',[python,'-m','pytest','--collect-only','-q','-o','pythonpath=',*files],cwd=snapshot,env=env,budget=120)
    nodes=[x for x in (collection/'output.log').read_text().splitlines() if x.startswith('tests/') and '::' in x]
    assert len(nodes)==len(set(nodes))==121
    json_write(target/'test-nodes.json',nodes)
    suite=run('general-driver-supplement',[python,'-m','pytest','-q','-o','pythonpath=',*files,'--junitxml='+str(target/'tests.xml')],cwd=snapshot,env=env,budget=180)
    accounting=verify_suite_xml(target/'tests.xml',nodes,direct_interpreter=False)
    verify_test_snapshot(snapshot,inputs)
    result.update(status='PASS',accounting=accounting,collection_record=str(collection/'record.json'),suite_record=str(suite/'record.json'),xml_sha256=sha(target/'tests.xml'),test_nodes_sha256=sha(target/'test-nodes.json'))
except BaseException as e:result.update(status='FAIL',error=repr(e));raise
finally:
    result.update(seconds=time.monotonic()-started,script_sha256=sha(__file__));json_write(target/'result.json',result);shutil.copyfile(__file__,target/'executed-driver.py')
print(json.dumps({'directory':str(target),'result_sha256':sha(target/'result.json')}))
