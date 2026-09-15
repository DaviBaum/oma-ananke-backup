"""Append-only portable peer/producer/control/diagnostic review supplement."""
from pathlib import Path
import hashlib,json

STAGE=Path(__file__).resolve().parents[1];ROOT=STAGE.parents[2]
OUT=STAGE/'evidence/math/shared-tree-coupled-review-supplement';OUT.mkdir(parents=True,exist_ok=True)
def sha(b):return hashlib.sha256(b).hexdigest()
def copy(source,target):
 target.parent.mkdir(parents=True,exist_ok=True);data=source.read_bytes()
 if target.exists():assert target.read_bytes()==data
 else:target.write_bytes(data)
def tree(source,target):
 for path in sorted(source.rglob('*')):
  if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':copy(path,target/path.relative_to(source))
tree(ROOT/'.oma/development/shared-tree-coupled-review/checker-peer/79887ab003b6436081f9f036bd412d34',OUT/'checker-peer')
tree(STAGE/'evidence/producer-independent-review/16723119554043be97e20f88e2fdd389',OUT/'producer-review')
tree(STAGE/'evidence/native-center-width/72a3d486357547b39ac88dc8dce84135',OUT/'native-center-width')
copy(STAGE/'evidence/review-summary.md',OUT/'review-summary.md')
copy(Path(__file__),OUT/'package_review_supplement.py')
files=[{'path':p.relative_to(OUT).as_posix(),'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size} for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='supplement.json']
result={'schema':'oma.shared-tree-coupled-review-supplement/1','status':'REVIEW_COMPLETE',
 'unchanged_handoff_sha256':'2b9f2115991fe7ab1ff1fcafbc6e53555c1aa06d15fa8909ff27fee36809ce6b',
 'checker_sha256':'c800938e03909fcbe8a014e21b46c9640ddf5736fe3684f345bdd57a5bfb7fd4',
 'producer_sha256':'8acee79562fd2a4da02ac507897ed7c70e124ed75c3fee20e07c9f0fa74e9dee',
 'files':files,'producer_review_checks':38,'peer_adversarial_cases':14,
 'scope':'Nominal identity/provenance/control review ready; actual pressure acceptance remains a separate unmet original validation. Center-image attribution is diagnostic only.',
 'production_or_original_input_changes':False}
(OUT/'supplement.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
assert all(sha((OUT/x['path']).read_bytes())==x['sha256'] for x in files)
print(json.dumps({'path':str(OUT/'supplement.json'),'sha256':sha((OUT/'supplement.json').read_bytes()),'files':len(files)}))
