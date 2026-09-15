import copy
import pytest

from oma.routing import shared_tree_proposals as p
from oma.routing.shared_tree_requirements import normalize_shared_tree_requirements
from shared_tree_coupled_fixture import fixture


def test_generated_pressure_mission_preserves_every_fixed_requirement_and_tee_role():
    r,s,c=fixture();result=p.compile_shared_tree_proposals(r,s,context=c,max_results=2)
    assert result['status']=='PROPOSALS_READY',result
    mission=copy.deepcopy(result['mission']);networks=mission.pop('network_alternatives')
    assert len(networks)==2
    assert normalize_shared_tree_requirements(mission)==normalize_shared_tree_requirements(r)
    assert result['catalogue_check']['status']=='PASS'
    assert result['independent_check']['status']=='PASS'
    for network in networks:
        assert {x['id'] for x in network['components'] if x['kind']=='tee'}=={'tee-a','tee-c'}
        assert {x['demand_id'] for x in network['demand_paths']}=={'demand-a','demand-b','demand-c'}
    assert result['limitations']['native_geometry_or_service_checked'] is False


def test_coupled_catalogue_binds_each_fixed_tee_identity_and_full_boundary():
    r,s,c=fixture();before=p.digest({'requirements':r,'search':s,'context':c})
    result=p.build_connector_catalogue(r,s,context=c)
    assert result['status']=='CATALOGUE_PROPOSED',result
    assert result['input_root']==before
    normalized=normalize_shared_tree_requirements(r);boundary=normalized['coupled_tree']
    assert result['normalized_requirements']==normalized
    assert {x['id'] for x in result['catalogue']['tee_instances']}==set(boundary['tee_outlet_loss_coefficients'])
    for tee in result['catalogue']['tee_instances']:
        assert tee['loss_contract_root']==p.digest({'model':'oma.coupled-tree-boundary/1','tee_id':tee['id'],
            'outlet_coefficients':boundary['tee_outlet_loss_coefficients'][tee['id']],
            'boundary_root':p.digest(boundary)})
    assert p.digest({'requirements':r,'search':s,'context':c})==before


@pytest.mark.parametrize('fault',[
    'extra_site','missing_site','missing_coefficient','extra_coefficient','duplicate_site',
    'static_budget','fixed_flow','physics','local_scope','duct','missing_sink','bad_boundary','requirements_list','search_list'])
def test_incomplete_or_ambiguous_coupled_generation_has_no_catalogue(fault):
    r,s,c=fixture()
    if fault=='extra_site':
        extra=copy.deepcopy(s['tee_instances'][0]);extra['id']='extra';s['tee_instances'].append(extra)
    if fault=='missing_site':s['tee_instances'].pop()
    if fault=='missing_coefficient':r['coupled_tree']['tee_outlet_loss_coefficients'].pop('tee-c')
    if fault=='extra_coefficient':r['coupled_tree']['tee_outlet_loss_coefficients']['extra']={'b':'1/5','branch':'3/10'}
    if fault=='duplicate_site':s['tee_instances'][1]['id']=s['tee_instances'][0]['id']
    if fault=='static_budget':r['sinks'][0]['available_static_pressure_pa']=100
    if fault=='fixed_flow':r['sinks'][0]['required_flow_m3_s']=.001
    if fault=='physics':
        from test_shared_tree_proposals import fixture as fixed
        r['physics']=fixed()[0]['physics']
    if fault=='local_scope':r['target_modality']='LOCAL_GEOMETRIC_COORDINATION'
    if fault=='duct':r['system_type']='ROUND_DUCT'
    if fault=='missing_sink':r['coupled_tree']['minimum_sink_flows_m3_s'].pop('sink-a')
    if fault=='bad_boundary':r['coupled_tree']={'schema':'unknown'}
    if fault=='requirements_list':r=[]
    if fault=='search_list':s=[]
    result=p.build_connector_catalogue(r,s,context=c)
    assert result['status']=='INVALID_INPUT' and result['catalogue'] is None,result


@pytest.mark.parametrize('field',['source_total_pressure_pa','minimum_sink_flows_m3_s',
    'flow_search_box_m3_s','tee_outlet_loss_coefficients'])
def test_each_exact_boundary_change_invalidates_all_tee_loss_bindings(field):
    r,s,c=fixture();before=p.build_connector_catalogue(r,s,context=c)
    changed=copy.deepcopy(r)
    if field=='source_total_pressure_pa':changed['coupled_tree'][field]={'lower':'201','upper':'201'}
    if field=='minimum_sink_flows_m3_s':changed['coupled_tree'][field]['sink-a']='1/1500'
    if field=='flow_search_box_m3_s':changed['coupled_tree'][field]['sink-a']['lower']='97/100000'
    if field=='tee_outlet_loss_coefficients':changed['coupled_tree'][field]['tee-a']['b']='1/4'
    after=p.build_connector_catalogue(changed,s,context=c)
    assert before['status']==after['status']=='CATALOGUE_PROPOSED'
    assert before['input_root']!=after['input_root']
    left={x['id']:x['loss_contract_root'] for x in before['catalogue']['tee_instances']}
    right={x['id']:x['loss_contract_root'] for x in after['catalogue']['tee_instances']}
    assert all(left[k]!=right[k] for k in left)
