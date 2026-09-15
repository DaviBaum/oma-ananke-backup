"""Retain the completed f73 package after the separate final index audit."""
import argparse,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
STAGE=Path(__file__).resolve().parent
NAME='f73a8793ae0d-ddbee4976390'
EVIDENCE=ROOT/'evidence/dependencies/native-build/portable-candidates'/NAME
PREP=ROOT/'evidence/release/factorized-tree-portable-preparation/6e8550168ebb4d21af44196962e2b8f8'
OUT=ROOT/'evidence/release/factorized-tree-portable-completed-ddbee4976390'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def identity(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
def read_bound(p,expected):
    data=Path(p).read_bytes();assert hashlib.sha256(data).hexdigest()==expected
    return json.loads(data.decode('utf-8-sig'))
def copy_exact(source,target,expected):
    data=Path(source).read_bytes();assert hashlib.sha256(data).hexdigest()==expected
    Path(target).write_bytes(data)
    assert sha(source)==sha(target)==expected
parser=argparse.ArgumentParser();parser.add_argument('--peer',type=Path,required=True)
parser.add_argument('--peer-sha256',required=True);a=parser.parse_args()
peer=read_bound(a.peer,a.peer_sha256)
seal=read_bound(EVIDENCE/'sealed-handoff.json',peer['sealed_handoff_sha256'])
p=read_bound(EVIDENCE/'result.json',seal['validation_result_sha256'])
assert seal['status']=='ISOLATED_NATIVE_PORTABLE_CANDIDATE_SEALED_NOT_PROMOTED'
assert peer['status']=='F73_SEALED_PACKAGE_INDEPENDENT_AUDIT_PASS'
assert peer['package']==p['package'] and peer['checker_version']==p['identity']['checker_version']
assert peer['sealed_handoff_sha256']==sha(EVIDENCE/'sealed-handoff.json')
assert peer['index_sha256']==seal['artifact_index_sha256']
package_index=Path(p['package'])/'artifact-files.json'
assert sha(package_index)==seal['artifact_index_sha256']
bound_receipts={'result.json':'validation_result_sha256',
    'bundled-full-suite.json':'bundled_full_suite_sha256','bundled-tests.xml':'bundled_test_xml_sha256',
    'offline-guard-probe.json':'offline_guard_sha256','real-office-validation.json':'real_office_validation_sha256',
    'real-office-pressure-validation.json':'real_office_pressure_validation_sha256',
    'real-office-coupled-pressure-validation.json':'real_office_coupled_pressure_validation_sha256'}
for name,key in bound_receipts.items():assert sha(EVIDENCE/name)==seal[key]
suite=read_bound(EVIDENCE/'bundled-full-suite.json',seal['bundled_full_suite_sha256'])
assert suite['passed']==3272 and suite['test_node_count']==3275 and suite['failed']==0 and len(suite['skipped'])==3
for mode in ('build','suite','cases','seal'):
    r=read(PREP/(mode+'-exit.json'));assert r['status']=='WRAPPER_EXIT_OBSERVED' and r['exit_code']==0
OUT.mkdir(exist_ok=False)
for name,key in bound_receipts.items():copy_exact(EVIDENCE/name,OUT/name,seal[key])
copy_exact(EVIDENCE/'sealed-handoff.json',OUT/'sealed-handoff.json',peer['sealed_handoff_sha256'])
copy_exact(a.peer,OUT/'independent-seal.json',a.peer_sha256)
prepared_files={x.relative_to(PREP).as_posix():sha(x) for x in PREP.rglob('*') if x.is_file()}
shutil.copytree(PREP,OUT/'preparation')
assert {x.relative_to(OUT/'preparation').as_posix():sha(x) for x in (OUT/'preparation').rglob('*') if x.is_file()}==prepared_files
assert {x.relative_to(PREP).as_posix():sha(x) for x in PREP.rglob('*') if x.is_file()}==prepared_files
for name in ('launcher.json','validation-launch.json','seal-watch-launcher.json','prepare.py','watch_build.py','launch_validations.py','wait_seal.py'):
    copy_exact(STAGE/name,OUT/name,sha(STAGE/name))
shutil.copyfile(__file__,OUT/'executed-handoff.py')
assert sha(package_index)==seal['artifact_index_sha256'] and sha(a.peer)==a.peer_sha256
for name,key in bound_receipts.items():assert sha(EVIDENCE/name)==sha(OUT/name)==seal[key]
h={'status':'F73_NATIVE_PORTABLE_SEALED_AND_INDEPENDENTLY_AUDITED','package':p['package'],
   'source_checkpoint':p['source_checkpoint'],'checker_version':p['identity']['checker_version'],
   'source_files':114,'frozen_test_inputs':305,'native_extension_sha256':seal['native_extension_sha256'],
   'artifact_index_sha256':seal['artifact_index_sha256'],'file_count':seal['file_count'],'logical_bytes':seal['logical_bytes'],
   'original_full':identity(ROOT/'evidence/release/compact-tree-original-full-d6d1204384b8/handoff.json'),
   'custom_full':identity(ROOT/'evidence/release/factorized-tree-custom-completed-0cf1c8bf0868/handoff.json'),
   'bundled_full':identity(EVIDENCE/'bundled-full-suite.json'),'bundled_passed':3272,'declared_direct_interpreter_na':3,
   'independent_final_audit':identity(a.peer),'sealed_handoff':identity(EVIDENCE/'sealed-handoff.json'),
   'real_native_scopes':seal['real_model_scopes'],'prepared_inputs':identity(PREP/'preparation.json'),
   'prior_packages_modified':False,'active_store_modified':False,
   'documentation_policy':'Validated package/docs is its captured pre-promotion EDF documentation. A separately indexed current f73 documentation companion will accompany the release ZIP; neither validation payload nor seal policy is changed.',
   'limitations':['Finite declared catalogues and supported native numerical scope; no unrestricted routing or physical-model completeness theorem',
       'Nonnegative pressure uniqueness requires the supported full parameter model and separately verified local/global proof',
       'Python network denial is an audit-hook diagnostic, not an OS firewall',
       'The Hospital attempts remain unresolved; analytic fixtures do not establish whole-building routing completion'],
   'retained_files':{x.relative_to(OUT).as_posix():sha(x) for x in OUT.rglob('*') if x.is_file()}}
(OUT/'handoff.json').write_text(json.dumps(h,indent=2),encoding='utf-8')
print(json.dumps({'directory':str(OUT),'handoff_sha256':sha(OUT/'handoff.json')}))
