"""Copy completed, independently audited validation evidence without altering it."""
from pathlib import Path
import hashlib
import importlib.util
import json
import shutil

STAGE = Path(__file__).resolve().parent
ROOT = STAGE.parents[2]
BASE = ROOT / '.oma/development/shared-tree-native/integration-validation/0c61106b1aba4f8b81552bd5e201b9a9'
PUBLIC = ROOT / 'evidence/math/shared-tree-generation-validation'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

assert not PUBLIC.exists(), 'Never overwrite retained evidence'
frozen = read(STAGE / 'frozen-inputs.json')
assert sha(STAGE / 'frozen-inputs.json') == 'd974f896a9d0f2d78ac9b03af3d91bed4419e4996417eecbbcae8d94263c3b9b'
post = read(STAGE / 'completed-independent-audit.json')
assert post['status'] == 'PASS' and post['full_tests'] == 2788
spec = importlib.util.spec_from_file_location('public_retention_inventory', STAGE / 'inventory-helper.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)

records = {'base-b965': (BASE, read(BASE / 'result.json'), 2696)}
for phase, count in (('focused', 360), ('full', 2788)):
    done = read(STAGE / (phase + '-complete.json'))
    directory = Path(done['directory'])
    record = read(directory / 'result.json')
    assert done['status'] == record['status'] == 'PASS'
    assert sha(directory / 'result.json') == done['result_sha256']
    records['combined/' + phase] = (directory, record, count)

# Reaccount the historical base as well as the current completed run before copying.
audits = {}
for label, (directory, record, count) in records.items():
    assert record['status'] == 'PASS' and record['passed'] == count
    nodes = read(directory / 'test-nodes.json')
    assert len(nodes) == count
    exact = helper.account_xml(directory / 'tests.xml', nodes)
    assert exact['passed'] == count
    source = Path(record['source_directory'])
    assert {p.relative_to(source).as_posix(): sha(p) for p in source.rglob('*.py')} == record['source_files']
    snapshot = Path(record['test_snapshot'])
    assert all(sha(snapshot / key) == value for key, value in record['snapshot_files'].items())
    if label != 'combined/focused':
        inventory = helper.snapshot(snapshot, record['snapshot_files'])
        assert inventory['derived_output_sha256'] == record['derived_test_outputs']
        assert len(inventory['derived_output_sha256']) == 6
    audits[label] = {'status': 'PASS', 'tests': count, 'exact_xml': exact,
                     'receipt_sha256': sha(directory / 'result.json'),
                     'source_count': len(record['source_files']),
                     'declared_inputs': len(record['snapshot_files'])}

PUBLIC.mkdir(parents=True)
origins = {}

def copy(original, relative, expected=None):
    original = Path(original)
    digest = sha(original)
    assert expected is None or digest == expected
    target = PUBLIC / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        assert sha(target) == digest
    else:
        shutil.copyfile(original, target)
    assert sha(target) == digest and sha(original) == digest
    origins[relative] = {'original': str(original.resolve()), 'sha256': digest}

for path in sorted(STAGE.iterdir()):
    if path.is_file():
        copy(path, 'combined/control/' + path.name)
for path in sorted((STAGE / 'retained-adjustments').rglob('*')):
    if path.is_file():
        copy(path, 'combined/retained-adjustments/' + path.relative_to(STAGE / 'retained-adjustments').as_posix())
for key, value in frozen['snapshot_files'].items():
    copy(Path(frozen['input_snapshot']) / key, 'combined/master/' + key, value)

locations = {}
for label, (directory, record, count) in records.items():
    source_label = 'sources/' + record['checker_version'].split(':')[-1] + '/src'
    for key, value in record['source_files'].items():
        copy(Path(record['source_directory']) / key, source_label + '/' + key, value)
    for path in sorted(directory.iterdir()):
        if path.is_file():
            copy(path, label + '/' + path.name)
    input_files = dict(record['snapshot_files'])
    input_files.update(record.get('derived_test_outputs', {}))
    for key, value in input_files.items():
        copy(Path(record['test_snapshot']) / key, label + '/snapshot/' + key, value)
    locations[label] = {'receipt': label + '/result.json', 'snapshot': label + '/snapshot',
                        'source': source_label, 'original_directory': str(directory),
                        'original_source': record['source_directory'],
                        'original_snapshot': record['test_snapshot'], 'passed': count,
                        'checker_version': record['checker_version']}

# Check the portable copies themselves; raw historical receipts remain byte-for-byte intact.
for label, (directory, record, count) in records.items():
    exact = helper.account_xml(PUBLIC / label / 'tests.xml', read(PUBLIC / label / 'test-nodes.json'))
    assert exact['passed'] == count
    if label != 'combined/focused':
        inventory = helper.snapshot(PUBLIC / label / 'snapshot', record['snapshot_files'])
        assert inventory['derived_output_sha256'] == record['derived_test_outputs']
    assert all(sha(PUBLIC / locations[label]['source'] / key) == value for key, value in record['source_files'].items())
    audits[label]['portable_copy_rechecked'] = True

write(PUBLIC / 'original-locations.json', {'schema': 'oma.validation-portable-locations/1',
      'records': locations, 'copied_files': origins})
write(PUBLIC / 'portable-audit.json', {'schema': 'oma.shared-tree-validation-portable-audit/1',
      'status': 'PASS', 'records': audits, 'all_copies_match_original_bytes': True,
      'raw_receipts_rewritten': False, 'no_test_rerun': True,
      'excluded': ['Python bytecode and pytest caches', 'temporary native-stores trees',
                   'interpreter and installed native DLL/PYD binaries'],
      'excluded_originals_retained': True})
(PUBLIC / 'README.md').write_text('''# Shared-tree generation: frozen validation evidence

The original native environment passed the exact frozen combined **2,788-test** suite and its **360-test** focused subset on source `33a20d125bba02a298d12048a5b6227e51a98d8a043b999097d94a8d88b67b95`. The separately retained historical base passed **2,696 tests** on `b9652e8e197783facaa03d3e837d67962bb9a60388783b345180833d19402cc1`.

This is the declared frozen suite, not every test subsequently added to the working repository. In particular, later package-harness validation and the custom native environment have separate receipts. These tests do not establish completion of the full original mathematical algorithms or global physical optimization.

`handoff.json` identifies the exact file index. `file-index.json` hashes every payload file, including `original-locations.json`, whose mappings locate byte-identical portable copies of paths retained in the original receipts. `portable-audit.json` records a fresh exact XML node-multiset and source/input/derived-output audit without rerunning tests. Both full runs retain all six explicitly allowed derived outputs, with no unexplained non-cache snapshot files.

The combined declaration has 112 source files and 162 test/support inputs; its historical base has 145 test/support inputs. `combined/control/test-denominator-audit.json` records all 2,696 base nodes retained and 92 additions. The two unsupported-profile fixture changes are retained as original bytes, replacements and diffs under `combined/retained-adjustments/`: only the unsupported example changed from newly supported coupled pressure to still unsupported passive-tree generation.

Source trees, declared inputs, XML, logs, node lists, runners, manifests, completion receipts and native-library identities are included. Original absolute paths in raw receipts have not been rewritten. Temporary native Stores, caches and installed interpreter/native binaries are not copied; their originals remain at the mapped locations. This evidence directory is not a replacement for the application's runnable distribution.
''', encoding='utf-8')
files = {p.relative_to(PUBLIC).as_posix(): sha(p) for p in sorted(PUBLIC.rglob('*')) if p.is_file()}
write(PUBLIC / 'file-index.json', {'schema': 'oma.exact-evidence-file-index/1', 'files': files,
      'excluded_self_and_handoff': ['file-index.json', 'handoff.json']})
handoff = {'schema': 'oma.shared-tree-generation-validation-handoff/1', 'status': 'PASS',
           'index': 'file-index.json', 'index_sha256': sha(PUBLIC / 'file-index.json'),
           'payload_files': len(files), 'records': locations, 'audits': audits,
           'frozen_input_sha256': sha(STAGE / 'frozen-inputs.json'),
           'portable_audit_sha256': sha(PUBLIC / 'portable-audit.json'),
           'scope': 'Frozen original-native 2788 full / 360 focused and historical 2696 full only; no current-repository-total, custom-environment, or new package claim'}
write(PUBLIC / 'handoff.json', handoff)
assert all(sha(PUBLIC / key) == value for key, value in files.items())
print(json.dumps({'status': 'PASS', 'path': str(PUBLIC), 'payload_files': len(files),
                  'handoff_sha256': sha(PUBLIC / 'handoff.json'),
                  'index_sha256': sha(PUBLIC / 'file-index.json')}))
