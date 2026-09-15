"""Root-executed one-time second CTRL_C for the already shutting-down owned server.

This is forced connection/task draining, not graceful lifespan completion.
No process-termination API or retry loop is used.
"""
from pathlib import Path
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import time
import psutil

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / 'AGENTS.md').is_file())
sys.path.insert(0, str(HERE / 'prepared'))
from validation_gate import completed_validation
import store_inventory

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def write(p, value):
    p.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')

def require(condition, message):
    if not condition:
        raise RuntimeError(message)

def same(record, meta):
    process = psutil.Process(record['pid'])
    require(process.create_time() == record['created'] and process.cmdline() == record['cmdline'] and process.exe() == record['exe'], 'Owned process identity changed')
    env = process.environ()
    require(env['PYTHONPATH'] == meta['pythonpath'] and env['OMA_EXECUTABLE_BUILD'] == meta['executable_build'], 'Owned process environment changed')
    return process

def idle(source):
    with sqlite3.connect((ROOT / '.oma/oma.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
        require(all(row[0] in store_inventory.terminal_states(source) for row in db.execute('SELECT status FROM runs')), 'A run is active')
        for pid, created in db.execute('SELECT pid, process_created FROM run_owners'):
            try:
                require(abs(psutil.Process(pid).create_time() - created) >= .1, 'A run owner is alive')
            except psutil.NoSuchProcess:
                pass

def listener_released():
    return not any(c.status == 'LISTEN' and c.laddr.port == 8768 for c in psutil.net_connections(kind='tcp'))

def execute(evidence):
    evidence = evidence.resolve()
    require(evidence == Path(read(HERE / 'prepared/latest-preflight.json')['directory']).resolve(), 'Wrong preflight directory')
    require(evidence.is_relative_to(ROOT / 'evidence/release/validated-backend-hospital-update'), 'Evidence outside approved handover tree')
    attempt = evidence / 'second-interrupt'
    require(not attempt.exists() and not (evidence / 'shutdown-complete.json').exists(), 'Second interrupt already attempted or shutdown completed')
    gate = completed_validation()
    require(gate == read(evidence / 'expected-source.json'), 'Completed gate identity changed')
    preflight = read(evidence / 'preflight.json')
    first = read(evidence / 'shutdown-request.json')
    require(preflight['status'] == 'OWNED_IDLE_PREFLIGHT_PASS' and preflight['private_console'] is True, 'No owned idle preflight')
    require(first['status'] == 'VERIFIED_PRIVATE_CONSOLE_CTRL_C_REQUESTED' and first['signal'] == 'CTRL_C_EVENT', 'First interrupt absent')
    require(first['launcher'] == preflight['launcher'] and first['server'] == preflight['server'], 'First interrupt identities differ')
    review = read(HERE / 'second-interrupt-review.json')
    require(all(sha(path) == value for path, value in review['reviewed_dependency_files'].items()), 'Reviewed Uvicorn/asyncio/application bytes changed')
    meta = read(evidence / 'old-service.validated.json')
    require(read(ROOT / '.oma/service.validated.json') == meta, 'Live metadata changed')
    require(sha(ROOT / '.oma/start_validated_backend.py') == meta['launcher_sha256'], 'Live launcher changed')
    require(listener_released(), 'Old listener still accepts connections')
    current_log = Path(meta['stderr']).read_text(encoding='utf-8-sig')
    require('Shutting down' in current_log and 'Waiting for connections to close. (CTRL+C to force quit)' in current_log, 'No observed Uvicorn connection-drain wait')
    require(f"Finished server process [{preflight['server']['pid']}]" not in current_log, 'Server already finished')
    baseline = read(evidence / 'before-all-store.json')
    before = store_inventory.snapshot()
    require(before == baseline, 'Store changed since preflight')
    idle(gate['source_directory'])
    launcher, server = same(preflight['launcher'], meta), same(preflight['server'], meta)
    require(server.ppid() == launcher.pid and not server.children(recursive=True), 'Owned server tree differs')
    children = launcher.children(recursive=True)
    require(all(p.pid == server.pid or (Path(p.exe()).resolve() == Path(os.environ['SystemRoot'], 'System32/conhost.exe').resolve() and p.ppid() == launcher.pid and abs(p.create_time() - launcher.create_time()) < .25) for p in children), 'Unexpected launcher descendant')
    require(len(children) <= 2, 'Unexpected launcher process count')
    attempt.mkdir()
    shutil.copyfile(__file__, attempt / 'executed-second-interrupt.py')
    shutil.copyfile(HERE / 'second-interrupt-review.json', attempt / 'review.json')
    for label, p in (('before-stderr.log', meta['stderr']), ('before-stdout.log', meta['stdout'])):
        shutil.copyfile(p, attempt / label)
    write(attempt / 'before-store-summary.json', {'equals_original_preflight': True, 'table_count': len(before['tables']), 'artifact_count': len(before['artifact_files']), 'original_snapshot_sha256': sha(evidence / 'before-all-store.json')})
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.FreeConsole.argtypes = []
    kernel.FreeConsole.restype = wintypes.BOOL
    kernel.AttachConsole.argtypes = [wintypes.DWORD]
    kernel.AttachConsole.restype = wintypes.BOOL
    kernel.GetConsoleProcessList.argtypes = [ctypes.POINTER(wintypes.DWORD), wintypes.DWORD]
    kernel.GetConsoleProcessList.restype = wintypes.DWORD
    kernel.SetConsoleCtrlHandler.argtypes = [ctypes.c_void_p, wintypes.BOOL]
    kernel.SetConsoleCtrlHandler.restype = wintypes.BOOL
    kernel.GenerateConsoleCtrlEvent.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.GenerateConsoleCtrlEvent.restype = wintypes.BOOL
    kernel.FreeConsole()
    require(kernel.AttachConsole(server.pid), 'Cannot attach exact owned console')
    try:
        members = (wintypes.DWORD * 64)()
        count = kernel.GetConsoleProcessList(members, 64)
        require(0 < count <= 64 and set(members[:count]) == {server.pid, launcher.pid, os.getpid()}, 'Console is not private to the two owned processes')
        require(kernel.SetConsoleCtrlHandler(None, True), 'Helper cannot ignore its own console interrupt')
        same(preflight['launcher'], meta)
        same(preflight['server'], meta)
        idle(gate['source_directory'])
        require(listener_released() and read(ROOT / '.oma/service.validated.json') == meta, 'Last ownership guard changed')
        write(attempt / 'request.json', {'status': 'VERIFIED_OWNED_SECOND_CTRL_C_REQUESTED', 'signal': 'CTRL_C_EVENT', 'console_members': list(members[:count]), 'first_request_sha256': sha(evidence / 'shutdown-request.json'), 'launcher': preflight['launcher'], 'server': preflight['server'], 'scope': 'One additional interrupt to the same idle owned private console; Uvicorn force_exit may skip normal lifespan shutdown. No kill/TerminateProcess, no retries.'})
        require(kernel.GenerateConsoleCtrlEvent(0, 0), 'Second CTRL_C generation failed')
        time.sleep(.25)
    finally:
        kernel.FreeConsole()
    gone, alive = psutil.wait_procs([server, launcher], timeout=30)
    write(attempt / 'wait-result.json', {'gone': [p.pid for p in gone], 'alive': [p.pid for p in alive], 'timeout_seconds': 30})
    require(not alive, 'Second interrupt did not finish; no further signal or kill attempted')
    require(listener_released(), 'Listener reappeared')
    require(read(ROOT / '.oma/service.validated.json') == meta, 'Metadata changed during drain')
    after = store_inventory.snapshot()
    require(after == before == baseline, 'Store changed during forced drain')
    idle(gate['source_directory'])
    for key in ('stdout', 'stderr'):
        shutil.copyfile(meta[key], evidence / ('closed-old-backend.' + key + '.log'))
        shutil.copyfile(meta[key], attempt / ('after-' + key + '.log'))
    log = (evidence / 'closed-old-backend.stderr.log').read_text(encoding='utf-8-sig')
    require(f'Finished server process [{server.pid}]' in log, 'Uvicorn server completion not observed')
    result = {'status': 'OWNED_FORCED_CONNECTION_DRAIN_COMPLETED', 'port_released': True, 'owned_processes_gone': True,
              'store_before_after_exact': True, 'table_count': len(after['tables']), 'artifact_count': len(after['artifact_files']),
              'force_termination': False, 'second_ctrl_c': True, 'graceful_application_lifespan_completed': False,
              'normal_lifespan_shutdown_claim': 'NOT_ESTABLISHED: installed Uvicorn skips its normal lifespan.shutdown when force_exit is set',
              'application_shutdown_complete_log_observed': 'Application shutdown complete.' in log,
              'request_sha256': sha(attempt / 'request.json'), 'before_snapshot_sha256': sha(evidence / 'before-all-store.json'),
              'disposition': 'Idle owned server stopped after one additional CTRL_C released connection/task waits. No active job/native worker existed; all Store tables/files and reachable assets preserved. This is not a graceful lifecycle claim.'}
    write(attempt / 'result.json', result)
    write(evidence / 'shutdown-complete.json', result)
    write(attempt / 'handoff.json', {'status': result['status'], 'retained_files': {p.name: sha(p) for p in attempt.iterdir() if p.is_file()}})
    print(json.dumps({'result': result, 'handoff': str(attempt / 'handoff.json'), 'handoff_sha256': sha(attempt / 'handoff.json')}))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--request-second-interrupt', action='store_true')
    args = parser.parse_args()
    require(args.request_second_interrupt, 'Explicit root execution flag required; preparation does not send signals')
    execute(args.evidence)
