"""Synthetic helper-only provenance challenges; no package or process mutation."""
from pathlib import Path
import hashlib
import importlib.util
import json
import shutil
import sys
import uuid

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n');return sha(p)

def main():
    out=ROOT/'evidence/release/portable-recovery-peer-review'/uuid.uuid4().hex
    (out/'scripts').mkdir(parents=True);(out/'tests').mkdir()
    names=['native_command_evidence.py','native_prepare.py','native_portable_recover_interrupted.py','native_seal_portable.py']
    for name in names:shutil.copyfile(ROOT/'scripts'/name,out/'scripts'/name)
    fixture=out/'tests/test_native_command_evidence.py'
    shutil.copyfile(ROOT/'tests/test_native_command_evidence.py',fixture)
    shutil.copyfile(Path(__file__),out/'executed-audit.py')
    sys.path.insert(0,str(out/'scripts'))
    import native_command_evidence as helper
    spec=importlib.util.spec_from_file_location('native_command_fixture',fixture)
    f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
    case=f.campaign.__wrapped__(out/'synthetic-closure')
    original=case['closure']()
    path=Path(case['suite']['suite_record']);record=json.loads(path.read_text())
    record['command']=[record['command'][0],'--version'];write(path,record)
    try:
        result=case['closure']();command={'status':'ACCEPTED','closure':result}
    except (AssertionError,KeyError) as e:command={'status':'REJECTED','reason':repr(e)}
    # Construct the existing fixture's retained-handle evidence but deliberately
    # provide no preserved raw wrapper receipt and a false wrapper digest.
    command_row=json.loads(path.read_text());observed=f.observation(command_row)
    digest=write(path,command_row);attempt=case['validation']/'attempts/retained-handle'
    write(attempt/'command-running.json',command_row)
    observed['original_command_record_sha256']=digest
    (attempt/'monitor.py').write_text('# synthetic only, never executed\n')
    observed['monitor_source_sha256']=sha(attempt/'monitor.py')
    monitorhash=write(attempt/'monitor-result.json',observed)
    recovery={'kind':helper.RECOVERY_KIND,'tests_rerun':False,'directory':str(attempt),
        'raw_wrapper_receipt_sha256':'0'*64,'original_command_record':str(path),'original_command_record_sha256':digest,
        'monitor_result_sha256':monitorhash,'completed_output_log_sha256':command_row['log_sha256'],
        'observation_scope':helper.validate_exit_observation(command_row,observed,digest)}
    try:
        scope=helper.verify_recovered_command(recovery,path,case['validation']);wrapper={'status':'ACCEPTED','scope':scope}
    except (AssertionError,KeyError,FileNotFoundError) as e:wrapper={'status':'REJECTED','reason':repr(e)}
    result={'scope':'Synthetic helper-only provenance review; no native computation, actual process manipulation, package write or full-sealer exploit claim',
        'source_hashes':{name:sha(out/'scripts'/name) for name in names},
        'positive_closure_command_count':len(original['commands']),'wrong_current_command_argv':command,
        'missing_raw_wrapper_and_false_digest':wrapper}
    write(out/'result.json',result)
    print(json.dumps({'directory':str(out),'result_sha256':sha(out/'result.json'),
        'wrong_command':command['status'],'missing_wrapper':wrapper['status']}))

if __name__=='__main__':main()
