"""Authored comb-family inputs; no generated NetworkDesign is used to set pressures."""
from fractions import Fraction as Q
import json
from pathlib import Path


def exact_pi():
    def atan_bounds(inverse):
        value=sum((Q((-1)**k,(2*k+1)*inverse**(2*k+1)) for k in range(64)),Q(0))
        return value,value+Q(1,129*inverse**129)
    a,b=atan_bounds(5),atan_bounds(239)
    return 16*a[0]-4*b[1],16*a[1]-4*b[0]


def fixture(count=4,pressure=True,source_pressure=2000):
    if type(count) is not int or not 2<=count<=8:raise ValueError('Two to eight authored sinks')
    target=Q(1,250*count)
    sinks=[{'id':'sink-main','demand_id':'demand-main','end_m':[2*(count-1),0,3]}]
    sinks += [{'id':f'sink-{j}','demand_id':f'demand-{j}','end_m':[1 if j==0 else 2*j,3,3]} for j in range(count-1)]
    r={'mission_type':'shared_network','system_type':'PRESSURE_PIPE','start_m':[-2,0,3],
       'sinks':sinks,'diameter_m':.0625,'insulation_m':.03125,'clearance_m':.0625,
       'minimum_straight_m':.125,'minimum_bend_radius_m':.25,
       'allowed_zone':{'min':[-3,-2,2],'max':[2*count,4,4]},'scenario_terminals':True,
       'target_modality':'ENGINEERING_SERVICE','source_representation_policy':'NATIVE_CAD_WITH_EXACT_PLANAR_ENCLOSURES',
       'objective_weights':{'length_m':1},'assumptions':['Predeclared synthetic equal-bore comb experiment; no building-equipment or measured-boundary claim.']}
    s={'schema':'oma.shared-tree-native-search/1','source_direction':[1,0,0],
       'sink_directions':{'sink-main':[1,0,0],**{f'sink-{j}':[0,1,0] for j in range(count-1)}},
       'tee_instances':[{'id':f'tee-{j}','center_m':[2*j,0,3],'axis_x':[1,0,0],'axis_y':[0,1,0],
           'trunk_takeout_m':'1/4','branch_takeout_m':'1/4'} for j in range(count-1)],
       'stub_lengths_m':['3/4'],'detour_planes':[{'axis':1,'value_m':'9/4'}]}
    coefficients={f'tee-{j}':{'b':str(Q(1,5)+Q(j,20)),'branch':str(Q(3,10)+Q(j,10))} for j in range(count-1)}
    # Each path item is straight length, pi-length coefficient, flow, excess K.
    paths={};trunk=[(Q(7,4),Q(0),count*target,Q(0))]
    for j in range(count-1):
        inlet=(count-j)*target
        paths[f'sink-{j}']=[*trunk,(Q(0),Q(0),inlet,Q(coefficients[f'tee-{j}']['branch'])),
            (Q(11,4),Q(1,4) if j==0 else Q(0),target,Q(2,5) if j==0 else Q(0))]
        trunk.append((Q(0),Q(0),inlet,Q(coefficients[f'tee-{j}']['b'])))
        trunk.append((Q(7,4) if j==count-2 else Q(3,2),Q(0),(count-j-1)*target,Q(0)))
    paths['sink-main']=trunk
    if pressure:
        b=json.loads((Path(__file__).parent/'fixtures/coupled-native-tree/boundary.json').read_text(encoding='utf-8'))
        source_pressure=Q(source_pressure)
        b['source_total_pressure_pa']={'lower':str(source_pressure),'upper':str(source_pressure)}
        b['minimum_sink_flows_m3_s']={x['id']:str(target*Q(4,5)) for x in sinks}
        b['flow_search_box_m3_s']={x['id']:{'lower':str(target*Q(99,100)),'upper':str(target*Q(101,100))} for x in sinks}
        b['tee_outlet_loss_coefficients']=coefficients
        pi=exact_pi();pressures={};diameter=Q(1,16)
        for sink,terms in paths.items():
            losses=[sum(8*1000*flow**2*(Q(1,50)*(straight+arc*angle)/diameter**5+excess/diameter**4)/angle**2
                for straight,arc,flow,excess in terms) for angle in pi]
            lower,upper=source_pressure-losses[0],source_pressure-losses[1]
            assert lower<=upper and lower>0
            pressures[sink]={'lower':str(Q((lower*10**6).__floor__(),10**6)),
                             'upper':str(Q((upper*10**6).__ceil__(),10**6))}
        b['sink_total_pressures_pa']=pressures
        b['boundary_control_assumption']='Hypothetical regulated total-pressure intervals authored by independent exact Machin arithmetic on an explicit comb model before catalogue generation; the analytic target flow is not a prescribed delivered flow.'
        r['coupled_tree']=b
    else:
        r['physics']={'density_kg_m3':1000,'darcy_friction':.02,'maximum_velocity_m_s':2,'gravity_m_s2':9.81,
            'elbow_loss_coefficient':.2,'tee_straight_loss_coefficient':.2,'tee_branch_loss_coefficient':.3,
            'source_kinetic_energy_correction':1,'sink_kinetic_energy_correction':1,
            'applicability':'Hypothetical fixed ideal bore and loss coefficients for synthetic fixture',
            'fixed_flow_control_assumption':'Hypothetical independently regulated terminal flows',
            'friction_convention':'DARCY','elbow_loss_reference':'EXCESS_LOCAL_LOSS_EXCLUDING_CURVED_PIPE_FRICTION',
            'tee_loss_reference':'INLET_VELOCITY_TOTAL_IRREVERSIBLE_LOSS','boundary_loss_scope':'BETWEEN_PHYSICAL_NETWORK_PORTS_ONLY'}
        for sink in sinks:sink.update(required_flow_m3_s=float(target),available_static_pressure_pa=2000)
    context={'state_root':'a'*64,'source_sha256':'b'*64,'checker_version':'private-general-tree-experiment',
             'scope':'AUTHORED_NOMINAL_COMB_INPUT_ONLY_NO_NATIVE_AUTHORITY'}
    authoring={'target_leaf_flow_m3_s':str(target),'source_total_pressure_pa':str(source_pressure),'diameter_m':'1/16',
              'paths':{k:[[str(x) for x in term] for term in v] for k,v in paths.items()},
              'pi_interval':[str(x) for x in exact_pi()],'tee_total_inlet_flow_reference':True,
              'tee_skeleton_darcy_charged':False,'generated_network_used_to_set_boundaries':False}
    return r,s,context,authoring
