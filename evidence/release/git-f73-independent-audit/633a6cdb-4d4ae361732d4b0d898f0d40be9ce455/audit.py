"""Read-only immutable-commit byte and recovery-entrypoint audit; no test run."""
from pathlib import Path, PurePosixPath
from collections import Counter
import hashlib
import json
import posixpath
import re
import subprocess
import xml.etree.ElementTree as ET

COMMIT = '633a6cdbcd75a24b0146f4d8228edef1bc0c4046'
F73 = 'f73a8793ae0df76d9ec53400cec18b05d2731f63c735b225c2246fee62df6b21'
HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / 'AGENTS.md').is_file())
FULL = 'evidence/release/compact-tree-original-full-d6d1204384b8'
DOCS = 'evidence/math/compact-factorized-documentation/fa54e8be956c4e1684f3dc23bea04b8f/handoff.json'
CUSTOM = 'evidence/release/factorized-tree-custom-completed-0cf1c8bf0868/handoff.json'
LIVE = 'evidence/release/validated-backend-f73-update/dd31cd72c26c467d9c1b7de0af7c126b/handoff.json'
BACKUP = 'evidence/release/github-backup/1a202fcf467a47368a4b3abc1167eb94'
EDF = 'evidence/release/github-edf-portable/completed-218ccb24ff4d4ba7824d1187b95f57e4'
HOSPITALS = ['evidence/benchmarks/hospital-generated-tree/' + p for p in (
    'full-federation-1e87dd6ad9af48b5962cd500603fdfdc',
    'architecture-d3e1be8f981146fcadede8107addadbe')]

def sha(data): return hashlib.sha256(data).hexdigest()
def git(*args, data=None):
    return subprocess.run(['git', *args], cwd=ROOT, input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=60, check=True).stdout
assert git('rev-parse', COMMIT + '^{commit}').decode().strip() == COMMIT
assert git('rev-parse', '--show-object-format').decode().strip() == 'sha1'
tree_raw = git('ls-tree', '-r', '--full-tree', '-z', COMMIT)
assert len(tree_raw) < 64 * 1024 * 1024
tree = {}
for item in tree_raw.rstrip(b'\0').split(b'\0'):
    meta, path = item.split(b'\t', 1)
    mode, kind, oid = meta.decode().split()
    name = path.decode('utf-8')
    assert name not in tree
    tree[name] = {'mode': mode, 'kind': kind, 'object': oid}

cache = {}
def fetch(names):
    names = sorted(set(names) - set(cache))
    if not names: return
    assert len(names) <= 2048
    for name in names:
        assert name in tree and tree[name]['kind'] == 'blob', name
        assert tree[name]['mode'] in ('100644', '100755'), name
    raw = git('cat-file', '--batch', data=''.join(tree[n]['object'] + '\n' for n in names).encode('ascii'))
    assert len(raw) < 128 * 1024 * 1024
    position = 0
    for name in names:
        end = raw.index(b'\n', position)
        oid, kind, size_text = raw[position:end].decode().split()
        size = int(size_text)
        assert oid == tree[name]['object'] and kind == 'blob'
        start = end + 1
        content = raw[start:start + size]
        assert len(content) == size and raw[start + size:start + size + 1] == b'\n'
        assert hashlib.sha1(b'blob ' + str(size).encode() + b'\0' + content).hexdigest() == oid
        cache[name] = content
        position = start + size + 1
    assert position == len(raw)
def load(name):
    fetch([name])
    return json.loads(cache[name].decode('utf-8'))

pinned = {FULL + '/handoff.json': '9bce3f89d8801dd8a94b7ef0169cf5d9494a37ad6535145f7335abe29c273beb',
          CUSTOM: '9d240091e585e690f7ca51747e3c71c9f89e37606c4d35b65b47f784b69b8612',
          LIVE: 'bd85221893954eeae54910a20361e0f9913144f30f9504bb9af2e07285db70e4'}
