"""Measured original P4 symbolic fixture under an explicit total interpretation."""
import hashlib
import json
from pathlib import Path
import runpy
import time

from oma.optimization.symbolic import compile_symbolic, verify_symbolic


ROOT = Path(__file__).resolve().parents[1]
scope = 'original-pages-p4-forty-xor-modules-fixed-width-activation-v1'
paths = [ROOT/'src/oma/optimization'/name for name in ('symbolic.py', 'fdqa.py', 'finite.py')]
before = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
fixture = runpy.run_path(str(ROOT/'tests/test_optimization_symbolic.py'))
started = time.perf_counter()
theory = fixture['forty_module_model']()
preparation = time.perf_counter() - started
started = time.perf_counter()
certificate = compile_symbolic(theory, context_root=scope)
compile_time = time.perf_counter() - started
started = time.perf_counter()
verification = verify_symbolic(theory, certificate, context_root=scope)
check_time = time.perf_counter() - started
assert verification['status'] == 'PASS'
assert certificate['domain_count'] == 2**40 and len(certificate['blocks']) == 5
assert certificate['metrics']['accepted_binary_splits'] == 3
after = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
assert before == after, 'Implementation changed during benchmark'
encoded = (json.dumps(certificate, sort_keys=True, separators=(',', ':'))+'\n').encode('utf8')
artifact = ROOT/'evidence/math/original-symbolic-forty-module-certificate.json'
artifact.write_bytes(encoded)
report = {
    'status': 'PASS', 'source_sha256': '0ad4cd0c72cdb8fac573b3bfd262d86d9580a8218a98657c828b01eaba92d970',
    'source_ranges': ['1-10:P10006-P12808', '1-10:P12104-P12187'],
    'source_objects': ['ALG-AB1', 'ALG-AB4', 'THM-AB10', 'THM-AB22', 'DEF-AB35'],
    'scope': 'Synthetic exact Boolean theory: 40 XOR-constrained module pairs; saturated count at four',
    'context_interpretation': 'Activate the first inactive module and preserve each a XOR b = 1; identity if all modules are active. A total fixed-width map, not literal append or a physical design alteration.',
    'source_amendments': ['A030: three accepted binary splits from two initial blocks to five final blocks',
                          'A031: explicitly total fixed-width activation replaces undefined literal append semantics'],
    'not_claimed': ['Physical model adequacy', 'Complete real-building symbolic physics', 'Arbitrary compact SAT or SMT tractability', 'Measured speedup against enumeration of the trillion assignments'],
    'variables': len(theory.variables), 'input_circuit_gates': len(theory.gates),
    'represented_assignments': certificate['domain_count'],
    'final_blocks': len(certificate['blocks']), 'block_counts': sorted(row['count'] for row in certificate['blocks']),
    'compiler_metrics': certificate['metrics'], 'independent_checker': verification,
    'timings_seconds': {'input_circuit_construction': preparation, 'symbolic_compilation': compile_time, 'independent_check': check_time},
    'implementation_sha256': before, 'certificate': str(artifact.relative_to(ROOT)),
    'certificate_sha256': hashlib.sha256(encoded).hexdigest(), 'certificate_bytes': len(encoded),
    'validation': 'Focused tests independently enumerate all small XOR assignments and all paired residual behaviors in 18 random three-variable context theories; neither production compiler nor checker enumerates the concrete carrier.',
}
(ROOT/'evidence/math/original-symbolic-forty-module-benchmark.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
print(json.dumps(report, indent=2))
