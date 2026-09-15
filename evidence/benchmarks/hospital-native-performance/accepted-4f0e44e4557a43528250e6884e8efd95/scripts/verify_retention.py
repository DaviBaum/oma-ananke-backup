"""Standard-library verification of retained bytes, decoded originals and closed index."""
from pathlib import Path
import gzip
import hashlib
import json
import sys

root = Path(sys.argv[1]).resolve()
def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
def read(path):
    return json.loads(path.read_bytes())
index, retained = read(root/'index.json'), read(root/'retention.json')['retained_files']
assert {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()} == set(retained) | {'retention.json'}
assert all(sha(root/name) == value for name,value in retained.items())
assert len(index['files']) == index['file_count']
assert sum(row['bytes'] for row in index['files'].values()) == index['bytes']
for name,row in index['files'].items():
    path = root/name
    assert path.stat().st_size == row['bytes'] and sha(path) == row['sha256']
for row in read(root/'public-mapping.json')['files']:
    path = root/row['path']
    assert sha(path) == row['sha256']
    if row['encoding'] == 'gzip':
        with gzip.open(path, 'rb') as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == row['original_sha256']
    else:
        assert sha(path) == row['original_sha256']
handoff = read(root/'handoff.json')
assert handoff['index_sha256'] == sha(root/'index.json')
assert handoff['summary_sha256'] == sha(root/'summary.json')
print(json.dumps({'status': 'EXACT_RETAINED_BYTES_PASS', 'files': len(retained)+1, 'index_sha256': sha(root/'index.json')}))
