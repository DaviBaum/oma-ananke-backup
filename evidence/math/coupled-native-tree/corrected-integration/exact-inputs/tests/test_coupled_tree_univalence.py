from copy import deepcopy
from fractions import Fraction as Q
import hashlib
import json
import random

import pytest

from oma.optimization import coupled_tree_pressure as local
from oma.optimization import coupled_tree_univalence as u


def interval(lo, hi=None):
    return {'lower': str(lo), 'upper': str(lo if hi is None else hi)}


def example(n=4):
    leaves = [chr(97+i) for i in range(n)]
    terms = [{'id': 'singleton-' + i, 'coefficient_id': 'singleton',
              'descendant_leaves': [i], 'applies_to_leaves': [i]} for i in leaves]
    terms.append({'id': 'unequal-root', 'coefficient_id': 'shared',
                  'descendant_leaves': leaves[:], 'applies_to_leaves': [leaves[-1]]})
    if n > 2:
        terms.append({'id': 'unequal-subtree', 'coefficient_id': 'shared',
                      'descendant_leaves': leaves[:2], 'applies_to_leaves': [leaves[0]]})
    model = {'schema': local.MODEL_SCHEMA, 'leaves': leaves, 'terms': terms,
             'coefficients': {'singleton': interval(1), 'shared': interval(Q(1, 10))},
             'available_heads': {}, 'context_root': 'a'*64, 'physical_model_root': 'b'*64,
             'assumptions': deepcopy(local.MODEL_ASSUMPTIONS)}
    q = {i: Q(index+1) for index, i in enumerate(leaves)}
    model['available_heads'] = {i: interval(sum(Q(model['coefficients'][t['coefficient_id']]['lower']) *
        sum(q[j] for j in t['descendant_leaves'])**2 for t in terms if i in t['applies_to_leaves'])) for i in leaves}
    box = {i: interval(value-Q(1, 100), value+Q(1, 100)) for i, value in q.items()}
    return model, box


def reroot(certificate):
    body = {k: v for k, v in certificate.items() if k != 'certificate_root'}
    certificate['certificate_root'] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    return certificate


def exact_inverse_and_determinant(matrix):
    """Independent Fraction Gauss–Jordan oracle, unrelated to certificate code."""
    n = len(matrix)
    a = [[Q(v) for v in row] + [Q(i == j) for j in range(n)] for i, row in enumerate(matrix)]
    determinant = Q(1)
    for col in range(n):
        pivot = next(i for i in range(col, n) if a[i][col])
        if pivot != col:
            a[pivot], a[col] = a[col], a[pivot]
            determinant *= -1
        value = a[col][col]
        determinant *= value
        a[col] = [v/value for v in a[col]]
        for row in range(n):
            if row != col:
                multiplier = a[row][col]
                a[row] = [v - multiplier*w for v, w in zip(a[row], a[col])]
    return [row[n:] for row in a], determinant


def test_exact_polarization_and_nonsymmetric_nested_matrix_oracle():
    model, _ = example()
    names = model['leaves']
    rng = random.Random(1047)
    negative_inverse_seen = False
    for _ in range(40):
        q = {i: Q(rng.randrange(1, 10), rng.randrange(1, 6)) for i in names}
        r = {i: Q(rng.randrange(0, 10), rng.randrange(1, 6)) for i in names}
        coefficients = {i: Q(rng.randrange(1, 8), rng.randrange(1, 6)) for i in model['coefficients']}
        matrix = [[Q(0) for _ in names] for _ in names]
        def f(vector):
            return [sum(coefficients[t['coefficient_id']] * sum(vector[j] for j in t['descendant_leaves'])**2
                        for t in model['terms'] if i in t['applies_to_leaves']) for i in names]
        for t in model['terms']:
            scale = coefficients[t['coefficient_id']] * sum(q[i]+r[i] for i in t['descendant_leaves'])
            for i, name in enumerate(names):
                for j, other in enumerate(names):
                    if name in t['applies_to_leaves'] and other in t['descendant_leaves']:
                        matrix[i][j] += scale
        difference = [q[i]-r[i] for i in names]
        assert [a-b for a, b in zip(f(q), f(r))] == [sum(a*v for a, v in zip(row, difference)) for row in matrix]
        assert any(matrix[i][j] != matrix[j][i] for i in range(4) for j in range(4))
        inverse, determinant = exact_inverse_and_determinant(matrix)
        assert determinant > 0
        assert all(sum(inverse[i][j] for i in range(4)) > 0 for j in range(4))
        negative_inverse_seen |= any(v < 0 for row in inverse for v in row)
    assert negative_inverse_seen  # The theorem must not assume B^-1 >= 0.


