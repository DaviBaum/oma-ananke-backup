"""Independent bounded read-only producer diff/control/identity review; no CAD."""
from pathlib import Path
import copy,difflib,hashlib,importlib.util,json,sys,time,uuid

STAGE=Path(__file__).resolve().parents[1];ROOT=STAGE.parents[2]
CURRENT=ROOT/'.oma/development/shared-tree-coupled/src'
BASE=ROOT/'.oma/development/shared-tree-native/runtimes/b9652e8e197783facaa03d3e837d67962bb9a60388783b345180833d19402cc1/src'
OUT=STAGE/'evidence/producer-independent-review'/uuid.uuid4().hex;OUT.mkdir(parents=True)
def sha(data):return hashlib.sha256(data).hexdigest()
def digest(value):return sha(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode())
def dump(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
records=[]
for path in sorted(CURRENT.rglob('*.py')):
 data=path.read_bytes();relative=path.relative_to(CURRENT);target=OUT/'src'/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
 records.append({'path':relative.as_posix(),'sha256':sha(data)})
relative='oma/routing/shared_tree_proposals.py';current=OUT/'src'/relative;old=BASE/relative
(OUT/'base-b965-producer.py').write_bytes(old.read_bytes())
(OUT/'executed.py').write_bytes(Path(__file__).read_bytes())
diff=''.join(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),current.read_text(encoding='utf-8').splitlines(True),fromfile='b965/shared_tree_proposals.py',tofile='reviewed/shared_tree_proposals.py'))
(OUT/'producer.diff').write_text(diff,encoding='utf-8')
sys.path.insert(0,str(OUT/'src'))
from oma.routing import shared_tree_proposals as producer
from oma.routing.network_scenario import SharedNetworkScenario,network_fixed_requirements
def load(path,name):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
baseline=load(OUT/'base-b965-producer.py','baseline_producer')
fixture=STAGE/'tests/fixtures/shared-tree-coupled-check/authored-3'
original=tuple(json.loads((fixture/(key+'.json')).read_text(encoding='utf-8')) for key in ('requirements','search','context'))
dump(OUT/'original-inputs.json',dict(zip(('requirements','search','context'),original)))
start=time.monotonic();checks=[]
def record(name,condition,detail=None):
 assert condition,(name,detail)
 checks.append({'name':name,'status':'PASS','detail':detail})
r,s,c=copy.deepcopy(original);before=digest([r,s,c])
out=producer.compile_shared_tree_proposals(r,s,context=c)
record('actual authored pressure request generates checked nominal proposals',out['status']=='PROPOSALS_READY',out.get('reason'))
record('caller inputs unchanged',digest([r,s,c])==before)
mission=SharedNetworkScenario.model_validate(out['mission'])
fixed=network_fixed_requirements(mission,'resolved-source')
normalized=out['generation']['normalized_requirements']
record('full canonical coupled boundary unchanged',fixed['coupled_tree']==normalized['coupled_tree'])
record('all fixed exact sink records unchanged',fixed['sinks']==normalized['sinks'])
for key in ('start_m','diameter_m','insulation_m','clearance_m','minimum_straight_m','minimum_bend_radius_m','allowed_zone','system_type','target_modality','source_representation_policy','objective_weights','assumptions'):
 record('fixed requirement preserved: '+key,fixed[key]==normalized[key])
for tee in out['generation']['catalogue']['tee_instances']:
 b=normalized['coupled_tree'];expected={'model':'oma.coupled-tree-boundary/1','tee_id':tee['id'],'outlet_coefficients':b['tee_outlet_loss_coefficients'][tee['id']],'boundary_root':digest(b)}
 record('current named tee coefficient binding: '+tee['id'],tee['loss_contract_root']==digest(expected))
