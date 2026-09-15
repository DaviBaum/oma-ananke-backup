"""Independently reconcile remote assets and publish the completed backup index."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
ID='1a202fcf467a47368a4b3abc1167eb94'
DEST=ROOT/'.release/github-backup'/ID
OUT=ROOT/'evidence/release/github-backup'/ID
REPO='DaviBaum/oma-ananke-backup';TAG='backup-2026-09-15'
COMMIT='0c7b0fb592e0fe64bd69b4e54088995781336158'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def gh(*args):return subprocess.check_output(['gh',*args],cwd=ROOT,text=True)
uploads=read(OUT/'upload-result.json');prepared=read(OUT/'result.json');extra=read(OUT/'dataset-provenance-upload.json')
assert uploads['status']=='ALL_BACKUP_ASSETS_UPLOADED_AND_REMOTE_DIGESTS_VERIFIED'
assert prepared['status']=='ALL_BACKUP_ASSETS_PREPARED_AND_VERIFIED'
assert uploads['preparation_receipt_sha256']==sha(OUT/'result.json')
assert extra['status']=='ADDITIONAL_DATASET_NOTICES_UPLOADED_AND_VERIFIED'
repo=json.loads(gh('repo','view',REPO,'--json','isPrivate,url,nameWithOwner'));assert repo['isPrivate'] is True
tag=json.loads(gh('api',f'repos/{REPO}/git/ref/tags/{TAG}'))
assert tag['object']['type']=='commit' and tag['object']['sha']==COMMIT
remote=json.loads(gh('api',f'repos/{REPO}/releases/tags/{TAG}'))
assert remote['prerelease'] is True
expected={a['name']:{'sha256':a['sha256'],'bytes':a['bytes']} for a in uploads['assets']}
expected[extra['asset']['name']]={'sha256':extra['local_sha256'],'bytes':extra['asset']['size']}
assert len(expected)==12 and {a['name'] for a in remote['assets']}==set(expected)
for a in remote['assets']:
    assert a['state']=='uploaded' and a['digest']=='sha256:'+expected[a['name']]['sha256'] and a['size']==expected[a['name']]['bytes']
index={'status':'PRIVATE_GITHUB_BACKUP_COMPLETE','repository':repo['url'],'release':remote['html_url'],'private':True,
    'backup_tag_commit':COMMIT,'current_source_checkpoint':'33a20d125bba02a298d12048a5b6227e51a98d8a043b999097d94a8d88b67b95',
    'sealed_runtime_checkpoint':'5e8fe9659cfde60f84f5cf93f38a1959428b3e7522de741e905d1f505db2b73c',
    'covered':['Git application source, committed evidence and full history','24 original math files','14 hospital IFCs, project license/model card and original enclosing dataset license/README','current Store:31 projects,73 revisions,55 runs,99 candidates;4816 verified manifest files plus backup manifest','13 raw pending UI files and binary diff','unchanged sealed5e8 Windows package:14450 indexed files plus original index'],
    'assets':[{**expected[a['name']],'name':a['name'],'id':a['id'],'url':a['browser_download_url'],'remote_digest':a['digest']} for a in remote['assets']],
    'total_asset_bytes_excluding_this_index':sum(a['bytes'] for a in expected.values()),
    'restore':'Download all parts for each chosen archive, verify SHA256, and extract to a new directory; see RESTORE.md. Existing reports may be stale under a different source/runtime; no unchecked report is upgraded by backup.',
    'limits':'No claim to back up every ignored scratch/development directory, historical temporary Store, installed .venv, live process or arbitrary external file. Git source33a and the separately validated packaged runtime5e8 are distinct. No public redistribution clearance or new hospital result is claimed.',
    'preparation_receipt_sha256':sha(OUT/'result.json'),'upload_receipt_sha256':sha(OUT/'upload-result.json'),'script_sha256':sha(__file__)}
path=DEST/'BACKUP-COMPLETE.json';path.write_text(json.dumps(index,indent=2),encoding='utf-8')
gh('release','upload',TAG,str(path),'--repo',REPO)
remote=json.loads(gh('api',f'repos/{REPO}/releases/tags/{TAG}'))
final,=[a for a in remote['assets'] if a['name']==path.name]
assert final['digest']=='sha256:'+sha(path) and final['size']==path.stat().st_size and len(remote['assets'])==13
notes=OUT/'completed-release-notes.md'
notes.write_text('''Private backup complete. All 13 release assets have verified GitHub SHA-256 digests.

The repository retains application source, evidence, and full Git history. Release assets cover original mathematics, both seven-discipline hospital IFC schema tracks with original notices, the current portable project Store, pending UI files, and the unchanged sealed 5e8 runtime.

Read BACKUP-COMPLETE.json for the exact scope and SHA-256 inventory, and RESTORE.md before restoring into a NEW directory. Download all parts for each selected archive.

The current application source checkpoint is 33a; the separately validated packaged runtime is 5e8. No runtime upgrade, public redistribution clearance, or new hospital analysis result is claimed by this backup. This repository remains private.
''',encoding='utf-8')
gh('release','edit',TAG,'--repo',REPO,'--notes-file',str(notes))
(OUT/'BACKUP-COMPLETE.json').write_bytes(path.read_bytes())
(OUT/'remote-assets-final.json').write_text(json.dumps(remote,indent=2),encoding='utf-8')
(OUT/'executed-finalize-upload.py').write_bytes(Path(__file__).read_bytes())
receipt={'status':'FINAL_PRIVATE_BACKUP_REMOTE_AUDIT_PASS','private':True,'tag_commit':COMMIT,'release':remote['html_url'],
    'assets':13,'total_uploaded_bytes':sum(a['size'] for a in remote['assets']),'completed_index_sha256':sha(path),
    'completed_index_remote_digest':final['digest'],'remote_asset_list_sha256':sha(OUT/'remote-assets-final.json'),
    'original_store_unchanged':read(OUT/'store-backup-verification.json')['original_rows_unchanged'],'no_source_or_ui_edits':True}
(OUT/'final-remote-audit.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt))