@pytest.mark.parametrize('n', [1, 2, 4, 8])
def test_complete_hierarchy_and_independent_replay(n, monkeypatch):
    model, _ = example(n)
    certificate = u.compile_coupled_tree_univalence(model)
    assert certificate['status'] == 'CERTIFIED_UNIVALENCE'
    assert len(certificate['hierarchy']) <= 2*n-1
    monkeypatch.setattr(u, 'compile_coupled_tree_univalence', lambda *a, **k: pytest.fail('Producer invoked'))
    monkeypatch.setattr(u, '_produce_hierarchy', lambda *a, **k: pytest.fail('Producer hierarchy invoked'))
    result = u.verify_coupled_tree_univalence(model, certificate)
    assert result['status'] == 'PASS' and result['proof_complete']
    assert result['model_root'] == certificate['model_root']
    assert result['limitations']['existence_proved_by_univalence_alone'] is False


@pytest.mark.parametrize('attack', ['remove_singleton', 'zero_lower', 'missing_all_singletons'])
def test_unsupported_positive_singleton_premise_is_unknown(attack):
    model, _ = example()
    if attack == 'zero_lower': model['coefficients']['singleton'] = interval(0, 1)
    elif attack == 'remove_singleton':
        model['terms'] = [t for t in model['terms'] if t['id'] != 'singleton-a']
    else:
        model['terms'] = [{'id': 'whole', 'coefficient_id': 'shared', 'descendant_leaves': model['leaves'][:], 'applies_to_leaves': model['leaves'][:]}]
        del model['coefficients']['singleton']
    result = u.compile_coupled_tree_univalence(model)
    assert result['status'] == 'UNKNOWN' and not result['proof_complete']


@pytest.mark.parametrize('attack', ['nonlaminar', 'foreign_application', 'unused_coefficient', 'duplicate_term', 'duplicate_leaf', 'negative_coefficient', 'false_assumptions'])
def test_invalid_declared_model_never_gets_a_theorem(attack):
    model, _ = example()
    if attack == 'nonlaminar':
        model['terms'].append({'id': 'cross', 'coefficient_id': 'shared', 'descendant_leaves': ['b', 'c'], 'applies_to_leaves': ['b']})
    elif attack == 'foreign_application': model['terms'][0]['applies_to_leaves'] = ['b']
    elif attack == 'unused_coefficient': model['coefficients']['unused'] = interval(1)
    elif attack == 'duplicate_term': model['terms'].append(deepcopy(model['terms'][0]))
    elif attack == 'duplicate_leaf': model['leaves'].append('a')
    elif attack == 'negative_coefficient': model['coefficients']['shared'] = interval(-1, 1)
    else: model['assumptions']['regime'] = 'REVERSE_FLOW'
    assert u.compile_coupled_tree_univalence(model)['status'] == 'INVALID_INPUT'


@pytest.mark.parametrize('attack', ['omit_node', 'duplicate_node', 'wrong_root', 'wrong_parent', 'omit_child', 'extra_child', 'omit_term', 'extra_term', 'wrong_row_support', 'wrong_set', 'wrong_step', 'omit_leaf', 'false_sum', 'coefficient_identity', 'parameter_root', 'scope'])
def test_coherently_rerooted_certificate_attacks_are_rejected(attack):
    model, _ = example()
    certificate = u.compile_coupled_tree_univalence(model)
    root = next(r for r in certificate['hierarchy'] if r['parent'] is None)
    leaf = certificate['hierarchy'][0]
    if attack == 'omit_node': certificate['hierarchy'].pop(0)
    elif attack == 'duplicate_node': certificate['hierarchy'].append(deepcopy(leaf))
    elif attack == 'wrong_root': certificate['hierarchy_root'] = leaf['id']
    elif attack == 'wrong_parent': leaf['parent'] = leaf['id']
    elif attack == 'omit_child': root['children'].pop()
    elif attack == 'extra_child': root['children'].append(root['children'][0])
    elif attack == 'omit_term': leaf['term_ids'] = []
    elif attack == 'extra_term': root['term_ids'].append('singleton-a')
    elif attack == 'wrong_row_support': root['row_terms']['a'] = root['term_ids'][:]
    elif attack == 'wrong_set': root['leaves'] = ['a']
    elif attack == 'wrong_step': leaf['step'] = 'LAMINAR_BLOCK_RANK_ONE_UPDATE'
    elif attack == 'omit_leaf': del certificate['leaf_witnesses']['a']
    elif attack == 'false_sum': certificate['leaf_witnesses']['a']['coefficient_lower_sum'] = '999'
    elif attack == 'coefficient_identity': certificate['model_manifest']['terms'][0]['coefficient_id'] = 'shared'
    elif attack == 'parameter_root': certificate['parameter_root'] = '0'*64
    else: certificate['scope'] = 'EXISTENCE_AND_ALL_SIGNED_ROOTS'
    result = u.verify_coupled_tree_univalence(model, reroot(certificate))
    assert result['status'] != 'PASS' and not result['proof_complete']


