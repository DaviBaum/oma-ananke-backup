"""Fresh evidence-only native reference. All outputs stay in this private stage."""
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

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').exists())
STAGE=ROOT/'.oma/development/coupled-native-tree-reference'
BUILD='8144e76ddff8f1b4cb146aad47592a1ced7ba12dc2d21853c0f087c386cc2a70'
RUNTIME=ROOT/'.oma/development/coupled-tree-pressure/runtimes'/BUILD/'src'
ORIGINAL=ROOT/'.oma/development/passive-native-tree/evidence/native-three-sink/5c0e4ad0641d4acab0aca886eb023bf0/original.ifc'
FIXTURE=ROOT/'.oma/development/passive-native-tree/tests/native_three_sink_fixture.py'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def child(out):
    from oma.build_identity import checker_version
    out=Path(out).resolve();sys.path.insert(0,str(out))
    from native_three_sink_fixture import complete_native_evidence
    declared=read(out/'predeclaration.json')
    assert checker_version()==declared['checker_version']
    for name,key in [('original.ifc','source_sha256'),('specification.json','specification_sha256'),('boundary.json','boundary_sha256'),('manufactured-nominal.json','manufactured_sha256')]:
        assert sha(out/name)==declared[key]
    native=complete_native_evidence(out/'original.ifc',out/'unequal-outlet-tree.ifc',read(out/'specification.json'))
    write(out/'native-evidence.json',native)
    assert native['semantics']['status']==native['cad']['coordination_status']==native['cad']['self_interference_status']==native['zone']['status']=='PASS'
    assert native['cad']['pairs_accounted']==7 and len(native['cad']['self_pair_results'])==21
    assert len(native['semantics']['parts'])==7 and len(native['semantics']['ports'])==16
    assert len(native['native_connection_signs'])==6 and len(native['zone']['parts'])==7
    import ifcopenshell
    before=ifcopenshell.open(str(out/'original.ifc'));after=ifcopenshell.open(str(out/'unequal-outlet-tree.ifc'))
    differences=[e.id() for e in before if str(e)!=str(after.by_id(e.id()))]
    preservation={'status':'PASS' if not differences else 'FAIL','original_parsed_entities':len(list(before)),
        'export_parsed_entities':len(list(after)),'changed_original_parsed_entities':differences,
        'original_file_sha256':sha(out/'original.ifc'),'interpretation':'Exact equality of canonical parsed IFC entity strings at original STEP IDs; source bytes unchanged. No raw output serializer byte identity claim.'}
    write(out/'original-preservation.json',preservation);assert preservation['status']=='PASS'
    assert checker_version()==declared['checker_version'] and sha(out/'original.ifc')==declared['source_sha256']
    print(json.dumps({'status':'PASS','parts':7,'ports':16,'source_pairs':7,'self_pairs':21,'zone_parts':7}))


