"""Summarize completed immutable hospital receipts; no geometry regeneration."""
import json,gzip,hashlib,uuid,shutil
from pathlib import Path
from oma.store import Store
from oma.ifc.audit import atomic_json,sha256_file
STAGE=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
full=read(STAGE/'campaigns/f07c0723bf8b47f880a5cda57a8b01b0/result.json')
arc=read(STAGE/'campaigns/eac181c60f1748f4841b0796dfd69e00/result.json')
assert full['status']=='GENERATION_BLOCKED' and full['generation_run']['status']=='MISSING_INPUTS'
assert arc['status']!='RUNNING'
closure_path=STAGE/'completion/42ec2d9c4a5c4fe6ae3ee80d7953d62c/result.json'
closure=read(closure_path)
assert closure['status']=='OWNED_TIMEOUT_CLOSED_WITHOUT_REPORT'
partial=read(STAGE/'observations/575e90919b244331846ba216598c35d5/result.json')
out=STAGE/'report'/uuid.uuid4().hex;out.mkdir(parents=True);shutil.copyfile(__file__,out/'executed.py')
full_store=Store(full['store']);arc_store=Store(arc['store'])
assert full_store.project(full['project_id'])==read(STAGE/'campaigns/f07c0723bf8b47f880a5cda57a8b01b0/predeclaration.json')['project_before']
assert not full_store.candidates(full['project_id'])
native=[]
for row in [*arc.get('candidates',[]),*([arc['exported_candidate']] if arc.get('exported_candidate') else [])]:
    folder=STAGE/'campaigns/eac181c60f1748f4841b0796dfd69e00/candidates'/row['id']
    sem_path=folder/'network-native-semantics.json.gz'
    sem=json.loads(gzip.decompress(sem_path.read_bytes())) if sem_path.exists() else {}
    cad_path=folder/'network-all-source-clearance.json.gz'
    cad=json.loads(gzip.decompress(cad_path.read_bytes())) if cad_path.exists() else {}
    native.append({**row,'original_parsed_records_checked':sem.get('original_records_checked'),'native_semantics_status':sem.get('status'),
        'native_semantics_errors':sem.get('errors'),'represented_support_enclosures':cad.get('represented_support_enclosures'),
        'missing_geometry':cad.get('missing_geometry'),'native_coordinate_status':cad.get('coordinate_status'),
        'native_performance':cad.get('performance'),'native_proof_level':cad.get('proof_level'),
        'preservation_scope':'Canonical parsed source entity strings at every original STEP ID plus protected inverse-relationship checks, not byte-identical serializer spelling'})
assert arc_store.candidate(closure['candidate_after']['id'])==closure['candidate_after']
assert arc_store.run(closure['run_after']['id'])==closure['run_after']
assert arc_store.project(arc['project_id'])==arc['project_after']
original=read(STAGE/'attempts/6f55c59953f5457daba32dc8223101b2/predeclaration.json')
assert all(sha256_file(Path(s['path']))==s['sha256'] for s in original['inputs'])
result={'schema':'oma.hospital-generated-tree-report/1','checker_version':original['checker_version'],
    'hospital':'West Riverside Hospital IFC4','original_sources':original['inputs'],'all_seven_originals_unchanged':True,
    'complete_federation':{'sources':7,'import_elapsed_seconds':279.593,'product_records':149822,'ports':85602,'explicit_connections':42801,
        'alignment':'UNRESOLVED','generation_status':'MISSING_INPUTS','generation_seconds':full['elapsed_seconds'],
        'reason':full['reason'],'candidate_count':0,'accepted':False,'native_route_or_export_checked':False},
    'architecture_only':{'scope':'Separate hypothetical mission; all architectural obstacles, excluding six disciplines explicitly outside this second scope',
        'import_elapsed_seconds':19.938,'product_records':15316,'original_terminal_ports':0,
        'scenario':'Two simultaneous 0.5 L/s hypothetical deliveries; 100 Pa static boundary; finite two tee sites and connector templates',
        'campaign_status':arc['status'],'campaign_seconds':arc['elapsed_seconds'],'proposal_count':arc.get('proposal_count'),
        'selected_candidate':None,'accepted':False,'exported':False,'candidates_and_fresh_export':native,
        'final_candidate_status':closure['candidate_after']['status'],'final_run_status':closure['run_after']['status'],
        'native_supervision':{k:arc['native_supervision'][k] for k in ('status','elapsed_seconds','peak_tree_rss_bytes','termination')},
        'physical_source_inventory':14641,'grounded_assemblies':232,'represented_physical_source_inventory':14409,
        'native_source_clearance':'UNKNOWN_NOT_COMPLETED','complete_source_pair_count':None,'complete_self_pair_count':None,
        'service_verdict':'NOT_ESTABLISHED','second_generated_alternative':'NOT_NATIVE_CHECKED_WITHIN_BUDGET',
        'partial_native_semantics':{'status':'PASS','components':partial['new_components'],'ports':partial['ports'],
            'original_parsed_records_checked':partial['original_parsed_records_checked'],'artifact_root':partial['semantic_root'],
            'authority':partial['authority']},
        'timeout_reconciliation':str(closure_path)},
    'limitations':['No whole-federation clearance or operating claim while alignment is unresolved',
        'The architecture IFC has no original distribution ports. Source and sinks are explicitly authored hypothetical terminals, not discovered installed connections',
        'Fixed prescribed simultaneous flows, ideal circular bore from native envelope minus declared insulation, fixed Darcy and fitting-loss assumptions',
        'Numerical native CAD and exact source support enclosures have their declared representation/numerical assumptions; no real-world measurement certificate',
        'Finite generated alternatives only, no continuous global routing optimum',
        'Initial successful-import wrappers read the wrong project key; unchanged raw failures and separate completion reconciliations retained without native rerun',
        'Architecture screening proximity field has a historical nearest_mep label; no MEP exists in this scope and it used the nearest architectural box. Screening is proposal-only.'],
    'receipts':{'full_campaign':full['out'],'arc_campaign':arc['out'],'datum_inventory':str(STAGE/'datums/fa2e6835c6494e9a9444b3bf06eac0c2')},
    'application_or_original_store_mutations':False}
atomic_json(out/'result.json',result);print(json.dumps({'report':str(out),'status':arc['status']}),flush=True)
