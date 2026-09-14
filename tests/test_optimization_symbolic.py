from collections import Counter
from copy import deepcopy
from itertools import combinations, product
import json
from math import comb
import random

import pytest

from oma.optimization.symbolic import BooleanTheory, compile_symbolic, verify_symbolic


class Circuit:
    def __init__(self, variables):
        self.variables, self.gates = tuple(variables), [('const', False), ('const', True)]
        self.ids = {name: self.add('var', name) for name in variables}

    def add(self, *gate):
        self.gates.append(gate)
        return len(self.gates)-1


def forty_module_model(n=40, threshold=4):
    """Original P4's cardinality fixture under corrected fixed-width activation.

    Activating the first inactive module is a total map on the fixed XOR domain.
    It is not literal append or a physical building alteration.
    """
    if not 1 <= threshold <= n:
        raise ValueError('Every unsaturated and saturated count must be reachable')
    circuit = Circuit([name for i in range(n) for name in (f'a{i}', f'b{i}')])
    domain, prefix = 1, 1
    at_least = [1] + [0]*threshold
    replacements = []
    for i in range(n):
        a, b = circuit.ids[f'a{i}'], circuit.ids[f'b{i}']
        domain = circuit.add('and', domain, circuit.add('xor', a, b))
        at_least = [1] + [circuit.add('or', at_least[j], circuit.add('and', a, at_least[j-1]))
                         for j in range(1, threshold+1)]
        active = circuit.add('or', a, prefix)
        replacements += [active, circuit.add('not', active)]
        prefix = circuit.add('and', prefix, a)
    saturated = at_least[threshold]
    not_saturated = circuit.add('not', saturated)
    return BooleanTheory(circuit.variables, tuple(circuit.gates), domain,
                         {'saturated': (saturated, True), 'unsaturated': (not_saturated, False)},
                         {'activate_first_inactive': tuple(replacements)})


def raw_evaluate(theory, assignment):
    values = []
    by_name = dict(zip(theory.variables, assignment))
    for gate in theory.gates:
        if gate[0] == 'const': value = gate[1]
        elif gate[0] == 'var': value = by_name[gate[1]]
        elif gate[0] == 'not': value = not values[gate[1]]
        elif gate[0] == 'and': value = values[gate[1]] and values[gate[2]]
        elif gate[0] == 'or': value = values[gate[1]] or values[gate[2]]
        else: value = values[gate[1]] != values[gate[2]]
        values.append(value)
    return values


def predicate(certificate, root, assignment):
    while root >= 2:
        variable, low, high = certificate['nodes'][root-2]
        root = high if assignment[variable] else low
    return bool(root)


def test_trillion_state_symbolic_discovery_checks_without_state_enumeration():
    theory = forty_module_model()
    cert = compile_symbolic(theory, context_root='original-p4-corrected-total-activation')
    assert cert['status'] == 'EXACT_BOOLEAN_SYMBOLIC_QUOTIENT'
    assert cert['domain_count'] == 2**40
    assert len(cert['blocks']) == 5
    assert cert['metrics']['accepted_binary_splits'] == 3
    assert cert['metrics']['concrete_states_enumerated'] == 0
    assert sorted(row['count'] for row in cert['blocks']) == [1, 40, 780, 9880, 2**40-sum(comb(40,k) for k in range(4))]
    result = verify_symbolic(theory, json.loads(json.dumps(cert)), context_root='original-p4-corrected-total-activation')
    assert result['status'] == 'PASS'
    assert result['verified_distinguishers'] == 10


def test_small_xor_fixture_matches_all_concrete_assignments_and_contexts():
    theory = forty_module_model(4, 3)
    cert = compile_symbolic(theory, context_root='small')
    counts = Counter()
    for assignment in product((False, True), repeat=len(theory.variables)):
        values = raw_evaluate(theory, assignment)
        matches = [i for i, row in enumerate(cert['blocks']) if predicate(cert, row['predicate'], assignment)]
        assert len(matches) == int(values[theory.domain])
        if not matches:
            continue
        block = matches[0]
        counts[block] += 1
        for name, roots in theory.contexts.items():
            following = [values[root] for root in roots]
            assert predicate(cert, cert['blocks'][cert['transitions'][name][block]]['predicate'], following)
    assert [counts[i] for i in range(len(cert['blocks']))] == [row['count'] for row in cert['blocks']]


