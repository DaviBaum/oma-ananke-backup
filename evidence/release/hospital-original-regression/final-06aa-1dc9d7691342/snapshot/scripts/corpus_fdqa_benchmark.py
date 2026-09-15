"""Reproduce the original Pages P2 finite hotel example, explicitly synthetic."""
from pathlib import Path
import hashlib
import json
import runpy
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from oma.optimization.fdqa import compile_fdqa, verify_fdqa


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    files = [ROOT / "src/oma/optimization/fdqa.py", ROOT / "src/oma/optimization/finite.py",
             ROOT / "src/oma/dependencies.py", ROOT / "tests/test_optimization_fdqa.py", Path(__file__)]
    before = {str(p.relative_to(ROOT)):sha(p) for p in files}
    fixture = runpy.run_path(str(ROOT / "tests/test_optimization_fdqa.py"))["hotel_model"]
    carriers, operations, outputs = fixture()
    context = "original-pages-1-10-p2:table1736215:synthetic-hotel-v1"
    started = perf_counter()
    certificate = compile_fdqa(carriers, operations, outputs, context_root=context)
    compiled = perf_counter()
    checked = verify_fdqa(carriers, operations, outputs, certificate, context_root=context)
    ended = perf_counter()
    assert checked["status"] == "PASS"
    assert before == {str(p.relative_to(ROOT)):sha(p) for p in files}
    dest = ROOT / "evidence/math"
    certificate_path = dest / "original-fdqa-hotel-certificate.json"
    certificate_path.write_text(json.dumps(certificate, indent=2)+"\n", encoding="utf8")
    result = {
        "schema":"oma.original.fdqa.synthetic-benchmark/1",
        "source":{"document":"1-10.pages", "sha256":"0ad4cd0c72cdb8fac573b3bfd262d86d9580a8218a98657c828b01eaba92d970",
                  "paragraphs":[6616,6918], "native_pattern_table":1736215},
        "scope":"EXPLICIT_SYNTHETIC_SOURCE_TABLE; NOT REAL IFC OR PHYSICAL VALIDATION",
        "interpretation":"Named binary assignment fields and complete native 12-row pattern table; no reconstruction of damaged inline equations or disordered source tuples.",
        "states":len(certificate["states"]), "blocks":len(certificate["blocks"]),
        "refinement_counts":certificate["refinement_counts"],
        "strict_refinement_rounds":certificate["strict_refinement_rounds"],
        "independent_check":checked, "compiler_seconds":compiled-started, "checker_seconds":ended-compiled,
        "certificate":str(certificate_path.relative_to(ROOT)), "certificate_sha256":sha(certificate_path),
        "implementation_sha256":before,
        "limitations":["No complete physical application adapter", "No measured large-building compression", "No physical model validity", "No continuous or unlisted context completeness"],
    }
    path = dest / "original-fdqa-hotel-benchmark.json"
    path.write_text(json.dumps(result,indent=2)+"\n",encoding="utf8")
    print(json.dumps(result,indent=2))


if __name__ == "__main__":
    main()
