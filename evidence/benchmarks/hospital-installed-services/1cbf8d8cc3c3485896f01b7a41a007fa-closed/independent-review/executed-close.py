"""Bind closed independent graph audit to original Store and child completion."""
from pathlib import Path
import hashlib,json,shutil,sqlite3,uuid,zlib
ROOT=Path(__file__).resolve().parents[3];STAGE=Path(__file__).resolve().parent
AUDIT=STAGE/'campaign-peer/2646246da3a8472e914372e2ab604100'
CAMPAIGN=ROOT/'.oma/development/building-services-20260915/campaigns/1cbf8d8cc3c3485896f01b7a41a007fa'
OLD=ROOT/'.oma/development/hospital-generated-tree/stores/6f55c59953f5457daba32dc8223101b2'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def dump(p,v):Path(p).write_text(json.dumps(v,indent=2),encoding='utf-8')
out=STAGE/'completed-reviews'/uuid.uuid4().hex;out.mkdir(parents=True)
shutil.copyfile(__file__,out/'executed-close.py')
hand=load(AUDIT/'handoff.json');bound={}
for name,row in hand['retained_files'].items():
    original=AUDIT/name;assert sha(original)==row['sha256']
    target=out/'graph-audit'/name;target.parent.mkdir(exist_ok=True)
    shutil.copyfile(original,target);assert sha(target)==sha(original)
assert sha(AUDIT/'result.json')==hand['result_sha256']=='9e0e90e2efce002ddb60f85fce0b4eb73055c66198f12b58257009754ab7d340'
for p,h in load(AUDIT/'inputs.json').items():assert sha(p)==h
result=load(CAMPAIGN/'result.json');decl=load(CAMPAIGN/'predeclaration.json')
execution=load(CAMPAIGN/'supervision/check.json')
assert execution==result['execution'] and execution['status']=='COMPLETED' and execution['returncode']==0
expected=[str(ROOT/'.venv/Scripts/python.exe'),'-m','oma.worker',result['store'],result['run_id']]
assert execution['command']==expected
assert execution['launched_command'][1:]==expected[1:]
assert execution['checker_version']==decl['checker_version']
assert execution['interpreter']['frozen_pythonpath_retained']==decl['source_path']
assert execution['containment']['active_processes']==0
assert execution['containment']['assigned_before_resume'] is True
assert execution['containment']['completion_authority']=='KERNEL_JOB_ACTIVE_PROCESSES_ZERO'
for stream in ('stdout','stderr'):
    row=execution[stream];p=Path(row['path'])
    assert p.stat().st_size==row['retained_bytes']==row['total_bytes'] and row['truncated'] is False
    assert sha(p)==row['sha256_of_observed_stream']
    target=out/(stream+'.log');shutil.copyfile(p,target);assert sha(target)==sha(p)
for name in ('result.json','predeclaration.json','supervision/check.json','executed.py'):
    p=CAMPAIGN/name;bound[str(p)]=sha(p);target=out/'campaign-bindings'/name
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target);assert sha(target)==sha(p)
db=sqlite3.connect((OLD/'oma.sqlite3').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
oldrow=dict(db.execute('SELECT * FROM projects WHERE id=?',(decl['original_project']['id'],)).fetchone())
assert oldrow==decl['original_project']
def blob(directory,root):
    p=directory/'blobs'/(root+'.json.z');bound[str(p)]=sha(p);raw=zlib.decompress(p.read_bytes())
    assert hashlib.sha256(raw).hexdigest()==root
    return json.loads(raw)
oldstate=blob(OLD,oldrow['state_root'])
newstate=blob(Path(result['store']),decl['new_project']['state_root'])
assert {k:v for k,v in oldstate.items() if k!='project_id'}=={k:v for k,v in newstate.items() if k!='project_id'}
assert oldrow==dict(db.execute('SELECT * FROM projects WHERE id=?',(oldrow['id'],)).fetchone())
assert all(sha(p)==h for p,h in bound.items())
audit=load(AUDIT/'result.json')
totals={key:sum(s['summary'][key] for s in audit['summaries']) for key in ('source_product_count','source_port_count','source_explicit_connection_count','source_system_count','service_product_count','network_count','portless_service_product_count')}
dump(out/'bindings.json',bound)
dump(out/'result.json',{'status':'CLOSED_INDEPENDENT_HOSPITAL_ALL_SERVICE_REVIEW_PASS','graph_audit_sha256':sha(AUDIT/'result.json'),'campaign_result_sha256':sha(CAMPAIGN/'result.json'),'predeclaration_sha256':sha(CAMPAIGN/'predeclaration.json'),'checker_version':decl['checker_version'],'supervision_sha256':sha(CAMPAIGN/'supervision/check.json'),'observed_child_returncode':execution['returncode'],'command_and_frozen_source_binding_verified':True,'old_project_unchanged':True,'new_project_state_is_original_except_project_id':True,'new_project_revisions':1,'new_candidates':0,'source_count':7,'totals':totals,'summaries':audit['summaries'],'engineering_result':'MISSING_DESIGN_CONTRACT_FOR_EVERY_COMPONENT','native_geometry_rerun':False,'full_building_optimization_or_code_approval':False,'all_bound_inputs_unchanged':True,'scope':'Independent complete explicit topology and original source/Store/app/request/completed child bindings. Components are product/port ownership incidence components; internal device circuits and engineering source/sink duties are not inferred.'})
files={p.relative_to(out).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in out.rglob('*') if p.is_file()}
dump(out/'handoff.json',{'schema':'oma.independent-hospital-installed-service-review/1','status':'CLOSED','retained_files':files,'result_sha256':sha(out/'result.json')})
print(json.dumps({'directory':str(out),'result_sha256':sha(out/'result.json'),'handoff_sha256':sha(out/'handoff.json'),'totals':totals}),flush=True)
