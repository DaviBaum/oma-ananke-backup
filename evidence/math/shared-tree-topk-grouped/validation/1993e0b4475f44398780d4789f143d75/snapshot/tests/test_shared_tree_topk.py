"""Independent finite-oracle, compatibility, closure and resource attacks."""
import copy
from fractions import Fraction as Q
from functools import lru_cache
import itertools,json,math
from pathlib import Path

import pytest

from oma.optimization import shared_tree_topk as t
import test_general_shared_tree_synthesis as f


def check(p,**kw):
    a=t.compile_shared_tree_topk_catalogue(p,**kw)
    assert a['status']=='CERTIFIED',a
    b=t.verify_shared_tree_topk_catalogue(p,a['certificate'],**kw)
    assert b['status']=='PASS',b
    assert a['proposals']==b['proposals'] and a['counts']['complete_assignments']==b['counts']['complete_assignments']
    return a,b


def reseal(c):
    c['certificate_root']=f.digest({k:v for k,v in c.items() if k!='certificate_root'})
    return c


@pytest.mark.parametrize('n',[2,3,4])
@pytest.mark.parametrize('k',[1,3,8,32])
def test_same_prefix_as_independent_full_ledger(n,k):
    p=f.catalogue(n,dense=True,parallel=False)
    old=f.s.compile_shared_tree_catalogue(p,max_results=k,max_partial_trees=200000)
    assert old['status']=='CERTIFIED'
    a,b=check(p,k=k)
    assert a['proposals']==old['proposals']
    assert int(a['counts']['complete_assignments'])==old['counts']['complete_assignments']
    oracle=f.incoming_function_oracle(p)
    assert len(oracle)==int(a['counts']['complete_assignments'])


@pytest.mark.parametrize('n',range(4,9))
@pytest.mark.parametrize('layout',['chain','balanced'])
def test_sparse_positive_four_through_eight(n,layout):
    p=f.catalogue(n,layout=layout);a,b=check(p)
    assert int(a['counts']['complete_assignments'])==len(f.incoming_function_oracle(p))==2
    assert a['proposals']==f.s.compile_shared_tree_catalogue(p)['proposals']
    assert all(len(x['connector_ids'])==2*n-1 for x in a['proposals'])
    if n==8:assert b['counts']['induced_disconnected_states']>20000


@pytest.mark.parametrize('k',[1,8,32])
def test_actual_authored_18048_tree_catalogue_exact_v1_prefix(k):
    d=Path(__file__).parent/'fixtures/shared-tree-topk'
    p=json.loads((d/'authored-four-catalogue.json').read_text(encoding='utf-8'))
    want=json.loads((d/'authored-four-v1-prefix32.json').read_text(encoding='utf-8'))
    a,b=check(p,k=k)
    assert a['input_root']==want['input_root'] and a['problem_root']==want['problem_root']
    assert int(a['counts']['complete_assignments'])==want['complete_assignments']==18048
    assert a['proposals']==want['proposals'][:k]
    assert a['counts']['stored_labels']<=45*k
    assert a['work']<2963067 and b['work']<3952986


@lru_cache(None)
def shapes(n):
    if n==1:return (None,)
    return tuple((a,b) for k in range(1,n) for a in shapes(k) for b in shapes(n-k))


def shape_permutation_oracle(p,k):
    """Third algorithm: all ordered binary shapes and node labellings (n<=5)."""
    sinks=sorted(x['id'] for x in p['sinks']);tees=sorted(x['id'] for x in p['tee_instances'])
    assert len(sinks)<=5 and len(tees)==len(sinks)-1
    pairs={((e['from']['node'],e['from']['port']),(e['to']['node'],e['to']['port'])):e['id'] for e in p['connectors']}
    assert len(pairs)==len(p['connectors'])
    words=set()
    for shape in shapes(len(sinks)):
        for tee_order in itertools.permutations(tees):
            for sink_order in itertools.permutations(sinks):
                ti=iter(tee_order);si=iter(sink_order);edges=[]
                def build(node):
                    if node is None:return next(si),'in'
                    root=next(ti);left=build(node[0]);right=build(node[1])
                    edges.extend([pairs[(root,'b'),left],pairs[(root,'branch'),right]])
                    return root,'a'
                root=build(shape);edges.append(pairs[(p['source']['id'],'out'),root])
                word=tuple(sorted(edges));assert word not in words;words.add(word)
    return len(words),sorted(words)[:k]


