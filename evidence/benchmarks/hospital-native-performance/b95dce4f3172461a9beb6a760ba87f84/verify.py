from pathlib import Path
import gzip,hashlib,json
root=Path(__file__).resolve().parent
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
index=json.loads((root/'files.json').read_text());rows=index['files']
assert len(rows)==len({r['path'] for r in rows})
assert {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}=={r['path'] for r in rows}|{'files.json','handoff.json'}
for row in rows:
    p=root/row['path'];assert p.resolve().is_relative_to(root) and not p.is_symlink()
    assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
for row in json.loads((root/'public-mapping.json').read_text()):
    p=root/row['retained_path'];assert sha(p)==row['retained_sha256']
    data=gzip.decompress(p.read_bytes()) if row['encoding']=='gzip' else p.read_bytes()
    assert len(data)==row['original_bytes'] and hashlib.sha256(data).hexdigest()==row['original_sha256']
handoff=json.loads((root/'handoff.json').read_text());assert sha(root/'files.json')==handoff['index_sha256']
print(json.dumps({'status':'EXACT_RETAINED_BYTES_AND_MAPPING_PASS','files':len(rows),'original_mappings':len(json.loads((root/'public-mapping.json').read_text()))}))
