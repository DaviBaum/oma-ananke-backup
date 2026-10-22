from collections import Counter
from copy import deepcopy
from itertools import product
import json
import random

import pytest

from oma.optimization.separator import (
    Region, compile_separator, verify_separator, reconstruct_separator_choices,
    substitute_labeled_menu,
)


def shared_capacity_model():
    """Synthetic two-demand joint scenario traces; hidden brackets repeat labels."""
    loads = {'east': (2, 0), 'west': (0, 2), 'east_bracket': (2, 0)}
    carriers = {name: tuple(loads) for name in ('A', 'B')}
    regions = [Region(name, (), {choice: {(): state} for choice, state in
                                 ((state, state) for state in loads)}) for name in carriers]
    merge = {(a, b): str(tuple(x + y for x, y in zip(loads[a], loads[b])))
             for a, b in product(loads, repeat=2)}
    carriers['R'] = tuple(sorted(set(merge.values())))
    regions.append(Region('R', ('A', 'B'), {'assemble': merge}))
    outputs = {name: {state: ('DEFINED', 'EVIDENCE_CURRENT') for state in loads} for name in ('A', 'B')}
    outputs['R'] = {state: {'joint_scenario_loads': json.loads(state.replace('(', '[').replace(')', ']')),
                            'universal_capacity_pass': state == '(2, 2)'} for state in carriers['R']}
    return carriers, tuple(regions), outputs


def exhaustive(carriers, regions, outputs, cert):
    """Independent raw source assignment evaluation, retaining every label tuple."""
    nodes = {node.name: node for node in regions}
    names = sorted(nodes)
    index = {tuple(state): i for i, state in enumerate(cert['fdqa']['states'])}
    counts = Counter()
    outcomes = Counter()
    for choices in product(*(nodes[name].choices for name in names)):
        assignment = dict(zip(names, choices))
        def visit(name):
            node = nodes[name]
            return node.choices[assignment[name]][tuple(visit(child) for child in node.children)]
        state = visit(cert['root_region'])
        counts[cert['fdqa']['block_of'][index[cert['root_region'], state]]] += 1
        outcomes[json.dumps(outputs[cert['root_region']][state], sort_keys=True)] += 1
    return counts, outcomes


def test_joint_scenario_capacity_and_labels_match_exhaustive_ground_truth():
    carriers, regions, outputs = shared_capacity_model()
    cert = compile_separator(carriers, regions, outputs, root_region='R', context_root='two-demands-two-scenarios')
    assert cert['status'] == 'EXACT_FINITE_SEPARATOR'
    assert cert['metrics']['message_counts'] == {'A': 2, 'B': 2, 'R': 3}
    assert cert['metrics']['root_labeled_realization_count'] == 9
    assert sorted(row['count'] for row in cert['messages']['R']) == [1, 4, 4]
    assert verify_separator(carriers, regions, outputs, json.loads(json.dumps(cert)),
                            root_region='R', context_root='two-demands-two-scenarios')['status'] == 'PASS'
    counts, _ = exhaustive(carriers, regions, outputs, cert)
    assert counts == {row['block']: row['count'] for row in cert['messages']['R']}
    # Opposite correlated traces have identical unordered marginal values but
    # different behavior against a fixed sibling, so cannot be merged.
    ids = {tuple(state): i for i, state in enumerate(cert['fdqa']['states'])}
    labels = cert['fdqa']['block_of']
    assert labels[ids['A', 'east']] != labels[ids['A', 'west']]
    assert labels[ids['A', 'east']] == labels[ids['A', 'east_bracket']]
    for row in cert['messages']['R']:
        assignment = reconstruct_separator_choices(cert, row['block'])
        menu = substitute_labeled_menu(carriers, regions, outputs, cert, {'witness': assignment},
                                      root_region='R', context_root='two-demands-two-scenarios')
        assert menu['profiles']['witness']['block'] == row['block']


@pytest.mark.parametrize('field', ['count', 'witness', 'missing', 'extra', 'metrics', 'transition', 'root', 'tree'])
def test_independent_separator_checker_rejects_tampering(field):
    carriers, regions, outputs = shared_capacity_model()
    cert = compile_separator(carriers, regions, outputs, root_region='R', context_root='scope')
    if field == 'count': cert['messages']['A'][0]['count'] += 1
    elif field == 'witness': cert['messages']['R'][0]['witness']['children'] = [999, 999]
    elif field == 'missing': cert['messages']['R'].pop()
    elif field == 'extra': cert['messages']['R'].append(deepcopy(cert['messages']['R'][0]))
    elif field == 'metrics': cert['metrics']['root_message_count'] -= 1
    elif field == 'transition':
        operation = next(op['name'] for op in cert['fdqa']['operations'] if op['output'] == 'R')
        cert['fdqa']['transitions'][operation][0]['result'] = 999
    elif field == 'root': cert['root'] = 'different'
    else: cert['tree'][0]['choices'] = []
    assert verify_separator(carriers, regions, outputs, cert, root_region='R', context_root='scope')['status'] == 'FAIL'


