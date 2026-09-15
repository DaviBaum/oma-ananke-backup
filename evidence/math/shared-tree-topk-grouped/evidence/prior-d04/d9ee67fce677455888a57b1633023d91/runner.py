"""Retained bounded nominal benchmark; no native or producer-provenance rerun."""
from pathlib import Path
import hashlib
import json
import shutil
import sys
import time
import uuid

STAGE = Path(__file__).resolve().parent
PROBES = STAGE.parent / 'general-shared-tree-native/catalogue-probes/b66610f8c6b54966aa8cf2b7a9bf8d1e'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


receipt = read(STAGE / 'latest-validation.json')
assert receipt['status'] == 'PASS'
snapshot = Path(receipt['snapshot'])
out = STAGE / 'evidence/actual-five-eight' / uuid.uuid4().hex
out.mkdir(parents=True)
shutil.copyfile(__file__, out / 'runner.py')
for name, expected in receipt['source_files'].items():
    target = out / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(snapshot / name, target)
    assert sha(target) == expected
sys.path.insert(0, str(out / 'src'))
from oma.optimization import shared_tree_topk as kernel

input_hashes = {}
for n in range(5, 9):
    folder = out / str(n)
    folder.mkdir()
    for name in ('generated.json', 'requirements.json', 'search.json', 'context.json', 'authoring.json', 'checked.json'):
        original = PROBES / str(n) / name
        shutil.copyfile(original, folder / name)
        input_hashes[f'{n}/{name}'] = sha(original)

limits = dict(max_connectors=512, max_work=20_000_000, max_states=50_000,
              max_transitions=2_000_000, max_label_pairs=10_000_000,
              max_bytes=16_777_216)
declaration = {
    'schema': 'oma.topk-authored-benchmark/1',
    'source_files': receipt['source_files'], 'inputs': input_hashes,
    'validation_receipt_sha256': receipt['receipt_sha256'],
    'limits_per_stage': limits, 'seconds_per_stage': 30,
    'queries': 'K=2 for all 5..8; additionally K=8 only if both K=2 stages pass, combined work <= 6M and combined elapsed <= 10s',
    'scope': 'Complete nominal catalogue proof only. Retained upstream provenance is historical; no native or pressure/physical acceptance claim.',
    'runner_sha256': sha(out / 'runner.py'),
}
write(out / 'declaration.json', declaration)
print(json.dumps({'started': str(out)}), flush=True)


def run_stage(operation, problem, certificate, k):
    began = time.perf_counter()
    deadline = began + 30
    expired = TimeoutError('Declared 30-second benchmark phase limit')
    def checkpoint(*args, **kwargs):
        if time.perf_counter() >= deadline:
            raise expired
    try:
        if operation == 'producer':
            result = kernel.compile_shared_tree_topk_catalogue(problem, k=k, checkpoint=checkpoint, **limits)
        else:
            result = kernel.verify_shared_tree_topk_catalogue(problem, certificate, k=k, checkpoint=checkpoint, **limits)
    except TimeoutError as caught:
        assert caught is expired
        result = {'status': 'UNKNOWN', 'proof_complete': False, 'proposals': [],
                  'reason': 'BENCHMARK_DEADLINE', 'exception_identity_preserved': True}
    return result, time.perf_counter() - began


records = {}
for n in range(5, 9):
    folder = out / str(n)
    problem = read(folder / 'generated.json')['catalogue']
    records[str(n)] = {}
    for k in (2, 8):
        if k == 8:
            earlier = records[str(n)]['2']
            if not (earlier['independently_checked'] and earlier['combined_work'] <= 6_000_000
                    and earlier['combined_seconds'] <= 10):
                records[str(n)]['8'] = {'status': 'NOT_RUN', 'reason': 'Declared adaptive benchmark bound'}
                continue
        produced, producer_seconds = run_stage('producer', problem, None, k)
        write(folder / f'produced-k{k}.json', produced)
        if produced['status'] == 'CERTIFIED':
            checked, checker_seconds = run_stage('checker', problem, produced['certificate'], k)
        else:
            checked, checker_seconds = {'status': 'NOT_RUN', 'reason': 'Producer did not certify'}, 0
        write(folder / f'checked-k{k}.json', checked)
        passed = produced['status'] == 'CERTIFIED' and checked['status'] == 'PASS'
        if passed:
            assert produced['proposals'] == checked['proposals']
            assert produced['counts']['complete_assignments'] == checked['counts']['complete_assignments']
        record = {
            'producer_status': produced['status'], 'checker_status': checked['status'],
            'producer_reason': produced.get('reason'), 'checker_reason': checked.get('reason'),
            'producer_seconds': producer_seconds, 'checker_seconds': checker_seconds,
            'combined_seconds': producer_seconds + checker_seconds,
            'producer_work': produced.get('work'), 'checker_work': checked.get('work'),
            'combined_work': produced.get('work', 0) + checked.get('work', 0),
            'independently_checked': passed, 'counts': produced.get('counts'),
            'certificate_root': produced.get('certificate_root'),
            'certificate_bytes': len(json.dumps(produced['certificate'], sort_keys=True, separators=(',', ':'),
                                               ensure_ascii=False).encode('utf-8')) if 'certificate' in produced else None,
        }
        records[str(n)][str(k)] = record
        write(out / 'progress.json', records)
        print(json.dumps({'sinks': n, 'k': k, **record}), flush=True)

assert all(sha(snapshot / name) == expected == sha(out / name) for name, expected in receipt['source_files'].items())
assert all(sha(PROBES / name) == expected == sha(out / name) for name, expected in input_hashes.items())
result = {'status': 'COMPLETED', 'declaration_sha256': sha(out / 'declaration.json'),
          'source_and_inputs_unchanged': True, 'queries': records, 'scope': declaration['scope']}
write(out / 'result.json', result)
write(out / 'file-index.json', {p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob('*'))
                               if p.is_file() and '__pycache__' not in p.parts and p.name != 'file-index.json'})
print(json.dumps({'completed': str(out), 'result_sha256': sha(out / 'result.json')}), flush=True)
