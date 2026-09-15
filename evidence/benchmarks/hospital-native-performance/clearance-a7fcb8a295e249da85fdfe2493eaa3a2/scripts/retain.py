"""Retain completed, immutable geometry-only evidence; no CAD or Store writes."""
from pathlib import Path
import gzip
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
STAGE = Path(__file__).resolve().parent
PROBE = STAGE / 'full-probes/a7fcb8a295e249da85fdfe2493eaa3a2'
OUT = ROOT / 'evidence/benchmarks/hospital-native-performance/clearance-a7fcb8a295e249da85fdfe2493eaa3a2'
PEER = ROOT / '.oma/development/hospital-alignment-service-audit/acceleration-review'
OLD = ROOT / 'evidence/benchmarks/hospital-generated-tree/architecture-d3e1be8f981146fcadede8107addadbe'

def digest(data):
    return hashlib.sha256(data).hexdigest()

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def read(path):
    return json.loads(path.read_bytes())

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')

result = read(PROBE / 'result.json')
child = read(PROBE / 'child-result.json')
decl = read(PROBE / 'predeclaration.json')
assert result['status'] == 'FULL_CAD_PROBE_COMPLETE'
assert result['supervision']['status'] == 'COMPLETED'
assert result['supervision']['returncode'] == 0
assert result['supervision']['containment']['active_processes'] == 0
assert result['child'] == child
assert child['cad_status'] == child['coordination_status'] == 'PASS'
assert (child['route_count'], child['obstacle_count'], child['pairs_accounted'], child['self_pairs']) == (4, 14409, 57636, 6)
assert all(child[name] == 0 for name in ('failed_pairs', 'unknown_pairs', 'blocked_pairs', 'missing_geometry'))
assert sha(PROBE / 'cad-report.json') == child['cad_report_sha256']
assert sha(PROBE / 'actual.ifc') == child['export_sha256'] == decl['export_sha256']
assert sha(Path(decl['source'])) == child['source_sha256'] == decl['source_sha256']
assert {p.relative_to(STAGE / 'combined-src').as_posix(): sha(p) for p in (STAGE / 'combined-src').rglob('*.py')} == decl['app_files']
cache = child['performance']['source_cache'][0]
assert cache['selected_physical_count'] == len(cache['physical_inventory']['physical_step_ids']) == 14641
assert len(cache['accounted_assembly_step_ids']) == 232
assert cache['lazy_support']['enclosure_only_count'] == 13151
assert cache['lazy_support']['native_refinement_count'] == 1258
assert cache['lazy_support']['all_source_products_accounted'] is True
assert sha(PEER / 'result.json') == 'e61c5cf3f4d49e6d025ccdb4149baca2be8658ae34c4a0a1edb6b39c6caf86de'
for run, expected in [('42911be3cae240f9be6e071603a5901d', (59, 0, 0, 0)), ('79506467013a42a6b29bf35e34d4b010', (59, 1, 0, 0))]:
    directory = STAGE / 'validation' / run
    test_decl = read(directory / 'predeclaration.json')
    assert all(sha(directory / name) == value for name, value in test_decl['files'].items())
    xml = ET.parse(directory / 'tests.xml')
    counts = tuple(len(xml.findall('.//' + name)) for name in ('testcase', 'failure', 'error', 'skipped'))
    assert counts == expected

OUT.mkdir(parents=True, exist_ok=False)
mapping = {}
compressed = {}

def copy(source, destination):
    target = OUT / destination
    assert not target.exists()
    raw = source.read_bytes()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    assert sha(source) == sha(target) == digest(raw)
    mapping[destination] = {'original_path': str(source.resolve()), 'sha256': digest(raw), 'bytes': len(raw)}

def tree(source, destination, excluded=()):
    for item in sorted(source.rglob('*')):
        relative = item.relative_to(source)
        if item.is_file() and not any(part in excluded or part in ('__pycache__', '.pytest_cache') for part in relative.parts):
            copy(item, (Path(destination) / relative).as_posix())

for directory in ('base-src', 'combined-src', 'tests'):
    tree(STAGE / directory, directory)
for name in ('prepare.py', 'prepare_combined.py', 'source-preparation.json', 'combined-source.json', 'profile_enclosure.py', 'run_profile.py', 'run_tests.py', 'full_probe.py', 'run_full_probe.py'):
    copy(STAGE / name, 'scripts/' + name)
