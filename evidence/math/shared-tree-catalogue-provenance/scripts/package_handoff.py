"""Copy the exact new component and retained receipts into a portable evidence tree."""
from pathlib import Path
import hashlib,json,shutil,sys

STAGE=Path(__file__).resolve().parents[1]
ROOT=STAGE.parents[2]
OUT=STAGE/'evidence/math/shared-tree-catalogue-provenance'
OUT.mkdir(parents=True,exist_ok=True)
RECEIPT='6ee4dfcb1f67409baee0be07f8a986cd'
result=json.loads((STAGE/'validation'/RECEIPT/'result.json').read_text(encoding='utf-8'))
def sha(data):return hashlib.sha256(data).hexdigest()
def copy_file(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    data=source.read_bytes()
    if target.exists():assert target.read_bytes()==data,str(target)
    else:target.write_bytes(data)
def copy_tree(source,target):
    for path in sorted(source.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':copy_file(path,target/path.relative_to(source))

merge=[]
runtime=STAGE/'runtimes'/result['source_root']
for record in result['files']:
    source=runtime/record['path'];assert sha(source.read_bytes())==record['sha256']
    copy_file(source,OUT/'implementation'/record['path'])
    merge.append({**record,'handoff_path':'implementation/'+record['path']})
doc='docs/math/shared-tree-catalogue-provenance.md'
copy_file(STAGE/doc,OUT/'implementation'/doc)
merge.append({'path':doc,'sha256':sha((STAGE/doc).read_bytes()),'handoff_path':'implementation/'+doc})
for receipt in (RECEIPT,'ea16b6f1110b4aaca0b85a1047dec11d'):
    copy_tree(STAGE/'validation'/receipt,OUT/'validation'/receipt)
copy_tree(STAGE/'runtimes/eb88d3a78038b7ddbec08408b28584d91082e9292617f33806d579147904ef85',
          OUT/'validation/ea16b6f1110b4aaca0b85a1047dec11d/snapshot')
copy_file(STAGE/'dependencies/base.json',OUT/'dependency-source-manifest.json')
dependency=json.loads((STAGE/'dependencies/base.json').read_text(encoding='utf-8'))
copy_tree(STAGE/'dependencies'/dependency['root']/'src',OUT/'dependencies/src')
old=ROOT/'.oma/development/shared-tree-synthesis/evidence/adapter-readonly-review/905d79e1f74b4c4c874d806dbf9114b3'
copy_tree(old,OUT/'producer-resource-review/original-905d79')
copy_tree(STAGE/'evidence/corrected-producer-resource-review/9915534d5b6a4de49a89dc2ee3911a92',OUT/'producer-resource-review/corrected-991553')
sentinel=ROOT/'.oma/development/shared-tree-synthesis/evidence/supplementary-parser-audit/0cffe70ba3144e89839cfbd8548b930c'
copy_tree(sentinel,OUT/'pure-kernel-parser-sentinel')
copy_file(ROOT/'.oma/development/next-math-priority/evidence/source-excerpts.json',OUT/'source/source-excerpts.json')
copy_tree(STAGE/'scripts',OUT/'scripts')
peer=[]
for argument in sys.argv[1:]:
    source=Path(argument).resolve();target=OUT/'independent-reviews'/source.name
    copy_tree(source,target)
    peer.append({'path':target.relative_to(OUT).as_posix(),'original':str(source.relative_to(ROOT)).replace('\\','/')})
reproducer='''"""Replay the exact portable checker tests against the retained dependency source."""
from pathlib import Path
import os,subprocess,sys
p=Path(__file__).resolve().parent
env=os.environ.copy();env['PYTHONPATH']=str(p/'dependencies/src');env['OMA_CATALOGUE_CHECK_SOURCE']=str(p/'implementation/src/oma/routing/shared_tree_catalogue_check.py')
raise SystemExit(subprocess.call([sys.executable,'-m','pytest',str(p/'implementation/tests/test_shared_tree_catalogue_check.py'),'-q','-o','addopts=','-o','pythonpath='+(p/'dependencies/src').as_posix()],env=env))
'''
(OUT/'replay.py').write_text(reproducer,encoding='utf-8')
files=[{'path':p.relative_to(OUT).as_posix(),'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size} for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='handoff.json']
handoff={'schema':'oma.shared-tree-catalogue-provenance-handoff/1','status':'READY',
 'new_component_snapshot':result['source_root'],'production_build_identity':False,
 'module_sha256':result['module_sha256'],'dependency_source_root':dependency['root'],
 'merge_files':merge,'validation':{'receipt':'validation/'+RECEIPT+'/result.json','tests':94,'failed':0,'errors':0,'skipped':0},
 'independent_reviews':peer,'evidence_files':files,
 'scope':'Supplied current-input catalogue/template/geometry/cost provenance only; no all-template completeness, native feasibility, physical cost lower bound or acceptance authority',
 'production_files_changed':False,'original_failed_evidence_preserved':True,
 'replay':'python replay.py with the same declared runtime dependencies installed'}
(OUT/'handoff.json').write_text(json.dumps(handoff,indent=2)+'\n',encoding='utf-8')
assert all(sha((OUT/x['path']).read_bytes())==x['sha256'] for x in files)
print(json.dumps({'path':str(OUT/'handoff.json'),'sha256':sha((OUT/'handoff.json').read_bytes()),'merge_files':len(merge),'evidence_files':len(files)}))
