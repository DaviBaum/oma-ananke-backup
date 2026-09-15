"""Independent finite-coverage/rank attacks on the immutable synthesis kernel."""
from copy import deepcopy
from fractions import Fraction as Q
from functools import cmp_to_key
from pathlib import Path
import hashlib
import importlib.util
import json
import shutil
import sys
import uuid
import reference as ref

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').exists())
STAGE=Path(__file__).resolve().parent
KERNEL=ROOT/'.oma/development/shared-tree-synthesis/runtimes/d1245404a41acadc38880a45a584757654c867aeb15971d7260cccf817551cb7/src/oma/optimization/shared_tree_synthesis.py'
EXPECTED='0034130d057fbb012d031fb31a69ce89aac857ce6aeaf4d8a73f55c2d1a23d43'
NATIVE=STAGE/'evidence/4d1dc2c5572143f3a8a3e8a8b0d5a300'

def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def seal(proof):
    proof.pop('certificate_root',None);proof['certificate_root']=ref.digest(proof);return proof

def exact_compare(a,b):
    da,db=[Q(x)-Q(y) for x,y in zip(a['nominal_cost'],b['nominal_cost'])]
    if not da and not db: return (a['connector_ids']>b['connector_ids'])-(a['connector_ids']<b['connector_ids'])
    bounds=[]
    for d in (5,239):
        total=sum((Q((-1)**k,(2*k+1)*d**(2*k+1)) for k in range(64)),Q(0))
        tail=Q(1,129*d**129);bounds.append((total,total+tail))
    lo,hi=16*bounds[0][0]-4*bounds[1][1],16*bounds[0][1]-4*bounds[1][0]
    a,b=sorted((da+db*lo,da+db*hi));assert a>0 or b<0
    return 1 if a>0 else -1

