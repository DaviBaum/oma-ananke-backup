"""Read-only HTTP and state verification for the isolated launched backend."""
from pathlib import Path
import hashlib
import json
import sqlite3
import urllib.request
import sys

HERE = Path(__file__).resolve().parent
out = Path(sys.argv[1]).resolve()
assert out.parent == HERE
manifest = json.loads((out / 'manifest.json').read_text())


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(name, data):
    (out / name).write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def get(path, port=8769):
    with urllib.request.urlopen(f'http://127.0.0.1:{port}' + path, timeout=30) as response:
        body = response.read()
        return body, {'status': response.status, 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest(),
                      'content_type': response.headers.get('Content-Type')}


def table_inventory(path):
    db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    try:
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        result = {}
        for name, in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
            quoted = '"' + name.replace('"', '""') + '"'
            rows = sorted(json.dumps(row, ensure_ascii=False, separators=(',', ':'))
                          for row in db.execute('SELECT * FROM ' + quoted))
            result[name] = {'rows': len(rows), 'sha256': hashlib.sha256(('\n'.join(rows) + '\n').encode()).hexdigest()}
        return result
    finally:
        db.close()


before = table_inventory(Path(manifest['store']) / 'oma.sqlite3')
assert before == manifest['initial_database_table_inventory']
health = json.loads(get('/api/health')[0])
identity = health['server_identity']
assert health['status'] == 'ok'
assert identity['checker_version'] == identity['current_disk_checker_version'] == identity['declared_checker_version'] == manifest['checker_version']
assert identity['source_changed'] is False and identity['startup_environment_matches'] is True and identity['identity_error'] is None
assert Path(identity['data_directory']).resolve() == Path(manifest['store']).resolve()
assert Path(identity['python_executable']).resolve() == Path(manifest['native_environment']['interpreter']).resolve()
write('health8769.json', health)
openapi = json.loads(get('/openapi.json')[0])
assert 'design_services' in openapi['components']['schemas']['RunRequest']['properties']['operation']['enum']
write('openapi.json', openapi)
projects = json.loads(get('/api/projects')[0])
assert projects == manifest['projects']
write('projects-api.json', projects)
run_id = manifest['runs'][0]['id']
run = json.loads(get('/api/runs/' + run_id)[0])
assert run['operation'] == 'design_services' and run['status'] == 'MISSING_INPUTS'
assert run['base_root'] == projects[0]['state_root'] and run['base_revision'] == 0
write('run-api.json', run)
report = json.loads(get('/api/artifacts/' + manifest['report_root'])[0])
canonical = json.dumps(report, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()
assert hashlib.sha256(canonical).hexdigest() == manifest['report_root']
assert report['summary'] == manifest['report_summary']
assert report['summary']['source_count'] == 7 and report['summary']['network_count'] == 5463
assert report['summary']['network_status_counts'] == {'MISSING_DESIGN_CONTRACT': 5463}
assert report['whole_building_optimized'] is False and report['project_state_changed'] is False
assert report['construction_approval'] is False and report['native_checks_run'] is False
write('report-api.json', report)
ui = {}
for relative, expected in manifest['support_files'].items():
    if relative.startswith('ui/dist/'):
        suffix = relative[len('ui/dist/'):]
        url = '/' if suffix == 'index.html' else '/' + suffix
        body, metadata = get(url)
        assert metadata['sha256'] == expected
        ui[url] = metadata
write('ui-http-verification.json', ui)
main = json.loads(get('/api/health', port=8768)[0])
original_main = json.loads((out / 'main8768-health-before.json').read_text())
assert main['server_identity'] == original_main['server_identity']
write('main8768-health-after.json', main)
after = table_inventory(Path(manifest['store']) / 'oma.sqlite3')
assert after == before
source_store = Path(manifest['closed_campaign_store'])
actual_closed = {p.relative_to(source_store).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size}
                 for p in sorted(source_store.rglob('*')) if p.is_file()}
assert actual_closed == manifest['closed_campaign_file_inventory']
actual_blobs = {p.relative_to(Path(manifest['store']) / 'blobs').as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size}
                for p in sorted((Path(manifest['store']) / 'blobs').rglob('*')) if p.is_file()}
assert actual_blobs == manifest['blob_inventory']
assert all(sha(item['path']) == item['sha256'] for item in manifest['original_ifcs'])
source = Path(manifest['runtime']) / 'src'
assert {p.relative_to(source).as_posix(): sha(p) for p in source.rglob('*.py')} == manifest['source_files']
receipt = json.loads((out / 'startup-receipt.json').read_text())
write('handoff.json', {'schema': 'oma.validated-whole-services-live-backend-handoff/1',
    'status': 'LIVE_VALIDATED_READ_ONLY_VERIFICATION_PASS', 'url': 'http://127.0.0.1:8769',
    'pid': receipt['pid'], 'checker_version': manifest['checker_version'],
    'runtime': manifest['runtime'], 'cloned_store': manifest['store'],
    'project_id': projects[0]['id'], 'project_name': projects[0]['name'], 'revision': 0,
    'state_root': projects[0]['state_root'], 'run_id': run_id, 'report_root': manifest['report_root'],
    'report_summary': manifest['report_summary'], 'operation_design_services_in_openapi': True,
    'exact_application_files': 117, 'exact_ui_assets_served': 6,
    'recover': False, 'timeout_graceful_shutdown_seconds': 10,
    'cloned_store_tables_unchanged': True, 'cloned_blobs_unchanged': True,
    'closed_campaign_store_unchanged': True, 'original_ifcs_unchanged': True,
    'main8768_identity_unchanged': True,
    'regression_result': manifest['regression_result'], 'regression_result_sha256': sha(manifest['regression_result']),
    'launcher_sha256': sha(out / 'launch_backend.py'), 'manifest_sha256': sha(out / 'manifest.json'),
    'database_table_inventory': after,
    'scope': 'Independent local backend on cloned campaign Store. Existing report remains MISSING_INPUTS for all 5463 installed components; no new design job, IFC edit, network approval or whole-building optimum was issued.'})
write('support-index.json', {p.name: {'sha256': sha(p), 'bytes': p.stat().st_size}
                           for p in out.iterdir() if p.is_file() and p.name not in ('support-index.json', 'server.stdout.log', 'server.stderr.log')})
print(json.dumps({'status': 'LIVE_VALIDATED_READ_ONLY_VERIFICATION_PASS', 'handoff': str(out / 'handoff.json'),
                  'sha256': sha(out / 'handoff.json'), 'pid': receipt['pid']}))
