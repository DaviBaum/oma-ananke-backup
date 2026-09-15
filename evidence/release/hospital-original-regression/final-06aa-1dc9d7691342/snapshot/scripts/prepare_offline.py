"""Lock and acquire the runtime dependency closure for a Windows offline install.

Development-only corpus readers and test tools are excluded. Every runtime pin
comes from the tested environment; no resolver upgrades are permitted here.
"""
from __future__ import annotations

import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import subprocess
import sys
import tomllib

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]


def runtime_closure():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    queue = project["project"]["dependencies"] + project["build-system"]["requires"] + ["wheel", "pip"]
    found = {}
    while queue:
        req = Requirement(queue.pop())
        if req.marker and not req.marker.evaluate({"extra": ""}):
            continue
        name = canonicalize_name(req.name)
        if name in found:
            continue
        dist = metadata.distribution(name)
        if req.specifier and dist.version not in req.specifier:
            raise RuntimeError(f"Installed {name} {dist.version} violates {req}")
        found[name] = dist.version
        queue.extend(dist.requires or [])
    return found


def main():
    packages = runtime_closure()
    lock = ROOT / "requirements-runtime.lock"
    lock.write_text("\n".join(f"{name}=={version}" for name, version in sorted(packages.items())) + "\n", encoding="utf-8")
    wheelhouse = ROOT / ".release" / "wheelhouse"
    wheelhouse.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "pip", "download", "--only-binary=:all:", "--no-deps", "-r", str(lock), "-d", str(wheelhouse)], check=True)
    wheels = []
    for path in sorted(wheelhouse.glob("*.whl")):
        h = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(4*1024**2), b""):
                h.update(chunk)
        wheels.append({"name": path.name, "size_bytes": path.stat().st_size, "sha256": h.hexdigest()})
    report = {"target": "Windows CPython3.12 x86_64", "packages": packages, "wheels": wheels,
              "runtime_excludes_development_tools": [name for name in ("pymupdf", "pytest", "python-docx") if name not in packages],
              "source_notice_review": "PENDING", "fresh_offline_install": "NOT_RUN"}
    out = ROOT / "evidence" / "dependencies" / "offline-wheelhouse.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"packages": len(packages), "wheels": len(wheels), "bytes": sum(w["size_bytes"] for w in wheels)}))


if __name__ == "__main__":
    main()
