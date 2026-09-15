"""Read-only source/provenance review; never executes completion scripts."""
import ast
import hashlib
import json
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STAGE = ROOT / '.oma/development/factorized-tree-portable'
COMMIT = '633a6cdbcd75a24b0146f4d8228edef1bc0c4046'
OUT = Path(__file__).resolve().parent / 'completion-review' / uuid.uuid4().hex
OUT.mkdir(parents=True)

def digest(data):
    return hashlib.sha256(data).hexdigest()

raw = subprocess.check_output(['git', 'ls-tree', '-r', '-z', COMMIT], cwd=ROOT)
tree = {}
for record in raw.split(b'\0'):
    if not record:
        continue
    header, name = record.split(b'\t', 1)
    mode, kind, object_id = header.decode('ascii').split()
    tree[name.decode('utf-8')] = (mode, kind, object_id)
(OUT / 'git-ls-tree.bin').write_bytes(raw)

reviewed = {}
for name in ('final_handoff.py', 'complete_documentation.py', 'archive.py'):
    data = (STAGE / name).read_bytes()
    ast.parse(data.decode('utf-8-sig'), filename=name)
    (OUT / name).write_bytes(data)
    reviewed[name] = {'sha256': digest(data), 'bytes': len(data)}

captured = {}
manifest_hashes = {}
for folder in ('documentation-source-633a6cdb', 'documentation-registers-633a6cdb'):
    source = STAGE / folder
    data = (source / 'source-manifest.json').read_bytes()
    manifest = json.loads(data.decode('utf-8-sig'))
    assert manifest['git_commit'] == COMMIT
    manifest_hashes[folder] = digest(data)
    (OUT / (folder + '-manifest.json')).write_bytes(data)
    assert set(manifest['files']).isdisjoint(captured)
    assert {p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()} == set(manifest['files']) | {'source-manifest.json'}
    for name, row in manifest['files'].items():
        data = (source / name).read_bytes()
        assert digest(data) == row['sha256'] and len(data) == row['bytes'], name
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest()
        assert tree[name][1] == 'blob' and blob == tree[name][2] == row['git_blob'], name
        captured[name] = {'sha256': digest(data), 'bytes': len(data), 'git_blob': blob}
assert len(captured) == 73
for name, row in reviewed.items():
    assert digest((STAGE / name).read_bytes()) == row['sha256']

result = {
    'schema': 'oma.portable-completion-script-peer-review/1',
    'status': 'F73_COMPLETION_SOURCE_AND_DOCUMENTATION_REVIEW_PASS',
    'git_commit': COMMIT,
    'git_tree_sha256': digest(raw),
    'reviewed_scripts': reviewed,
    'captured_documentation': {'file_count': len(captured), 'bytes': sum(r['bytes'] for r in captured.values()), 'files': captured, 'manifest_sha256': manifest_hashes},
    'static_findings': [
        'Initial outer-receipt retention gap was reported and corrected: all seven core receipt files are now bound to seal hashes before and after exact byte copying; peer SHA is an explicit argument; package index is rechecked.',
        'Archive reads sealed package and separate docs namespaces; exact physical membership and both self-index exceptions are explicit. Every compressed input stream and every decompressed ZIP member is checked against its namespace inventory.',
        'Documentation guidance distinguishes historical EDF package docs from the current f73 companion, package default port 8765 from separate workspace service 8768, and runtime backup from separate building data.',
        'All 73 captured documentation/example/register files independently match immutable Git tree object IDs, Git blob hashes, byte counts and SHA256 values.'
    ],
    'remaining_concrete_findings': [],
    'scope': 'Read-only source/provenance review. Completion scripts were AST-parsed but not executed. No archive creation, package modification, native rerun or final sealed-package audit occurred in this review.',
}
(OUT / 'executed-review.py').write_bytes(Path(__file__).read_bytes())
(OUT / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps({'directory': str(OUT), 'status': result['status'], 'result_sha256': digest((OUT / 'result.json').read_bytes()), 'documentation_files': 73, 'documentation_bytes': result['captured_documentation']['bytes']}))
