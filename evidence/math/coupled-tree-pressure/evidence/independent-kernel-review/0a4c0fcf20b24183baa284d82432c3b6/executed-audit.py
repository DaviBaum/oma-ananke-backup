"""Independent exact hierarchical roots and complete rational Banach replay."""
from copy import deepcopy
from fractions import Fraction as Q
import hashlib
import itertools
import json
from pathlib import Path
import random
import shutil
import time
import uuid

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
STAGE=ROOT/'.oma/development/coupled-tree-pressure'
BUILD='a6ac45709a8ae32ac117acb48f011bf74340b8393cb07e7700432965d83bb0e6'
EXPECTED='56b72b90155f41450ada3ed620d11bc6f443039bc8e00af5c0cd08070ae55022'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def enc(a,b=None):return {'lower':str(a),'upper':str(a if b is None else b)}
def dec(v):return Q(v['lower']),Q(v['upper'])
def add(a,b):return a[0]+b[0],a[1]+b[1]
def sub(a,b):return a[0]-b[1],a[1]-b[0]
def mul(a,b):
    x=[u*v for u in a for v in b];return min(x),max(x)
def isum(values):
    value=(Q(0),Q(0))
    for v in values:value=add(value,v)
    return value
def encode_matrix(m,interval=False):return [[enc(*v) if interval else str(v) for v in row] for row in m]
def reseal(c):c['certificate_root']=digest({k:v for k,v in c.items() if k!='certificate_root'});return c


def losses(model,flows,coefficients):
    return {i:sum(coefficients[t['coefficient_id']]*sum(flows[j] for j in t['descendant_leaves'])**2
        for t in model['terms'] if i in t['applies_to_leaves']) for i in model['leaves']}


def manufacture(module,seed,n):
    rng=random.Random(seed);leaves=[f'L{i}' for i in range(n)]
    q={i:Q(rng.randrange(3,13),4) for i in leaves};width={i:q[i]/1000 for i in leaves}
    terms=[];coeff={'shared-pipe':Q(1,100)}
    def term(name,a,d,app,reused=False):
        key='shared-pipe' if reused else name
        if not reused:coeff[key]=a
        terms.append({'id':name,'coefficient_id':key,'descendant_leaves':d,'applies_to_leaves':app})
    def branch(group,name):
        if len(group)==1:
            term('leaf-'+group[0],Q(rng.randrange(4,11)),group,group);return
        split=len(group)//2;a,b=group[:split],group[split:]
        term('pipe-'+name,Q(1,100),group,group,True)
        term('tee-'+name+'-a',Q(rng.randrange(1,8),20),group,a)
        term('tee-'+name+'-b',Q(rng.randrange(9,16),20),group,b)
        branch(a,name+'a');branch(b,name+'b')
    branch(leaves,'root')
    if n==1:coeff.pop('shared-pipe')
    epsilon=Q(1,1000000) if seed%2 else Q(0)
    intervals={i:enc(v*(1-epsilon),v*(1+epsilon)) for i,v in coeff.items()}
    m={'schema':module.MODEL_SCHEMA,'leaves':leaves,'coefficients':intervals,'terms':terms,
        'context_root':'a'*64,'physical_model_root':'b'*64,'assumptions':deepcopy(module.MODEL_ASSUMPTIONS)}
    lowq={i:q[i]-width[i]/100 for i in leaves};highq={i:q[i]+width[i]/100 for i in leaves}
    low=losses(m,lowq,{k:Q(v['lower']) for k,v in intervals.items()})
    high=losses(m,highq,{k:Q(v['upper']) for k,v in intervals.items()})
    m['available_heads']={i:enc(low[i],high[i]) for i in leaves}
    box={i:enc(q[i]-width[i],q[i]+width[i]) for i in leaves}
    samples=[]
    for s in range(4):
        flow={i:q[i]+((-1)**(s+j))*width[i]/100 for j,i in enumerate(leaves)}
        values={k:Q(v['lower'] if (s+j)%2 else v['upper']) for j,(k,v) in enumerate(intervals.items())}
        heads=losses(m,flow,values)
        assert all(low[i]<=heads[i]<=high[i] for i in leaves)
        samples.append({'flows':flow,'coefficients':values,'heads':heads})
    return m,box,q,samples


