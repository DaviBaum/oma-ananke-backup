"""Independent incoming-edge-function oracles and adversarial general-tree proofs."""
import copy
from fractions import Fraction as Q
import hashlib
import importlib.util
import itertools
import json
import os
from pathlib import Path
import random

import pytest


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


s = load(os.environ.get('OMA_SHARED_TREE_SOURCE', Path(__file__).parents[1]/'src/oma/optimization/shared_tree_synthesis.py'), 'general_tree_under_test')
legacy = load(Path(__file__).parent/'fixtures/general-shared-tree-synthesis/legacy003.py', 'legacy_shared_tree')
old_test = load(Path(__file__).parent/'test_shared_tree_synthesis.py', 'legacy_tree_fixtures')
ROOT = '1'*64


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def reseal(c):
    c['certificate_root'] = digest({k:v for k,v in c.items() if k != 'certificate_root'})
    return c


def catalogue(n=4, *, layout='chain', dense=False, extra_tees=0, parallel=True):
    """Explicit complete cap catalogue, without any geometry/native proof claim."""
    p = old_test.make_catalogue(n, n-1+extra_tees)
    caps = {('source','out'): p['source']['cap']}
    for item in p['sinks']:
        caps[item['id'],'in'] = item['cap']
    for item in p['tee_instances']:
        center = tuple(map(Q, item['center_m']))
        for port, axis, take in [('a',item['axis_x'],-Q(item['trunk_takeout_m'])),
                                 ('b',item['axis_x'],Q(item['trunk_takeout_m'])),
                                 ('branch',item['axis_y'],Q(item['branch_takeout_m']))]:
            caps[item['id'],port] = {'position_m':[str(c+take*d) for c,d in zip(center,axis)], 'flow_direction':axis[:]}
    pairs = []
    tees = [x['id'] for x in p['tee_instances']]
    sinks = [x['id'] for x in p['sinks']]
    if dense:
        pairs = [(('source','out'),(t,'a')) for t in tees]
        pairs += [((t,port),(u,'a')) for t in tees for port in ('b','branch') for u in tees if t != u]
        pairs += [((t,port),(u,'in')) for t in tees for port in ('b','branch') for u in sinks]
    else:
        next_tee = [0]
        def branch(leaves):
            if len(leaves) == 1:
                return leaves[0], 'in'
            root = tees[next_tee[0]]
            next_tee[0] += 1
            split = 1 if layout == 'chain' else len(leaves)//2
            left, right = branch(leaves[:split]), branch(leaves[split:])
            pairs.extend([((root,'b'),left), ((root,'branch'),right)])
            return root, 'a'
        root = branch(sinks)
        pairs.append((('source','out'),root))
    p['connectors'] = []
    for i,(start,end) in enumerate(pairs):
        p['connectors'].append({'id':f'edge-{i:03d}', 'from':dict(node=start[0],port=start[1]),
             'to':dict(node=end[0],port=end[1]), 'start_cap':copy.deepcopy(caps[start]),
             'end_cap':copy.deepcopy(caps[end]), 'section':copy.deepcopy(p['section']),
             'geometry_root':ROOT,'fabrication_root':ROOT,'nominal_cost':[str(Q(i%5+1,7)),'0']})
    if parallel:
        extra = copy.deepcopy(p['connectors'][-1])
        extra['id'] = 'parallel-last'
        extra['nominal_cost'] = ['3','0']
        p['connectors'].append(extra)
    return p


def incoming_function_oracle(p):
    """Enumerate all parent-edge functions; no subtree DP or open-slot search."""
    sinks = {x['id'] for x in p['sinks']}
    tees = {x['id']:x for x in p['tee_instances']}
    source = p['source']['id']
    answer = {}
    for chosen_tees in itertools.combinations(sorted(tees), len(sinks)-1):
        selected = set(chosen_tees)
        for enter in p['connectors']:
            if enter['from']['node'] != source or enter['to']['node'] not in selected:
                continue
            root = enter['to']['node']
            targets = sorted((selected-{root}) | sinks)
            choices = [[e for e in p['connectors'] if e['to']['node']==node and e['from']['node'] in selected]
                       for node in targets]
            for edges in itertools.product(*choices):
                slots = [(e['from']['node'],e['from']['port']) for e in edges]
                if len(set(slots)) != len(slots):
                    continue
                if set(slots) != {(tee,port) for tee in selected for port in ('b','branch')}:
                    continue
                # Check directed reachability independently by repeated edge closure.
                reached = {source}
                full = (enter,)+edges
                for _ in range(len(selected)+len(sinks)):
                    reached |= {e['to']['node'] for e in full if e['from']['node'] in reached}
                if reached != {source}|selected|sinks:
                    continue
                ids = tuple(sorted(e['id'] for e in full))
                assert ids not in answer
                components = [tees[t] for t in selected]+list(full)
                price = tuple(sum((Q(x['nominal_cost'][j]) for x in components),Q()) for j in range(2))
                answer[ids] = (tuple(sorted(selected)), tuple(map(str,price)))
    return answer


