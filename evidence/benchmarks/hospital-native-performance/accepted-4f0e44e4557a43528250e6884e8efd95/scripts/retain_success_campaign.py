"""Retain a fully CLOSED generated-network campaign with fresh checked export.

Standard library only; no Store mutation, application import, CAD run or Git action.
Usage: python retain_success_campaign.py CAMPAIGN_DIRECTORY OUTPUT_DIRECTORY
"""
from pathlib import Path
from itertools import combinations
import argparse
import gzip
import hashlib
import json
import re
import shutil
import sqlite3
import zlib

observed_reads = {}

def sha(path):
    with Path(path).open('rb') as stream:
        value = hashlib.file_digest(stream, 'sha256').hexdigest()
    observed_reads.setdefault(str(Path(path).resolve()), value)
    return value

def read(path):
    raw = Path(path).read_bytes()
    observed_reads.setdefault(str(Path(path).resolve()), hashlib.sha256(raw).hexdigest())
    return json.loads(raw)

def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2)+'\n', encoding='utf-8')

parser = argparse.ArgumentParser()
parser.add_argument('campaign', type=Path)
parser.add_argument('output', type=Path)
parser.add_argument('--support-file', action='append', type=Path, default=[])
parser.add_argument('--audit-directory', type=Path)
parser.add_argument('--audit-result-sha256')
args = parser.parse_args()
campaign, output = args.campaign.resolve(), args.output.resolve()
parent = campaign.parents[1]
root = next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
result, declaration = read(campaign/'result.json'), read(campaign/'predeclaration.json')
assert result['status'] == 'ACCEPTED_AND_FRESH_EXPORT_CHECKED', 'Campaign is not a closed success'
assert result['original_bytes_unchanged'] is True and result['app_unchanged'] is True
exit_record = read(parent/'campaign-exit.json')
assert exit_record['returncode'] == 0
assert str(parent/'campaign.py') in exit_record['command']
for name in ('generation_supervision', 'native_supervision'):
    supervision = result[name]
    assert supervision['status'] == 'COMPLETED' and supervision['returncode'] == 0
    assert supervision['containment']['active_processes'] == 0
assert len(result['candidates']) == result['proposal_count'] == 2
chosen = result['selected_candidate_id']
exported = result['exported_candidate']['id']
assert chosen in {c['id'] for c in result['candidates']} and exported != chosen
assert result['accepted']['revision'] == declaration['project_before']['revision']+1 == result['project_after']['revision']
assert result['export']['status'] == 'CHECKED_LOCAL_SCOPE' and result['export']['round_trip'] == 'PASS'
manifest = read(campaign/'export-manifest.json')
assert manifest['candidate_id'] == chosen and manifest['checking']['exported_candidate_id'] == exported
assert len(manifest['checking']['release_bindings']) == 9 and all(v is True for v in manifest['checking']['release_bindings'].values())
assert manifest['status'] == 'CHECKED_LOCAL_SCOPE' and manifest['round_trip'] == 'PASS'
assert manifest['whole_building_release'] == 'NOT_CERTIFIED'
app, store = Path(declaration['app_source']), Path(result['store'])
def blob(root_id):
    path = store/'blobs'/(root_id+'.json.z')
    encoded = path.read_bytes()
    observed_reads.setdefault(str(path.resolve()), hashlib.sha256(encoded).hexdigest())
    raw = zlib.decompress(encoded)
    assert hashlib.sha256(raw).hexdigest() == root_id
    return json.loads(raw)

assert manifest == blob(result['export']['artifact_root'])
assert {p.relative_to(app).as_posix(): sha(p) for p in app.rglob('*.py')} == declaration['app_sources']
assert sha(campaign/'executed.py') == declaration['script_sha256']
assert all(sha(Path(p)) == h for p,h in declaration['original_files'].items())
if args.audit_directory:
    assert args.audit_result_sha256 and sha(args.audit_directory/'result.json') == args.audit_result_sha256
    audit_result = read(args.audit_directory/'result.json')
    audit_inputs = read(args.audit_directory/'inputs.json')
    assert audit_result['status'] == 'BOTH_FIXED_ALTERNATIVES_AND_SELECTED_FRESH_EXPORT_AUDITED'
    assert audit_result['files_unchanged'] and audit_result['app_unchanged'] and audit_result['store_project_unchanged']
    assert audit_inputs['app'] == declaration['app_sources']
    assert audit_inputs['files'][str(campaign/'result.json')] == sha(campaign/'result.json')