def independent_replay(m,box,packet):
    names=sorted(m['leaves']);n=len(names);center={i:Q(packet['center'][i]) for i in names}
    a={k:dec(v) for k,v in m['coefficients'].items()};bounds={i:dec(box[i]) for i in names}
    terms=m['terms']
    f={i:sub(isum(mul(a[t['coefficient_id']],(sum(center[j] for j in t['descendant_leaves'])**2,)*2)
        for t in terms if i in t['applies_to_leaves']),dec(m['available_heads'][i])) for i in names}
    j=[[isum(mul(a[t['coefficient_id']],(2*sum(bounds[k][0] for k in t['descendant_leaves']),
        2*sum(bounds[k][1] for k in t['descendant_leaves']))) for t in terms
        if row in t['applies_to_leaves'] and col in t['descendant_leaves']) for col in names] for row in names]
    assert packet['center_residual']=={i:enc(*v) for i,v in f.items()}
    assert packet['jacobian']==encode_matrix(j,True)
    r=[[Q(x) for x in row] for row in packet['preconditioner']]
    inv=[[Q(x) for x in row] for row in packet['inverse_witness']]
    identity=[[Q(int(i==k)) for k in range(n)] for i in range(n)]
    for first,second in ((r,inv),(inv,r)):
        assert [[sum(first[i][k]*second[k][j] for k in range(n)) for j in range(n)] for i in range(n)]==identity
    b=[[sub((Q(int(i==col)),)*2,isum(mul((r[i][k],)*2,j[k][col]) for k in range(n))) for col in range(n)] for i in range(n)]
    norms=[sum(max(abs(v[0]),abs(v[1])) for v in row) for row in b]
    images={};root={};margins={}
    for i,name in enumerate(names):
        images[name]=sub((center[name],)*2,isum(mul((r[i][k],)*2,f[node]) for k,node in enumerate(names)))
        root[name]=add(images[name],isum(mul(b[i][k],sub(bounds[node],(center[node],)*2)) for k,node in enumerate(names)))
        margins[name]={'lower':str(root[name][0]-bounds[name][0]),'upper':str(bounds[name][1]-root[name][1])}
    expected={'derivative_map':encode_matrix(b,True),'row_norm_upper':[str(x) for x in norms],
        'contraction_norm_upper':str(max(norms)),'center_image':{i:enc(*x) for i,x in images.items()},
        'root_enclosure':{i:enc(*x) for i,x in root.items()},'inclusion_margins':margins}
    assert all(packet[k]==v for k,v in expected.items())
    assert max(norms)<1 and all(Q(v)>0 for row in margins.values() for v in row.values())
    return expected


