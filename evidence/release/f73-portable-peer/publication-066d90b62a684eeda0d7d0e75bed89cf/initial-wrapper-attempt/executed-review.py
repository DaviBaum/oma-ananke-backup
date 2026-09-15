"""Read-only GitHub metadata and final documentation peer review."""
import hashlib
import json
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'evidence/release/f73-portable-peer' / ('publication-' + uuid.uuid4().hex)
OUT.mkdir(parents=True)
REPO = 'DaviBaum/oma-ananke-backup'
TAG = 'validated-compact-pressure-2026-09-15'
COMMIT = 'd76febd07db7c385c3da36357914d9fe0ffd3f99'
PUBLICATION = ROOT / 'evidence/release/github-compact-portable/5f95cfb7b71341e88756c644711c81e0/completed-handoff.json'
FINALIZATION = ROOT / 'evidence/release/compact-final-documentation/d0c6d198db14494d81a24810adef16c9/handoff.json'
PACKAGE_HANDOFF = ROOT / 'evidence/release/factorized-tree-portable-completed-ddbee4976390/handoff.json'
SEAL = ROOT / 'evidence/dependencies/native-build/portable-candidates/f73a8793ae0d-ddbee4976390/sealed-handoff.json'

def sha(data): return hashlib.sha256(data).hexdigest()
def read(path): return json.loads(path.read_bytes().decode('utf-8-sig'))
def save(path, value): path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
commands = []
def api(endpoint, name):
    cmd = ['gh', 'api', endpoint]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, check=True)
    (OUT / (name + '.json')).write_bytes(proc.stdout)
    commands.append({'argv': cmd, 'cwd': str(ROOT), 'exit_code': proc.returncode,
                     'stdout_sha256': sha(proc.stdout), 'stderr_sha256': sha(proc.stderr)})
    assert not proc.stderr
    return json.loads(proc.stdout)

repo = api('repos/' + REPO, 'github-repository')
release = api('repos/' + REPO + '/releases/tags/' + TAG, 'github-release')
tag = api('repos/' + REPO + '/git/ref/tags/' + TAG, 'github-tag')
assert repo['private'] is True and repo['visibility'] == 'private'
assert release['draft'] is False and release['prerelease'] is True and release['published_at']
assert release['tag_name'] == TAG and release['target_commitish'] == COMMIT
assert tag['object'] == {'sha': COMMIT, 'type': 'commit', 'url': f'https://api.github.com/repos/{REPO}/git/commits/{COMMIT}'}
published = read(PUBLICATION)
assert published['status'] == 'PRIVATE_COMPACT_PORTABLE_RELEASE_PUBLISHED_AND_VERIFIED'
assert published['commit'] == COMMIT and published['url'] == release['html_url']
assets = {r['name']: r for r in release['assets']}
assert len(release['assets']) == len(assets) == 3 and set(assets) == set(published['assets'])
for name, expected in published['assets'].items():
    observed = assets[name]
    assert observed['state'] == 'uploaded'
    assert observed['size'] == expected['bytes'] and observed['digest'] == 'sha256:' + expected['sha256']
assert sum(r['size'] for r in assets.values()) == published['total_bytes'] == 1175670105

final = read(FINALIZATION)
handoff = read(PACKAGE_HANDOFF)
seal = read(SEAL)
assert final['release_handoff_sha256'] == sha(PUBLICATION.read_bytes())
assert final['package_handoff_sha256'] == sha(PACKAGE_HANDOFF.read_bytes())
assert final['source_checkpoint'] == handoff['source_checkpoint'] == published['source_checkpoint']
assert final['runtime_source_or_inputs_changed'] is False
assert final['full_original_math_complete'] is False and final['whole_hospital_verified'] is False
assert seal['artifact_index_sha256'] == handoff['artifact_index_sha256'] == 'de03e716e647f7ec8902f8ad793dc64f2355c2c763d849b8653b5f929030e01c'
assert seal['file_count'] == 14625 and seal['logical_bytes'] == 1993462494 and seal['bundled_passed'] == 3272

retained_counts = {}
for record_path, record in ((PUBLICATION, published), (FINALIZATION, final)):
    for name, expected in record['retained_files'].items():
        assert sha((record_path.parent / name).read_bytes()) == expected, name
    retained_counts[str(record_path.relative_to(ROOT))] = len(record['retained_files'])
for name, expected in final['changed_files'].items():
    assert sha((ROOT / name).read_bytes()) == expected, name

reviewed_docs = {}
local_links = []
for name in ('docs/native-portable-candidate.md', 'docs/PROGRESS.md', 'docs/GITHUB_BACKUP.md'):
    path = ROOT / name
    data = path.read_bytes()
    text = data.decode('utf-8-sig')
    assert 'validated-compact-pressure-2026-09-15' in text and '8765' in text and '8768' in text
    for link in re.findall(r'\]\(([^)]+)\)', text):
        if link.startswith(('https://', 'http://', '#')):
            continue
        target = path.parent / unquote(link.split('#', 1)[0])
        assert target.exists(), (name, link)
        local_links.append({'document': name, 'link': link})
    dest = OUT / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    reviewed_docs[name] = sha(data)
for name, expected in reviewed_docs.items():
    assert sha((ROOT / name).read_bytes()) == expected
for name, path in (('publication-handoff.json', PUBLICATION), ('finalization-handoff.json', FINALIZATION),
                   ('package-handoff.json', PACKAGE_HANDOFF), ('sealed-handoff.json', SEAL)):
    (OUT / name).write_bytes(path.read_bytes())
(OUT / 'executed-review.py').write_bytes(Path(__file__).read_bytes())
save(OUT / 'commands.json', commands)
result = {'schema': 'oma.published-release-peer-review/1', 'status': 'FINAL_F73_PUBLICATION_AND_DOCUMENTATION_PEER_PASS',
          'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'release_url': release['html_url'],
          'repository_private': True, 'release_draft': False, 'release_prerelease': True,
          'release_target_commit': COMMIT, 'actual_tag_commit': tag['object']['sha'],
          'source_checkpoint': published['source_checkpoint'], 'asset_count': 3,
          'remote_assets': {n: {'bytes': a['size'], 'sha256': a['digest'].removeprefix('sha256:')} for n, a in assets.items()},
          'total_remote_bytes': published['total_bytes'], 'reviewed_docs': reviewed_docs,
          'all_six_finalization_doc_hashes_verified': True, 'local_links_verified': local_links,
          'retained_receipt_files_verified': retained_counts, 'remaining_findings': [],
          'scope': 'Read-only native GitHub API metadata/digest comparison and local final documentation/receipt review. No release asset download or archive rehash, no native/test rerun, no production/Git mutation. The release is a published prerelease in a private repository; it does not claim all original mathematics or whole-Hospital completion.'}
save(OUT / 'result.json', result)
rows = {p.relative_to(OUT).as_posix(): sha(p.read_bytes()) for p in OUT.rglob('*') if p.is_file()}
save(OUT / 'retention.json', {'schema': 'oma.independent-peer-retention/1', 'status': 'FINAL_F73_PUBLICATION_PEER_EVIDENCE_CLOSED',
                             'retained_files': rows, 'file_count': len(rows), 'exclusions': ['retention.json itself']})
assert all(sha((OUT / name).read_bytes()) == expected for name, expected in rows.items())
print(json.dumps({'directory': str(OUT), 'status': result['status'], 'result_sha256': sha((OUT / 'result.json').read_bytes()),
                  'retention_sha256': sha((OUT / 'retention.json').read_bytes()), 'retained_files': len(rows)}))