def check(p, **kw):
    a = s.compile_shared_tree_catalogue(p, **kw)
    assert a['status'] == 'CERTIFIED', a
    b = s.verify_shared_tree_catalogue(p,a['certificate'],**kw)
    assert b['status'] == 'PASS', b
    assert a['proposals'] == b['proposals']
    return a,b


def row_map(result):
    return {tuple(r['connector_ids']):(tuple(r['tee_ids']),tuple(r['nominal_cost'])) for r in result['certificate']['assignments']}


@pytest.fixture(scope='module')
def dense_four():
    p = catalogue(4,dense=True,parallel=False)
    a,b = check(p, max_partial_trees=200000)
    return p,a,b


def test_complete_four_sink_parent_function_oracle(dense_four):
    p,a,b = dense_four
    reference = incoming_function_oracle(p)
    assert len(reference) == len(a['certificate']['assignments']) == 720
    assert row_map(a) == reference
    expected = sorted(reference, key=lambda ids:(Q(reference[ids][1][0]),ids))[:32]
    assert [tuple(x['connector_ids']) for x in b['proposals']] == expected


@pytest.mark.parametrize('n',range(4,9))
@pytest.mark.parametrize('layout',['chain','balanced'])
def test_sparse_four_through_eight_exact_oracle(n,layout):
    p = catalogue(n,layout=layout)
    a,b = check(p)
    assert row_map(a) == incoming_function_oracle(p)
    assert len(a['proposals']) == 2
    for proposal in b['proposals']:
        assert len(proposal['tee_ids']) == n-1
        assert len(proposal['connector_ids']) == 2*n-1
        assert {x['id'] for x in proposal['sinks']} == {x['id'] for x in p['sinks']}
        assert {x['demand_id'] for x in proposal['sinks']} == {x['demand_id'] for x in p['sinks']}


@pytest.mark.parametrize('seed',range(8))
def test_sparse_independent_topology_oracle(seed):
    p = catalogue(4,dense=True,extra_tees=1,parallel=False)
    rng = random.Random(seed)
    p['connectors'] = [e for e in p['connectors'] if rng.random() < .35]
    a,b = check(p)
    assert row_map(a) == incoming_function_oracle(p)


def test_shared_trunk_is_charged_once():
    p = catalogue(8,parallel=False)
    for e in p['connectors']:
        e['nominal_cost'] = ['0','0']
        if e['from']['node']=='source': e['nominal_cost'] = ['13','2']
    for t in p['tee_instances']:t['nominal_cost']=['1','0']
    a,_ = check(p)
    assert a['proposals'][0]['nominal_cost'] == ['20','2']
    shared = next(e['id'] for e in p['connectors'] if e['from']['node']=='source')
    assert all(shared in x['connector_path'] for x in a['proposals'][0]['sinks'])


def test_disconnected_cyclic_catalogue_has_no_complete_tree():
    p = catalogue(4,dense=True,parallel=False)
    # All tee cycles remain; one terminal has no incoming connector.
    p['connectors'] = [e for e in p['connectors'] if e['to']['node'] != 'sink-3']
    a,b = check(p,max_partial_trees=200000)
    assert a['certificate']['assignments'] == b['proposals'] == []
    assert row_map(a) == incoming_function_oracle(p) == {}
    assert 'physical infeasibility' in ' '.join(a['certificate']['limitations'])


def test_prefix_one_does_not_drop_any_finite_assignment(dense_four):
    p,all_rows,_ = dense_four
    a,b = check(p,max_results=1,max_partial_trees=200000)
    assert a['certificate']['assignments'] == all_rows['certificate']['assignments']
    assert len(a['proposals']) == 1


