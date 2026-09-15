"""Bounded completion/retention of one already running frozen native suite."""
import hashlib,json,shutil,subprocess,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
STAGE=Path(__file__).resolve().parent
FULL=ROOT/'evidence/dependencies/native-build/checkpoint-validation/f73a8793ae0d-0cf1c8bf0868'
PREP=STAGE/'prepared/ebffb306b3184dbb8719e4542ad4355e'
OUT=ROOT/'evidence/release/factorized-tree-custom-completed-0cf1c8bf0868'
WORK=STAGE/'completion'/uuid.uuid4().hex
WORK.mkdir(parents=True)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,indent=2),encoding='utf-8')
def identity(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
shutil.copyfile(__file__,WORK/'executed-driver.py')
write(WORK/'status.json',{'status':'WAITING_FOR_RUNNING_FROZEN_3275','result':str(FULL/'result.json')})
try:
    start=time.monotonic()
    while time.monotonic()-start<3000:
        if (PREP/'exit.json').exists():break
        time.sleep(20)
    else:raise TimeoutError('Bounded wrapper completion wait expired')
    assert read(PREP/'exit.json')['exit_code']==0
    r=read(FULL/'result.json')
    assert r['status']=='CUSTOM_NATIVE_NEW_CHECKPOINT_FULL_SUITE_PASS'
    assert r['passed']==r['test_node_count']==3275 and r['failed']==r['skipped']==0
    prep=read(PREP/'preparation.json')
    audit_driver=ROOT/'scripts/native_checkpoint_audit.py'
    assert sha(audit_driver)==prep['driver_source_files'][audit_driver.name]
    with (WORK/'audit.stdout.log').open('w') as out,(WORK/'audit.stderr.log').open('w') as err:
        audit=subprocess.run([str(ROOT/'.venv/Scripts/python.exe'),str(audit_driver),'--result',str(FULL/'result.json')],cwd=ROOT,stdout=out,stderr=err,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
    assert audit.returncode==0
    a=read(FULL/'post-run-exact-audit.json')
    assert a['result_sha256']==sha(FULL/'result.json')
    assert a['test_input_files']==305 and a['source_python_files']==114 and a['test_node_count']==3275
    assert r['driver_bytes_unchanged'] is True
    direct=Path(r['kernel_direct_load']['path'])
    candidate=read(FULL/'identity-comparison.json')['candidate']
    assert direct.resolve()==(Path(r['runtime']['PYTHONPATH'])/'oma/optimization/shared_tree_synthesis.py').resolve()
    assert sha(direct)==r['kernel_direct_load']['sha256']==candidate['source_files']['optimization/shared_tree_synthesis.py']
    OUT.mkdir(exist_ok=False)
    shutil.copytree(FULL,OUT/'custom-full')
    shutil.copytree(PREP,OUT/'preparation')
    shutil.copyfile(__file__,OUT/'executed-completion.py')
    commands={}
    for key in ('test_collection_record','test_suite_record'):
        directory=Path(r[key]).parent;record=read(directory/'record.json')
        assert record['status']=='PASS' and sha(directory/'output.log')==record['log_sha256']
        shutil.copytree(directory,OUT/'commands'/directory.name)
        commands[key]=identity(directory/'record.json')
    result={'status':'EXACT_FACTORIZED_CUSTOM_NATIVE_3275_PASS',
        'source_checkpoint':r['source_checkpoint'],'checker_version':r['runtime']['OMA_EXECUTABLE_BUILD'],
        'native_extension_sha256':r['native_extension_sha256'],'custom_full':identity(FULL/'result.json'),
        'custom_audit':identity(FULL/'post-run-exact-audit.json'),'test_nodes':3275,
        'test_input_files':305,'source_files':114,'failed':0,'skipped':0,
        'kernel_direct_load':r['kernel_direct_load'],'commands':commands,
        'original_full_scope':'Separate original run is retained by its owner; this receipt establishes only this exact custom-native completion.',
        'package_status':'No package built by this script. Package release requires all additional exact bundled/native validations.',
        'original_inputs_modified':False,'active_runtime_modified':False,'tests_rerun_for_audit':False,
        'retained_files':{p.relative_to(OUT).as_posix():sha(p) for p in OUT.rglob('*') if p.is_file()}}
    write(OUT/'handoff.json',result)
    write(WORK/'status.json',{'status':'COMPLETE_EXACT_CUSTOM_3275_PASS','directory':str(OUT),'handoff_sha256':sha(OUT/'handoff.json')})
except BaseException as e:
    write(WORK/'status.json',{'status':'FAILED_OR_INCOMPLETE','error':repr(e)});raise
print((WORK/'status.json').read_text(),flush=True)
