"""Retain a compact completed handoff without touching the sealed package."""
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
NAME = '5e8fe9659cfd-82d3a00a6ff4'
EVIDENCE = ROOT/'evidence/dependencies/native-build/portable-candidates'/NAME
PREP = ROOT/'evidence/release/coupled-portable-preparation/d1b4a436d49f42f9ba3e17b463712f4d'
TARGET = ROOT/'evidence/release/coupled-portable-completed-82d3a00a6ff4'
TARGET.mkdir(exist_ok=False)
def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def identity(path): return {'path':str(Path(path).resolve()),'sha256':sha(path)}
result = read(EVIDENCE/'result.json')
sealed = read(EVIDENCE/'sealed-handoff.json')
peer_path = EVIDENCE/'independent-seal/aee0cb2e283e45a9a9ca182c1ce1b9b4/result.json'
peer = read(peer_path)
assert sealed['status'] == 'ISOLATED_NATIVE_PORTABLE_CANDIDATE_SEALED_NOT_PROMOTED'
assert peer['status'] == 'PASS' and peer['sealed_handoff_sha256'] == sha(EVIDENCE/'sealed-handoff.json')
assert peer['index_sha256'] == sealed['artifact_index_sha256']
for mode in ('build','suite','cases','seal'):
    receipt = read(PREP/(mode+'-exit.json'))
    assert receipt['status'] == 'WRAPPER_EXIT_OBSERVED' and receipt['exit_code'] == 0
tests = {}
for name, expected in (('coupled-package-harness-final-tests.xml',73),('coupled-package-replay-tests.xml',48),('coupled-package-default-fixture-tests.xml',48)):
    path = PREP/name
    xml = ET.parse(path).getroot()
    assert len(xml.findall('.//testcase')) == expected
    assert not any(xml.findall('.//'+tag) for tag in ('failure','error','skipped'))
    tests[name] = {**identity(path),'passed':expected}
changed = ['scripts/native_command_evidence.py','scripts/native_package_evidence.py',
    'scripts/native_real_model_validation.py','scripts/native_seal_portable.py',
    'tests/test_native_command_evidence.py','tests/test_native_package_three_roles.py',
    'tests/test_native_coupled_package_adversarial.py']
sources = {}
for name in changed:
    path = ROOT/name
    if name.startswith('scripts/'):
        assert sha(path) == read(PREP/'preparation.json')['driver_sources'][name]
    else:
        assert sha(path) == sha(PREP/'focused-tests'/path.name)
    target = TARGET/'changed-sources'/name
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(path,target)
    sources[name] = identity(path)
failed = ROOT/'.oma/development/coupled-office-campaign/package-peer-complete-reseal.xml'
shutil.copyfile(failed,TARGET/'retained-initial-two-summary-failures.xml')
closure = read(Path(result['package'])/'provenance/command-closure.json')
handoff = {'status':'SEALED_LOCAL_5E8_PACKAGE_AND_INDEPENDENT_AUDIT_PASS','package':result['package'],
    'source_checkpoint':result['source_checkpoint'],'checker_version':result['identity']['checker_version'],
    'native_extension_sha256':sealed['native_extension_sha256'],'file_count':sealed['file_count'],
    'logical_bytes':sealed['logical_bytes'],'artifact_index_sha256':sealed['artifact_index_sha256'],
    'sealed_handoff':identity(EVIDENCE/'sealed-handoff.json'),'independent_final_audit':identity(peer_path),
    'original_full':identity(ROOT/'evidence/release/coupled-tree-full-17ea63bc503a4b78bb572ffee1dce06f/result.json'),
    'custom_full':identity(ROOT/'evidence/dependencies/native-build/checkpoint-validation/5e8fe9659cfd-bbd4ca64f2c2/result.json'),
    'bundled_full':identity(EVIDENCE/'bundled-full-suite.json'),'bundled_passed':2464,'bundled_not_applicable':3,
    'declared_exact_nodes':2467,'declared_frozen_inputs':131,'app_source_files':107,
    'required_command_count':len(closure['commands']),'real_native_scopes':sealed['real_model_scopes'],
    'focused_packaging_tests':tests,'focused_test_scope':'73 harness cases plus48 independent cases replayed both on saved Office and a fresh analytic native fixture; separate from frozen2467 suite',
    'changed_sources':sources,'preparation':identity(PREP/'preparation.json'),
    'initial_resealed_summary_failures':identity(TARGET/'retained-initial-two-summary-failures.xml'),
    'correction_scope':'Pure service summary accepted coherent forged internal interval copies; fresh bounded envelope replay now rejects them. Outer managed Store/report binding was not bypassed by those helper tests.',
    'limitations':['Local package checkpoint, not whole-building or global routing optimality certification',
        'Coupled uniqueness/service applies only to the declared supported forward-flow model and its bound full parameter box; no reverse-flow or physical-model truth theorem',
        'Python audit-hook socket denial is not an OS/native-library firewall',
        'Not promoted; public redistribution remains not cleared; previous packages and original IFC/Store heads remain unchanged'],
    'next_custom_b965':'Prepared13d4bf10fdc041a3bb56a6d90af2d16e; explicitly UNLAUNCHED by parent instruction pending combined generation checkpoint'}
(TARGET/'handoff.json').write_text(json.dumps(handoff,indent=2),encoding='utf-8')
shutil.copyfile(__file__,TARGET/'executed-handoff.py')
print(json.dumps({'path':str(TARGET/'handoff.json'),'sha256':sha(TARGET/'handoff.json'),'commands':len(closure['commands'])}))
