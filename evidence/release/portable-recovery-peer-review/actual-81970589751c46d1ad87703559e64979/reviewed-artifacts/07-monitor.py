"""Continue bounded observation of the existing pytest process; never rerun it."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import time
import psutil
import ctypes
from ctypes import wintypes

directory = Path(__file__).resolve().parent
record_path = directory / 'command-running.json'
original = json.loads(record_path.read_text())
process = psutil.Process(original['pid'])
assert process.cmdline() == original['command']
assert Path(process.cwd()).resolve() == Path(original['cwd']).resolve()
started = datetime.fromisoformat(original['started_utc']).timestamp()
assert abs(process.create_time() - started) < 5
kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
kernel.OpenProcess.restype = wintypes.HANDLE
kernel.GetProcessId.argtypes = (wintypes.HANDLE,)
kernel.GetProcessId.restype = wintypes.DWORD
kernel.GetProcessTimes.argtypes = (wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4))
kernel.GetProcessTimes.restype = wintypes.BOOL
kernel.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
kernel.WaitForSingleObject.restype = wintypes.DWORD
kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
kernel.GetExitCodeProcess.restype = wintypes.BOOL
kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
kernel.CloseHandle.restype = wintypes.BOOL
handle = kernel.OpenProcess(0x00100000 | 0x1000, False, process.pid)
assert handle, ctypes.get_last_error()
assert kernel.GetProcessId(handle) == process.pid
times = [wintypes.FILETIME() for _ in range(4)]
assert kernel.GetProcessTimes(handle, *(ctypes.byref(value) for value in times))
handle_creation = ((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime) / 10_000_000 - 11644473600
assert abs(handle_creation - process.create_time()) < .00001
image = ctypes.create_unicode_buffer(32768)
size = wintypes.DWORD(len(image))
assert kernel.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(size))
assert Path(image.value).resolve() == Path(original['command'][0]).resolve()
assert process.cmdline() == original['command'] and process.create_time() == psutil.Process(process.pid).create_time()
deadline = started + original['budget_seconds']
record = {'status': 'MONITORING_EXISTING_PROCESS', 'pid': process.pid,
          'creation_time': process.create_time(), 'command': process.cmdline(),
          'cwd': process.cwd(), 'original_command_record_sha256': hashlib.sha256(record_path.read_bytes()).hexdigest(),
          'original_started_utc': original['started_utc'], 'original_budget_seconds': original['budget_seconds'],
          'monitor_started_utc': datetime.now(timezone.utc).isoformat(),
          'monitor_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'retained_process_handle': True, 'handle_pid': kernel.GetProcessId(handle),
          'handle_creation_time': handle_creation, 'handle_executable': image.value,
          'tests_restarted': False, 'peak_observed_rss_bytes': 0,
          'scope': 'Parent wrapper interruption retained; current child PID/creation/command/cwd independently matched. No observation claimed for the gap before this monitor.'}
output = directory / 'monitor-result.json'
owned = {}
last = 0
def write():
    output.write_text(json.dumps(record, indent=2) + '\n')
write()
try:
    while True:
        wait_status = kernel.WaitForSingleObject(handle, 500)
        assert wait_status in (0, 0x102), (wait_status, ctypes.get_last_error())
        if wait_status == 0:
            exit_code = wintypes.DWORD()
            assert kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            record.update(status='EXISTING_PROCESS_EXIT_OBSERVED', exit_code=exit_code.value)
            break
        descendants = process.children(recursive=True)
        for child in descendants:
            owned[child.pid] = child
        rss = 0
        for current in [process, *descendants]:
            try:
                rss += current.memory_info().rss
            except psutil.NoSuchProcess:
                pass
        record['peak_observed_rss_bytes'] = max(record['peak_observed_rss_bytes'], rss)
        elapsed = time.time() - started
        record['elapsed_since_original_start_seconds'] = elapsed
        cancel = Path(original['cancel_file']).exists()
        if time.time() >= deadline or rss > 48 * 1024**3 or cancel:
            record['status'] = 'EXISTING_PROCESS_LIMIT_STOP'
            record['reason'] = 'cancel' if cancel else 'deadline' if time.time() >= deadline else 'memory'
            for child in reversed(list(owned.values())):
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            process.kill()
            record['exit_code'] = process.wait(timeout=10)
            break
        if time.monotonic() - last >= 30:
            last = time.monotonic()
            write()
            print(json.dumps({'status': record['status'], 'elapsed_seconds': elapsed, 'rss_bytes': rss}), flush=True)
except BaseException as error:
    record.update(status='MONITOR_INCOMPLETE', error=repr(error))
    raise
finally:
    kernel.CloseHandle(handle)
    record['completed_utc'] = datetime.now(timezone.utc).isoformat()
    write()
    print(json.dumps(record), flush=True)
