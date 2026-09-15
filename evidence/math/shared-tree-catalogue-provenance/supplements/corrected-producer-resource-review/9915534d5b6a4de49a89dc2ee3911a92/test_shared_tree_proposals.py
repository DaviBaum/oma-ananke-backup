import copy
from fractions import Fraction as Q
from itertools import product
import pytest

from oma.routing import shared_tree_proposals as p


def fixture():
    requirements={'mission_type':'shared_network','system_type':'PRESSURE_PIPE','start_m':[-2,0,3],
        'sinks':[{'id':'sink-a','demand_id':'demand-a','end_m':[3,0,3],'required_flow_m3_s':.001},
                 {'id':'sink-b','demand_id':'demand-b','end_m':[1,3,3],'required_flow_m3_s':.001}],
        'diameter_m':.125,'insulation_m':.03125,'clearance_m':.0625,'minimum_straight_m':.125,
        'minimum_bend_radius_m':.25,'allowed_zone':{'min':[-3,-2,2],'max':[5,4,4]},'scenario_terminals':True,
        'target_modality':'ENGINEERING_SERVICE','source_representation_policy':'NATIVE_CAD_WITH_EXACT_PLANAR_ENCLOSURES',
        'physics':{'density_kg_m3':1000,'darcy_friction':.02,'maximum_velocity_m_s':2,'gravity_m_s2':9.81,
            'elbow_loss_coefficient':.2,'tee_straight_loss_coefficient':.2,'tee_branch_loss_coefficient':.3,
            'source_kinetic_energy_correction':1,'sink_kinetic_energy_correction':1,
            'applicability':'Hypothetical constant ideal-bore pipe and fixed loss model for analytic fixture',
            'fixed_flow_control_assumption':'Hypothetical independently prescribed positive terminal deliveries',
            'friction_convention':'DARCY','elbow_loss_reference':'EXCESS_LOCAL_LOSS_EXCLUDING_CURVED_PIPE_FRICTION',
            'tee_loss_reference':'INLET_VELOCITY_TOTAL_IRREVERSIBLE_LOSS','boundary_loss_scope':'BETWEEN_PHYSICAL_NETWORK_PORTS_ONLY'},
        'objective_weights':{'length_m':1},'assumptions':['Explicit analytic fixed-flow fixture']}
    search={'schema':p.SCHEMA,'source_direction':[1,0,0],'sink_directions':{'sink-a':[1,0,0],'sink-b':[0,1,0]},
        'tee_instances':[{'id':identity,'center_m':[x,0,3],'axis_x':[1,0,0],'axis_y':[0,1,0],
            'trunk_takeout_m':'1/4','branch_takeout_m':'1/4'} for identity,x in [('tee-a',0),('tee-b',1)]],
        'stub_lengths_m':['3/4'],'detour_planes':[{'axis':1,'value_m':'9/4'}]}
    return requirements,search,{'state_root':'a'*64,'source_sha256':'b'*64,'checker_version':'test-current'}


def test_directed_template_endpoints_and_no_duplicate_words():
    axes=[(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)]
    for u,v in product(axes,repeat=2):
        words=list(p.connector_templates((0,0,0),(3,4,5),u,v,['3/4'],[{'axis':2,'value_m':'7'}]))
        assert len(words)==len({tuple(w) for w in words})
        for word in words:
            assert word[0]==(0,0,0) and word[-1]==(3,4,5)
            assert p._direction(word[0],word[1])==u and p._direction(word[-2],word[-1])==v
            assert all(sum(x!=y for x,y in zip(a,b))==1 for a,b in zip(word,word[1:]))


def test_two_site_catalogue_has_real_direct_and_two_bend_connectors():
    r,s,c=fixture();result=p.build_connector_catalogue(r,s,context=c)
    assert result['status']=='CATALOGUE_PROPOSED',result
    catalogue=result['catalogue'];rows=catalogue['connectors']
    assert len(catalogue['tee_instances'])==2 and len(catalogue['sinks'])==2
    assert any(x['from']=={'node':'tee-b','port':'branch'} and x['to']=={'node':'sink-b','port':'in'} and x['nominal_cost']==['11/4','0'] for x in rows)
    assert any(x['from']=={'node':'tee-a','port':'branch'} and x['to']=={'node':'sink-b','port':'in'} and Q(x['nominal_cost'][1])==Q(1,4) for x in rows)
    assert not result['limitations']['native_geometry_or_service_checked']
    for row in rows:
        macro=result['connector_macros'][row['id']]
        assert macro['independent_check']['status']=='PASS'
        assert p.digest(macro['geometry'])==row['geometry_root']
        components=macro['geometry']['components']
        assert components[0]['geometry']['start_m']==[float(Q(x)) for x in row['start_cap']['position_m']]
        assert components[-1]['geometry']['end_m']==[float(Q(x)) for x in row['end_cap']['position_m']]
        for a,b in zip(components,components[1:]): assert a['geometry']['end_m']==b['geometry']['start_m']


