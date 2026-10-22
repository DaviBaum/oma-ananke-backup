"""Fixed-ID coupled provenance; no hydraulic solver is an admission shortcut."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest
from test_shared_tree_catalogue_check import v,digest,fixture as fixed_fixture


def fixture(name='3'):
    folder=Path(__file__).parent/'fixtures/shared-tree-coupled-check'/str(name)
    return tuple(json.loads((folder/(key+'.json')).read_text(encoding='utf-8')) for key in ('requirements','search','context','generated'))


def check(r,s,c,g,**kw):return v.verify_generated_catalogue(r,s,g,context=c,**kw)


@pytest.mark.parametrize('name,tees,macros',[('2',1,8),('3',2,21),('authored-3',2,28)])
def test_current_complete_fixed_id_coupled_provenance(name,tees,macros):
    r,s,c,g=fixture(name);out=check(r,s,c,g)
    assert out['status']=='PASS',out
    assert out['counts']['tees']==tees and out['counts']['connector_macros']==macros
    boundary=g['normalized_requirements']['coupled_tree']
    assert set(boundary['tee_outlet_loss_coefficients'])=={t['id'] for t in s['tee_instances']}
    for tee in g['catalogue']['tee_instances']:
        expected={'model':'oma.coupled-tree-boundary/1','tee_id':tee['id'],
          'outlet_coefficients':boundary['tee_outlet_loss_coefficients'][tee['id']],'boundary_root':digest(boundary)}
        assert tee['loss_contract_root']==digest(expected)
    assert out['input_root']==digest({'requirements':r,'search':s,'context':c})
    assert out['generated_root']==digest(g)
    assert not out['limitations']['native_acceptance_authority']


@pytest.mark.parametrize('attack',['missing_tee_key','extra_tee_key','renamed_tee_key','wrong_number_of_tees','duplicate_search_tee',
 'missing_sink_pressure','extra_sink_pressure','wrong_sink_identity','minimum_missing','box_missing','zero_minimum','degenerate_box','nonpositive_box',
 'zero_b','negative_branch','bad_loss_reference','bad_section_interpretation','bad_pressure_reference','missing_applicability',
 'legacy_fixed_flow','legacy_static_budget','physics_coexistence','wrong_service','wrong_modality','zero_friction','nan_boundary','zero_denominator'])
def test_coupled_profile_premises_fail_closed_before_macro_replay(attack,monkeypatch):
    r,s,c,g=fixture();b=r['coupled_tree']
    if attack=='missing_tee_key':del b['tee_outlet_loss_coefficients']['tee-b']
    elif attack=='extra_tee_key':b['tee_outlet_loss_coefficients']['extra']={'b':'1','branch':'1'}
    elif attack=='renamed_tee_key':b['tee_outlet_loss_coefficients']['renamed']=b['tee_outlet_loss_coefficients'].pop('tee-b')
    elif attack=='wrong_number_of_tees':s['tee_instances']=s['tee_instances'][:1]
    elif attack=='duplicate_search_tee':s['tee_instances'][1]=copy.deepcopy(s['tee_instances'][0])
    elif attack=='missing_sink_pressure':del b['sink_total_pressures_pa']['sink-c']
    elif attack=='extra_sink_pressure':b['sink_total_pressures_pa']['extra']={'lower':'0','upper':'0'}
    elif attack=='wrong_sink_identity':
        for key in ('sink_total_pressures_pa','minimum_sink_flows_m3_s','flow_search_box_m3_s'):b[key]['renamed']=b[key].pop('sink-c')
    elif attack=='minimum_missing':del b['minimum_sink_flows_m3_s']['sink-a']
    elif attack=='box_missing':del b['flow_search_box_m3_s']['sink-a']
    elif attack=='zero_minimum':b['minimum_sink_flows_m3_s']['sink-a']='0'
    elif attack=='degenerate_box':b['flow_search_box_m3_s']['sink-a']['upper']=b['flow_search_box_m3_s']['sink-a']['lower']
    elif attack=='nonpositive_box':b['flow_search_box_m3_s']['sink-a']['lower']='0'
    elif attack=='zero_b':b['tee_outlet_loss_coefficients']['tee-a']['b']='0'
    elif attack=='negative_branch':b['tee_outlet_loss_coefficients']['tee-b']['branch']='-1'
    elif attack=='bad_loss_reference':b['tee_loss_reference']='COMMON_OUTLET_HEAD'
    elif attack=='bad_section_interpretation':b['hydraulic_section_interpretation']='MEASURED_BORE'
    elif attack=='bad_pressure_reference':b['pressure_reference']='STATIC'
    elif attack=='missing_applicability':b['applicability']=''
    elif attack=='legacy_fixed_flow':r['sinks'][0]['required_flow_m3_s']=.001
    elif attack=='legacy_static_budget':r['sinks'][0]['available_static_pressure_pa']=100
    elif attack=='physics_coexistence':r['physics']=fixed_fixture()[0]['physics']
    elif attack=='wrong_service':r['system_type']='AIR_DUCT'
    elif attack=='wrong_modality':r['target_modality']='LOCAL_GEOMETRIC_COORDINATION'
    elif attack=='zero_friction':b['darcy_friction']='0'
    elif attack=='nan_boundary':b['source_total_pressure_pa']['upper']=float('nan')
    elif attack=='zero_denominator':b['tee_outlet_loss_coefficients']['tee-a']['b']='1/0'
    def forbidden(*args,**kwargs):raise AssertionError('Invalid profile must stop before expensive macro replay')
    monkeypatch.setattr(v,'verify_orthogonal_fabrication',forbidden)
    out=check(r,s,c,g)
    assert out['status']=='FAIL' and out['proof_complete'] is False,out


@pytest.mark.parametrize('attack',['old_physics_root','different_tee_id','outlet_swap','other_tee_coefficients','common_outlet_coefficient','wrong_boundary_root','omit_model_discriminator'])
def test_resealed_tee_loss_identity_fails(attack):
    r,s,c,g=fixture();b=g['normalized_requirements']['coupled_tree'];tee=g['catalogue']['tee_instances'][0]
    packet={'model':'oma.coupled-tree-boundary/1','tee_id':tee['id'],
      'outlet_coefficients':copy.deepcopy(b['tee_outlet_loss_coefficients'][tee['id']]),'boundary_root':digest(b)}
    if attack=='old_physics_root':tee['loss_contract_root']=digest(None)
    else:
        if attack=='different_tee_id':packet['tee_id']='tee-b'
        elif attack=='outlet_swap':packet['outlet_coefficients']={key:packet['outlet_coefficients'][other] for key,other in (('b','branch'),('branch','b'))}
        elif attack=='other_tee_coefficients':packet['outlet_coefficients']=copy.deepcopy(b['tee_outlet_loss_coefficients']['tee-b'])
        elif attack=='common_outlet_coefficient':packet['outlet_coefficients']['branch']=packet['outlet_coefficients']['b']
        elif attack=='wrong_boundary_root':packet['boundary_root']='f'*64
        elif attack=='omit_model_discriminator':packet.pop('model')
        tee['loss_contract_root']=digest(packet)
    out=check(r,s,c,g);assert out['status']=='FAIL',out


@pytest.mark.parametrize('field',['source_pressure','sink_pressure','minimum','flow_box','coefficient','loss_assumption','velocity','gravity','density','elbow'])
def test_changed_current_pressure_obligation_cannot_reuse_old_nominal_packet(field):
    r,s,c,g=fixture();b=r['coupled_tree']
    if field=='source_pressure':b['source_total_pressure_pa']={'lower':'201','upper':'201'}
    elif field=='sink_pressure':b['sink_total_pressures_pa']['sink-a']={'lower':'1','upper':'1'}
    elif field=='minimum':b['minimum_sink_flows_m3_s']['sink-a']='1/9000'
    elif field=='flow_box':b['flow_search_box_m3_s']['sink-a']['upper']='3/1000'
    elif field=='coefficient':b['tee_outlet_loss_coefficients']['tee-a']['b']='1/4'
    elif field=='loss_assumption':b['applicability']+=' Changed declared premise.'
    elif field=='velocity':b['maximum_velocity_m_s']='3'
    elif field=='gravity':b['gravity_m_s2']='1'
    elif field=='density':b['density_kg_m3']='999'
    elif field=='elbow':b['elbow_loss_coefficient']='1/4'
    out=check(r,s,c,g);assert out['status']=='FAIL',out


def test_original_fixed_flow_loss_roots_stay_identical():
    r,s,c,g=fixed_fixture();out=check(r,s,c,g)
    assert out['status']=='PASS',out
    for tee in g['catalogue']['tee_instances']:assert tee['loss_contract_root']==digest(g['normalized_requirements']['physics'])
    assert out['input_root']==g['input_root'] and out['catalogue_root']==digest(g['catalogue'])


def test_legacy_complete_result_byte_identity_against_frozen688():
    path=Path(__file__).parent/'fixtures/shared-tree-coupled-check/base688.py'
    assert __import__('hashlib').sha256(path.read_bytes()).hexdigest()=='688cb03a0c75f23ee07e3e4b668980ec7d94267337b6c0f9b7ac4e5309045f7b'
    spec=importlib.util.spec_from_file_location('frozen_base688',path)
    base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
    r,s,c,g=fixed_fixture()
    assert check(r,s,c,g)==base.verify_generated_catalogue(r,s,g,context=c)


@pytest.mark.parametrize('mode,mixed',[('passive_tree',False),('passive_tree',True),('pressure_driven',False),('pressure_driven',True)])
def test_other_pressure_profiles_remain_explicitly_unknown(mode,mixed,monkeypatch):
    r,s,c,g=fixture('2');b=copy.deepcopy(r['coupled_tree'])
    if not mixed:r['coupled_tree']=None
    for key in ('flow_search_box_m3_s','minimum_sink_flows_m3_s','tee_outlet_loss_coefficients'):b.pop(key)
    if mode=='passive_tree':
        b['schema']='oma.passive-tree-boundary/1';b['source_total_pressure_pa']='200'
        b['sink_total_pressures_pa']={k:'0' for k in ('sink-a','sink-b')}
        b['minimum_sink_flows_m3_s']={k:'1/10000' for k in ('sink-a','sink-b')}
        b['tee_common_loss_coefficients']={'tee-a':'1/5'}
        b['tee_loss_reference']='IDENTICAL_OUTLET_TOTAL_LOSS_AT_INLET_FLOW_COMMON_HEAD'
    else:
        b['schema']='oma.two-sink-pressure-boundary/1';b['source_total_pressure_pa']=200.
        b['sink_total_pressures_pa']={k:0. for k in ('sink-a','sink-b')}
        b['tee_straight_loss_coefficient']=.2;b['tee_branch_loss_coefficient']=.3
        b['tee_loss_reference']='INLET_VELOCITY_TOTAL_IRREVERSIBLE_LOSS';b.pop('connection_model')
        from fractions import Fraction
        for key in ('density_kg_m3','darcy_friction','maximum_velocity_m_s','gravity_m_s2','elbow_loss_coefficient'):b[key]=float(Fraction(b[key]))
    r[mode]=b
    monkeypatch.setattr(v,'verify_orthogonal_fabrication',lambda *a,**k:pytest.fail('Unsupported profile must not reach macro replay'))
    out=check(r,s,c,g)
    assert out['status']=='UNKNOWN' and out['reason']=='GENERATED_PRESSURE_TEE_IDENTITY_PROFILE_NOT_IMPLEMENTED',out


def test_checked_generated_design_preserves_exact_coupled_requirement_projection():
    r,s,c,g=fixture('authored-3');assert check(r,s,c,g)['status']=='PASS'
    from oma.optimization.shared_tree_synthesis import compile_shared_tree_catalogue,verify_shared_tree_catalogue
    from oma.routing.shared_tree_proposals import _network_from_assignment
    from oma.routing.network_scenario import SharedNetworkScenario,network_fixed_requirements
    produced=compile_shared_tree_catalogue(g['catalogue'],max_results=2)
    assert produced['status']=='CERTIFIED',produced
    checked=verify_shared_tree_catalogue(g['catalogue'],produced['certificate'],max_results=2)
    assert checked['status']=='PASS' and checked['proposals'],checked
    normalized=g['normalized_requirements'];before=digest([r,s,c,g])
    alternatives=[_network_from_assignment(normalized,g,proposal) for proposal in checked['proposals']]
    scenario=SharedNetworkScenario.model_validate({**normalized,'network_alternatives':alternatives})
    fixed=network_fixed_requirements(scenario,'resolved-source')
    assert fixed['coupled_tree']==normalized['coupled_tree']
    assert fixed['sinks']==normalized['sinks'] and fixed['source_id']=='resolved-source'
    assert fixed['physics'] is None and 'pressure_driven' not in fixed and 'passive_tree' not in fixed
    assert all({component['id'] for component in n['components'] if component['kind']=='tee'}==set(fixed['coupled_tree']['tee_outlet_loss_coefficients']) for n in alternatives)
    assert digest([r,s,c,g])==before


@pytest.mark.parametrize('name',['2','3','authored-3'])
def test_verifier_never_calls_nominal_producer_or_pressure_solver(name,monkeypatch):
    r,s,c,g=fixture(name)
    from oma.routing import shared_tree_proposals as producer,coupled_tree_pressure as hydraulic
    from oma.optimization import fabrication,coupled_tree_pressure as local,coupled_tree_univalence as global_proof
    def forbidden(*args,**kw):raise AssertionError('A producer or pressure solver was used as catalogue authority')
    for module,names in ((producer,('build_connector_catalogue','connector_templates','_physical_components','_cost')),
      (fabrication,('compile_orthogonal_fabrication',)),(hydraulic,('evaluate_coupled_tree','verify_coupled_tree_envelope')),
      (local,('compile_coupled_tree_pressure',)),(global_proof,('compile_coupled_tree_univalence',))):
        for key in names:monkeypatch.setattr(module,key,forbidden)
    out=check(r,s,c,g);assert out['status']=='PASS',out
    assert out['limitations']['native_acceptance_authority'] is False


@pytest.mark.parametrize('target',['source_pressure','tee_coefficient','search_site','generated_loss_root','context'])
def test_last_callback_mutations_do_not_publish_bound_success(target):
    r,s,c,g=fixture();fired=[]
    def callback(stage):
        if fired:raise AssertionError('Callback after the final mutation guard began')
        if stage=='shared_tree_catalogue_check_complete':
            fired.append(stage)
            if target=='source_pressure':r['coupled_tree']['source_total_pressure_pa']['upper']='1000'
            elif target=='tee_coefficient':r['coupled_tree']['tee_outlet_loss_coefficients']['tee-a']['b']='1000'
            elif target=='search_site':s['tee_instances'][0]['center_m'][0]=99
            elif target=='generated_loss_root':g['catalogue']['tee_instances'][0]['loss_contract_root']='f'*64
            elif target=='context':c['new_identity']='f'*64
    out=check(r,s,c,g,checkpoint=callback)
    assert fired and out['status']=='FAIL' and out['proof_complete'] is False,out


@pytest.mark.parametrize('budget',[{'max_work':1},{'max_bytes':1024},{'max_macros':1},{'max_attempts':1}])
def test_coupled_resource_unknown_has_no_partial_authority(budget):
    r,s,c,g=fixture();out=check(r,s,c,g,**budget)
    assert out['status']=='UNKNOWN' and out['proof_complete'] is False,out


def test_exact_complete_work_includes_boundary_and_final_tail():
    r,s,c,g=fixture();out=check(r,s,c,g);assert out['status']=='PASS',out
    assert check(r,s,c,g,max_work=out['work'])==out
    limited=check(r,s,c,g,max_work=out['work']-1)
    assert limited['status']=='UNKNOWN' and limited['proof_complete'] is False


@pytest.mark.parametrize('error',[TimeoutError('timeout'),ValueError('cancel-shaped'),v._Limit('caller-limit')])
def test_coupled_callback_exception_identity(error):
    r,s,c,g=fixture();before=digest([r,s,c,g])
    def callback(stage):raise error
    with pytest.raises(type(error)) as caught:check(r,s,c,g,checkpoint=callback)
    assert caught.value is error and digest([r,s,c,g])==before