fetch([*pinned, DOCS])
for name, digest in pinned.items(): assert sha(cache[name]) == digest
full, docs = load(FULL + '/handoff.json'), load(DOCS)
assert full['checker_version'] == 'oma-independent-checker/2:' + F73
assert docs['source_checkpoint'] == F73
assert full['accounting'] == {'passed': 3275, 'failed': 0, 'skipped': []}
manifest_names = ['source.json', 'inputs.json', 'test-nodes.json', 'tests.xml', 'derived-outputs.json', 'native-environment.json']
fetch([FULL + '/' + p for p in manifest_names])
for p in manifest_names: assert sha(cache[FULL + '/' + p]) == full['retained_files'][p], p
source = load(FULL + '/source.json')
inputs = load(FULL + '/inputs.json')['files']
assert source == full['source_manifest'] and inputs == full['snapshot_inputs']
assert len(source) == 114 and len(inputs) == 305 and len(docs['files']) == 10
groups = {'application_source': {'src/' + p: h for p, h in source.items()},
          'frozen_test_support': inputs, 'integrated_docs_examples': docs['files']}
assert {p for p in tree if p.startswith('src/') and p.endswith('.py')} == set(groups['application_source'])
committed_tests = {p for p in tree if p.startswith('tests/') and p.endswith('.py')}
assert committed_tests <= set(inputs) and len(committed_tests) == 138
expected = {}
for group in groups.values():
    assert not set(group) & set(expected)
    expected.update(group)
assert len(expected) == 429
fetch(expected)
comparison = []
for category, group in groups.items():
    for path, digest in sorted(group.items()):
        actual = sha(cache[path])
        assert actual == digest, (path, actual, digest)
        comparison.append({'group': category, 'path': path, 'git_blob': tree[path]['object'],
                           'bytes': len(cache[path]), 'sha256': actual})

# Independent comparison of retained exact node IDs to the recorded JUnit
# testcase multiset; this reads evidence, not pytest or native code.
nodes = load(FULL + '/test-nodes.json')
assert len(nodes) == len(set(nodes)) == 3275
declared = Counter()
for node in nodes:
    parts = node.split('::')
    assert parts[0] in inputs and len(parts) >= 2
    module = parts[0].removesuffix('.py').replace('/', '.')
    declared[('.'.join([module, *parts[1:-1]]), parts[-1])] += 1
xml = ET.fromstring(cache[FULL + '/tests.xml'])
cases = list(xml.iter('testcase'))
assert len(cases) == 3275
assert not any(list(c) for c in cases), 'No failing/skipped/error testcase children expected'
recorded = Counter((c.attrib['classname'], c.attrib['name']) for c in cases)
assert declared == recorded

entrypoints = ['AGENTS.md', 'docs/PROGRESS.md', 'docs/GITHUB_BACKUP.md', 'docs/native-portable-candidate.md',
    'docs/shared-tree-generation.md', 'docs/math/shared-tree-topk.md', 'docs/math/factorized-tree-pressure.md',
    'docs/checkpoint-edf-before-compact.md', '.gitattributes', 'requirements.lock',
    BACKUP + '/completed-handoff.json', BACKUP + '/BACKUP-COMPLETE.json', BACKUP + '/RESTORE.md',
    BACKUP + '/backup-assets-manifest.json', BACKUP + '/original-mathematics-input-manifest.json',
    BACKUP + '/hospital-original-models-input-manifest.json', EDF + '/completed-handoff.json']
for p in HOSPITALS:
    entrypoints += [p + '/' + f for f in ('README.md', 'files.json', 'handoff.json', 'public-mapping.json', 'scripts/verify_retention.py')]
fetch(entrypoints)
links = []
for path in entrypoints:
    if not path.endswith('.md'): continue
    text = cache[path].decode('utf-8')
    for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', text):
        if re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', target):
            links.append({'from': path, 'target': target, 'scope': 'EXTERNAL_LINK_RETAINED_NOT_FETCHED'})
            continue
        if target.startswith('#'): continue
        normalized = posixpath.normpath(posixpath.join(posixpath.dirname(path), target.split('#')[0]))
        assert normalized in tree and tree[normalized]['kind'] == 'blob', (path, target)
        links.append({'from': path, 'target': normalized, 'scope': 'COMMITTED_BLOB_EXISTS'})
