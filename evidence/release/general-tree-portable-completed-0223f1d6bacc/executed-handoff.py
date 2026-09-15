"""Retain completed EDF portable evidence only after seal and independent audit."""
import argparse,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
NAME='edf555760245-0223f1d6bacc'
EVIDENCE=ROOT/'evidence/dependencies/native-build/portable-candidates'/NAME
PREP=ROOT/'evidence/release/general-tree-portable-preparation/cb56c1917cb1452da62517c408fd7d53'
OUT=ROOT/'evidence/release/general-tree-portable-completed-0223f1d6bacc'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def identity(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
parser=argparse.ArgumentParser();parser.add_argument('--peer',type=Path,required=True);a=parser.parse_args()
portable=read(EVIDENCE/'result.json');seal=read(EVIDENCE/'sealed-handoff.json');peer=read(a.peer)
assert seal['status']=='ISOLATED_NATIVE_PORTABLE_CANDIDATE_SEALED_NOT_PROMOTED'
assert peer['schema']=='oma.independent-sealed-portable-audit/1'
assert peer['package']==portable['package'] and peer['checker_version']==portable['identity']['checker_version']
assert peer['status']=='EDF_SEALED_PACKAGE_INDEPENDENT_AUDIT_PASS' and peer['sealed_handoff_sha256']==sha(EVIDENCE/'sealed-handoff.json')
assert peer['index_sha256']==seal['artifact_index_sha256']
suite=read(EVIDENCE/'bundled-full-suite.json')
assert suite['passed']==3009 and suite['test_node_count']==3012 and len(suite['skipped'])==3
for mode in ('build','suite','cases','seal'):
    result=read(PREP/(mode+'-exit.json'));assert result['status']=='WRAPPER_EXIT_OBSERVED' and result['exit_code']==0
OUT.mkdir(exist_ok=False)
for name in ('result.json','sealed-handoff.json','bundled-full-suite.json','bundled-tests.xml','offline-guard-probe.json',
             'real-office-validation.json','real-office-pressure-validation.json','real-office-coupled-pressure-validation.json'):
    p=EVIDENCE/name
    if p.exists():shutil.copyfile(p,OUT/name)
shutil.copyfile(a.peer,OUT/'independent-seal.json')
for name in ('preparation.json','real-model-inputs.json','build-exit.json','suite-exit.json','cases-exit.json','seal-exit.json'):
    shutil.copyfile(PREP/name,OUT/name)
for name in ('native_validate_checkpoint.py','native_portable_full_suite.py'):
    shutil.copyfile(PREP/'driver-sources'/name,OUT/name)
shutil.copyfile(__file__,OUT/'executed-handoff.py')
attempt=ROOT/'.oma/development/general-tree-portable/orchestration/defa4272a31447a4a7d3364f3d41e140'
assert read(attempt/'status.json')['status']=='FAILED_OR_INCOMPLETE'
shutil.copytree(attempt,OUT/'retained-initial-wait-wrapper-failure')
handoff={'status':'EDF_NATIVE_PORTABLE_SEALED_AND_INDEPENDENTLY_AUDITED',
    'package':portable['package'],'source_checkpoint':portable['source_checkpoint'],
    'checker_version':portable['identity']['checker_version'],'source_files':112,'frozen_test_inputs':264,
    'native_extension_sha256':seal['native_extension_sha256'],'artifact_index_sha256':seal['artifact_index_sha256'],
    'file_count':seal['file_count'],'logical_bytes':seal['logical_bytes'],
    'original_full':identity(ROOT/'evidence/release/general-tree-original-full-a29404ec828e/handoff.json'),
    'custom_full':identity(ROOT/'evidence/release/general-tree-custom-completed-4c1eddeca46f/handoff.json'),
    'bundled_full':identity(EVIDENCE/'bundled-full-suite.json'),'bundled_passed':3009,'declared_direct_interpreter_na':3,
    'separate_current_driver_121':identity(ROOT/'evidence/release/general-tree-package-harness/431a2bdce9c64ca0a9b8d5ba572d6a32/result.json'),
    'independent_final_audit':identity(a.peer),'sealed_handoff':identity(EVIDENCE/'sealed-handoff.json'),
    'real_native_scopes':seal['real_model_scopes'],'prepared_inputs':identity(PREP/'preparation.json'),
    'prior_packages_modified':False,'active_store_modified':False,
    'retained_orchestration_failure':'Initial optional wait wrapper rejected the valid state where only the original suite had finished. It stopped before any package build. Corrected wait permits one completed side but requires both full passes; no test rerun or native failure.',
    'limitations':['Finite declared topology/catalogue and native numerical scope; no unrestricted routing/global physical-model theorem',
                  'Unique nonnegative coupled flow applies only to the supported bound model/full parameter box and separately verified local+global proofs',
                  'Python socket audit denial is not a native-library or OS firewall',
                  'The next private compact-search implementation is absent from this EDF package'],
    'retained_files':{p.relative_to(OUT).as_posix():sha(p) for p in OUT.rglob('*') if p.is_file()}}
(OUT/'handoff.json').write_text(json.dumps(handoff,indent=2),encoding='utf-8')
print(json.dumps({'directory':str(OUT),'handoff_sha256':sha(OUT/'handoff.json')}))
