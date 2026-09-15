"""Root-owned publication of a reviewed sealed archive, with resumable draft checks."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,time,traceback,uuid
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
SOURCE='f73a8793ae0df76d9ec53400cec18b05d2731f63c735b225c2246fee62df6b21'
REPO='DaviBaum/oma-ananke-backup';TAG='validated-compact-pressure-2026-09-15'
parser=argparse.ArgumentParser();parser.add_argument('manifest');parser.add_argument('restore');parser.add_argument('notes');args=parser.parse_args()
OUT=ROOT/'evidence/release/github-compact-portable'/uuid.uuid4().hex;OUT.mkdir(parents=True)
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(name,obj):(OUT/name).write_text(json.dumps(obj,indent=2)+'\n',encoding='utf-8')
shutil.copyfile(__file__,OUT/'executed-publish.py');seq=0
def command(argv,allow_failure=False,json_output=False):
    global seq
    seq+=1;prefix=f'{seq:02}';start=time.monotonic()
    with (OUT/(prefix+'.stdout.log')).open('wb') as stdout,(OUT/(prefix+'.stderr.log')).open('wb') as stderr:
        r=subprocess.run(argv,cwd=ROOT,stdout=stdout,stderr=stderr)
    out=(OUT/(prefix+'.stdout.log')).read_text(encoding='utf-8');err=(OUT/(prefix+'.stderr.log')).read_text(encoding='utf-8')
    write(prefix+'.command.json',{'argv':argv,'returncode':r.returncode,'seconds':time.monotonic()-start,
        'stdout_sha256':sha(OUT/(prefix+'.stdout.log')),'stderr_sha256':sha(OUT/(prefix+'.stderr.log'))})
    if r.returncode and not allow_failure:raise RuntimeError(f'Command{seq} failed; retained stdout/stderr')
    return (r.returncode,out,err) if allow_failure else (json.loads(out) if json_output else out)
def release_view(allow_failure=False):
    return command(['gh','release','view',TAG,'--repo',REPO,'--json','databaseId,isDraft,isPrerelease,targetCommitish'],allow_failure=allow_failure,json_output=not allow_failure)
try:
    manifest_path=Path(args.manifest).resolve();restore=Path(args.restore).resolve();notes=Path(args.notes).resolve()
    manifest=read(manifest_path);assert manifest['source_checkpoint']==SOURCE
    archive=Path(manifest['archive']).resolve();assert archive.parent==manifest_path.parent==restore.parent
    assets_paths=[archive,manifest_path,restore];assert len({p.name for p in assets_paths})==3
    assets={p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in assets_paths}
    assert assets[archive.name]=={'bytes':manifest['archive_bytes'],'sha256':manifest['archive_sha256']}
    for p in (manifest_path,restore,notes):shutil.copyfile(p,OUT/p.name)
    head=command(['git','rev-parse','HEAD']).strip()
    # Match Git source/test/support bytes to the passing immutable native suite.
    full=ROOT/'evidence/release/compact-tree-original-full-d6d1204384b8'
    expected={'src/'+k:v for k,v in read(full/'source.json').items()}|read(full/'inputs.json')['files']
    names=sorted(expected)
    raw=subprocess.check_output(['git','cat-file','--batch'],cwd=ROOT,input=''.join(head+':'+name+'\n' for name in names).encode())
    pos=0
    for name in names:
        end=raw.index(b'\n',pos);header=raw[pos:end].split();assert header[1]==b'blob'
        size=int(header[2]);start=end+1;assert hashlib.sha256(raw[start:start+size]).hexdigest()==expected[name],name
        assert raw[start+size:start+size+1]==b'\n';pos=start+size+1
    assert pos==len(raw) and len(names)==419
    write('preflight.json',{'status':'ARCHIVE_AND_EXACT_COMMITTED_SOURCE_INPUTS_VERIFIED','assets':assets,'commit':head,'source_checkpoint':SOURCE,'git_inputs':419})
    command(['git','push','origin','master'])
    remote_head=command(['git','ls-remote','origin','refs/heads/master']).split()[0];assert remote_head==head
    code,text,error=release_view(allow_failure=True)
    if code:
        assert 'release not found' in error.lower(),error
        command(['gh','release','create',TAG,'--repo',REPO,'--target',head,'--title','Validated compact topology and pressure backend','--draft','--prerelease','--notes-file',str(notes)])
        view=release_view()
    else:view=json.loads(text)
    assert view['isPrerelease'] and view['targetCommitish']==head
    endpoint=f'repos/{REPO}/releases/{view["databaseId"]}'
    remote=command(['gh','api',endpoint],json_output=True)
    def observed(d):return {a['name']:{'bytes':a['size'],'sha256':a['digest'].removeprefix('sha256:')} for a in d['assets']}
    found=observed(remote);assert all(name in assets and value==assets[name] for name,value in found.items())
    missing=[p for p in assets_paths if p.name not in found]
    if missing:
        assert view['isDraft'],'Do not change published release assets'
        command(['gh','release','upload',TAG,'--repo',REPO,*map(str,missing)])
    remote=command(['gh','api',endpoint],json_output=True)
    assert remote['tag_name']==TAG and remote['target_commitish']==head and observed(remote)==assets
    assert all(a['state']=='uploaded' for a in remote['assets'])
    write('remote-assets-verified.json',{'status':'ALL_REMOTE_DIGESTS_AND_BYTES_MATCH','assets':assets,'release_id':remote['id']})
    if remote['draft']:command(['gh','release','edit',TAG,'--repo',REPO,'--draft=false','--prerelease'])
    final=command(['gh','api',f'repos/{REPO}/releases/tags/{TAG}'],json_output=True)
    assert not final['draft'] and final['prerelease'] and observed(final)==assets
    write('completed-handoff.json',{'status':'PRIVATE_COMPACT_PORTABLE_RELEASE_PUBLISHED_AND_VERIFIED','url':final['html_url'],
        'commit':head,'source_checkpoint':SOURCE,'assets':assets,'total_bytes':sum(a['bytes'] for a in assets.values()),
        'full_original_math_complete':False,'whole_hospital_verified':False,
        'retained_files':{p.name:sha(p) for p in OUT.iterdir() if p.is_file()}})
    print(json.dumps({'status':'COMPLETE','url':final['html_url'],'evidence':str(OUT)}),flush=True)
except BaseException:
    write('failure.json',{'status':'FAILED_RETAINED','traceback':traceback.format_exc()});raise
