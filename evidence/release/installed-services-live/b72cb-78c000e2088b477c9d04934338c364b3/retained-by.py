"""Retain the validated side-server launch without copying a mutable live Store."""
from pathlib import Path
import hashlib, json, shutil

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'AGENTS.md').is_file())
SOURCE = Path(__file__).resolve().parent / 'live-backend/b72cb-78c000e2088b477c9d04934338c364b3'
OUT = ROOT / 'evidence/release/installed-services-live/b72cb-78c000e2088b477c9d04934338c364b3'
CAMPAIGN = ROOT / 'evidence/benchmarks/hospital-installed-services/1cbf8d8cc3c3485896f01b7a41a007fa-closed'

def sha(p):
    with p.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')

def copy(source, relative):
    target = OUT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    assert sha(source) == sha(target)

assert not OUT.exists()
OUT.mkdir(parents=True)
handoff = json.loads((SOURCE / 'handoff.json').read_text())
assert handoff['status'] == 'LIVE_VALIDATED_READ_ONLY_VERIFICATION_PASS'
assert handoff['exact_application_files'] == 117 and handoff['exact_ui_assets_served'] == 6
index = json.loads((SOURCE / 'support-index.json').read_text())
for relative, record in index.items():
    source = (SOURCE / relative).resolve()
    assert source.is_relative_to(SOURCE.resolve()) and sha(source) == record['sha256']
    copy(source, 'support/' + relative)
copy(SOURCE / 'support-index.json', 'support-index.json')
runtime = Path(handoff['runtime'])
application = json.loads((CAMPAIGN / 'application-source-manifest.json').read_text())
assert {p.relative_to(runtime / 'src').as_posix(): sha(p) for p in (runtime / 'src').rglob('*.py')} == application
for relative, expected in application.items():
    assert sha(CAMPAIGN / 'source' / relative) == expected
write(OUT / 'application-source-reference.json', {'path_from_repository_root': (CAMPAIGN / 'source').relative_to(ROOT).as_posix(), 'files': application})
for p in (runtime / 'ui/dist').rglob('*'):
    if p.is_file():
        copy(p, 'runtime-support/ui/dist/' + p.relative_to(runtime / 'ui/dist').as_posix())
copy(runtime / 'docs/capabilities.json', 'runtime-support/docs/capabilities.json')
copy(Path(__file__), 'retained-by.py')
write(OUT / 'restore-references.json', {
    'closed_original_store_snapshot': (CAMPAIGN / 'store/oma.sqlite3').relative_to(ROOT).as_posix(),
    'closed_content_addressed_artifact_index': (CAMPAIGN / 'artifact-index.json').relative_to(ROOT).as_posix(),
    'original_ifc_index': (CAMPAIGN / 'original-source-index.json').relative_to(ROOT).as_posix(),
    'regression': 'evidence/release/installed-services-regression/c3482addaad441e5958746e2ab7a41ba/handoff.json',
    'scope': 'Development-runtime launch record on the original machine; not a relocatable portable release. Live mutable data was not copied.'})
files = {p.relative_to(OUT).as_posix(): sha(p) for p in OUT.rglob('*') if p.is_file()}
write(OUT / 'handoff.json', {'schema': 'oma.installed-services-live-retention/1',
    'status': handoff['status'], 'checker_version': handoff['checker_version'], 'url': handoff['url'],
    'project_id': handoff['project_id'], 'report_root': handoff['report_root'],
    'retained_files': files, 'whole_building_optimized': False, 'construction_approval': False,
    'main8768_unchanged': True, 'live_store_is_separate_clone': True,
    'scope': handoff['scope']})
print(json.dumps({'status': 'RETAINED_AND_HASH_VERIFIED', 'handoff': str(OUT / 'handoff.json'),
    'sha256': sha(OUT / 'handoff.json'), 'files': len(files)}))
