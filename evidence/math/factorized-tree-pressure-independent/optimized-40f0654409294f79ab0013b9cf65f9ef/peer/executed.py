"""Exact old/new proof equivalence and untrusted service-proposal consumer gates."""
from pathlib import Path
import copy,hashlib,importlib,json,shutil,sys,types,uuid
STAGE=Path(__file__).resolve().parent
ROOT=next(p for p in STAGE.parents if (p/'AGENTS.md').exists())
OLD=ROOT/'.oma/development/factorized-tree-pressure/probes/78236775b4134a4aaa0374e84288b155/src'
NEW=ROOT/'.oma/development/factorized-tree-pressure/native-model-probes/cc7cfcc9e3af4db3bf6c6165d64eb978'
def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def digest(v):return hashlib.sha256(canonical(v)).hexdigest()
def reseal(c):c['certificate_root']=digest({k:v for k,v in c.items() if k!='certificate_root'})
def dump(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf8')
for alias,source in [('oldmath',OLD),('newmath',NEW/'src')]:
    package=types.ModuleType(alias);package.__path__=[str(source/'oma')];sys.modules[alias]=package
old=importlib.import_module('oldmath.optimization.factorized_tree_pressure')
new=importlib.import_module('newmath.optimization.factorized_tree_pressure')
out=STAGE/'optimized-delta'/uuid.uuid4().hex;out.mkdir(parents=True);shutil.copyfile(__file__,out/'executed.py')
source_paths=[Path(old.__file__),Path(new.__file__),NEW/'src/oma/routing/coupled_tree_pressure.py']
source_hashes={str(p):sha(p) for p in source_paths};assert sha(Path(old.__file__))=='bc37fb0dc97c453eb2337fc5be31ea581029565cb9801d048e5cefb6f18614bf'
results=[]
for count in (5,7,8):
    folder=(ROOT/'.oma/development/factorized-tree-pressure/tests/fixtures/five-native') if count==5 else NEW/str(count)
    model=read(folder/'model.json');box=read(folder/('original-box.json' if count==5 else 'box.json'))
    first=old.compile_factorized_tree_pressure(model,box);second=new.compile_factorized_tree_pressure(model,box)
    assert first['status']==second['status']=='CERTIFIED_BOX';assert canonical(first)==canonical(second)
    checked=new.verify_factorized_tree_pressure(model,box,first);assert checked['status']=='PASS'
    dest=out/str(count);dest.mkdir();dump(dest/'old-and-new-identical-certificate.json',first);dump(dest/'new-consumer.json',checked)
    results.append({'sinks':count,'old_new_certificate_bytes_identical':True,'certificate_root':first['certificate_root'],
        'new_independent_status':checked['status'],'work':checked['work']})
sys.path.insert(0,str(NEW/'src'))
from oma.routing import coupled_tree_pressure as a
data=NEW/'8';boundary=read(data/'boundary.json');network=read(data/'network.json');metrics=read(data/'metrics.json');context=read(data/'context.json')
packet=read(data/'envelope.json')['certificate'];model=packet['model'];box=packet['flow_box']
originals={name:getattr(a,name) for name in ('evaluate_coupled_tree','_service_from_enclosure')}
old_global=a.global_proof.compile_coupled_tree_univalence;old_local=a.local.compile_coupled_tree_pressure;old_factor=a.factorized.compile_factorized_tree_pressure
def forbidden(*args,**kwargs):raise AssertionError('Producer invoked during independent consumer replay')
a.evaluate_coupled_tree=a.local.compile_coupled_tree_pressure=a.global_proof.compile_coupled_tree_univalence=a.factorized.compile_factorized_tree_pressure=forbidden
genuine=a.verify_coupled_tree_envelope(boundary,network,metrics,packet,context=context)
assert genuine['status']==genuine['verdict']==genuine['local_check']['status']==genuine['global_check']['status']=='PASS'
assert genuine['service']==packet['service']
exact=a.verify_coupled_tree_envelope(boundary,network,metrics,packet,context=context,max_work=genuine['work'])
short=a.verify_coupled_tree_envelope(boundary,network,metrics,packet,context=context,max_work=genuine['work']-1)
assert exact['status']=='PASS' and short['status']=='UNKNOWN'
dump(out/'eight-consumer.json',genuine)
attacks=[]
a.evaluate_coupled_tree=originals['evaluate_coupled_tree']
def global_producer(m,**kwargs):return copy.deepcopy(packet['univalence_certificate'])
def local_inclusion_failure(m,b,**kwargs):return {'status':'UNKNOWN','reason':'STRICT_BOX_INCLUSION_NOT_ESTABLISHED','work':0}
def factorized_producer(m,b,**kwargs):
    assert m==model and b==box;return copy.deepcopy(packet['local_certificate'])
a.global_proof.compile_coupled_tree_univalence=global_producer;a.local.compile_coupled_tree_pressure=local_inclusion_failure;a.factorized.compile_factorized_tree_pressure=factorized_producer
for mode in ('wrong_service_only_on_first_proposal','forged_local_polynomial','forged_global_proof'):
    a._service_from_enclosure=originals['_service_from_enclosure'];a.factorized.compile_factorized_tree_pressure=factorized_producer;a.global_proof.compile_coupled_tree_univalence=global_producer
    calls=[]
    if mode=='wrong_service_only_on_first_proposal':
        def service(*args,**kwargs):
            result=originals['_service_from_enclosure'](*args,**kwargs);calls.append(1)
            if len(calls)==1:result['deliveries'].pop()
            return result
        a._service_from_enclosure=service
    elif mode=='forged_local_polynomial':
        def fake_factor(*args,**kwargs):
            c=factorized_producer(*args,**kwargs);c['preconditioned_polynomial'][0]['weight']='0';reseal(c);return c
        a.factorized.compile_factorized_tree_pressure=fake_factor
    else:
        def fake_global(*args,**kwargs):
            c=global_producer(*args,**kwargs);c['model_root']='0'*64;reseal(c);return c
        a.global_proof.compile_coupled_tree_univalence=fake_global
    result=a.evaluate_coupled_tree(boundary,network,metrics,context=context)
    assert result['status']!='CERTIFIED_ENVELOPE' and result['proof_complete'] is False
    if mode=='wrong_service_only_on_first_proposal':assert len(calls)==2
    dump(out/(mode+'.json'),result);attacks.append({'mode':mode,'status':result['status'],'reason':result.get('reason'),'service_helper_calls':len(calls)})
assert all(sha(p)==source_hashes[str(p)] for p in source_paths)
result={'status':'OPTIMIZED_PROOF_EQUIVALENCE_AND_FINAL_CONSUMER_GATES_PASS','source_hashes':source_hashes,
    'certificate_equivalence':results,'eight_consumer_producer_disabled':genuine['status'],
    'eight_consumer_work':genuine['work'],'same_exact_work_budget_status':exact['status'],'one_less_work_status':short['status'],
    'untrusted_proposal_attacks':attacks,'source_or_physical_input_changes':False,'native_geometry_rerun':False,
    'scope':'Exact same pure certificates on original5/7/8 models and boxes;8-sink complete metric/physics proof consumer replay. Native authority remains in original retained reports.'}
dump(out/'result.json',result);print(json.dumps({'out':str(out),**result},indent=2))
