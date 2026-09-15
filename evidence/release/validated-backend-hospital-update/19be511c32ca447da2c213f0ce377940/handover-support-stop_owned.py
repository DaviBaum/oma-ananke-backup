"""Signal only a freshly verified private console of our idle server."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import shutil
import sqlite3
import time
import psutil
from validation_gate import completed_validation
import store_inventory as store_guard
GATE=completed_validation()

ROOT=next(p for p in Path(__file__).resolve().parents if (p/"AGENTS.md").exists())
EVIDENCE=Path(json.loads((Path(__file__).parent/'latest-preflight.json').read_text())['directory'])
data=json.loads((EVIDENCE/'preflight.json').read_text())
assert data['status']=='OWNED_IDLE_PREFLIGHT_PASS' and data['private_console'] is True
assert GATE == json.loads((EVIDENCE/'expected-source.json').read_text(encoding='utf-8'))
def same(record):
    p=psutil.Process(record['pid'])
    assert p.create_time()==record['created'] and p.cmdline()==record['cmdline'] and p.exe()==record['exe']
    return p
assert store_guard.snapshot()==json.loads((EVIDENCE/'before-all-store.json').read_text())
assert json.loads((ROOT/'.oma/service.validated.json').read_text(encoding='utf-8-sig')) == json.loads((EVIDENCE/'old-service.validated.json').read_text(encoding='utf-8-sig'))
launcher,server=same(data['launcher']),same(data['server'])
assert server.ppid()==launcher.pid and not server.children(recursive=True)
with sqlite3.connect((ROOT/'.oma/oma.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
    assert all(r[0] in store_guard.terminal_states(GATE['source_directory']) for r in db.execute('SELECT status FROM runs'))
    for pid,created in db.execute('SELECT pid,process_created FROM run_owners'):
        try: assert abs(psutil.Process(pid).create_time()-created)>=.1
        except psutil.NoSuchProcess: pass
listeners=[c for c in psutil.net_connections(kind='tcp') if c.status=='LISTEN' and c.laddr.port==8768]
assert len(listeners)==1 and listeners[0].pid==server.pid and listeners[0].laddr.ip=='127.0.0.1'
kernel=ctypes.WinDLL('kernel32',use_last_error=True)
kernel.FreeConsole()
assert kernel.AttachConsole(server.pid)
try:
    ids=(wintypes.DWORD*64)()
    count=kernel.GetConsoleProcessList(ids,64)
    assert 0<count<=64 and set(ids[:count])=={launcher.pid,server.pid,os.getpid()}
    assert kernel.SetConsoleCtrlHandler(None,True)
    same(data['launcher']);same(data['server'])
    request={'status':'VERIFIED_PRIVATE_CONSOLE_CTRL_C_REQUESTED','console_members':list(ids[:count]),
             'launcher':data['launcher'],'server':data['server'],'signal':'CTRL_C_EVENT','scope':'Only two owned idle application processes and this ignored-signal helper share the target console'}
    (EVIDENCE/'shutdown-request.json').write_text(json.dumps(request,indent=2))
    assert kernel.GenerateConsoleCtrlEvent(0,0)
    time.sleep(.25)
finally:
    kernel.FreeConsole()
gone,alive=psutil.wait_procs([server,launcher],timeout=20)
assert not alive,'Graceful shutdown did not complete; no force termination attempted'
assert not [c for c in psutil.net_connections(kind='tcp') if c.status=='LISTEN' and c.laddr.port==8768]
meta=json.loads((EVIDENCE/'old-service.validated.json').read_text())
for key in ('stdout','stderr'):
    shutil.copyfile(meta[key],EVIDENCE/('closed-old-backend.'+key+'.log'))
log=(EVIDENCE/'closed-old-backend.stderr.log').read_text()
assert 'Application shutdown complete.' in log and f'Finished server process [{server.pid}]' in log
(EVIDENCE/'shutdown-complete.json').write_text(json.dumps({'status':'GRACEFUL_OWNED_SHUTDOWN_COMPLETED','port_released':True,'force_termination':False},indent=2))
shutil.copyfile(__file__,EVIDENCE/'executed-stop.py')
print('GRACEFUL_OWNED_SHUTDOWN_COMPLETED')
