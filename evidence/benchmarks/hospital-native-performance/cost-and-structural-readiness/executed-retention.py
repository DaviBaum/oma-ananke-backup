from pathlib import Path
import hashlib, json, shutil

ROOT = Path(__file__).resolve().parents[3]
STAGE = Path(__file__).resolve().parent
OUT = ROOT / 'evidence/benchmarks/hospital-native-performance/cost-and-structural-readiness'
if (OUT / 'handoff.json').exists():
    raise RuntimeError('Completed evidence may not be overwritten')
OUT.mkdir(parents=True, exist_ok=True)

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

mapping = {}
def copy(source, name):
    dest = OUT / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest)
    if sha(source) != sha(dest):
        raise RuntimeError('Copy mismatch')
    mapping[name] = {'original_path': str(source), 'sha256': sha(source), 'bytes': source.stat().st_size}

copy(Path(__file__), 'executed-retention.py')
for folder in ('first-inventory', 'checked-bill-v3'):
    for source in (STAGE / folder).rglob('*'):
        if source.is_file():
            copy(source, folder + '/' + source.relative_to(STAGE / folder).as_posix())
for name in ('takeoff-tests.xml',):
    copy(STAGE / name, 'validation/' + name)
copy(ROOT / 'tests/test_checked_network_takeoff.py', 'validation/test_checked_network_takeoff.py')
structural = ROOT / '.oma/development/hospital-structural-readiness'
handoff_path = structural / 'handoff.json'
if not handoff_path.is_file():
    raise RuntimeError('Structural completed handoff required before retention')
sh = json.loads(handoff_path.read_text(encoding='utf-8'))
for relative, expected in sh['retained_files'].items():
    source = (structural / relative).resolve()
    if not source.is_relative_to(structural.resolve()) or sha(source) != expected['sha256'] or source.stat().st_size != expected['bytes']:
        raise RuntimeError('Structural handoff mismatch')
    copy(source, 'structural/' + relative)
copy(handoff_path, 'structural/handoff.json')
dependencies = [
    'evidence/benchmarks/hospital-generated-tree/full-federation-1e87dd6ad9af48b5962cd500603fdfdc/handoff.json',
    'evidence/benchmarks/hospital-generated-tree/full-federation-1e87dd6ad9af48b5962cd500603fdfdc/files.json',
    'evidence/benchmarks/hospital-generated-tree/full-federation-1e87dd6ad9af48b5962cd500603fdfdc/public-mapping.json',
    'evidence/benchmarks/hospital-native-performance/accepted-4f0e44e4557a43528250e6884e8efd95/handoff.json',
    'evidence/benchmarks/hospital-native-performance/outcome-independent-95ec195c23b0451faee62f3d27747e51/handoff.json',
]
prior = {p: sha(ROOT / p) for p in dependencies}
(OUT / 'file-origins.json').write_text(json.dumps(mapping, indent=2) + '\n', encoding='utf-8')
index = {p.relative_to(OUT).as_posix(): sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()}
result = {'status': 'CLOSED_READ_ONLY_HOSPITAL_COST_AND_STRUCTURAL_READINESS_AUDIT',
          'retained_files': index, 'prior_retained_source_and_campaign_dependencies': prior,
          'original_sources_changed': False, 'application_source_changed': False,
          'new_optimized_design': False, 'structural_verification': 'NOT_IMPLEMENTED_AND_INPUTS_INCOMPLETE',
          'whole_building_savings': None, 'scope': 'Source quantity inventory and conditional unpriced bill comparison; not construction approval'}
(OUT / 'handoff.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': result['status'], 'files': len(index), 'handoff_sha256': sha(OUT / 'handoff.json')}))