def test_five_sink_catalan_shape_oracle_40320_and_exact_zero_ties():
    p=f.catalogue(5,dense=True,parallel=False)
    for x in p['tee_instances']+p['connectors']:x['nominal_cost']=['0','0']
    a,b=check(p,k=3)
    total,prefix=shape_permutation_oracle(p,3)
    assert total==int(a['counts']['complete_assignments'])==40320
    assert [tuple(x['connector_ids']) for x in a['proposals']]==prefix


def parallel_chain(n=8,options=5):
    p=f.catalogue(n,parallel=False);original=copy.deepcopy(p['connectors']);p['connectors']=[]
    for edge in original:
        for i in range(options):
            other=copy.deepcopy(edge);other['id']+=f'-option{i}';p['connectors'].append(other)
    return p


def test_eight_sink_compact_count_over_30_billion_words():
    p=parallel_chain();a,b=check(p,k=3)
    assert int(a['counts']['complete_assignments'])==5**15==30517578125
    assert a['counts']['reachable_states']==7 and a['counts']['stored_labels']==21
    assert len(a['proposals'])==3
    # These are connector-ID choices, not a claim of distinct native geometries.
    assert any('identical physical geometry' in x for x in a['certificate']['limitations'])
    limited=f.s.compile_shared_tree_catalogue(p,max_results=3)
    assert limited['status']=='UNKNOWN' and limited['proposals']==[]


def test_exact_tee_mask_preserves_outside_compatibility():
    p=f.catalogue(5,dense=True,parallel=False)
    allowed={('source','out','tee-0'),('tee-0','b','tee-1'),('tee-0','branch','tee-2'),
             ('tee-1','b','sink-0'),('tee-1','branch','tee-2'),('tee-1','branch','tee-3'),
             ('tee-2','b','sink-1'),('tee-2','branch','sink-2'),('tee-2','b','sink-3'),('tee-2','branch','sink-4'),
             ('tee-3','b','sink-1'),('tee-3','branch','sink-2')}
    p['connectors']=[e for e in p['connectors'] if (e['from']['node'],e['from']['port'],e['to']['node']) in allowed]
    for x in p['tee_instances']+p['connectors']:x['nominal_cost']=['0','0']
    expensive=next(e for e in p['connectors'] if e['from']['node']=='tee-1' and e['to']['node']=='tee-3')
    expensive['nominal_cost']=['5','0']
    a,_=check(p,k=1)
    assert int(a['counts']['complete_assignments'])==len(f.incoming_function_oracle(p))==1
    assert expensive['id'] in a['proposals'][0]['connector_ids']
    states=[x for x in a['certificate']['states'] if x['state'][0]=='tee-1' and x['state'][1]==7]
    assert {x['state'][2] for x in states}=={6,10}
    assert {tuple(x['labels'][0]['nominal_cost']) for x in states}=={('0','0'),('5','0')}


def test_empty_universe_is_not_physical_infeasibility():
    p=f.catalogue(8);p['connectors']=[e for e in p['connectors'] if e['to']['node']!='sink-7']
    a,b=check(p)
    assert a['counts']['complete_assignments']=='0' and a['proposals']==[]
    assert 'physical infeasibility' in ' '.join(a['certificate']['limitations'])


@pytest.mark.parametrize('attack',['missing_state','duplicate_state','missing_label','duplicate_label','wrong_label_cost',
    'wrong_label_word','wrong_label_root','wrong_state_count','wrong_total_count','wrong_state_root','wrong_leaf_mask',
    'wrong_tee_mask','mask_bool','header_bool','domain_bool','wrong_domain','reverse_prefix','missing_prefix',
    'duplicate_prefix','prefix_cost','prefix_root','scope','input_root','problem_root','changed_k','extra_field'])