@pytest.mark.parametrize('budget', [{'max_leaves': 2}, {'max_terms': 2}, {'max_work': 1},
                                  {'max_input_bytes': 256}, {'max_certificate_bytes': 256}])
def test_bounded_resources_return_unknown(budget):
    model, _ = example()
    assert u.compile_coupled_tree_univalence(model, **budget)['status'] == 'UNKNOWN'


def test_huge_rational_and_large_proof_shape_stop_before_authority():
    model, _ = example()
    model['coefficients']['singleton'] = interval(2**40)
    assert u.compile_coupled_tree_univalence(model, max_rational_bits=32)['status'] == 'UNKNOWN'
    model, _ = example()
    certificate = u.compile_coupled_tree_univalence(model)
    certificate['hierarchy'] *= 100
    assert u.verify_coupled_tree_univalence(model, certificate)['status'] == 'UNKNOWN'


@pytest.mark.parametrize('phase', ['producer', 'verifier'])
def test_final_callback_mutation_cannot_publish_proof(phase):
    model, _ = example()
    certificate = u.compile_coupled_tree_univalence(model)
    def callback(stage):
        if stage == 'univalence_' + phase + '_complete':
            model['available_heads']['a']['upper'] = '900'
    result = (u.compile_coupled_tree_univalence(model, checkpoint=callback) if phase == 'producer'
              else u.verify_coupled_tree_univalence(model, certificate, checkpoint=callback))
    assert result['status'] != 'PASS' and result['status'] != 'CERTIFIED_UNIVALENCE'


def test_late_certificate_mutation_and_caller_exception_identity():
    model, _ = example()
    certificate = u.compile_coupled_tree_univalence(model)
    def mutate(stage):
        if stage == 'univalence_verifier_complete': certificate['hierarchy'].clear()
    assert u.verify_coupled_tree_univalence(model, certificate, checkpoint=mutate)['status'] == 'FAIL'
    error = ValueError('caller cancellation')
    def cancel(stage): raise error
    with pytest.raises(ValueError) as caught:
        u.compile_coupled_tree_univalence(model, checkpoint=cancel)
    assert caught.value is error


def test_composition_requires_two_replays_same_full_model_and_local_existence(monkeypatch):
    model, box = example(2)
    global_proof = u.compile_coupled_tree_univalence(model)
    local_proof = local.compile_coupled_tree_pressure(model, box)
    assert local_proof['status'] == 'CERTIFIED_BOX', local_proof
    monkeypatch.setattr(local, 'compile_coupled_tree_pressure', lambda *a, **k: pytest.fail('Local producer used'))
    monkeypatch.setattr(u, 'compile_coupled_tree_univalence', lambda *a, **k: pytest.fail('Global producer used'))
    result = u.verify_coupled_tree_nonnegative_family(model, box, local_proof, global_proof)
    assert result['status'] == 'PASS', result
    assert result['model_root'] == local_proof['model_root'] == global_proof['model_root']
    assert result['scope'] == u.COMPOSED_SCOPE
    model['coefficients']['shared'] = interval(Q(1, 10), Q(1, 9))
    assert u.verify_coupled_tree_nonnegative_family(model, box, local_proof, global_proof)['status'] != 'PASS'


