"""Upload only individually verified immutable backup assets; retain remote digests."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[3]
ID='1a202fcf467a47368a4b3abc1167eb94'
EVIDENCE=ROOT/'evidence/release/github-backup'/ID
DEST=ROOT/'.release/github-backup'/ID
REPO='DaviBaum/oma-ananke-backup'
TAG='backup-2026-09-15'
COMMIT='0c7b0fb592e0fe64bd69b4e54088995781336158'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
    return h.hexdigest()
def gh(*args):
    r=subprocess.run(['gh',*args],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=900)
    if r.returncode:raise RuntimeError('gh '+args[0]+' failed: '+r.stderr[-3000:])
    return r.stdout
def release():return json.loads(gh('api',f'repos/{REPO}/releases/tags/{TAG}'))
result_path=EVIDENCE/'upload-result.json'
state=read(result_path) if result_path.exists() else {'status':'RUNNING','repo':REPO,'tag':TAG,'target_commit':COMMIT,'assets':[],
    'started_utc':datetime.now(timezone.utc).isoformat(),'authorization':'Explicit user upload request; parent confirmed initial full-history push and authorized private prerelease/upload',
    'uploader_sha256':sha(__file__)}
def persist():result_path.write_text(json.dumps(state,indent=2),encoding='utf-8')
persist()
try:
    assert json.loads(gh('repo','view',REPO,'--json','isPrivate'))['isPrivate'] is True
    existing=json.loads(gh('api',f'repos/{REPO}/releases'))
    if not any(r['tag_name']==TAG for r in existing):
        gh('release','create',TAG,'--repo',REPO,'--target',COMMIT,'--prerelease','--title','Private OMA + ANANKE backup — 2026-09-15',
            '--notes-file',str(Path(__file__).parent/'release-notes.md'))
    remote=release();assert remote['prerelease'] is True and remote['tag_name']==TAG
    state['release_url']=remote['html_url'];persist()
    stop=time.monotonic()+1800
    def upload(path,expected):
        assert sha(path)==expected
        remote=release();old=[a for a in remote['assets'] if a['name']==path.name]
        assert len(old)<=1
        if not old:
            state['active_asset']=path.name;persist()
            gh('release','upload',TAG,str(path),'--repo',REPO)
            old=[a for a in release()['assets'] if a['name']==path.name]
        assert len(old)==1 and old[0]['state']=='uploaded'
        asset=old[0]
        assert asset['size']==path.stat().st_size and asset['digest']=='sha256:'+expected
        assert sha(path)==expected
        row={'name':path.name,'id':asset['id'],'bytes':asset['size'],'sha256':expected,
             'remote_digest':asset['digest'],'url':asset['browser_download_url'],'status':'REMOTE_SIZE_SHA256_VERIFIED'}
        state['assets']=[a for a in state['assets'] if a['name']!=path.name]+[row]
        state.pop('active_asset',None);persist();print(json.dumps(row),flush=True)
    while time.monotonic()<stop:
        prepared=read(EVIDENCE/'result.json')
        for asset in prepared['assets']:
            assert asset['status']=='ZIP_MEMBER_SHA256_VERIFIED'
            if not any(a['name']==asset['name'] for a in state['assets']):upload(Path(asset['path']),asset['sha256'])
        if prepared['status']=='FAILED_RETAINED_PARTIAL_ASSETS':raise RuntimeError('Asset preparation failed: '+prepared.get('error',''))
        if prepared['status']=='ALL_BACKUP_ASSETS_PREPARED_AND_VERIFIED':
            for name in ('backup-assets-manifest.json','RESTORE.md'):upload(DEST/name,sha(DEST/name))
            remote=release()
            expected={a['name']:a['sha256'] for a in state['assets']}
            assert all(a['digest']=='sha256:'+expected[a['name']] for a in remote['assets'] if a['name'] in expected)
            state.update(status='ALL_BACKUP_ASSETS_UPLOADED_AND_REMOTE_DIGESTS_VERIFIED',completed_utc=datetime.now(timezone.utc).isoformat(),
                preparation_receipt_sha256=sha(EVIDENCE/'result.json'),manifest_sha256=sha(DEST/'backup-assets-manifest.json'),
                total_uploaded_bytes=sum(a['bytes'] for a in state['assets']))
            persist();print(json.dumps({'status':state['status'],'assets':len(state['assets']),'url':state['release_url']}),flush=True);break
        time.sleep(10)
    else:raise TimeoutError('Bounded upload wait exhausted; completed remote assets retained')
except BaseException as exc:
    state.update(status='FAILED_RETAINED_COMPLETED_UPLOADS',error=repr(exc));persist();raise
