"""Seal only completed seven-discipline evidence, independently of the active ARC run."""
from pathlib import Path
import gzip,hashlib,json,shutil,uuid,zlib
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').exists())
STAGE=Path(__file__).resolve().parent
OUT=ROOT/'evidence/benchmarks/hospital-generated-tree'/('full-federation-'+uuid.uuid4().hex)
OUT.mkdir(parents=True)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def dump(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
mapping=[]
def copy(old,new):
    old=old.resolve();h=sha(old);new.parent.mkdir(parents=True,exist_ok=True)
    compress=old.suffix.lower()=='.ifc' or (old.stat().st_size>8*1024**2 and old.suffix=='.json')
    if compress:
        new=new.with_name(new.name+'.gz')
        with old.open('rb') as src,new.open('wb') as target:
            with gzip.GzipFile(filename='',mode='wb',fileobj=target,mtime=0) as stream:shutil.copyfileobj(src,stream)
        with gzip.open(new,'rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==h
    else:shutil.copyfile(old,new);assert sha(new)==h
    assert sha(old)==h
    mapping.append({'original_path':str(old),'path':new.relative_to(OUT).as_posix(),'sha256':sha(new),'bytes':new.stat().st_size,
        'original_sha256':h,'original_bytes':old.stat().st_size,'encoding':'gzip' if compress else 'identity'})
import_dir=STAGE/'attempts/6f55c59953f5457daba32dc8223101b2'
datum_dir=STAGE/'datums/fa2e6835c6494e9a9444b3bf06eac0c2'
campaign_dir=STAGE/'campaigns/f07c0723bf8b47f880a5cda57a8b01b0'
declaration=read(import_dir/'predeclaration.json')
completed=read(import_dir/'completion/b50465ae30204398a2ab9d53cd701c63/result.json')
generation=read(campaign_dir/'result.json');datums=read(datum_dir/'result.json')
assert completed['status']=='IMPORTED_CURRENT_SOURCE_INVENTORY'
assert completed['federation']['status']==datums['alignment']=='UNRESOLVED'
assert generation['status']=='GENERATION_BLOCKED' and generation['generation_run']['status']=='MISSING_INPUTS'
assert generation['generation_supervision']['status']=='COMPLETED'
assert generation['project_after']==read(campaign_dir/'predeclaration.json')['project_before']
assert generation['original_bytes_unchanged'] and generation['app_unchanged']
for source,label in ((import_dir,'import'),(datum_dir,'datums'),(campaign_dir,'generation')):
    for p in sorted(source.rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts:copy(p,OUT/label/p.relative_to(source))
for name in ('prepare.py','reconcile_import.py','assess_datums.py','run_datums.py','campaign.py','retain_full_federation.py','verify_retention.py'):
    copy(STAGE/name,OUT/'scripts'/name)
app=Path(declaration['application_source']);assert {p.relative_to(app).as_posix():sha(p) for p in app.rglob('*.py')}==declaration['application_sources']
for p in sorted(app.rglob('*.py')):copy(p,OUT/'source'/p.relative_to(app))
for item in declaration['inputs']:
    p=Path(item['path']);assert sha(p)==item['sha256'];copy(p,OUT/'original-ifc'/p.name)
for p in (ROOT/'data/ifc-bench/projects/west_riverside_hospital/model_card.md',ROOT/'data/ifc-bench/projects/west_riverside_hospital/license.txt',
          ROOT/'evidence/ifc/federations/west_riverside_hospital-ifc4.json',ROOT/'evidence/ifc/west_riverside_hospital-preseed.json'):
    copy(p,OUT/'source-provenance'/p.name)
state=read(import_dir/'completion/b50465ae30204398a2ab9d53cd701c63/imported-state.json')
audits=[]
for s in state['sources']:
    path=Path(completed['store'])/'blobs'/(s['audit_root']+'.json.z');copy(path,OUT/'source-audits'/path.name)
    audit=json.loads(zlib.decompress(path.read_bytes()));assert audit['source_sha256']==s['sha256']
    audits.append({'name':s['name'],'sha256':s['sha256'],'audit_root':s['audit_root'],'product_count':s['product_count'],
        'geometry_counts':s['geometry_counts'],'blockers':s['blockers'],'physical_inventory':audit.get('physical_inventory'),
        'inventory_version':audit.get('inventory_version')})
result={'schema':'oma.hospital-seven-discipline-result/1','status':'IMPORTED_BUT_GENERATION_BLOCKED_BY_UNRESOLVED_ALIGNMENT',
    'checker_version':declaration['checker_version'],'application_python_files':len(declaration['application_sources']),
    'inputs':declaration['inputs'],'counts':completed['counts'],'current_source_audits':audits,
    'import_seconds':completed['original_elapsed_seconds'],'datum_audit_seconds':datums['elapsed_seconds'],
    'generation_seconds':generation['elapsed_seconds'],'generation_run_status':generation['generation_run']['status'],
    'generation_reason':generation['reason'],'datum_reasons':datums['sources'],'candidate_count':0,
    'accepted':False,'native_route_check':'NOT_RUN','export_check':'NOT_RUN','project_head_unchanged_after_generation':True,
    'all_original_bytes_unchanged':True,'source_count':7,'architecture_only_run_included':False,
    'limitations':['No projected CRS, map conversion or grid declarations in any source; differing identity/north/storey anchors remain unresolved',
        'Complete imported inventory and explicit connections do not establish whole-building or engineering adequacy',
        'Source geometry meshes were reused as checked copied import assets; current inventory, coordinates and port ownership were rederived',
        'Initial import-report wrapper used head_root instead of state_root; its failure and separate completion reconciliation are retained; import was not rerun',
        'Copied scripts preserve historical absolute paths; source/IFC hashes are retained, and fresh import can regenerate omitted mesh caches. No live Store or native cache is copied']}
dump(OUT/'result.json',result)
(OUT/'README.md').write_text('''# West Riverside Hospital: complete IFC4 federation

The validated 33a backend imported all seven disciplines, but correctly blocked generated routing because their alignment is unresolved. No candidate, acceptance or checked export was produced. This handoff contains no partial architecture-only result.

| Operation | Actual result | Time |
|---|---|---:|
| Complete seven-source import | 149,822 product records; 85,602 ports; 42,801 explicit connections | 279.593 s |
| Independent IFC datum inventory | Alignment unresolved | 37.406 s |
| Supervised finite generation request | `MISSING_INPUTS`; no candidate or head change | 4.375 s |

The sources total 223,562,189 bytes: architecture, structure, mechanical, plumbing, electrical, fire alarm and sprinklers. None declares an `IfcMapConversion`, `IfcProjectedCRS` or `IfcGrid`. Every non-architectural source has differing Site, Building and Project GUIDs. Several also disagree on TrueNorth or named storey elevations. Exact declarations and per-source reasons are retained under `datums/`. No identity transform was silently approved and no discipline was removed.

The request was a predeclared hypothetical two-sink, fixed-flow design generated from finite tee sites and connector templates, not complete input trees. The source-frame admission gate rejected it before native route checks. This is an input-alignment blocker, not proof that hospital routing is physically infeasible.

All seven original IFC byte hashes remain unchanged. Their exact decoded bytes are retained as gzip files with the supplied model card and license, crediting Wawan Solihin and the OpenIFC Model Repository, University of Auckland. The 112 frozen Python source files and actual executed scripts are retained. Mesh caches and live Stores are excluded; fresh imports can regenerate meshes from the original IFCs.

The initial import-report wrapper read the wrong public project key after successful import. Its raw failure remains alongside a separate reconciliation against the completed managed worker and actual project state. No import was rerun or original receipt rewritten.

`files.json`, `handoff.json` and `public-mapping.json` bind the retained files and decoded originals. Verify with `python scripts/verify_retention.py <this-directory>` using only the standard library. Verification checks retained bytes; it does not upgrade native or engineering scope.
''',encoding='utf8')
dump(OUT/'public-mapping.json',{'schema':'oma.hospital-public-retention/1','files':mapping,'live_stores_or_native_caches_copied':False,'architecture_inflight_artifacts_copied':False})
rows=[{'path':p.relative_to(OUT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(OUT.rglob('*')) if p.is_file()]
dump(OUT/'files.json',{'files':rows,'file_count':len(rows),'bytes':sum(r['bytes'] for r in rows),'excluded':['files.json','handoff.json']})
handoff={'status':'EXACT_PUBLIC_RETENTION_PASS','output':str(OUT),'indexed_files':len(rows),'indexed_bytes':sum(r['bytes'] for r in rows),
    'index_sha256':sha(OUT/'files.json'),'original_files_unchanged':True,'application_or_store_changes':False,'scope':'Completed seven-discipline import/datum/generation blocker only'}
dump(OUT/'handoff.json',handoff);print(json.dumps(handoff),flush=True)
