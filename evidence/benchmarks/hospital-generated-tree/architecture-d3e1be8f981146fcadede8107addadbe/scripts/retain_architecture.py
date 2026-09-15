"""Seal the bounded ARC-only outcome, preserving all attempts and decoded IFC bytes."""
from pathlib import Path
import gzip, hashlib, json, shutil, uuid, zlib
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').exists())
STAGE=Path(__file__).resolve().parent
OUT=ROOT/'evidence/benchmarks/hospital-generated-tree'/('architecture-'+uuid.uuid4().hex)
OUT.mkdir(parents=True)
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def dump(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
mapping=[]
def copy(old,new):
    old=old.resolve();h=sha(old);new.parent.mkdir(parents=True,exist_ok=True)
    compress=old.suffix.lower()=='.ifc' or (old.stat().st_size>8*1024**2 and old.suffix=='.json')
    if compress:
        new=new.with_name(new.name+'.gz')
        with old.open('rb') as src,new.open('wb') as dst:
            with gzip.GzipFile(filename='',mode='wb',fileobj=dst,mtime=0) as f:shutil.copyfileobj(src,f)
        with gzip.open(new,'rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==h
    else:shutil.copyfile(old,new);assert sha(new)==h
    assert sha(old)==h
    mapping.append({'original_path':str(old),'path':new.relative_to(OUT).as_posix(),'sha256':sha(new),'bytes':new.stat().st_size,
        'original_sha256':h,'original_bytes':old.stat().st_size,'encoding':'gzip' if compress else 'identity'})
def tree(source,label):
    for p in sorted(source.rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts:copy(p,OUT/label/p.relative_to(source))

campaign=STAGE/'campaigns/eac181c60f1748f4841b0796dfd69e00'
declaration=read(campaign/'predeclaration.json');raw=read(campaign/'result.json')
report=read(STAGE/'report/d0bc037c5f5a47259138dfa53fdfa1fb/result.json')
closure=read(STAGE/'completion/42ec2d9c4a5c4fe6ae3ee80d7953d62c/result.json')
assert raw['status']=='NO_CHECKED_INCUMBENT' and raw['native_supervision']['status']=='UNKNOWN_TIMEOUT'
assert closure['candidate_after']['status']=='UNKNOWN' and closure['run_after']['status']=='TIMED_OUT'
assert raw['original_bytes_unchanged'] and raw['app_unchanged']
assert report['architecture_only']['accepted'] is False and report['architecture_only']['exported'] is False
assert raw['project_after']==declaration['project_before']
for source,label in (
    (STAGE/'attempts/2cda40ea47794a7b9335d9cd5774e476','import'),
    (STAGE/'screening/9b2d07baed04465dbbe7c6eaf7a5f423','proposal-screen'),
    (campaign,'campaign'),
    (STAGE/'observations/575e90919b244331846ba216598c35d5','partial-native-observation'),
    (STAGE/'completion/42ec2d9c4a5c4fe6ae3ee80d7953d62c','timeout-reconciliation'),
    (STAGE/'report/d0bc037c5f5a47259138dfa53fdfa1fb','combined-report')):tree(source,label)
store=Path(raw['store'])
tree(store/'checks/candidate-executions/1f7870e7a47841698d0c29005ccd046e','partial-child-execution')
for name in ('prepare_architecture.py','reconcile_import.py','screen.py','campaign.py','observe_native_phase.py',
             'close_timed_out_campaign.py','finalize_report.py','retain_architecture.py','verify_retention.py'):
    copy(STAGE/name,OUT/'scripts'/name)
app=Path(declaration['app_source'])
assert {p.relative_to(app).as_posix():sha(p) for p in app.rglob('*.py')}==declaration['app_sources']
for p in sorted(app.rglob('*.py')):copy(p,OUT/'source'/p.relative_to(app))
state=read(STAGE/'attempts/2cda40ea47794a7b9335d9cd5774e476/completion/8bf77ef0031a4e908cf816468dfc5b98/imported-state.json')
source,=state['sources']
audit_path=store/'blobs'/(source['audit_root']+'.json.z')
audit=json.loads(zlib.decompress(audit_path.read_bytes()));assert audit['source_sha256']==source['sha256']
copy(audit_path,OUT/'source-audits'/audit_path.name)
original=ROOT/'data/ifc-bench/projects/west_riverside_hospital/arc_ifc4.ifc'
assert sha(original)==source['sha256'];copy(original,OUT/'original-ifc'/original.name)
for name in ('model_card.md','license.txt'):copy(original.parent/name,OUT/'source-provenance'/name)
full=ROOT/'evidence/benchmarks/hospital-generated-tree/full-federation-1e87dd6ad9af48b5962cd500603fdfdc'
assert sha(full/'files.json')=='4db9df476ebb2fc5185eee61476b1e9610e69b88dd71cc595f05eeeef2406fc3'
copy(full/'handoff.json',OUT/'related-full-federation-handoff.json')
result={'schema':'oma.hospital-architecture-bounded-outcome/1','status':'NATIVE_CLEARANCE_UNKNOWN_TIMEOUT',
    'checker_version':declaration['checker_version'],'application_python_files':len(declaration['app_sources']),
    'architecture_only':report['architecture_only'],'original_ifc_sha256':source['sha256'],
    'original_ifc_bytes':original.stat().st_size,'original_input_and_project_head_unchanged':True,
    'related_full_federation':'../'+full.name,'related_full_federation_index_sha256':sha(full/'files.json'),
    'no_complete_report_or_acceptance':True,'raw_candidate_ifc_is_unchecked':True,
    'preservation':'Partial native semantic artifact checked canonical parsed entity strings at every original STEP ID and protected inverse semantics. No byte-identical serializer claim.',
    'raw_import_wrapper_failure_and_timeout_preserved':True,
    'reproduction':'Frozen source, original IFC, exact hypothetical request, executed scripts and logs retained. Historical absolute paths must be relocated; fresh import regenerates omitted mesh/native caches.'}
dump(OUT/'result.json',result)
(OUT/'README.md').write_text('''# West Riverside Hospital: separate architecture-only run

The 33a backend generated two finite shared-tree alternatives, but the full architectural clearance check exceeded its predeclared 1,800-second budget. The final candidate is `UNKNOWN`, the run is `TIMED_OUT`, and the project remains at its imported revision 1. Nothing was accepted or exported as checked.

This scope includes every architectural obstacle. Electrical, mechanical, plumbing, structural, fire and sprinkler sources are explicitly outside this separate mission. The complete seven-source import/alignment blocker is retained in the sibling `full-federation-1e87dd6ad9af48b5962cd500603fdfdc` handoff; neither result establishes whole-hospital coordination.

| Stage | Result |
|---|---|
| Separate architectural import | Completed in 19.938 s; 15,316 product records; 14,641 physical elements, including 232 grounded assemblies; no original distribution ports |
| Authored finite generation | Two alternatives from tee sites/stubs/detour plane; independent finite-kernel and catalogue-provenance checks passed |
| First actual IFC | Four components, nine ports; partial native semantics passed and checked 1,346,650 original parsed records |
| Full source/self/service report | Not completed; no pair denominator or service verdict established |
| Supervised timeout | 1,800.031 s; peak sampled tree RSS 10,279,280,640 bytes; all owned kernel-job processes terminated |
| Entire generation/optimization campaign | 1,802.594 s; no selected incumbent, no acceptance, no checked export |

The predeclared hypothetical request supplies two simultaneous 0.5 L/s terminal deliveries at 100 Pa available static pressure, a 62.5 mm nominal circular section, declared insulation and fixed Darcy/fitting-loss assumptions. Terminals were authored in a screened Level 2 region. They are not discovered installed hospital connections. The imported-box screen only proposes geometry; it does not replace the unfinished native obstacle check. Its historical `nearest_mep` label actually refers to the nearest architectural box in this scope; that limitation is recorded explicitly.

Both complete generated alternatives and the first materialized candidate IFC are retained. The second alternative was not native-checked within the budget. `actual.ifc.gz` is an unchecked candidate artifact, not a released IFC. The observed semantic PASS remains a partial child artifact without candidate publication or acceptance authority. Timeout does not establish physical infeasibility.

The outer deadline interrupted the inner parent before it could close its execution. The original `CHECKING` receipt is preserved; a separate public-Store, execution-token-checked reconciliation closed only that owned execution as `UNKNOWN_TIMEOUT` after the retained kernel-job termination confirmed zero remaining processes. Original input bytes, hypothetical mission, project head and frozen application sources were unchanged. No retry was performed.

The source model and partial semantic comparison preserve canonical parsed original entity semantics, not the spelling of every serialized STEP record. Original IFC bytes themselves remain unchanged. The supplied model card/license credit Wawan Solihin and the OpenIFC Model Repository, University of Auckland.

`files.json`, `handoff.json` and `public-mapping.json` bind all retained bytes and decoded gzip originals. Run `python scripts/verify_retention.py <this-directory>` for a standard-library byte audit. Live Stores and native caches are omitted; scripts retain original absolute provenance for relocation. This byte audit does not upgrade the incomplete native outcome.
''',encoding='utf8')
dump(OUT/'public-mapping.json',{'schema':'oma.hospital-public-retention/1','files':mapping,'live_stores_or_native_caches_copied':False})
rows=[{'path':p.relative_to(OUT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(OUT.rglob('*')) if p.is_file()]
dump(OUT/'files.json',{'files':rows,'file_count':len(rows),'bytes':sum(r['bytes'] for r in rows),'excluded':['files.json','handoff.json']})
handoff={'status':'EXACT_PUBLIC_RETENTION_PASS','output':str(OUT),'indexed_files':len(rows),'indexed_bytes':sum(r['bytes'] for r in rows),
    'index_sha256':sha(OUT/'files.json'),'scope':'Completed architecture-only bounded UNKNOWN_TIMEOUT; no selected/accepted/released candidate',
    'original_files_unchanged':True,'application_or_original_store_changes':False}
dump(OUT/'handoff.json',handoff);print(json.dumps(handoff),flush=True)
