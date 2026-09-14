"""Read-only pre-seal identity and dual-receipt audit; no native rerun."""
from pathlib import Path
import hashlib
import json
import shutil
import sys
import time
import uuid

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
BASE=ROOT/'evidence/dependencies/native-build/portable-candidates/52bd5d292171-2563efa50156'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    start=time.perf_counter();out=ROOT/'evidence/release/pressure-package-harness-peer-review'/('corrected52bd-preseal-'+uuid.uuid4().hex)
    (out/'reviewed-scripts').mkdir(parents=True)
    scripts=('native_package_evidence.py','native_seal_portable.py','native_real_model_validation.py','native_prepare.py','native_build.py')
    hashes={}
    for name in scripts:
        source=ROOT/'scripts'/name;target=out/'reviewed-scripts'/name
        shutil.copyfile(source,target);hashes[name]=sha(source);assert sha(target)==hashes[name]
    sys.path.insert(0,str(out/'reviewed-scripts'))
    import native_package_evidence as helper
    resultpath=BASE/'result.json';portable=read(resultpath);package=Path(portable['package'])
    initial={name:sha(BASE/name) for name in ('result.json','real-office-validation.json','real-office-pressure-validation.json')}
    print(json.dumps({'stage':'AUDIT_STARTED','directory':str(out)}),flush=True)
    payload=helper.verify_payload(package,portable)
    print(json.dumps({'stage':'PAYLOAD_REHASHED','files':len(payload['files'])}),flush=True)
    checkpoint,manifest=helper.verify_checkpoint_inputs(package,portable)
    print(json.dumps({'stage':'CHECKPOINT_BOUND','inputs':len(manifest['files'])}),flush=True)
    assert len(manifest['files'])==110 and checkpoint['test_node_count']==1979
    declaration=helper.real_model_inputs(package,portable)
    scopes={role:helper.verify_real_model_receipt(package,portable,resultpath,role,read(BASE/filename))
        for role,(filename,_) in helper.REAL_MODEL_ROLES.items()}
    assert scopes['joint_fitting_budget']['source_pairs']==4818 and scopes['joint_fitting_budget']['cross_route_pairs']==5
    assert scopes['joint_fitting_budget']['fittings']==scopes['joint_fitting_budget']['fitting_budget']==2
    assert all(sha(BASE/name)==expected for name,expected in initial.items())
    assert all(sha(ROOT/'scripts'/name)==expected for name,expected in hashes.items())
    result={'status':'CORRECTED_PACKAGE_PAYLOAD_CHECKPOINT_AND_DUAL_RECEIPTS_BOUND_PRESEAL',
        'source_checkpoint':portable['source_checkpoint'],'checker_version':portable['identity']['checker_version'],
        'portable_result_sha256':initial['result.json'],'package':str(package),'reviewed_script_sha256':hashes,
        'payload_files_rehashed':len(payload['files']),'payload_manifest_sha256':portable['validated_payload_manifest_sha256'],
        'checkpoint_sha256':sha(package/'provenance/checkpoint-validation/result.json'),
        'test_inputs':110,'test_nodes':1979,'native_scopes':scopes,'declared_roles':declaration,
        'receipt_sha256':{n:h for n,h in initial.items() if n.startswith('real-office')},
        'package_written':False,'native_rerun':False,'seal_claim':False,
        'full_bundled_suite_accounting':'PENDING_AT_THIS_REVIEW; separately required before seal',
        'source_receipts_unchanged':True,'seconds':time.perf_counter()-start,
        'limitations':'Read-only artifact binding and retained native-report scope. No promotion, new app version validation or full-suite completion claim.'}
    (out/'result.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    shutil.copyfile(Path(__file__),out/'executed-audit.py')
    (out/'README.md').write_text('The corrected 52bd portable payload was rehashed, and its copied checkpoint SHA and complete 110-input / 1,979-node declaration match the immutable portable result. Both separately predeclared Office receipts bind their original/export bytes, isolated Store artifacts, current managed execution token and full native denominators. B2 retains 4,818 source pairs, five cross-route pairs and two new fittings within B=2; the pressure receipt is separate. This is a pre-seal review while the bundled full suite is still running. Its final XML accounting and seal remain pending. No package write or native rerun occurred.\n',encoding='utf-8')
    print(json.dumps({'directory':str(out),'result_sha256':sha(out/'result.json'),'seconds':result['seconds']}))

if __name__=='__main__':main()
