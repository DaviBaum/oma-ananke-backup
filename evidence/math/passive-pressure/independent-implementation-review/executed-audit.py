"""Independent manufactured-network oracle and coherent proof attacks."""
from pathlib import Path
from fractions import Fraction as Q
from copy import deepcopy
import hashlib
import importlib.util
import itertools
import json
import random
import time
import uuid
from math import isqrt

STAGE = Path(__file__).resolve().parents[1]
MODULE = STAGE / 'src/oma/optimization/passive_pressure.py'
EXPECTED = '10fd4677d37952d4e0b41a1bf90aeba9bbdef5506e7e5c33ec8773dd456ec51e'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def interval(a, b=None):
    return {'lower': str(a), 'upper': str(a if b is None else b)}


def bounds(rows, key):
    return {r[key]: (Q(r['lower']), Q(r['upper'])) for r in rows}


def gaussian(matrix, vector):
    rows = [list(row) + [v] for row, v in zip(matrix, vector)]
    n = len(rows)
    for col in range(n):
        pivot = next(i for i in range(col, n) if rows[i][col])
        rows[col], rows[pivot] = rows[pivot], rows[col]
        scale = rows[col][col]
        rows[col] = [v / scale for v in rows[col]]
        for i in range(n):
            if i != col:
                scale = rows[i][col]
                rows[i] = [a - scale*b for a,b in zip(rows[i], rows[col])]
    return [row[-1] for row in rows]


def manufacture(p, seed, uncertain):
    # Solve a rational linear conductance network, then choose each quadratic
    # K so these exact heads/flows also solve the different passive law.
    rng = random.Random(seed)
    n = rng.randrange(4, 9)
    nodes = [str(i) for i in range(n)]
    internal = nodes[1:-1]
    boundary = {'0': Q(rng.randrange(5,15)), str(n-1): Q(-rng.randrange(0,4))}
    undirected = {(str(i-1), str(i)) for i in range(1,n)}
    undirected |= {pair for pair in itertools.combinations(nodes,2) if rng.random() < .45}
    edges = []
    for i,(u,v) in enumerate(sorted(undirected)):
        if rng.randrange(2): u,v = v,u
        edges.append((f'e{i}',u,v,Q(rng.randrange(1,8),rng.randrange(1,8))))
    a = [[Q(0) for _ in internal] for _ in internal]
    b = [Q(0) for _ in internal]
    for _,u,v,g in edges:
        for x,y in ((u,v),(v,u)):
            if x in internal:
                i = internal.index(x); a[i][i] += g
                if y in internal: a[i][internal.index(y)] -= g
                else: b[i] += g*boundary[y]
    head = {**boundary, **dict(zip(internal, gaussian(a,b)))}
    flows, native_edges = {}, []
    divergence = {v:Q(0) for v in nodes}
    for name,u,v,g in edges:
        q = g*(head[u]-head[v])
        k = (head[u]-head[v])/(q*abs(q)) if q else Q(3,2)
        assert k > 0 and head[u]-head[v] == k*q*abs(q)
        flows[name] = q; divergence[u] += q; divergence[v] -= q
        native_edges.append({'id':name,'source':u,'target':v,'resistance':
            interval(k*Q(9,10),k*Q(11,10)) if uncertain else interval(k)})
    assert all(divergence[v] == 0 for v in internal)
    model = {'schema':p.MODEL_SCHEMA,'nodes':nodes,'internal_nodes':internal,
        'boundary_heads':{v:interval(h-Q(1,10),h+Q(1,10)) if uncertain else interval(h) for v,h in boundary.items()},
        'edges':native_edges,'context_root':'a'*64,'physical_model_root':'b'*64,
        'assumptions':deepcopy(p.MODEL_ASSUMPTIONS)}
    return model, head, flows


