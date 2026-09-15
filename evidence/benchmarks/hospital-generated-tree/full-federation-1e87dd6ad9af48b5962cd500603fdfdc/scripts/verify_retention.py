"""Portable standard-library byte verification of one public hospital handoff."""
from pathlib import Path
import gzip,hashlib,json,sys
root=Path(sys.argv[1]).resolve()
def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
index=read(root/'files.json');handoff=read(root/'handoff.json')
assert sha(root/'files.json')==handoff['index_sha256']
assert index['excluded']==['files.json','handoff.json']
rows=index['files'];assert len(rows)==len({r['path'] for r in rows})==index['file_count']==handoff['indexed_files']
assert {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}=={r['path'] for r in rows}|set(index['excluded'])
for row in rows:
    path=(root/row['path']).resolve();assert path.is_relative_to(root) and not path.is_symlink()
    assert path.stat().st_size==row['bytes'] and sha(path)==row['sha256'],row['path']
assert sum(r['bytes'] for r in rows)==index['bytes']==handoff['indexed_bytes']
mapping=read(root/'public-mapping.json')
for row in mapping['files']:
    path=(root/row['path']).resolve();assert path.is_relative_to(root)
    assert sha(path)==row['sha256']
    if row['encoding']=='gzip':
        with gzip.open(path,'rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==row['original_sha256']
    else:assert row['encoding']=='identity' and sha(path)==row['original_sha256']
print(json.dumps({'status':'PASS','indexed_files':len(rows),'indexed_bytes':index['bytes'],
    'decoded_original_hashes_checked':len(mapping['files']),'original_private_paths_read':False,
    'scope':'Exact retained bytes only; native and engineering verdicts remain scoped by original receipts.'},indent=2))
