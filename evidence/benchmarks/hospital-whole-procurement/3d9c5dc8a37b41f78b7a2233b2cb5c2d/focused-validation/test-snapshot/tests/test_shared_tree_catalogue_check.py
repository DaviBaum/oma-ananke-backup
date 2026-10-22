"""Independent replay, semantic forgeries and resource/control boundaries."""
import copy
from fractions import Fraction as Q
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest

_private_base=Path(__file__).parents[1]/'dependencies/base.json'
if _private_base.exists():
    _private_root=json.loads(_private_base.read_text(encoding='utf-8'))['root']
    sys.path.insert(0,str(_private_base.parent/_private_root/'src'))

if os.environ.get('OMA_CATALOGUE_CHECK_SOURCE'):
    spec=importlib.util.spec_from_file_location('catalogue_checker_under_test',os.environ['OMA_CATALOGUE_CHECK_SOURCE'])
    v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
else:
    try:from oma.routing import shared_tree_catalogue_check as v
    except ImportError:
        stage=Path(__file__).parents[1]
        root=json.loads((stage/'dependencies/base.json').read_text(encoding='utf-8'))['root']
        sys.path.insert(0,str(stage/'dependencies'/root/'src'))
        spec=importlib.util.spec_from_file_location('catalogue_checker_under_test',stage/'src/oma/routing/shared_tree_catalogue_check.py')
        v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def fixture():
    d=Path(__file__).parent/'fixtures/shared-tree-catalogue-check'
    return tuple(json.loads((d/(name+'.json')).read_text(encoding='utf-8')) for name in ('requirements','search','context','generated'))


def verify(r,s,c,g,**kw):return v.verify_generated_catalogue(r,s,g,context=c,**kw)


def chosen(g,elbow=False):
    for row in g['catalogue']['connectors']:
        macro=g['connector_macros'][row['id']]
        if not elbow or any(x['kind']=='elbow' for x in macro['geometry']['components']):return row,macro
    raise AssertionError('Fixture lacks elbow')


def rebind_geometry(row,macro):row['geometry_root']=digest(macro['geometry'])


def reseal_fabrication(row,macro):
    cert=macro['certificate'];cert['certificate_root']=digest({k:x for k,x in cert.items() if k!='certificate_root'})
    row['fabrication_root']=cert['certificate_root'];macro['independent_check']['certificate_root']=cert['certificate_root']


def test_complete_fresh_independent_provenance():
    r,s,c,g=fixture();out=verify(r,s,c,g)
    assert out['status']=='PASS',out
    assert out['input_root']==digest({'requirements':r,'search':s,'context':c})
    assert out['generated_root']==digest(g) and out['catalogue_root']==digest(g['catalogue'])
    assert out['counts']=={'tees':2,'terminals':3,'connector_macros':20,'physical_components_in_catalogue':106,'admitted_attempts':20,'untrusted_diagnostic_attempts':10}
    assert not out['limitations']['native_acceptance_authority']


@pytest.mark.parametrize('attack',['macro_missing','macro_extra','row_missing','row_duplicate','admission_missing','admission_duplicate',
    'admission_points','tee_missing','tee_extra','tee_position','tee_diameter','tee_insulation','tee_takeout','tee_ports','tee_root',
    'tee_loss_root','normalization','context','cost_policy','source_roots','terminal_position','terminal_direction','demand_id',
    'header_section','macro_section','macro_start','macro_end_direction','nominal_cost','geometry_root','fabrication_root',
    'stored_check','scope','work_bool','unknown_field'])
