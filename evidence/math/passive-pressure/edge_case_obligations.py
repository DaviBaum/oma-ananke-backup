"""Exact tiny counterexamples/limitations for the design, not a network solver."""
from fractions import Fraction as Q
from pathlib import Path
import hashlib
import json

from reference_examples import divergence, edge_interval, encode, flux_intervals

STAGE = Path(__file__).resolve().parents[1]


def main():
    negative = edge_interval((Q(-4), Q(-1)), (Q(1), Q(4)))
    assert negative == (Q(-2), Q(-1,2))
    # A sharp exact barrier has equal irrational terms. Naive separate interval
    # sums cannot establish the true equality; outward slack is necessary.
    edges = [('SJ','S','J',(Q(1),Q(4))), ('JT','J','T',(Q(1),Q(4)))]
    lower = flux_intervals(edges, {'S':(Q(1),Q(1)), 'T':(Q(0),Q(0)), 'J':(Q(1,5),Q(1,5))})
    lower_residual = divergence(edges,lower,'J')
    assert lower_residual[1] > 0
    relaxed = flux_intervals(edges, {'S':(Q(1),Q(1)), 'T':(Q(0),Q(0)),
        'J':(Q(1,5)-Q(1,10**6),Q(1,5)-Q(1,10**6))})
    relaxed_residual = divergence(edges,relaxed,'J')
    assert relaxed_residual[1] < 0
    zero = flux_intervals(edges, {'S':(Q(3),Q(3)), 'T':(Q(3),Q(3)), 'J':(Q(3),Q(3))})
    assert all(x == (0,0) for x in zero.values())
    eps = Q(1,1000)
    assert eps > eps*eps
    # Equal boundary pressures with no internal vertices still yield a complete
    # known flow relation; no nonempty grounding-path sum is needed.
    boundary_only = edge_interval((Q(4),Q(4)),(Q(1),Q(1)))
    assert boundary_only == (2,2)
    # At a bidirectional boundary, uniqueness is not a forward-delivery proof.
    uncertain_direction = edge_interval((-eps*eps,eps*eps),(Q(1),Q(1)))
    assert uncertain_direction[0] <= -eps < 0 < eps <= uncertain_direction[1]
    binary_edges = [('SJ1','S','J1',(Q(1),Q(1))), ('J1T1','J1','T1',(Q(1),Q(1))),
        ('J1J2','J1','J2',(Q(1),Q(1))), ('J2T2','J2','T2',(Q(1),Q(1))),
        ('J2T3','J2','T3',(Q(1),Q(1)))]
    binary_pressure = {'S':14,'J1':5,'J2':1,'T1':4,'T2':0,'T3':0}
    binary_flow = {'SJ1':3,'J1T1':1,'J1J2':2,'J2T2':1,'J2T3':1}
    for name,u,v,_ in binary_edges:
        assert binary_pressure[u]-binary_pressure[v] == binary_flow[name]*abs(binary_flow[name])
    for v in ('J1','J2'):
        assert divergence(binary_edges,{k:(Q(q),Q(q)) for k,q in binary_flow.items()},v) == (0,0)
    result = {'status':'EXACT_DESIGN_EDGE_CASES_CHECKED','production_implementation':False,
        'cases':{
            'negative_resistance_endpoint_selection':{'drop':[-4,-1],'K':[1,4],'exact_flow':negative},
            'sharp_barrier_interval_cancellation':{'true_uniform_pressure_bounds':['1/5','4/5'],
                'true_lower_worst_residual':'0 = -sqrt(1/5)+sqrt(1/5)',
                'naive_outward_residual':lower_residual,'naive_certificate_disposition':'UNRESOLVED_SIGN',
                'relaxed_lower':'1/5-1/1000000','relaxed_residual':relaxed_residual,
                'point':'Never replace a positive outward endpoint by an epsilon zero; use exact cancellation or outward slack'},
            'equal_pressure_zero_flow':{'pressure':'3','flows':zero,'requires_minimum_flow':False},
            'boundary_only':{'delta_h':4,'K':1,'flow':boundary_only,'internal_count':0},
            'zero_flow_lipschitz_counterexample':{'K':1,'pressure_residual':eps*eps,'flow_error':eps,
                'claimed_flow_error_le_pressure_residual':False},
            'direction_not_certified':{'pressure_drop':[-eps*eps,eps*eps],'flow':uncertain_direction,
                'unique_per_parameter_tuple':True,'strict_positive_delivery_proved':False},
            'two_junction_three_sink_tree':{'edges':binary_edges,'pressure':binary_pressure,'flow':binary_flow,
                'all_edge_losses_and_internal_continuity_exact':True,'native_junction_loss_applicability':False},
            'ungrounded_component':{'pressures_1':[0,0],'pressures_2':[5,5],'same_edge_flow':0,
                'disposition':'INVALID_MODEL_NO_DIRICHLET_GROUND'},
            'zero_resistance_cycle':{'K':[0,0,0],'pressure':[0,0,0],
                'distinct_continuity_flows':[[0,0,0],[1,1,1]],'disposition':'INVALID_MODEL_NONPOSITIVE_RESISTANCE'}}}
    result['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    out=STAGE/'evidence/edge-case-obligations.json'
    out.write_text(json.dumps(encode(result),indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':result['status'],'cases':len(result['cases']),
        'result_sha256':hashlib.sha256(out.read_bytes()).hexdigest()}))


if __name__=='__main__':
    main()
