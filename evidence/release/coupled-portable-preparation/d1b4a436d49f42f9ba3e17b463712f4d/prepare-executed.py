import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import uuid
import zlib

ROOT = Path(__file__).resolve().parents[3]
SOURCE = '5e8fe9659cfde60f84f5cf93f38a1959428b3e7522de741e905d1f505db2b73c'
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def write(path, value): Path(path).write_text(json.dumps(value, indent=2), encoding='utf-8')
directory = ROOT / 'evidence/release/coupled-portable-preparation' / uuid.uuid4().hex
directory.mkdir(parents=True)
old = ROOT / '.release/native-build/portable-candidates/52bd5d292171-2563efa50156/provenance/real-model-validation-inputs.json'
plan = read(old)
plan.update(schema='oma.portable-real-model-inputs/2', source_checkpoint=SOURCE,
            scope='Three separately declared immutable exported Office cases; original Stores read-only. Current native, exact-model and service proofs remain limited to each fixed declared mission.')
source_store = ROOT / '.oma/development/coupled-office-campaign/bench-stores/fd34a7bc66b04290a8a6b8c46b78a7ab'
cid = '269952d7410844a18c7cff57217634a1'
with sqlite3.connect((source_store / 'oma.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
    state_root, report_root, payload, status = db.execute('SELECT state_root,report_root,payload,status FROM candidates WHERE id=?', (cid,)).fetchone()
kind = json.loads(payload)['kind']
assert status == 'CHECKED' and kind == 'physical_network'
report = json.loads(zlib.decompress((source_store / 'blobs' / (report_root + '.json.z')).read_bytes()))
manifest_path = ROOT / 'evidence/benchmarks/coupled-pressure/office/fd34a7bc66b04290a8a6b8c46b78a7ab/export-manifest.json'
manifest = read(manifest_path)
assert manifest['status'] == 'CHECKED_LOCAL_SCOPE' and manifest['exported_state_root'] == state_root
assert manifest['verification_root'] == report_root and report['checker_version'] == 'oma-independent-checker/2:' + SOURCE
export, = manifest['files']
assert sha(export['path']) == export['sha256']
plan['roles']['coupled_pressure_network'] = dict(candidate_id=cid, candidate_root=state_root,
    prior_report_root=report_root, prior_checker_version=report['checker_version'], physical_kind=kind,
    original_store=str(source_store), expected_export_sha256=export['sha256'])
write(directory / 'real-model-inputs.json', plan)
checkpoint = ROOT / 'evidence/dependencies/native-build/checkpoint-validation/5e8fe9659cfd-bbd4ca64f2c2/result.json'
assert read(checkpoint)['status'] == 'CUSTOM_NATIVE_NEW_CHECKPOINT_FULL_SUITE_PASS'
sources = {}
for path in sorted((ROOT / 'scripts').glob('native_*.py')):
    target = directory / 'driver-sources' / path.name
    target.parent.mkdir(exist_ok=True)
    shutil.copyfile(path, target)
    sources[path.relative_to(ROOT).as_posix()] = sha(path)
for name in ('test_native_package_three_roles.py', 'test_native_coupled_package_adversarial.py', 'test_native_command_evidence.py'):
    path = ROOT / 'tests' / name
    target = directory / 'focused-tests' / name
    target.parent.mkdir(exist_ok=True)
    shutil.copyfile(path, target)
write(directory / 'preparation.json', dict(schema='oma.coupled-portable-preparation/1', source_checkpoint=SOURCE,
    checkpoint_validation=str(checkpoint), checkpoint_validation_sha256=sha(checkpoint),
    real_model_inputs_sha256=sha(directory/'real-model-inputs.json'), old_two_role_declaration_sha256=sha(old),
    coupled_export_manifest_sha256=sha(manifest_path), driver_sources=sources,
    ui_files={p.relative_to(ROOT/'ui/dist').as_posix():sha(p) for p in (ROOT/'ui/dist').rglob('*') if p.is_file()},
    expected_nodes=2467, expected_inputs=131, expected_app_files=107,
    focused_harness_tests='Separate packaging tests; not included in frozen application full suite'))
shutil.copyfile(__file__, directory/'prepare-executed.py')
print(directory)