def snapshot():
    db = sqlite3.connect((store/'oma.sqlite3').resolve().as_uri()+'?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    db.execute('BEGIN')
    project_id = result['project_id']
    tables = {'projects': [dict(db.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone())]}
    for table in ('runs', 'candidates', 'revisions', 'events'):
        tables[table] = [dict(r) for r in db.execute('SELECT * FROM '+table+' WHERE project_id=? ORDER BY rowid', (project_id,))]
    tables['check_executions'] = [dict(r) for r in db.execute('SELECT e.* FROM check_executions e JOIN candidates c ON c.id=e.candidate_id WHERE c.project_id=? ORDER BY e.rowid', (project_id,))]
    db.close()
    return tables

rows = snapshot()
assert rows['projects'][0] == result['project_after']
candidate_summaries = result['candidates']+[result['exported_candidate']]
candidate_ids = {c['id'] for c in candidate_summaries}
assert {r['id'] for r in rows['candidates']} == candidate_ids
assert len(rows['check_executions']) == len(candidate_ids)
assert all(r['status'] == 'COMPLETED' for r in rows['check_executions'])
for execution in rows['check_executions']:
    raw = zlib.decompress((store/'blobs'/(execution['evidence_root']+'.json.z')).read_bytes())
    assert hashlib.sha256(raw).hexdigest() == execution['evidence_root']
    evidence = json.loads(raw)
    receipt, binding = evidence['observed_receipt'], json.loads(execution['binding'])
    assert evidence['status'] == evidence['supervision']['status'] == 'COMPLETED'
    assert evidence['supervision']['returncode'] == 0 and evidence['supervision']['containment']['active_processes'] == 0
    assert receipt['execution_id'] == execution['execution_id'] and receipt['candidate_id'] == execution['candidate_id']
    assert receipt['candidate_root'] == binding['candidate_root']
    assert receipt['checker_version'] == declaration['checker_version'] == binding['checker_version']
    assert receipt['report_root'] == execution['report_root'] == evidence['report_root']
selected_row = next(c for c in rows['candidates'] if c['id'] == chosen)
assert selected_row['state_root'] == result['project_after']['state_root'] == manifest['state_root']
assert all(c['status'] in ('CHECKED', 'REJECTED', 'UNKNOWN') for c in rows['candidates'])

def compressed_json(path):
    encoded = path.read_bytes()
    observed_reads.setdefault(str(path.resolve()), hashlib.sha256(encoded).hexdigest())
    return json.loads(gzip.decompress(encoded))

observations = []
for item in candidate_summaries:
    directory = campaign/'candidates'/item['id']
    material, report = read(directory/'materialization.json'), read(directory/'report.json')
    current_row = next(c for c in rows['candidates'] if c['id'] == item['id'])
    assert all(current_row[k] == item[k] for k in ('status','state_root','report_root'))
    assert report == blob(item['report_root'])
    state = compressed_json(directory/'state.json.gz')
    assert state == blob(item['state_root'])
    assert len(state['physical_networks']) == 1
    assert material == blob(state['physical_networks'][0]['geometry_artifact'])
    assert sha(directory/'actual.ifc') == material['export_sha256'] == item['actual_ifc_sha256']
    assert report['candidate_root'] == item['state_root'] and report['checker_version'] == declaration['checker_version']
    checks = {c['id']:c for c in report['results']}
    assert len(checks) == len(report['results'])
    observation = {'id':item['id'], 'status':item['status'], 'report_status':report['status'],
        'state_root':item['state_root'], 'report_root':item['report_root'], 'ifc_sha256':material['export_sha256'],
        'components':material['physical_component_count'], 'ports':material['physical_port_count'],
        'checks':{k:v['status'] for k,v in checks.items()}}
    if item['id'] in (chosen, exported):
        assert item['status'] == 'CHECKED' and report['status'] == 'PASS'
    if item['status'] == 'CHECKED':
        assert report['status'] == 'PASS'
        assert all(c['status'] == 'PASS' for c in report['results'])
        sem = compressed_json(directory/'network-native-semantics.json.gz')
        cad = compressed_json(directory/'network-all-source-clearance.json.gz')
        assert sem == blob(checks['network-native-semantics']['witness']['artifact'])
        assert cad == blob(checks['network-all-source-clearance']['witness']['artifact'])
        guids = [p['ifc_guid'] for p in sem['parts']]
        n = len(guids)
        assert n == len(set(guids)) == cad['route_count']
        assert set(cad['route_guids']) == set(guids) and len(cad['route_guids']) == n
        assert len(cad['self_pair_results']) == n*(n-1)//2
        assert {frozenset(p['participant_guids']) for p in cad['self_pair_results']} == {frozenset(p) for p in combinations(guids,2)}
        assert cad['pairs_accounted'] == n*cad['obstacle_count']
        assert cad['status'] == cad['coordination_status'] == cad['self_interference_status'] == 'PASS'
        assert not cad['missing_geometry'] and not cad['failed_pairs'] and not cad['unknown_pairs'] and not cad['blocked_pairs']
        assert checks['network-demand-conditioned-service']['status'] == 'PASS'
        assert compressed_json(directory/'fixed-flow-service.json.gz') == checks['network-demand-conditioned-service']['witness']['calculation']
        assert sem['physical_ports'] == len(sem['ports'])
        assert all(p['status'] == 'PASS' for p in sem['ports'])
        assert any(e['candidate_id'] == item['id'] and e['report_root'] == item['report_root'] for e in rows['check_executions'])
        observation.update(obstacles=cad['obstacle_count'], source_pairs=cad['pairs_accounted'], self_pairs=len(cad['self_pair_results']),
            source_preservation=cad['coordinate_status'], service_status=checks['network-demand-conditioned-service']['status'])
    observations.append(observation)
for row in manifest['files']:
    assert sha(Path(row['path'])) == row['sha256']

# Only after all completion/admission bindings above may public retention start.
output.mkdir(parents=True, exist_ok=False)
mapping, content_destinations = [], {}

def copy(source, relative, deduplicate=False):
    source = source.resolve()
    source_hash, size = sha(source), source.stat().st_size
    assert source_hash == observed_reads[str(source)], 'Input changed after earlier validation read'
    compressed = source.suffix.lower() == '.ifc' or (source.suffix.lower() == '.json' and size > 8*1024**2)
    target_name = str(relative)+('.gz' if compressed else '')
    if deduplicate and source_hash in content_destinations:
        destination = output/content_destinations[source_hash]
    else:
        destination = output/target_name
        assert not destination.exists()
        destination.parent.mkdir(parents=True, exist_ok=True)
        if compressed:
            with source.open('rb') as incoming, destination.open('wb') as target:
                with gzip.GzipFile(filename='', mode='wb', fileobj=target, mtime=0) as encoded:
                    shutil.copyfileobj(incoming, encoded)
            with gzip.open(destination, 'rb') as decoded:
                assert hashlib.file_digest(decoded, 'sha256').hexdigest() == source_hash
        else:
            shutil.copyfile(source, destination)
            assert sha(destination) == source_hash
        content_destinations[source_hash] = destination.relative_to(output).as_posix()
    assert sha(source) == source_hash and source.stat().st_size == size
    mapping.append({'original_path':str(source), 'path':destination.relative_to(output).as_posix(), 'sha256':sha(destination),
        'bytes':destination.stat().st_size, 'original_sha256':source_hash, 'original_bytes':size,
        'encoding':'gzip' if destination.name.endswith('.gz') and not source.name.endswith('.gz') else 'identity',
        'requested_public_path':target_name, 'deduplicated':destination.relative_to(output).as_posix() != target_name})

def tree(source, label, deduplicate=False):
    for item in sorted(source.rglob('*')):
        if item.is_file() and not any(p in ('__pycache__', '.pytest_cache', 'cad-cache') for p in item.parts):
            copy(item, (Path(label)/item.relative_to(source)).as_posix(), deduplicate=deduplicate)

tree(campaign, 'campaign')
plan = read(parent/'campaign-plan.json')
import_result = Path(plan['import_result'])
import_data = read(import_result)
assert import_data['status'] == 'IMPORTED_CURRENT_SOURCE_INVENTORY'
assert import_data['input_bytes_unchanged'] and import_data['application_unchanged']
tree(import_result.parent, 'import')
for name in ('campaign.py', 'prepare_architecture.py', 'campaign-plan.json', 'campaign-exit.json', 'campaign.stdout.log',
             'campaign.stderr.log', 'import.stdout.log', 'import.stderr.log', 'source.json', 'cache-seed.json'):
    if (parent/name).is_file(): copy(parent/name, 'campaign-wrapper/'+name)
for row in rows['check_executions']:
    tree(store/'checks/candidate-executions'/row['execution_id'], 'candidate-executions/'+row['execution_id'])
export_directory = Path(result['export']['directory']).resolve()
assert export_directory.is_relative_to(store.resolve()/'exports')
tree(export_directory, 'checked-export', deduplicate=True)
tree(app, 'source')
copy(Path(__file__), 'scripts/retain_success_campaign.py')
copy(Path(__file__).with_name('verify_failed_retention.py'), 'scripts/verify_retention.py')
for path in args.support_file:
    copy(path, 'support-scripts/'+path.name)
if args.audit_directory:
    tree(args.audit_directory, 'independent-outcome-audit')
    for original_path, expected in audit_inputs['files'].items():
        path = Path(original_path)
        assert sha(path) == expected
        copy(path, 'independent-audit-inputs/'+expected+'-'+path.name, deduplicate=True)
dump(output/'readonly-store-records.json', {'scope':'Closed isolated campaign project only, mode=ro snapshot; no Store database copied.', 'tables':rows})

pending, roots = [declaration, result, rows, import_data, manifest], set()
def discover(value):
    if isinstance(value, dict):
        for child in value.values(): discover(child)
    elif isinstance(value, list):
        for child in value: discover(child)
    elif isinstance(value, str):
        if re.fullmatch('[0-9a-f]{64}', value) and (store/'blobs'/(value+'.json.z')).is_file():
            if value not in roots: roots.add(value); pending.append(value)
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
    else: discover(value)

state = read(import_result.parent/'imported-state.json')
for source in state['sources']:
    original = Path(source['original_path'])
    assert sha(original) == source['sha256']
    copy(original, 'original-ifc/'+original.name)
    audit = Path(source['artifacts']['audit'])
    copy(audit, 'source-audits/'+audit.name)
    for name in ('license.txt', 'model_card.md'): copy(original.parent/name, 'source-provenance/'+name)

assert snapshot() == rows, 'Closed campaign project changed during retention'
assert all(sha(Path(p)) == h for p,h in declaration['original_files'].items())
assert {p.relative_to(app).as_posix():sha(p) for p in app.rglob('*.py')} == declaration['app_sources']
dump(output/'summary.json', {'schema':'oma.hospital-generated-success-retention/1', 'status':'ACCEPTED_AND_FRESH_EXPORT_CHECKED',
    'checker_version':declaration['checker_version'], 'python_sources':len(declaration['app_sources']), 'elapsed_seconds':result['elapsed_seconds'],
    'candidates':observations, 'selected_candidate_id':chosen, 'fresh_export_candidate_id':exported,
    'import_revision':declaration['project_before']['revision'], 'accepted_revision':result['accepted']['revision'],
    'fresh_export_status':manifest['status'], 'round_trip':manifest['round_trip'], 'release_bindings':manifest['checking']['release_bindings'],
    'original_input_bytes_unchanged':True, 'physical_requirements_unchanged':plan['mission_unchanged'],
    'scope':declaration['scope'], 'whole_building_release':manifest['whole_building_release'],
    'immutable_blobs':len(roots), 'no_cache_or_full_store_copied':True,
    'preservation_scope':'Canonical parsed original entity semantics plus original input byte hashes, not raw serializer spelling.',
    'limitations':['Explicit hypothetical prescribed flows, not discovered installed terminal capacities or clinical adequacy.',
        'Architecture-only; seven-discipline alignment remains unresolved.', 'Two finite generated alternatives; no unrestricted global routing optimum.']})
(output/'README.md').write_text('''# Hospital ARC: accepted generated network and fresh checked export

This closed campaign generated two finite alternatives from the unchanged, explicitly hypothetical two-sink request. Normal native selection chose the recorded candidate; the isolated project advanced from revision1 to revision2. The actual exported IFC copy received a separate managed native report with all nine release bindings. Exact candidate IDs, source/self/port denominators and timings are in summary.json and the unchanged campaign result.

Both alternatives remain retained, including any rejection or UNKNOWN. The selected and fresh-export reports, complete physical IFCs, native semantic/clearance/service artifacts, execution receipts, generator proofs, import/source snapshots, original ARC/license and all114 application files are preserved. No prior failure was rewritten. The previous f716 tee-volume failures and the historical timeout/cold geometry-only probe remain distinct results.

The two fixed prescribed deliveries and loss/ideal-bore assumptions are hypothetical requirements. This success does not establish installed hospital terminal capacity, clinical adequacy, seven-discipline coordination or unrestricted global optimality. Whole-building release remains NOT_CERTIFIED. Canonical parsed original entity preservation is distinct from raw STEP serializer spelling; original IFC bytes themselves remain unchanged.

public-mapping.json retains original absolute provenance and maps lossless gzip originals. A byte-identical exported IFC may share the same retained content as the fresh-export candidate; the mapping records every original export path. Cache/mesh artifacts and the full Store are omitted. Immutable blobs and mode=ro project rows preserve acceptance and managed-check bindings for independent audit. Historical scripts need path relocation; reimport can reconstruct omitted caches.

Run `python scripts/verify_retention.py <this-folder>` for a standard-library hash and decompression audit. It performs no CAD run and grants no new result authority.
''', encoding='utf-8')
dump(output/'public-mapping.json', {'schema':'oma.lossless-public-mapping/1', 'files':mapping,
    'excluded':['Native/mesh caches','Full Store database','Python caches']})
files = {p.relative_to(output).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(output.rglob('*')) if p.is_file()}
dump(output/'index.json', {'files':files, 'file_count':len(files), 'bytes':sum(v['bytes'] for v in files.values()), 'self_exclusions':['index.json','handoff.json','retention.json']})
assert all(sha(output/name) == row['sha256'] for name,row in files.items())
dump(output/'handoff.json', {'schema':'oma.success-campaign-public-handoff/1', 'status':'EXACT_SUCCESS_OUTCOME_RETAINED',
    'index_sha256':sha(output/'index.json'), 'summary_sha256':sha(output/'summary.json'), 'indexed_files':len(files),
    'indexed_bytes':sum(v['bytes'] for v in files.values()), 'scope':'Architecture-only hypothetical generated network accepted and fresh IFC copy checked.',
    'no_source_or_store_mutations':True})
retained = {p.relative_to(output).as_posix():sha(p) for p in output.rglob('*') if p.is_file()}
dump(output/'retention.json', {'retained_files':retained, 'scope':'All closed retained files; self-map excluded.'})
print(json.dumps({'output':str(output), 'handoff_sha256':sha(output/'handoff.json'), 'retention_sha256':sha(output/'retention.json'),
    'files':len(retained)+1, 'indexed_bytes':sum(v['bytes'] for v in files.values())}))
