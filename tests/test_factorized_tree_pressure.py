from copy import deepcopy
from fractions import Fraction as Q
from itertools import product
from pathlib import Path
import json
import pytest
from oma.optimization import factorized_tree_pressure as f
from oma.optimization import coupled_tree_pressure as old
from test_coupled_tree_pressure import example,interval,seal


@pytest.fixture(scope='module')
def actual():
    m,b=example(True);c=f.compile_factorized_tree_pressure(m,b)
    assert c['status']=='CERTIFIED_BOX',c
    assert f.verify_factorized_tree_pressure(m,b,c)['status']=='PASS'
    return m,b,c


def test_exact_original_five_native_box():
    p=Path(__file__).parent/'fixtures/five-native'
    m=json.loads((p/'model.json').read_text());b=json.loads((p/'original-box.json').read_text())
    before=deepcopy((m,b));legacy=old.compile_coupled_tree_pressure(m,b)
    assert legacy['status']=='UNKNOWN' and legacy['reason']=='STRICT_BOX_INCLUSION_NOT_ESTABLISHED'
    c=f.compile_factorized_tree_pressure(m,b)
    assert c['status']=='CERTIFIED_BOX',c
    v=f.verify_factorized_tree_pressure(m,b,c);assert v['status']=='PASS',v
    assert (m,b)==before
    assert c['schema']==f.CERTIFICATE_SCHEMA and all(x is False for x in c['limitations'].values())


@pytest.mark.parametrize('uncertain',[False,True])
def test_independent_direct_polynomial_and_jacobian_oracle(uncertain):
    m,b=example(uncertain)
    # Same identity in multiple subtree equations, distinct equal-valued IDs.
    m['coefficients']['shared']=interval('1/1000','1/500')
    for leaf in ('A','B'):
        m['terms'].append({'id':'extra-'+leaf,'coefficient_id':'shared','descendant_leaves':[leaf],'applies_to_leaves':[leaf]})
    c=f.compile_factorized_tree_pressure(m,b);assert c['status']=='CERTIFIED_BOX',c
    assert f.verify_factorized_tree_pressure(m,b,c)['status']=='PASS'
    leaves=sorted(m['leaves']);r=[[Q(x) for x in row] for row in c['preconditioner']]
    assert any(x<0 for row in r for x in row)
    # Exact values use original term/equation laws, never production expansion.
    for qsigns in product(('lower','upper'),repeat=len(leaves)):
        q={l:Q(b[l][s]) for l,s in zip(leaves,qsigns)}
        for coefficient_end in ('lower','upper'):
            a={k:Q(v[coefficient_end]) for k,v in m['coefficients'].items()}
            heads={l:Q(m['available_heads'][l][coefficient_end]) for l in leaves}
            direct=[];j=[]
            for leaf in leaves:
                direct.append(sum(a[t['coefficient_id']]*sum(q[x] for x in t['descendant_leaves'])**2
                                  for t in m['terms'] if leaf in t['applies_to_leaves'])-heads[leaf])
                j.append([sum(2*a[t['coefficient_id']]*sum(q[x] for x in t['descendant_leaves'])
                              for t in m['terms'] if leaf in t['applies_to_leaves'] and col in t['descendant_leaves']) for col in leaves])
            for i,leaf in enumerate(leaves):
                rows=[x for x in c['preconditioned_polynomial'] if x['row']==leaf]
                expanded=sum(Q(x['weight'])*a[x['coefficient_id']]*q[x['variables'][0]]*q[x['variables'][1]] for x in rows)
                expanded-=sum(r[i][k]*heads[l] for k,l in enumerate(leaves))
                assert expanded==sum(r[i][k]*direct[k] for k in range(len(leaves)))
                for col,name in enumerate(leaves):
                    derivative=Q(int(i==col))-sum(r[i][k]*j[k][col] for k in range(len(leaves)))
                    bound=c['derivative_map'][i][col]
                    assert Q(bound['lower'])<=derivative<=Q(bound['upper'])


def test_verifier_does_not_call_producers(actual,monkeypatch):
    m,b,c=deepcopy(actual)
    def fail(*a,**kw):raise AssertionError('Producer called by independent checker')
    for name in ('compile_factorized_tree_pressure','_producer_polynomial','_producer_evaluate'):
        monkeypatch.setattr(f,name,fail)
    for name in ('compile_coupled_tree_pressure','_produce_polynomial','_inverse'):
        monkeypatch.setattr(old,name,fail)
    assert f.verify_factorized_tree_pressure(m,b,c)['status']=='PASS'


