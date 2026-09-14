"""Read-only original access and checked baseline/cache copying for private campaign."""
from pathlib import Path
import hashlib,json,shutil,sqlite3
from oma.store import Store,_Connection
from oma.ifc.audit import atomic_json,sha256_file
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
PRIOR_RUN='deb6bc686d184021aeb3646dd0f67e6c'
PRIOR_CANDIDATE='123924e355164a5ba330e5b30cc72384'
class Original(Store):
    def __init__(self,directory=None):
        self.directory=Path(directory or ROOT/'.oma').resolve()
        self.database=self.directory/'oma.sqlite3';self.blobs=self.directory/'blobs'
    def connect(self):
        db=sqlite3.connect(self.database.as_uri()+'?mode=ro',uri=True,factory=_Connection)
        db.row_factory=sqlite3.Row
        return db
    def put(self,value):raise RuntimeError('Original Store is read-only')

def copy_baseline(original, target, baseline_root):
    from oma.backup import _asset_references, _content_roots
    store = Store(target)
    pending, copied, references = {baseline_root}, set(), set()
    while pending:
        root = pending.pop()
        if root in copied:
            continue
        value = original.get(root)
        shutil.copyfile(original.blobs / (root + '.json.z'), store.blobs / (root + '.json.z'))
        assert store.get(root) == value
        copied.add(root)
        references.update(_asset_references(value))
        pending.update(r for r in _content_roots(value) if r not in copied and (original.blobs / (r + '.json.z')).is_file())
    assets, aliases = [], []
    for reference in sorted(references):
        source = original.resolve_path(reference).resolve()
        assert source.is_file(), source
        hashed = sha256_file(source)
        relative = Path('copied-baseline-inputs') / hashed / source.name
        destination = store.directory / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copyfile(source, destination)
        assert sha256_file(source) == sha256_file(destination) == hashed
        aliases.append((str(Path(reference).expanduser()), str(relative), hashed))
        assets.append({'reference': reference, 'source': str(source), 'copy': str(destination), 'sha256': hashed})
    with store.transaction() as db:
        db.executemany('INSERT INTO asset_aliases VALUES(?,?,?)', aliases)
    record = {'status': 'BASELINE_CLOSURE_COPIED', 'baseline_root': baseline_root,
        'artifact_roots': sorted(copied), 'assets': assets, 'original_database_access': 'READ_ONLY'}
    atomic_json(store.directory / 'baseline-input-copy.json', record)
    return store, record


def seed_native_cache(original, store, baseline, policy):
    """Copy exact-key native conversion artifacts; the checker revalidates them."""
    from oma.ifc.cad_cache import _key
    records = []
    for source in baseline['sources']:
        path = store.resolve_path(source['immutable_path'])
        key = _key(path, None, policy)
        root = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()
        origin = original.directory / 'cad-cache' / 'entries' / root
        if not (origin / 'manifest.json').is_file():
            records.append({'source_sha256': source['sha256'], 'cache_key': root, 'status': 'NO_EXACT_PRIOR_ENTRY'})
            continue
        raw = (origin / 'manifest.json').read_bytes()
        assert hashlib.sha256(raw).hexdigest() == (origin / 'manifest.sha256').read_text().strip()
        manifest = json.loads(raw)
        assert manifest['key'] == key
        destination = store.directory / 'cad-cache' / 'entries' / root
        destination.mkdir(parents=True)
        files = []
        for name in ('manifest.json', 'manifest.sha256'):
            shutil.copyfile(origin / name, destination / name)
            assert sha256_file(origin / name) == sha256_file(destination / name)
        for item in manifest['objects']:
            name = item['brep_sha256'] + '.brep.gz'
            asset = original.directory / 'cad-cache' / 'objects' / name
            target = store.directory / 'cad-cache' / 'objects' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(asset, target)
            assert sha256_file(asset) == sha256_file(target) == item['compressed_sha256']
            files.append({'name': name, 'sha256': item['compressed_sha256']})
        records.append({'source_sha256': source['sha256'], 'cache_key': root, 'status': 'EXACT_KEY_ARTIFACTS_COPIED',
            'manifest_sha256': hashlib.sha256(raw).hexdigest(), 'objects': files,
            'authority': 'Locally trusted checker conversion provenance only; source coverage and native topology rechecked, no pair verdict reuse'})
    return records

