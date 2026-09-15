"""Retain the completed exact regression and its independent review."""
from pathlib import Path
import gzip, hashlib, json, sys

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'AGENTS.md').is_file())
STAGE = Path(__file__).resolve().parent
RUN = STAGE / 'combined-validation/c3482addaad441e5958746e2ab7a41ba'
OUT = ROOT / 'evidence/release/installed-services-regression/c3482addaad441e5958746e2ab7a41ba'
CAMPAIGN = ROOT / 'evidence/benchmarks/hospital-installed-services/1cbf8d8cc3c3485896f01b7a41a007fa-closed'

def sha(p):
    with p.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def write(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')

def copy(p, relative):
    raw = p.read_bytes()
    compressed = len(raw) > 500_000 and p.suffix in {'.json', '.log', '.xml'}
    target = OUT / (relative + ('.gz' if compressed else ''))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0) if compressed else raw)
    assert (gzip.decompress(target.read_bytes()) if compressed else target.read_bytes()) == raw
    mappings.append({'original': str(p), 'retained': target.relative_to(OUT).as_posix(),
        'encoding': 'gzip' if compressed else 'identity', 'original_sha256': sha(p),
        'original_bytes': len(raw), 'retained_sha256': sha(target)})

result = json.loads((RUN / 'result.json').read_text())
assert result['status'] == 'PASS' and result['passed'] == result['test_node_count'] == 3426
assert result['observed_xml_counts'] == {'testcase': 3426, 'failure': 0, 'error': 0, 'skipped': 0}
for key in ('exact_case_identity_multiset', 'inputs_unchanged', 'source_unchanged', 'native_unchanged'):
    assert result[key] is True
assert not (OUT / 'handoff.json').exists()
OUT.mkdir(parents=True, exist_ok=True)
mappings = []
for p in sorted(RUN.iterdir()):
    if p.is_file():
        copy(p, 'regression/' + p.name)
for relative, expected in result['snapshot_files'].items():
    p = RUN / 'snapshot' / relative
    assert sha(p) == expected
    copy(p, 'snapshot/' + relative)
for relative, expected in result['derived_outputs'].items():
    p = RUN / 'snapshot' / relative
    assert sha(p) == expected
    copy(p, 'snapshot/' + relative)
application = json.loads((CAMPAIGN / 'application-source-manifest.json').read_text())
assert application == result['source_files'] and len(application) == 117
for relative, expected in application.items():
    assert sha(CAMPAIGN / 'source' / relative) == expected
write(OUT / 'application-source-reference.json', {'path_from_repository_root': (CAMPAIGN / 'source').relative_to(ROOT).as_posix(),
    'files': application, 'checker_version': result['checker_version']})

review = Path(sys.argv[1]).resolve()
handoff = json.loads((review / 'handoff.json').read_text())
for relative, expected in handoff.get('retained_files', handoff.get('files')).items():
    p = review / relative
    if not p.is_file():
        p = ROOT / relative
    assert p.resolve().is_relative_to(review) and sha(p) == (expected['sha256'] if isinstance(expected, dict) else expected)
    copy(p, 'independent-review/' + p.resolve().relative_to(review).as_posix())
copy(review / 'handoff.json', 'independent-review/original-handoff.json')
copy(Path(__file__), 'retained-by.py')
write(OUT / 'file-mapping.json', mappings)
files = {p.relative_to(OUT).as_posix(): sha(p) for p in OUT.rglob('*') if p.is_file()}
write(OUT / 'handoff.json', {'schema': 'oma.installed-services-full-regression-retention/1',
    'status': 'PASS', 'checker_version': result['checker_version'], 'passed': result['passed'],
    'failures': 0, 'errors': 0, 'skips': 0, 'source_file_count': len(application),
    'frozen_input_count': len(result['snapshot_files']), 'derived_output_count': len(result['derived_outputs']),
    'test_seconds': result['test_seconds'], 'exact_testcase_multiset_verified': True,
    'retained_files': files, 'external_application_sources': 'application-source-reference.json',
    'native_environment': 'regression/native-environment.json',
    'scope': 'Exact original-native Python regression for this build; not a whole-building engineering or portable-runtime approval'})
print(json.dumps({'status': 'RETAINED_AND_HASH_VERIFIED', 'handoff': str(OUT / 'handoff.json'),
    'sha256': sha(OUT / 'handoff.json'), 'files': len(files)}))
