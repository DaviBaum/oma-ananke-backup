"""Independent final callback/producer alias attacks against the corrected adapter."""
from pathlib import Path
import copy,hashlib,json,shutil,sys,time,uuid
STAGE=Path(__file__).resolve().parent;ROOT=next(p for p in STAGE.parents if (p/'AGENTS.md').exists())
FROZEN=ROOT/'.oma/development/factorized-tree-pressure/native-model-probes/4623a210ad0447ddaeda012624a080d0'
sys.path.insert(0,str(FROZEN/'src'))
from oma.routing import coupled_tree_pressure as a
def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf8')
out=STAGE/'final-packet-guard'/uuid.uuid4().hex;out.mkdir(parents=True);shutil.copyfile(__file__,out/'executed.py')
source_files={p.relative_to(FROZEN/'src').as_posix():sha(p) for p in (FROZEN/'src').rglob('*.py')}
write(out/'source-files.json',source_files)
normal=[];started=time.perf_counter()
for count in (7,8):
    path=FROZEN/str(count);values=[read(path/(name+'.json')) for name in ('boundary','network','metrics','context')]
    got=a.evaluate_coupled_tree(*values[:3],context=values[3]);assert got['status']=='CERTIFIED_ENVELOPE' and got['verdict']=='PASS'
    old=read(path/'envelope.json');assert got['certificate']==old['certificate']
    assert got['work']<=2_000_000
    write(out/f'normal-{count}.json',got)
    normal.append({'sinks':count,'status':got['status'],'work':got['work'],'certificate_unchanged':True})
    if count==8:
        exact=a.evaluate_coupled_tree(*values[:3],context=values[3],max_work=got['work'])
        short=a.evaluate_coupled_tree(*values[:3],context=values[3],max_work=got['work']-1)
        assert exact['status']=='CERTIFIED_ENVELOPE' and short['status']=='UNKNOWN'
        write(out/'one-less-work.json',short)
path=FROZEN/'7';base_values=[read(path/(name+'.json')) for name in ('boundary','network','metrics','context')]
packet=read(path/'envelope.json')['certificate']
functions={'global':a.global_proof.compile_coupled_tree_univalence,'local':a.local.compile_coupled_tree_pressure,
    'factor':a.factorized.compile_factorized_tree_pressure,'service':a._service_from_enclosure,'verify':a.verify_coupled_tree_envelope}
attacks=[]
for mode in ('local_packet','global_packet','service_packet','held_consumer_result','caller_context','exception','oversized_late_packet'):
    values=copy.deepcopy(base_values);held={};fired=[]
    def global_producer(m,**kw):
        held['global']=copy.deepcopy(packet['univalence_certificate']);return held['global']
    def local_producer(*args,**kw):return {'status':'UNKNOWN','reason':'STRICT_BOX_INCLUSION_NOT_ESTABLISHED','work':0}
    def factor_producer(m,b,**kw):
        assert m==packet['model'] and b==packet['flow_box'];held['local']=copy.deepcopy(packet['local_certificate']);return held['local']
    service_calls=[]
    def service(*args,**kw):
        result=functions['service'](*args,**kw);service_calls.append(1)
        if len(service_calls)==1:held['service']=result
        return result
    def verify(*args,**kw):
        result=functions['verify'](*args,**kw);held['consumer']=result;return result
    a.global_proof.compile_coupled_tree_univalence=global_producer;a.local.compile_coupled_tree_pressure=local_producer
    a.factorized.compile_factorized_tree_pressure=factor_producer;a._service_from_enclosure=service;a.verify_coupled_tree_envelope=verify
    error=RuntimeError('independent final forced cancellation')
    def checkpoint(stage):
        if stage!='coupled_tree_producer_complete':return
        fired.append(stage)
        if mode=='local_packet':held['local']['contraction_norm_upper']='0'
        elif mode=='global_packet':held['global']['model_root']='0'*64
        elif mode=='service_packet':held['service']['deliveries'].pop()
        elif mode=='held_consumer_result':held['consumer']['service']['deliveries'].clear();held['consumer']['full_certificate_root']='0'*64
        elif mode=='caller_context':values[3]['independent_late_mutation']=True
        elif mode=='oversized_late_packet':held['local']['late_payload']='X'*10000
        else:raise error
    try:got=a.evaluate_coupled_tree(*values[:3],context=values[3],checkpoint=checkpoint)
    except RuntimeError as caught:
        assert mode=='exception' and caught is error;got={'status':'CALLER_EXCEPTION_IDENTITY_PRESERVED','proof_complete':False}
    assert len(fired)==1
    if mode=='held_consumer_result':
        assert got['status']=='CERTIFIED_ENVELOPE' and len(got['service']['deliveries'])==7
        assert got['service']==packet['service']
    else:assert got['status']!='CERTIFIED_ENVELOPE' and got.get('proof_complete') is False
    write(out/(mode+'.json'),got);attacks.append({'mode':mode,'status':got['status'],'reason':got.get('reason'),'service_calls':len(service_calls)})
a.global_proof.compile_coupled_tree_univalence=functions['global'];a.local.compile_coupled_tree_pressure=functions['local']
a.factorized.compile_factorized_tree_pressure=functions['factor'];a._service_from_enclosure=functions['service'];a.verify_coupled_tree_envelope=functions['verify']
def forbidden(*args,**kw):raise AssertionError('No producer authority during independent check')
a.global_proof.compile_coupled_tree_univalence=a.local.compile_coupled_tree_pressure=a.factorized.compile_factorized_tree_pressure=forbidden
fresh=a.verify_coupled_tree_envelope(*base_values[:3],packet,context=base_values[3]);assert fresh['status']==fresh['verdict']=='PASS'
write(out/'producer-disabled-check.json',fresh)
assert source_files=={p.relative_to(FROZEN/'src').as_posix():sha(p) for p in (FROZEN/'src').rglob('*.py')}
result={'status':'FINAL_PACKET_GUARD_AND_DETACHED_CONSUMER_REVIEW_PASS','source':str(FROZEN/'src'),
    'adapter_sha256':source_files['oma/routing/coupled_tree_pressure.py'],'normal':normal,'attacks':attacks,
    'producer_disabled_verification':fresh['status'],'eight_exact_work_budget':'CERTIFIED_ENVELOPE','eight_one_less_work_budget':'UNKNOWN',
    'native_geometry_rerun':False,'source_and_original_inputs_changed':False,'seconds':time.perf_counter()-started}
write(out/'result.json',result);print(json.dumps({'directory':str(out),**result},indent=2))
