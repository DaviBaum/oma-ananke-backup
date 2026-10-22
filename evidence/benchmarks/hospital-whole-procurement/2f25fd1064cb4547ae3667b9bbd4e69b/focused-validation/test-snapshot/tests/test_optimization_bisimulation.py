from copy import deepcopy
from itertools import product
import json
import random

import pytest

from oma.optimization.bisimulation import (
    NondeterministicAction as Action, compile_bisimulation, verify_bisimulation,
)


def branching_model():
    states = ('p', 'q', 'b_only', 'c_only', 'both', 'done')
    rows = {a: {s: () for s in states} for a in ('a', 'b', 'c')}
    rows['a']['p'] = ('b_only', 'c_only')
    rows['a']['q'] = ('both',)
    rows['b']['b_only'] = rows['b']['both'] = ('done',)
    rows['c']['c_only'] = rows['c']['both'] = ('done',)
    return {'S': states}, tuple(Action(a, 'S', 'S', r) for a, r in rows.items()), {'S': {s: int(s == 'done') for s in states}}


def compile_model(model, **kwargs):
    return compile_bisimulation(*model, context_root='complete-synthetic-model-v1', **kwargs)


def check_model(model, cert, **kwargs):
    return verify_bisimulation(*model, cert, context_root='complete-synthetic-model-v1', **kwargs)


def label(cert, state, sort='S'):
    return cert['block_of'][cert['states'].index([sort, state])]


def test_branching_distinction_survives_identical_linear_trace_observations():
    model = branching_model()
    _, actions, observations = model
    # A linear trace records only reached terminal observations. Every possible
    # word has the same outcome set from p and q; choices are resolved at
    # different times, which strong bisimulation must preserve.
    for length in range(6):
        for word in product(range(3), repeat=length):
            result = []
            for start in ('p', 'q'):
                reached = {start}
                for a in word:
                    reached = {t for s in reached for t in actions[a].transitions[s]}
                result.append({observations['S'][s] for s in reached})
            assert result[0] == result[1]
    cert = compile_model(model)
    assert cert['status'] == 'EXACT_FINITE_STRONG_BISIMULATION'
    assert label(cert, 'p') != label(cert, 'q')
    assert cert['strict_refinement_rounds'] >= 2
    checked = check_model(model, json.loads(json.dumps(cert)))
    assert checked['status'] == 'PASS'
    assert checked['verified_separated_block_pairs'] == 15
    assert any(n['op'] == 'not' for n in cert['modal_nodes'])


def test_disabled_action_distinct_from_enabled_stuttering_and_multiplicity_ignored():
    model = ({'S': ('off', 'one', 'two')},
             (Action('step', 'S', 'S', {'off': (), 'one': ('one',), 'two': ('one', 'two')}),),
             {'S': {'off': 0, 'one': 0, 'two': 0}})
    cert = compile_model(model)
    assert label(cert, 'off') != label(cert, 'one') == label(cert, 'two')
    assert check_model(model, cert)['status'] == 'PASS'


def test_typed_actions_same_state_names_and_same_observations_do_not_merge_sorts():
    model = ({'A': ('x', 'y'), 'B': ('x', 'y')},
             (Action('join', 'A', 'B', {'x': ('x',), 'y': ('x', 'y')}),),
             {'A': {'x': 0, 'y': 0}, 'B': {'x': 1, 'y': 1}})
    cert = compile_model(model)
    assert len(cert['blocks']) == 2
    assert label(cert, 'x', 'A') == label(cert, 'y', 'A')
    assert label(cert, 'x', 'A') != label(cert, 'x', 'B')
    assert check_model(model, cert)['status'] == 'PASS'


@pytest.mark.parametrize('field', ['root', 'states', 'actions', 'blocks', 'block_of', 'observations', 'transitions', 'modal_nodes', 'characteristic_formulas', 'scope'])
def test_independent_verifier_rejects_tampering(field):
    model = branching_model()
    cert = compile_model(model)
    cert[field] = 'corrupted'
    assert check_model(model, cert)['status'] == 'FAIL'


def test_bisimulation_stability_alone_cannot_certify_an_overrefined_quotient():
    model = ({'S': ('x', 'y')}, (Action('a', 'S', 'S', {'x': ('x',), 'y': ('y',)}),), {'S': {'x': 0, 'y': 0}})
    cert = compile_model(model)
    assert len(cert['blocks']) == 1
    # This singleton partition is stable, but is not coarsest. No modal formula
    # can distinguish x from y, so both claimed characteristic formulas fail.
    cert.update(blocks=[[0], [1]], block_of=[0, 1], observations=cert['observations'] * 2,
                transitions=[[{'source': 0, 'targets': [0]}, {'source': 1, 'targets': [1]}]],
                characteristic_formulas=[0, 0])
    result = check_model(model, cert)
    assert result['status'] == 'FAIL'
    assert 'characterize' in result['reason']