backup = load(BACKUP + '/completed-handoff.json')
assert backup['all_jobs_complete'] is True
for file in ('BACKUP-COMPLETE.json', 'RESTORE.md', 'backup-assets-manifest.json',
             'original-mathematics-input-manifest.json', 'hospital-original-models-input-manifest.json'):
    assert sha(cache[BACKUP + '/' + file]) == backup['files'][file]
edf = load(EDF + '/completed-handoff.json')
assert edf['status'] == 'PRIVATE_PRERELEASE_PUBLISHED_AND_VERIFIED'
assert edf['source_checkpoint'].startswith('edf555') and len(edf['assets']) == 3
assert sum(v['bytes'] for v in edf['assets'].values()) == edf['total_bytes'] == 1174189376
assert docs['history_sha256'] == sha(cache['docs/checkpoint-edf-before-compact.md'])
capabilities = load('docs/capabilities.json')
assert capabilities['release_status'] == 'IN_PROGRESS'
trace = load('evidence/math/traceability_register.json')
algorithms = load('evidence/math/source_algorithm_capabilities.json')
assert len(trace['obligations']) == 42 and trace['full_engine_mathematics_implemented'] is False
assert algorithms['all_source_algorithms_implemented'] is False
assert all(x['full_algorithm_implemented'] is False for x in algorithms['algorithms'])
fetch([CUSTOM, LIVE])
assert load(CUSTOM)['test_nodes'] == 3275 and load(CUSTOM)['failed'] == load(CUSTOM)['skipped'] == 0
assert load(LIVE)['status'] == 'VALIDATED_F73_LIVE_UPDATE_COMPLETED'

result = {'status': 'IMMUTABLE_COMMIT_F73_BYTES_AND_ENTRYPOINTS_PASS', 'commit': COMMIT, 'source_checkpoint': F73,
    'checked_group_counts': {k: len(v) for k,v in groups.items()}, 'exact_files': 429,
    'complete_committed_python_source_inventory': 114,
    'all_committed_python_test_files_in_frozen_inputs': 138,
    'declared_and_xml_node_multiset': {'count': 3275, 'status': 'PASS'},
    'full_receipt_hashes': pinned, 'documentation_manifest_sha256': sha(cache[DOCS]),
    'entrypoint_count': len(entrypoints), 'entrypoint_links': links,
    'frozen_native_environment_sha256': sha(cache[FULL + '/native-environment.json']),
    'retained_derived_output_receipt_sha256': sha(cache[FULL + '/derived-outputs.json']),
    'edf_archive_receipt': {'source_checkpoint': edf['source_checkpoint'], 'assets': edf['assets'],
                            'scope': 'Previously recorded remote equality only; no new remote check or archive download'},
    'hospital_scope': 'Committed complete-federation alignment blocker and separate architecture timeout entrypoints retained; no native acceptance inferred.',
    'reproducibility_scope': 'Committed application and all frozen test/support bytes match the completed original suite. XML/node and environment receipts are retained. No execution, dependency install, fresh build or package redownload performed.',
    'all_original_math_complete': False, 'all_full_algorithm_flags_false': True,
    'tests_or_CAD_run': False, 'git_or_source_or_index_modified': False,
    'working_tree_NOT_authority': True, 'script_sha256': sha(Path(__file__).read_bytes()),
    'tree_inventory_sha256': sha(tree_raw)}
for filename, obj in [('result.json', result), ('verified-files.json', comparison),
                      ('verified-entrypoints.json', {p: {'git_blob': tree[p]['object'], 'sha256': sha(cache[p])} for p in entrypoints})]:
    (HERE / filename).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': result['status'], 'commit': COMMIT, 'exact_files': 429,
                  'nodes': 3275, 'entrypoints': len(entrypoints), 'result_sha256': sha((HERE / 'result.json').read_bytes())}))