def mutation_audit(spec,boundary,metrics,context,packet):
    import reference as r
    cases=[]
    def test(name,mutate,which='packet'):
        values={'spec':deepcopy(spec),'boundary':deepcopy(boundary),'metrics':deepcopy(metrics),'context':deepcopy(context),'packet':deepcopy(packet)}
        mutate(values[which]);p=values['packet']
        # Coherently reseal modified physical mapping: the replay must inspect semantics.
        p['model']['physical_model_root']=r.digest(p['physical'])
        answer=r.check_reference(values['spec'],values['boundary'],values['metrics'],values['context'],p)
        cases.append({'name':name,'status':answer['status']});assert answer['status']=='FAIL',name
    test('missing_port',lambda p:p['physical']['ports'].pop('tee-1.branch'))
    test('wrong_tee_inlet_sum',lambda p:p['model']['terms'][1].update(descendant_leaves=['sink-b','sink-c']))
    test('outlet_flow_used_for_tee_loss',lambda p:p['physical']['term_metadata']['tee-1:branch'].update(hydraulic_inlet_descendants=['sink-a']))
    test('swapped_tee_outlet_coefficients',lambda p:p['model']['coefficients'].update({'tee-1:b':p['model']['coefficients']['tee-1:branch']}))
    test('tee_darcy_double_charge',lambda p:p['physical']['term_metadata']['tee-2:b'].update(tee_skeleton_darcy_charged=True))
    test('missing_pipe_term',lambda p:p['model']['terms'].pop())
    test('duplicate_term',lambda p:p['model']['terms'].append(deepcopy(p['model']['terms'][0])))
    test('missing_component_section',lambda p:p['physical']['sections'].pop('trunk'))
    test('nominal_area_substitution',lambda p:p['physical']['sections']['trunk'].update(area_m2=r.enc(Q(1,100))))
    test('wrong_insulation',lambda p:p['physical']['sections']['trunk'].update(declared_insulation_m='0'))
    test('wrong_port_outward_sign',lambda p:p['physical']['ports']['tee-1.a'].update(outward_flow_sign=1))
    test('wrong_branch_flow',lambda p:p['physical']['ports']['tee-1.branch'].update(forward_flow_leaf_coefficients={'sink-b':1}))
    test('unjustified_common_outlet_head',lambda p:p['physical']['ports']['tee-1.branch'].update(total_head_loss_terms=p['physical']['ports']['tee-1.b']['total_head_loss_terms']))
    test('static_total_pressure_confusion',lambda p:p['physical']['ports']['trunk.a'].update(total_pressure_relation='H_port'))
    test('wrong_cap_position',lambda p:p['physical']['ports']['trunk.a']['position_m'][2].update(lower='0',upper='0'))
    test('missing_continuity_identity',lambda p:p['physical']['continuity'].pop())
    test('duplicate_continuity_identity',lambda p:p['physical']['continuity'].__setitem__(0,deepcopy(p['physical']['continuity'][1])))
    test('forged_zero_continuity',lambda p:p['physical']['continuity'][0]['port_coefficients'].update({'trunk.a':2}))
    test('missing_singleton_positive_witness',lambda p:p['physical']['positive_singleton_leaf_terms'].update({'sink-c':[]}))
    test('wrong_available_head',lambda p:p['model']['available_heads']['sink-a'].update(lower='0'))
    test('changed_context',lambda p:p.update(export_sha256='0'*64),'context')
    test('changed_boundary',lambda p:p.update(gravity_m_s2='0'),'boundary')
    test('changed_native_radius',lambda p:p['components']['trunk']['outer_radius_m'].update(lower='1/100'),'metrics')
    test('duplicate_current_component',lambda p:p['components'].append(deepcopy(p['components'][0])),'spec')
    test('wrong_source_to_leaf_partition',lambda p:p['demand_paths'][0]['steps'].__setitem__(1,{'component':'tee-1','entry_port':'a','exit_port':'b'}),'spec')
    original=r.derive_reference
    r.derive_reference=lambda *a,**k:(_ for _ in ()).throw(AssertionError('Producer disabled'))
    try: independent=r.check_reference(spec,boundary,metrics,context,packet)
    finally:r.derive_reference=original
    assert independent['status']=='PASS'
    return {'status':'PASS','rejected_mutations':cases,'producer_disabled_reference_check':independent}