@pytest.mark.parametrize('mutation', ['cycle', 'wrong_sort', 'wrong_action', 'true_for_everything'])
def test_modal_certificate_is_replayed_and_type_checked(mutation):
    model = branching_model()
    cert = compile_model(model)
    if mutation == 'cycle':
        cert['modal_nodes'][0] = {'op': 'not', 'child': 0}
    elif mutation == 'wrong_sort':
        cert['modal_nodes'][0]['sort'] = 'Missing'
    elif mutation == 'wrong_action':
        node = next(n for n in cert['modal_nodes'] if n['op'] == 'diamond')
        node['action'] = True
    else:
        cert['modal_nodes'][0] = {'op': 'and', 'sort': 'S', 'children': []}
        cert['characteristic_formulas'] = [0] * len(cert['blocks'])
    assert check_model(model, cert)['status'] == 'FAIL'


def test_unstable_merge_and_missing_disabled_quotient_rows_fail():
    model = branching_model()
    cert = compile_model(model)
    q = label(cert, 'p')
    row = next(r for r in cert['transitions'][0] if r['source'] == q)
    row['targets'] = []
    assert 'Successor block' in check_model(model, cert)['reason']
    cert = compile_model(model)
    cert['transitions'][0].pop()
    assert check_model(model, cert)['status'] == 'FAIL'


def test_relation_and_observation_family_changes_invalidate_unchanged_state_ids():
    model = branching_model()
    cert = compile_model(model)
    carriers, actions, observations = deepcopy(model)
    actions[0].transitions['p'] = ('both',)
    assert check_model((carriers, actions, observations), cert)['status'] == 'FAIL'
    assert verify_bisimulation(*model, cert, context_root='new-observation-family')['status'] == 'FAIL'
    carriers, actions, observations = deepcopy(model)
    observations['S']['p'] = [0, 'new-evidence']
    assert check_model((carriers, actions, observations), cert)['status'] == 'FAIL'


@pytest.mark.parametrize('mutation', ['missing_row', 'unknown_successor', 'duplicate_successor', 'unknown_target', 'missing_observation'])
def test_incomplete_or_ill_typed_models_cannot_be_treated_as_disabled(mutation):
    carriers, actions, observations = deepcopy(branching_model())
    if mutation == 'missing_row':
        del actions[0].transitions['p']
    elif mutation == 'unknown_successor':
        actions[0].transitions['p'] = ('unknown',)
    elif mutation == 'duplicate_successor':
        actions[0].transitions['p'] = ('both', 'both')
    elif mutation == 'unknown_target':
        actions = (Action('a', 'S', 'Unknown', actions[0].transitions),)
    else:
        del observations['S']['p']
    with pytest.raises(ValueError):
        compile_model((carriers, actions, observations))


def test_budget_exhaustion_is_unknown_and_no_action_model_is_valid():
    model = branching_model()
    assert compile_model(model, max_work=0)['status'] == 'UNKNOWN'
    cert = compile_model(model)
    assert check_model(model, cert, max_work=0)['status'] == 'UNKNOWN'
    model = ({'S': ('x', 'y', 'z')}, (), {'S': {'x': 0, 'y': 0, 'z': 1}})
    cert = compile_model(model)
    assert len(cert['blocks']) == 2 and check_model(model, cert)['status'] == 'PASS'


def greatest_relation_ground_truth(states, actions, observations):
    # Independent elimination of inconsistent *pairs*, not block refinement.
    relation = {(x, y) for x in states for y in states if observations[x] == observations[y]}
    while True:
        keep = set()
        for x, y in relation:
            if all(all(any((u, v) in relation for v in a.transitions[y]) for u in a.transitions[x])
                   and all(any((u, v) in relation for u in a.transitions[x]) for v in a.transitions[y])
                   for a in actions):
                keep.add((x, y))
        if keep == relation:
            return keep
        relation = keep


def test_eighty_random_nondeterministic_systems_match_independent_greatest_relation():
    rng = random.Random(87281)
    for _ in range(80):
        states = tuple(str(i) for i in range(rng.randint(2, 7)))
        actions = tuple(Action(a, 'S', 'S', {s: tuple(t for t in states if rng.random() < .25) for s in states}) for a in ('act', 'inspect'))
        observations = {s: rng.randrange(2) for s in states}
        model = {'S': states}, actions, {'S': observations}
        ground = greatest_relation_ground_truth(states, actions, observations)
        cert = compile_model(model)
        assert check_model(model, cert)['status'] == 'PASS'
        for x in states:
            for y in states:
                assert (label(cert, x) == label(cert, y)) == ((x, y) in ground)