@pytest.mark.parametrize('n,tees',[(2,1),(2,3),(3,1),(3,2),(3,3)])
@pytest.mark.parametrize('limit',[1,32])
def test_legacy_complete_result_and_callback_bytes_unchanged(n,tees,limit):
    p=old_test.make_catalogue(n,tees)
    before_events=[];after_events=[]
    before=legacy.compile_shared_tree_catalogue(p,max_results=limit,checkpoint=before_events.append)
    after=s.compile_shared_tree_catalogue(p,max_results=limit,checkpoint=after_events.append)
    assert json.dumps(before,sort_keys=True)==json.dumps(after,sort_keys=True)
    assert before_events==after_events
    bv=legacy.verify_shared_tree_catalogue(p,before['certificate'],max_results=limit)
    av=s.verify_shared_tree_catalogue(p,before['certificate'],max_results=limit)
    assert json.dumps(bv,sort_keys=True)==json.dumps(av,sort_keys=True)


@pytest.mark.parametrize('attack',['missing','duplicate','cost','tee','connector','row_root','rank_reverse','rank_missing',
    'rank_duplicate','scope','input_root','problem_root','count_bool','max_bool','max_results','extra_field','swapped_costs'])
def test_resealed_full_ledger_attacks(attack):
    p=catalogue(4);a,_=check(p);c=copy.deepcopy(a['certificate'])
    if attack=='missing':c['assignments'].pop();c['assignment_count']-=1
    elif attack=='duplicate':c['assignments'].append(copy.deepcopy(c['assignments'][0]));c['assignment_count']+=1
    elif attack=='cost':c['assignments'][0]['nominal_cost']=['0','0']
    elif attack=='tee':c['assignments'][0]['tee_ids'].pop()
    elif attack=='connector':c['assignments'][0]['connector_ids'][0]=c['assignments'][0]['connector_ids'][1]
    elif attack=='row_root':c['assignments'][0]['assignment_root']='2'*64
    elif attack=='rank_reverse':c['ranked_prefix'].reverse()
    elif attack=='rank_missing':c['ranked_prefix'].pop()
    elif attack=='rank_duplicate':c['ranked_prefix'][1]=c['ranked_prefix'][0]
    elif attack=='scope':c['scope']='GLOBAL_NATIVE_OPTIMUM'
    elif attack=='input_root':c['input_root']='2'*64
    elif attack=='problem_root':c['problem_root']='2'*64
    elif attack=='count_bool':c['assignment_count']=True
    elif attack=='max_bool':c['max_results']=True
    elif attack=='max_results':c['max_results']=1;c['ranked_prefix']=c['ranked_prefix'][:1]
    elif attack=='extra_field':c['assignments'][0]['native_pass']=True
    elif attack=='swapped_costs':c['assignments'][0]['nominal_cost'],c['assignments'][1]['nominal_cost']=c['assignments'][1]['nominal_cost'],c['assignments'][0]['nominal_cost']
    # Recompute row roots too; rejection must come from independent full reconstruction.
    if attack in ('cost','tee','connector','swapped_costs'):
        for row in c['assignments']:
            row['assignment_root']=digest({'problem_root':c['problem_root'],**{k:v for k,v in row.items() if k!='assignment_root'}})
    result=s.verify_shared_tree_catalogue(p,reseal(c))
    assert result['status']=='FAIL' and not result['proof_complete'] and result['proposals']==[]


@pytest.mark.parametrize('field',['context_root','cost_policy_root','source_roots','loss','terminal','demand','connector_geometry'])
def test_changed_complete_input_binding(field):
    p=catalogue(4);a,_=check(p)
    if field in ('context_root','cost_policy_root'):p[field]='2'*64
    elif field=='source_roots':p[field]['source_ifc']='2'*64
    elif field=='loss':p['tee_instances'][1]['loss_contract_root']='2'*64
    elif field=='terminal':p['sinks'][0]['cap']['position_m'][0]='500'
    elif field=='demand':p['sinks'][0]['demand_id']='other-demand'
    else:p['connectors'][0]['geometry_root']='2'*64
    assert s.verify_shared_tree_catalogue(p,a['certificate'])['status']=='FAIL'


@pytest.mark.parametrize('kwargs',[{'max_partial_trees':1},{'max_work':100},{'max_assignments':1},
    {'max_tee_instances':1},{'max_connectors':1},{'max_bytes':256}])
