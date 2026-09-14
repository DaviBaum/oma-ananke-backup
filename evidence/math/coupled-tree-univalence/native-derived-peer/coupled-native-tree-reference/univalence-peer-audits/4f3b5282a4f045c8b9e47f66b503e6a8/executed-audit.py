"""Separate sufficient-univalence replay on the immutable native reference model."""
from pathlib import Path
from copy import deepcopy
from fractions import Fraction as Q
import hashlib
import json
import uuid

STAGE=Path(__file__).resolve().parent
BUILD='ba979df65757aa9f4baa9c757a92a918c9df6f3183663adcf5c63a499d2e9dc1'
SOURCE_SHA='f433e0c007912aa9501306b2bfc95f0809a135e46b5ad898421410eabe10e4df'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def reroot(c):
    c['certificate_root']=hashlib.sha256(json.dumps({k:v for k,v in c.items() if k!='certificate_root'},sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    return c

def inverse_det(m):
    n=len(m);a=[row[:]+[Q(i==j) for j in range(n)] for i,row in enumerate(m)];det=Q(1)
    for col in range(n):
        index=next(i for i in range(col,n) if a[i][col])
        if index!=col:a[index],a[col]=a[col],a[index];det=-det
        pivot=a[col][col];det*=pivot;a[col]=[x/pivot for x in a[col]]
        for i in range(n):
            if i!=col:
                scale=a[i][col];a[i]=[v-scale*w for v,w in zip(a[i],a[col])]
    return [x[n:] for x in a],det

def main():
    from oma.optimization import coupled_tree_univalence as u
    from oma.optimization import coupled_tree_pressure as local
    assert BUILD in str(Path(u.__file__).resolve()) and sha(u.__file__)==SOURCE_SHA
    attempt=STAGE/'evidence/d5b064b69b3f4cf19b7c5824cd439f63';out=STAGE/'univalence-peer-audits'/uuid.uuid4().hex;out.mkdir(parents=True)
    model=read(attempt/'polynomial-model.json');box=read(attempt/'boundary.json')['flow_search_box_m3_s'];local_cert=read(attempt/'local-banach-certificate.json')
    snapshot={n:sha(attempt/n) for n in ('polynomial-model.json','boundary.json','local-banach-certificate.json','native-evidence.json')}
    write(out/'inputs.json',{'math_snapshot':BUILD,'source_sha256':SOURCE_SHA,'native_reference':str(attempt),'input_sha256':snapshot})
    cert=u.compile_coupled_tree_univalence(model);write(out/'univalence-certificate.json',cert)
    check=u.verify_coupled_tree_univalence(model,cert);write(out/'univalence-check.json',check);assert check['status']=='PASS'
    composition=u.verify_coupled_tree_nonnegative_family(model,box,local_cert,cert);write(out/'composed-check.json',composition);assert composition['status']=='PASS'
    cases=[]
    def attack(name,mutate):
        bad=deepcopy(cert);mutate(bad);reroot(bad)
        result=u.verify_coupled_tree_univalence(model,bad);cases.append({'name':name,'status':result['status']});assert result['status']=='FAIL'
    attack('remove_terminal_arm_c_positive_witness',lambda c:c['leaf_witnesses'].pop('sink-c'))
    attack('zero_terminal_singleton_sum',lambda c:c['leaf_witnesses']['sink-b'].update(coefficient_lower_sum='0'))
    attack('tee_terms_assigned_to_terminal_node',lambda c:c['hierarchy'][0]['term_ids'].append('tee-1:b'))
    attack('remove_one_native_pipe_term',lambda c:c['model_manifest']['terms'].pop())
    attack('weaken_full_native_parameter_interval',lambda c:c['model_manifest']['coefficients']['trunk'].update(lower='0'))
    attack('forge_native_context_root',lambda c:c.update(context_root='0'*64))
    attack('remove_hierarchy_node',lambda c:c['hierarchy'].pop())
    attack('duplicate_hierarchy_node',lambda c:c['hierarchy'].__setitem__(0,deepcopy(c['hierarchy'][1])))
    attack('change_unequal_outlet_support',lambda c:c['model_manifest']['terms'][0].update(applies_to_leaves=['sink-c']))
    no_singleton=deepcopy(model);no_singleton['coefficients']['arm-c']['lower']='0'
    unsupported=u.compile_coupled_tree_univalence(no_singleton);assert unsupported['status']=='UNKNOWN'
    wrong_parameter=deepcopy(model);wrong_parameter['available_heads']['sink-a']['upper']=str(Q(wrong_parameter['available_heads']['sink-a']['upper'])+1)
    altered=u.compile_coupled_tree_univalence(wrong_parameter)
    mismatch=u.verify_coupled_tree_nonnegative_family(model,box,local_cert,altered);assert mismatch['status']!='PASS'
    callbacks=[]
    for target in ('model','local','global'):
        m,b,lc,gc=deepcopy(model),deepcopy(box),deepcopy(local_cert),deepcopy(cert);fired=[]
        def callback(stage):
            if stage=='univalence_composition_complete' and not fired:
                fired.append(stage)
                if target=='model':m['available_heads']['sink-a']['lower']='0'
                elif target=='local':lc['center']['sink-a']='1'
                else:gc['leaf_witnesses']['sink-a']['coefficient_lower_sum']='0'
        answer=u.verify_coupled_tree_nonnegative_family(m,b,lc,gc,checkpoint=callback)
        assert fired and answer['status']!='PASS';callbacks.append({'target':target,'status':answer['status']})
    saved={name:getattr(u,name) for name in ('compile_coupled_tree_univalence','_produce_hierarchy')}
    saved_local={name:getattr(local,name) for name in ('compile_coupled_tree_pressure','_produce_polynomial')}
    def disabled(*a,**k):raise AssertionError('Producer invoked by independent checker')
    for name in saved:setattr(u,name,disabled)
    for name in saved_local:setattr(local,name,disabled)
    try: independent=u.verify_coupled_tree_nonnegative_family(model,box,local_cert,cert)
    finally:
        for name,value in saved.items():setattr(u,name,value)
        for name,value in saved_local.items():setattr(local,name,value)
    assert independent['status']=='PASS'
    work=composition['work'];limited=u.verify_coupled_tree_nonnegative_family(model,box,local_cert,cert,max_work=work-1)
    assert limited['status']=='UNKNOWN' and 'WORK_BUDGET' in limited['reason']
    # Independent exact polarization for the native nine-term polynomial, including zero competitor flows.
    leaves=model['leaves'];oracle=[]
    for choice in range(6):
        q=dict(zip(leaves,map(Q,('3/1000','3/2000','1/1000'))))
        competitor={leaf:Q(0) if choice==0 else q[leaf]*Q(choice+index,4) for index,leaf in enumerate(leaves)}
        coeff={k:Q(v['lower'] if choice%2==0 else v['upper']) for k,v in model['coefficients'].items()}
        matrix=[[Q(0) for _ in leaves] for _ in leaves]
        def f(vector):return [sum((coeff[t['coefficient_id']]*sum(vector[j] for j in t['descendant_leaves'])**2 for t in model['terms'] if leaf in t['applies_to_leaves']),Q(0)) for leaf in leaves]
        for term in model['terms']:
            a=coeff[term['coefficient_id']]*sum(q[j]+competitor[j] for j in term['descendant_leaves'])
            for i,leaf in enumerate(leaves):
                for j,other in enumerate(leaves):
                    if leaf in term['applies_to_leaves'] and other in term['descendant_leaves']:matrix[i][j]+=a
        assert [x-y for x,y in zip(f(q),f(competitor))]==[sum(v*(q[leaf]-competitor[leaf]) for v,leaf in zip(row,leaves)) for row in matrix]
        inv,det=inverse_det(matrix);columns=[sum(row[j] for row in inv) for j in range(3)]
        assert det>0 and min(columns)>0 and any(matrix[i][j]!=matrix[j][i] for i in range(3) for j in range(3))
        oracle.append({'case':choice,'determinant':str(det),'inverse_column_sums':[str(v) for v in columns],'competitor_nonnegative':True,'polarization_exact':True})
    assert snapshot=={n:sha(attempt/n) for n in snapshot} and sha(u.__file__)==SOURCE_SHA
    result={'status':'PASS','math_snapshot':BUILD,'source_sha256':SOURCE_SHA,'native_model_root':composition['model_root'],
        'standalone_univalence':check,'composed_local_global':composition,'producer_disabled_composition':independent,
        'resealed_attacks':cases,'late_mutation_attacks':callbacks,'zero_singleton_domain':unsupported,'mismatched_parameter_composition':mismatch,
        'shared_work_limit':limited,'independent_exact_native_polarizations':oracle,
        'scope':'Separate mathematical same-tuple univalence/local-existence conjunction on the declared native-derived polynomial. No native adapter integration, physical applicability beyond stated numerical/ideal assumptions, or project acceptance.'}
    write(out/'result.json',result)
    print(json.dumps({'status':'PASS','directory':str(out),'result_sha256':sha(out/'result.json'),'composed_scope':composition['scope']}))

if __name__=='__main__':main()
