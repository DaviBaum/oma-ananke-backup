"""Predeclared hypothetical pressures, independent of generated network objects.

The analytic target uses the fixed A/C sites and three 1 L/s leaf flows solely
to author total-pressure intervals. Delivery is subsequently pressure driven.
These sums are fixture inputs, never a substitute for the native model proof.
"""
from fractions import Fraction as Q
import json
from pathlib import Path

from oma.routing.coupled_tree_pressure import pi_interval
from test_shared_tree_proposals import fixture as fixed_fixture


def fixture():
    r,s,c=fixed_fixture()
    r.pop('physics')
    r['sinks'][0]['end_m']=[4,0,3]
    r['sinks'].append({'id':'sink-c','demand_id':'demand-c','end_m':[2,3,3]})
    for sink in r['sinks']:
        sink.pop('required_flow_m3_s',None);sink.pop('available_static_pressure_pa',None)
    s['sink_directions']['sink-c']=[0,1,0]
    s['tee_instances'][1]['id']='tee-c';s['tee_instances'][1]['center_m']=[2,0,3]
    b=json.loads((Path(__file__).parent/'fixtures/coupled-native-tree/boundary.json').read_text(encoding='utf8'))
    b['tee_outlet_loss_coefficients']={'tee-a':{'b':'1/5','branch':'3/10'},'tee-c':{'b':'1/4','branch':'2/5'}}
    b['minimum_sink_flows_m3_s']={x['id']:'1/1250' for x in r['sinks']}
    b['flow_search_box_m3_s']={x['id']:{'lower':'99/100000','upper':'101/100000'} for x in r['sinks']}
    # Each tuple is (straight length, coefficient of pi in length, flow, excess K).
    # Tee losses use total inlet flow; tee body Darcy loss is already included.
    source=(Q(7,4),Q(0),Q(3,1000),Q(0))
    trunk=(Q(3,2),Q(0),Q(1,500),Q(0))
    tee_a_b=(Q(0),Q(0),Q(3,1000),Q(1,5))
    paths={
        'sink-a':[source,tee_a_b,trunk,(Q(0),Q(0),Q(1,500),Q(1,4)),(Q(7,4),Q(0),Q(1,1000),Q(0))],
        'sink-b':[source,(Q(0),Q(0),Q(3,1000),Q(3,10)),(Q(11,4),Q(1,4),Q(1,1000),Q(2,5))],
        'sink-c':[source,tee_a_b,trunk,(Q(0),Q(0),Q(1,500),Q(2,5)),(Q(11,4),Q(0),Q(1,1000),Q(0))]}
    pi=pi_interval();rho=Q(1000);friction=Q(1,50);diameter=Q(1,8)
    pressures={}
    for sink,terms in paths.items():
        drops=[]
        for angle in (pi.hi,pi.lo):
            loss=sum(8*rho*flow**2*(friction*(straight+arc*angle)/diameter**5+excess/diameter**4)/angle**2
                for straight,arc,flow,excess in terms)
            drops.append(loss)
        lower=Q(200)-drops[1];upper=Q(200)-drops[0]
        scale=10**6
        lo=Q((lower*scale).__floor__(),scale);hi=Q((upper*scale).__ceil__(),scale)
        pressures[sink]={'lower':str(lo),'upper':str(hi)}
    b['sink_total_pressures_pa']=pressures
    b['boundary_control_assumption']='Explicit hypothetical total-pressure intervals manufactured before generation from an analytic nominal 1 L/s-per-sink target on the fixed tee sites; generated alternatives are pressure-driven and must prove their own full operating relation.'
    r['coupled_tree']=b
    r['assumptions']=['Hypothetical fixed-site unequal-tee pressure-generation experiment; analytic target flows do not prescribe deliveries.']
    c={**c,'experiment':'predeclared-fixed-tee-identity-coupled-generation','operating_authority':'NONE_FROM_NOMINAL_GENERATION'}
    return r,s,c
