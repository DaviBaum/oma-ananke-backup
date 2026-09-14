"""Retain the prior one-line Python-equality seam and corrected rejection."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
from oma.optimization import coupled_tree_univalence as current

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

directory = ROOT / 'evidence' / ('header-schema-' + uuid.uuid4().hex)
directory.mkdir(parents=True)
source = Path(current.__file__).read_text()
fixed = "if p._hash({k: packet[k] for k in header}, b) != p._hash(header, b):"
prior = "if any(packet[k] != v for k, v in header.items()):"
assert source.count(fixed) == 1
prior_path = directory / 'prior-draft-reconstructed.py'
prior_path.write_text(source.replace(fixed, prior))
old = load('oma.optimization.univalence_prior_header_guard', prior_path)
fixtures = load('univalence_test_helpers', ROOT / 'tests/test_coupled_tree_univalence.py')
model, _ = fixtures.example(1)
proof = current.compile_coupled_tree_univalence(model)
proof['polarization']['same_parameter_tuple'] = 1
fixtures.reroot(proof)
before = old.verify_coupled_tree_univalence(model, proof)
after = current.verify_coupled_tree_univalence(model, proof)
assert before['status'] == 'PASS' and after['status'] == 'FAIL'
for name, value in (('model.json', model), ('certificate.json', proof), ('prior-result.json', before), ('current-result.json', after)):
    (directory / name).write_text(json.dumps(value, indent=2) + '\n')
result = {'status': 'PRIOR_TYPED_SCHEMA_SEAM_REPRODUCED_AND_CURRENT_REJECTION_CONFIRMED',
          'prior_source': 'Prior draft reconstructed by restoring the exact single-line header comparison; this run actually executes that reconstruction.',
          'prior_source_sha256': hashlib.sha256(prior_path.read_bytes()).hexdigest(),
          'current_module_sha256': hashlib.sha256(Path(current.__file__).read_bytes()).hexdigest(),
          'scope': 'Boolean/int JSON schema substitution only; no different equilibrium theorem or native report was admitted.'}
(directory / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'status': result['status'], 'directory': str(directory)}))