def main():
    from oma.optimization import coupled_tree_pressure as c
    module=Path(c.__file__);assert sha(module)==EXPECTED and BUILD in str(module)
    start=time.perf_counter();out=STAGE/'evidence/independent-kernel-review'/uuid.uuid4().hex;out.mkdir(parents=True)
    for path,name in ((module,'reviewed-kernel.py'),(Path(c.p.__file__),'reviewed-rational-helper.py'),(Path(__file__),'executed-audit.py')):shutil.copyfile(path,out/name)
    cases=[];attacks=[]
    for index in range(24):
        m,box,nominal,samples=manufacture(c,41200+index,1+index%8)
        cert=c.compile_coupled_tree_pressure(m,box);assert cert['status']=='CERTIFIED_BOX',cert
        verified=c.verify_coupled_tree_pressure(m,box,cert);assert verified['status']=='PASS',verified
        independent=independent_replay(m,box,cert)
        for sample in samples:
            assert losses(m,sample['flows'],sample['coefficients'])==sample['heads']
            assert all(Q(cert['root_enclosure'][i]['lower'])<=q<=Q(cert['root_enclosure'][i]['upper']) for i,q in sample['flows'].items())
        nonsymmetric=any(cert['jacobian'][i][j]!=cert['jacobian'][j][i] for i in range(len(m['leaves'])) for j in range(len(m['leaves'])))
        assert nonsymmetric or len(m['leaves'])==1
        cases.append({'model':m,'flow_box':box,'exact_parameter_root_samples':[{k:{n:str(v) for n,v in values.items()} for k,values in s.items()} for s in samples],
            'certificate':cert,'independent_rational_replay':independent,'verification':verified,'nonsymmetric_jacobian':nonsymmetric})
        first=sorted(m['leaves'])[0]
        changes=[(('term_evidence',),[]),(('inventories','equation_terms',first),[]),
            (('center_residual',first,'lower'),'999'),(('jacobian',0,0,'lower'),'999'),
            (('preconditioner',0,0),'0'),(('inverse_witness',0,0),'0'),(('derivative_map',0,0,'lower'),'999'),
            (('contraction_norm_upper',),'0'),(('root_enclosure',first,'lower'),'0'),(('inclusion_margins',first,'lower'),'999'),
            (('scope',),'GLOBAL_UNIQUENESS'),(('limitations','other_equilibria_excluded'),True)]
        for path,value in changes:
            bad=deepcopy(cert);cursor=bad
            for key in path[:-1]:cursor=cursor[key]
            assert cursor[path[-1]]!=value
            cursor[path[-1]]=value;reseal(bad)
            verdict=c.verify_coupled_tree_pressure(m,box,bad);assert verdict['status']=='FAIL',(path,verdict)
            attacks.append({'case':index,'changed_path':list(path),'result':verdict})
    m,box,_,_=manufacture(c,41203,4);cert=c.compile_coupled_tree_pressure(m,box)
    def forbidden(*a,**kw):raise AssertionError('Independent verifier called producer')
    saved={n:getattr(c,n) for n in ('compile_coupled_tree_pressure','_inverse','_produce_polynomial','_term_values')}
    try:
        for n in saved:setattr(c,n,forbidden)
        disabled=c.verify_coupled_tree_pressure(m,box,cert);assert disabled['status']=='PASS'
    finally:
        for n,v in saved.items():setattr(c,n,v)
    for verify in (False,True):
        for target in ('model','box','certificate') if verify else ('model','box'):
            mm,bb,cc=deepcopy(m),deepcopy(box),deepcopy(cert);seen=[]
            def mutate(stage):
                if seen:raise AssertionError('Callback after final checkpoint')
                if stage==('coupled_verifier_complete' if verify else 'coupled_producer_complete'):
                    seen.append(stage)
                    if target=='model':mm['context_root']='e'*64
                    elif target=='box':bb[next(iter(bb))]['lower']='1/1000000'
                    else:cc['contraction_norm_upper']='0'
            result=c.verify_coupled_tree_pressure(mm,bb,cc,checkpoint=mutate) if verify else c.compile_coupled_tree_pressure(mm,bb,checkpoint=mutate)
            assert seen and result['status']==('FAIL' if verify else 'INVALID_INPUT')
            attacks.append({'changed_path':['last_callback',target],'result':result})
    budgets=[]
    for limits in ({'max_leaves':1},{'max_terms':1},{'max_matrix_entries':1},{'max_work':1},{'max_input_bytes':256},{'max_certificate_bytes':256}):
        v=c.verify_coupled_tree_pressure(m,box,cert,**limits);assert v['status']=='UNKNOWN',v;budgets.append({'limits':limits,'result':v})
    assert sha(module)==EXPECTED
    result={'status':'INDEPENDENT_COUPLED_TREE_BOX_KERNEL_AUDIT_PASS','build':BUILD,'module_sha256':EXPECTED,
        'models':len(cases),'distinct_exact_parameter_root_instances':sum(len(v['exact_parameter_root_samples']) for v in cases),
        'nonsymmetric_models':sum(v['nonsymmetric_jacobian'] for v in cases),'rejected_attacks':len(attacks),
        'independent_full_F_J_inverse_B_norm_K_replay':True,'producer_disabled_verifier':disabled,'budget_unknowns':budgets,
        'cases':cases,'attacks':attacks,'seconds':time.perf_counter()-start,
        'scope':'One root inside the declared positive box for each same parameter tuple. No global univalence, native applicability, physical completeness, delivery or velocity authority.'}
    (out/'result.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    (out/'README.md').write_text('Twenty-four independently manufactured rational hierarchical tree models (one to eight leaves) exercise unequal outlet losses and reused named parameters. Ninety-six distinct admitted parameter/root instances satisfy the complete equations and the certified enclosure. Separate Fraction interval code exactly reconstructs center residuals, nonsymmetric Jacobians, both inverse products, the derivative map, norm and fixed-point image. Re-sealed inventory/algebra/scope attacks and final-callback mutation fail; six resource limits return UNKNOWN and disabling producer helpers leaves verification working. This bounded review found no concrete kernel soundness defect. It establishes no global uniqueness or native physical applicability.\n',encoding='utf-8')
    print(json.dumps({'directory':str(out),'result_sha256':sha(out/'result.json'),'models':len(cases),'attacks':len(attacks),'seconds':result['seconds']}))

if __name__=='__main__':main()
