"""Measured finite synthetic original-P8 relation compilation and verification."""
from hashlib import sha256
import json
from pathlib import Path
import platform
from time import perf_counter

from oma.optimization.bisimulation import NondeterministicAction, compile_bisimulation, verify_bisimulation

ROOT = Path(__file__).resolve().parents[1]


def main():
    states = tuple(f'd{d:02}-copy{k}' for d in range(41) for k in range(8))
    depths = {f'd{d:02}-copy{k}': d for d in range(41) for k in range(8)}
    actions = (
        NondeterministicAction('advance', 'S', 'S', {s: tuple(f'd{depths[s]-1:02}-copy{k}' for k in range(8)) if depths[s] else () for s in states}),
        NondeterministicAction('stutter', 'S', 'S', {s: tuple(f'd{depths[s]:02}-copy{k}' for k in range(8)) for s in states}),
    )
    observations = {'S': {s: depths[s] == 0 for s in states}}
    start = perf_counter()
    cert = compile_bisimulation({'S': states}, actions, observations, context_root='synthetic-depth40-clone8-v1', max_work=20_000_000)
    compile_seconds = perf_counter() - start
    start = perf_counter()
    checked = verify_bisimulation({'S': states}, actions, observations, cert, context_root='synthetic-depth40-clone8-v1', max_work=20_000_000)
    check_seconds = perf_counter() - start
    assert checked['status'] == 'PASS'
    assert len(cert['blocks']) == 41
    for block in cert['blocks']:
        assert len(block) == 8 and len({depths[cert['states'][i][1]] for i in block}) == 1
    certificate_bytes = (json.dumps(cert, sort_keys=True, separators=(',', ':')) + '\n').encode()
    destination = ROOT / 'evidence/math/original-causal-macro-certificate.json'
    destination.write_bytes(certificate_bytes)
    result = {'schema': 'oma.synthetic-causal-macro-benchmark/1', 'status': 'PASS',
              'scope': 'SYNTHETIC_SUPPLIED_FINITE_TRANSITION_SYSTEM_ONLY',
              'source': {'document': '1-10', 'sha256': '0ad4cd0c72cdb8fac573b3bfd262d86d9580a8218a98657c828b01eaba92d970',
                         'paragraphs': [18648, 18747, 19214, 19264], 'objects': ['DEF-CS5', 'LEM-CS3', 'THM-CS3', 'ALG-CS1', 'THM-CS21']},
              'model': {'states': len(states), 'actions': 2, 'transitions': sum(len(t) for a in actions for t in a.transitions.values()),
                        'complete_direct_observations': len(states), 'ground_truth': '41 exact depth classes, eight interchangeable clones per depth'},
              'result': {'classes': len(cert['blocks']), 'strict_refinement_rounds': cert['strict_refinement_rounds'],
                         'modal_nodes': len(cert['modal_nodes']), 'verified_separated_block_pairs': checked['verified_separated_block_pairs'],
                         'compile_work': cert['work'], 'check_work': checked['work']},
              'timing': {'compile_seconds': compile_seconds, 'independent_check_seconds': check_seconds,
                         'measurement': 'single non-isolated workstation wall-clock run'},
              'environment': {'python': platform.python_version(), 'platform': platform.platform()},
              'code_sha256': sha256((ROOT / 'src/oma/optimization/bisimulation.py').read_bytes()).hexdigest(),
              'artifact': {'path': str(destination.relative_to(ROOT)), 'sha256': sha256(certificate_bytes).hexdigest(), 'bytes': len(certificate_bytes)},
              'limitations': ['No physical transitions or actual project model are inferred.', 'No probabilistic or weak-bisimulation claim.',
                              'The finite example does not establish general compression efficiency or whole-source implementation.']}
    (ROOT / 'evidence/math/original-causal-macro-benchmark.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
