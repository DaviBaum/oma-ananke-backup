"""Exact old-certificate equivalence and independent grouped-edge attacks."""
import copy
import importlib.util
import json
from fractions import Fraction as Q
from pathlib import Path

import pytest

from oma.optimization import shared_tree_topk as current
import test_general_shared_tree_synthesis as fixtures

FIXTURES = Path(__file__).parent / 'fixtures/shared-tree-topk'
spec = importlib.util.spec_from_file_location('oma.optimization.old_d04_grouped_test', FIXTURES/'d04_shared_tree_topk.py')
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)


def byte_equal(problem, k):
    limits = dict(k=k, max_work=20_000_000, max_transitions=2_000_000)
    old = original.compile_shared_tree_topk_catalogue(problem, **limits)
    new = current.compile_shared_tree_topk_catalogue(problem, **limits)
    assert old['status'] == new['status'] == 'CERTIFIED', (old, new)
    assert new['certificate'] == old['certificate']
    assert new['proposals'] == old['proposals']
    assert current.verify_shared_tree_topk_catalogue(problem, old['certificate'], **limits)['status'] == 'PASS'
    assert original.verify_shared_tree_topk_catalogue(problem, new['certificate'], **limits)['status'] == 'PASS'
    return new


@pytest.mark.parametrize('n', [2, 3, 4])
@pytest.mark.parametrize('k', [1, 3, 8])
@pytest.mark.parametrize('ties', [False, True])
def test_complete_old_certificate_bytes_and_bidirectional_replay(n, k, ties):
    problem = fixtures.catalogue(n, dense=True, extra_tees=1 if n < 4 else 0)
    if ties:
        for record in problem['connectors'] + problem['tee_instances']:
            record['nominal_cost'] = ['0', '0']
    new = byte_equal(problem, k)
    oracle = fixtures.incoming_function_oracle(problem)
    assert int(new['counts']['complete_assignments']) == len(oracle)
    if ties:
        assert [tuple(row['connector_ids']) for row in new['proposals']] == sorted(oracle)[:k]


@pytest.mark.parametrize('n', [3, 5, 8])
@pytest.mark.parametrize('k', [1, 3, 8])
def test_all_parallel_multiplicities_counted_when_only_k_can_rank(n, k):
    problem = fixtures.catalogue(n, parallel=False)
    old_edges = problem['connectors'][:]
    problem['connectors'] = []
    for edge in old_edges:
        for j in range(9):
            added = copy.deepcopy(edge)
            added['id'] = edge['id'] + '-choice-' + str(j)
            added['nominal_cost'] = [str(j % 3), str(j // 3)]
            problem['connectors'].append(added)
    result = byte_equal(problem, k)
    assert int(result['counts']['complete_assignments']) == 9**(2*n-1)


@pytest.mark.parametrize('k', [1, 3, 8])
def test_parallel_rational_pi_and_context_lex_order(k):
    problem = fixtures.pi_catalogue()
    edge = copy.deepcopy(problem['connectors'][-1])
    for cost, identity in [(['22/7', '0'], 'aaa-rational'), (['0', '1'], 'zzz-pi'), (['0', '1'], 'bbb-pi')]:
        added = copy.deepcopy(edge)
        added['id'] = identity
        added['nominal_cost'] = cost
        problem['connectors'].append(added)
    byte_equal(problem, k)


def test_authored_dense_six_certifies_exact_count_under_original_hard_limits():
    problem = json.loads((FIXTURES/'authored-six-catalogue.json').read_text(encoding='utf-8'))
    limits = dict(k=2, max_work=2_000_000, max_transitions=500_000)
    produced = current.compile_shared_tree_topk_catalogue(problem, **limits)
    assert produced['status'] == 'CERTIFIED', produced
    checked = current.verify_shared_tree_topk_catalogue(problem, produced['certificate'], **limits)
    assert checked['status'] == 'PASS', checked
    assert produced['counts']['complete_assignments'] == '801286604'
    assert produced['counts']['transitions'] < 22_000
    assert produced['certificate_root'] == '36b1e35436c76677895d7adfeaa9173ddd717e2abfbea315e21d9e043b813a19'


def test_checker_does_not_invoke_any_producer_product_grouping_or_join(monkeypatch):
    problem = fixtures.catalogue(4, dense=True)
    proof = current.compile_shared_tree_topk_catalogue(problem, k=3)['certificate']
    def forbidden(*args, **kwargs):
        raise AssertionError('producer dependency')
    for name in vars(current):
        if name.startswith('_producer_'):
            monkeypatch.setattr(current, name, forbidden)
    assert current.verify_shared_tree_topk_catalogue(problem, proof, k=3)['status'] == 'PASS'


@pytest.mark.parametrize('attack', ['count', 'omit-label', 'wrong-cost', 'wrong-edge', 'omit-state', 'duplicate-state'])
def test_resealed_grouped_count_and_label_attacks(attack):
    problem = fixtures.catalogue(4, dense=True)
    result = current.compile_shared_tree_topk_catalogue(problem, k=3)
    certificate = copy.deepcopy(result['certificate'])
    row = next(r for r in certificate['states'] if len(r['labels']) == 3)
    if attack == 'count': row['tree_count'] = str(int(row['tree_count'])-1)
    elif attack == 'omit-label': row['labels'].pop()
    elif attack == 'wrong-cost': row['labels'][0]['nominal_cost'][0] = '0'
    elif attack == 'wrong-edge': row['labels'][0]['connector_ids'][0] = problem['connectors'][-1]['id']
    elif attack == 'omit-state': certificate['states'].pop()
    else: certificate['states'].append(copy.deepcopy(row))
    for state in certificate['states']:
        for label in state['labels']:
            body = {key: label[key] for key in ('connector_ids', 'nominal_cost')}
            label['label_root'] = fixtures.digest({'problem_root': certificate['problem_root'], 'state': state['state'], **body})
    fixtures.reseal(certificate)
    assert current.verify_shared_tree_topk_catalogue(problem, certificate, k=3)['status'] == 'FAIL'


@pytest.mark.parametrize('verifier', [False, True])
def test_late_grouped_input_mutation_cannot_publish(verifier):
    problem = fixtures.catalogue(4, dense=True)
    proof = current.compile_shared_tree_topk_catalogue(problem, k=2)['certificate']
    def checkpoint(stage):
        if stage.endswith('_complete'):
            problem['connectors'][-1]['nominal_cost'][0] = '1234'
    result = (current.verify_shared_tree_topk_catalogue(problem, proof, k=2, checkpoint=checkpoint) if verifier
              else current.compile_shared_tree_topk_catalogue(problem, k=2, checkpoint=checkpoint))
    assert result['status'] in ('FAIL', 'INVALID_INPUT')
    assert result['proposals'] == []


@pytest.mark.parametrize('verifier', [False, True])
def test_exact_grouped_work_boundary_still_includes_final_guard(verifier):
    problem = fixtures.catalogue(4, dense=True)
    produced = current.compile_shared_tree_topk_catalogue(problem, k=2)
    fn = (lambda **kw: current.verify_shared_tree_topk_catalogue(problem, produced['certificate'], k=2, **kw)) if verifier else (
        lambda **kw: current.compile_shared_tree_topk_catalogue(problem, k=2, **kw))
    work = fn()['work']
    assert fn(max_work=work)['status'] in ('CERTIFIED', 'PASS')
    result = fn(max_work=work-1)
    assert result['status'] == 'UNKNOWN' and result['proposals'] == []