def test_resealed_recurrence_and_header_attacks(attack):
    p=f.catalogue(4,dense=True,parallel=False);a,_=check(p,k=3);c=copy.deepcopy(a['certificate'])
    row=next(x for x in c['states'] if len(x['labels'])==3);label=row['labels'][0]
    if attack=='missing_state':c['states'].pop()
    elif attack=='duplicate_state':c['states'].append(copy.deepcopy(c['states'][0]))
    elif attack=='missing_label':row['labels'].pop()
    elif attack=='duplicate_label':row['labels'][1]=copy.deepcopy(label)
    elif attack=='wrong_label_cost':label['nominal_cost']=['0','0']
    elif attack=='wrong_label_word':label['connector_ids'][0]=label['connector_ids'][1]
    elif attack=='wrong_label_root':label['label_root']='2'*64
    elif attack=='wrong_state_count':row['tree_count']=str(int(row['tree_count'])+1)
    elif attack=='wrong_total_count':c['total_tree_count']=str(int(c['total_tree_count'])+1)
    elif attack=='wrong_state_root':row['state'][0]='tee-absent'
    elif attack=='wrong_leaf_mask':row['state'][1]^=1
    elif attack=='wrong_tee_mask':row['state'][2]^=1
    elif attack=='mask_bool':c['states'][0]['state'][2]=True
    elif attack=='header_bool':c['k']=True
    elif attack=='domain_bool':c['state_domain_count']=True
    elif attack=='wrong_domain':c['state_domain_count']+=1
    elif attack=='reverse_prefix':c['ranked_prefix'].reverse()
    elif attack=='missing_prefix':c['ranked_prefix'].pop()
    elif attack=='duplicate_prefix':c['ranked_prefix'][1]=copy.deepcopy(c['ranked_prefix'][0])
    elif attack=='prefix_cost':c['ranked_prefix'][0]['nominal_cost']=['0','0']
    elif attack=='prefix_root':c['ranked_prefix'][0]['assignment_root']='2'*64
    elif attack=='scope':c['scope']='NATIVE_GLOBAL_OPTIMUM'
    elif attack=='input_root':c['input_root']='2'*64
    elif attack=='problem_root':c['problem_root']='2'*64
    elif attack=='changed_k':c['k']=1;c['ranked_prefix']=c['ranked_prefix'][:1]
    elif attack=='extra_field':c['states'][0]['native_pass']=True
    # Coherently rehash edited label bodies too.
    if attack in ('wrong_label_cost','wrong_label_word'):
        label['label_root']=f.digest({'problem_root':c['problem_root'],'state':row['state'],**{k:v for k,v in label.items() if k!='label_root'}})
    result=t.verify_shared_tree_topk_catalogue(p,reseal(c),k=3)
    assert result['status']=='FAIL' and not result['proof_complete'] and result['proposals']==[]


@pytest.mark.parametrize('kw',[{'max_states':1},{'max_transitions':1},{'max_label_pairs':1},{'max_work':100},
    {'max_bytes':256},{'max_tee_instances':1},{'max_connectors':1}])
def test_budget_unknown_has_no_partial_authority(kw):
    p=f.catalogue(4);a,_=check(p)
    for r in (t.compile_shared_tree_topk_catalogue(p,**kw),t.verify_shared_tree_topk_catalogue(p,a['certificate'],**kw)):
        assert r['status']=='UNKNOWN' and r['proposals']==[] and not r['proof_complete']


def test_count_bit_budget_on_late_source_sum():
    p=parallel_chain(4,5)
    for r in (t.compile_shared_tree_topk_catalogue(p,k=1,max_count_bits=16),):
        assert r['status']=='UNKNOWN' and r['reason']=='TREE_COUNT_BIT_BUDGET' and r['proposals']==[]
    a,_=check(p,k=1)
    assert int(a['counts']['complete_assignments'])==5**7
    assert t.verify_shared_tree_topk_catalogue(p,a['certificate'],k=1,max_count_bits=16)['status']=='UNKNOWN'


@pytest.mark.parametrize('name,value',[('k',True),('k',0),('k',33),('max_states',True),('max_states',100001),
    ('max_transitions',0),('max_label_pairs',10000001),('max_count_bits',15),('max_count_bits',4097)])
def test_strict_new_budgets(name,value):
    assert t.compile_shared_tree_topk_catalogue(f.catalogue(4),**{name:value})['status']=='INVALID_INPUT'


def test_exact_work_transition_and_pair_limits():
    p=f.catalogue(4);a,b=check(p)
    for verifier,result in ((False,a),(True,b)):
        run=(lambda **kw:t.verify_shared_tree_topk_catalogue(p,a['certificate'],**kw)) if verifier else (lambda **kw:t.compile_shared_tree_topk_catalogue(p,**kw))
        for option,value in [('max_work',result['work']),('max_transitions',result['counts']['transitions']),('max_label_pairs',result['counts']['label_pairs'])]:
            assert run(**{option:value})['status'] in ('CERTIFIED','PASS')
            assert run(**{option:value-1})['status']=='UNKNOWN'


