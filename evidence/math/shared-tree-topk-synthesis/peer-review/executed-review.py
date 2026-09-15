"""Read-only independent edge-subset oracle and resealed compact proof review."""
import copy,hashlib,itertools,json,os,random,sys,time,uuid
from fractions import Fraction as Q
from pathlib import Path
ROOT=Path.cwd()
FROZEN=ROOT/'.oma/development/shared-tree-topk-synthesis/validation/ef68bb4f7ebb443e99204d20e9fbb068/snapshot'
OUT=Path(__file__).resolve().parent/uuid.uuid4().hex;OUT.mkdir()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(name,v):(OUT/name).write_text(json.dumps(v,indent=2),encoding='utf-8')
inputs={p.relative_to(FROZEN).as_posix():sha(p) for p in FROZEN.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
assert inputs['src/oma/optimization/shared_tree_topk.py']=='d04f2ad9ffb72f9935cba93472f49f5dbbe257a0595ccc8c39dcb62d14ca2dbc'
sys.path[:0]=[str(FROZEN/'src'),str(FROZEN/'tests')]
os.environ['OMA_SHARED_TREE_SOURCE']=str(FROZEN/'src/oma/optimization/shared_tree_synthesis.py')
from oma.optimization import shared_tree_topk as t
import test_general_shared_tree_synthesis as f
def oracle(p):
    """Every fixed-size edge subset; degree equations and directed reachability."""
    source=p['source']['id'];leaves={x['id'] for x in p['sinks']};tees={x['id']:x for x in p['tee_instances']}
    valid={};considered=0
    for edges in itertools.combinations(p['connectors'],2*len(leaves)-1):
        considered+=1;incoming={};outgoing={};used=set();bad=False
        for e in edges:
            a,b=e['from']['node'],e['to']['node'];slot=(a,e['from']['port'])
            if b in incoming or slot in outgoing:bad=True;break
            incoming[b]=a;outgoing[slot]=b;used|={a,b}
        if bad:continue
        selected=used & set(tees)
        if len(selected)!=len(leaves)-1 or used!={source}|leaves|selected:continue
        if set(incoming)!=leaves|selected:continue
        if set(outgoing)!={(source,'out')}|{(a,b) for a in selected for b in ('b','branch')}:continue
        reached={source}
        for _ in range(len(used)):
            reached|={b for (a,_),b in outgoing.items() if a in reached}
        if reached!=used:continue
        word=tuple(sorted(e['id'] for e in edges));assert word not in valid
        cost=sum((Q(e['nominal_cost'][0]) for e in (*edges,*(tees[x] for x in selected))),Q())
        valid[word]=(cost,tuple(sorted(selected)))
    return valid,considered
def seal(c):
    c['certificate_root']=f.digest({k:v for k,v in c.items() if k!='certificate_root'});return c
started=time.monotonic();rows=[];attacks=[]
try:
    for seed in range(14):
        n=3 if seed>=12 else 2+seed%3;rng=random.Random(84319+seed)
        p=f.catalogue(n,dense=True,extra_tees=1,parallel=False)
        chain=f.catalogue(n,extra_tees=1,parallel=False)
        keys={(e['from']['node'],e['from']['port'],e['to']['node']) for e in chain['connectors']}
        required=[e for e in p['connectors'] if (e['from']['node'],e['from']['port'],e['to']['node']) in keys]
        others=[e for e in p['connectors'] if e not in required];rng.shuffle(others)
        p['connectors']=required+(others if seed>=12 else others[:15-len(required)])
        twin=copy.deepcopy(p['connectors'][seed%len(p['connectors'])]);twin['id']='parallel-'+str(seed);p['connectors'].append(twin)
        for x in p['connectors']+p['tee_instances']:x['nominal_cost']=[str(Q(rng.randrange(5),rng.randrange(1,5))),'0']
        if seed%3==0:
            for x in p['connectors']+p['tee_instances']:x['nominal_cost']=['0','0']
        rng.shuffle(p['connectors']);rng.shuffle(p['tee_instances']);rng.shuffle(p['sinks'])
        answer,considered=oracle(p);assert answer
        ranking=sorted(answer,key=lambda word:(answer[word][0],word))
        for k in (1,3,8):
            a=t.compile_shared_tree_topk_catalogue(p,k=k);assert a['status']=='CERTIFIED',a
            assert int(a['counts']['complete_assignments'])==len(answer)
            assert [tuple(x['connector_ids']) for x in a['proposals']]==ranking[:k]
            for x in a['proposals']:
                cost,tees=answer[tuple(x['connector_ids'])]
                assert tuple(x['tee_ids'])==tees and Q(x['nominal_cost'][0])==cost and Q(x['nominal_cost'][1])==0
            original=t._producer_states;t._producer_states=lambda *a,**k:(_ for _ in ()).throw(AssertionError('producer disabled'))
            try:b=t.verify_shared_tree_topk_catalogue(p,a['certificate'],k=k)
            finally:t._producer_states=original
            assert b['status']=='PASS' and b['proposals']==a['proposals']
            rows.append({'seed':seed,'n':n,'k':k,'enumerated_edge_subsets':considered,'full_count':len(answer),'input_root':a['input_root'],'certificate_root':a['certificate_root']})
        if seed==0:
            for mode in ('omit_state','count_plus_one','mask_bool','label_duplicate','omit_prefix','false_domain','false_k'):
                bad=copy.deepcopy(a['certificate'])
                if mode=='omit_state':bad['states'].pop()
                elif mode=='count_plus_one':bad['states'][0]['tree_count']=str(int(bad['states'][0]['tree_count'])+1)
                elif mode=='mask_bool':bad['states'][0]['state'][1]=True
                elif mode=='label_duplicate':bad['states'][0]['labels'].append(copy.deepcopy(bad['states'][0]['labels'][0]))
                elif mode=='omit_prefix':bad['ranked_prefix'].pop()
                elif mode=='false_domain':bad['state_domain_count']+=1
                else:bad['k']=7
                v=t.verify_shared_tree_topk_catalogue(p,seal(bad),k=8);assert v['status']!='PASS'
                attacks.append({'mode':mode,'status':v['status'],'reason':v['reason']})
    assert inputs=={p.relative_to(FROZEN).as_posix():sha(p) for p in FROZEN.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    write('result.json',{'status':'PASS','seconds':time.monotonic()-started,'comparisons':rows,'resealed_attacks':attacks,'frozen_inputs':inputs,
        'script_sha256':sha(__file__),'scope':'Independent finite edge-subset exact rational cost oracle on12 sparse plus2 dense weighted/zero-tie catalogues with extra tees/parallel edges;42 prefixes and producer-disabled replays;7 resealed attacks. No physical/native or unconstrained search claim.'})
except BaseException as e:
    write('result.json',{'status':'FAIL','error':repr(e),'comparisons':rows,'resealed_attacks':attacks});raise
finally:
    (OUT/'executed-review.py').write_bytes(Path(__file__).read_bytes())
print(json.dumps({'directory':str(OUT),'result_sha256':sha(OUT/'result.json'),'seconds':time.monotonic()-started}))
