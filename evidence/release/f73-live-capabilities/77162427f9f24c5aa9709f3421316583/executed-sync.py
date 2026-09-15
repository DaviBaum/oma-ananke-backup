"""Restore current descriptive metadata in the frozen live runtime; no code changes."""
from pathlib import Path
import hashlib,json,shutil,urllib.request,uuid

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
SOURCE='f73a8793ae0df76d9ec53400cec18b05d2731f63c735b225c2246fee62df6b21'
OUT=ROOT/'evidence/release/f73-live-capabilities'/uuid.uuid4().hex
OUT.mkdir(parents=True)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(name,obj):(OUT/name).write_text(json.dumps(obj,indent=2)+'\n',encoding='utf-8')
def health():
    with urllib.request.urlopen('http://127.0.0.1:8768/api/health',timeout=20) as response:
        return json.load(response)

metadata=read(ROOT/'.oma/service.validated.json')
source=Path(metadata['pythonpath']).resolve()
assert source==ROOT/'.oma/validated-runtimes/f73a8793ae0d-dd31cd72c26c/src'
expected=read(metadata['expected_source_manifest'])['files']
def source_manifest():return {p.relative_to(source).as_posix():sha(p) for p in source.rglob('*.py')}
assert source_manifest()==expected and len(expected)==114
before=health();write('before-health.json',before)
assert before['server_identity']['checker_version'].endswith(':'+SOURCE)
assert not before['server_identity']['source_changed'] and before['status']=='ok'
target=source.parent/'docs/capabilities.json'
if target.exists():shutil.copyfile(target,OUT/'before-capabilities.json')
current=ROOT/'docs/capabilities.json'
catalogue=read(current)
assert catalogue['capabilities']
shutil.copyfile(current,OUT/'installed-capabilities.json')
target.parent.mkdir(exist_ok=True)
temporary=target.with_name('capabilities-'+uuid.uuid4().hex+'.tmp')
shutil.copyfile(current,temporary)
temporary.replace(target)
assert sha(target)==sha(current)==sha(OUT/'installed-capabilities.json')
after=health();write('after-health.json',after)
assert after['capabilities']==[{**c,'label':c['id'].replace('_',' ')} for c in catalogue['capabilities']]
assert after['server_identity']==before['server_identity'] and after['status']=='ok'
assert source_manifest()==expected
shutil.copyfile(__file__,OUT/'executed-sync.py')
write('handoff.json',{'status':'LIVE_CAPABILITY_REGISTER_RESTORED_AND_VERIFIED',
    'source_checkpoint':SOURCE,'runtime_target':str(target),'capabilities_count':len(catalogue['capabilities']),
    'capabilities_sha256':sha(target),'application_source_unchanged':True,
    'server_restarted':False,'store_mutated':False,
    'retained_files':{p.name:sha(p) for p in OUT.iterdir() if p.is_file()}})
print(json.dumps({'status':'PASS','handoff':str(OUT/'handoff.json'),'capabilities_count':len(catalogue['capabilities'])}))
