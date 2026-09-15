"""Prepare isolated backend files and a read-only backup of the closed campaign."""
from pathlib import Path
import hashlib
import json
import shutil
import sqlite3
import sys
import urllib.request
import uuid
import zlib

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
ROOT = STAGE.parents[2]
REGRESSION = STAGE / 'combined-validation/c3482addaad441e5958746e2ab7a41ba/result.json'
SOURCE_STORE = STAGE / 'stores/1cbf8d8cc3c3485896f01b7a41a007fa'
BUILD = 'oma-independent-checker/2:b72cb24732b8b1d5ab08fdebda5e5649640a652b82bdda24a58f00d4da81b52c'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def file_inventory(directory):
    return {p.relative_to(directory).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size}
            for p in sorted(directory.rglob('*')) if p.is_file()}


def readonly_db(path):
    return sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True)


def db_inventory(path):
    with readonly_db(path) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        result = {}
        for name, in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
            quoted = '"' + name.replace('"', '""') + '"'
            rows = sorted(json.dumps(row, ensure_ascii=False, separators=(',', ':'))
                          for row in db.execute('SELECT * FROM ' + quoted))
            result[name] = {'rows': len(rows), 'sha256': hashlib.sha256(('\n'.join(rows) + '\n').encode()).hexdigest()}
        return result


result = json.loads(REGRESSION.read_text())
assert result['checker_version'] == BUILD
assert len(result['source_files']) == 117
assert result['status'] in ('RUNNING', 'PASS'), result['status']
out = HERE / ('b72cb-' + uuid.uuid4().hex)
out.mkdir()
runtime, cloned_store = out / 'runtime', out / 'store'
source_dir = Path(result['source_directory'])
expected = result['source_files']
assert {p.relative_to(source_dir).as_posix(): sha(p) for p in source_dir.rglob('*.py')} == expected
for relative, expected_sha in expected.items():
    destination = runtime / 'src' / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_dir / relative, destination)
    assert sha(destination) == expected_sha
assert {p.relative_to(runtime / 'src').as_posix(): sha(p) for p in (runtime / 'src').rglob('*.py')} == expected
ui_files = [p for p in (ROOT / 'ui/dist').rglob('*') if p.is_file()]
assert len(ui_files) == 6
support = {}
for source in [*ui_files, ROOT / 'docs/capabilities.json']:
    before_hash = sha(source)
    relative = source.relative_to(ROOT)
    target = runtime / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    assert sha(source) == sha(target) == before_hash
    support[relative.as_posix()] = before_hash

# immutable=1 prevents SQLite from touching the closed source's WAL/SHM files.
# It is only valid here because the completed campaign has an empty WAL.
assert not (SOURCE_STORE / 'oma.sqlite3-wal').exists() or (SOURCE_STORE / 'oma.sqlite3-wal').stat().st_size == 0
source_before = file_inventory(SOURCE_STORE)
table_before = db_inventory(SOURCE_STORE / 'oma.sqlite3')
cloned_store.mkdir()
with readonly_db(SOURCE_STORE / 'oma.sqlite3') as origin, sqlite3.connect(cloned_store / 'oma.sqlite3') as destination:
    origin.backup(destination)
for source in (SOURCE_STORE / 'blobs').rglob('*'):
    if source.is_file():
        target = cloned_store / source.relative_to(SOURCE_STORE)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        assert sha(source) == sha(target)
assert db_inventory(cloned_store / 'oma.sqlite3') == table_before
assert file_inventory(cloned_store / 'blobs') == file_inventory(SOURCE_STORE / 'blobs')
assert file_inventory(SOURCE_STORE) == source_before

with readonly_db(cloned_store / 'oma.sqlite3') as db:
    db.row_factory = sqlite3.Row
    projects = [dict(row) for row in db.execute('SELECT * FROM projects ORDER BY id')]
    runs = [dict(row) for row in db.execute('SELECT * FROM runs ORDER BY id')]
    events = [json.loads(row[0]) for row in db.execute('SELECT payload FROM events ORDER BY seq')]
assert len(projects) == len(runs) == 1
assert runs[0]['status'] == 'MISSING_INPUTS'
assert not table_before['candidates']['rows']
report_root = next(event['payload']['service_design_artifact_root'] for event in reversed(events)
                   if 'service_design_artifact_root' in event.get('payload', {}))


def blob(root):
    raw = zlib.decompress((cloned_store / 'blobs' / (root + '.json.z')).read_bytes())
    assert hashlib.sha256(raw).hexdigest() == root
    return json.loads(raw)


report = blob(report_root)
state = blob(projects[0]['state_root'])
assert report['checker_version'] == BUILD
assert report['summary']['source_count'] == 7 and report['summary']['network_count'] == 5463
original_ifcs = []
for source in state['sources']:
    path = Path(source['immutable_path']).resolve()
    assert path.is_file() and sha(path) == source['sha256']
    original_ifcs.append({'path': str(path), 'sha256': source['sha256'], 'bytes': path.stat().st_size})
native = json.loads((REGRESSION.parent / 'native-environment.json').read_text())
assert Path(native['interpreter']).resolve() == Path(sys.executable).resolve()
assert sha(sys.executable) == native['python_sha256']
for value in native['native_extensions'].values():
    assert sha(value['path']) == value['sha256']
with urllib.request.urlopen('http://127.0.0.1:8768/api/health', timeout=10) as response:
    main_health = json.load(response)
assert main_health['server_identity']['checker_version'].endswith('06aa865600b4ab2dc8f42f77b2cb5f82816dec99bbf8a1ff5f67673fb44c1949')
write(out / 'main8768-health-before.json', main_health)
manifest = {'schema': 'oma.validated-whole-services-backend/1', 'checker_version': BUILD,
            'source_files': expected, 'support_files': support, 'runtime': str(runtime), 'store': str(cloned_store),
            'host': '127.0.0.1', 'port': 8769, 'timeout_graceful_shutdown': 10, 'recover': False,
            'regression_result': str(REGRESSION), 'regression_status_at_preparation': result['status'],
            'closed_campaign_store': str(SOURCE_STORE), 'closed_campaign_file_inventory': source_before,
            'initial_database_table_inventory': table_before, 'blob_inventory': file_inventory(cloned_store / 'blobs'),
            'native_environment': native, 'projects': projects, 'runs': runs,
            'report_root': report_root, 'report_summary': report['summary'], 'original_ifcs': original_ifcs}
write(out / 'manifest.json', manifest)
shutil.copyfile(HERE / 'launch_backend.py', out / 'launch_backend.py')
write(out / 'prepared.json', {'status': 'READY_AWAITING_FULL_REGRESSION_PASS', 'directory': str(out),
                            'manifest_sha256': sha(out / 'manifest.json'), 'launcher_sha256': sha(out / 'launch_backend.py'),
                            'source_file_count': len(expected), 'support_file_count': len(support),
                            'store_exact_backup': True, 'original_store_unchanged': True})
write(HERE / 'prepared-location.json', {'directory': str(out)})
print(json.dumps({'status': 'READY_AWAITING_FULL_REGRESSION_PASS', 'directory': str(out),
                  'application_files': len(expected), 'blob_files': len(manifest['blob_inventory']),
                  'blob_bytes': sum(v['bytes'] for v in manifest['blob_inventory'].values()),
                  'table_counts': {k:v['rows'] for k,v in table_before.items()}}))
