import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import urllib.request
import uuid
import zlib
import psutil

ROOT = Path(__file__).resolve().parents[3]
TARGET = ROOT/'evidence/release/validated-backend-general-tree-update'/uuid.uuid4().hex
TARGET.mkdir(parents=True)
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(name,value): (TARGET/name).write_text(json.dumps(value,indent=2),encoding='utf-8')
def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def blob(root):
    value = json.loads(zlib.decompress((ROOT/'.oma/blobs'/f'{root}.json.z').read_bytes()))
    raw = json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
    assert hashlib.sha256(raw).hexdigest() == root
    return value
def request(path):
    with urllib.request.urlopen('http://127.0.0.1:8768'+path,timeout=10) as r: return r.read()
def process(p):
    return {'pid':p.pid,'created':p.create_time(),'exe':p.exe(),'cmdline':p.cmdline(),'parent':p.ppid()}
meta = read(ROOT/'.oma/service.validated.json')
for name in ('service.validated.json','start_validated_backend.py'):
    shutil.copyfile(ROOT/'.oma'/name,TARGET/('old-'+name))
for key in ('stdout','stderr'):
    shutil.copyfile(meta[key],TARGET/('old-backend.'+key+'.log'))
health = json.loads(request('/api/health'));write('before-health.json',health)
assert health['server_identity']['checker_version'] == meta['executable_build']
assert health['server_identity']['data_directory'] == str(ROOT/'.oma')
assert health['server_identity']['source_changed'] is False and health['server_identity']['startup_environment_matches'] is True
launcher = psutil.Process(meta['pid'])
assert abs(launcher.create_time()-datetime.fromisoformat(meta['started_utc'].replace('Z','+00:00')).timestamp()) < .25
assert launcher.cmdline() == [str(ROOT/'.venv/Scripts/python.exe'),str(ROOT/'.oma/start_validated_backend.py')]
listeners = [c for c in psutil.net_connections(kind='tcp') if c.status=='LISTEN' and c.laddr.ip=='127.0.0.1' and c.laddr.port==8768]
assert len(listeners)==1
server = psutil.Process(listeners[0].pid)
assert server.ppid()==launcher.pid and server.cmdline()[-1]==str(ROOT/'.oma/start_validated_backend.py')
assert not server.children(recursive=True)
children=launcher.children(recursive=True)
hosts=[p for p in children if p.pid!=server.pid]
assert len(hosts)<=1
assert all(Path(p.exe()).resolve()==Path(os.environ['SystemRoot'],'System32','conhost.exe').resolve()
           and p.ppid()==launcher.pid and abs(p.create_time()-launcher.create_time())<.25 for p in hosts)
for p in (launcher,server):
    env=p.environ()
    assert env['PYTHONPATH']==meta['pythonpath'] and env['OMA_EXECUTABLE_BUILD']==meta['executable_build']
with sqlite3.connect((ROOT/'.oma/oma.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
    db.row_factory=sqlite3.Row
    projects=[dict(r) for r in db.execute('SELECT * FROM projects ORDER BY id')]
    revisions=[dict(r) for r in db.execute('SELECT * FROM revisions ORDER BY project_id,revision')]
    runs=[dict(r) for r in db.execute('SELECT * FROM runs ORDER BY id')]
    owners=[dict(r) for r in db.execute('SELECT * FROM run_owners')]
    candidates=[dict(r) for r in db.execute('SELECT * FROM candidates ORDER BY id')]
assert all(r['status'] in {'COMPLETED','FAILED','CANCELLED','NO_INCUMBENT_FOUND','BUDGET_EXHAUSTED'} for r in runs)
live_owners=[]
for row in owners:
    try:
        p=psutil.Process(row['pid'])
        if abs(p.create_time()-row['process_created']) < .1: live_owners.append(row)
    except psutil.NoSuchProcess: pass
assert not live_owners
files={}
project_sources={}
for project in projects:
    state=blob(project['state_root'])
    project_sources[project['id']]=state.get('sources',[])
    for source in state.get('sources',[]):
        path=Path(source['immutable_path'])
        assert path.is_file() and sha(path)==source['sha256']
        files[str(path)]=source['sha256']
write('before-store.json',{'projects':projects,'revisions':revisions,'runs':runs,'candidates':candidates,'owners':owners,
                          'live_owners':live_owners,'project_sources':project_sources,'source_files':files})
ui={p.relative_to(ROOT/'ui/dist').as_posix():sha(p) for p in (ROOT/'ui/dist').rglob('*') if p.is_file()}
assert len(ui)==6
served={name:hashlib.sha256(request('/'+name)).hexdigest() for name in ui}
assert served==ui
write('before-ui.json',{'files':ui,'served':served})
full_path=ROOT/'evidence/release/general-tree-original-full-a29404ec828e/result.json'
full=read(full_path)
assert full['status']=='PASS' and full['passed']==3012 and full['returncode']==0
assert full['source_unchanged'] and full['inputs_unchanged'] and full['native_unchanged']
source=ROOT/'evidence/release/general-tree-original-full-a29404ec828e/src'
expected={('oma/'+k if not k.startswith('oma/') else k):v for k,v in full['source_files'].items()}
actual={p.relative_to(source).as_posix():sha(p) for p in source.rglob('*.py')}
assert actual==expected and len(actual)==112
assert actual=={p.relative_to(ROOT/'src').as_posix():sha(p) for p in (ROOT/'src').rglob('*.py')}
write('expected-source.json',{'checker_version':full['checker_version'],'source_directory':str(source),'files':expected,
    'original_full_receipt':str(full_path),'original_full_receipt_sha256':sha(full_path)})
write('owned-processes.json',{'launcher':process(launcher),'server':process(server),'console_hosts':[process(p) for p in hosts]})
# Console attachment here is read-only and detached before exit. No signal.
kernel=ctypes.WinDLL('kernel32',use_last_error=True)
kernel.FreeConsole()
attached=bool(kernel.AttachConsole(server.pid))
console=[]
error=ctypes.get_last_error() if not attached else None
if attached:
    ids=(wintypes.DWORD*64)()
    count=kernel.GetConsoleProcessList(ids,64)
    assert 0<count<=64
    console=list(ids[:count])
    kernel.FreeConsole()
result={'status':'OWNED_IDLE_PREFLIGHT_PASS','directory':str(TARGET),'launcher':process(launcher),'server':process(server),
    'projects':len(projects),'revisions':len(revisions),'runs':len(runs),'candidates':len(candidates),'original_source_files':len(files),
    'source_checkpoint':full['checker_version'],'console_attached':attached,'console_error':error,'console_processes':console,
    'probe_pid':os.getpid(),'private_console':attached and set(console)=={launcher.pid,server.pid,os.getpid()},
    'scope':'Read-only preflight; no shutdown, project mutation, source or UI edits'}
write('preflight.json',result)
shutil.copyfile(__file__,TARGET/'executed-preflight.py')
(Path(__file__).parent/'latest-preflight.json').write_text(json.dumps({'directory':str(TARGET)}))
print(json.dumps(result))
