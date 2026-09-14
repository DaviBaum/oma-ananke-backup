"""Peer audit of a supplied immutable passive native-tree adapter runtime."""
from pathlib import Path
from copy import deepcopy
from fractions import Fraction as Q
import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import uuid

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
STAGE=ROOT/'.oma/development/passive-native-tree'
NATIVE=STAGE/'evidence/native-three-sink/5c0e4ad0641d4acab0aca886eb023bf0'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def reseal(c):c['certificate_root']=digest({k:v for k,v in c.items() if k!='certificate_root'});return c
def contains(row,value):return Q(row['lower'])<=Q(value)<=Q(row['upper'])


def main():
    from oma.build_identity import checker_version
    from oma.routing import passive_tree_pressure as adapter
    from oma.routing import passive_tree_scenario as scenario
    parser=argparse.ArgumentParser();parser.add_argument('--expected-build',required=True);args=parser.parse_args()
    assert checker_version()==args.expected_build
    sources={p.name:{'path':str(p),'sha256':sha(p)} for p in (Path(adapter.__file__),Path(scenario.__file__))}
    out=STAGE/'evidence/independent-adapter-review'/uuid.uuid4().hex;out.mkdir(parents=True)
    for row in sources.values():shutil.copyfile(row['path'],out/Path(row['path']).name)
    shutil.copyfile(__file__,out/'executed-audit.py')
    fixture_names=('specification.json','new-boundary-declaration.json','native-metrics.json','native-evidence.json','independent-nominal-reference.json','result.json')
    fixture_hashes={name:sha(NATIVE/name) for name in fixture_names}
    for name in fixture_names:shutil.copyfile(NATIVE/name,out/('input-'+name))
    boundary=read(NATIVE/'new-boundary-declaration.json');network=read(NATIVE/'specification.json')
    metrics=read(NATIVE/'native-metrics.json');native=read(NATIVE/'native-evidence.json');reference=read(NATIVE/'independent-nominal-reference.json')
    context={'source_sha256':native['source_sha256'],'export_sha256':native['export_sha256'],
             'native_evidence_root':metrics['native_evidence_root'],'native_checker_version':read(NATIVE/'result.json')['checker_version']}
    declared={'adapter_checker_version':checker_version(),'adapter_sources':sources,'native_input_hashes':fixture_hashes,
              'script_sha256':sha(__file__),'context':context,'pressure_width_target':'1/10000'}
    write(out/'predeclaration.json',declared)
    start=time.perf_counter();observations=[]
    def evaluate(b=boundary,n=network,m=metrics,**kw):
        return adapter.evaluate_passive_tree(b,n,m,context=context,pressure_width_target='1/10000',**kw)
    def verify(c,b=boundary,n=network,m=metrics,**kw):
        return adapter.verify_passive_tree_envelope(b,n,m,c,context=context,pressure_width_target='1/10000',**kw)
    actual=evaluate();write(out/'actual-result.json',actual)
    assert actual['status']=='CERTIFIED_ENVELOPE' and actual['verdict']=='PASS',actual
    packet=actual['certificate'];service=packet['service'];derivation=packet['derivation']
    expected_groups=[{('trunk','a')},{('trunk','b'),('tee-1','a')},
        {('tee-1','b'),('tee-1','branch'),('arm-a','a'),('inter-tee','a')},
        {('inter-tee','b'),('tee-2','a')},{('tee-2','b'),('tee-2','branch'),('arm-b','a'),('arm-c','a')},
        {('arm-a','b')},{('arm-b','b')},{('arm-c','b')}]
    assert {frozenset(tuple(slot) for slot in group['slots']) for group in derivation['quotient_nodes']}=={frozenset(x) for x in expected_groups}
    assert derivation['counts']=={'components':7,'physical_ports':16,'connections':6,'tees':2,'graph_nodes':8,'boundaries':4}
    mapped={(r['component'],r['port']):r for r in service['physical_ports']}
    assert len(mapped)==len(service['physical_ports'])==16 and len(service['deliveries'])==3
    component_heads={'trunk':('source','tee-1-in'),'tee-1':('tee-1-in','tee-1-out'),'arm-a':('tee-1-out',None),
        'inter-tee':('tee-1-out','tee-2-in'),'tee-2':('tee-2-in','tee-2-out'),'arm-b':('tee-2-out',None),'arm-c':('tee-2-out',None)}
    for cid,ports in reference['physical_port_forward_flows_m3_s'].items():
        for port,flow in ports.items():
            row=mapped[(cid,port)];assert contains(row['flow_m3_s'],flow),(cid,port,row,flow)
            assert row['forward_status']==row['maximum_velocity_status']=='PASS'
            hname=component_heads[cid][0 if port=='a' else 1]
            h=Q(reference['relative_total_head_pa'][hname]) if hname else Q(0)
            assert contains(row['total_pressure_pa'],h),(cid,port,row,h)
            assert contains(row['total_head_pa'],h+Q(1000)*Q('9.80665')*3)
    assert len(service['conservation_identities'])==17
    # Every quotient edge is a unique actual component and uses its own section.
    sections=derivation['component_sections'];assert set(sections)=={c['id'] for c in network['components']}
    assert all(x['tee_darcy_charged'] is False for x in sections.values())
    for cid in ('tee-1','tee-2'):
        k=Q(boundary['tee_common_loss_coefficients'][cid]);beta=Q(reference['beta_pa_s2_m6'])
        assert contains(sections[cid]['resistance_pa_s2_m6'],k*beta)
    mutations={
        'drop_second_tee_quotient':lambda c:c['derivation']['quotient_nodes'].pop(),
        'drop_component_edge':lambda c:c['model']['edges'].pop(),
        'duplicate_port':lambda c:c['service']['physical_ports'].__setitem__(-1,deepcopy(c['service']['physical_ports'][0])),
        'tee_inlet_flow_for_outlet':lambda c:next(x for x in c['service']['physical_ports'] if (x['component'],x['port'])==('tee-1','branch')).update(flow_expression={'tee-1':1}),
        'omit_conservation':lambda c:c['service']['conservation_identities'].pop(),
        'omit_delivery':lambda c:c['service']['deliveries'].pop(),
        'forged_section':lambda c:c['derivation']['component_sections']['tee-2']['area_m2'].update(lower='1',upper='1'),
    }
    for name,mutate in mutations.items():
        bad=deepcopy(packet);mutate(bad);reseal(bad);result=verify(bad)
        assert result['status']=='FAIL',(name,result)
        observations.append({'attack':name,'result':result})
    for name,change in (
        ('boundary_loss_changed',lambda b:b['tee_common_loss_coefficients'].__setitem__('tee-2','1/2')),
        ('minimum_changed',lambda b:b['minimum_sink_flows_m3_s'].__setitem__('sink-c','1/10'))):
        b=deepcopy(boundary);change(b);result=verify(packet,b=b)
        assert result['status']=='FAIL';observations.append({'attack':name,'result':result})
    for name,alter in (
        ('velocity_limit',lambda b:b.__setitem__('maximum_velocity_m_s','1/10000')),
        ('delivery_limit',lambda b:b['minimum_sink_flows_m3_s'].__setitem__('sink-b','1/10')),
        ('reverse_pressure',lambda b:(b.__setitem__('source_total_pressure_pa','0'),b.__setitem__('sink_total_pressures_pa',{s:'100' for s in b['sink_total_pressures_pa']})))):
        b=deepcopy(boundary);alter(b);result=evaluate(b=b)
        assert result['status']=='CERTIFIED_ENVELOPE' and result['verdict']=='FAIL',(name,result)
        observations.append({'case':name,'status':result['status'],'verdict':result['verdict'],'service':result['certificate']['service']})
    for target in ('boundary','metrics','certificate'):
        b,m,c=deepcopy(boundary),deepcopy(metrics),deepcopy(packet);seen=[]
        def mutate(stage):
            if stage=='passive_tree_verifier_complete':
                seen.append(stage)
                if target=='boundary':b['source_total_pressure_pa']='101'
                elif target=='metrics':m['components']['tee-2']['outer_radius_m']['upper']='1'
                else:c['service']['physical_ports'].pop()
        result=verify(c,b=b,m=m,checkpoint=mutate)
        assert seen and result['status']=='FAIL' and 'changed' in result['reason'],result
        observations.append({'attack':'late_'+target,'result':result})
    assert all(sha(NATIVE/name)==value for name,value in fixture_hashes.items())
    assert all(sha(row['path'])==row['sha256'] for row in sources.values()) and checker_version()==args.expected_build
    result={'status':'INDEPENDENT_NATIVE_TREE_ADAPTER_REVIEW_PASS','adapter_build':args.expected_build,
        'native_geometry_previously_checked':True,'new_native_geometry_run':False,'original_files_unchanged':True,
        'exact_quotient_groups':8,'components':7,'physical_ports':16,'deliveries':3,'flow_reference_memberships':16,
        'independent_nominal_head_memberships':32,'conservation_identities':17,'attacks_and_service_cases':observations,
        'actual_result_sha256':sha(out/'actual-result.json'),'seconds':time.perf_counter()-start,
        'scope':'Actual native metrics + independent nominal model/reference and adversarial certificate reconstruction; external native authenticity/loss/boundary applicability remains a caller premise, no acceptance/export integration claim.'}
    write(out/'result.json',result)
    print(json.dumps({'status':result['status'],'directory':str(out),'result_sha256':sha(out/'result.json'),'seconds':result['seconds']}))


if __name__=='__main__':main()
