from copy import deepcopy
from itertools import product
import json
import random

import pytest

from oma.optimization.fdqa import Operation, compile_fdqa, verify_fdqa, evaluate_compiled_term


def hotel_model():
    """Original 1-10 Pages P2 paragraphs6616-6918; native table1736215.

    The table supplies every feasible pattern's damaged inline metric formulas.
    No missing prose equation or disordered example tuple is reconstructed.
    """
    pattern_rows = (
        (0,0,0,0,102,24,30), (0,0,0,1,100,27,30), (0,0,1,0,103,24,32),
        (0,1,0,0,100,20,29), (0,1,0,1,98,23,29), (0,1,1,0,101,20,31),
        (0,1,1,1,99,23,31), (1,0,0,0,105,24,31), (1,0,0,1,103,27,31),
        (1,0,1,0,106,24,33), (1,1,0,0,103,20,30), (1,1,1,0,104,20,32),
    )
    patterns = {r[:4]: r[4:] for r in pattern_rows}
    assignments = {''.join(map(str, row)): dict(zip(('s','g','h','e','v','c','b','d'), row))
                   for row in product((0,1), repeat=8)}
    carriers = {sort: tuple(assignments) for sort in ('B','U','P')}
    outputs = {sort: {} for sort in carriers}
    for state, x in assignments.items():
        for sort in carriers:
            if x['g'] and x['h'] and x['d']:
                out = ('beamFail',)
            elif x['c'] and not x['h'] and x['d']:
                out = ('sequenceFail',)
            else:
                cost, fan, schedule = patterns[x['g'],x['h'],x['c'],x['d']]
                out = ('feasible', cost+2*x['s']+x['v'], fan+2*x['s'], schedule, 2-x['v'])
                if sort == 'P':
                    out += ('pass' if x['e'] == 0 else 'fail',)
            outputs[sort][state] = out
    operations = tuple(Operation('atom_'+state, (), 'B', {():state}) for state in assignments)
    operations += (Operation('clearance850', ('B',), 'U', {(x,):x for x in assignments}),
                   Operation('replace', ('U',), 'P', {(x,):x for x in assignments}))
    return carriers, operations, outputs


