"""Retain the closed seven-source job without changing its inputs or Store."""
from pathlib import Path
import gzip, hashlib, json, shutil, sqlite3, zlib

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'AGENTS.md').is_file())
STAGE = Path(__file__).resolve().parent
CAMPAIGN = STAGE / 'campaigns/1cbf8d8cc3c3485896f01b7a41a007fa'
OUT = ROOT / 'evidence/benchmarks/hospital-installed-services/1cbf8d8cc3c3485896f01b7a41a007fa-closed'
ARCHIVE = ROOT / 'evidence/benchmarks/hospital-generated-tree/full-federation-1e87dd6ad9af48b5962cd500603fdfdc'
REVIEW = ROOT / '.oma/development/installed-service-network-extraction/completed-reviews/943f4765b8fb488b8016ad3b0d47dcf0'

def sha(p):
    with Path(p).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')

def retain(source, relative, compress=True):
    raw = source.read_bytes()
    compressed = compress and len(raw) >= 500_000 and source.suffix in {'.json', '.log', '.xml'}
    target = OUT / (relative + ('.gz' if compressed else ''))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0) if compressed else raw)
    restored = gzip.decompress(target.read_bytes()) if compressed else target.read_bytes()
    assert restored == raw
    mapping.append({'original': str(source), 'retained': target.relative_to(OUT).as_posix(),
                    'encoding': 'gzip' if compressed else 'identity', 'original_bytes': len(raw),
                    'original_sha256': hashlib.sha256(raw).hexdigest(), 'retained_sha256': sha(target)})

assert not (OUT / 'handoff.json').exists(), 'Never rewrite a closed retained campaign'
OUT.mkdir(parents=True, exist_ok=True)
mapping = []
result = json.loads((CAMPAIGN / 'result.json').read_text())
declaration = json.loads((CAMPAIGN / 'predeclaration.json').read_text())
packet = json.loads((CAMPAIGN / 'whole-project-service-report.json').read_text())
assert result['status'] == 'WHOLE_PROJECT_SERVICE_JOB_COMPLETED_WITH_DESIGN_INPUTS_REQUIRED'
assert result['run']['status'] == 'MISSING_INPUTS' and result['execution']['returncode'] == 0
assert packet['summary']['network_count'] == 5463 and not packet['whole_building_optimized']
assert sha(CAMPAIGN / 'whole-project-service-report.json') == result['report_sha256']
store = Path(result['store'])
for p in sorted(CAMPAIGN.rglob('*')):
    if p.is_file() and 'networks' not in p.relative_to(CAMPAIGN).parts:
        retain(p, 'campaign/' + p.relative_to(CAMPAIGN).as_posix())

# Content-addressed graph blobs already contain all of the exported JSON facts.
# Preserve one exact encoded copy; verify reproducibility of the pretty exports.
artifact_index = {}
for p in sorted((store / 'blobs').glob('*.json.z')):
    root = p.name.removesuffix('.json.z')
    raw = zlib.decompress(p.read_bytes())
    assert hashlib.sha256(raw).hexdigest() == root
    archived = ARCHIVE / 'source-audits' / p.name
    if archived.is_file() and sha(archived) == sha(p):
        target = archived
    else:
        retain(p, 'store/blobs/' + p.name, compress=False)
        target = OUT / 'store/blobs' / p.name
    artifact_index[root] = {'path_from_repository_root': target.relative_to(ROOT).as_posix(),
        'encoding': 'zlib', 'encoded_sha256': sha(target), 'encoded_bytes': target.stat().st_size,
        'decoded_sha256': root, 'decoded_bytes': len(raw)}
    del raw
exports = []
for source in packet['sources']:
    root = source['network_inventory_root']
    raw = zlib.decompress((ROOT / artifact_index[root]['path_from_repository_root']).read_bytes())
    original = CAMPAIGN / 'networks' / (source['name'] + '.json')
    newline = '\r\n' if b'\r\n' in original.read_bytes() else '\n'
    regenerated = (json.dumps(json.loads(raw), indent=2, allow_nan=False) + '\n').replace('\n', newline).encode('utf-8')
    assert hashlib.sha256(regenerated).hexdigest() == sha(original)
    exports.append({'original': str(original), 'original_sha256': sha(original),
                    'artifact_root': root, 'line_ending': repr(newline),
                    'reconstruction': 'json.dumps(json.loads(zlib.decompress(blob)), indent=2, allow_nan=False) + LF; replace LF with line_ending; UTF-8'})
write(OUT / 'artifact-index.json', artifact_index)
write(OUT / 'graph-export-mapping.json', exports)

