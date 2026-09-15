"""Losslessly retain a closed failed native campaign without copying its Store/cache.

Usage: python retain_failed_campaign.py CAMPAIGN_DIRECTORY OUTPUT_DIRECTORY
Both directories are explicit; the output must not already exist.
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import re
import shutil
import sqlite3
import zlib

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def read(path):
    return json.loads(Path(path).read_bytes())

def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n', encoding='utf-8')

parser = argparse.ArgumentParser()
parser.add_argument('campaign', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
campaign, output = args.campaign.resolve(), args.output.resolve()
root = next(p for p in Path(__file__).resolve().parents if (p / 'AGENTS.md').is_file())
parent = campaign.parents[1]
declaration, result = read(campaign/'predeclaration.json'), read(campaign/'result.json')
store, app = Path(result['store']), Path(declaration['app_source'])
assert result['status'] == 'NO_CHECKED_INCUMBENT'
assert result['optimization_run']['status'] == 'NO_INCUMBENT_FOUND'
assert result['project_after'] == declaration['project_before']
assert result['app_unchanged'] and result['original_bytes_unchanged']
assert len(result['candidates']) == result['proposal_count'] == 2
assert all(c['status'] == 'REJECTED' and c['report_status'] == 'FAIL' for c in result['candidates'])
for key in ('generation_supervision', 'native_supervision'):
    assert result[key]['status'] == 'COMPLETED' and result[key]['returncode'] == 0
    assert result[key]['containment']['active_processes'] == 0
assert read(parent/'campaign-exit.json')['returncode'] == 0
assert {p.relative_to(app).as_posix(): sha(p) for p in app.rglob('*.py')} == declaration['app_sources']
assert sha(campaign/'executed.py') == declaration['script_sha256']
assert all(sha(Path(p)) == h for p, h in declaration['original_files'].items())

con = sqlite3.connect((store/'oma.sqlite3').resolve().as_uri() + '?mode=ro', uri=True)
con.row_factory = sqlite3.Row
project_id = result['project_id']
project = dict(con.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone())
assert project == result['project_after']
rows = {'projects': [project]}
for table in ('runs', 'candidates', 'revisions', 'events'):
    rows[table] = [dict(r) for r in con.execute('SELECT * FROM ' + table + ' WHERE project_id=?', (project_id,))]
rows['check_executions'] = [dict(r) for r in con.execute('SELECT e.* FROM check_executions e JOIN candidates c ON c.id=e.candidate_id WHERE c.project_id=?', (project_id,))]
candidate_ids = {c['id'] for c in result['candidates']}
assert {r['id'] for r in rows['candidates']} == candidate_ids
assert all(r['status'] == 'REJECTED' for r in rows['candidates'])
assert len(rows['check_executions']) == 2 and all(r['status'] == 'COMPLETED' for r in rows['check_executions'])
con.close()

summary_candidates = []
for candidate in result['candidates']:
    directory = campaign/'candidates'/candidate['id']
    material = read(directory/'materialization.json')
    report = read(directory/'report.json')
    semantics = json.loads(gzip.decompress((directory/'network-native-semantics.json.gz').read_bytes()))
    assert sha(directory/'actual.ifc') == candidate['actual_ifc_sha256'] == material['export_sha256']
    assert report['status'] == 'FAIL' and report['candidate_root'] == candidate['state_root']
    failed = [r for r in report['results'] if r['status'] != 'PASS']
    assert len(failed) == 1 and failed[0]['id'] == 'network-native-semantics'
    assert failed[0]['witness']['errors'] == ['Native volume disagrees with independent analytic component:tee-a']
    assert not any(r['id'] in ('network-native-clearance', 'network-hydraulic-service') for r in report['results'])
    summary_candidates.append({'id': candidate['id'], 'status': 'REJECTED', 'report_status': 'FAIL',
        'state_root': candidate['state_root'], 'report_root': candidate['report_root'],
        'actual_ifc_sha256': candidate['actual_ifc_sha256'], 'components': material['physical_component_count'],
        'ports': material['physical_port_count'], 'connections': len(material['explicit_internal_connections']),
        'failure': failed[0]['witness']['errors'], 'source_clearance_completed': False, 'service_completed': False})

output.mkdir(parents=True, exist_ok=False)
mapping = []

def copy(source, relative):
    source = source.resolve()
    old_hash, old_size = sha(source), source.stat().st_size
    compressed = source.suffix.lower() == '.ifc' or (source.suffix.lower() == '.json' and old_size > 8*1024**2)
    destination = output / (str(relative) + ('.gz' if compressed else ''))
    assert not destination.exists()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if compressed:
        with source.open('rb') as incoming, destination.open('wb') as target:
            with gzip.GzipFile(filename='', mode='wb', fileobj=target, mtime=0) as encoded:
                shutil.copyfileobj(incoming, encoded)
        with gzip.open(destination, 'rb') as decoded:
            assert hashlib.file_digest(decoded, 'sha256').hexdigest() == old_hash
    else:
        shutil.copyfile(source, destination)
        assert sha(destination) == old_hash
    assert sha(source) == old_hash and source.stat().st_size == old_size
    mapping.append({'original_path': str(source), 'path': destination.relative_to(output).as_posix(),
        'sha256': sha(destination), 'bytes': destination.stat().st_size, 'original_sha256': old_hash,
        'original_bytes': old_size, 'encoding': 'gzip' if compressed else 'identity'})

def tree(source, label):
    for item in sorted(source.rglob('*')):
        if item.is_file() and not any(p in ('__pycache__', '.pytest_cache') for p in item.parts):
            copy(item, (Path(label)/item.relative_to(source)).as_posix())

tree(campaign, 'campaign')
plan = read(parent/'campaign-plan.json')
import_result = Path(plan['import_result'])
import_data = read(import_result)
assert import_data['status'] == 'IMPORTED_CURRENT_SOURCE_INVENTORY'
assert import_data['input_bytes_unchanged'] and import_data['application_unchanged']
tree(import_result.parent, 'import')
for name in ('campaign.py', 'prepare_architecture.py', 'campaign-plan.json', 'cache-seed.json', 'campaign-exit.json',
             'campaign.stdout.log', 'campaign.stderr.log', 'import.stdout.log', 'import.stderr.log'):
    copy(parent/name, 'campaign-wrapper/'+name)
for row in rows['check_executions']:
    tree(store/'checks/candidate-executions'/row['execution_id'], 'candidate-executions/'+row['execution_id'])
tree(app, 'source')
copy(Path(__file__), 'scripts/retain_failed_campaign.py')
copy(Path(__file__).with_name('verify_failed_retention.py'), 'scripts/verify_failed_retention.py')
dump(output/'readonly-store-records.json', {'scope': 'Only isolated campaign project rows, read via SQLite mode=ro; no full Store copy.', 'tables': rows})

# Preserve exact immutable blob closure, without copying cache/mesh/other Store state.
pending = [declaration, result, rows, import_data]
roots = set()
def discover(value):
    if isinstance(value, dict):
        for child in value.values(): discover(child)
    elif isinstance(value, list):
        for child in value: discover(child)
    elif isinstance(value, str):
        if re.fullmatch('[0-9a-f]{64}', value) and (store/'blobs'/(value+'.json.z')).exists():
            if value not in roots:
                roots.add(value)
                pending.append(value)
        elif value.startswith(('{', '[')):
            try: discover(json.loads(value))
            except (ValueError, TypeError): pass
while pending:
    value = pending.pop()
    if isinstance(value, str):
        path = store/'blobs'/(value+'.json.z')
        raw = zlib.decompress(path.read_bytes())
        assert hashlib.sha256(raw).hexdigest() == value
        copy(path, 'immutable-blobs/'+path.name)
        discover(json.loads(raw))
    else:
        discover(value)

source_state = read(import_result.parent/'imported-state.json')
for source in source_state['sources']:
    original = Path(source['original_path'])
    assert sha(original) == source['sha256']
    copy(original, 'original-ifc/'+original.name)
    copy(Path(source['artifacts']['audit']), 'source-audits/'+Path(source['artifacts']['audit']).name)
    for name in ('license.txt', 'model_card.md'):
        copy(original.parent/name, 'source-provenance/'+name)

volume_probe = root/'.oma/development/hospital-outcome-audit/volume-probes/ca4ef44543834f22a3a5fe1ba5e41e56'
assert read(volume_probe/'result.json')['status'] == 'NATIVE_TEE_VOLUME_INTEGRATION_DIAGNOSTIC_COMPLETE'
tree(volume_probe, 'unchanged-brep-integration-diagnostic')
tree(Path(__file__).parent/'volume-review/bf1c82c8c5694652be34337afdc3406b', 'independent-integration-review')
dump(output/'summary.json', {'schema': 'oma.hospital-failed-campaign-retention/1', 'status': 'BOTH_CANDIDATES_REJECTED_NATIVE_TEE_VOLUME',
    'checker_version': declaration['checker_version'], 'python_sources': len(declaration['app_sources']),
    'elapsed_seconds': result['elapsed_seconds'], 'candidate_count': len(summary_candidates), 'candidates': summary_candidates,
    'generated_proposals': 2, 'generation_status': result['generation_status'], 'optimization_status': result['optimization_run']['status'],
    'accepted': False, 'checked_export': False, 'project_head_unchanged': True,
    'original_input_bytes_unchanged': True, 'physical_requirements_unchanged_from_prior_authored_mission': plan['mission_unchanged'],
    'scope': declaration['scope'], 'native_clearance_and_service_not_reached': True,
    'independent_diagnostic': 'All adaptive/default/GK and centered-copy volume evaluations agree within5e-14 m3 for each unchanged BRep; this does not support a quadrature fix.',
    'inventory_limits': 'Complete source remains declared but no clearance-pair denominator or service PASS is established by this failed campaign.',
    'native_cache_copied': False, 'full_store_copied': False, 'immutable_blob_count': len(roots)})
(output/'README.md').write_text('''# Hospital ARC: retained tee-volume failure

Frozen f716dd5c generated two finite alternatives from the unchanged hypothetical two-sink mission. Both native candidates were REJECTED, and optimization ended NO_INCUMBENT_FOUND after 108.125 seconds. No candidate was accepted and no checked export was produced. The isolated project remains at its original imported revision 1.

The alternatives contain four components/nine ports and twelve components/25 ports. Each report fails only the native semantic tee-a analytic-volume comparison. Its unchanged threshold is 1e-9 m3 for this tee. Clearance and hydraulic service were not reached; this record establishes no Hospital clearance or delivery PASS. The 14,409-obstacle source scope remains declared, not selectively reduced. The separate historical saved-candidate cold geometry probe has a different IFC and its own authority scope.

An independent diagnostic compares default, adaptive Gauss, Gauss-Kronrod, and translated-copy integration on exact old/new BReps. All methods preserve the old/new semantic dispositions and agree within5e-14 m3 per BRep. This evidence does not support changing quadrature or weakening the threshold. Any later geometry/conversion repair requires a distinct build and fresh checks.

This is architecture-only, using predeclared hypothetical terminal requirements. It does not resolve seven-discipline alignment or establish installed clinical service. The original source bytes and authored physical requirements remain unchanged. Materialization/semantics record canonical parsed original entity preservation, not raw serializer-line identity.

Both complete failed actual IFCs, all report/witness/semantic files, generator packets, declarations, closed execution records/logs, import receipt/state/source audit, exact114-file application snapshot and relevant immutable blob closure are retained. Gzip files are lossless and public-mapping.json binds their decoded originals. Native caches, meshes and the full live Store are omitted. closed-cache provenance remains in campaign-wrapper/cache-seed.json, but neither failed candidate reached the source-clearance phase.

Historical absolute provenance is preserved. Relocation requires the mapping and decompression; fresh import reconstructs omitted cache/display artifacts. `python scripts/verify_failed_retention.py <folder>` audits all indexed bytes and compressed originals without rerunning native geometry or altering outcomes. The original failed records remain unchanged.
''', encoding='utf-8')
dump(output/'public-mapping.json', {'schema': 'oma.lossless-public-mapping/1', 'files': mapping,
    'excluded': ['Native caches', 'Mesh caches', 'Full Store database', 'Python caches']})
files = {p.relative_to(output).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in sorted(output.rglob('*')) if p.is_file()}
dump(output/'index.json', {'files': files, 'file_count': len(files), 'bytes': sum(v['bytes'] for v in files.values()), 'self_exclusions': ['index.json', 'handoff.json', 'retention.json']})
assert all(sha(output/name) == row['sha256'] for name,row in files.items())
dump(output/'handoff.json', {'schema': 'oma.failed-campaign-public-handoff/1', 'status': 'EXACT_FAILED_OUTCOME_RETAINED',
    'index_sha256': sha(output/'index.json'), 'summary_sha256': sha(output/'summary.json'), 'indexed_files': len(files),
    'indexed_bytes': sum(v['bytes'] for v in files.values()), 'scope': 'Both actual candidates rejected; no clearance/service/acceptance/export success.', 'no_source_or_store_mutations': True})
retained = {p.relative_to(output).as_posix(): sha(p) for p in output.rglob('*') if p.is_file()}
dump(output/'retention.json', {'retained_files': retained, 'scope': 'All closed retained files; self-map excluded.'})
print(json.dumps({'output': str(output), 'handoff_sha256': sha(output/'handoff.json'), 'retention_sha256': sha(output/'retention.json'), 'files': len(retained)+1, 'indexed_bytes': sum(v['bytes'] for v in files.values())}))