def roots(value):
    scale = 1 << 100
    a = Q(isqrt(value.numerator*scale*scale//value.denominator),scale)
    return a, a if a*a == value else a + Q(1,scale)


def independent_packet(model, certificate, pressures):
    c = deepcopy(certificate)
    edge_order = sorted(model['edges'], key=lambda e:e['id'])
    bd = set(model['boundary_heads'])

    def edges(ps):
        rows, net = [], {v:[Q(0),Q(0)] for v in model['nodes']}
        for e in edge_order:
            u,v = e['source'],e['target']
            drops = (ps[u][0]-ps[v][1],ps[u][1]-ps[v][0])
            k = tuple(Q(e['resistance'][s]) for s in ('lower','upper'))
            # Independently enumerate the four scalar corners. Select extrema
            # with signed-square ordering, rather than producer helper calls.
            corner = [(d/r if d >= 0 else -abs(d)/r,d,r) for d in drops for r in k]
            first, last = min(corner), max(corner)
            sr0, sr1 = roots(abs(first[1])/first[2]), roots(abs(last[1])/last[2])
            flow = (-sr0[1] if first[1]<0 else sr0[0], -sr1[0] if last[1]<0 else sr1[1])
            rows.append({'edge':e['id'],'lower_endpoint_sqrt':interval(*sr0),'upper_endpoint_sqrt':interval(*sr1),'flow':interval(*flow)})
            net[u][0]+=flow[0];net[u][1]+=flow[1]
            net[v][0]-=flow[1];net[v][1]-=flow[0]
        return rows, net

    low = {v:pressures[v] if v in bd else (pressures[v][0],)*2 for v in pressures}
    high = {v:pressures[v] if v in bd else (pressures[v][1],)*2 for v in pressures}
    c['lower_barrier_edges'], low_net = edges(low)
    c['upper_barrier_edges'], high_net = edges(high)
    c['flow_edges'], net = edges(pressures)
    c['pressure_bounds'] = [{'node':v,**interval(*pressures[v])} for v in sorted(pressures)]
    c['barrier_residuals'] = [{'node':v,'lower_barrier':interval(*low_net[v]),'upper_barrier':interval(*high_net[v])} for v in sorted(model['internal_nodes'])]
    c['boundary_net_injections'] = [{'node':v,'net_outgoing_flow':interval(*net[v])} for v in sorted(bd)]
    widths = {v:pressures[v][1]-pressures[v][0] for v in model['internal_nodes']}
    maximum = max(widths.values(),default=Q(0))
    c['widths'] = {'internal_widths':{v:str(x) for v,x in widths.items()},'maximum_internal_width':str(maximum),
        'target_accuracy_met':None if c['pressure_width_target'] is None else maximum<=Q(c['pressure_width_target'])}
    c['certificate_root'] = digest({k:v for k,v in c.items() if k!='certificate_root'})
    return c


def main():
    started = time.perf_counter()
    assert sha(MODULE) == EXPECTED
    out = STAGE / 'evidence/independent-kernel-implementation-review' / uuid.uuid4().hex
    out.mkdir(parents=True)
    (out/'reviewed-passive_pressure.py').write_bytes(MODULE.read_bytes())
    (out/'executed-audit.py').write_bytes(Path(__file__).read_bytes())
    spec = importlib.util.spec_from_file_location('independently_reviewed_passive',out/'reviewed-passive_pressure.py')
    p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)
    records, attacks = [], []
    for seed in range(32):
        m,h,q = manufacture(p,9410+seed,bool(seed%2))
        c = p.compile_passive_pressure(m, pressure_width_target='1/1000000',max_refinement_passes=12)
        assert c['status']=='CERTIFIED_ENCLOSURE',c
        v = p.verify_passive_pressure(m,c,pressure_width_target='1/1000000')
        assert v['status']=='PASS',v
        pb,fb = bounds(v['pressure_bounds'],'node'),bounds(v['flow_bounds'],'edge')
        assert all(pb[n][0]<=x<=pb[n][1] for n,x in h.items())
        assert all(fb[n][0]<=x<=fb[n][1] for n,x in q.items())
        assert v['edge_enclosures_checked']==3*len(m['edges'])
        records.append({'seed':9410+seed,'uncertain':bool(seed%2),'model':m,'exact_heads':{k:str(x) for k,x in h.items()},
            'exact_flows':{k:str(x) for k,x in q.items()},'certificate':c,'verification':v})
        # Reseal every attacked packet, defeating only a shallow root check.
        for key in ('pressure_bounds','lower_barrier_edges','upper_barrier_edges','barrier_residuals','flow_edges','boundary_net_injections'):
            bad=deepcopy(c);bad[key][-1]=deepcopy(bad[key][0]);bad['certificate_root']=digest({k:x for k,x in bad.items() if k!='certificate_root'})
            result=p.verify_passive_pressure(m,bad,pressure_width_target='1/1000000')
            assert result['status']!='PASS',(key,result)
            attacks.append({'case':seed,'attack':'duplicate_'+key,'result':result})
        if seed%2==0:
            # Honest radical/residual fields for a wrong zero-width pressure
            # vector must fail specifically at the universal barrier sign.
            wrong = {n: (Q(m['boundary_heads'][n]['lower']),Q(m['boundary_heads'][n]['upper'])) if n in m['boundary_heads'] else (Q(1),Q(1)) for n in m['nodes']}
            bad = independent_packet(m,c,wrong)
            result=p.verify_passive_pressure(m,bad,pressure_width_target='1/1000000')
            assert result['status']=='FAIL' and 'signs not established' in result['reason'],result
            attacks.append({'case':seed,'attack':'coherent_wrong_barrier','result':result,'certificate':bad})
    m,h,q=manufacture(p,9410,False)
    c=records[0]['certificate']
    def forbidden(*args,**kw): raise AssertionError('Producer called by independent verifier')
    names=('_sqrt','_producer_flow','_producer_edges','_producer_residual','_coordinate_residual','_refine','isqrt')
    saved={name:getattr(p,name) for name in names}
    try:
        for name in names:setattr(p,name,forbidden)
        producer_disabled=p.verify_passive_pressure(m,c,pressure_width_target='1/1000000')
        assert producer_disabled['status']=='PASS',producer_disabled
    finally:
        for name,value in saved.items():setattr(p,name,value)
    for target in ('model','certificate'):
        mm,cc=deepcopy(m),deepcopy(c)
        hit=[]
        def mutate(stage):
            if stage=='passive_verifier_complete':
                hit.append(stage)
                if target=='model':mm['edges'][0]['resistance']['upper']='999'
                else:cc['flow_edges'][0]['flow']['upper']='999'
        result=p.verify_passive_pressure(mm,cc,pressure_width_target='1/1000000',checkpoint=mutate)
        assert hit and result['status']=='FAIL' and 'changed' in result['reason'],result
        attacks.append({'attack':'final_callback_'+target,'result':result})
    unknown=[]
    for options in ({'max_work':1},{'max_nodes':2},{'max_edges':0},{'max_input_bytes':256},{'max_certificate_bytes':256}):
        result=p.verify_passive_pressure(m,c,pressure_width_target='1/1000000',**options)
        assert result['status']=='UNKNOWN' and result['proof_complete'] is False,result
        unknown.append({'options':options,'result':result})
    assert sha(MODULE)==EXPECTED
    summary={'status':'INDEPENDENT_IMPLEMENTATION_AUDIT_PASS_NO_FALSE_BOUND_FOUND','module_sha256':EXPECTED,
        'reviewed_build':'oma-independent-checker/2:6792b9b6eefbe8ceb91392b86582c4a2a4dcf6e7e3d2e994c84f8e2b37896cca',
        'script_sha256':sha(__file__),'manufactured_graphs':len(records),'exact_rational_equilibrium_membership':True,
        'coherent_and_inventory_attacks':len(attacks),'budget_unknown_cases':len(unknown),'producer_disabled_check':producer_disabled,
        'models_and_certificates':records,'attacks':attacks,'budgets':unknown,'seconds':time.perf_counter()-started,
        'scope':'Standalone declared passive signed quadratic model only. Finite manufactured exact equilibria and adversarial packets supplement source-level proof review; no native/BIM/tee-flow applicability, delivery requirement, tight interval hull or whole-backend claim.'}
    (out/'result.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    (out/'README.md').write_text('Reviewed exact source 10fd4677 under the final 6792 module checkpoint. Independent rational Gaussian elimination manufactures equilibrium heads and flows, then derives positive quadratic coefficients. All 32 differently oriented tree/loop networks lie inside the actual public API certificates; 16 models also include nontrivial parameter uncertainty. Rehashed duplicate-denominator packets and honest-radical wrong-barrier packets are rejected. Disabling every producer/refinement/square-root helper leaves certificate verification passing. Final model/certificate callback mutations fail; bounded work/count/byte exhaustion stays UNKNOWN.\n\nNo concrete false enclosure was found. Existence and uniqueness rely on grounded positive-K scalar junctions and the comparison principle reviewed separately. The implementation does not prove native applicability or current upstream-total-flow tee compatibility. It intentionally certifies potentially coarse enclosures even if the requested width is unmet, reporting target_accuracy_met separately.\n',encoding='utf-8')
    print(json.dumps({'directory':str(out),'status':summary['status'],'graphs':len(records),'attacks':len(attacks),'seconds':summary['seconds'],'result_sha256':sha(out/'result.json')}))


if __name__=='__main__':main()
