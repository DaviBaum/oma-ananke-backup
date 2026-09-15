from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as Q
from itertools import combinations, permutations, product
import random

import pytest

from oma.optimization import ports
from oma.optimization.ports import (LinearPortModel, compile_linear_port, verify_linear_port,
    reconstruct_linear_port, certify_linear_residual, compile_kron_network, verify_kron_network)


ROOT = "synthetic-declared-linear-model-v1"
BINDINGS = dict(model_id="synthetic-linear-springs", units="consistent-declared-matrix-units",
                regime="linear", parameter_domain="exact-listed-matrix", scenario_domain="fixed-load",
                source_root="source-p6-worked-example")


def model(a, boundary, loads):
    return LinearPortModel(tuple(map(tuple, a)), tuple(boundary), tuple(loads), BINDINGS)


def spring():
    return model([[1,-1,0,0],[-1,3,-2,0],[0,-2,3,-1],[0,0,-1,1]], [0,3], [0,0])


def test_original_spring_schur_full_system_and_reduced_residual():
    source = spring()
    cert = compile_linear_port(source, context_root=ROOT)
    assert cert['response_matrix'] == [['2/5','-2/5'],['-2/5','2/5']]
    assert verify_linear_port(source, cert, context_root=ROOT)['status'] == 'PASS'
    witness = reconstruct_linear_port(source, cert, [0,1], context_root=ROOT)
    assert witness['status'] == 'REALIZATION_CHECKED'
    assert witness['full_state'] == ['0','2/5','3/5','1']
    assert witness['boundary_forces'] == ['-2/5','2/5']
    error = certify_linear_residual(source, cert, [0,1], ['1/2','1/2'], context_root=ROOT)
    assert error['status'] == 'ERROR_BOUND_CHECKED'
    assert error['residual'] == ['-1/2','1/2']
    assert error['interior_component_error'] == ['1/2','1/2']
    assert error['inverse_infinity_norm'] == '1'
    assert error['physical_discrepancy_included'] is False
    exact_error = max(abs(Q(x)-Q('1/2')) for x in witness['internal_state'])
    assert exact_error == Q('1/10') <= Q(error['interior_infinity_error'])


def test_affine_internal_load_and_boundary_permutation():
    source = model([[2,-1],[-1,3]], [1], [2])
    cert = compile_linear_port(source, context_root=ROOT)
    assert cert['response_matrix'] == [['5/2']]
    assert cert['force_offset'] == ['-1']
    assert reconstruct_linear_port(source, cert, [2], context_root=ROOT)['full_state'] == ['2','2']
    assert reconstruct_linear_port(source, cert, [2], [5], context_root=ROOT)['status'] == 'NO_REALIZATION'


@pytest.mark.parametrize('matrix,loads,ub,fb,expected', [
    ([[0,1],[1,0]], [2], [2], [3], ['2','3']),
    ([[2,0],[0,0]], [0], [3], [6], ['3','0']),
    ([[0,0],[0,0]], [0], [9], [0], ['9','0']),
    ([[1,1,1],[1,1,0],[0,0,0]], [0,0], [2], [3], ['2','-2','3']),
])
def test_singular_relations_preserve_free_and_compatibility_modes(matrix, loads, ub, fb, expected):
    source = model(matrix, [0], loads)
    cert = compile_linear_port(source, context_root=ROOT)
    assert cert['method'] == 'AFFINE_RELATION'
    assert verify_linear_port(source, cert, context_root=ROOT)['status'] == 'PASS'
    result = reconstruct_linear_port(source, cert, ub, fb, context_root=ROOT)
    assert result['status'] == 'REALIZATION_CHECKED'
    assert result['full_state'] == expected
    assert reconstruct_linear_port(source, cert, ub, context_root=ROOT)['status'] == 'UNKNOWN'
    assert certify_linear_residual(source, cert, ub, [0]*len(loads), context_root=ROOT)['status'] == 'UNKNOWN'