def test_complete_inventory_and_binding_attacks(attack):
    r,s,c,g=fixture();row,macro=chosen(g)
    if attack=='macro_missing':del g['connector_macros'][row['id']]
    elif attack=='macro_extra':g['connector_macros']['extra']=copy.deepcopy(macro)
    elif attack=='row_missing':g['catalogue']['connectors'].remove(row)
    elif attack=='row_duplicate':g['catalogue']['connectors'].append(copy.deepcopy(row))
    elif attack=='admission_missing':g['attempts']=[a for a in g['attempts'] if a.get('connector_id')!=row['id']]
    elif attack=='admission_duplicate':g['attempts'].append(copy.deepcopy(next(a for a in g['attempts'] if a.get('connector_id')==row['id'])))
    elif attack=='admission_points':next(a for a in g['attempts'] if a.get('connector_id')==row['id'])['points_m'][0][0]='0'
    elif attack=='tee_missing':del g['tee_components']['tee-a']
    elif attack=='tee_extra':g['tee_components']['extra']=copy.deepcopy(g['tee_components']['tee-a'])
    elif attack=='tee_position':g['tee_components']['tee-a']['geometry']['frame_m'][0][3]=.25
    elif attack=='tee_diameter':g['tee_components']['tee-a']['diameter_m']=.25
    elif attack=='tee_insulation':g['tee_components']['tee-a']['insulation_m']=0
    elif attack=='tee_takeout':g['tee_components']['tee-a']['geometry']['trunk_takeout_m']=.5
    elif attack=='tee_ports':g['tee_components']['tee-a']['ports']['branch']='SINK'
    elif attack=='tee_root':g['catalogue']['tee_instances'][0]['catalogue_root']='f'*64
    elif attack=='tee_loss_root':g['catalogue']['tee_instances'][0]['loss_contract_root']='f'*64
    elif attack=='normalization':g['normalized_requirements']['diameter_m']=.25
    elif attack=='context':c['checker_version']='new-version'
    elif attack=='cost_policy':g['catalogue']['cost_policy_root']='f'*64
    elif attack=='source_roots':g['catalogue']['source_roots']['search']='f'*64
    elif attack=='terminal_position':g['catalogue']['sinks'][0]['cap']['position_m'][0]='0'
    elif attack=='terminal_direction':g['catalogue']['sinks'][0]['cap']['flow_direction']=[-1,0,0]
    elif attack=='demand_id':g['catalogue']['sinks'][0]['demand_id']='phantom'
    elif attack=='header_section':g['catalogue']['section']['diameter_m']='1/4'
    elif attack=='macro_section':row['section']['diameter_m']='1/4'
    elif attack=='macro_start':row['start_cap']['position_m'][0]='0'
    elif attack=='macro_end_direction':row['end_cap']['flow_direction']=[-1,0,0]
    elif attack=='nominal_cost':row['nominal_cost']=['0','0']
    elif attack=='geometry_root':row['geometry_root']='f'*64
    elif attack=='fabrication_root':row['fabrication_root']='f'*64
    elif attack=='stored_check':macro['independent_check']['fabrication_status']='UNKNOWN'
    elif attack=='scope':g['limitations']['candidate_acceptance_authority']=True
    elif attack=='work_bool':g['work']=True
    elif attack=='unknown_field':g['native_pass']=True
    out=verify(r,s,c,g);assert out['status']=='FAIL',(attack,out)


@pytest.mark.parametrize('field',['diameter_m','insulation_m','start','end','normal','center','radius','angle','id','order','missing','extra'])
def test_resealed_physical_macro_geometry_forgery(field):
    r,s,c,g=fixture();row,macro=chosen(g,elbow=True);parts=macro['geometry']['components'];elbow=next(p for p in parts if p['kind']=='elbow')
    if field in ('diameter_m','insulation_m'):parts[0][field]+=.015625
    elif field=='start':parts[0]['geometry']['start_m'][0]+=.125
    elif field=='end':parts[0]['geometry']['end_m'][1]+=.125
    elif field=='normal':elbow['geometry']['normal']=[-x for x in elbow['geometry']['normal']]
    elif field=='center':elbow['geometry']['center_m'][0]+=.125
    elif field=='radius':elbow['geometry']['bend_radius_m']*=2
    elif field=='angle':elbow['geometry']['angle_rad']/=2
    elif field=='id':parts[0]['id']='forged-id'
    elif field=='order':parts.reverse()
    elif field=='missing':parts.pop()
    elif field=='extra':parts.append(copy.deepcopy(parts[-1]))
    rebind_geometry(row,macro)
    out=verify(r,s,c,g);assert out['status']=='FAIL',(field,out)


@pytest.mark.parametrize('field',['outer_radius','body_bounds','trim','point','context','status','reorder'])
def test_resealed_fabrication_claims(field):
    r,s,c,g=fixture();row,macro=chosen(g,elbow=True);cert=macro['certificate']
    if field=='outer_radius':cert['components'][0]['outer_radius_m']='1/128'
    elif field=='body_bounds':cert['components'][0]['body_bounds_m'][0][0]='0'
    elif field=='trim':cert['transitions'][0]['trim_debt_m']='0'
    elif field=='point':cert['manifest']['points_m'][0][0]='0'
    elif field=='context':cert['manifest']['context_root']='f'*64
    elif field=='status':cert['status']='FAIL'
    elif field=='reorder':
        cert['components'].reverse()
        # A fabrication proof's set-like component denominator permits reordering;
        # the physical expansion still must follow independently derived path order.
        macro['geometry']['components'].reverse();rebind_geometry(row,macro)
    reseal_fabrication(row,macro)
    out=verify(r,s,c,g);assert out['status']=='FAIL',(field,out)


