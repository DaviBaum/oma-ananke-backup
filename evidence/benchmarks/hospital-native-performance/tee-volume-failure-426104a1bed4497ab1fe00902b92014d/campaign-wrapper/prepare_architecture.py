"""Separate architectural-scope hospital import with immutable inputs and retained supervision."""
import hashlib,json,os,shutil,sys,time,uuid,traceback
from pathlib import Path
from oma.store import Store,digest
from oma.ifc.audit import atomic_json,sha256_file
from oma.build_identity import checker_version
from oma.export_checks import supervise_check

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
STAGE=Path(__file__).resolve().parent
BUILD='f716dd5cbdd84134a50d855b217b91a886832abc582ee761b1340cec2026b8e7'
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def main():
    start=time.monotonic();out=STAGE/'attempts'/uuid.uuid4().hex;out.mkdir(parents=True)
    source=Path(os.environ['PYTHONPATH']);assert checker_version()=='oma-independent-checker/2:'+BUILD
    inputs=read(ROOT/'evidence/ifc/federations/west_riverside_hospital-ifc4.json')['sources']
    inputs=[item for item in inputs if Path(item['path']).name=='arc_ifc4.ifc']
    app={p.relative_to(source).as_posix():sha256_file(p) for p in source.rglob('*.py')};assert len(app)==114
    rows=[]
    for s in inputs:
        p=Path(s['path']);assert sha256_file(p)==s['source_id']
        rows.append({'path':str(p),'sha256':s['source_id'],'bytes':p.stat().st_size})
    declaration={'schema':'oma.hospital-generated-tree-import/1','application_source':str(source),'checker_version':checker_version(),
        'application_sources':app,'inputs':rows,'input_count':len(rows),'script_sha256':sha256_file(Path(__file__)),
        'import_budget_seconds':1800,'memory_limit_bytes':12*1024**3,
        'scope':'Separate explicit architecture-only scope. It does not establish coordination against the six omitted disciplines; the original seven-discipline attempt remains unchanged. All architectural objects remain included.'}
    atomic_json(out/'predeclaration.json',declaration);shutil.copyfile(__file__,out/'executed.py')
    store=Store(STAGE/'stores'/out.name)
    result={'status':'RUNNING','store':str(store.directory),'output':str(out),'declaration_root':digest(declaration)}
    atomic_json(out/'result.json',result);print(json.dumps(result),flush=True)
    try:
        cached=[]
        for row in rows:
            origin=ROOT/'.oma/geometry'/row['sha256'];audit_paths=list(origin.glob('*.audit.json'));assert len(audit_paths)==1
            raw=read(audit_paths[0]);assert raw['source_sha256']==row['sha256']
            target=store.directory/'geometry'/row['sha256'];target.mkdir(parents=True)
            artifacts={}
            for key,path in raw['artifacts'].items():
                old=Path(path);assert old.is_file(),old
                new=target/old.name;shutil.copyfile(old,new);assert sha256_file(old)==sha256_file(new)
                artifacts[key]=str(new)
            raw['artifacts']=artifacts
            atomic_json(target/audit_paths[0].name,raw)
            cached.append({'source':row['path'],'audit_sha256':sha256_file(audit_paths[0]),'original_counts':raw['geometry_counts'],
                'original_bounds':raw.get('bounds'),'port_count':len(raw.get('ports',[])),'copied_artifacts':artifacts})
        atomic_json(out/'cached-audit-inputs.json',cached)
        empty={'schema_version':1,'sources':[],'entities':[],'ports':[],'routes':[],'explicit_connections':[],
            'inferred_connections':[],'mission':None,'assumptions':[],'dependencies':{},'derived_artifacts':{},'units':'m'}
        project=store.create_project('West Riverside Hospital - separate architecture-only generated-tree benchmark',empty)
        run=store.create_run(project['id'],{'operation':'import','paths':[r['path'] for r in rows],'budget_seconds':1800})
        result.update(project_id=project['id'],import_run_id=run['id']);atomic_json(out/'result.json',result)
        supervision=supervise_check([sys.executable,'-m','oma.worker',str(store.directory),run['id']],
            environment=dict(os.environ),directory=out/'import-supervision',deadline=time.monotonic()+1800,memory_limit_bytes=12*1024**3)
        result['supervision']=supervision;result['run']=store.run(run['id']);result['project']=store.project(project['id'])
        assert supervision['status']=='COMPLETED' and result['run']['status']=='COMPLETED'
        state=store.get(result['project']['state_root']);atomic_json(out/'imported-state.json',state)
        result['counts']={'sources':len(state['sources']),'entities':len(state['entities']),'ports':len(state['ports']),
            'explicit_connections':len(state['explicit_connections'])}
        result['sources']=[{k:s.get(k) for k in ('id','name','sha256','audit_root','bounds','blockers','product_count','geometry_counts','coordinate_scope','transform_m')} for s in state['sources']]
        result['federation']=state['derived_artifacts']['local_coordinate_evidence']
        result['status']='IMPORTED_CURRENT_SOURCE_INVENTORY'
    except Exception:
        result['status']='IMPORT_FAILED';result['traceback']=traceback.format_exc()
    finally:
        result['input_bytes_unchanged']=all(sha256_file(Path(r['path']))==r['sha256'] for r in rows)
        result['application_unchanged']={p.relative_to(source).as_posix():sha256_file(p) for p in source.rglob('*.py')}==app
        result['elapsed_seconds']=time.monotonic()-start;atomic_json(out/'result.json',result)
        print(json.dumps({k:v for k,v in result.items() if k not in ('federation','sources','supervision')},default=str),flush=True)
if __name__=='__main__':main()
