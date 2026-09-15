"""Verify already uploaded draft by release ID, then publish. Preserve prior404."""
from pathlib import Path
import hashlib,json,subprocess,shutil,time,uuid
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
PRIOR=ROOT/'evidence/release/github-edf-portable/b18fa86afdd840d199162e4cee854bd5'
OUT=ROOT/'evidence/release/github-edf-portable'/('completed-'+uuid.uuid4().hex);OUT.mkdir()
REPO='DaviBaum/oma-ananke-backup';TAG='validated-general-tree-2026-09-15'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,obj):(OUT/name).write_text(json.dumps(obj,indent=2)+'\n',encoding='utf-8')
shutil.copyfile(__file__,OUT/'executed-finish.py');seq=0
def cmd(args):
    global seq
    seq+=1;start=time.monotonic();p=str(seq)
    r=subprocess.run(args,cwd=ROOT,capture_output=True)
    (OUT/(p+'.stdout.log')).write_bytes(r.stdout);(OUT/(p+'.stderr.log')).write_bytes(r.stderr)
    write(p+'.command.json',{'argv':args,'returncode':r.returncode,'seconds':time.monotonic()-start})
    assert r.returncode==0,(p,r.stderr.decode())
    return json.loads(r.stdout) if args[1]=='api' or args[1:3]==['release','view'] else r.stdout.decode()
before=json.loads((PRIOR/'preflight.json').read_text());assets=before['assets']
view=cmd(['gh','release','view',TAG,'--repo',REPO,'--json','databaseId,isDraft,isPrerelease,targetCommitish'])
assert view['isPrerelease'] and view['targetCommitish']==before['commit']
remote=cmd(['gh','api',f'repos/{REPO}/releases/{view["databaseId"]}'])
def verify(d):
    assert d['tag_name']==TAG and d['target_commitish']==before['commit']
    assert {a['name']:{'bytes':a['size'],'sha256':a['digest'].removeprefix('sha256:')} for a in d['assets']}==assets
    assert all(a['state']=='uploaded' for a in d['assets'])
verify(remote)
write('remote-verified-before-publication.json',{'status':'ALL_REMOTE_ASSET_DIGESTS_AND_SIZES_MATCH','assets':assets,'release_id':remote['id']})
if view['isDraft']:cmd(['gh','release','edit',TAG,'--repo',REPO,'--draft=false','--prerelease'])
final=cmd(['gh','api',f'repos/{REPO}/releases/tags/{TAG}']);verify(final)
assert not final['draft'] and final['prerelease']
write('completed-handoff.json',{'status':'PRIVATE_PRERELEASE_PUBLISHED_AND_VERIFIED','url':final['html_url'],
    'source_checkpoint':before['source_checkpoint'],'commit':before['commit'],'assets':assets,'total_bytes':sum(a['bytes'] for a in assets.values()),
    'prior_upload_directory':str(PRIOR),'prior_closed_files':{p.name:sha(p) for p in PRIOR.iterdir() if p.is_file()},
    'prior_failure':'Draft release tag endpoint returned404; existing uploaded draft was resolved by release ID, checked, then published without uploading or replacing assets.',
    'prior_finish_attempts':{p.name:{f.name:sha(f) for f in p.iterdir() if f.is_file()} for p in OUT.parent.glob('completed-*') if p!=OUT},
    'files':{p.name:sha(p) for p in OUT.iterdir() if p.is_file()},'full_original_math_complete':False,'whole_hospital_verified':False})
print(json.dumps({'status':'COMPLETE','evidence':str(OUT),'url':final['html_url']}))