record('all generated complete trees retain exact fixed tee set',all({x.id for x in n.components if x.kind=='tee'}==set(normalized['coupled_tree']['tee_outlet_loss_coefficients']) for n in mission.network_alternatives))
record('nominal proof scopes preserved',out['catalogue_check']['status']=='PASS' and out['independent_check']['status']=='PASS' and not out['limitations']['candidate_acceptance_authority'])
dump(OUT/'nominal-result.json',out)
fixed_dir=STAGE/'tests/fixtures/shared-tree-catalogue-check'
fixed_inputs=tuple(json.loads((fixed_dir/(key+'.json')).read_text(encoding='utf-8')) for key in ('requirements','search','context'))
rr,ss,cc=copy.deepcopy(fixed_inputs)
new_fixed=producer.compile_shared_tree_proposals(rr,ss,context=cc)
old_fixed=baseline.compile_shared_tree_proposals(rr,ss,context=cc)
record('legacy nominal complete result byte identity',new_fixed==old_fixed)
record('old profile remains explicitly unsupported in b965',baseline.build_connector_catalogue(*copy.deepcopy(original[:2]),context=copy.deepcopy(original[2]))['status']=='UNKNOWN')
for mutation in ('missing_key','extra_key','wrong_site_id','duplicate_site','legacy_flow','legacy_static','physics','wrong_mode'):
 rr,ss,cc=copy.deepcopy(original);b=rr['coupled_tree']
 if mutation=='missing_key':b['tee_outlet_loss_coefficients'].pop('tee-c')
 elif mutation=='extra_key':b['tee_outlet_loss_coefficients']['extra']={'b':'1','branch':'1'}
 elif mutation=='wrong_site_id':ss['tee_instances'][0]['id']='renamed'
 elif mutation=='duplicate_site':ss['tee_instances'][1]=copy.deepcopy(ss['tee_instances'][0])
 elif mutation=='legacy_flow':rr['sinks'][0]['required_flow_m3_s']=.001
 elif mutation=='legacy_static':rr['sinks'][0]['available_static_pressure_pa']=100
 elif mutation=='physics':rr['physics']=fixed_inputs[0]['physics']
 elif mutation=='wrong_mode':rr['target_modality']='LOCAL_GEOMETRIC_COORDINATION'
 answer=producer.build_connector_catalogue(rr,ss,context=cc)
 record('invalid fixed pressure profile rejects: '+mutation,answer['status']=='INVALID_INPUT',answer.get('reason'))
work=out['work']
equal=producer.compile_shared_tree_proposals(*copy.deepcopy(original[:2]),context=copy.deepcopy(original[2]),max_work=work)
record('exact full reported work succeeds',equal['status']=='PROPOSALS_READY' and equal['work']==work)
low=producer.compile_shared_tree_proposals(*copy.deepcopy(original[:2]),context=copy.deepcopy(original[2]),max_work=work-1)
record('one-less work publishes no proposal',low['status']=='UNKNOWN' and low.get('mission') is None,low)
for target in ('pressure','coefficient','context'):
 rr,ss,cc=copy.deepcopy(original);seen=[]
 def callback(stage):
  if seen:raise AssertionError('Unexpected callback after final binding pulse')
  if stage=='shared_tree_proposal_complete':
   seen.append(stage)
   if target=='pressure':rr['coupled_tree']['source_total_pressure_pa']['upper']='999'
   elif target=='coefficient':rr['coupled_tree']['tee_outlet_loss_coefficients']['tee-a']['b']='1'
   else:cc['changed_context']=True
 answer=producer.compile_shared_tree_proposals(rr,ss,context=cc,checkpoint=callback)
 record('final caller mutation rejects: '+target,bool(seen) and answer['status']=='INVALID_INPUT' and answer.get('mission') is None,answer.get('reason'))
for error in (TimeoutError('review timeout'),ValueError('review caller value'),producer._Unavailable('review caller unavailable')):
 rr,ss,cc=copy.deepcopy(original);raw=digest([rr,ss,cc])
 def callback(stage):raise error
 caught=None
 try:producer.compile_shared_tree_proposals(rr,ss,context=cc,checkpoint=callback)
 except BaseException as exc:caught=exc
 record('caller exception identity: '+type(error).__name__,caught is error and digest([rr,ss,cc])==raw)
unchanged=all(sha((OUT/'src'/row['path']).read_bytes())==row['sha256'] for row in records)
current_unchanged=all(sha((CURRENT/row['path']).read_bytes())==row['sha256'] for row in records)
result={'schema':'oma.coupled-producer-independent-review/1','status':'PASS','source_files':records,
 'producer_sha256':sha(current.read_bytes()),'base_producer_sha256':sha(old.read_bytes()),
 'checks':checks,'checks_count':len(checks),'elapsed_seconds':time.monotonic()-start,
 'snapshot_unchanged':unchanged,'reviewed_current_source_unchanged':current_unchanged,
 'nominal_proposals':len(out['mission']['network_alternatives']),'reported_work':work,
 'scope':'Read-only producer diff and bounded nominal identity/control review. No CAD/pressure/native/Store action; no physical feasibility or pressure acceptance claim.'}
assert unchanged and current_unchanged
dump(OUT/'result.json',result)
print(json.dumps({'path':str(OUT/'result.json'),'sha256':sha((OUT/'result.json').read_bytes()),'checks':len(checks),'source_sha256':result['producer_sha256']}))