copy(Path(__file__), 'scripts/retain.py')
tree(STAGE / 'profiles', 'profiles')
tree(STAGE / 'validation', 'validation', excluded=('temporary',))
tree(PEER, 'independent-peer')
tree(PROBE, 'cold-probe', excluded=('cache', 'actual.ifc', 'cad-report.json'))

old_gzip = OLD / 'campaign/candidates/85453f9ad960487297bf0231cd549a79/actual.ifc.gz'
assert sha(old_gzip) == decl['original_gzip_sha256']
assert digest(gzip.decompress(old_gzip.read_bytes())) == decl['export_sha256']
copy(old_gzip, 'cold-probe/actual.ifc.gz')
compressed['cold-probe/actual.ifc.gz'] = {'uncompressed_sha256': decl['export_sha256'], 'uncompressed_bytes': (PROBE / 'actual.ifc').stat().st_size, 'original_gzip_bytes_preserved': True}
raw = (PROBE / 'cad-report.json').read_bytes()
packed = gzip.compress(raw, compresslevel=6, mtime=0)
assert gzip.decompress(packed) == raw
(OUT / 'cold-probe/cad-report.json.gz').write_bytes(packed)
compressed['cold-probe/cad-report.json.gz'] = {'uncompressed_sha256': digest(raw), 'uncompressed_bytes': len(raw), 'gzip_sha256': digest(packed)}
copy(OLD / 'campaign/predeclaration.json', 'historical-authored-query.json')
copy(ROOT / '.oma/development/hospital-clearance-20260915/campaign-v1/cache-seed.json', 'closed-cache-seed.json')

write(OUT / 'compression.json', compressed)
write(OUT / 'path-mapping.json', {'schema': 'oma.evidence-source-mapping/1', 'files': mapping, 'compressed_files': compressed,
    'excluded': ['Native cache BReps (closed cache-seed receipt retained)', 'live or copied Store databases', 'pytest temporary fixtures and caches', 'duplicate full original Hospital source IFC'],
    'source_input': {'path': decl['source'], 'sha256': decl['source_sha256']},
    'replay': 'Historical absolute paths and commands are retained verbatim. For relocation, map these roots to the copied folders, decompress both .gz inputs, and use the exact frozen combined-src with matching native dependencies. No rerun is performed by this retainer.'})
