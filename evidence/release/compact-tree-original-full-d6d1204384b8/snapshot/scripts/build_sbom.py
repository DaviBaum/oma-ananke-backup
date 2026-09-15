"""Inventory the exact installed distribution metadata and license texts."""
from pathlib import Path
import hashlib
import importlib.metadata as metadata
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from oma.store import utcnow

ROLES = {
    "ifcopenshell": ("IFC parsing, geometry conversion, authoring", "LGPL distribution obligations must be satisfied for packaged binaries; source and license correspondence retained", "tests/test_ifc_pipeline.py; tests/test_ifc_cad.py", "Missing/unsupported representations block applicable physical checks"),
    "cadquery-ocp": ("Independent native CAD Boolean, distance and topology checking", "OpenCASCADE and binding license texts require binary/source-notice review", "tests/test_ifc_cad.py; tests/test_route_adversarial.py", "Invalid/ambiguous kernel outputs never grant a physical PASS"),
    "scipy": ("HiGHS restricted LP proposals", "Retain SciPy and bundled solver notices", "tests/test_optimization_master.py", "Exact rational/finite checker disposes numeric proposals; no numeric status trusted as proof"),
    "cupy-cuda12x": ("RTX 3090 bounded spatial broad phase", "Retain CuPy/bundled notices; NVIDIA driver/toolkit supplied separately", "tests/test_broadphase.py; evidence/benchmarks/gpu-broadphase-first.json", "CPU reference fallback; no safety predicate weakened"),
    "numpy": ("Typed geometry arrays and CPU spatial processing", "Retain package/bundled numerical-library notices", "tests/test_broadphase.py", "Nonfinite input and invalid bounds rejected"),
    "fastapi": ("Loopback application HTTP API", "Retain license notice", "tests/test_api.py", "Explicit errors, no remote binding by default"),
    "pydantic": ("Typed unit-explicit engineering and request schemas", "Retain license notice", "tests/test_store.py; tests/test_routing_integration.py", "Missing/invalid fields rejected"),
    "huggingface-hub": ("Supported immutable public dataset acquisition only", "Client license is separate from every acquired model license", "scripts/ifc_acquire.py and evidence/ifc acquisition records", "No runtime connection required after acquisition"),
}


def build():
    out = ROOT / "evidence" / "dependencies"
    out.mkdir(parents=True, exist_ok=True)
    distributions = []
    for dist in sorted(metadata.distributions(), key=lambda d: d.metadata.get("Name", "").lower()):
        name = dist.metadata.get("Name", "unknown")
        if name == "oma-ananke":
            continue
        role, implications, tested, failure = ROLES.get(name.lower(), ("Transitive or development dependency", "Read and preserve included package license terms", "Covered through dependent integration tests; no independent capability claim", "Inherited dependency capability gate"))
        license_texts = []
        for file in dist.files or []:
            if "license" in file.name.lower() or "copying" in file.name.lower() or "notice" in file.name.lower():
                path = Path(dist.locate_file(file))
                if path.is_file() and path.stat().st_size < 2 * 1024**2:
                    raw = path.read_bytes()
                    target = out / "licenses" / name / str(file).replace("/", "_").replace("\\", "_")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(raw)
                    license_texts.append({"path": str(target.relative_to(ROOT)), "sha256": hashlib.sha256(raw).hexdigest()})
        distributions.append({"name": name, "version": dist.version, "role": role,
            "license_expression": dist.metadata.get("License-Expression"), "declared_license": dist.metadata.get("License"),
            "project_urls": dist.metadata.get_all("Project-URL") or [], "requires": dist.requires or [],
            "license_artifacts": license_texts, "redistribution_implications": implications,
            "tested_api_evidence": tested, "failure_and_fallback": failure})
    report = {"schema_version": 1, "generated_at": utcnow(), "python_distributions": distributions,
        "frontend_lock": "ui/package-lock.json", "frontend_license_review": "PENDING",
        "data_license_inventory": "evidence/ifc; project-specific licenses retained in data/ifc-bench",
        "application_distribution_gate": "PENDING_SOURCE_NOTICE_AND_FRONTEND_REVIEW",
        "notice": "Installed metadata is an inventory, not a declaration that all redistribution obligations are complete"}
    (out / "sbom.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"distributions": len(distributions), "output": str(out / "sbom.json")}))


if __name__ == "__main__":
    build()