def test_fresh_loss_and_search_changes_cannot_reuse_old_roots():
    for domain in ('loss','search','requirements'):
        r,s,c,g=fixture()
        if domain=='loss':r['physics']['tee_branch_loss_coefficient']=.4
        elif domain=='search':s['stub_lengths_m']=['1/2']
        else:r['minimum_bend_radius_m']=.5
        assert verify(r,s,c,g)['status']=='FAIL'


def test_coherent_supplied_subcatalogue_is_not_full_template_completeness():
    r,s,c,g=fixture();row,macro=chosen(g)
    g['catalogue']['connectors']=[row];g['connector_macros']={row['id']:macro}
    g['attempts']=[a for a in g['attempts'] if a.get('connector_id')==row['id']]
    out=verify(r,s,c,g)
    assert out['status']=='PASS',out
    assert out['counts']['connector_macros']==1 and not out['limitations']['all_templates_enumerated']


def test_failed_attempt_disposition_is_explicitly_untrusted():
    r,s,c,g=fixture();a=next(a for a in g['attempts'] if a['status']=='NOMINAL_TEMPLATE_NOT_ADMITTED')
    a['certificate']={'invented':'diagnostic only'};a['check']={'status':'PASS','native_acceptance':True}
    out=verify(r,s,c,g)
    assert out['status']=='PASS' and not out['limitations']['diagnostic_rejections_certified']


@pytest.mark.parametrize('kwargs',[{'max_work':1},{'max_bytes':1024},{'max_macros':1},{'max_attempts':1}])
def test_supported_limits_return_unknown(kwargs):
    out=verify(*fixture(),**kwargs);assert out['status']=='UNKNOWN' and not out['proof_complete']


@pytest.mark.parametrize('name,value',[('max_work',True),('max_bytes',0),('max_macros',0),('max_attempts',False)])
def test_strict_resource_types(name,value):assert verify(*fixture(),**{name:value})['status']=='FAIL'


@pytest.mark.parametrize('error_type',[ValueError,TimeoutError,v._Limit])
@pytest.mark.parametrize('stage',['shared_tree_catalogue_check_input','shared_tree_catalogue_check_fabrication_complete','shared_tree_catalogue_check_complete'])
def test_original_callback_exception_identity(error_type,stage):
    marker=error_type('caller exception')
    def checkpoint(current):
        if current==stage:raise marker
    with pytest.raises(error_type) as raised:verify(*fixture(),checkpoint=checkpoint)
    assert raised.value is marker


@pytest.mark.parametrize('target',['requirements','search','context','generated'])
def test_final_callback_mutation_is_rejected(target):
    r,s,c,g=fixture();complete=[False]
    def checkpoint(stage):
        assert not complete[0],'No callback permitted after final boundary'
        if stage=='shared_tree_catalogue_check_complete':
            complete[0]=True
            if target=='requirements':r['diameter_m']=.25
            elif target=='search':s['stub_lengths_m']=['1/2']
            elif target=='context':c['state_root']='c'*64
            else:g['catalogue']['connectors'].pop()
    assert verify(r,s,c,g,checkpoint=checkpoint)['status']=='FAIL' and complete[0]


def test_producer_helpers_not_invoked(monkeypatch):
    from oma.routing import shared_tree_proposals as producer
    import oma.optimization.fabrication as fabrication
    def forbidden(*args,**kwargs):raise AssertionError('producer helper invoked')
    for name in ('build_connector_catalogue','connector_templates','_physical_components','_cost','_network_from_assignment'):
        monkeypatch.setattr(producer,name,forbidden)
    monkeypatch.setattr(fabrication,'compile_orthogonal_fabrication',forbidden)
    assert verify(*fixture())['status']=='PASS'


def test_exact_work_tail_budget():
    data=fixture();r=verify(*data);assert r['status']=='PASS'
    assert verify(*data,max_work=r['work'])['status']=='PASS'
    assert verify(*data,max_work=r['work']-1)['status']=='UNKNOWN'


def test_input_nan_and_zero_denominator_fail_closed():
    for bad in (float('nan'),'1/0'):
        r,s,c,g=fixture();s['stub_lengths_m']=[bad]
        assert verify(r,s,c,g)['status']=='FAIL'


