"""Lightweight exact recovery audit; prior payload and native receipts are bound."""
from pathlib import Path
import hashlib
import json
import shutil
import sys
import uuid

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
BASE=ROOT/'evidence/dependencies/native-build/portable-candidates/52bd5d292171-2563efa50156'
PRIOR=ROOT/'evidence/release/pressure-package-harness-peer-review/corrected52bd-preseal-5c5eee060f914bbe9968255ba98e824d/result.json'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

def main():
    out=ROOT/'evidence/release/portable-recovery-peer-review'/('actual-'+uuid.uuid4().hex)
    (out/'reviewed-scripts').mkdir(parents=True)
    names=('native_command_evidence.py','native_package_evidence.py','native_prepare.py','native_portable_recover_interrupted.py','native_seal_portable.py')
    hashes={}
    for name in names:
        shutil.copyfile(ROOT/'scripts'/name,out/'reviewed-scripts'/name);hashes[name]=sha(ROOT/'scripts'/name)
    sys.path.insert(0,str(out/'reviewed-scripts'))
    import native_package_evidence as evidence
    import native_command_evidence as commands
    prior=read(PRIOR);portable=read(BASE/'result.json');package=Path(portable['package'])
    full=read(BASE/'bundled-full-suite.json');recovery=full['recovery']
    assert sha(BASE/'result.json')==prior['portable_result_sha256']
    assert sha(package/'validated-payload.json')==prior['payload_manifest_sha256']
    for name,expected in prior['receipt_sha256'].items():assert sha(BASE/name)==expected
    assert full['status']=='BUNDLED_EXACT_FROZEN_FULL_SUITE_PASS_WITH_DECLARED_DIRECT_INTERPRETER_NOT_APPLICABLE'
    assert full['checker_version']==portable['identity']['checker_version'] and full['source_checkpoint']==portable['source_checkpoint']
    assert full['portable_validation_result_sha256']==sha(BASE/'result.json')
    assert full['validated_payload_manifest_sha256']==portable['validated_payload_manifest_sha256']
    assert Path(full['package']).resolve()==package.resolve()
    checkpoint,manifest=evidence.verify_checkpoint_inputs(package,portable)
    assert full['test_source_manifest']==manifest and len(manifest['files'])==110
    nodepath=package/'provenance/checkpoint-validation/selected-tests.args'
    assert sha(nodepath)==full['test_node_manifest_sha256']==checkpoint['test_node_manifest_sha256']
    nodes=nodepath.read_text().splitlines();assert len(nodes)==len(set(nodes))==full['test_node_count']==1979
    xml=BASE/'bundled-tests.xml';assert sha(xml)==full['test_xml_sha256']
    accounting=evidence.verify_suite_xml(xml,nodes)
    assert all(full[k]==v for k,v in accounting.items()) and accounting['passed']==1976 and len(accounting['skipped'])==3
    inventory=evidence.verify_test_snapshot(Path(full['directory'])/'test-suite',manifest['files'],allow_generated_evidence=True)
    assert inventory==full['final_test_snapshot_inventory']
    scope=commands.verify_recovered_command(recovery,full['suite_record'],BASE,full)
    receipts={role:read(BASE/filename) for role,(filename,_) in evidence.REAL_MODEL_ROLES.items()}
    closure=commands.candidate_command_closure(package,portable,checkpoint,full,receipts,
        workspace=ROOT,commands_root=ROOT/'evidence/dependencies/native-build/commands',validation_directory=BASE)
    recovered_commands=[r for r in closure['commands'].values() if r['raw_status']=='RUNNING']
    assert len(recovered_commands)==1 and recovered_commands[0]['roles']==['bundled.full']
    assert sha(full['suite_record'])==recovery['original_command_record_sha256']
    observation=read(Path(recovery['directory'])/'monitor-result.json')
    assert observation['exit_code']==0 and observation['retained_process_handle'] is True
    artifacts=[BASE/'result.json',BASE/'bundled-full-suite.json',xml,PRIOR,Path(full['suite_record']),
        Path(recovery['directory'])/'bundled-full-suite-running.json',Path(recovery['directory'])/'monitor-result.json',Path(recovery['directory'])/'monitor.py']
    records=[]
    for i,path in enumerate(artifacts):
        target=out/'reviewed-artifacts'/f'{i:02d}-{path.name}';target.parent.mkdir(exist_ok=True)
        shutil.copyfile(path,target);records.append({'path':str(path),'sha256':sha(path),'copy':target.relative_to(out).as_posix()})
    assert all(sha(ROOT/'scripts'/name)==expected for name,expected in hashes.items())
    write(out/'command-closure.json',closure)
    result={'status':'ACTUAL_RECOVERED_SUITE_EXACT_ACCOUNTING_AND_COMMAND_CLOSURE_PASS_PRESEAL',
        'script_sha256':hashes,'reviewed_artifacts':records,'source_checkpoint':portable['source_checkpoint'],
        'checker_version':full['checker_version'],'accounting':accounting,'test_inputs':110,'test_nodes':1979,
        'retained_handle_exit_code':0,'retained_pid':observation['pid'],'observation_scope':scope,
        'original_command_still_running_bytes_unchanged':True,'command_count':len(closure['commands']),
        'command_closure_sha256':sha(out/'command-closure.json'),'prior_payload_and_dual_receipts_sha256':sha(PRIOR),
        'payload_rehashed_again':False,'tests_rerun':False,'package_written':False,
        'seal_claim':False,'scope':'Exact artifacts of the surviving pytest process with an explicitly unobserved supervision interval; no continuous process-tree monitoring claim and no inference from XML alone'}
    write(out/'result.json',result);shutil.copyfile(Path(__file__),out/'executed-audit.py')
    (out/'README.md').write_text('The actual surviving bundled pytest process finished through a retained Windows handle with exit 0. Exact XML accounting is 1,976 passes and three specifically named direct-interpreter N/A tests over the 1,979-node declaration. All 110 declared test inputs match, as do the complete allowed generated-output inventory, copied checkpoint and original driver snapshots. The raw wrapper and command records remain preserved; the command record is still RUNNING. The monitoring gap remains explicit. Candidate command closure includes only pinned native history and nine current required command roles with exact argv, logs and input bindings. Prior independently checked payload/native receipts remain hash-bound; no duplicate native test or package write occurred. Final file-index verification follows sealing.\n',encoding='utf-8')
    print(json.dumps({'directory':str(out),'result_sha256':sha(out/'result.json'),'commands':len(closure['commands']),**accounting}))

if __name__=='__main__':main()