def test_empty_singular_fiber_and_incompatible_boundary_are_not_solvers_failed():
    source = model([[0,0],[0,0]], [0], [1])
    cert = compile_linear_port(source, context_root=ROOT)
    assert verify_linear_port(source, cert, context_root=ROOT)['status'] == 'PASS'
    assert reconstruct_linear_port(source, cert, [1], [0], context_root=ROOT)['status'] == 'NO_REALIZATION'
    source = model([[0,1],[1,0]], [0], [2])
    cert = compile_linear_port(source, context_root=ROOT)
    assert reconstruct_linear_port(source, cert, [1], [99], context_root=ROOT)['status'] == 'NO_REALIZATION'


def test_no_internal_coordinates():
    source = model([[2,-1],[-1,3]], [1,0], [])
    cert = compile_linear_port(source, context_root=ROOT)
    assert cert['method'] == 'SCHUR'
    assert verify_linear_port(source, cert, context_root=ROOT)['status'] == 'PASS'
    assert reconstruct_linear_port(source, cert, [1,2], context_root=ROOT)['boundary_forces'] == ['1','3']
    assert certify_linear_residual(source, cert, [1,2], [], context_root=ROOT)['interior_infinity_error'] == '0'


def test_independent_checker_never_calls_inverse_or_compiler(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError('Checker called producer')
    sources = [spring(), model([[0,1],[1,0]], [0], [2])]
    certs = [compile_linear_port(s, context_root=ROOT) for s in sources]
    monkeypatch.setattr(ports, '_inverse', forbidden)
    monkeypatch.setattr(ports, 'compile_linear_port', forbidden)
    for source, cert in zip(sources, certs):
        assert verify_linear_port(source, cert, context_root=ROOT)['status'] == 'PASS'


@pytest.mark.parametrize('field', ['root','response_matrix','internal_inverse','force_offset',
    'reconstruction_matrix','reconstruction_offset','boundary_indices','physical_applicability_verified'])
def test_schur_tampering_fails(field):
    source = spring()
    cert = compile_linear_port(source, context_root=ROOT)
    if field in ('response_matrix','internal_inverse','reconstruction_matrix'):
        cert[field][0][0] = str(Q(cert[field][0][0])+1)
    elif field in ('force_offset','reconstruction_offset'):
        cert[field][0] = '99'
    elif field == 'boundary_indices':
        cert[field].reverse()
    else:
        cert[field] = 'tampered'
    assert verify_linear_port(source, cert, context_root=ROOT)['status'] == 'FAIL'


@pytest.mark.parametrize('field', ['row_transform','row_transform_inverse','reduced_internal',
    'transformed_external','transformed_rhs','internal_pivot_columns','constraint_matrix','constraint_rhs'])
def test_singular_certificate_tampering_fails(field):
    source = model([[0,1],[1,0]], [0], [2])
    cert = compile_linear_port(source, context_root=ROOT)
    if field == 'internal_pivot_columns':
        cert[field] = []
    elif field in ('transformed_rhs','constraint_rhs'):
        cert[field][0] = '99'
    else:
        cert[field][0][0] = str(Q(cert[field][0][0])+1)
    assert verify_linear_port(source, cert, context_root=ROOT)['status'] == 'FAIL'


def determinant(matrix):
    """Independent Leibniz formula, no Gaussian elimination or matrix library."""
    n = len(matrix)
    total = Q(0)
    for p in permutations(range(n)):
        inversions = sum(p[i] > p[j] for i in range(n) for j in range(i+1,n))
        term = Q((-1)**inversions)
        for i in range(n):
            term *= matrix[i][p[i]]
        total += term
    return total


def rank_by_minors(a):
    n, m = len(a), len(a[0])
    for k in range(min(n,m),0,-1):
        for rows in combinations(range(n),k):
            for cols in combinations(range(m),k):
                if determinant([[a[i][j] for j in cols] for i in rows]):
                    return k
    return 0


def test_random_projection_against_independent_all_minors_compatibility_oracle():
    rng = random.Random(39844)
    for _ in range(30):
        n = rng.randrange(2,5)
        a = [[Q(rng.randrange(-2,3)) for _ in range(n)] for _ in range(n)]
        # Force some truly singular interiors, including hidden nullspaces.
        if rng.randrange(2):
            for j in range(1,n):
                a[n-1][j] = Q(0)
        loads = [Q(rng.randrange(-2,3)) for _ in range(n-1)]
        source = model(a, [0], loads)
        cert = compile_linear_port(source, context_root=ROOT)
        assert verify_linear_port(source, cert, context_root=ROOT)['status'] == 'PASS'
        c = [row[1:] for row in a]
        original_rank = rank_by_minors(c)
        for ub, fb in product(range(-2,3), repeat=2):
            rhs = [(fb if i == 0 else loads[i-1])-a[i][0]*ub for i in range(n)]
            exists = rank_by_minors([row+[r] for row,r in zip(c,rhs)]) == original_rank
            result = reconstruct_linear_port(source, cert, [ub], [fb], context_root=ROOT)
            assert (result['status'] == 'REALIZATION_CHECKED') == exists


def test_conditioning_cannot_be_replaced_by_a_small_residual():
    source = model([[1,0],[0,'1/1000000']], [0], [1])
    cert = compile_linear_port(source, context_root=ROOT)
    result = certify_linear_residual(source, cert, [0], [999999], context_root=ROOT)
    assert result['residual_infinity_norm'] == '1/1000000'
    assert result['interior_infinity_error'] == '1'
    assert result['stability_lower_infinity'] == '1/1000000'


def test_positive_network_kron_and_exact_energy_identity():
    nodes, edges, boundary = ('a','b','c','d'), [('a','b',1),('b','c',2),('c','d',1)], ('a','d')
    result = compile_kron_network(nodes, edges, boundary, context_root=ROOT, model_bindings=BINDINGS)
    assert result['certificate']['response_matrix'] == [['2/5','-2/5'],['-2/5','2/5']]
    checked = verify_kron_network(nodes, edges, boundary, result['model'], result['certificate'], context_root=ROOT, model_bindings=BINDINGS)
    assert checked['status'] == 'PASS' and checked['positive_edge_energy_identity_checked']
    altered = [('a','b',2),*edges[1:]]
    assert verify_kron_network(nodes, altered, boundary, result['model'], result['certificate'], context_root=ROOT, model_bindings=BINDINGS)['status'] == 'FAIL'
    # The floating internal component is retained instead of grounded silently.
    floating = compile_kron_network(('a','b','c'), [('b','c',1)], ('a',), context_root=ROOT, model_bindings=BINDINGS)
    assert floating['certificate']['method'] == 'AFFINE_RELATION'
    assert verify_kron_network(('a','b','c'), [('b','c',1)], ('a',), floating['model'], floating['certificate'], context_root=ROOT, model_bindings=BINDINGS)['singular_modes_retained']


def test_exact_domain_budget_and_binding_failures():
    source = spring()
    cert = compile_linear_port(source, context_root=ROOT)
    assert compile_linear_port(source, context_root=ROOT, max_dimension=2)['status'] == 'UNKNOWN'
    assert compile_linear_port(source, context_root=ROOT, max_work=0)['status'] == 'UNKNOWN'
    assert verify_linear_port(source, cert, context_root=ROOT, max_work=0)['status'] == 'UNKNOWN'
    assert verify_linear_port(source, cert, context_root='changed')['status'] == 'FAIL'
    changed = replace(source, model_bindings=dict(BINDINGS, regime='changed'))
    assert verify_linear_port(changed, cert, context_root=ROOT)['status'] == 'FAIL'
    for bad in (model([[1.0]], [0], []), model([[1]], [0,0], []), model([[1,2]], [0], []),
                model([[1]], [], [1]), replace(source, model_bindings={})):
        with pytest.raises(ValueError):
            compile_linear_port(bad, context_root=ROOT)
    for bad in (0,-1,'-1/100'):
        with pytest.raises(ValueError):
            compile_kron_network(('a','b'), [('a','b',bad)], ('a',), context_root=ROOT, model_bindings=BINDINGS)