@pytest.mark.parametrize('attack',['weight','omit','duplicate','coefficient','variables','row','head','inverse','margin','norm','enclosure','schema','rule'])
def test_resealed_forgery_rejected(actual,attack):
    m,b,c=deepcopy(actual);row=c['preconditioned_polynomial'][0]
    if attack=='weight':row['weight']=str(Q(row['weight'])+1)
    elif attack=='omit':c['preconditioned_polynomial'].pop()
    elif attack=='duplicate':c['preconditioned_polynomial'].append(deepcopy(row))
    elif attack=='coefficient':row['coefficient_id']='missing'
    elif attack=='variables':row['variables']=['A','A'] if row['variables']!=['A','A'] else ['B','B']
    elif attack=='row':row['row']='missing'
    elif attack=='head':c['center_image']['A']['lower']='0'
    elif attack=='inverse':c['preconditioner'][0][0]='0'
    elif attack=='margin':c['inclusion_margins']['A']['lower']='100'
    elif attack=='norm':c['contraction_norm_upper']='0'
    elif attack=='enclosure':c['root_enclosure']['A']={'lower':'1','upper':'1'}
    else:c[attack]='unsupported'
    result=f.verify_factorized_tree_pressure(m,b,seal(c));assert result['status']=='FAIL',result


@pytest.mark.parametrize('key,value,reason',[
    ('max_work',1,'WORK_BUDGET'),('max_leaves',1,'VARIABLE_BUDGET'),('max_terms',1,'TERM_BUDGET'),
    ('max_matrix_entries',1,'MATRIX_ENTRY_BUDGET'),('max_monomials',1,'MONOMIAL_BUDGET'),
    ('max_input_bytes',256,'INPUT_BYTE_BUDGET'),('max_certificate_bytes',256,'CERTIFICATE_BYTE_BUDGET')])
def test_budgets_do_not_emit_proofs(actual,key,value,reason):
    m,b,c=actual
    for result in (f.compile_factorized_tree_pressure(m,b,**{key:value}),f.verify_factorized_tree_pressure(m,b,c,**{key:value})):
        assert result['status']=='UNKNOWN' and result['proof_complete'] is False,result
        assert reason in result['reason'],result


@pytest.mark.parametrize('value',[True,0,-1,262145,'1',None])
def test_invalid_monomial_budget(actual,value):
    m,b,c=actual
    assert f.compile_factorized_tree_pressure(m,b,max_monomials=value)['status']=='INVALID_INPUT'
    assert f.verify_factorized_tree_pressure(m,b,c,max_monomials=value)['status']=='FAIL'


def test_complete_packet_including_root_obeys_byte_budget(actual):
    m,b,c=actual
    size=len(json.dumps(c,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())
    result=f.compile_factorized_tree_pressure(m,b,max_certificate_bytes=size-1)
    assert result['status']=='UNKNOWN' and result['reason']=='CERTIFICATE_BYTE_BUDGET'
    assert f.compile_factorized_tree_pressure(m,b,max_certificate_bytes=size)['certificate_root']==c['certificate_root']


@pytest.mark.parametrize('verify',[False,True])
def test_cancellation_identity_propagates(actual,verify):
    m,b,c=deepcopy(actual);error=RuntimeError('cancel exact run')
    def callback(stage):raise error
    with pytest.raises(RuntimeError) as caught:
        if verify:f.verify_factorized_tree_pressure(m,b,c,checkpoint=callback)
        else:f.compile_factorized_tree_pressure(m,b,checkpoint=callback)
    assert caught.value is error


@pytest.mark.parametrize('verify',[False,True])
def test_final_callback_input_mutation_cannot_pass(actual,verify):
    m,b,c=deepcopy(actual)
    def callback(stage):
        if stage==('factorized_verifier_complete' if verify else 'factorized_producer_complete'):
            m['available_heads']['A']['lower']='0'
    result=f.verify_factorized_tree_pressure(m,b,c,checkpoint=callback) if verify else f.compile_factorized_tree_pressure(m,b,checkpoint=callback)
    assert result['status']==('FAIL' if verify else 'INVALID_INPUT') and not result['proof_complete']
