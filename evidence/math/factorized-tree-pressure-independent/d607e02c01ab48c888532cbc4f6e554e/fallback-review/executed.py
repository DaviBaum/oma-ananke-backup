"""Narrow composition/remaining-budget dispatch audit on retained native5 inputs."""
from pathlib import Path
import copy,hashlib,json,shutil,sys,uuid
STAGE=Path(__file__).resolve().parent
ROOT=next(p for p in STAGE.parents if (p/'AGENTS.md').exists())
SOURCE=ROOT/'.oma/development/factorized-tree-pressure/runtimes/73d7eed7accfd706f9972e1548e750009127e24c6106cc25d98c812239a836ee/src'
INPUT=STAGE/'native-replays/7b7374e18b4c4d1c8352b890e011251d'
sys.path.insert(0,str(SOURCE))
from oma.routing import coupled_tree_pressure as a
def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf8')
out=STAGE/'fallback-gates'/uuid.uuid4().hex;out.mkdir(parents=True);shutil.copyfile(__file__,out/'executed.py')
selected=INPUT/'candidates/9246175acf184b3a93b19bf3f27e37a8'
generated=read(INPUT/'generation.json');boundary=generated['authored_query']['requirements']['coupled_tree']
material=read(selected/'materialization.json');network=copy.deepcopy(material['network_spec']);network.pop('source_to_federation_matrix')
metrics=read(selected/'metrics.json');context=read(selected/'replay-context.json');packet=read(selected/'calculation.json')['certificate']
trace=[];results=[];source_before=sha(Path(a.__file__))
def global_producer(model,**kwargs):
    trace.append(('global',kwargs['max_work'],digest(model)));kwargs['checkpoint']('independent_global_stub');return copy.deepcopy(packet['univalence_certificate'])
a.global_proof.compile_coupled_tree_univalence=global_producer
for status,reason in [('UNKNOWN','WORK_BUDGET'),('UNKNOWN','RATIONAL_BIT_BUDGET'),('UNKNOWN','CERTIFICATE_BYTE_BUDGET'),
    ('UNKNOWN','INPUT_BYTE_BUDGET'),('UNKNOWN','UNRECOGNIZED_REASON'),('INVALID_INPUT','malformed'),('FAIL','forged')]:
    trace.clear()
    def old_local(model,box,**kwargs):
        trace.append(('legacy',kwargs['max_work'],digest(model),digest(box)));kwargs['checkpoint']('independent_legacy_stub');return {'status':status,'reason':reason,'work':1}
    a.local.compile_coupled_tree_pressure=old_local
    def forbidden(*args,**kwargs):raise AssertionError('Fallback invoked for resource/invalid/unrecognized outcome')
    a.factorized.compile_factorized_tree_pressure=forbidden
    result=a.evaluate_coupled_tree(boundary,network,metrics,context=context)
    assert result['status']=='UNKNOWN' and result['proof_complete'] is False
    assert [x[0] for x in trace]==['global','legacy'] and trace[1][1]<trace[0][1]
    results.append({'case':status+':'+reason,'status':result['status'],'fallback_called':False,'remaining_work':[x[1] for x in trace]})
for reason in ('STRICT_BOX_INCLUSION_NOT_ESTABLISHED','CONTRACTION_NOT_ESTABLISHED'):
    trace.clear()
    def old_local(model,box,**kwargs):
        trace.append(('legacy',kwargs['max_work'],digest(model),digest(box)));kwargs['checkpoint']('independent_legacy_stub');return {'status':'UNKNOWN','reason':reason,'work':1}
    def new_local(model,box,**kwargs):
        trace.append(('factorized',kwargs['max_work'],digest(model),digest(box)));kwargs['checkpoint']('independent_factorized_stub');return copy.deepcopy(packet['local_certificate'])
    a.local.compile_coupled_tree_pressure=old_local;a.factorized.compile_factorized_tree_pressure=new_local
    result=a.evaluate_coupled_tree(boundary,network,metrics,context=context)
    assert result['status']=='CERTIFIED_ENVELOPE' and result['verdict']=='PASS'
    assert trace[1][2:]==trace[2][2:] and trace[2][1]<trace[1][1]<trace[0][1]
    assert result['certificate']['model']==packet['model'] and result['certificate']['flow_box']==packet['flow_box']
    assert result['independent_check']['local_check']['status']==result['independent_check']['global_check']['status']=='PASS'
    results.append({'case':reason,'status':result['status'],'identical_model_and_box':True,'remaining_work':[x[1] for x in trace],
        'independent_local_and_global_required':True})
assert sha(Path(a.__file__))==source_before
result={'status':'FALLBACK_IDENTITY_RESOURCE_AND_UNKNOWN_GATES_PASS','checks':len(results),'results':results,
    'adapter_source_sha256':source_before,'script_sha256':sha(out/'executed.py'),
    'test_scope':'Controlled producer-return stubs against actual saved native inputs. Actual independent proof consumers run on unmodified certificates. No new native or acceptance claim.'}
dump(out/'result.json',result);print(json.dumps({'out':str(out),'status':result['status'],'checks':len(results)}))
