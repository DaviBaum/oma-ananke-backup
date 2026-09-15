"""Root-only forced recovery of the two exact idle processes after failed drains."""
from pathlib import Path
import argparse
import ctypes
from ctypes import wintypes
import json
import os
import shutil
import sqlite3
import sys
import psutil

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / 'AGENTS.md').is_file())
sys.path.insert(0, str(HERE))
from second_interrupt_owned import same, idle, listener_released, read, sha, write, require
sys.path.insert(0, str(HERE / 'prepared'))
from validation_gate import completed_validation
import store_inventory

def quick_check():
    with sqlite3.connect((ROOT / '.oma/oma.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
        rows = [r[0] for r in db.execute('PRAGMA quick_check')]
    require(rows == ['ok'], 'SQLite quick_check failed')
    return rows

def execute(evidence):
    evidence = evidence.resolve()
    require(evidence == Path(read(HERE / 'prepared/latest-preflight.json')['directory']).resolve(), 'Different handover evidence')
    require(evidence.is_relative_to(ROOT / 'evidence/release/validated-backend-hospital-update'), 'Unapproved evidence location')
    attempt = evidence / 'forced-process-recovery'
    require(not attempt.exists() and not (evidence / 'shutdown-complete.json').exists(), 'Recovery already attempted or stop completed')
    gate = completed_validation()
    require(gate == read(evidence / 'expected-source.json'), 'Full/source/outcome gate changed')
    preflight = read(evidence / 'preflight.json')
    meta = read(evidence / 'old-service.validated.json')
    review = read(HERE / 'forced-recovery-review.json')
    require(all(sha(p) == value for p, value in review['guard_files'].items()), 'Reviewed recovery guard changed')
    require(sha(__file__) == review['recovery_script_sha256'], 'Recovery code differs from review')
    require(preflight['status'] == 'OWNED_IDLE_PREFLIGHT_PASS' and preflight['private_console'] is True, 'Missing private idle preflight')
    first = read(evidence / 'shutdown-request.json')
    second = read(evidence / 'second-interrupt/request.json')
    failed_wait = read(evidence / 'second-interrupt/wait-result.json')
    require(first['status'] == 'VERIFIED_PRIVATE_CONSOLE_CTRL_C_REQUESTED' and second['status'] == 'VERIFIED_OWNED_SECOND_CTRL_C_REQUESTED', 'Two retained interrupt requests required')
    require(first['launcher'] == second['launcher'] == preflight['launcher'] and first['server'] == second['server'] == preflight['server'], 'Prior interrupt ownership differs')
    require(second['first_request_sha256'] == sha(evidence / 'shutdown-request.json'), 'First interrupt binding differs')
    require(failed_wait['gone'] == [] and set(failed_wait['alive']) == {preflight['launcher']['pid'], preflight['server']['pid']}, 'Retained second wait is not the specified failure')
    require(read(ROOT / '.oma/service.validated.json') == meta and sha(ROOT / '.oma/start_validated_backend.py') == meta['launcher_sha256'], 'Old metadata/launcher changed')
    require(listener_released(), 'A listener reappeared')
    baseline = read(evidence / 'before-all-store.json')
    before = store_inventory.snapshot()
    require(before == baseline, 'Store no longer equals preflight')
    sqlite_before = quick_check()
    idle(gate['source_directory'])
    launcher, server = same(preflight['launcher'], meta), same(preflight['server'], meta)
    def children_checked():
        require(not server.children(recursive=True) and server.ppid() == launcher.pid, 'Server has a child or wrong parent')
        children = launcher.children(recursive=True)
        require(len(children) <= 2, 'Unexpected launcher descendant count')
        require(all(p.pid == server.pid or (Path(p.exe()).resolve() == Path(os.environ['SystemRoot'], 'System32/conhost.exe').resolve() and p.ppid() == launcher.pid and abs(p.create_time() - launcher.create_time()) < .25) for p in children), 'Unexpected launcher descendant')
    children_checked()
    attempt.mkdir()
    shutil.copyfile(__file__, attempt / 'executed-recovery.py')
    shutil.copyfile(HERE / 'forced-recovery-review.json', attempt / 'review.json')
    for key in ('stdout', 'stderr'):
        shutil.copyfile(meta[key], attempt / ('before-' + key + '.log'))
    write(attempt / 'before-store-summary.json', {'exact_preflight_match': True, 'table_count': len(before['tables']), 'artifact_count': len(before['artifact_files']), 'sqlite_quick_check': sqlite_before, 'snapshot_sha256': sha(evidence / 'before-all-store.json'), 'consistent_preflight_backup_sha256': sha(evidence / 'before-store.sqlite3')})
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    signatures = {
        'OpenProcess': ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
        'CloseHandle': ([wintypes.HANDLE], wintypes.BOOL),
        'GetProcessTimes': ([wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4, wintypes.BOOL),
        'QueryFullProcessImageNameW': ([wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
        'WaitForSingleObject': ([wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
        'TerminateProcess': ([wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
        'FreeConsole': ([], wintypes.BOOL), 'AttachConsole': ([wintypes.DWORD], wintypes.BOOL),
        'GetConsoleProcessList': ([ctypes.POINTER(wintypes.DWORD), wintypes.DWORD], wintypes.DWORD)}
    for name, (argtypes, restype) in signatures.items():
        function = getattr(kernel, name); function.argtypes = argtypes; function.restype = restype
    handles = {}
    identities = {}
    try:
        for label in ('server', 'launcher'):
            record = preflight[label]
            same(record, meta)
            handle = kernel.OpenProcess(0x0001 | 0x1000 | 0x00100000, False, record['pid'])
            require(handle, 'Cannot pin exact owned process handle')
            handles[label] = handle
            times = [wintypes.FILETIME() for _ in range(4)]
            require(kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)), 'Cannot read pinned process creation')
            ticks = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
            created = (ticks - 116444736000000000) / 10000000
            require(abs(created - record['created']) < .00001, 'Pinned handle is not the preflight process')
            buffer = ctypes.create_unicode_buffer(32768); size = wintypes.DWORD(len(buffer))
            require(kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)), 'Cannot read pinned process image')
            require(Path(buffer.value).resolve() == Path(record['exe']).resolve(), 'Pinned handle image differs')
            require(kernel.WaitForSingleObject(handle, 0) == 258, 'Pinned process already exited')
            same(record, meta)
            identities[label] = {'pid': record['pid'], 'creation_filetime': ticks, 'image': buffer.value, 'cmdline': record['cmdline']}
        # Attachment verifies console membership only; no further signal is sent.
        kernel.FreeConsole()
        require(kernel.AttachConsole(server.pid), 'Cannot inspect exact old private console')
        try:
            ids = (wintypes.DWORD * 64)(); count = kernel.GetConsoleProcessList(ids, 64)
            require(0 < count <= 64 and set(ids[:count]) == {server.pid, launcher.pid, os.getpid()}, 'Console ownership changed')
            members = list(ids[:count])
        finally:
            kernel.FreeConsole()
        idle(gate['source_directory']); children_checked()
        same(preflight['launcher'], meta); same(preflight['server'], meta)
        require(listener_released() and read(ROOT / '.oma/service.validated.json') == meta, 'Last pre-termination ownership check changed')
        request = {'status': 'VERIFIED_OWNED_IDLE_PROCESS_RECOVERY_REQUESTED', 'identities': identities, 'console_members': members,
                   'first_request_sha256': sha(evidence / 'shutdown-request.json'), 'second_request_sha256': sha(evidence / 'second-interrupt/request.json'),
                   'failed_second_wait_sha256': sha(evidence / 'second-interrupt/wait-result.json'),
                   'action': 'Terminate exact pinned server handle; wait15s. Wait15s for launcher exit, and only if still alive freshly verify and terminate exact pinned launcher handle. No descendant or other process termination.'}
        write(attempt / 'request.json', request)
        require(kernel.TerminateProcess(handles['server'], 1), 'Pinned server termination failed')
        require(kernel.WaitForSingleObject(handles['server'], 15000) == 0, 'Pinned server did not exit after termination')
        launcher_terminated = False
        launcher_wait = kernel.WaitForSingleObject(handles['launcher'], 15000)
        require(launcher_wait in (0, 258), 'Launcher wait failed')
        if launcher_wait == 258:
            launcher = same(preflight['launcher'], meta)
            idle(gate['source_directory'])
            children = launcher.children(recursive=True)
            require(all(Path(p.exe()).resolve() == Path(os.environ['SystemRoot'], 'System32/conhost.exe').resolve() and p.ppid() == launcher.pid and abs(p.create_time() - launcher.create_time()) < .25 for p in children) and len(children) <= 1, 'Unexpected remaining launcher descendant')
            require(listener_released(), 'Listener appeared before launcher recovery')
            write(attempt / 'launcher-termination-request.json', {'status': 'REVERIFIED_EXACT_LAUNCHER_RECOVERY_REQUESTED', 'identity': identities['launcher'], 'server_handle_already_signalled': True})
            require(kernel.TerminateProcess(handles['launcher'], 1), 'Pinned launcher termination failed')
            launcher_terminated = True
            require(kernel.WaitForSingleObject(handles['launcher'], 15000) == 0, 'Pinned launcher did not exit after termination')
        write(attempt / 'process-exit.json', {'server_handle_signalled': True, 'launcher_handle_signalled': True, 'server_terminated': True, 'launcher_terminated': launcher_terminated})
    finally:
        for handle in handles.values():
            kernel.CloseHandle(handle)
    require(listener_released(), 'Listener remains after process recovery')
    require(read(ROOT / '.oma/service.validated.json') == meta, 'Service metadata changed during recovery')
    sqlite_after = quick_check()
    after = store_inventory.snapshot()
    require(after == before == baseline, 'All-table/artifact/reachable Store invariants changed')
    idle(gate['source_directory'])
    for key in ('stdout', 'stderr'):
        shutil.copyfile(meta[key], evidence / ('closed-old-backend.' + key + '.log'))
        shutil.copyfile(meta[key], attempt / ('after-' + key + '.log'))
    result = {'status': 'FORCED_OWNED_IDLE_PROCESS_RECOVERY_COMPLETED', 'port_released': True, 'owned_processes_gone': True,
              'force_termination': True, 'graceful_application_lifespan_completed': False, 'second_ctrl_c': True,
              'store_before_after_exact': True, 'table_count': len(after['tables']), 'artifact_count': len(after['artifact_files']),
              'sqlite_quick_check_before': sqlite_before, 'sqlite_quick_check_after': sqlite_after,
              'server_terminated': True, 'launcher_terminated': launcher_terminated,
              'request_sha256': sha(attempt / 'request.json'), 'before_snapshot_sha256': sha(evidence / 'before-all-store.json'),
              'consistent_preflight_backup_sha256': sha(evidence / 'before-store.sqlite3'),
              'normal_lifespan_shutdown_claim': 'NOT_COMPLETED: two bounded interrupt attempts failed; exact idle owned process recovery was used',
              'disposition': 'Forced termination of only the verified idle old server, and launcher only if needed. No active native worker existed. Exact complete Store invariants and SQLite quick_check passed before/after. Both failed interrupt attempts remain retained.'}
    write(attempt / 'result.json', result)
    write(attempt / 'handoff.json', {'status': result['status'], 'retained_files': {p.name: sha(p) for p in attempt.iterdir() if p.is_file()}})
    write(evidence / 'shutdown-complete.json', result)
    print(json.dumps({'result': result, 'handoff': str(attempt / 'handoff.json'), 'sha256': sha(attempt / 'handoff.json')}))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--terminate-exact-owned-idle-processes', action='store_true')
    args = parser.parse_args()
    require(args.terminate_exact_owned_idle_processes, 'Explicit root execution flag required')
    execute(args.evidence)
