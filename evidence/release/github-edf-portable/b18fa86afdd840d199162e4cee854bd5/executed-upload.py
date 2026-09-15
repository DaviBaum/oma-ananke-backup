"""Root-owned private release upload; publish only after GitHub digest checks."""
from pathlib import Path
import hashlib,json,subprocess,time,uuid,shutil,traceback
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
OUT=ROOT/'evidence/release/github-edf-portable'/uuid.uuid4().hex
OUT.mkdir(parents=True)
shutil.copyfile(__file__,OUT/'executed-upload.py')
REPO='DaviBaum/oma-ananke-backup'; TAG='validated-general-tree-2026-09-15'
ASSETS=ROOT/'.release/github-backup/edf555760245-9259b9b50228'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def write(name,d): (OUT/name).write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
seq=0
def command(args):
    global seq
    seq+=1; start=time.monotonic(); prefix=f'{seq:02}'
    with (OUT/(prefix+'.stdout.log')).open('wb') as out,(OUT/(prefix+'.stderr.log')).open('wb') as err:
        result=subprocess.run(args,cwd=ROOT,stdout=out,stderr=err)
    write(prefix+'.command.json',{'argv':args,'exit_code':result.returncode,'seconds':time.monotonic()-start,
          'stdout_sha256':sha(OUT/(prefix+'.stdout.log')),'stderr_sha256':sha(OUT/(prefix+'.stderr.log'))})
    if result.returncode: raise RuntimeError(f'command{seq} exit{result.returncode}; see retained logs')
    return (OUT/(prefix+'.stdout.log')).read_text(encoding='utf-8')
try:
    manifest=json.loads((ASSETS/'edf-portable-archive-manifest.json').read_text())
    names=['oma-ananke-edf555760245-portable.zip','edf-portable-archive-manifest.json','RESTORE-EDF-PORTABLE.md']
    assets={name:{'bytes':(ASSETS/name).stat().st_size,'sha256':sha(ASSETS/name)} for name in names}
    assert assets[names[0]]=={'bytes':manifest['archive_bytes'],'sha256':manifest['archive_sha256']}
    head=command(['git','rev-parse','HEAD']).strip()
    write('preflight.json',{'status':'ASSET_HASHES_VERIFIED','commit':head,'assets':assets,'source_checkpoint':manifest['source_checkpoint']})
    command(['git','push','origin','master'])
    notes='''Validated general-tree backend checkpoint, source edf555760245.

This private Windows portable package is a recoverable, sealed application checkpoint. It contains the original/native regression evidence (3,012 passed in each environment), and the bundled run (3,009 passed; three named direct-interpreter bridge cases do not apply). All three saved Office IFC export roles passed fresh native rechecks. The archive contains 14,578 sealed files plus their index, and each archive member was decompressed and rehashed.

Download the ZIP, manifest and restore instructions. Verify the SHA-256 digest before extracting to a new directory and launching OMA.cmd. Keep prior sealed packages intact.

The original mathematical directive and full production readiness remain incomplete. This package includes full-ledger branching generation; the subsequent compact top-K and factorized pressure stage is separately validated and is not included here. Hospital source files and both completed hospital campaign results are in the repository and initial backup release. The full federation needs resolved alignment; the architecture-only native clearance run timed out without an accepted candidate. No whole-hospital verification or unrestricted physical optimum is claimed.
'''
    (OUT/'release-notes.md').write_text(notes,encoding='utf-8')
    command(['gh','release','create',TAG,'--repo',REPO,'--target',head,'--title','Validated general-tree portable checkpoint (EDF)','--draft','--prerelease','--notes-file',str(OUT/'release-notes.md')])
    command(['gh','release','upload',TAG,'--repo',REPO,*[str(ASSETS/n) for n in names]])
    remote=json.loads(command(['gh','api',f'repos/{REPO}/releases/tags/{TAG}']))
    assert remote['draft'] and remote['prerelease']
    observed={a['name']:{'bytes':a['size'],'sha256':a['digest'].removeprefix('sha256:')} for a in remote['assets']}
    assert observed==assets,(observed,assets)
    write('remote-verified.json',{'status':'ALL_REMOTE_ASSET_DIGESTS_AND_SIZES_MATCH','assets':observed,'release_id':remote['id']})
    command(['gh','release','edit',TAG,'--repo',REPO,'--draft=false','--prerelease'])
    final=json.loads(command(['gh','api',f'repos/{REPO}/releases/tags/{TAG}']))
    assert not final['draft'] and final['prerelease']
    assert {a['name']:{'bytes':a['size'],'sha256':a['digest'].removeprefix('sha256:')} for a in final['assets']}==assets
    write('completed-handoff.json',{'status':'PRIVATE_PRERELEASE_PUBLISHED_AND_VERIFIED','url':final['html_url'],
          'source_checkpoint':manifest['source_checkpoint'],'commit':head,'assets':assets,'total_bytes':sum(a['bytes'] for a in assets.values()),
          'files':{p.name:sha(p) for p in OUT.iterdir() if p.is_file()},'full_original_math_complete':False,'whole_hospital_verified':False})
    print(json.dumps({'status':'COMPLETE','evidence':str(OUT),'url':final['html_url']}),flush=True)
except BaseException:
    write('failure.json',{'status':'FAILED_RETAINED','traceback':traceback.format_exc()})
    raise