def main():
    from oma.build_identity import checker_version
    from oma.export_checks import supervise_check
    import reference as r
    assert checker_version()=='oma-independent-checker/2:'+BUILD
    out=STAGE/'evidence'/uuid.uuid4().hex;out.mkdir(parents=True)
    for source,name in [(Path(__file__),'executed-campaign.py'),(STAGE/'reference.py','reference.py'),(FIXTURE,'native_three_sink_fixture.py'),(ORIGINAL,'original.ifc')]:shutil.copyfile(source,out/name)
    sys.path.insert(0,str(out))
    from native_three_sink_fixture import three_sink_spec
    spec=three_sink_spec();spec['network_id']='explicit-unequal-outlet-three-sink-native-reference'
    boundary,manufactured=r.nominal_declaration(spec)
    write(out/'specification.json',spec);write(out/'boundary.json',boundary);write(out/'manufactured-nominal.json',manufactured)
    source_map={p.relative_to(RUNTIME).as_posix():sha(p) for p in RUNTIME.rglob('*.py')}
    declared={'schema':'oma.unequal-tee-native-predeclaration/1','checker_version':checker_version(),
        'source_sha256':sha(out/'original.ifc'),'original_readonly_path':str(ORIGINAL),
        'specification_sha256':sha(out/'specification.json'),'boundary_sha256':sha(out/'boundary.json'),
        'manufactured_sha256':sha(out/'manufactured-nominal.json'),'reference_sha256':sha(out/'reference.py'),
        'script_sha256':sha(out/'executed-campaign.py'),'fixture_sha256':sha(out/'native_three_sink_fixture.py'),
        'application_sources':source_map,'declared_before_native_checks':True,'native_absolute_metric_uncertainty_m':str(r.TOL),
        'geometry_policy':'Same seven geometric components and directed physical caps as existing analytic fixture; new network identity and new hypothetical unequal-outlet hydraulic declaration only.',
        'scope':'Native geometry plus independent declared polynomial reference/local Banach proof. No app adapter integration, accepted project, global uniqueness or measured bore claim.'}
    write(out/'predeclaration.json',declared)
    print(json.dumps({'phase':'PREDECLARED','directory':str(out),'boundary_sha256':declared['boundary_sha256']}),flush=True)
    env=os.environ.copy();env.update(PYTHONPATH=str(RUNTIME),OMA_EXECUTABLE_BUILD=checker_version(),PYTHONDONTWRITEBYTECODE='1')
    supervision=supervise_check([sys.executable,str(out/'executed-campaign.py'),'--child',str(out)],environment=env,directory=out/'process',deadline=time.monotonic()+120)
    write(out/'supervision.json',supervision);assert supervision['status']=='COMPLETED',supervision
    native=read(out/'native-evidence.json');metrics=r.metrics_from_native(spec,native);write(out/'native-metrics.json',metrics)
    context={'source_sha256':native['source_sha256'],'export_sha256':native['export_sha256'],'native_evidence_root':r.digest(native),
        'predeclaration_sha256':sha(out/'predeclaration.json'),'supervision_sha256':sha(out/'supervision.json'),'checker_version':checker_version()}
    write(out/'context.json',context)
    packet=r.derive_reference(spec,boundary,metrics,context);write(out/'reference-packet.json',packet);write(out/'polynomial-model.json',packet['model'])
    check=r.check_reference(spec,boundary,metrics,context,packet);write(out/'reference-check.json',check);assert check['status']=='PASS',check
    oracle=r.nominal_oracle(spec,boundary,manufactured,packet);write(out/'independent-nominal-oracle.json',oracle)
    mutations=mutation_audit(spec,boundary,metrics,context,packet);write(out/'mapping-mutation-audit.json',mutations)
    from oma.optimization import coupled_tree_pressure as kernel
    cert=kernel.compile_coupled_tree_pressure(packet['model'],boundary['flow_search_box_m3_s'])
    write(out/'local-banach-certificate.json',cert)
    check=kernel.verify_coupled_tree_pressure(packet['model'],boundary['flow_search_box_m3_s'],cert)
    write(out/'local-banach-check.json',check);assert check['status']=='PASS',check
    old=kernel.compile_coupled_tree_pressure;kernel.compile_coupled_tree_pressure=lambda *a,**k:(_ for _ in ()).throw(AssertionError('Producer disabled'))
    try: independent=kernel.verify_coupled_tree_pressure(packet['model'],boundary['flow_search_box_m3_s'],cert)
    finally:kernel.compile_coupled_tree_pressure=old
    assert independent['status']=='PASS';write(out/'producer-disabled-banach-check.json',independent)
    # Service bounds here are local-reference consequences only, not application admission.
    flows={k:r.interval(v) for k,v in check['root_enclosure'].items()};delivery={}
    for leaf,q in flows.items():delivery[leaf]={'flow_m3_s':r.enc(*q),'minimum_m3_s':boundary['minimum_sink_flows_m3_s'][leaf],'status':'PASS' if q[0]>=Q(boundary['minimum_sink_flows_m3_s'][leaf]) else 'UNKNOWN'}
    ports={}
    for pid,p in packet['physical']['ports'].items():
        q=(Q(0),Q(0))
        for leaf,a in p['forward_flow_leaf_coefficients'].items():q=r.add(q,r.mul(r.point(a),flows[leaf]))
        v=r.div(q,r.interval(packet['physical']['sections'][p['component_id']]['area_m2']))
        ports[pid]={'forward_flow_m3_s':r.enc(*q),'outward_flow_m3_s':r.enc(*r.mul(q,r.point(p['outward_flow_sign']))),
            'velocity_m_s':r.enc(*r.rounded(v,12)),'maximum_velocity_m_s':boundary['maximum_velocity_m_s'],'status':'PASS' if v[1]<=Q(boundary['maximum_velocity_m_s']) else 'UNKNOWN'}
    service={'scope':'ONLY ROOT INSIDE DECLARED BOX; global uniqueness and native admission NOT_RUN','deliveries':delivery,'ports':ports}
    assert len(delivery)==3 and len(ports)==16 and all(x['status']=='PASS' for x in [*delivery.values(),*ports.values()]);write(out/'local-reference-service.json',service)
    guards={'original_bytes':sha(ORIGINAL)==declared['source_sha256']==sha(out/'original.ifc'),
        'specification':sha(out/'specification.json')==declared['specification_sha256'],'boundary':sha(out/'boundary.json')==declared['boundary_sha256'],
        'manufactured':sha(out/'manufactured-nominal.json')==declared['manufactured_sha256'],
        'fixture':sha(FIXTURE)==declared['fixture_sha256'],'reference':sha(STAGE/'reference.py')==declared['reference_sha256'],
        'script':sha(__file__)==declared['script_sha256'],'frozen_application':{p.relative_to(RUNTIME).as_posix():sha(p) for p in RUNTIME.rglob('*.py')}==source_map}
    assert all(guards.values()),guards
    result={'status':'NATIVE_REFERENCE_AND_LOCAL_BANACH_PASS','checker_version':checker_version(),'preservation':guards,
        'native_denominators':{'components':7,'ports':16,'connections':6,'source_obstacles':1,'source_pairs':7,'self_pairs':21,'zone_solids':7},
        'polynomial_denominators':{'terms':9,'pipe_terms':5,'tee_outlet_terms':4,'continuity_identities':17,'positive_singleton_leaf_terms':3},
        'source_sha256':native['source_sha256'],'export_sha256':native['export_sha256'],'network_root':metrics['network_root'],
        'native_evidence_root':metrics['native_evidence_root'],'metrics_root':r.digest(metrics),'model_root':check['model_root'],
        'certificate_root':check['certificate_root'],'reference_check_sha256':sha(out/'reference-check.json'),
        'mapping_mutations_rejected':len(mutations['rejected_mutations']),'local_banach_status':check['status'],
        'local_reference_delivery_count':3,'local_reference_velocity_count':16,'scope':declared['scope']}
    write(out/'result.json',result)
    (out/'README.md').write_text('Fresh supervised native IFC geometry and semantics PASS: seven unique components, two distinct tees, 16 ports, six matching connections, all seven original-source pairs, 21 self pairs and seven zone checks. Original parsed entities and original file bytes are preserved.\n\nThis NEW hypothetical unequal-outlet declaration was saved before native checks. Each tee outlet loses a different positive coefficient times FULL tee inlet flow squared; no extra Darcy term is charged for the tee skeleton. Five actual pipe lengths, seven outer radii and 16 cap positions carry explicit one-micrometre native uncertainty. Hydraulic bore is an ideal declared envelope-minus-insulation assumption.\n\nThe independent path replay covers all nine terms, 16 port flow/head equations and 17 continuity identities. A manufactured rational nominal flow vector has separately computed 85-digit pressures. The reviewed rational Banach checker proves one root inside the declared positive box for each same parameter tuple of the conservative derived coefficient/head box. Local delivery/velocity implications pass. Global uniqueness, production adapter integration and native project acceptance have not been run and are not claimed.\n',encoding='utf-8')
    write(out/'files.json',{'files':[{'path':p.relative_to(out).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(out.rglob('*')) if p.is_file()]})
    print(json.dumps({'status':result['status'],'directory':str(out),'result_sha256':sha(out/'result.json'),'scope':result['scope']}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--child',type=Path);args=parser.parse_args()
    child(args.child) if args.child else main()
