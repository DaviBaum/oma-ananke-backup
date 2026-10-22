"""Measured workstation diagnostics and conservative job admission."""
from __future__ import annotations

import importlib.metadata
import json
import platform
import shutil
import subprocess
import threading
import time
from pathlib import Path

import psutil

GiB = 1024 ** 3
_cache: tuple[float, dict] = (0, {})
_lock = threading.Lock()


def diagnose(directory: str | Path = ".", refresh: bool = False) -> dict:
    global _cache
    with _lock:
        if not refresh and time.monotonic() - _cache[0] < 2:
            return _cache[1].copy()
        memory = psutil.virtual_memory()
        gpu = None
        gpu_error = None
        if shutil.which("nvidia-smi"):
            try:
                result = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu,driver_version", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=3, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=True)
                values = result.stdout.splitlines()[0].split(",")
                gpu = {"name": values[0].strip(), "memory_total_bytes": int(values[1]) * 1024 ** 2,
                       "memory_used_bytes": int(values[2]) * 1024 ** 2, "memory_free_bytes": int(values[3]) * 1024 ** 2,
                       "utilization_percent": int(values[4]), "driver": values[5].strip()}
            except (OSError, ValueError, subprocess.SubprocessError, IndexError) as exc:
                gpu_error = str(exc)
        versions = {}
        for package in ("ifcopenshell", "numpy", "scipy", "fastapi", "pydantic", "cupy-cuda12x", "manifold3d"):
            try:
                versions[package] = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                versions[package] = None
        total, used, free = shutil.disk_usage(Path(directory).resolve())
        result = {"os": platform.platform(), "python": platform.python_version(), "cpu": platform.processor(),
                  "physical_cores": psutil.cpu_count(logical=False), "logical_cores": psutil.cpu_count(),
                  "cpu_percent": psutil.cpu_percent(), "ram_total_bytes": memory.total,
                  "ram_available_bytes": memory.available, "ram_used_bytes": memory.used,
                  "process_rss_bytes": psutil.Process().memory_info().rss,
                  "gpu": gpu, "gpu_error": gpu_error, "cuda_toolkit": shutil.which("nvcc"),
                  "disk_total_bytes": total, "disk_free_bytes": free, "versions": versions,
                  "resource_policy": {"application_ram_limit_bytes": min(96 * GiB, int(memory.total * .75)),
                                      "gpu_compute_limit_bytes": min(18 * GiB, max(0, (gpu or {}).get("memory_free_bytes", 0) - 3 * GiB)),
                                      "max_parallel_geometry_workers": 2, "threads_per_geometry_worker": 4,
                                      "disk_reserve_bytes": 30 * GiB}}
        _cache = (time.monotonic(), result)
        return result.copy()


class ResourceBroker:
    def __init__(self, directory: str | Path, max_workers: int = 2):
        self.directory = Path(directory)
        self.semaphore = threading.BoundedSemaphore(max_workers)

    def admit(self, estimated_ram_bytes: int = 1 * GiB, estimated_disk_bytes: int = 0):
        health = diagnose(self.directory)
        if health["ram_available_bytes"] < estimated_ram_bytes + 4 * GiB:
            raise MemoryError("Insufficient available RAM for bounded job; close other applications or reduce job scope")
        if health["disk_free_bytes"] < estimated_disk_bytes + health["resource_policy"]["disk_reserve_bytes"]:
            raise OSError("Disk reserve would be exceeded; archive derived caches before retrying")
        return self.semaphore
