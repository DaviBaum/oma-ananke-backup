"""Independent adapter comparison against saved fresh native/path reference."""
from pathlib import Path
from copy import deepcopy
from fractions import Fraction as Q
from decimal import Decimal, localcontext
import argparse
import hashlib
import json
import shutil
import uuid
import reference as r

STAGE=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def contained(outer,inner):
    lo,hi=r.interval(outer);a,b=r.interval(inner)
    return lo<=a<=b<=hi
def reroot(packet):packet['certificate_root']=r.digest({k:v for k,v in packet.items() if k!='certificate_root'});return packet

def main(expected_sha):
    from oma.routing import coupled_tree_pressure as a
    from oma.optimization import coupled_tree_pressure as local
    from oma.optimization import coupled_tree_univalence as global_proof
    assert sha(a.__file__)==expected_sha
    assert sha(local.__file__)=='ce5a264c7815b860b9ce0b8001e1b35cc3ecf7f4acacafc4925f7a6e37060c90'
    assert sha(global_proof.__file__)=='f433e0c007912aa9501306b2bfc95f0809a135e46b5ad898421410eabe10e4df'
    attempt=STAGE/'evidence/d5b064b69b3f4cf19b7c5824cd439f63';out=STAGE/'adapter-peer-audits'/uuid.uuid4().hex;out.mkdir(parents=True)
    files=('boundary.json','specification.json','native-metrics.json','context.json','reference-packet.json','independent-nominal-oracle.json','native-evidence.json')
    inputs={name:read(attempt/name) for name in files};hashes={name:sha(attempt/name) for name in files}
    b,n,m,context=(inputs[x] for x in files[:4]);reference=inputs['reference-packet.json'];oracle=inputs['independent-nominal-oracle.json']
    shutil.copyfile(__file__,out/'executed-audit.py')
    write(out/'inputs.json',{'native_reference':str(attempt),'input_sha256':hashes,'adapter_path':a.__file__,'adapter_sha256':expected_sha,
        'local_kernel_sha256':sha(local.__file__),'univalence_kernel_sha256':sha(global_proof.__file__),'audit_sha256':sha(__file__)})
    model,box,d=a.derive_coupled_tree_model(b,n,m,context=context)
    write(out/'derived.json',{'model':model,'box':box,'derivation':d})
    assert box==b['flow_search_box_m3_s']
    expected_counts={'components':7,'physical_ports':16,'connections':6,'tees':2,'terms':9,'leaves':3,'boundaries':4}
    assert d['counts']==expected_counts
    assert d['network_root']==m['network_root'] and d['native_evidence_root']==m['native_evidence_root'] and d['metric_root']==r.digest(m)
    terms={t['id']:t for t in model['terms']};physics={x['term_id']:x for x in d['term_physics']}
    assert len(terms)==len(model['terms'])==len(physics)==len(d['term_physics'])==9
    translation={};coefficient_rows=[]
    for tid,p in physics.items():
        cid,slot=p['component'],p['outlet'];old=f'{cid}:{slot}' if slot!='body' else cid;translation[tid]=old
        expected=reference['physical']['term_metadata'][old];term=terms[tid]
        assert term['descendant_leaves']==expected['hydraulic_inlet_descendants'] and term['applies_to_leaves']==expected['applies_to_leaves']
        assert p['descendant_leaves']==term['descendant_leaves'] and p['applies_to_leaves']==term['applies_to_leaves']
        assert p['flow_reference']=='COMPLETE_COMPONENT_INLET_DESCENDANTS' and p['tee_darcy_charged'] is False
        raw=d['component_sections'][cid]['loss_coefficients_pa_s2_m6'][slot];outer=model['coefficients'][term['coefficient_id']]
        assert contained(expected['exact_coefficient_bounds'],raw) and contained(outer,raw)
        assert outer==r.enc(*r.dyadic(r.interval(raw)))
        coefficient_rows.append({'reference_term':old,'adapter_term':tid,'raw_enclosed_by_independent_reference':True,
            'raw_enclosed_by_published_dyadic':True,'published_equals_reference_dyadic':outer==reference['model']['coefficients'][old]})
    assert set(translation.values())==set(reference['model']['coefficients'])
    for cid,section in d['component_sections'].items():
        expected=reference['physical']['sections'][cid]
        assert section['diameter_m']==expected['diameter_m'] and contained(expected['area_m2'],section['area_m2'])
        assert section['tee_darcy_charged'] is False
    assert model['available_heads']==reference['model']['available_heads']
    for leaf,raw in d['available_heads_pa'].items():assert contained(model['available_heads'][leaf],raw)
    port_paths={f"{p['component']}.{p['port']}":p for p in d['port_paths']};assert len(port_paths)==len(d['port_paths'])==16
    for pid,p in port_paths.items():
        ref=reference['physical']['ports'][pid]
        assert p['descendant_leaves']==sorted(ref['forward_flow_leaf_coefficients'])
        assert [translation[t] for t in p['loss_terms']]==ref['total_head_loss_terms']
    for leaf,path in d['sink_paths'].items():
        assert path==[[s['component'],s['entry_port'],s['exit_port']] for s in reference['physical']['paths'][leaf]]
    evaluation=a.evaluate_coupled_tree(b,n,m,context=context);write(out/'evaluation.json',evaluation)
    assert evaluation['status']=='CERTIFIED_ENVELOPE' and evaluation['verdict']=='PASS'
    cert=evaluation['certificate'];check=a.verify_coupled_tree_envelope(b,n,m,cert,context=context);write(out/'verified.json',check)
    assert check['status']==check['verdict']=='PASS' and check['proof_complete'] is True
    assert check['local_check']['model_root']==check['global_check']['model_root']==check['model_root']
    assert cert['local_certificate']['parameter_root']==check['global_check']['parameter_root']
    service=check['service'];assert service['counts']=={'physical_ports':16,'deliveries':3,'conservation_identities':17,'head_path_identities':19}
    assert len({x['id'] for x in service['conservation_identities']})==17 and all(x['difference']=={} for x in service['conservation_identities'])
    actual_ports={f"{p['component']}.{p['port']}":p for p in service['physical_ports']};assert len(actual_ports)==16
    with localcontext() as ctx:
        ctx.prec=100
        def decimal(q):q=Q(q);return Decimal(q.numerator)/Decimal(q.denominator)
        for pid,p in actual_ports.items():
            ref=reference['physical']['ports'][pid];nom=oracle['ports'][pid]
            assert p['flow_expression']==ref['forward_flow_leaf_coefficients']
            assert [translation[t] for t in p['loss_terms']]==ref['total_head_loss_terms']
            assert p['forward_status']==p['maximum_velocity_status']=='PASS'
            for actual,nominal in [('flow_m3_s','forward_flow_m3_s'),('velocity_m_s','velocity_m_s'),('total_head_pa','total_head_pa'),('total_pressure_pa','total_pressure_pa')]:
                lo,hi=r.interval(p[actual]);value=decimal(nom[nominal]);assert decimal(lo)<=value<=decimal(hi),(pid,actual)
    attacks=[]
    def attack(name,mutate):
        bad=deepcopy(cert);mutate(bad);reroot(bad)
        answer=a.verify_coupled_tree_envelope(b,n,m,bad,context=context)
        attacks.append({'name':name,'status':answer['status']});assert answer['status']!='PASS',name
    attack('missing_global_certificate',lambda p:p.pop('univalence_certificate'))
    attack('missing_local_certificate',lambda p:p.pop('local_certificate'))
    attack('unrelated_global_model',lambda p:p['univalence_certificate'].update(model_root='0'*64))
    attack('unrelated_local_parameter_box',lambda p:p['local_certificate'].update(parameter_root='0'*64))
    attack('remove_current_native_section',lambda p:p['derivation']['component_sections'].pop('arm-c'))
    attack('missing_actual_port',lambda p:p['derivation']['port_paths'].pop())
    attack('duplicate_actual_port',lambda p:p['derivation']['port_paths'].__setitem__(0,deepcopy(p['derivation']['port_paths'][1])))
    attack('scalar_midpoint_coefficient',lambda p:p['model']['coefficients'][next(iter(p['model']['coefficients']))].update(lower='1',upper='1'))
    attack('wrong_full_tee_inlet_descendants',lambda p:next(x for x in p['derivation']['term_physics'] if x['component']=='tee-1' and x['outlet']=='b').update(descendant_leaves=['sink-b','sink-c']))
    attack('tee_skeleton_darcy_double_charge',lambda p:p['derivation']['component_sections']['tee-1'].update(tee_darcy_charged=True))
    attack('wrong_dyadic_rounding_claim',lambda p:p['derivation']['parameter_rounding'].update(substitutes_midpoint=True))
    attack('wrong_ideal_bore_radius',lambda p:p['derivation']['component_sections']['trunk']['diameter_m'].update(lower='7/50',upper='7/50'))
    attack('missing_delivery',lambda p:p['service']['deliveries'].pop())
    attack('forged_delivery_count',lambda p:p['service']['counts'].update(deliveries=2))
    attack('wrong_forward_sign',lambda p:p['service']['physical_ports'][0].update(forward_status='FAIL'))
    attack('forged_total_as_static_pressure',lambda p:p['service']['physical_ports'][0]['total_pressure_pa'].update(lower='0',upper='0'))
    attack('missing_continuity_identity',lambda p:p['service']['conservation_identities'].pop())
    attack('common_tee_outlet_head_substitution',lambda p:next(x for x in p['service']['physical_ports'] if x['component']=='tee-1' and x['port']=='branch').update(total_head_pa=deepcopy(next(x for x in p['service']['physical_ports'] if x['component']=='tee-1' and x['port']=='b')['total_head_pa'])))
    # Input mutation is distinct from a forged certificate; all bound dimensions remain authoritative.
    input_attacks=[]
    for target in ('native_radius','native_cap','native_length','minimum','inlet_loss'):
        bb,mm=deepcopy(b),deepcopy(m)
        if target=='native_radius':mm['components']['trunk']['outer_radius_m']={'lower':'7/100','upper':'7/100'}
        elif target=='native_cap':mm['components']['tee-1']['ports']['a']['position_m'][2]={'lower':'0','upper':'0'}
        elif target=='native_length':mm['components']['arm-a']['length_m']={'lower':'1','upper':'1'}
        elif target=='minimum':bb['minimum_sink_flows_m3_s']['sink-a']='1'
        else:bb['tee_outlet_loss_coefficients']['tee-1']['branch']=bb['tee_outlet_loss_coefficients']['tee-1']['b']
        answer=a.verify_coupled_tree_envelope(bb,n,mm,cert,context=context)
        assert answer['status']!='PASS';input_attacks.append({'target':target,'status':answer['status']})
    saved={name:getattr(a,name) for name in ('evaluate_coupled_tree','derive_coupled_tree_model')}
    saved_local=local.compile_coupled_tree_pressure;saved_global=global_proof.compile_coupled_tree_univalence
    def disabled(*args,**kwargs):raise AssertionError('Producer invoked during independent replay')
    for name in saved:setattr(a,name,disabled)
    local.compile_coupled_tree_pressure=global_proof.compile_coupled_tree_univalence=disabled
    try: independent=a.verify_coupled_tree_envelope(b,n,m,cert,context=context)
    finally:
        for name,value in saved.items():setattr(a,name,value)
        local.compile_coupled_tree_pressure=saved_local;global_proof.compile_coupled_tree_univalence=saved_global
    assert independent['status']==independent['verdict']=='PASS'
    late=[]
    for target in ('boundary','metrics','certificate','context'):
        bb,mm,cc,ctx=deepcopy(b),deepcopy(m),deepcopy(cert),deepcopy(context);fired=[]
        def pulse(stage):
            if stage=='coupled_tree_verifier_complete' and not fired:
                fired.append(stage)
                if target=='boundary':bb['minimum_sink_flows_m3_s']['sink-a']='1'
                elif target=='metrics':mm['components']['arm-a']['length_m']['lower']='0'
                elif target=='certificate':cc['service']['verdict']='FAIL'
                else:ctx['export_sha256']='0'*64
        answer=a.verify_coupled_tree_envelope(bb,n,mm,cc,context=ctx,checkpoint=pulse)
        assert fired and answer['status']!='PASS';late.append({'target':target,'status':answer['status']})
    budget=a.verify_coupled_tree_envelope(b,n,m,cert,context=context,max_work=check['work']-1)
    assert budget['status']=='UNKNOWN'
    assert hashes=={name:sha(attempt/name) for name in files} and sha(a.__file__)==expected_sha
    result={'status':'PASS','adapter_sha256':expected_sha,'native_reference':str(attempt),'coefficients':coefficient_rows,
        'reference_counts':expected_counts,'service_counts':service['counts'],'native_nominal_oracle_enclosed_at_all16_ports':True,
        'reference_derivation_agrees':True,'rejected_resealed_attacks':attacks,'rejected_input_changes':input_attacks,
        'late_mutations':late,'producer_disabled_status':independent['status'],'shared_work_limit':budget,
        'model_root':check['model_root'],'local_root':check['local_check']['certificate_root'],'global_root':check['global_check']['certificate_root'],
        'scope':'Independent adapter reference comparison and proof/port/delivery attacks. Supplied metrics remain separately native-authenticated; no application acceptance/export run in this audit.'}
    write(out/'result.json',result);print(json.dumps({'status':'PASS','directory':str(out),'result_sha256':sha(out/'result.json')}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--expected-sha',required=True);args=parser.parse_args();main(args.expected_sha)
