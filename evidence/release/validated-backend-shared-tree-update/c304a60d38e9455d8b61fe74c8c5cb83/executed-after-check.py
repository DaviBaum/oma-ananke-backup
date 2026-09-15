import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import time
import urllib.request
import zlib
import psutil

ROOT=Path(__file__).resolve().parents[3]
EVIDENCE=Path(json.loads((Path(__file__).parent/'latest-preflight.json').read_text())['directory'])
def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def request(path):
    with urllib.request.urlopen('http://127.0.0.1:8768'+path,timeout=10) as r:return r.read()
meta=read(ROOT/'.oma/service.validated.json')
expected=read(EVIDENCE/'live-expected-source.json')
health=None
for attempt in range(20):
    try: health=json.loads(request('/api/health'));break
    except OSError: time.sleep(.5)
assert health is not None
identity=health['server_identity']
assert identity['checker_version']==identity['current_disk_checker_version']==expected['checker_version']
assert identity['declared_checker_version']==expected['checker_version']
assert identity['data_directory']==str(ROOT/'.oma') and identity['source_changed'] is False
assert identity['startup_environment_matches'] is True and identity['identity_error'] is None
assert identity['python_executable']==str(ROOT/'.venv/Scripts/python.exe')
(EVIDENCE/'after-health.json').write_text(json.dumps(health,indent=2))
source=Path(meta['pythonpath'])
assert {p.relative_to(source).as_posix():sha(p) for p in source.rglob('*.py')}==expected['files']
old_ui=read(EVIDENCE/'before-ui.json')['files']
served={name:hashlib.sha256(request('/'+name)).hexdigest() for name in old_ui}
assert served==old_ui
assert {p.relative_to(ROOT/'ui/dist').as_posix():sha(p) for p in (ROOT/'ui/dist').rglob('*') if p.is_file()}==old_ui
before=read(EVIDENCE/'before-store.json')
with sqlite3.connect((ROOT/'.oma/oma.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
    db.row_factory=sqlite3.Row
    after={}
    for name,order in (('projects','id'),('revisions','project_id,revision'),('runs','id'),('candidates','id')):
        after[name]=[dict(r) for r in db.execute('SELECT * FROM '+name+' ORDER BY '+order)]
        assert after[name]==before[name],name+' changed'
    after['owners']=[dict(r) for r in db.execute('SELECT * FROM run_owners')]
    assert after['owners']==before['owners']
for path,value in before['source_files'].items():assert sha(path)==value
for project in after['projects']:
    data=zlib.decompress((ROOT/'.oma/blobs'/(project['state_root']+'.json.z')).read_bytes())
    state=json.loads(data)
    canonical=json.dumps(state,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
    assert hashlib.sha256(canonical).hexdigest()==project['state_root']
    assert state.get('sources',[])==before['project_sources'][project['id']]
web_projects=json.loads(request('/api/projects'))
assert isinstance(web_projects,list) and {r['id'] for r in web_projects}=={r['id'] for r in after['projects']}
for item in web_projects:
    original=next(p for p in after['projects'] if p['id']==item['id'])
    assert item['state_root']==original['state_root'] and item['revision']==original['revision']
listeners=[c for c in psutil.net_connections(kind='tcp') if c.status=='LISTEN' and c.laddr.port==8768]
assert len(listeners)==1 and listeners[0].laddr.ip=='127.0.0.1'
server=psutil.Process(listeners[0].pid);launcher=psutil.Process(meta['pid'])
assert server.ppid()==launcher.pid and not server.children(recursive=True)
assert launcher.cmdline()==[str(ROOT/'.venv/Scripts/python.exe'),str(ROOT/'.oma/start_validated_backend.py')]
result={'status':'VALIDATED_33A_BACKEND_LIVE_AND_INVARIANTS_PASS','url':'http://127.0.0.1:8768',
    'checker_version':identity['checker_version'],'source_files':len(expected['files']),
    'same_original_native_environment':True,'recovery_enabled':False,'served_ui_files':served,
    'projects_unchanged':len(after['projects']),'revisions_unchanged':len(after['revisions']),
    'runs_unchanged':len(after['runs']),'candidates_unchanged':len(after['candidates']),
    'original_source_files_unchanged':len(before['source_files']),'project_source_manifests_unchanged':True,
    'old_shutdown':'VERIFIED_PRIVATE_CONSOLE_GRACEFUL_CTRL_C','force_termination':False,
    'launcher_pid':launcher.pid,'launcher_created':launcher.create_time(),'server_pid':server.pid,'server_created':server.create_time(),
    'source_manifest_sha256':sha(EVIDENCE/'live-expected-source.json'),'launcher_sha256':sha(ROOT/'.oma/start_validated_backend.py'),
    'scope':'Live local API only; prior package remains immutable; candidate evidence can correctly become stale under the new checker version'}
(EVIDENCE/'after-ui.json').write_text(json.dumps({'served':served},indent=2))
(EVIDENCE/'after-store.json').write_text(json.dumps(after,indent=2))
(EVIDENCE/'after-http-projects.json').write_text(json.dumps(web_projects,indent=2))
(EVIDENCE/'result.json').write_text(json.dumps(result,indent=2))
shutil.copyfile(__file__,EVIDENCE/'executed-after-check.py')
print(json.dumps(result))