# Read-only SQLite online backup captures a consistent, independently readable DB.
source_db = sqlite3.connect((store / 'oma.sqlite3').as_uri() + '?mode=ro', uri=True)
target_db = sqlite3.connect(OUT / 'store/oma.sqlite3')
source_db.backup(target_db)
assert target_db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
tables = [r[0] for r in source_db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
for table in tables:
    assert table.replace('_', '').isalnum()
    assert source_db.execute(f'SELECT * FROM "{table}"').fetchall() == target_db.execute(f'SELECT * FROM "{table}"').fetchall()
source_db.close(); target_db.close()

source_index = []
for original, expected in declaration['source_files'].items():
    source = Path(original)
    assert sha(source) == expected
    archived = ARCHIVE / 'original-ifc' / (source.name + '.gz')
    with gzip.open(archived, 'rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == expected
    source_index.append({'name': source.name, 'original_sha256': expected,
        'original_bytes': source.stat().st_size, 'original_path': original,
        'archive': archived.relative_to(ROOT).as_posix(), 'archive_sha256': sha(archived), 'encoding': 'gzip'})
write(OUT / 'original-source-index.json', source_index)

frozen = Path(declaration['source_path'])
actual = {p.relative_to(frozen).as_posix(): sha(p) for p in frozen.rglob('*.py')}
assert actual == declaration['application_sources'] and len(actual) == 117
for relative in actual:
    retain(frozen / relative, 'source/' + relative, compress=False)
write(OUT / 'application-source-manifest.json', actual)
review_handoff = json.loads((REVIEW / 'handoff.json').read_text())
for relative, expected in review_handoff['retained_files'].items():
    assert sha(REVIEW / relative) == (expected['sha256'] if isinstance(expected, dict) else expected)
    retain(REVIEW / relative, 'independent-review/' + relative)
retain(REVIEW / 'handoff.json', 'independent-review/original-handoff.json')

recovery = STAGE / 'property-recovery/1c50d43d0c0f46478077a9abd8b39e55'
recovery_handoff = json.loads((recovery / 'handoff.json').read_text())
for relative, expected in recovery_handoff['files'].items():
    original = (ROOT / relative).resolve()
    assert original.is_relative_to(recovery.resolve()) and sha(original) == expected
    retain(original, 'equipment-label-recovery/' + original.relative_to(recovery.resolve()).as_posix())
retain(recovery / 'handoff.json', 'equipment-label-recovery/original-handoff.json')

for tag in ('probe-c9d0f02b6e404946b29b6b7c7c7ecc8f', 'fixed-d907d7f5beef447fb03f17bf1efe2462'):
    original = ROOT / '.oma/development/installed-service-network-extraction/peer' / tag
    for p in sorted(original.rglob('*')):
        if p.is_file():
            retain(p, 'historical-integrity-probes/' + tag + '/' + p.relative_to(original).as_posix())
retain(Path(__file__), 'retained-by.py', compress=False)
write(OUT / 'file-mapping.json', mapping)
summary = {key: sum(s['summary'][key] for s in packet['sources']) for key in
    ('source_product_count', 'source_port_count', 'source_explicit_connection_count', 'source_system_count',
     'service_product_count', 'network_count', 'portless_service_product_count', 'branched_network_count', 'cyclic_network_count')}
write(OUT / 'summary.json', {'status': result['status'], 'checker_version': packet['checker_version'],
    'seconds': result['seconds'], 'totals': summary, 'per_source': [
        {'name': s['name'], 'source_sha256': s['source_id'], 'discipline_label': s['discipline_label'],
         'summary': s['summary']} for s in packet['sources']],
    'independent_inventory_review': 'PASS', 'whole_building_optimized': False,
    'network_engineering_verdict': 'NOT_RUN', 'construction_approval': False,
    'contracts_supplied': 0, 'unresolved_networks': 5463,
    'original_inputs_and_project_state_unchanged': True,
    'scope': 'Whole-project installed-service accounting and original-source semantic reconciliation; not physical or code verification'})
files = {p.relative_to(OUT).as_posix(): sha(p) for p in OUT.rglob('*') if p.is_file()}
write(OUT / 'handoff.json', {'schema': 'oma.hospital-installed-services-retention/1',
    'status': 'CLOSED_SOURCE_BOUND_WHOLE_PROJECT_ACCOUNTING_WITH_DESIGN_INPUTS_REQUIRED',
    'checker_version': packet['checker_version'], 'campaign_id': CAMPAIGN.name,
    'run_id': result['run_id'], 'project_id': result['project']['id'], 'report_root': result['report_root'],
    'retained_files': files, 'retained_bytes': sum((OUT / name).stat().st_size for name in files),
    'external_dependencies': {'original_source_index': 'original-source-index.json', 'content_addressed_artifacts': 'artifact-index.json'},
    'full_regression': 'Retained separately; this handoff grants no test-suite or engineering PASS',
    'whole_building_optimized': False, 'construction_approval': False})
print(json.dumps({'status': 'RETAINED_AND_HASH_VERIFIED', 'handoff': str(OUT / 'handoff.json'),
                  'sha256': sha(OUT / 'handoff.json'), 'files': len(files), 'summary': summary}))
