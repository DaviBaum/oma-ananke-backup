"""Independent rational equilibria and proof attacks for the residual adapter."""
from copy import deepcopy
from fractions import Fraction as Q
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import time
import uuid

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
STAGE=ROOT/'.oma/development/passive-residual-bound'
BUILD='123f1fe4133e0d988eed185303364e7c9ab05b43fd08e6f70011c9a4be0ddf7a'
MODULE=STAGE/'runtimes'/BUILD/'src/oma/optimization/passive_residual.py'
EXPECTED='553b92f34237b74018f3de7825c183149c3e5d0c07a271a26ca180592b6ee0fc'
ORACLE=ROOT/'.oma/development/passive-pressure-networks/scripts/independent_kernel_api_audit.py'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def interval(a,b=None):return {'lower':str(a),'upper':str(a if b is None else b)}
def reseal(c):c['certificate_root']=digest({k:v for k,v in c.items() if k!='certificate_root'});return c


def main():
    started=time.perf_counter()
    from oma.optimization import passive_residual as r
    from oma.optimization import passive_pressure as p
    assert Path(r.__file__).resolve()==MODULE.resolve() and sha(MODULE)==EXPECTED
    out=STAGE/'evidence/independent-implementation-review'/uuid.uuid4().hex
    out.mkdir(parents=True)
    for path,name in ((MODULE,'reviewed-passive_residual.py'),(Path(p.__file__),'reviewed-passive_pressure.py'),
            (Path(__file__),'executed-audit.py'),(ORACLE,'independent-equilibrium-oracle.py')):
        shutil.copyfile(path,out/name)
    spec=importlib.util.spec_from_file_location('exact_equilibrium_oracle',out/'independent-equilibrium-oracle.py')
    oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
    cases=[];attacks=[]
    for index in range(24):
        m,h,q=oracle.manufacture(p,17401+index,bool(index%2))
        # Add disjoint zero-span and boundary-only components. The latter has
        # parameterized flow uncertainty but identically zero approximation error.
        if index%3==0:
            m['nodes']+=['C0','C1','C2','W','Z'];m['internal_nodes']+=['C1']
            m['boundary_heads'].update(C0=interval(7),C2=interval(7),W=interval(-2,2),Z=interval(-1,1))
            m['edges'] += [{'id':name,'source':u,'target':v,'resistance':interval(lo,hi)}
                for name,u,v,lo,hi in [('constant-a','C0','C1',1,8),('constant-b','C1','C2',2,12),('boundary-edge','W','Z',1,3)]]
            h.update(C0=Q(7),C1=Q(7),C2=Q(7),W=Q(0),Z=Q(0));q.update({'constant-a':Q(0),'constant-b':Q(0),'boundary-edge':Q(0)})
        x={n:str(h[n]+(Q((-1)**(i+index),100) if n!='C1' and index%4 else 0)) for i,n in enumerate(m['internal_nodes'])}
        cert=r.compile_passive_residual(m,x,pressure_error_target='1/1000000')
        assert cert['status']=='CERTIFIED_BOUND',cert
        checked=r.verify_passive_residual(m,x,cert,pressure_error_target='1/1000000')
        assert checked['status']=='PASS',checked
        error=Q(checked['pressure_l2_error_upper'])
        actual_error_squared=sum((Q(x[n])-h[n])**2 for n in m['internal_nodes'])
        assert actual_error_squared<=error**2
        pb={z['node']:(Q(z['lower']),Q(z['upper'])) for z in checked['pressure_bounds']}
        fb={z['edge']:z for z in checked['flow_error_bounds']}
        assert set(pb)==set(m['nodes']) and set(fb)==set(q)
        assert all(pb[n][0]<=value<=pb[n][1] for n,value in h.items())
        parameter={e['id']:e for e in m['edges']}
        flow_tests=[]
        for name,flow in q.items():
            row=fb[name];assert Q(row['flow_enclosure']['lower'])<=flow<=Q(row['flow_enclosure']['upper'])
            e=parameter[name];u,v=e['source'],e['target']
            true_drop=h[u]-h[v]
            # For manufactured nonzero edges, recover the exact admitted K from
            # the independent rational equilibrium; zero edges use any midpoint.
            k=true_drop/(flow*abs(flow)) if flow else (Q(e['resistance']['lower'])+Q(e['resistance']['upper']))/2
            assert Q(e['resistance']['lower'])<=k<=Q(e['resistance']['upper'])
            approx_drop=Q(x.get(u,h[u]))-Q(x.get(v,h[v]))
            lo,hi=oracle.roots(abs(approx_drop)/k)
            if approx_drop<0:lo,hi=-hi,-lo
            # Exact rational identity resolves an actual zero difference; the
            # unrelated dyadic sqrt oracle need not represent that rational.
            if approx_drop==k*flow*abs(flow):lo=hi=flow
            difference_upper=max(abs(flow-lo),abs(flow-hi));bound=Q(row['flow_error_upper'])
            assert difference_upper<=bound or (flow==lo==hi and bound==0),(name,difference_upper,bound)
            flow_tests.append({'edge':name,'actual_K':str(k),'exact_equilibrium_flow':str(flow),
                'independent_approximate_flow_interval':interval(lo,hi),'difference_upper':str(difference_upper),'claimed_error':str(bound)})
        if index%3==0:
            assert next(v for v in checked['pressure_bounds'] if v['node']=='C1')['coordinate_error_upper']=='0'
            assert fb['boundary-edge']['flow_error_upper']=='0'
            assert Q(fb['boundary-edge']['flow_enclosure']['lower'])<0<Q(fb['boundary-edge']['flow_enclosure']['upper'])
        cases.append({'seed':17401+index,'model':m,'approximation':x,'exact_heads':{k:str(v) for k,v in h.items()},
            'actual_error_squared':str(actual_error_squared),'flow_family_tests':flow_tests,'certificate':cert,'verification':checked})
        for field in ('conductances','grounding_paths','approximate_flow_edges','residuals','pressure_bounds','solution_flow_edges','flow_error_bounds'):
            bad=deepcopy(cert);bad[field][-1]=deepcopy(bad[field][0]);reseal(bad)
            verdict=r.verify_passive_residual(m,x,bad,pressure_error_target='1/1000000')
            assert verdict['status']=='FAIL',(field,verdict)
            attacks.append({'case':index,'mutation':'duplicate_'+field,'result':verdict})
        for field in ('sigma_head_per_flow','residual_squared_norm_upper','pressure_l2_error_upper'):
            bad=deepcopy(cert);bad[field]=str(Q(bad[field])+1);reseal(bad)
            verdict=r.verify_passive_residual(m,x,bad,pressure_error_target='1/1000000')
            assert verdict['status']=='FAIL',(field,verdict)
            attacks.append({'case':index,'mutation':'forged_'+field,'result':verdict})
    first=cases[1];m,x,c=first['model'],first['approximation'],first['certificate']
    def forbidden(*a,**kw):raise AssertionError('Producer used by verifier')
    saved={n:getattr(r,n) for n in ('_make_conductances','_make_paths')}
    psaved={n:getattr(p,n) for n in ('_sqrt','_producer_edges','_producer_flow','_producer_residual','isqrt')}
    try:
        for n in saved:setattr(r,n,forbidden)
        for n in psaved:setattr(p,n,forbidden)
        independent=r.verify_passive_residual(m,x,c,pressure_error_target='1/1000000')
        assert independent['status']=='PASS'
    finally:
        for n,v in saved.items():setattr(r,n,v)
        for n,v in psaved.items():setattr(p,n,v)
    for kind in ('model','approximation','certificate'):
        mm,xx,cc=deepcopy(m),deepcopy(x),deepcopy(c);hit=[]
        def mutate(stage):
            if stage=='residual_verifier_complete':
                hit.append(stage)
                if kind=='model':mm['context_root']='c'*64
                elif kind=='approximation':xx[next(iter(xx))]='0'
                else:cc['pressure_l2_error_upper']='0'
        result=r.verify_passive_residual(mm,xx,cc,pressure_error_target='1/1000000',checkpoint=mutate)
        assert hit==['residual_verifier_complete'] and result['status']=='FAIL',result
        attacks.append({'mutation':'last_callback_'+kind,'result':result})
    budgets=[]
    for kw in ({'max_work':1},{'max_path_steps':0},{'max_input_bytes':256},{'max_certificate_bytes':256}):
        v=r.verify_passive_residual(m,x,c,pressure_error_target='1/1000000',**kw)
        assert v['status']=='UNKNOWN',v;budgets.append({'budget':kw,'result':v})
    assert sha(MODULE)==EXPECTED and sha(ORACLE)==sha(out/'independent-equilibrium-oracle.py')
    result={'status':'INDEPENDENT_RESIDUAL_IMPLEMENTATION_AUDIT_PASS','build':BUILD,'module_sha256':EXPECTED,
        'oracle_sha256':sha(ORACLE),'model_cases':len(cases),'resealed_and_late_mutation_attacks':len(attacks),
        'budget_unknown_cases':len(budgets),'producer_disabled_verifier':independent,
        'cases':cases,'attacks':attacks,'budgets':budgets,'seconds':time.perf_counter()-started,
        'scope':'Exact manufactured parameter instances inside full declared boxes; independent implementation challenge, not exhaustive mathematical proof or native applicability certification',
        'review_findings':['Positive bounded-drop conductance is independently gated by 4*c^2*Kmax*M<=1.',
            'Complete simple actual grounding paths establish a conservative global sigma; path optimality is never required.',
            'The residual includes all signed incidences with each actual boundary tuple, not a boundary-midpoint substitution.',
            'Constant disconnected components and boundary-only families keep exact zero approximation error while interval variation remains separate.',
            'Absolute flow boxes widen the whole approximate family and intersect a separately checked pressure-image box; zero-crossing factor two remains explicit.',
            'Final input/proof identity guards disable callbacks before bounded rehash; no partial budget exhaustion gains bound authority.']}
    write(out/'result.json',result)
    (out/'README.md').write_text('Read-only review of frozen residual module 553b / build 123f. Twenty-four independently manufactured exact rational equilibria cover random oriented trees/loops and eight mixed disconnected constant/boundary-only additions. All actual pressure errors and per-edge errors against the parameterized approximate family fit the checked bounds. Two hundred forty resealed proof-field attacks plus three final-callback identity attacks fail, and four resource limits return UNKNOWN. Disabling producer and radical-generation helpers leaves independent verification working. No mathematical counterexample or concrete implementation authority gap was found in this bounded review. The result does not establish native physical applicability or a tight correlated uncertainty hull.\n',encoding='utf-8')
    print(json.dumps({'directory':str(out),'result_sha256':sha(out/'result.json'),'cases':len(cases),'attacks':len(attacks),'seconds':result['seconds']}))

if __name__=='__main__':main()
