"""Read-only review of the historical package's copied-checkpoint and receipts."""
from pathlib import Path
from copy import deepcopy
import hashlib
import importlib.util
import json
import shutil
import sys
import time
import uuid

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
BASE = ROOT/'evidence/dependencies/native-build/portable-candidates/1abe9a077844-f5cb8453a001'


def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value): path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


def main():
    start=time.perf_counter()
    out=ROOT/'evidence/release/pressure-package-harness-peer-review'/('final-receipts-'+uuid.uuid4().hex)
    (out/'reviewed-scripts').mkdir(parents=True)
    scripts=('native_package_evidence.py','native_seal_portable.py','native_real_model_validation.py','native_prepare.py','native_build.py')
    script_hashes={}
    for name in scripts:
        source=ROOT/'scripts'/name;copy=out/'reviewed-scripts'/name
        shutil.copyfile(source,copy);script_hashes[name]=sha(source);assert sha(copy)==script_hashes[name]
    sys.path.insert(0,str(out/'reviewed-scripts'))
    import native_package_evidence as helper
    portable_path=BASE/'result.json';portable=read(portable_path);package=Path(portable['package'])
    initial={name:sha(BASE/name) for name in ('result.json','real-office-validation.json','real-office-pressure-validation.json','PROMOTION-BLOCKED.json','checkpoint-source-binding-audit.json')}
    payload=helper.verify_payload(package,portable)
    checkpoint,manifest=helper.verify_checkpoint_inputs(package,portable)
    assert len(manifest['files'])==106 and checkpoint['test_node_count']==1847
    declaration=helper.real_model_inputs(package,portable)
    scopes={}
    for role,(filename,_) in helper.REAL_MODEL_ROLES.items():
        scopes[role]=helper.verify_real_model_receipt(package,portable,portable_path,role,read(BASE/filename))
    assert scopes['joint_fitting_budget']['source_pairs']==4818 and scopes['joint_fitting_budget']['cross_route_pairs']==5
    assert scopes['joint_fitting_budget']['fittings']==scopes['joint_fitting_budget']['fitting_budget']==2
    # Copy only checkpoint inputs to a disposable audit tree. No package write.
    scratch=out/'synthetic-checkpoint-copy'
    destination=scratch/'provenance/checkpoint-validation';destination.mkdir(parents=True)
    actual_checkpoint=package/'provenance/checkpoint-validation/result.json'
    shutil.copyfile(actual_checkpoint,destination/'result.json')
    shutil.copyfile(package/'provenance/checkpoint-validation/test-source-manifest.json',destination/'test-source-manifest.json')
    changed=deepcopy(checkpoint)
    # Coherently replaced checkpoint+source manifest still has old exact nodes.
    altered_manifest=deepcopy(manifest)
    first=next(iter(altered_manifest['files']))
    altered_manifest['files'][first]='0'*64
    write(destination/'test-source-manifest.json',altered_manifest)
    changed['test_source_manifest_sha256']=sha(destination/'test-source-manifest.json')
    write(destination/'result.json',changed)
    blocked=False
    try:helper.verify_checkpoint_inputs(scratch,portable)
    except AssertionError:blocked=True
    assert blocked
    blocker=read(BASE/'PROMOTION-BLOCKED.json')
    assert blocker['live_runtime_promoted'] is False and blocker['source_or_payload_replaced'] is False
    assert blocker['source_checkpoint']==portable['source_checkpoint']
    assert all(sha(BASE/name)==expected for name,expected in initial.items())
    assert all(sha(ROOT/'scripts'/name)==expected for name,expected in script_hashes.items())
    result={'status':'HISTORICAL_PACKAGE_CHECKPOINT_AND_DUAL_RECEIPTS_INDEPENDENTLY_BOUND',
        'reviewed_script_sha256':script_hashes,'portable_result_sha256':initial['result.json'],
        'package':str(package),'source_checkpoint':portable['source_checkpoint'],'checker_version':portable['identity']['checker_version'],
        'payload_files_rehashed':len(payload['files']),'payload_manifest_sha256':portable['validated_payload_manifest_sha256'],
        'checkpoint_sha256':sha(actual_checkpoint),'test_inputs':len(manifest['files']),'test_nodes':checkpoint['test_node_count'],
        'receipt_sha256':{k:v for k,v in initial.items() if k.startswith('real-office')},
        'declared_roles':declaration,'native_scopes':scopes,'coherent_checkpoint_manifest_replacement_rejected':blocked,
        'package_written':False,'native_tests_rerun':False,'source_receipts_unchanged':True,
        'promotion_blocker':blocker,'seconds':time.perf_counter()-start,
        'limitations':'Review validates retained historical evidence bindings and scope. No seal, promotion, affected fixed-flow correction, or new native computation. Future full-suite startup checkpoint guard remains separately pending; this audit supplies the post-run explicit binding for unchanged current evidence.'}
    write(out/'result.json',result)
    shutil.copyfile(Path(__file__),out/'executed-audit.py')
    (out/'README.md').write_text('The copied checkpoint is now checked against the immutable portable result before its exact test-source manifest and inventory are trusted. The positive actual package has 106 exact test inputs and 1,847 declared nodes. A coherent replacement of the copied checkpoint and source manifest is rejected by the portable checkpoint SHA binding. Both separately declared real-model receipts match their managed execution tokens, immutable blobs, candidate roots, original/export bytes and complete native scopes. The B2 receipt retains 4,818 source pairs, five cross-route pairs and two fittings; the pressure receipt is a separate candidate under the explicitly scoped pressure model.\n\nNo new native run or package write occurred. This historical 1abe package remains explicitly promotion-blocked for the known prescribed fixed-flow native-section issue; these distinct successful receipts do not repair that branch. The future full-suite startup call was still pending during this review; the new sealer helper and this read-only post-run audit establish the present copied-input binding.\n',encoding='utf-8')
    print(json.dumps({'status':result['status'],'directory':str(out),'result_sha256':sha(out/'result.json'),'seconds':result['seconds']}))


if __name__=='__main__':main()
