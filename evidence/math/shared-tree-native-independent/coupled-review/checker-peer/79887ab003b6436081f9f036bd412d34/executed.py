"""Standalone independent coupled catalogue identity attacks; no native run."""
from copy import deepcopy
from pathlib import Path
import hashlib,importlib.util,json,os,shutil,time,uuid
from audit_nominal import AUTH,ROOT,STAGE,read,write,digest

MODULE=ROOT/'.oma/development/shared-tree-coupled-checker/runtimes/0f780ef00357d14887bdb067263b8ed891cddeed91aa7ccdc5169e3ebf1a7a29/src/oma/routing/shared_tree_catalogue_check.py'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    started=time.monotonic();out=STAGE/'checker-peer'/uuid.uuid4().hex;out.mkdir(parents=True)
    shutil.copy2(__file__,out/'executed.py');shutil.copy2(MODULE,out/'checked-module.py')
    spec=importlib.util.spec_from_file_location('coupled_peer_checker',MODULE);checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
    from oma.routing import shared_tree_proposals as producer
    def forbidden(*a,**kw):raise AssertionError('No producer calls permitted')
    for name in ('build_connector_catalogue','compile_shared_tree_proposals','connector_templates','_network_from_assignment'):
        setattr(producer,name,forbidden)
    base={'requirements':read(AUTH/'requirements.json'),'search':read(AUTH/'search.json'),
          'generated':read(AUTH/'generated.json'),'context':read(AUTH/'context.json')}
    def verify(x,**kwargs):return checker.verify_generated_catalogue(x['requirements'],x['search'],x['generated'],context=x['context'],**kwargs)
    positive=verify(base);assert positive['status']=='PASS',positive
    cases=[]
    def attack(name,change):
        x=deepcopy(base);change(x);answer=verify(x)
        assert answer['status']!='PASS' and not answer['proof_complete'],(name,answer)
        cases.append({'name':name,'result':answer})
    def b(x):return x['requirements']['coupled_tree']
    attack('omit_tee_loss_id',lambda x:b(x)['tee_outlet_loss_coefficients'].pop('tee-c'))
    attack('extra_tee_site',lambda x:x['search']['tee_instances'].append(deepcopy(x['search']['tee_instances'][0])))
    attack('duplicate_tee_site_id',lambda x:x['search']['tee_instances'][1].__setitem__('id','tee-a'))
    attack('missing_sink_boundary',lambda x:b(x)['sink_total_pressures_pa'].pop('sink-c'))
    attack('forged_minimum_alias',lambda x:b(x)['minimum_sink_flows_m3_s'].__setitem__('sink-c','9/1000'))
    attack('legacy_prescribed_delivery',lambda x:x['requirements']['sinks'][0].__setitem__('required_flow_m3_s',.001))
    attack('legacy_static_pressure',lambda x:x['requirements']['sinks'][0].__setitem__('available_static_pressure_pa',100))
    attack('geometry_only_mode',lambda x:x['requirements'].__setitem__('target_modality','LOCAL_COORDINATION'))
    attack('wrong_tee_loss_reference',lambda x:b(x).__setitem__('tee_loss_reference','TOTAL_TEE_LOSS_AT_OUTLET_FLOW'))
    attack('changed_total_boundary',lambda x:b(x).__setitem__('source_total_pressure_pa',{'lower':'201','upper':'201'}))
    def swapped_loss_roots(x):
        a,c=x['generated']['catalogue']['tee_instances'];a['loss_contract_root'],c['loss_contract_root']=c['loss_contract_root'],a['loss_contract_root']
    attack('per_tee_loss_roots_swapped',swapped_loss_roots)
    def unbound_full_boundary(x):
        for tee in x['generated']['catalogue']['tee_instances']:
            tee['loss_contract_root']=digest({'model':'oma.coupled-tree-boundary/1','tee_id':tee['id'],
                'outlet_coefficients':b(x)['tee_outlet_loss_coefficients'][tee['id']]})
    attack('loss_root_omits_complete_boundary',unbound_full_boundary)
    def wrong_side(x):
        tee=x['generated']['catalogue']['tee_instances'][0];bb=deepcopy(x['generated']['normalized_requirements']['coupled_tree'])
        coefficients=bb['tee_outlet_loss_coefficients'][tee['id']]
        coefficients['b'],coefficients['branch']=coefficients['branch'],coefficients['b']
        tee['loss_contract_root']=digest({'model':'oma.coupled-tree-boundary/1','tee_id':tee['id'],'outlet_coefficients':coefficients,'boundary_root':digest(bb)})
    attack('coherent_hash_outlet_coefficients_swapped',wrong_side)
    x=deepcopy(base)
    def mutation(stage):
        if stage=='shared_tree_catalogue_check_complete':b(x)['flow_search_box_m3_s']['sink-a']['upper']='1/50'
    answer=verify(x,checkpoint=mutation);assert answer['status']=='FAIL' and not answer['proof_complete']
    cases.append({'name':'last_callback_flow_box_mutation','result':answer})
    exact=verify(base,max_work=positive['work']);small=verify(base,max_work=positive['work']-1)
    assert exact['status']=='PASS' and small['status']=='UNKNOWN'
    src=Path(os.environ['PYTHONPATH']);dependency_files={p.relative_to(src).as_posix():sha(p) for p in src.rglob('*.py')}
    result={'status':'PASS','module_sha256':sha(MODULE),'dependency_source':str(src),'dependency_files':dependency_files,
        'input_files':{p.name:sha(p) for p in AUTH.glob('*.json')},'actual_authored_packet_check':positive,'adversarial_cases':cases,
        'exact_work_passes':exact['status'],'one_less_work':small,'elapsed_seconds':time.monotonic()-started,
        'scope':'Fixed tee identity and exact coupled boundary provenance only; independent nominal fabrication replay. No native feasibility, pressure solve, service, complete templates or acceptance claim.'}
    assert result['module_sha256']=='c800938e03909fcbe8a014e21b46c9640ddf5736fe3684f345bdd57a5bfb7fd4'
    write(out/'result.json',result)
    (out/'README.md').write_text('Independent coupled checker review PASS on the actual predeclared root packet, with fourteen malformed/stale/coherently rehashed identity and callback attacks rejected. Exact work budget passes; one less returns UNKNOWN. Fixed tee IDs/count, sink identities, prohibition of old fixed-flow/static requirements, complete boundary and per-outlet loss roots were checked. The verifier never called producer code, native CAD, pressure evaluation or acceptance.\n',encoding='utf8')
    files={p.relative_to(out).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in out.rglob('*') if p.is_file()}
    write(out/'files.json',{'files':files})
    print(json.dumps({'status':'PASS','evidence':str(out),'attacks':len(cases),'elapsed_seconds':result['elapsed_seconds']}))

if __name__=='__main__':main()