def test_original_hotel_depth_two_quotient_complete_independent_certificate():
    carriers, ops, outputs = hotel_model()
    cert = compile_fdqa(carriers, ops, outputs, context_root='original-pages-p2-hotel-table1736215')
    assert cert['status'] == 'EXACT_FINITE_FDQA'
    assert cert['refinement_counts'] == [dict(B=50,P=98,U=50), dict(B=50,P=98,U=98), dict(B=98,P=98,U=98)]
    assert cert['strict_refinement_rounds'] == 2
    assert len(cert['blocks']) == 294
    checked = verify_fdqa(carriers, ops, outputs, cert, context_root='original-pages-p2-hotel-table1736215')
    assert checked['status'] == 'PASS'
    assert checked['verified_distinguishers'] == 3 * (98 * 97 // 2)
    pair = {tuple(state): i for i, state in enumerate(cert['states'])}
    compact = cert['block_of'][pair['B','00001000']]
    standard = cert['block_of'][pair['B','00011000']]
    bracket_b = cert['block_of'][pair['B','00001010']]
    assert compact == bracket_b != standard
    witness = next(w for w in cert['distinguishers'] if {w['first'],w['second']} == {compact,standard})
    assert [cert['primitive_manifest'][i]['operation'] for i in witness['actions']] == ['clearance850','replace']
    compiled = evaluate_compiled_term(cert, ('replace', (('clearance850', (('atom_00001000', ()),)),)))
    assert compiled['sort'] == 'P'
    assert compiled['block'] == cert['block_of'][pair['P','00001000']]
    # Plain JSON round trips preserve the certificate, including fixed arguments.
    roundtrip = json.loads(json.dumps(cert))
    assert verify_fdqa(carriers, ops, outputs, roundtrip, context_root='original-pages-p2-hotel-table1736215')['status'] == 'PASS'


def small_model():
    states = ('a','b','c')
    ops = [Operation(x, (), 'S', {():x}) for x in states]
    ops.append(Operation('step', ('S',), 'S', {('a',):'b', ('b',):'c', ('c',):'c'}))
    return {'S':states}, ops, {'S':{'a':0,'b':0,'c':1}}


@pytest.mark.parametrize('field', ['root','block_of','outputs','transitions','primitive_manifest','source_terms','distinguishers'])
def test_checker_rejects_tampering(field):
    carriers, ops, output = small_model()
    cert = compile_fdqa(carriers, ops, output, context_root='small')
    if field == 'root':
        cert[field] = 'wrong'
    elif field == 'block_of':
        cert[field][0] = cert[field][1]
    elif field == 'outputs':
        cert[field][0] = cert[field][-1]
    elif field == 'transitions':
        cert[field]['step'][0]['result'] = 0
    elif field == 'primitive_manifest':
        cert[field] = []
    elif field == 'source_terms':
        cert[field]['0']['operation'] = 'invented'
    else:
        cert[field] = cert[field][1:]
    assert verify_fdqa(carriers, ops, output, cert, context_root='small')['status'] == 'FAIL'


def test_unjustified_overrefinement_cannot_obtain_minimality_certificate():
    carriers, ops, outputs = small_model()
    outputs['S'] = dict.fromkeys(carriers['S'],0)
    cert = compile_fdqa(carriers, ops, outputs, context_root='same')
    assert len(cert['blocks']) == 1
    # A singleton partition is stable but has no valid distinguishing witnesses.
    cert['blocks'] = [[0],[1],[2]]
    cert['block_of'] = [0,1,2]
    cert['representatives'] = [0,1,2]
    cert['outputs'] *= 3
    cert['transitions'] = {op.name:[{'arguments':list(range(len(args))), 'result': carriers['S'].index(target)}]
                           for op in ops for args,target in op.table.items() if not args}
    cert['transitions']['step'] = [{'arguments':[i],'result':min(i+1,2)} for i in range(3)]
    cert['distinguishers'] = [{'first':a,'second':b,'actions':[]} for a,b in ((0,1),(0,2),(1,2))]
    result = verify_fdqa(carriers, ops, outputs, cert, context_root='same')
    assert result['status'] == 'FAIL' and 'distinguish' in result['reason']


def test_binary_all_argument_contexts_and_exhaustive_word_oracle():
    rng = random.Random(381)
    for _ in range(16):
        ids = tuple(map(str, range(4)))
        table = {(a,b):rng.choice(ids) for a,b in product(ids, repeat=2)}
        operations = [Operation('c'+s, (), 'S', {():s}) for s in ids]
        operations.append(Operation('combine', ('S','S'), 'S', table))
        out = {s:rng.randrange(2) for s in ids}
        cert = compile_fdqa({'S':ids}, operations, {'S':out}, context_root='random-finite')
        assert verify_fdqa({'S':ids}, operations, {'S':out}, cert, context_root='random-finite')['status'] == 'PASS'
        # Independent whole-context closure as unary functions, not refinement.
        generators = [tuple(ids.index(table[s,fixed]) for s in ids) for fixed in ids]
        generators += [tuple(ids.index(table[fixed,s]) for s in ids) for fixed in ids]
        contexts, pending = {tuple(range(4))}, [tuple(range(4))]
        while pending:
            context = pending.pop()
            for action in generators:
                composition = tuple(action[context[i]] for i in range(4))
                if composition not in contexts:
                    contexts.add(composition)
                    pending.append(composition)
        for i,j in product(range(4),repeat=2):
            equivalent = all(out[ids[c[i]]] == out[ids[c[j]]] for c in contexts)
            assert (cert['block_of'][i] == cert['block_of'][j]) == equivalent


def test_scope_changes_budget_and_input_mutation():
    carriers, ops, outputs = small_model()
    cert = compile_fdqa(carriers, ops, outputs, context_root='scope-v1')
    assert verify_fdqa(carriers, ops, outputs, cert, context_root='scope-v2')['status'] == 'FAIL'
    assert compile_fdqa(carriers, ops, outputs, context_root='scope-v1', max_work=0)['status'] == 'UNKNOWN'
    assert verify_fdqa(carriers, ops, outputs, cert, context_root='scope-v1', max_work=0)['status'] == 'UNKNOWN'
    outputs['S']['a'] = 4
    assert verify_fdqa(carriers, ops, outputs, cert, context_root='scope-v1')['status'] == 'FAIL'


def test_invalid_tables_unreachable_and_undefined_semantics():
    carriers, ops, outputs = small_model()
    bad = deepcopy(ops)
    del bad[-1].table[('b',)]
    with pytest.raises(ValueError, match='Incomplete'):
        compile_fdqa(carriers,bad,outputs,context_root='test')
    with pytest.raises(ValueError, match='Unreachable'):
        compile_fdqa(carriers,[],outputs,context_root='test')
    undefined = {'S':'c'}
    cert = compile_fdqa(carriers,ops,outputs,context_root='test',undefined=undefined)
    assert verify_fdqa(carriers,ops,outputs,cert,context_root='test',undefined=undefined)['status'] == 'PASS'
    ops[-1].table[('c',)] = 'a'
    with pytest.raises(ValueError, match='absorbing'):
        compile_fdqa(carriers,ops,outputs,context_root='test',undefined=undefined)


def test_term_type_cycle_and_deep_iterative_evaluation():
    carriers, ops, outputs = small_model()
    cert = compile_fdqa(carriers,ops,outputs,context_root='terms')
    term = ('a', ())
    for _ in range(2000):
        term = ('step',(term,))
    assert evaluate_compiled_term(cert,term)['block'] == 2
    cycle = ['step', []]
    cycle[1].append(cycle)
    with pytest.raises(ValueError, match='Cyclic'):
        evaluate_compiled_term(cert,cycle)
    with pytest.raises(ValueError, match='arity'):
        evaluate_compiled_term(cert,('step',()))