write(OUT / 'summary.json', {
    'schema': 'oma.hospital-cold-clearance-evidence/1', 'status': 'GEOMETRY_CLEARANCE_PASS',
    'checker_version': decl['checker_version'], 'frozen_python_files': len(decl['app_files']),
    'cad_seconds': child['seconds'], 'supervised_seconds': result['supervision']['elapsed_seconds'],
    'peak_tree_rss_bytes': result['supervision']['peak_tree_rss_bytes'],
    'physical_products': 14641, 'grounded_assemblies': 232, 'obstacles': 14409, 'route_parts': 4,
    'source_pairs': 57636, 'self_pairs': 6, 'missing_geometry': 0, 'unknown_pairs': 0, 'failed_pairs': 0,
    'checked_enclosure_only_obstacles': 13151, 'native_refined_obstacles': 1258,
    'source_sha256': decl['source_sha256'], 'export_sha256': decl['export_sha256'],
    'preservation': 'All original canonical parsed STEP entity records rechecked; original input bytes unchanged.',
    'focused_tests': {'final': '59 PASS', 'initial': '58 PASS, 1 failed test expectation; original XML/logs preserved'},
    'independent_peer': '768 affine corner memberships, 192 far queries, native-disabled exact enclosure, refinement-denominator and mutation checks PASS',
    'limitations': ['Geometry-only saved-candidate diagnostic, no service/selection/acceptance/export publication.', 'Connectivity check NOT_RUN in this direct CAD entry point.', 'Architecture scope only; seven-discipline alignment remains unresolved.', 'Historical 1800 s whole-verification timeout is preserved; it is not a measured completed baseline for an exact speedup ratio.'],
    'source_changes': {name: decl['app_files']['oma/ifc/' + name] for name in ('cad.py', 'enclosure.py', 'federation.py')},
    'initial_profile_setup_failure': {'attempt': 'f1b74eeca0bd47b3b0a785c6b9400b57', 'observed_exception': "KeyError: OMA_EXECUTABLE_BUILD", 'scope': 'Runner setup before child launch; original scripts/predeclaration retained. This is a retrospective annotation, not a recovered original traceback.'},
    'initial_instrumented_profile': {'attempt': '58f8d7ae5a2440288c54851ce70ad5e9', 'status': 'UNKNOWN_TIMEOUT', 'deadline_seconds': 120, 'completed_products': 174, 'scope': 'cProfile instrumented partial support experiment, not full clearance.'}
})
(OUT / 'README.md').write_text('''# Hospital architecture cold clearance evidence

The exact previously timed-out four-part candidate passes the full ARC geometry check under frozen f716dd5c in 305.41 s (312.58 s supervised; peak sampled RSS 4.02 GB). All 14,641 physical declarations remain accounted: 232 grounded assemblies and 14,409 represented obstacles, giving 57,636 source pairs and six self-pairs. No pair is failed, unknown, blocked or missing geometry.

Complete checked source enclosures prove 13,151 obstacles separated from every route. The other 1,258 obstacles use actual native refinement. This is the existing explicitly declared source-support policy; enclosure-only products are not claimed to be native valid solids. Native route geometry is unchanged. The full original canonical parsed STEP records and both IFC byte hashes are rechecked. The original raw source bytes remain unchanged; canonical parsed entity preservation is distinct from raw serializer record identity.

This is a geometry-only diagnostic. Direct CAD connectivity is NOT_RUN; no operating/service, selection, acceptance or newly exported result is claimed here. The separate fresh campaign records those obligations. All seven Hospital disciplines remain imported but unresolved for alignment; this ARC-only success does not validate the federation or installed clinical services.

The generic changes are exact-source-support-first native refinement, cached immutable raw project-ID discovery, and exact self-reference federation identity. `base-src` and `combined-src` preserve 114-file snapshots. Final CAD-focused tests are 59 PASS; the initial one failed test expectation and all raw logs remain. The independent review covers affine transformations, all-route predicates, missing refinement, source mutation and callback propagation. The initial setup exception and instrumented 120 s timeout are retained without converting either to success.

`cold-probe/cad-report.json.gz` is the exact losslessly compressed 50 MB report. `actual.ifc.gz` preserves the original retained gzip bytes; compression.json binds decompressed hashes. path-mapping.json maps original absolute provenance to public copies. The native cache and temporary test fixtures are excluded; closed-cache-seed.json separately documents later byte-exact cache reuse. The successful cold probe started without a populated cache. Original scripts retain their executed absolute-root assumptions; use the mapping when replaying elsewhere.

The prior 1800 s result remains UNKNOWN_TIMEOUT and is not used to claim an exact whole-pipeline speedup ratio. No CAD, tests, live Store or source writes are performed by this retention script.
''', encoding='utf-8')
rows = {p.relative_to(OUT).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in sorted(OUT.rglob('*')) if p.is_file()}
write(OUT / 'index.json', {'schema': 'oma.file-inventory/1', 'files': rows, 'file_count': len(rows), 'logical_bytes': sum(v['bytes'] for v in rows.values()), 'self_exclusions': ['index.json', 'handoff.json', 'retention.json']})
assert all(sha(OUT / name) == record['sha256'] for name, record in rows.items())
write(OUT / 'handoff.json', {'schema': 'oma.hospital-clearance-retention/1', 'status': 'RETAINED_AND_REHASHED', 'index_sha256': sha(OUT / 'index.json'), 'summary_sha256': sha(OUT / 'summary.json'), 'file_count': len(rows), 'logical_bytes': sum(v['bytes'] for v in rows.values()), 'scope': 'Completed cold geometry-only probe and focused/independent evidence; no acceptance claim.'})
files = {p.relative_to(OUT).as_posix(): sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()}
write(OUT / 'retention.json', {'schema': 'oma.public-retention/1', 'retained_files': files, 'scope': 'Closed exact files; this self-map alone excluded.'})
assert set(files) | {'retention.json'} == {p.relative_to(OUT).as_posix() for p in OUT.rglob('*') if p.is_file()}
assert all(sha(OUT / name) == value for name, value in files.items())
print(json.dumps({'directory': str(OUT), 'handoff_sha256': sha(OUT / 'handoff.json'), 'retention_sha256': sha(OUT / 'retention.json'), 'files': len(files) + 1, 'indexed_files': len(rows), 'logical_bytes': sum(v['bytes'] for v in rows.values())}))
