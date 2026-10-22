"""Bind engineering evidence to the executable Python source and native versions."""
from __future__ import annotations

import hashlib
import importlib.metadata
import os
import shutil
import sys
import uuid
from pathlib import Path


def checker_version() -> str:
    root = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    digest.update(sys.version.encode())
    for path in sorted(root.rglob("*.py")):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    for package in ("ifcopenshell", "cadquery-ocp", "numpy", "scipy", "pydantic", "cupy-cuda12x"):
        try:
            version = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            version = "absent"
        digest.update(f"{package}={version}\0".encode())
    return "oma-independent-checker/2:" + digest.hexdigest()


def frozen_environment(directory: str | Path) -> dict[str, str]:
    """Give each child checker an immutable executable snapshot, not live edits."""
    source = Path(__file__).resolve().parent
    version = checker_version()
    runtimes = Path(directory) / "runtimes"
    destination = runtimes / version.rsplit(":", 1)[-1]
    complete = destination / "build-version.txt"
    if not complete.exists():
        temporary = runtimes / f".pending-{uuid.uuid4().hex}"
        target = temporary / "src" / "oma"
        target.mkdir(parents=True, exist_ok=False)
        for path in source.rglob("*.py"):
            copied = target / path.relative_to(source)
            copied.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, copied)
        # A mutation during the copy is not a coherent executable build.
        if checker_version() != version:
            raise RuntimeError("Source changed while snapshotting checker; retry on a stable build")
        (temporary / "build-version.txt").write_text(version, encoding="ascii")
        try:
            temporary.rename(destination)
        except FileExistsError:
            if not complete.exists() or complete.read_text(encoding="ascii") != version:
                raise
    # A prior executable snapshot is checked byte-for-byte before reusing it.
    for path in source.rglob("*.py"):
        if (destination / "src" / "oma" / path.relative_to(source)).read_bytes() != path.read_bytes():
            raise RuntimeError("Immutable checker runtime was modified")
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(destination / "src")
    environment["OMA_EXECUTABLE_BUILD"] = version
    return environment
