"""Evidence-only rational barriers and independent tiny-network references.

This is not a production network solver/certificate API. Exact sign checks are
separate from finite Decimal consistency samples; samples prove no universality.
"""
from decimal import Decimal, localcontext
from fractions import Fraction as Q
from itertools import product
from math import isqrt
from pathlib import Path
import hashlib
import json
import random

STAGE = Path(__file__).resolve().parents[1]


def sqrt_bounds(value, bits=100):
    assert value >= 0
    scale = 1 << bits
    n = isqrt(value.numerator * scale * scale // value.denominator)
    low = Q(n, scale)
    high = low if low * low == value else Q(n+1, scale)
    assert low >= 0 and low * low <= value <= high * high
    return low, high


def signed_flow(drop, resistance):
    a, b = sqrt_bounds(abs(drop) / resistance)
    return (-b, -a) if drop < 0 else (a, b)


def edge_interval(drop, resistance):
    lo, hi = drop
    rlo, rhi = resistance
    assert 0 < rlo <= rhi and lo <= hi
    a = signed_flow(lo, rlo if lo < 0 else rhi)[0]
    b = signed_flow(hi, rhi if hi < 0 else rlo)[1]
    return a, b


def flux_intervals(edges, pressures):
    return {name: edge_interval((pressures[u][0]-pressures[v][1], pressures[u][1]-pressures[v][0]), r)
            for name, u, v, r in edges}


def divergence(edges, flows, vertex):
    low = high = Q(0)
    for name, u, v, _ in edges:
        a, b = flows[name]
        if u == vertex:
            low, high = low+a, high+b
        elif v == vertex:
            low, high = low-b, high-a
    return low, high


def barriers(model, lower, upper):
    edges, boundary = model['edges'], model['boundary']
    assert set(lower) == set(upper) == set(model['internal'])
    assert all(lower[v] <= upper[v] for v in lower)
    low_flows = flux_intervals(edges, {**boundary, **{v: (p, p) for v, p in lower.items()}})
    high_flows = flux_intervals(edges, {**boundary, **{v: (p, p) for v, p in upper.items()}})
    lower_residual = {v: divergence(edges, low_flows, v) for v in lower}
    upper_residual = {v: divergence(edges, high_flows, v) for v in upper}
    assert all(x[1] <= 0 for x in lower_residual.values())
    assert all(x[0] >= 0 for x in upper_residual.values())
    pressure = {**boundary, **{v: (lower[v], upper[v]) for v in lower}}
    flow = flux_intervals(edges, pressure)
    # A simple grounded path for each interior vertex is supplied, not inferred
    # from a numerical Jacobian. Each selected example has an edge to S.
    global_lo = min(x[0] for x in boundary.values())
    global_hi = max(x[1] for x in boundary.values())
    width = global_hi-global_lo
    gamma = Q(1, 8)
    assert all(4*gamma*gamma*r[1]*width <= 1 for _, _, _, r in edges)
    paths = {v: next(name for name, a, b, _ in edges if {a,b} == {v,'S'}) for v in lower}
    alpha = gamma / len(lower)
    centers = {v: (lower[v]+upper[v])/2 for v in lower}
    assert all(global_lo <= x <= global_hi for x in centers.values())
    residual_flow = flux_intervals(edges, {**boundary, **{v:(x,x) for v,x in centers.items()}})
    residual = {v: divergence(edges, residual_flow, v) for v in lower}
    residual_squared = sum(max(abs(a),abs(b))**2 for a,b in residual.values())
    error = sqrt_bounds(residual_squared / alpha**2)[1]
    assert error*error*alpha*alpha >= residual_squared
    return {'lower':lower, 'upper':upper, 'lower_residual_intervals':lower_residual,
        'upper_residual_intervals':upper_residual, 'pressure_intervals':pressure, 'flow_intervals':flow,
        'residual_error':{'center':centers,'edge_slope_lower':gamma,'grounded_paths':paths,
            'coercivity_lower':alpha,'uniform_residual':residual,'pressure_l2_error_upper':error},
        'scope':'Rational proposed-certificate inequalities for this explicit model; no native interface authority'}


def dec(x):
    x = Q(x)
    return Decimal(x.numerator)/Decimal(x.denominator)


def phi(drop, r):
    value = (abs(drop)/r).sqrt()
    return -value if drop < 0 else value


def samples(model):
    labels = [('r',e[0]) for e in model['edges']] + [('b',v) for v in model['boundary']]
    intervals = [e[3] for e in model['edges']] + list(model['boundary'].values())
    for bits in product((0,1), repeat=len(labels)):
        yield dict(zip(labels, [x[b] for x,b in zip(intervals,bits)])), 'corner'
    rng = random.Random(271828)
    for _ in range(16):
        yield dict(zip(labels, [a+(b-a)*Q(rng.randrange(1001),1000) for a,b in intervals])), 'interior'


def check_reference(model, envelope, kind):
    records = []
    for values, location in samples(model):
        rs = {e[0]:dec(values['r',e[0]]) for e in model['edges']}
        ps = {v:dec(values['b',v]) for v in model['boundary']}
        if kind == 'three_sink_tree':
            # Independent scalar continuity equation, not barrier construction.
            lo, hi = min(ps.values()), max(ps.values())
            for _ in range(280):
                h = (lo+hi)/2
                residual = phi(h-ps['S'],rs['SJ']) + sum(phi(h-ps[v],rs['J'+v]) for v in ('T1','T2','T3'))
                if residual <= 0:
                    lo = h
                else:
                    hi = h
            ps['J'] = (lo+hi)/2
        elif kind == 'triangle_loop':
            # Exact series-path elimination plus an independent direct branch.
            ps['A'] = (rs['AT']*ps['S']+rs['SA']*ps['T'])/(rs['SA']+rs['AT'])
        else:
            raise AssertionError(kind)
        qs = {name:phi(ps[u]-ps[v],rs[name]) for name,u,v,_ in model['edges']}
        tolerance = Decimal('1e-65')
        for v, p in ps.items():
            a,b = envelope['pressure_intervals'][v]
            assert dec(a)-tolerance <= p <= dec(b)+tolerance
        for name, q in qs.items():
            a,b = envelope['flow_intervals'][name]
            assert dec(a)-tolerance <= q <= dec(b)+tolerance
        for v in model['internal']:
            residual = sum((qs[name] if u==v else -qs[name] if w==v else Decimal(0))
                for name,u,w,_ in model['edges'])
            assert abs(residual) < tolerance
        er = envelope['residual_error']
        error_sq = sum((ps[v]-dec(er['center'][v]))**2 for v in model['internal'])
        assert error_sq <= dec(er['pressure_l2_error_upper'])**2+tolerance
        records.append({'kind':location,'parameters':values,'pressure':ps,'flow':qs})
    return {'cases':len(records),'records':records,
        'scope':'80-digit finite numerical consistency only; not the universal theorem or native geometry evidence'}


def encode(value):
    if isinstance(value, (Q,Decimal)):
        return str(value)
    if isinstance(value, dict):
        return {str(k):encode(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)):
        return [encode(v) for v in value]
    return value


def main():
    out = STAGE/'evidence'
    out.mkdir(parents=True,exist_ok=True)
    unit = (Q(99,100),Q(101,100))
    tree = {'internal':['J'], 'boundary':{'S':(Q(99,10),Q(101,10)),
        **{v:(Q(-1,100),Q(1,100)) for v in ('T1','T2','T3')}},
        'edges':[('SJ','S','J',unit), *[('J'+v,'J',v,unit) for v in ('T1','T2','T3')]]}
    triangle = {'internal':['A'],'boundary':{'S':(Q(99,25),Q(101,25)),'T':(Q(-1,100),Q(1,100))},
        'edges':[('SA','S','A',(Q(297,100),Q(303,100))),('AT','A','T',unit),('ST','S','T',unit)]}
    diamond = {'internal':['A','B'],'boundary':{'S':(Q(799,100),Q(801,100)),'T':(Q(-1,100),Q(1,100))},
        'edges':[(name,u,v,unit) for name,u,v in [('SA','S','A'),('AT','A','T'),('SB','S','B'),('BT','B','T'),('AB','A','B')]]}
    results = {}
    with localcontext() as context:
        context.prec = 80
        for name,model in [('three_sink_tree',tree),('triangle_loop',triangle),('zero_flow_bridged_diamond',diamond)]:
            lower = {v:Q(39,10) if model is diamond else Q(19,20) for v in model['internal']}
            upper = {v:Q(41,10) if model is diamond else Q(21,20) for v in model['internal']}
            proof = barriers(model,lower,upper)
            item = {'model':model,'rational_barrier_and_error_checks':proof}
            if model is not diamond:
                item['independent_reference'] = check_reference(model,proof,name)
            else:
                exact_pressure = {'S':Q(8),'T':Q(0),'A':Q(4),'B':Q(4)}
                exact_flow = {'SA':Q(2),'AT':Q(2),'SB':Q(2),'BT':Q(2),'AB':Q(0)}
                for edge,u,v,_ in model['edges']:
                    q = exact_flow[edge]
                    assert exact_pressure[u]-exact_pressure[v] == q*abs(q)
                assert divergence(model['edges'],{k:(v,v) for k,v in exact_flow.items()},'A') == (0,0)
                assert divergence(model['edges'],{k:(v,v) for k,v in exact_flow.items()},'B') == (0,0)
                item['exact_manufactured_solution'] = {'pressure':exact_pressure,'flow':exact_flow,'zero_flow_edge':'AB'}
            results[name] = item
    evidence = {'status':'REFERENCE_INEQUALITY_CHECKS_PASS','production_solver_implemented':False,
        'source_basis_sha256':hashlib.sha256((out/'source-basis.json').read_bytes()).hexdigest(),
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'total_finite_reference_cases':sum(x.get('independent_reference',{}).get('cases',0) for x in results.values()),
        'cases':results,'native_or_mission_authority':False,'universal_claim_basis':'Proposed exact comparison/stability theorem, not finite sampling'}
    target=out/'reference-results.json'
    target.write_text(json.dumps(encode(evidence),indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':evidence['status'],'finite_reference_cases':evidence['total_finite_reference_cases'],
        'result_sha256':hashlib.sha256(target.read_bytes()).hexdigest()}))


if __name__=='__main__':
    main()
