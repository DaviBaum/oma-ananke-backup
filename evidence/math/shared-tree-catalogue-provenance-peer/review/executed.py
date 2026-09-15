"""Independent frozen catalogue provenance replay on actual retained workflows."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time
import uuid
from oma.store import digest

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').exists())
STAGE=Path(__file__).resolve().parent
RUNTIME=ROOT/'.oma/development/shared-tree-native-checker/runtimes/2db9a9cd13eea2fbd1633b4b9a02f44892a90d37f870d25d005c6a283c648ab4/src'
spec=importlib.util.spec_from_file_location('independent_catalogue_checker',RUNTIME/'oma/routing/shared_tree_catalogue_check.py')
checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    started=time.monotonic();out=STAGE/'catalogue-peer'/uuid.uuid4().hex;out.mkdir(parents=True)
    shutil.copy2(__file__,out/'executed.py')
    old=STAGE/'attempts/80e707d380fd47088e1b42dfdf1d7e2c'
    fixture_path=ROOT/'.oma/development/shared-tree-native/validation/f9c75d13b1334319a6d4822e3acc05da/tests/test_shared_tree_proposals.py'
    spec=importlib.util.spec_from_file_location('retained_fixture',fixture_path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    r,s,_=mod.fixture()
    rows=json.loads((old/'store-rows.json').read_text())
    run=next(x for x in rows['runs'] if x['id']=='9e737d3ffa744b199b9c588144f27bfc')
    request=json.loads(run['request']);r['source_id']=request['mission']['source_id']
    g=json.loads((old/'generation.json').read_text())['generation']
    state=json.loads((old/'candidate-0/state.json').read_text())
    c={'base_root':run['base_root'],'source_sha256':state['sources'][0]['sha256'],
       'checker_version':'oma-independent-checker/2:2b6e780b5150e7522287e71abf4eb29df47848f60c66255da828aa16b368dc50'}
    assert digest({'requirements':r,'search':s,'context':c})==g['input_root']
    from oma.routing import shared_tree_proposals as producer
    def forbidden(*a,**k):raise AssertionError('Catalogue producer called by independent verifier')
    for name in ('build_connector_catalogue','compile_shared_tree_proposals','connector_templates','_native_macro','_cost'):
        if hasattr(producer,name):setattr(producer,name,forbidden)
    inputs={'requirements':r,'search':s,'context':c,'generated':g}
    (out/'actual-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
    result=checker.verify_generated_catalogue(r,s,g,context=c);assert result['status']=='PASS',result
    (out/'actual-check.json').write_text(json.dumps(result,indent=2)+'\n')
    first=g['catalogue']['connectors'][0]['id']
    attacks=[]
    def check(name,change):
        x=copy.deepcopy(inputs);change(x)
        checked=checker.verify_generated_catalogue(x['requirements'],x['search'],x['generated'],context=x['context'])
        assert checked['status']!='PASS', (name,checked)
        attacks.append({'name':name,'result':checked})
    def row(x):return x['generated']['catalogue']['connectors'][0]
    def geom(x):return x['generated']['connector_macros'][first]['geometry']
    def reseal_geom(x):row(x)['geometry_root']=digest(geom(x))
    check('missing_macro',lambda x:x['generated']['connector_macros'].pop(first))
    check('duplicate_connector',lambda x:x['generated']['catalogue']['connectors'].append(copy.deepcopy(row(x))))
    check('forged_nominal_cost',lambda x:row(x).__setitem__('nominal_cost',['0','0']))
    check('source_context_changed',lambda x:x['context'].__setitem__('base_root','0'*64))
    check('raw_request_changed',lambda x:x['requirements']['physics'].__setitem__('tee_branch_loss_coefficient',.4))
    check('lost_terminal',lambda x:x['generated']['catalogue']['sinks'].pop())
    check('flow_axis_reversed',lambda x:row(x)['end_cap'].__setitem__('flow_direction',[-1,0,0]))
    check('relabel_physical_authority',lambda x:x['generated']['limitations'].__setitem__('native_geometry_or_service_checked',True))
    def altered_end(x):
        geom(x)['components'][0]['geometry']['end_m'][0]+=.125;reseal_geom(x)
    check('coherent_geometry_root_wrong_trim',altered_end)
    def altered_section(x):
        geom(x)['components'][0]['diameter_m']*=2;reseal_geom(x)
    check('coherent_geometry_root_wrong_section',altered_section)
    def altered_tee(x):
        tee=x['generated']['catalogue']['tee_instances'][0]
        x['generated']['tee_components'][tee['id']]['geometry']['frame_m'][0][3]+=.125
        tee['catalogue_root']=digest(x['generated']['tee_components'][tee['id']])
    check('coherent_tee_root_wrong_site',altered_tee)
    def remove_admitted(x):
        x['generated']['attempts']=[a for a in x['generated']['attempts'] if a.get('connector_id')!=first]
    check('missing_admitted_incidence',remove_admitted)
    check('fabrication_root_replaced',lambda x:row(x).__setitem__('fabrication_root','0'*64))
    check('changed_stub_language',lambda x:x['search'].__setitem__('stub_lengths_m',['1/16']))
    for target in ('requirements','generated','context'):
        x=copy.deepcopy(inputs)
        def mutate(stage):
            if stage=='shared_tree_catalogue_check_complete':
                if target=='requirements':x[target]['clearance_m']=.125
                elif target=='context':x[target]['base_root']='f'*64
                else:x[target]['work']+=1
        checked=checker.verify_generated_catalogue(x['requirements'],x['search'],x['generated'],context=x['context'],checkpoint=mutate)
        assert checked['status']=='FAIL' and not checked['proof_complete'],(target,checked)
        attacks.append({'name':'final_callback_'+target,'result':checked})
    tiny=checker.verify_generated_catalogue(r,s,g,context=c,max_work=result['work']-1)
    assert tiny['status']=='UNKNOWN' and not tiny['proof_complete']
    exact=checker.verify_generated_catalogue(r,s,g,context=c,max_work=result['work'])
    assert exact['status']=='PASS'
    subset=copy.deepcopy(g);subset['connector_macros']={};subset['catalogue']['connectors']=[]
    subset['attempts']=[a for a in subset['attempts'] if a['status']!='NOMINAL_MACRO_ADMITTED']
    empty=checker.verify_generated_catalogue(r,s,subset,context=c)
    assert empty['status']=='PASS' and empty['limitations']['all_templates_enumerated'] is False
    class Stop(BaseException):pass
    stop=Stop('owned cancellation')
    try:
        checker.verify_generated_catalogue(r,s,g,context=c,checkpoint=lambda stage:(_ for _ in ()).throw(stop))
    except Stop as error:assert error is stop
    else:raise AssertionError('Cancellation swallowed')
    office_path=ROOT/'.oma/development/shared-tree-office/evidence/5f68a587a8654bd187768d03f913388d/generated-packet.json'
    office=json.loads(office_path.read_text());q=office['authored_query']
    officecheck=checker.verify_generated_catalogue(q['requirements'],q['search'],office['result']['generation'],context=office['context'])
    assert officecheck['status']=='PASS',officecheck
    (out/'office-check.json').write_text(json.dumps(officecheck,indent=2)+'\n')
    source_map={p.relative_to(RUNTIME).as_posix():sha(p) for p in RUNTIME.rglob('*.py')}
    final={'status':'PASS','module_sha256':sha(checker.__file__),'source_map':source_map,'fixture_sha256':sha(fixture_path),
        'original_generation_sha256':sha(old/'generation.json'),'office_packet_sha256':sha(office_path),
        'positive_actual_2b6e':result,'positive_actual_4b_office':officecheck,'attacks':attacks,
        'bounded_work':{'exact':exact['status'],'one_less':tiny},'cancellation_identity_preserved':True,
        'empty_supplied_subset_scope':empty,'producer_functions_disabled':True,'elapsed_seconds':time.monotonic()-started,
        'scope':'Supplied macro provenance, complete admitted denominator and finite template membership only; no full template enumeration or CAD authority'}
    assert final['module_sha256']=='688cb03a0c75f23ee07e3e4b668980ec7d94267337b6c0f9b7ac4e5309045f7b'
    (out/'result.json').write_text(json.dumps(final,indent=2)+'\n')
    print(json.dumps({'status':'PASS','evidence':str(out),'attacks':len(attacks),'elapsed_seconds':final['elapsed_seconds']}))

if __name__=='__main__':main()