@pytest.mark.parametrize('attack', ['bad_local', 'other_box', 'budget', 'late_model', 'late_global_proof', 'late_local_proof'])
def test_composed_certificate_failures_cannot_claim_existence_or_global_unique_family(attack):
    model, box = example(2)
    global_proof = u.compile_coupled_tree_univalence(model)
    local_proof = local.compile_coupled_tree_pressure(model, box)
    options = {}
    if attack == 'bad_local': local_proof['contraction_norm_upper'] = '2'
    elif attack == 'other_box': box['a'] = interval(5, 6)
    elif attack == 'budget': options['max_work'] = 1
    else:
        def mutate(stage):
            if stage == 'univalence_composition_complete':
                if attack == 'late_model': model['context_root'] = 'c'*64
                elif attack == 'late_global_proof': global_proof['scope'] = 'false'
                else: local_proof['scope'] = 'false'
        options['checkpoint'] = mutate
    result = u.verify_coupled_tree_nonnegative_family(model, box, local_proof, global_proof, **options)
    assert result['status'] != 'PASS' and not result['proof_complete']


def test_virtual_zero_update_root_and_multiple_shared_singleton_terms():
    model, _ = example()
    model['terms'] = [t for t in model['terms'] if t['id'].startswith('singleton-')]
    del model['coefficients']['shared']
    extra = deepcopy(model['terms'][0]); extra['id'] = 'second-a'
    model['terms'].append(extra)
    proof = u.compile_coupled_tree_univalence(model)
    root = next(row for row in proof['hierarchy'] if row['parent'] is None)
    assert root['term_ids'] == [] and all(not terms for terms in root['row_terms'].values())
    assert proof['leaf_witnesses']['a']['coefficient_lower_sum'] == '2'
    assert u.verify_coupled_tree_univalence(model, proof)['status'] == 'PASS'


def test_univalence_alone_is_available_even_when_positive_existence_is_false():
    model, box = example(2)
    model['available_heads'] = {i: interval(-1) for i in model['leaves']}
    proof = u.compile_coupled_tree_univalence(model)
    assert proof['status'] == 'CERTIFIED_UNIVALENCE'
    assert u.verify_coupled_tree_univalence(model, proof)['status'] == 'PASS'
    # Every positive term is nonnegative, while head=-1 forces F_i(q)>0.
    assert local.compile_coupled_tree_pressure(model, box)['status'] == 'UNKNOWN'


@pytest.mark.parametrize('composed', [False, True])
def test_final_guard_work_is_counted_in_total_budget(composed):
    model, box = example(2)
    proof = u.compile_coupled_tree_univalence(model)
    local_proof = local.compile_coupled_tree_pressure(model, box)
    run = (lambda **kw: u.verify_coupled_tree_nonnegative_family(model, box, local_proof, proof, **kw)) if composed else (lambda **kw: u.verify_coupled_tree_univalence(model, proof, **kw))
    passed = run()
    assert passed['status'] == 'PASS'
    stopped = run(max_work=passed['work']-1)
    assert stopped['status'] == 'UNKNOWN' and stopped['work'] <= passed['work']


def test_composed_late_cancellation_preserves_exception_identity():
    model, box = example(2)
    proof = u.compile_coupled_tree_univalence(model)
    local_proof = local.compile_coupled_tree_pressure(model, box)
    error = ValueError('late caller deadline')
    def checkpoint(stage):
        if stage == 'univalence_composition_complete': raise error
    with pytest.raises(ValueError) as caught:
        u.verify_coupled_tree_nonnegative_family(model, box, local_proof, proof, checkpoint=checkpoint)
    assert caught.value is error


def test_parameter_box_local_proof_and_univalence_use_exact_shared_coefficient_identity():
    model, box = example(2)
    model['coefficients']['shared'] = interval(Q(999, 10000), Q(1001, 10000))
    proof = u.compile_coupled_tree_univalence(model)
    local_proof = local.compile_coupled_tree_pressure(model, box)
    assert local_proof['status'] == 'CERTIFIED_BOX'
    result = u.verify_coupled_tree_nonnegative_family(model, box, local_proof, proof)
    assert result['status'] == 'PASS'
    assert result['parameter_root'] == proof['parameter_root'] == local_proof['parameter_root']


@pytest.mark.parametrize('field', ['true_premise', 'false_premise', 'limitation', 'integer_count'])
def test_resealed_boolean_integer_schema_substitution_is_rejected(field):
    model, _ = example(1)
    proof = u.compile_coupled_tree_univalence(model)
    if field == 'true_premise': proof['polarization']['same_parameter_tuple'] = 1
    elif field == 'false_premise': proof['polarization']['entrywise_nonnegative_inverse_required'] = 0
    elif field == 'limitation': proof['limitations']['existence_proved_by_univalence_alone'] = 0
    else: proof['counts']['leaves'] = True
    assert u.verify_coupled_tree_univalence(model, reroot(proof))['status'] == 'FAIL'