def test_verifier_uses_no_producer_or_full_ledger_helpers(monkeypatch):
    p=f.pi_catalogue();a,_=check(p)
    def forbidden(*args,**kw):raise AssertionError('producer helper invoked')
    for name in ('_producer_states','_producer_keep','_producer_join','compile_shared_tree_topk_catalogue'):
        monkeypatch.setattr(t,name,forbidden)
    for name in ('_producer_assignments','_checked_assignments','_row','_sum_cost','_pi_producer'):
        monkeypatch.setattr(t.b,name,forbidden)
    assert t.verify_shared_tree_topk_catalogue(p,a['certificate'])['status']=='PASS'


def test_pi_precision_and_schema_separation():
    p=f.pi_catalogue();a,_=check(p)
    assert a['proposals'][0]['nominal_cost']==['3141592653589793/1000000000000000','0']
    assert t.compile_shared_tree_topk_catalogue(p,max_pi_terms=1)['status']=='UNKNOWN'
    assert t.verify_shared_tree_topk_catalogue(p,a['certificate'],max_pi_terms=1)['status']=='UNKNOWN'
    v1=f.s.compile_shared_tree_catalogue(p)
    assert t.verify_shared_tree_topk_catalogue(p,v1['certificate'])['status']=='FAIL'
    assert f.s.verify_shared_tree_catalogue(p,a['certificate'])['status']=='FAIL'
    assert t.verify_shared_tree_topk_catalogue(p,None)['status']=='FAIL'


@pytest.mark.parametrize('mode',['producer','verifier'])
@pytest.mark.parametrize('error_type',[ValueError,TimeoutError,t.b._Exhausted])
def test_callback_exception_identity(mode,error_type):
    p=f.catalogue(4);a,_=check(p);marker=error_type('caller marker')
    def callback(stage):raise marker
    with pytest.raises(error_type) as caught:
        if mode=='producer':t.compile_shared_tree_topk_catalogue(p,checkpoint=callback)
        else:t.verify_shared_tree_topk_catalogue(p,a['certificate'],checkpoint=callback)
    assert caught.value is marker


@pytest.mark.parametrize('mode,target',[('producer','input'),('verifier','input'),('verifier','proof')])
def test_final_callback_binding_and_no_later_callbacks(mode,target):
    p=f.catalogue(4);a,_=check(p);proof=a['certificate'];done=[False]
    def callback(stage):
        assert not done[0]
        if stage==f'shared_tree_topk_{mode}_complete':
            done[0]=True
            if target=='input':p['cost_policy_root']='2'*64
            else:proof['total_tree_count']='0'
    r=t.compile_shared_tree_topk_catalogue(p,checkpoint=callback) if mode=='producer' else t.verify_shared_tree_topk_catalogue(p,proof,checkpoint=callback)
    assert done[0] and r['status'] not in ('CERTIFIED','PASS') and r['proposals']==[]


def test_captured_state_shape_and_count_resource_rechecked():
    p=f.catalogue(4);a,_=check(p);proof=a['certificate']
    def callback(stage):
        if stage=='shared_tree_topk_input':proof['states']*=1000
    assert t.verify_shared_tree_topk_catalogue(p,proof,max_states=100,checkpoint=callback)['status']=='UNKNOWN'
    with pytest.raises(t.b._Exhausted):t._count_string('9'*4000,{'max_count_bits':16})


def test_complete_certificate_byte_boundary():
    p=f.catalogue(4,dense=True,parallel=False);a,_=check(p)
    encode=lambda v:json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    size=len(encode(a['certificate']));assert size>len(encode(p))
    assert t.compile_shared_tree_topk_catalogue(p,max_bytes=size)['status']=='CERTIFIED'
    assert t.verify_shared_tree_topk_catalogue(p,a['certificate'],max_bytes=size)['status']=='PASS'
    assert t.compile_shared_tree_topk_catalogue(p,max_bytes=size-1)['status']=='UNKNOWN'
    assert t.verify_shared_tree_topk_catalogue(p,a['certificate'],max_bytes=size-1)['status']=='UNKNOWN'
