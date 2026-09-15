"""Recover only the wrapper's wrong project-key read; preserve the original receipt."""
import json,sys,uuid,time,shutil
from pathlib import Path
from oma.store import Store
from oma.ifc.audit import atomic_json,sha256_file
from oma.build_identity import checker_version
p=Path(sys.argv[1]);original=json.loads(p.read_text(encoding='utf8'));declaration=json.loads((p.parent/'predeclaration.json').read_text(encoding='utf8'))
out=p.parent/'completion'/uuid.uuid4().hex;out.mkdir(parents=True);shutil.copyfile(__file__,out/'executed.py')
store=Store(original['store']);run=store.run(original['import_run_id']);project=store.project(original['project_id'])
assert original['supervision']['status']=='COMPLETED' and run['status']=='COMPLETED'
assert original['traceback'].endswith("KeyError: 'head_root'\n")
state=store.get(project['state_root']);assert project['revision']==1
assert checker_version()==declaration['checker_version']
assert all(sha256_file(Path(r['path']))==r['sha256'] for r in declaration['inputs'])
source=Path(declaration['application_source']);assert {x.relative_to(source).as_posix():sha256_file(x) for x in source.rglob('*.py')}==declaration['application_sources']
atomic_json(out/'imported-state.json',state)
r={'status':'IMPORTED_CURRENT_SOURCE_INVENTORY','store':str(store.directory),'project_id':project['id'],'project':project,'import_run':run,
    'original_wrapper_receipt':str(p),'original_wrapper_sha256':sha256_file(p),'checker_version':checker_version(),
    'reconciliation':'Native import and supervision completed. Wrapper read head_root instead of the actual public project.state_root key. No import rerun or original receipt change.',
    'counts':{'sources':len(state['sources']),'entities':len(state['entities']),'ports':len(state['ports']),'explicit_connections':len(state['explicit_connections'])},
    'sources':[{k:s.get(k) for k in ('id','name','sha256','audit_root','bounds','blockers','product_count','geometry_counts','coordinate_scope','transform_m')} for s in state['sources']],
    'federation':state['derived_artifacts']['local_coordinate_evidence'],'source_bytes_unchanged':True,'application_sources_unchanged':True,
    'original_elapsed_seconds':original['elapsed_seconds']}
atomic_json(out/'result.json',r);print(json.dumps({'output':str(out),'counts':r['counts'],'federation':r['federation']['status'],'elapsed':r['original_elapsed_seconds']}))