def main():
    assert sha(KERNEL)==EXPECTED
    out=STAGE/'kernel-peer-audits'/uuid.uuid4().hex;out.mkdir(parents=True)
    for p in (Path(__file__),Path(__file__).with_name('reference.py'),KERNEL): shutil.copyfile(p,out/p.name)
    spec=importlib.util.spec_from_file_location('independent_frozen_synthesis',KERNEL);k=importlib.util.module_from_spec(spec);spec.loader.exec_module(k)
    def verify(model,cert,**kw):
        names=('compile_shared_tree_catalogue','_producer_assignments','_pi_producer');saved={n:getattr(k,n) for n in names}
        def disabled(*a,**b): raise AssertionError('Verifier called producer')
        for n in names:setattr(k,n,disabled)
        try:return k.verify_shared_tree_catalogue(model,cert,**kw)
        finally:
            for n,v in saved.items():setattr(k,n,v)
    results=[];attacks=[];budgets=[]
    for n in (2,3):
        model=read(NATIVE/f'catalogue-{n}.json');oracle=read(NATIVE/f'oracle-{n}.json')
        produced=k.compile_shared_tree_catalogue(model);assert produced['status']=='CERTIFIED'
        checked=verify(model,produced['certificate']);assert checked['status']=='PASS'
        proposals=checked['proposals'];assert len(proposals)==len(oracle)
        for got,want in zip(proposals,oracle):
            for key in ('tee_ids','connector_ids','nominal_cost'):assert got[key]==want[key]
            assert {s['id']:s['connector_path'] for s in got['sinks']}==want['sink_connector_paths']
        ref.write(out/f'kernel-{n}.json',{'producer':produced,'independent_verifier':checked})
        results.append({'sinks':n,'assignments':len(oracle),'status':'PASS','complete_oracle_equal':True})
        def attack(name,mutate):
            proof=deepcopy(produced['certificate']);mutate(proof);seal(proof)
            answer=verify(model,proof);attacks.append({'sinks':n,'name':name,'status':answer['status'],'reason':answer.get('reason')})
            assert answer['status']=='FAIL',name
        attack('omitted_assignment',lambda p:p['assignments'].pop())
        def remove_and_recount(p):
            gone=p['assignments'].pop();p['assignment_count']-=1;p['ranked_prefix'].remove(gone['assignment_root'])
        attack('coherent_omission_and_recount',remove_and_recount)
        attack('duplicated_assignment',lambda p:p['assignments'].append(deepcopy(p['assignments'][0])))
        attack('invented_short_cost',lambda p:p['assignments'][0].update(nominal_cost=['0','0']))
        attack('omitted_tee',lambda p:p['assignments'][0]['tee_ids'].pop())
        attack('duplicated_connector',lambda p:p['assignments'][0]['connector_ids'].append(p['assignments'][0]['connector_ids'][0]))
        attack('wrong_assignment_root',lambda p:p['assignments'][0].update(assignment_root='0'*64))
        attack('rank_swap',lambda p:p['ranked_prefix'].reverse())
        attack('rank_omission',lambda p:p['ranked_prefix'].pop())
        attack('unscoped_physical_claim',lambda p:p.update(scope='GLOBAL_NATIVE_OPTIMUM'))
        attack('omitted_limitations',lambda p:p.update(limitations=[]))
        attack('header_bool_alias',lambda p:p.update(assignment_count=True))
        for field in ('context_root','cost_policy_root'):
            altered=deepcopy(model);altered[field]='0'*64;ans=verify(altered,produced['certificate']);assert ans['status']=='FAIL'
            attacks.append({'sinks':n,'name':'changed_'+field,'status':ans['status']})
        for target in ('model','certificate'):
            m,c=deepcopy(model),deepcopy(produced['certificate'])
            def callback(stage):
                if stage=='shared_tree_verifier_complete':
                    if target=='model':m['source_roots']['original_ifc']='0'*64
                    else:c['ranked_prefix'].clear()
            ans=verify(m,c,checkpoint=callback);assert ans['status']=='FAIL'
            attacks.append({'sinks':n,'name':'final_callback_'+target,'status':ans['status']})
        for kw in ({'max_work':checked['work']-1},{'max_assignments':1},{'max_bytes':256},{'max_connectors':1}):
            ans=verify(model,produced['certificate'],**kw);assert ans['status']=='UNKNOWN' and not ans['proof_complete'] and ans['proposals']==[]
            budgets.append({'sinks':n,'limits':kw,'status':ans['status'],'reason':ans['reason']})
        # Prefix output quotas never reduce the complete checked assignment ledger.
        small=k.compile_shared_tree_catalogue(model,max_results=1);ans=verify(model,small['certificate'],max_results=1)
        assert ans['status']=='PASS' and len(ans['proposals'])==1 and ans['counts']['complete_assignments']==len(oracle)
    base=read(NATIVE/'catalogue-2.json');empty=deepcopy(base);empty['connectors']=[]
    absent=k.compile_shared_tree_catalogue(empty);absent_checked=verify(empty,absent['certificate'])
    assert absent_checked['status']=='PASS' and absent_checked['proposals']==[]
    # Add parallel catalogue choices and deliberately close rational/pi costs.
    parallel=deepcopy(base)
    parallel['tee_instances'][0]['nominal_cost']=['0','0'];parallel['tee_instances'][1]['nominal_cost']=['0','0']
    for c in parallel['connectors']:c['nominal_cost']=['0','0']
    original=next(c for c in parallel['connectors'] if c['id']=='source-A')
    original['nominal_cost']=['0','1']
    for suffix,cost in [('lower',['333/106','0']),('upper',['355/113','0']),('equal',['0','1'])]:
        variant=deepcopy(original);variant['id']='parallel-'+suffix;variant['nominal_cost']=cost;parallel['connectors'].append(variant)
    expected=sorted(ref.enumerate_oracle(parallel),key=cmp_to_key(exact_compare))
    pp=k.compile_shared_tree_catalogue(parallel);pv=verify(parallel,pp['certificate']);assert pv['status']=='PASS'
    assert [(x['connector_ids'],x['nominal_cost']) for x in pv['proposals']]==[(x['connector_ids'],x['nominal_cost']) for x in expected]
    ref.write(out/'parallel-rank.json',{'problem':parallel,'producer':pp,'independent_verifier':pv,'independent_rational_pi_oracle':expected})
    # Native identity roots remain declarations; pure proof cannot authenticate a fabricated root.
    unauthenticated=deepcopy(base);unauthenticated['connectors'][0]['geometry_root']='0'*64
    scoped=k.compile_shared_tree_catalogue(unauthenticated);sv=verify(unauthenticated,scoped['certificate']);assert sv['status']=='PASS'
    from audit import check_artifacts
    try:check_artifacts(unauthenticated,read(NATIVE/'artifacts-2.json'))
    except AssertionError: native_scope='EXTERNAL_NATIVE_ARTIFACT_BINDING_REJECTED'
    else:raise AssertionError('Native artifact identity was not checked')
    summary={'status':'PASS','kernel_sha256':sha(KERNEL),'actual_catalogue_results':results,'producer_disabled_verifier':True,
             'resealed_and_mutation_attacks':attacks,'bounded_unknown_results':budgets,'parallel_rank_assignments':len(expected),
             'empty_catalogue_scope':'CERTIFIED_FINITE_ABSENCE_ONLY','native_identity_scope':native_scope,
             'limitations':['No false defect found in this bounded implementation audit.','Pure-kernel PASS does not authenticate native roots or establish native feasibility.']}
    ref.write(out/'result.json',summary);print(json.dumps({'status':'PASS','evidence':str(out),'attacks':len(attacks),'budget_unknown':len(budgets),'parallel_assignments':len(expected)}))

if __name__=='__main__':main()
