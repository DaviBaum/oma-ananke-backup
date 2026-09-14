"""Build a local preview bundle and test its independent Python runtime offline.

This is not a release-gate bypass. The package carries the incomplete capability
register and must not be published as a complete engineering release.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from oma.build_identity import checker_version, frozen_environment

NAME = "cpython-3.12.14+20260901-x86_64-pc-windows-msvc-install_only.tar.gz"
URL = "https://github.com/astral-sh/python-build-standalone/releases/download/20260901/" + NAME.replace("+", "%2B")
SHA256 = "e90c1b6419da3bd812dd73bb3de40287a21abf153438147639ec5e20375ea93f"


def main():
    release = ROOT / ".release"
    release.mkdir(exist_ok=True)
    archive = release / NAME
    if not archive.exists():
        with urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "OMA-local-build/0.1"}), timeout=60) as source, archive.open("wb") as target:
            shutil.copyfileobj(source, target)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise RuntimeError("Standalone Python artifact does not match upstream release SHA256")
    version = checker_version()
    frozen_sources = Path(frozen_environment(release / "build-inputs")["PYTHONPATH"])
    package = release / f"portable-preview-{version.rsplit(':', 1)[-1][:12]}"
    if package.exists():
        raise RuntimeError("Preview destination already exists; preserve it and use a new source build")
    package.mkdir()
    with tarfile.open(archive, "r:gz") as contents:
        contents.extractall(package, filter="data")
    extracted = (package / "python").resolve()
    runtime = (package / "runtime").resolve()
    if not extracted.is_relative_to(release.resolve()) or not runtime.is_relative_to(release.resolve()):
        raise RuntimeError("Runtime path escapes the build workspace")
    extracted.rename(runtime)
    wheels = release / "wheelhouse"
    subprocess.run([sys.executable, "-m", "pip", "install", "--no-index", "--no-deps", "--no-compile", "--upgrade",
                    "--find-links", str(wheels), "--target", str(runtime / "Lib" / "site-packages"),
                    "-r", str(ROOT / "requirements-runtime.lock")], check=True)
    shutil.copytree(frozen_sources, package / "src", ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"))
    shutil.copytree(ROOT / "ui" / "dist", package / "ui" / "dist")
    shutil.copytree(ROOT / "docs", package / "docs")
    shutil.copytree(ROOT / "evidence" / "dependencies", package / "evidence" / "dependencies")
    for name in ("OMA.cmd", "Start-OMA.ps1", "Install-OMA.ps1", "README.md", "requirements-runtime.lock"):
        shutil.copyfile(ROOT / name, package / name)
    (runtime / "Lib" / "site-packages" / "oma-workbench.pth").write_text("../../../src\n", encoding="utf-8")
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PIP_NO_INDEX"] = "1"
    executable = runtime / "python.exe"
    probe = "import sys,json,sqlite3,numpy,ifcopenshell,OCP,cupy,oma;from oma.build_identity import checker_version;print(json.dumps({'python':sys.version,'executable':sys.executable,'oma':oma.__file__,'sqlite':sqlite3.sqlite_version,'ifcopenshell':ifcopenshell.version,'cupy':cupy.__version__,'gpu_sum':float(cupy.arange(1000,dtype=cupy.float64).sum().get()),'checker_build':checker_version()}))"
    result = subprocess.run([str(executable), "-s", "-c", probe], env=environment, cwd=package, text=True, capture_output=True, timeout=120)
    record = {"status": "PREVIEW_NATIVE_PROBE_PASS" if result.returncode == 0 else "PREVIEW_NATIVE_PROBE_FAIL",
              "source_build": version, "package": str(package), "python_artifact": {"url": URL, "sha256": SHA256},
              "runtime_probe": json.loads(result.stdout) if result.returncode == 0 else {"stdout": result.stdout, "stderr": result.stderr},
              "runtime_model_dependency": "NONE", "runtime_node_dependency": "NONE", "runtime_network_dependency": "NONE",
              "production_release": "INCOMPLETE_GATES", "redistribution_notice_review": "PENDING"}
    (package / "package-manifest.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    (ROOT / "evidence" / "dependencies" / "portable-preview.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps(record, indent=2))
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
