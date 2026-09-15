"""Retain corrected replay of the unchanged, previously captured review probes."""
from pathlib import Path
import hashlib,json,subprocess,sys,uuid

ROOT=Path(__file__).resolve().parents[4]
STAGE=Path(__file__).resolve().parents[1]
OLD=ROOT/'.oma/development/shared-tree-synthesis/evidence/adapter-readonly-review/905d79e1f74b4c4c874d806dbf9114b3'
SOURCE=ROOT/'.oma/development/shared-tree-native/src'
OUT=STAGE/'evidence/corrected-producer-resource-review'/uuid.uuid4().hex
OUT.mkdir(parents=True)
def sha(b):return hashlib.sha256(b).hexdigest()
records=[]
for path in sorted(SOURCE.rglob('*.py')):
    relative=path.relative_to(SOURCE);data=path.read_bytes()
    target=OUT/'src'/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    records.append({'path':relative.as_posix(),'sha256':sha(data)})
(OUT/'original-reproduce.py').write_bytes((OLD/'reproduce.py').read_bytes())
(OUT/'test_shared_tree_proposals.py').write_bytes((OLD/'test_shared_tree_proposals.py').read_bytes())
script=(OLD/'reproduce.py').read_text(encoding='utf-8')
script=script.replace("ROOT=HERE.parents[5]", "ROOT=HERE")
script=script.replace("PRIVATE=ROOT/'.oma/development/shared-tree-native'", "PRIVATE=HERE")
script=script.replace("else HERE/'shared_tree_proposals.py'", "else HERE/'src/oma/routing/shared_tree_proposals.py'")
(OUT/'reproduce.py').write_text(script,encoding='utf-8')
run=subprocess.run([sys.executable,str(OUT/'reproduce.py')],capture_output=True,text=True,encoding='utf-8',timeout=60)
(OUT/'stdout.txt').write_text(run.stdout,encoding='utf-8');(OUT/'stderr.txt').write_text(run.stderr,encoding='utf-8')
assert run.returncode==0,run.stderr
result=json.loads(run.stdout)
section=result['decimal_string_dimension'];manifest=section['fabrication_manifest']
from fractions import Fraction as Q
radius=Q(section['catalogue_section']['diameter_m'])/2+Q(section['catalogue_section']['insulation_m'])
assert result['polling_jump']['callbacks']
assert result['exact_remaining_work']['result']['status']=='UNKNOWN'
assert Q(manifest['outer_radius_m'])==radius,(manifest,radius)
checks={'polling_jump_observed':True,'exhausted_child_budget_is_unknown':True,'normalized_catalogue_and_fabrication_radius_identical':True}
receipt={'schema':'oma.corrected-producer-resource-review/1','status':'PASS','source_files':records,
 'source_manifest_root':sha(json.dumps(records,sort_keys=True,separators=(',',':')).encode()),
 'original_receipt':'../../../../shared-tree-synthesis/evidence/adapter-readonly-review/905d79e1f74b4c4c874d806dbf9114b3',
 'checks':checks,'probe':result,'original_failed_evidence_unchanged':True,
 'scope':'Private producer-only control and exact normalized-dimension replay; no native or Store action'}
(OUT/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'directory':str(OUT),'checks':checks,'source_sha256':result['source_sha256']}))
