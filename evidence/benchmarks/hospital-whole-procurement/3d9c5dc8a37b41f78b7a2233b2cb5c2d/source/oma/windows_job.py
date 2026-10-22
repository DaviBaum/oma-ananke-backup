"""Windows checker containment established before its primary thread runs.

Uses documented Win32 APIs only. An unnamed, non-inheritable Job Object owns
CreateProcess descendants; neither breakaway flag is enabled. This is process
lifecycle containment, not a security sandbox against external broker services.
Non-Windows callers explicitly remain unsupported.
"""
from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
import math
import os
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import uuid


class ContainmentError(OSError):
    pass


def prepare_python_command(command, environment):
    """Use the loaded CPython bytes, never a broker-backed venv launcher.

    A private content-addressed interpreter copy keeps ``sys.executable`` safe
    for ordinary recursive subprocess launches. Original application/native
    packages are read from the original venv; its files are never changed.
    This local cache is integrity checked, not a hostile-user security boundary.
    """
    if not command or os.path.normcase(os.path.abspath(command[0])) != os.path.normcase(os.path.abspath(sys.executable)):
        raise ContainmentError("Supervised checks must use the current Python interpreter")
    kernel = _kernel()
    kernel.GetModuleFileNameW.argtypes = [W.HANDLE,W.LPWSTR,W.DWORD]
    kernel.GetModuleFileNameW.restype = W.DWORD
    buffer = C.create_unicode_buffer(32768)
    size = kernel.GetModuleFileNameW(None,buffer,len(buffer))
    if not size or size >= len(buffer):
        raise ContainmentError("Loaded Python image path is unavailable")
    image = Path(buffer.value)
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    if os.path.normcase(str(image.resolve())) == os.path.normcase(str(Path(sys.executable).resolve())):
        child_env = dict(environment)
        child_env.pop("__PYVENV_LAUNCHER__",None)
        return list(command),child_env,{"method":"DIRECT_LOADED_PYTHON_IMAGE", "path":str(image), "sha256":sha(image)}
    base = image.parent
    sources = {"Scripts/python.exe":image}
    sources.update({"Scripts/"+p.name:p for p in base.glob("*.dll")})
    if (base/"DLLs").is_dir():
        sources.update({"DLLs/"+str(p.relative_to(base/"DLLs")).replace("\\","/"):p
            for p in (base/"DLLs").rglob("*") if p.is_file()})
    if not any(Path(name).name.lower().startswith("python") and name.endswith(".dll") for name in sources):
        raise ContainmentError("Loaded Python DLL support could not be bound")
    cfg = "home = "+str(base)+"\ninclude-system-site-packages = false\nversion = "+sys.version.split()[0]+"\n"
    site_packages = Path(sys.prefix)/"Lib/site-packages"
    if not site_packages.is_dir():
        raise ContainmentError("Original virtual-environment package path is unavailable")
    # A nested frozen_environment intentionally replaces PYTHONPATH. Restore
    # the bridge's own standard-library extensions during ordinary site startup
    # before loading any original package .pth files. The relative prefix avoids
    # embedding the content-addressed directory's own hash in its input bytes.
    pth = "import sys, os, site; sys.path.insert(0, os.path.join(sys.prefix, 'DLLs')); site.addsitedir("+repr(str(site_packages))+")\n"
    texts = {"pyvenv.cfg":cfg,"Lib/site-packages/oma-original.pth":pth}
    inventory = {name:{"source":str(path),"sha256":sha(path)} for name,path in sorted(sources.items())}
    text_hashes = {name:hashlib.sha256(value.encode()).hexdigest() for name,value in texts.items()}
    binding = {"schema":"oma.direct-python-bridge/1","source_prefix":sys.prefix,"python_version":sys.version,
        "files":inventory,"generated_file_hashes":text_hashes}
    root = hashlib.sha256(json.dumps(binding,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    cache = Path(tempfile.gettempdir())/"oma-checker-python-v1"
    cache.mkdir(parents=True,exist_ok=True)
    target = cache/root
    if not target.exists():
        staging = cache/(root+"-"+uuid.uuid4().hex)
        staging.mkdir()
        try:
            for name,source in sources.items():
                output = staging/name;output.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(source,output)
            for name,value in texts.items():
                output = staging/name;output.parent.mkdir(parents=True,exist_ok=True)
                output.write_bytes(value.encode())
            (staging/"manifest.json").write_text(json.dumps(binding,sort_keys=True),encoding="utf-8")
            try:
                staging.rename(target)
            except FileExistsError:
                pass
        finally:
            if staging.exists():
                staging.resolve().relative_to(cache.resolve())
                shutil.rmtree(staging)
    for name,record in inventory.items():
        if sha(target/name) != record["sha256"] or sha(sources[name]) != record["sha256"]:
            raise ContainmentError("Private interpreter copy or source bytes changed")
    for name,expected in text_hashes.items():
        if sha(target/name) != expected:
            raise ContainmentError("Private interpreter configuration changed")
    if json.loads((target/"manifest.json").read_text(encoding="utf-8")) != binding:
        raise ContainmentError("Private interpreter manifest changed")
    actual_files = {p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()}
    if actual_files != set(inventory) | set(text_hashes) | {"manifest.json"}:
        raise ContainmentError("Private interpreter contains unexpected executable/configuration files")
    child_env = dict(environment)
    child_env.pop("__PYVENV_LAUNCHER__",None)
    child_env["PYTHONPATH"] = str(target/"DLLs") + (os.pathsep+child_env["PYTHONPATH"] if child_env.get("PYTHONPATH") else "")
    child_env["PATH"] = str(target/"Scripts") + os.pathsep + child_env.get("PATH","")
    return [str(target/"Scripts/python.exe"),*command[1:]],child_env,{"method":"BYTE_IDENTICAL_DIRECT_PYTHON_BRIDGE",
        "root":root,"directory":str(target),"binding":binding,"sys_prefix_scope":"Private bridge; original venv site-packages",
        "frozen_pythonpath_retained":environment.get("PYTHONPATH")}


class _STARTUPINFO(C.Structure):
    _fields_ = [("cb",W.DWORD),("lpReserved",W.LPWSTR),("lpDesktop",W.LPWSTR),("lpTitle",W.LPWSTR),
        *[(name,W.DWORD) for name in ("dwX","dwY","dwXSize","dwYSize","dwXCountChars","dwYCountChars","dwFillAttribute","dwFlags")],
        ("wShowWindow",W.WORD),("cbReserved2",W.WORD),("lpReserved2",C.c_void_p),
        ("hStdInput",W.HANDLE),("hStdOutput",W.HANDLE),("hStdError",W.HANDLE)]


class _STARTUPINFOEX(C.Structure):
    _fields_ = [("StartupInfo",_STARTUPINFO),("lpAttributeList",C.c_void_p)]


class _PROCESS_INFORMATION(C.Structure):
    _fields_ = [("hProcess",W.HANDLE),("hThread",W.HANDLE),("dwProcessId",W.DWORD),("dwThreadId",W.DWORD)]


class _BASIC_LIMIT(C.Structure):
    _fields_ = [("PerProcessUserTimeLimit",C.c_longlong),("PerJobUserTimeLimit",C.c_longlong),("LimitFlags",W.DWORD),
        ("MinimumWorkingSetSize",C.c_size_t),("MaximumWorkingSetSize",C.c_size_t),("ActiveProcessLimit",W.DWORD),
        ("Affinity",C.c_size_t),("PriorityClass",W.DWORD),("SchedulingClass",W.DWORD)]


class _IO_COUNTERS(C.Structure):
    _fields_ = [(name,C.c_ulonglong) for name in ("ReadOperationCount","WriteOperationCount","OtherOperationCount",
        "ReadTransferCount","WriteTransferCount","OtherTransferCount")]


class _EXTENDED_LIMIT(C.Structure):
    _fields_ = [("BasicLimitInformation",_BASIC_LIMIT),("IoInfo",_IO_COUNTERS),
        *[(name,C.c_size_t) for name in ("ProcessMemoryLimit","JobMemoryLimit","PeakProcessMemoryUsed","PeakJobMemoryUsed")]]


class _ACCOUNTING(C.Structure):
    _fields_ = [(name,C.c_longlong) for name in ("TotalUserTime","TotalKernelTime","ThisPeriodTotalUserTime","ThisPeriodTotalKernelTime")]
    _fields_ += [(name,W.DWORD) for name in ("TotalPageFaultCount","TotalProcesses","ActiveProcesses","TotalTerminatedProcesses")]


def _kernel():
    if os.name != "nt":
        raise ContainmentError("Windows Job Object containment is unavailable on this operating system")
    kernel = C.WinDLL("kernel32",use_last_error=True)
    signatures = {
        "CreateJobObjectW":([C.c_void_p,W.LPCWSTR],W.HANDLE),
        "SetInformationJobObject":([W.HANDLE,C.c_int,C.c_void_p,W.DWORD],W.BOOL),
        "QueryInformationJobObject":([W.HANDLE,C.c_int,C.c_void_p,W.DWORD,C.c_void_p],W.BOOL),
        "AssignProcessToJobObject":([W.HANDLE,W.HANDLE],W.BOOL),
        "IsProcessInJob":([W.HANDLE,W.HANDLE,C.POINTER(W.BOOL)],W.BOOL),
        "TerminateJobObject":([W.HANDLE,W.UINT],W.BOOL),
        "InitializeProcThreadAttributeList":([C.c_void_p,W.DWORD,W.DWORD,C.POINTER(C.c_size_t)],W.BOOL),
        "UpdateProcThreadAttribute":([C.c_void_p,W.DWORD,C.c_size_t,C.c_void_p,C.c_size_t,C.c_void_p,C.c_void_p],W.BOOL),
        "DeleteProcThreadAttributeList":([C.c_void_p],None),
        "CreateProcessW":([W.LPCWSTR,W.LPWSTR,C.c_void_p,C.c_void_p,W.BOOL,W.DWORD,C.c_void_p,W.LPCWSTR,
            C.c_void_p,C.POINTER(_PROCESS_INFORMATION)],W.BOOL),
        "ResumeThread":([W.HANDLE],W.DWORD),
        "WaitForSingleObject":([W.HANDLE,W.DWORD],W.DWORD),
        "GetExitCodeProcess":([W.HANDLE,C.POINTER(W.DWORD)],W.BOOL),
        "TerminateProcess":([W.HANDLE,W.UINT],W.BOOL),
        "CloseHandle":([W.HANDLE],W.BOOL),
    }
    for name,(arguments,result) in signatures.items():
        function=getattr(kernel,name)
        function.argtypes=arguments
        function.restype=result
    return kernel


def _required(value, operation):
    if not value:
        code=C.get_last_error()
        raise ContainmentError(code, f"{operation}: {C.FormatError(code).strip()}")
    return value


class WindowsJobProcess:
    """Small Popen-compatible child handle with authoritative job accounting."""

    def __init__(self, command, *, environment):
        self.api=_kernel()
        self.args=list(map(str,command))
        if not self.args or any("\0" in item for item in self.args):
            raise ValueError("A nonempty NUL-free checker command is required")
        self.job=self.handle=self.thread=None
        self.stdout=self.stderr=None
        self.pid=None
        self.returncode=None
        self.assigned=False
        self.resumed=False
        descriptors=[]
        attribute_initialized=False
        attribute=None
        try:
            import msvcrt
            self.job=_required(self.api.CreateJobObjectW(None,None),"CreateJobObjectW")
            limits=_EXTENDED_LIMIT()
            limits.BasicLimitInformation.LimitFlags=0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            _required(self.api.SetInformationJobObject(self.job,9,C.byref(limits),C.sizeof(limits)),"SetInformationJobObject")
            reads=[]
            writes=[]
            for _ in range(2):
                read,write=os.pipe()
                descriptors.extend((read,write));reads.append(read);writes.append(write)
            stdin=os.open(os.devnull,os.O_RDONLY)
            descriptors.append(stdin)
            handles=(W.HANDLE*3)(*(msvcrt.get_osfhandle(fd) for fd in (stdin,*writes)))
            for handle in handles:
                os.set_handle_inheritable(handle,True)
            size=C.c_size_t()
            self.api.InitializeProcThreadAttributeList(None,1,0,C.byref(size))
            if not size.value:
                raise ContainmentError("Attribute-list allocation size unavailable")
            attribute=C.create_string_buffer(size.value)
            _required(self.api.InitializeProcThreadAttributeList(attribute,1,0,C.byref(size)),"InitializeProcThreadAttributeList")
            attribute_initialized=True
            # No job/process/thread handle is inherited. Only the three standard
            # streams are on this explicit handle allowlist.
            _required(self.api.UpdateProcThreadAttribute(attribute,0,0x00020002,C.cast(handles,C.c_void_p),
                C.sizeof(handles),None,None),"UpdateProcThreadAttribute(HANDLE_LIST)")
            startup=_STARTUPINFOEX()
            startup.StartupInfo.cb=C.sizeof(startup)
            startup.StartupInfo.dwFlags=0x00000100  # STARTF_USESTDHANDLES
            startup.StartupInfo.hStdInput,startup.StartupInfo.hStdOutput,startup.StartupInfo.hStdError=handles
            startup.lpAttributeList=C.cast(attribute,C.c_void_p)
            rows=[]
            for key,value in sorted(environment.items(),key=lambda item:item[0].upper()):
                if not isinstance(key,str) or not isinstance(value,str) or "\0" in key+value or "=" in key or not key:
                    raise ValueError("Invalid explicit child environment")
                rows.append(key+"="+value)
            env=C.create_unicode_buffer("\0".join(rows)+"\0\0")
            line=C.create_unicode_buffer(subprocess.list2cmdline(self.args))
            info=_PROCESS_INFORMATION()
            flags=0x00000004 | 0x08000000 | 0x00000400 | 0x00080000
            _required(self.api.CreateProcessW(self.args[0],line,None,None,True,flags,env,None,
                C.byref(startup),C.byref(info)),"CreateProcessW(CREATE_SUSPENDED)")
            self.handle,self.thread,self.pid=info.hProcess,info.hThread,info.dwProcessId
            _required(self.api.AssignProcessToJobObject(self.job,self.handle),"AssignProcessToJobObject before resume")
            member=W.BOOL()
            _required(self.api.IsProcessInJob(self.handle,self.job,C.byref(member)),"IsProcessInJob")
            if not member.value:
                raise ContainmentError("Created checker is not associated with its owned job")
            self.assigned=True
            if self.accounting()["active_processes"] != 1:
                raise ContainmentError("Unexpected job membership before primary-thread resume")
            self.stdout=os.fdopen(reads[0],"rb",buffering=0);descriptors.remove(reads[0])
            self.stderr=os.fdopen(reads[1],"rb",buffering=0);descriptors.remove(reads[1])
            previous=self.api.ResumeThread(self.thread)
            if previous != 1:
                raise ContainmentError(f"Primary-thread resume did not discharge exactly one suspension: {previous}")
            self.resumed=True
        except BaseException:
            # Assignment failure must never resume Python. The explicit process
            # handle is owned even when it never became a job member.
            if self.handle:
                self.api.TerminateProcess(self.handle,1)
            if self.job:
                self.api.TerminateJobObject(self.job,1)
            if self.handle:
                self.api.WaitForSingleObject(self.handle,2000)
            self.close()
            raise
        finally:
            if attribute_initialized:
                self.api.DeleteProcThreadAttributeList(attribute)
            if self.thread:
                self.api.CloseHandle(self.thread);self.thread=None
            for fd in descriptors:
                os.close(fd)

    def accounting(self):
        info=_ACCOUNTING()
        _required(self.api.QueryInformationJobObject(self.job,1,C.byref(info),C.sizeof(info),None),"QueryInformationJobObject(ACCOUNTING)")
        limits=_EXTENDED_LIMIT()
        _required(self.api.QueryInformationJobObject(self.job,9,C.byref(limits),C.sizeof(limits),None),"QueryInformationJobObject(EXTENDED_LIMIT)")
        return {"active_processes":int(info.ActiveProcesses),"total_processes":int(info.TotalProcesses),
            "terminated_processes":int(info.TotalTerminatedProcesses),"peak_job_committed_bytes":int(limits.PeakJobMemoryUsed)}

    def process_ids(self):
        # The kernel list includes children even after their parent has exited.
        capacity=64
        while capacity<=65536:
            class ProcessList(C.Structure):
                _fields_=[("assigned",W.DWORD),("listed",W.DWORD),("pids",C.c_size_t*capacity)]
            info=ProcessList()
            if self.api.QueryInformationJobObject(self.job,3,C.byref(info),C.sizeof(info),None):
                if info.listed>capacity:
                    raise ContainmentError("Invalid job process-list size")
                return list(info.pids[:info.listed])
            code=C.get_last_error()
            if code!=234:  # ERROR_MORE_DATA: processes may have arrived meanwhile.
                raise ContainmentError(code,"QueryInformationJobObject(PROCESS_LIST) failed")
            capacity=max(capacity*2,int(info.assigned)+16)
        raise ContainmentError("Job process inventory exceeded its inspection bound")

    def poll(self):
        if self.returncode is not None:
            return self.returncode
        status=self.api.WaitForSingleObject(self.handle,0)
        if status==258:
            return None
        if status!=0:
            raise ContainmentError("Checker process wait failed")
        code=W.DWORD()
        _required(self.api.GetExitCodeProcess(self.handle,C.byref(code)),"GetExitCodeProcess")
        self.returncode=int(code.value)
        return self.returncode

    def wait(self, timeout=None):
        milliseconds=0xFFFFFFFF if timeout is None else min(0xFFFFFFFE,max(0,math.ceil(timeout*1000)))
        status=self.api.WaitForSingleObject(self.handle,milliseconds)
        if status==258:
            raise subprocess.TimeoutExpired(self.args,timeout)
        if status!=0:
            raise ContainmentError("Checker process wait failed")
        return self.poll()

    def terminate(self):
        _required(self.api.TerminateJobObject(self.job,1),"TerminateJobObject")

    def close(self, *, close_streams=True):
        # Kill-on-close is a final ownership backstop if explicit termination or
        # accounting failed. No handle to an unrelated process is signalled.
        for name in ("job","thread","handle"):
            handle=getattr(self,name,None)
            if handle:
                self.api.CloseHandle(handle);setattr(self,name,None)
        for stream in ((self.stdout,self.stderr) if close_streams else ()):
            if stream is not None and not stream.closed:
                stream.close()