def test_explicit_budget_exhaustion_no_partial_authority(kwargs):
    p=catalogue(4);a,_=check(p)
    for result in (s.compile_shared_tree_catalogue(p,**kwargs),s.verify_shared_tree_catalogue(p,a['certificate'],**kwargs)):
        assert result['status']=='UNKNOWN' and result['proposals']==[] and not result['proof_complete']


@pytest.mark.parametrize('value',[True,0,-1,200001,1.5,'20'])
def test_strict_new_partial_budget(value):
    p=catalogue(4)
    assert s.compile_shared_tree_catalogue(p,max_partial_trees=value)['status']=='INVALID_INPUT'


def test_exact_new_partial_and_work_budget_boundaries():
    p=catalogue(8);a,b=check(p)
    for mode,base,work in [('producer',a,a['work']),('verifier',b,b['work'])]:
        run=(lambda **kw:s.compile_shared_tree_catalogue(p,**kw)) if mode=='producer' else (lambda **kw:s.verify_shared_tree_catalogue(p,a['certificate'],**kw))
        cap=base['counts']['partial_join_attempts' if mode=='producer' else 'checked_partial_tree_attempts']
        assert run(max_partial_trees=cap)['status'] in ('CERTIFIED','PASS')
        assert run(max_partial_trees=cap-1)['status']=='UNKNOWN'
        assert run(max_work=work)['status'] in ('CERTIFIED','PASS')
        assert run(max_work=work-1)['status']=='UNKNOWN'


def test_general_verifier_independent_of_all_producer_cost_and_join_helpers(monkeypatch):
    p=catalogue(4);a,_=check(p)
    def forbidden(*args,**kw):raise AssertionError('producer helper called')
    for name in ('_producer_assignments','_producer_general_assignments','_sum_cost','_row','_pi_producer','compile_shared_tree_catalogue'):
        monkeypatch.setattr(s,name,forbidden)
    assert s.verify_shared_tree_catalogue(p,a['certificate'])['status']=='PASS'


@pytest.mark.parametrize('mode',['producer','verifier'])
@pytest.mark.parametrize('error_type',[ValueError,TimeoutError,s._Exhausted])
def test_callback_exact_exception_identity(mode,error_type):
    p=catalogue(4);a,_=check(p);marker=error_type('same caller exception')
    def callback(stage):raise marker
    with pytest.raises(error_type) as got:
        if mode=='producer':s.compile_shared_tree_catalogue(p,checkpoint=callback)
        else:s.verify_shared_tree_catalogue(p,a['certificate'],checkpoint=callback)
    assert got.value is marker


@pytest.mark.parametrize('mode,target',[('producer','input'),('verifier','input'),('verifier','certificate')])
def test_final_callback_mutation_no_more_callbacks(mode,target):
    p=catalogue(4);a,_=check(p);c=a['certificate'];done=[False]
    def callback(stage):
        assert not done[0]
        if stage==f'shared_tree_{mode}_complete':
            done[0]=True
            if target=='input':p['tee_instances'][-1]['loss_contract_root']='2'*64
            else:c['assignments'].pop()
    result=s.compile_shared_tree_catalogue(p,checkpoint=callback) if mode=='producer' else s.verify_shared_tree_catalogue(p,c,checkpoint=callback)
    assert done[0] and result['status'] not in ('CERTIFIED','PASS') and result['proposals']==[]


def test_more_than_eight_sinks_is_explicit_unknown_before_parsing():
    p=catalogue(8);p['sinks'].append({'invalid':'not parsed'})
    r=s.compile_shared_tree_catalogue(p)
    assert r['status']=='UNKNOWN' and r['reason']=='SINK_DOMAIN'


def test_input_domain_rechecked_after_first_callback():
    p=catalogue(8)
    def callback(stage):
        if stage=='shared_tree_input':p['sinks'].append({'invalid':'not parsed'})
    r=s.compile_shared_tree_catalogue(p,checkpoint=callback)
    assert r['status']=='UNKNOWN' and r['reason']=='SINK_DOMAIN'


def test_rational_scientific_exponent_never_reaches_fraction(monkeypatch):
    p=catalogue(4);p['section']['diameter_m']='1e1000000000'
    def forbidden(*args,**kw):raise AssertionError('unsafe Fraction parsing')
    monkeypatch.setattr(s,'Q',forbidden)
    assert s.compile_shared_tree_catalogue(p)['status']=='INVALID_INPUT'