def test_root_memory_cost_is_not_bounded_by_largest_nonroot_message():
    n = 8
    carriers = {'A': tuple(map(str, range(n))), 'B': tuple(map(str, range(n)))}
    regions = [Region(name, (), {state: {(): state} for state in values}) for name, values in carriers.items()]
    rows = {(a, b): f'{a}:{b}' for a, b in product(carriers['A'], carriers['B'])}
    carriers['R'] = tuple(rows.values())
    regions.append(Region('R', ('A', 'B'), {'pair': rows}))
    outputs = {name: {state: (state if name == 'R' else None) for state in values} for name, values in carriers.items()}
    cert = compile_separator(carriers, regions, outputs, root_region='R', context_root='root-width')
    metrics = cert['metrics']
    assert metrics['max_nonroot_message_bits'] == 3
    assert metrics['root_message_bits'] == 6
    assert metrics['stored_message_count_including_root'] == 8 + 8 + 64
    assert verify_separator(carriers, regions, outputs, cert, root_region='R', context_root='root-width')['status'] == 'PASS'


def test_original_menu_multiplicity_preserved_for_non_duplicate_invariant_rule():
    carriers, regions, outputs = shared_capacity_model()
    cert = compile_separator(carriers, regions, outputs, root_region='R', context_root='menu')
    assignment = {'A': 'east', 'B': 'west', 'R': 'assemble'}
    menu = {label: assignment for label in ('original', 'identical_other', 'another')}
    replaced = substitute_labeled_menu(carriers, regions, outputs, cert, menu, root_region='R', context_root='menu')
    choose = lambda profiles: set(profiles) if len(profiles) >= 3 else set()
    assert replaced['preserved_label_count'] == 3
    assert choose(replaced['profiles']) == set(menu)
    assert choose({'one_quotient_representative': next(iter(replaced['profiles'].values()))}) == set()


def test_random_complete_merge_tables_match_exhaustive_assignment_counts():
    rng = random.Random(917)
    for example in range(24):
        carriers = {'A': ('a', 'b', 'c'), 'B': ('x', 'y')}
        regions = [Region('A', (), {'a0': {(): 'a'}, 'a1': {(): 'a'}, 'b': {(): 'b'}, 'c': {(): 'c'}}),
                   Region('B', (), {'x': {(): 'x'}, 'y': {(): 'y'}})]
        rows = {(a, b): str(rng.randrange(4)) for a, b in product(carriers['A'], carriers['B'])}
        carriers['R'] = tuple(sorted(set(rows.values())))
        regions.append(Region('R', ('A', 'B'), {'join': rows}))
        outputs = {name: {state: (rng.randrange(2) if name == 'R' else None) for state in states}
                   for name, states in carriers.items()}
        cert = compile_separator(carriers, regions, outputs, root_region='R', context_root=str(example))
        assert verify_separator(carriers, regions, outputs, cert, root_region='R', context_root=str(example))['status'] == 'PASS'
        counts, _ = exhaustive(carriers, regions, outputs, cert)
        assert counts == {row['block']: row['count'] for row in cert['messages']['R']}


def test_undefined_and_defined_infeasible_remain_distinct_without_pruning():
    carriers = {'A': ('good', 'bad', 'undefined'), 'R': ('feasible', 'infeasible', 'undefined')}
    regions = (Region('A', (), {'a': {(): 'good'}, 'b': {(): 'bad'}, 'u': {(): 'undefined'}}),
               Region('R', ('A',), {'join': {('good',): 'feasible', ('bad',): 'infeasible', ('undefined',): 'undefined'}}))
    outputs = {name: {state: state for state in states} for name, states in carriers.items()}
    undefined = {'A': 'undefined', 'R': 'undefined'}
    cert = compile_separator(carriers, regions, outputs, root_region='R', context_root='failures', undefined=undefined)
    assert len(cert['messages']['R']) == 3
    assert verify_separator(carriers, regions, outputs, cert, root_region='R', context_root='failures', undefined=undefined)['status'] == 'PASS'


def test_budget_changed_context_and_illegal_decompositions():
    carriers, regions, outputs = shared_capacity_model()
    cert = compile_separator(carriers, regions, outputs, root_region='R', context_root='scope')
    assert compile_separator(carriers, regions, outputs, root_region='R', context_root='scope', max_work=0)['status'] == 'UNKNOWN'
    assert verify_separator(carriers, regions, outputs, cert, root_region='R', context_root='scope', max_work=10)['status'] == 'UNKNOWN'
    assert verify_separator(carriers, regions, outputs, cert, root_region='R', context_root='changed')['status'] == 'FAIL'
    with pytest.raises(ValueError, match='Distinct declared children'):
        compile_separator(carriers, regions[:2] + (Region('R', ('A', 'A'), {'join': {}}),), outputs, root_region='R', context_root='bad')
    with pytest.raises(ValueError, match='Incomplete operation table'):
        compile_separator(carriers, regions[:2] + (Region('R', ('A', 'B'), {'join': {}}),), outputs, root_region='R', context_root='bad')
    with pytest.raises(ValueError, match='tree'):
        compile_separator(carriers, (Region('A', ('B',), {'x': {}}), regions[1], regions[2]), outputs, root_region='R', context_root='bad')
