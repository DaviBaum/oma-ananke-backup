"""Read-only declaration of the two saved export cases before package creation."""
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
from native_package_evidence import ReadOnlyBlobs
from native_prepare import json_write, sha

source = '1abe9a077844a184ec17e1c8a0a390aa4bf33d05dd302a6eefff7d770a0ff719'
cases = {'joint_fitting_budget': (ROOT / '.oma', '4e4ae2ec320c4e038f09cae18bd386bf',
    'c9bb6d41e8fd3ae6adea5dc3fd132b23e606d89e0c6988f695a3f7dd12ac1a5d'),
    'pressure_network': (ROOT / '.oma/development/two-sink-pressure/bench-stores/b44b3123cdb641709b2aa32ae5bd526c',
    'cde5e507fca2488d9a957364f6d5a763', 'c116e3cf909e97719a613888043ca2b214aba538575e17f79dd3639bb5a12e58')}
roles = {}
for role, (directory, candidate_id, expected_export) in cases.items():
    store = ReadOnlyBlobs(directory)
    with sqlite3.connect((directory / 'oma.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        candidate = dict(db.execute('SELECT * FROM candidates WHERE id=?', (candidate_id,)).fetchone())
    assert candidate['status'] == 'CHECKED'
    payload = json.loads(candidate['payload'])
    state, report = store.get(candidate['state_root']), store.get(candidate['report_root'])
    assert report['status'] == 'PASS' and report['candidate_root'] == candidate['state_root']
    physical = state['routes'] if role == 'joint_fitting_budget' else state['physical_networks']
    materials = [store.get(p['geometry_artifact']) for p in physical]
    assert {m['export_sha256'] for m in materials} == {expected_export}
    assert all(sha(store.resolve_path(m['export_path'])) == expected_export for m in materials)
    assert all(sha(store.resolve_path(s['immutable_path'])) == s['sha256'] for s in state['sources'])
    roles[role] = {'candidate_id': candidate_id, 'candidate_root': candidate['state_root'],
        'prior_report_root': candidate['report_root'], 'prior_checker_version': report['checker_version'],
        'physical_kind': payload['kind'], 'original_store': str(directory.resolve()),
        'expected_export_sha256': expected_export}
declaration = {'schema': 'oma.portable-real-model-inputs/1', 'source_checkpoint': source, 'roles': roles,
    'scope': 'Two separately declared immutable exported IFC cases, original Stores read-only, prior reports retained under their genuine distinct checker identities. No geometry regeneration or original mission alteration.'}
destination = Path(__file__).parent / (source + '.json')
assert not destination.exists()
json_write(destination, declaration)
print(json.dumps({'declaration': str(destination), 'sha256': sha(destination), 'roles': roles}), flush=True)