@pytest.mark.parametrize('fault',['duplicate_tee','same_axis','missing_sink','colon_identity','source_identity','unknown_field','old_complete_alternatives','bad_direction'])
def test_malformed_search_has_no_catalogue(fault):
    r,s,c=fixture()
    if fault=='duplicate_tee':s['tee_instances'][1]['id']=s['tee_instances'][0]['id']
    if fault=='same_axis':s['tee_instances'][0]['axis_y']=[1,0,0]
    if fault=='missing_sink':s['sink_directions'].pop('sink-a')
    if fault=='colon_identity':s['tee_instances'][0]['id']='tee:role'
    if fault=='source_identity':s['tee_instances'][0]['id']='source'
    if fault=='unknown_field':s['unknown']=False
    if fault=='old_complete_alternatives':r['network_alternatives']=[]
    if fault=='bad_direction':s['source_direction']=[True,0,0]
    result=p.build_connector_catalogue(r,s,context=c)
    assert result['status']=='INVALID_INPUT' and result['catalogue'] is None,result


@pytest.mark.parametrize('fault',['work','non_dyadic_cap','pressure_identity'])
def test_unsupported_or_exhausted_search_is_unknown(fault):
    r,s,c=fixture();kwargs={}
    if fault=='work':kwargs['max_work']=1
    if fault=='non_dyadic_cap':s['tee_instances'][0]['trunk_takeout_m']='1/3'
    if fault=='pressure_identity':r['coupled_tree']={'unvalidated':'must not be accepted'}
    result=p.build_connector_catalogue(r,s,context=c,**kwargs)
    assert result['status']=='UNKNOWN' and result['catalogue'] is None,result


def test_final_callback_input_change_cannot_return_catalogue():
    r,s,c=fixture();seen=[]
    def checkpoint(stage):
        if stage=='shared_tree_connector_complete':seen.append(stage);r['sinks'][0]['required_flow_m3_s']=.05
    result=p.build_connector_catalogue(r,s,context=c,checkpoint=checkpoint)
    assert seen and result['status']=='INVALID_INPUT' and result['catalogue'] is None


@pytest.mark.parametrize('exception',[ValueError('caller'),RuntimeError('caller')])
def test_caller_exception_identity_is_preserved(exception):
    r,s,c=fixture()
    def checkpoint(stage):raise exception
    with pytest.raises(type(exception)) as caught:p.build_connector_catalogue(r,s,context=c,checkpoint=checkpoint)
    assert caught.value is exception


def test_checked_catalogue_assignments_become_distinct_valid_native_trees():
    r,s,c=fixture();result=p.compile_shared_tree_proposals(r,s,context=c,max_results=8)
    assert result['status']=='PROPOSALS_READY',result
    assert result['independent_check']['status']=='PASS'
    alternatives=result['mission']['network_alternatives']
    assert 2<=len(alternatives)<=8
    assert len({x['network_id'] for x in alternatives})==len(alternatives)
    assert result['synthesis']['proposals'][0]['nominal_cost']==['8','0']
    assert any(x['nominal_cost']==['8','1/4'] for x in result['synthesis']['proposals'])
    for network in alternatives:
        assert len([x for x in network['components'] if x['kind']=='tee'])==1
        assert {x['id'] for x in network['sinks']}=={'sink-a','sink-b'}
        assert len(network['components'])==len({x['id'] for x in network['components']})
        assert len(network['demand_paths'])==2
        p.NetworkDesign.model_validate(network)
    p.SharedNetworkScenario.model_validate(result['mission'])
    assert r==fixture()[0] and 'network_alternatives' not in r


def test_composed_final_boundary_preserves_authored_requirements():
    r,s,c=fixture();seen=[]
    def checkpoint(stage):
        if stage=='shared_tree_proposal_complete':seen.append(stage);r['start_m'][0]=-99
    result=p.compile_shared_tree_proposals(r,s,context=c,checkpoint=checkpoint)
    assert seen and result['status']=='INVALID_INPUT' and result['mission'] is None


def test_composed_caller_exception_identity():
    r,s,c=fixture();expected=ValueError('cancel-composed')
    def checkpoint(stage):
        if stage=='shared_tree_verifier_complete':raise expected
    with pytest.raises(ValueError) as caught:p.compile_shared_tree_proposals(r,s,context=c,checkpoint=checkpoint)
    assert caught.value is expected
