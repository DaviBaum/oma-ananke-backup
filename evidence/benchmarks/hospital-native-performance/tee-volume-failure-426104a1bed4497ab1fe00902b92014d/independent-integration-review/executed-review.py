"""Independent read-only arithmetic/API/cache review; no native geometry run."""
from pathlib import Path
import hashlib
import json
import math
import sys
import uuid

ROOT = Path(__file__).resolve().parents[3]
STAGE = Path(__file__).resolve().parent
INPUT = ROOT / '.oma/development/hospital-outcome-audit/volume-probes/ca4ef44543834f22a3a5fe1ba5e41e56'
APP = STAGE / 'combined-src'
sys.path.insert(0, str(APP))
from oma.ifc.cad_cache import _same_native_applicability
from OCP.BRepGProp import BRepGProp

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n', encoding='utf-8')

out = STAGE / 'volume-review' / uuid.uuid4().hex
out.mkdir(parents=True)
raw = (INPUT / 'result.json').read_bytes()
packet = json.loads(raw)
assert packet['status'] == 'NATIVE_TEE_VOLUME_INTEGRATION_DIAGNOSTIC_COMPLETE'
expected = math.pi * (3/64)**2 * (3/8) - (8/3) * (3/64)**3
observations = {}
for name, row in packet['observations'].items():
    assert sha(INPUT / (name + '.brep')) == row['brep_sha256']
    measurements = row['measurements']
    assert len(measurements) == 12
    assert all(math.isfinite(m['volume_m3']) for m in measurements)
    assert {m['centered_diagnostic_copy'] for m in measurements} == {False, True}
    differences = [abs(m['volume_m3'] - row['source_native_volume_m3']) for m in measurements]
    errors = [abs(m['volume_m3'] - expected) for m in measurements]
    assert max(differences) < 5e-14
    assert (all(e <= 1e-9 for e in errors) if name == 'old' else all(e > 1e-9 for e in errors))
    observations[name] = {'brep_sha256': row['brep_sha256'], 'volume_m3': row['source_native_volume_m3'],
        'analytic_volume_m3': expected, 'default_absolute_error_m3': abs(row['source_native_volume_m3'] - expected),
        'maximum_algorithm_or_translation_delta_m3': max(differences), 'minimum_absolute_error_across_all_methods_m3': min(errors),
        'all_methods_keep_original_semantic_disposition': True}

key = {'format': 'checker-native-source-cache/1', 'cad_code_sha256': 'a'*64,
       'enclosure_code_sha256': 'b'*64, 'cache_code_sha256': 'c'*64,
       'source_sha256': 'd'*64, 'guids': ['tee']}
assert not _same_native_applicability(key, {**key, 'cad_code_sha256': 'e'*64})
assert _same_native_applicability(key, {**key, 'enclosure_code_sha256': 'e'*64})
assert not _same_native_applicability(key, {**key, 'guids': ['different']})
doc = BRepGProp.VolumeProperties_s.__doc__ + '\n' + BRepGProp.VolumePropertiesGK_s.__doc__
(out / 'loaded-native-api.txt').write_text(doc, encoding='utf-8')
(out / 'input-result.json').write_bytes(raw)
(out / 'executed-review.py').write_bytes(Path(__file__).read_bytes())
for name in ('cad.py', 'cad_cache.py', 'network_semantics.py'):
    (out / name).write_bytes((APP / 'oma/ifc' / name).read_bytes())
write(out / 'result.json', {'schema': 'oma.native-volume-diagnostic-peer/1', 'status': 'DIAGNOSTIC_CONFIRMED_NO_QUADRATURE_FIX',
    'input_result_path': str(INPUT / 'result.json'), 'input_result_sha256': hashlib.sha256(raw).hexdigest(),
    'observations': observations, 'semantic_tolerance_m3_unchanged': 1e-9,
    'cache_guards': {'cad_hash_change_rejects_migration': True, 'enclosure_only_change_may_migrate': True, 'changed_guid_set_rejected': True},
    'algorithm_scope': 'Adaptive Eps controls successive-refinement relative convergence per face; returned whole-shape relative error is an estimate, not a rigorous interval bound. No production algorithm or threshold changed.',
    'official_reference': 'https://dev.opencascade.org/doc/refman/html/class_b_rep_g_prop___gauss.html',
    'next_boundary': 'IFC-to-BRep conversion/Boolean precision or physical interpretation remains to diagnose; retained volume data alone does not identify the cause.',
    'native_rerun': False})
files = {p.name: sha(p) for p in out.iterdir() if p.is_file()}
write(out / 'retention.json', {'retained_files': files, 'scope': 'Read-only peer review and captured inputs; self-map excluded.'})
print(json.dumps({'out': str(out), 'result_sha256': sha(out/'result.json'), 'retention_sha256': sha(out/'retention.json')}))
