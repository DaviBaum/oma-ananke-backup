"""Actual measured exact linear port reuse on a declared synthetic chain."""
from dataclasses import asdict
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from oma.optimization import ports


def main():
    repeats = 13
    bindings = dict(model_id='original-P6-three-spring-series-motif', units='synthetic-consistent-force/displacement',
                    regime='positive-linear-elastic', parameter_domain='exact-conductances-1-2-1',
                    scenario_domain='all-rational-boundary-displacements-zero-internal-load',
                    source_root='original-1-10-P15949-P16027')
    nodes = tuple(f'n{i}' for i in range(3*repeats+1))
    edges = [(nodes[i], nodes[i+1], (1,2,1)[i%3]) for i in range(len(nodes)-1)]
    boundary = (nodes[0], nodes[-1])
    begin = perf_counter()
    full = ports.compile_kron_network(nodes, edges, boundary, context_root='synthetic-chain-full-v1', model_bindings=bindings)
    compiled_seconds = perf_counter()-begin
    begin = perf_counter()
    check = ports.verify_kron_network(nodes, edges, boundary, full['model'], full['certificate'],
                                     context_root='synthetic-chain-full-v1', model_bindings=bindings)
    checked_seconds = perf_counter()-begin
    assert check['status'] == 'PASS'

    coarse_nodes = tuple(f'port{i}' for i in range(repeats+1))
    coarse_edges = [(coarse_nodes[i],coarse_nodes[i+1],Q(2,5)) for i in range(repeats)]
    begin = perf_counter()
    coarse = ports.compile_kron_network(coarse_nodes, coarse_edges, (coarse_nodes[0],coarse_nodes[-1]),
                                       context_root='synthetic-condensed-chain-v1', model_bindings=bindings)
    coarse_compile_seconds = perf_counter()-begin
    begin = perf_counter()
    coarse_check = ports.verify_kron_network(coarse_nodes, coarse_edges, (coarse_nodes[0],coarse_nodes[-1]),
        coarse['model'], coarse['certificate'], context_root='synthetic-condensed-chain-v1', model_bindings=bindings)
    coarse_check_seconds = perf_counter()-begin
    assert coarse_check['status'] == 'PASS'
    # Independent circuit-law oracle: series compliances add exactly.
    compliance = sum((1/Q(g) for _,_,g in edges), Q(0))
    expected = [[str(1/compliance),str(-1/compliance)],[str(-1/compliance),str(1/compliance)]]
    assert full['certificate']['response_matrix'] == coarse['certificate']['response_matrix'] == expected
    u0, u1 = Q(2), Q(7)
    flow = (u1-u0)/compliance
    expected_states, cumulative = [u0], Q(0)
    for _,_,g in edges:
        cumulative += 1/Q(g)
        expected_states.append(u0+flow*cumulative)
    begin = perf_counter()
    witness = ports.reconstruct_linear_port(full['model'], full['certificate'], [u0,u1],
                                            context_root='synthetic-chain-full-v1')
    replay_seconds = perf_counter()-begin
    assert witness['status'] == 'REALIZATION_CHECKED'
    assert list(map(Q,witness['full_state'])) == expected_states
    assert list(map(Q,witness['boundary_forces'])) == [-flow,flow]

    artifact = dict(full_model=asdict(full['model']), full_certificate=full['certificate'],
                    composed_model=asdict(coarse['model']), composed_certificate=coarse['certificate'])
    encoded = json.dumps(artifact, default=str, sort_keys=True, separators=(',',':')).encode()
    destination = ROOT / 'evidence/math/original-linear-port-chain-certificate.json'
    destination.write_bytes(encoded)
    report = dict(schema='oma.original-linear-port-benchmark/1', scope='SYNTHETIC_EXACT_LINEAR_NETWORK',
        original_source=dict(archive='1-10', sha256='0ad4cd0c72cdb8fac573b3bfd262d86d9580a8218a98657c828b01eaba92d970',
                             paragraphs=[15949,16027], objects=['THM-PO6','THM-PO31','ALG-PO1','ALG-PO7']),
        repeated_motifs=repeats, full_coordinates=len(nodes), full_internal_coordinates=len(nodes)-2,
        composed_coordinates=len(coarse_nodes), retained_boundary_coordinates=2,
        exact_effective_stiffness=str(1/compliance), all_boundary_inputs_covered_by_matrix_identity=True,
        independent_checks=['positive edge-incidence energy identity','two-sided interior inverse identity',
            'original matrix reconstruction identity','independent series compliance sum',
            'every full state compared to independent cumulative compliance oracle'],
        exact_model_physical_applicability_verified=False,
        limitations=['Synthetic linear springs/conductances, no actual building simulation or measured physical calibration.',
            'No nonlinear flow, dynamics, buckling, thermal radiation, model discrepancy or general PCPE library.',
            'Every public reconstruction rechecks the certificate; this timing includes that conservative cost.',
            'These measurements do not claim universal reduction speedup or cheaper online certification.'],
        timings_seconds=dict(full_compile=compiled_seconds, full_independent_check=checked_seconds,
            composed_compile=coarse_compile_seconds, composed_independent_check=coarse_check_seconds,
            full_witness_with_recheck=replay_seconds),
        artifact=dict(path=str(destination.relative_to(ROOT)), bytes=len(encoded), sha256=hashlib.sha256(encoded).hexdigest()),
        implementation=dict(path='src/oma/optimization/ports.py', sha256=hashlib.sha256(Path(ports.__file__).read_bytes()).hexdigest()),
        verdict='ALL_DECLARED_EXACT_COMPARISONS_PASS')
    path = ROOT / 'evidence/math/original-linear-port-chain-benchmark.json'
    path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