def test_coherent_valid_macro_outside_authored_template_is_rejected():
    from oma.routing import shared_tree_proposals as p
    from oma.optimization.fabrication import compile_orthogonal_fabrication,verify_orthogonal_fabrication
    r,s,c,g=fixture();normalized=g['normalized_requirements']
    row=next(x for x in g['catalogue']['connectors'] if any('9/4' in point for point in g['connector_macros'][x['id']]['geometry']['points_m']))
    old_id=row['id'];macro=g['connector_macros'][old_id]
    path=[[('2' if value=='9/4' else value) for value in point] for point in macro['geometry']['points_m']]
    definition={'from':row['from'],'to':row['to'],'points_m':path};new_id='connector-'+digest(definition)[:24]
    scenario=p._fabrication_scenario(normalized,list(map(Q,path[0])),list(map(Q,path[-1])))
    cert=compile_orthogonal_fabrication(scenario,path,context_root=g['input_root'],max_points=16)
    fresh=verify_orthogonal_fabrication(scenario,path,cert,context_root=g['input_root'],max_points=16)
    assert fresh['status']=='PASS' and fresh['fabrication_status']=='PASS'
    geometry={'points_m':path,'components':p._physical_components(cert,new_id,normalized)}
    new_macro={'geometry':geometry,'certificate':cert,'independent_check':fresh}
    row.update(id=new_id,geometry_root=digest(geometry),fabrication_root=cert['certificate_root'],nominal_cost=p._cost(cert,(Q(1),Q(0))))
    del g['connector_macros'][old_id];g['connector_macros'][new_id]=new_macro
    attempt=next(a for a in g['attempts'] if a.get('connector_id')==old_id)
    attempt.update(points_m=path,connector_id=new_id)
    out=verify(r,s,c,g)
    assert out['status']=='FAIL' and 'template language' in out['reason']


@pytest.mark.parametrize('text',['1e100000000','1e1_000_000','1e-1_000_000'])
def test_scientific_exponent_is_bounded_before_fraction_allocation(monkeypatch,text):
    r,s,c,g=fixture();s['stub_lengths_m']=[text]
    original=v.Q
    def guarded(value=0,*args):
        if isinstance(value,str) and '100000000' in value:raise AssertionError('Huge power converted before exponent guard')
        return original(value,*args)
    monkeypatch.setattr(v,'Q',guarded)
    out=verify(r,s,c,g)
    assert out['status']=='UNKNOWN' and out['reason']=='RATIONAL_BUDGET'


def test_scientific_fabrication_witness_never_reaches_legacy_parser(monkeypatch):
    r,s,c,g=fixture();row,macro=chosen(g)
    macro['certificate']['components'][0]['outer_radius_m']='1e100000000'
    reseal_fabrication(row,macro)
    def forbidden(*args,**kwargs):raise AssertionError('Unbounded witness entered legacy verifier')
    monkeypatch.setattr(v,'verify_orthogonal_fabrication',forbidden)
    out=verify(r,s,c,g)
    assert out['status']=='FAIL' and 'rational fabrication witness' in out['reason']


@pytest.mark.parametrize('text,expected',[('1_0/4',Q(5,2)),('+1/4',Q(1,4)),('2.5e-1',Q(1,4)),(' 0.25 ',Q(1,4))])
def test_bounded_authored_numeric_notation(text,expected):assert v._q(text)==expected


def test_intermediate_rational_budget():
    # Both operands fit; their sum has a denominator wider than the512-bit budget.
    a=Q(1,2**510-1);b=Q(1,2**509)
    with pytest.raises(v._Limit):v._plus((a,Q(0),Q(0)),(1,0,0),b)


def test_exact_generated_byte_boundary():
    data=fixture();g=data[-1]
    size=len(json.dumps(g,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())
    assert verify(*data,max_bytes=size)['status']=='PASS'
    assert verify(*data,max_bytes=size-1)['status']=='UNKNOWN'


def test_macro_budget_rechecked_after_initial_callback():
    r,s,c,g=fixture();row,macro=chosen(g)
    g['catalogue']['connectors']=[row];g['connector_macros']={row['id']:macro}
    g['attempts']=[a for a in g['attempts'] if a.get('connector_id')==row['id']]
    def checkpoint(stage):
        if stage=='shared_tree_catalogue_check_input':g['connector_macros']['extra']=copy.deepcopy(macro)
    out=verify(r,s,c,g,max_macros=1,checkpoint=checkpoint)
    assert out['status']=='UNKNOWN' and out['reason']=='MACRO_BUDGET'


def test_absent_geometry_cannot_be_hidden_in_diagnostic_status():
    r,s,c,g=fixture();row,_=chosen(g)
    a=next(a for a in g['attempts'] if a.get('connector_id')==row['id'])
    a.pop('connector_id');a.update(status='UNSUPPORTED_TEMPLATE',reason='invented')
    assert verify(r,s,c,g)['status']=='FAIL'
