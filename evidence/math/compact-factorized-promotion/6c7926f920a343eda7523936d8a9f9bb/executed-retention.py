"""Retain and stage the exact approved source/test promotion and reviewed gate."""
from pathlib import Path
import hashlib,json,shutil,subprocess
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
PREP=ROOT/'.oma/development/f73-live-handover-review/prepared'
ATTEMPT=PREP/'promotion-attempts/6c7926f920a343eda7523936d8a9f9bb'
OUT=ROOT/'evidence/math/compact-factorized-promotion/6c7926f920a343eda7523936d8a9f9bb'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
r=read(ATTEMPT/'result.json');assert r['status']=='EXACT_F73_5_SOURCE_43_TEST_PROMOTION_COMPLETE_NO_LIVE_CHANGE'
assert len(r['items'])==48
for name,row in r['items'].items():assert sha(ROOT/name)==row['after']
OUT.mkdir(parents=True,exist_ok=False)
def copy(p,t):t.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,t);assert sha(p)==sha(t)
for p in ATTEMPT.rglob('*'):
    if p.is_file():copy(p,OUT/'attempt'/p.relative_to(ATTEMPT))
review=read(PREP/'review.json')
for name,digest in review['prepared_sources'].items():
    assert sha(PREP/name)==digest;copy(PREP/name,OUT/'reviewed-workflow'/name)
for name in ('review.json','static-review-result.json'):copy(PREP/name,OUT/'reviewed-workflow'/name)
copy(ROOT/'.oma/development/factorized-tree-pressure/promotion/review.json',OUT/'source-test-review.json')
copy(Path(__file__),OUT/'executed-retention.py')
handoff={'status':'EXACT_F73_5_SOURCE_43_TEST_PROMOTION_RETAINED','source_checkpoint':r['checker_version'],
         'application_changes':5,'test_support_changes':43,'promotion_result_sha256':sha(ATTEMPT/'result.json'),
         'ui_modified':False,'scope':'Reviewed exact source/test promotion after both3275 native suites passed. Live handover has a separate receipt.',
         'retained_files':{p.relative_to(OUT).as_posix():sha(p) for p in OUT.rglob('*') if p.is_file()}}
(OUT/'handoff.json').write_text(json.dumps(handoff,indent=2)+'\n',encoding='utf-8')
names=list(r['items'])+[p.relative_to(ROOT).as_posix() for p in OUT.rglob('*') if p.is_file()]
listing=Path(__file__).with_name('promoted-paths.nul');listing.write_bytes(b''.join(n.encode()+b'\0' for n in names))
subprocess.run(['git','add','-f','--pathspec-from-file='+str(listing),'--pathspec-file-nul'],cwd=ROOT,check=True)
print(json.dumps({'status':'RETAINED_AND_STAGED','directory':str(OUT),'files':len(names),'handoff_sha256':sha(OUT/'handoff.json')}))
