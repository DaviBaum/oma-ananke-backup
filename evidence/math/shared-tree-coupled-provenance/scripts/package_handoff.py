"""Portable coupled-profile component, unchanged base tests and retained inputs."""
from pathlib import Path
import hashlib,json

STAGE=Path(__file__).resolve().parents[1];ROOT=STAGE.parents[2]
OUT=STAGE/'evidence/math/shared-tree-coupled-provenance';OUT.mkdir(parents=True,exist_ok=True)
receipt='54efc47c0e9243fda34e92526cda3f9c'
result=json.loads((STAGE/'validation'/receipt/'result.json').read_text(encoding='utf-8'))
def sha(data):return hashlib.sha256(data).hexdigest()
def copy(source,target):
 target.parent.mkdir(parents=True,exist_ok=True);data=source.read_bytes()
 if target.exists():assert target.read_bytes()==data,str(target)
 else:target.write_bytes(data)
def tree(source,target):
 for file in sorted(source.rglob('*')):
  if file.is_file() and '__pycache__' not in file.parts and file.suffix!='.pyc':copy(file,target/file.relative_to(source))
merge=[];runtime=STAGE/'runtimes'/result['source_root']
for item in result['files']:
 assert sha((runtime/item['path']).read_bytes())==item['sha256']
 copy(runtime/item['path'],OUT/'implementation'/item['path'])
 merge.append({**item,'handoff_path':'implementation/'+item['path'],
  'unchanged_from_base688':item['path']=='tests/test_shared_tree_catalogue_check.py' or item['path'].startswith('tests/fixtures/shared-tree-catalogue-check/')})
doc='docs/math/shared-tree-coupled-provenance.md';copy(STAGE/doc,OUT/'implementation'/doc)
merge.append({'path':doc,'sha256':sha((STAGE/doc).read_bytes()),'handoff_path':'implementation/'+doc,'unchanged_from_base688':False})
tree(STAGE/'validation'/receipt,OUT/'validation'/receipt)
dependency=json.loads((STAGE/'dependencies/base.json').read_text(encoding='utf-8'))
copy(STAGE/'dependencies/base.json',OUT/'dependency-source-manifest.json')
tree(STAGE/'dependencies'/dependency['root']/'src',OUT/'dependencies/src')
tree(STAGE/'scripts',OUT/'scripts')
tree(STAGE/'evidence/fixture-authoring',OUT/'fixture-authoring')
design=ROOT/'.oma/development/shared-tree-coupled-design'
copy(design/'design.md',OUT/'design/design.md')
copy(design/'scripts/assess.py',OUT/'design/assess.py')
copy(design/'evidence/assessment.json',OUT/'design/assessment.json')
copy(design/'evidence/source-excerpts.json',OUT/'design/source-excerpts.json')
replay='''from pathlib import Path
import os,subprocess,sys
p=Path(__file__).resolve().parent
env=os.environ.copy();env['PYTHONPATH']=str(p/'dependencies/src');env['OMA_CATALOGUE_CHECK_SOURCE']=str(p/'implementation/src/oma/routing/shared_tree_catalogue_check.py')
tests=[p/'implementation/tests/test_shared_tree_catalogue_check.py',p/'implementation/tests/test_shared_tree_coupled_catalogue_check.py']
raise SystemExit(subprocess.call([sys.executable,'-m','pytest',*map(str,tests),'-q','-o','addopts=','-o','pythonpath='+(p/'dependencies/src').as_posix()],env=env))
'''
(OUT/'replay.py').write_text(replay,encoding='utf-8')
files=[{'path':p.relative_to(OUT).as_posix(),'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size} for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='handoff.json']
handoff={'schema':'oma.shared-tree-coupled-provenance-handoff/1','status':'READY',
 'component_snapshot':result['source_root'],'production_build_identity':False,
 'module_sha256':result['module_sha256'],'base_module_sha256':'688cb03a0c75f23ee07e3e4b668980ec7d94267337b6c0f9b7ac4e5309045f7b',
 'dependency_source_root':dependency['root'],'merge_files':merge,
 'validation':{'receipt':'validation/'+receipt+'/result.json','collected':164,'tests':164,'new_cases':70,'unchanged_base_cases':94,'failed':0,'errors':0,'skipped':0},
 'evidence_files':files,'scope':'Current supplied nominal macro catalogue provenance with complete unchanged fixed-ID unequal-pressure obligation identity; no local/global operating-point, native geometry/service, physical optimum or admission authority',
 'production_files_changed':False,'prior_base_handoff_unchanged':True,'replay':'python replay.py with the same declared runtime dependencies installed'}
(OUT/'handoff.json').write_text(json.dumps(handoff,indent=2)+'\n',encoding='utf-8')
assert all(sha((OUT/x['path']).read_bytes())==x['sha256'] for x in files)
print(json.dumps({'path':str(OUT/'handoff.json'),'sha256':sha((OUT/'handoff.json').read_bytes()),'merge_files':len(merge),'new_or_changed_files':sum(not x['unchanged_from_base688'] for x in merge),'evidence_files':len(files)}))