def test_random_boolean_contexts_match_exhaustive_residual_distinctions():
    rng = random.Random(29)
    for example in range(18):
        circuit = Circuit(['a', 'b', 'c'])
        for _ in range(12):
            circuit.add(rng.choice(('and', 'or', 'xor')), rng.randrange(len(circuit.gates)), rng.randrange(len(circuit.gates)))
        output = rng.randrange(2, len(circuit.gates))
        inverse = circuit.add('not', output)
        contexts = {name: tuple(rng.randrange(len(circuit.gates)) for _ in range(3)) for name in ('k', 'l')}
        theory = BooleanTheory(circuit.variables, tuple(circuit.gates), 1,
                              {'true': (output, True), 'false': (inverse, False)}, contexts)
        cert = compile_symbolic(theory, context_root=str(example))
        assert verify_symbolic(theory, cert, context_root=str(example))['status'] == 'PASS'
        assignments = tuple(product((False, True), repeat=3))
        evaluations = {x: raw_evaluate(theory, x) for x in assignments}
        state_block = {x: next(i for i, row in enumerate(cert['blocks']) if predicate(cert, row['predicate'], x)) for x in assignments}
        for a, b in combinations(assignments, 2):
            pending, seen, distinct = [(a, b)], set(), False
            while pending:
                pair = pending.pop()
                if pair in seen: continue
                seen.add(pair)
                x, y = pair
                if evaluations[x][output] != evaluations[y][output]:
                    distinct = True
                    break
                for roots in contexts.values():
                    pending.append((tuple(evaluations[x][i] for i in roots), tuple(evaluations[y][i] for i in roots)))
            assert distinct == (state_block[a] != state_block[b])


@pytest.mark.parametrize('field', ['count', 'missing', 'overlap', 'transition', 'witness', 'representative', 'diagram', 'metrics', 'root'])
def test_symbolic_checker_rejects_tampered_certificate(field):
    theory = forty_module_model(4, 3)
    cert = compile_symbolic(theory, context_root='check')
    if field == 'count': cert['blocks'][0]['count'] += 1
    elif field == 'missing': cert['blocks'].pop()
    elif field == 'overlap': cert['blocks'].append(deepcopy(cert['blocks'][0]))
    elif field == 'transition': cert['transitions']['activate_first_inactive'][0] = 999
    elif field == 'witness': cert['distinguishers'].pop()
    elif field == 'representative': cert['blocks'][0]['representative'] = [False]*8
    elif field == 'diagram': cert['nodes'][0][1] = 999
    elif field == 'metrics': cert['metrics']['accepted_binary_splits'] += 1
    else: cert['root'] = 'changed'
    assert verify_symbolic(theory, cert, context_root='check')['status'] == 'FAIL'


def test_context_totality_output_coverage_and_resource_limits():
    theory = forty_module_model(3, 2)
    cert = compile_symbolic(theory, context_root='scope')
    assert compile_symbolic(theory, context_root='scope', max_nodes=2)['status'] == 'UNKNOWN'
    assert compile_symbolic(theory, context_root='scope', max_work=0)['status'] == 'UNKNOWN'
    assert verify_symbolic(theory, cert, context_root='scope', max_work=10)['status'] == 'UNKNOWN'
    assert verify_symbolic(theory, cert, context_root='other')['status'] == 'FAIL'
    invalid = BooleanTheory(theory.variables, theory.gates, theory.domain, theory.outputs, {'invalid': (0,)*6})
    with pytest.raises(ValueError, match='not total'):
        compile_symbolic(invalid, context_root='invalid')
    incomplete = BooleanTheory(theory.variables, theory.gates, theory.domain, {'only': theory.outputs['saturated']}, {})
    with pytest.raises(ValueError, match='omit'):
        compile_symbolic(incomplete, context_root='invalid')
    overlapping = BooleanTheory(theory.variables, theory.gates, theory.domain, {'a': (1, True), 'b': (1, False)}, {})
    with pytest.raises(ValueError, match='overlap'):
        compile_symbolic(overlapping, context_root='invalid')


def test_equal_output_fibers_merge_and_empty_domain_is_separate():
    circuit = Circuit(['x'])
    opposite = circuit.add('not', circuit.ids['x'])
    theory = BooleanTheory(circuit.variables, tuple(circuit.gates), 1,
                          {'one': (circuit.ids['x'], 'same'), 'two': (opposite, 'same')}, {})
    cert = compile_symbolic(theory, context_root='same')
    assert len(cert['blocks']) == 1 and cert['blocks'][0]['count'] == 2
    assert verify_symbolic(theory, cert, context_root='same')['status'] == 'PASS'
    empty = BooleanTheory(circuit.variables, tuple(circuit.gates), 0, theory.outputs, {})
    assert compile_symbolic(empty, context_root='empty')['status'] == 'EMPTY_FINITE_DOMAIN'
