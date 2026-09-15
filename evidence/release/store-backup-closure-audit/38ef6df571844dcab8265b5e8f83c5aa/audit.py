"""Read-only current Store closure versus the published initial backup manifest."""
from pathlib import Path
from collections import Counter, defaultdict
import hashlib
import json
import sqlite3
import time
import zlib

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / 'AGENTS.md').is_file())
LIVE = ROOT / '.oma'
INITIAL = ROOT / 'evidence/release/github-backup/1a202fcf467a47368a4b3abc1167eb94'
UPGRADE = ROOT / 'evidence/release/validated-backend-f73-update/dd31cd72c26c467d9c1b7de0af7c126b'
START = time.monotonic()

def pulse():
    if time.monotonic() - START > 180:
        raise TimeoutError('Bounded read-only closure audit exceeded 180 seconds')
def hash_file(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        while chunk := f.read(4 * 1024 * 1024):
            pulse()
            h.update(chunk)
    return h.hexdigest()
def load(p): return json.loads(p.read_text(encoding='utf-8'))
def connect(p):
    db = sqlite3.connect(p.resolve().as_uri() + '?mode=ro', uri=True)
    db.execute('BEGIN')
    return db
def tables(db):
    names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    return {n: db.execute('SELECT * FROM "' + n.replace('"','""') + '"').fetchall() for n in names}
def signature(rows):
    return Counter(json.dumps(r, ensure_ascii=False, separators=(',',':'), default=repr) for r in rows)

completed = load(INITIAL / 'completed-handoff.json')
assert hash_file(INITIAL / 'current-project-store-input-manifest.json') == completed['files']['current-project-store-input-manifest.json']
manifest = load(INITIAL / 'current-project-store-input-manifest.json')
backup = Path(manifest['root'])
base = {r['path']: r for r in manifest['files']}
assert len(base) == len(manifest['files']) == 4817
assert hash_file(backup / 'oma.sqlite3') == base['oma.sqlite3']['sha256']
assert hash_file(backup / 'backup-manifest.json') == base['backup-manifest.json']['sha256']
portable = load(backup / 'backup-manifest.json')
assert portable['format'] == 'oma-portable-store/1' and portable['status'] == 'COMPLETE'
assert len(portable['files']) == 4816
assert {r['path']: (r['size_bytes'],r['sha256']) for r in portable['files']} == {
    p:(v['bytes'],v['sha256']) for p,v in base.items() if p != 'backup-manifest.json'}
up = load(UPGRADE / 'handoff.json')
for name in ('before-store.sqlite3','before-all-store.json','result.json'):
    assert hash_file(UPGRADE / name) == up['retained_files'][name]
full = load(UPGRADE / 'before-all-store.json')['artifact_files']
old_db, snap_db, live_db = (connect(p) for p in (backup/'oma.sqlite3', UPGRADE/'before-store.sqlite3', LIVE/'oma.sqlite3'))
old, snap, current = (tables(db) for db in (old_db,snap_db,live_db))
assert set(old) == set(snap) == set(current) and len(old) == 14
assert all(signature(snap[n]) == signature(current[n]) for n in snap)
comparisons = []
for n in sorted(old):
    a,b = signature(old[n]),signature(current[n])
    comparisons.append({'table':n,'backup_rows':len(old[n]),'current_rows':len(current[n]),
                        'equal':a==b,'backup_only_rows':sum((a-b).values()),'current_only_rows':sum((b-a).values())})
different = {r['table'] for r in comparisons if not r['equal']}
assert different == {'metadata','asset_aliases','run_owners'}
assert len(old['asset_aliases']) == 13 and current['asset_aliases'] == []
assert old['run_owners'] == [] and len(current['run_owners']) == 75
assert dict(old['metadata']) == dict(current['metadata']) | {'relocation_roots': json.dumps([str(LIVE.resolve())])}

available = {p.removeprefix('blobs/').removesuffix('.json.z'): v for p,v in full.items()
             if p.startswith('blobs/') and p.endswith('.json.z')}
backed = {p.removeprefix('blobs/').removesuffix('.json.z') for p in base
          if p.startswith('blobs/') and p.endswith('.json.z')}
assert len(available) == 1088 and len(backed) == 1086 and backed <= set(available)

# Independently walk all JSON-valued database fields and reachable immutable
# documents. File fields follow the declared portable-store contract. Content
# roots are followed everywhere, including property values; file fields under
# arbitrary IFC properties/checksum maps are not executable asset references.
roots, references = set(), set()
file_keys = {'immutable_path','source_path','export_path','mesh_json_gz','mesh_npz','audit','replacement_path'}
def scan(value):
    stack = [(value, True)]
    while stack:
        item, assets = stack.pop()
        if isinstance(item,str):
            if item in available: roots.add(item)
        elif isinstance(item,list):
            stack.extend((x,assets) for x in item)
        elif isinstance(item,dict):
            for key,v in item.items():
                if assets and isinstance(v,str) and (key in file_keys or key == 'path' and ('sha256' in item or 'source_sha256' in item)):
                    references.add(v)
                stack.append((v, assets and key not in {'properties','artifact_sha256'}))
for rows in current.values():
    for row in rows:
        for value in row:
            if isinstance(value,str):
                if value in available: roots.add(value)
                if value.startswith(('{','[')):
                    try: scan(json.loads(value))
                    except json.JSONDecodeError: pass

visited, decoded_bytes = set(), 0
while roots - visited:
    pulse()
    root = min(roots - visited)
    relative = 'blobs/' + root + '.json.z'
    assert root in backed, ('Required content root missing from backup',root)
    data = (LIVE / relative).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    assert digest == base[relative]['sha256'] == available[root]['sha256']
    raw = zlib.decompress(data)
    assert hashlib.sha256(raw).hexdigest() == root
    decoded_bytes += len(raw)
    document = json.loads(raw)
    visited.add(root)
    scan(document)
    del document, raw, data
    if len(visited) % 100 == 0:
        print(json.dumps({'reachable_blobs':len(visited),'seconds':time.monotonic()-START}),flush=True)

aliases = {original:(relative,digest) for original,relative,digest in old['asset_aliases']}
asset_rows, file_cache = [], {}
def check_file(raw_path, *, sidecar=False):
    path = Path(raw_path).expanduser().resolve()
    assert path.is_file(), ('Missing current referenced file',str(path))
    if path not in file_cache:
        file_cache[path] = hash_file(path)
    digest = file_cache[path]
    if str(path) in aliases:
        relative, recorded = aliases[str(path)]
        assert digest == recorded
    elif path.is_relative_to(LIVE.resolve()):
        relative = path.relative_to(LIVE.resolve()).as_posix()
    else:
        relative = 'external-assets/' + digest + '/' + path.name
        if sidecar:
            # External IFC sidecars retain the parent IFC asset's directory.
            parent = path.with_suffix('.ifc')
            matches = [v[0] for k,v in aliases.items() if Path(k).with_suffix('.manifest.json') == path]
            assert len(matches) == 1, str(path)
            relative = str(Path(matches[0]).with_suffix('.manifest.json')).replace('\\','/')
    relative = relative.replace('\\','/')
    assert relative in base, ('Required file omitted from base manifest',str(path),relative)
    assert digest == base[relative]['sha256'] and path.stat().st_size == base[relative]['bytes']
    asset_rows.append({'reference':str(path),'backup_member':relative,'bytes':path.stat().st_size,
                       'sha256':digest,'sidecar':sidecar})
for reference in sorted(references):
    pulse()
    check_file(reference)
    path = Path(reference)
    if path.suffix.lower() == '.ifc' and path.with_suffix('.manifest.json').is_file():
        check_file(str(path.with_suffix('.manifest.json')),sidecar=True)

unbacked = sorted(set(available)-backed)
assert not set(unbacked) & visited
missing_raw = {p:v for p,v in full.items() if p not in base}
changed = {p:v for p,v in full.items() if p in base and v['sha256'] != base[p]['sha256']}
assert not changed
prefixes = defaultdict(lambda:{'files':0,'bytes':0})
for p,v in missing_raw.items():
    prefixes[p.split('/')[0]]['files'] += 1
    prefixes[p.split('/')[0]]['bytes'] += v['bytes']
end_db = connect(LIVE/'oma.sqlite3')
assert all(signature(rows)==signature(tables(end_db)[name]) for name,rows in current.items())
end_db.close()
for db in (old_db,snap_db,live_db): db.close()
result = {'status':'CURRENT_LIVE_STORE_REQUIRED_CLOSURE_ALREADY_BACKED_UP',
    'initial_published_manifest_sha256':hash_file(INITIAL/'current-project-store-input-manifest.json'),
    'f73_upgrade_handoff_sha256':hash_file(UPGRADE/'handoff.json'),
    'portable_database_sha256':base['oma.sqlite3']['sha256'], 'table_comparison':comparisons,
    'current_database_equals_completed_upgrade':True,'database_unchanged_during_audit':True,
    'initial_backup_manifest_files':4816,'current_preserved_raw_artifact_inventory_files':13190,
    'raw_files_absent_at_same_backup_path':len(missing_raw),
    'raw_bytes_absent_at_same_backup_path':sum(v['bytes'] for v in missing_raw.values()),
    'raw_missing_prefix_disposition':dict(sorted(prefixes.items())),
    'reachable_blobs_checked':len(visited),'reachable_blob_decoded_bytes':decoded_bytes,
    'asset_references_checked':len(references),'unique_required_asset_files_checked':len(file_cache),
    'required_asset_bytes_hashed':sum(p.stat().st_size for p in file_cache),
    'required_missing_files':0,'required_missing_bytes':0,
    'two_unbacked_blobs':unbacked,'two_unbacked_blob_bytes':sum(available[r]['bytes'] for r in unbacked),
    'unbacked_blob_scope':'Not reachable from any current database JSON/root through immutable documents; no accepted or candidate state depends on them.',
    'backup_database_differences':'Exactly the declared relocation aliases/metadata and removed old process owners; all application records equal.',
    'delta_recommendation':'No live project-state delta is needed at this snapshot. Keep the initial portable Store plus current committed application/evidence and separately versioned runtime. Do not copy raw caches or resurrect run ownership.',
    'future_delta_recipe':'For any later project publication, capture a consistent SQLite backup, remove live owners, preserve roots and relocation aliases; traverse the complete supported reference closure; copy only files whose path/hash is not supplied by a hash-pinned base. Publish a full reconstructed manifest and base+delta asset hashes. Assemble in a new directory and run verify_backup plus a read-only restored closure check before release.',
    'scope':'Read-only current-live Store and published-manifest comparison. No archive creation, download, extraction, remote revalidation, native test, CAD run or inclusion claim for every private temporary validation Store. Old checker reports may require fresh checking under f73.',
    'retained_initial_harness_failure':'initial-failure.json',
    'seconds':time.monotonic()-START,'script_sha256':hash_file(Path(__file__))}
for name,obj in [('result.json',result),('verified-required-assets.json',asset_rows),('reachable-blob-roots.json',sorted(visited))]:
    (HERE/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':result['status'],'reachable_blobs':len(visited),'required_assets':len(file_cache),
                  'missing_required_files':0,'missing_required_bytes':0,'seconds':result['seconds']}),flush=True)
