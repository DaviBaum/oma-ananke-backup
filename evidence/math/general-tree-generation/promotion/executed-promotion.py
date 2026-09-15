"""Reviewable exact4-source/4-test EDF promotion. Default is read-only."""
import argparse,hashlib,json,os,shutil,subprocess,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
STAGE=Path(__file__).resolve().parent
REVIEW=ROOT/'.oma/development/general-shared-tree-native/promotion/review.json'
FULL=ROOT/'evidence/release/general-tree-original-full-a29404ec828e'
CUSTOM=ROOT/'evidence/dependencies/native-build/checkpoint-validation/edf555760245-4c1eddeca46f/result.json'
SOURCE='edf555760245581599c33a06d99e1010f88f684a5c323ae00e3370f31f73448c'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
review=read(REVIEW);full=read(FULL/'result.json');custom=read(CUSTOM)
assert full['status']=='PASS' and full['passed']==3012 and full['returncode']==0
assert custom['status']=='CUSTOM_NATIVE_NEW_CHECKPOINT_FULL_SUITE_PASS' and custom['passed']==3012
assert full['checker_version']=='oma-independent-checker/2:'+SOURCE
assert custom['source_checkpoint']==SOURCE
expected={('src/'+k):v for k,v in full['source_files'].items()}
changed=review['changed_source_files'];tests=review['new_test_support_files']
assert len(changed)==len(tests)==4
base=expected|{k:v['before'] for k,v in changed.items()}
current={p.relative_to(ROOT).as_posix():sha(p) for p in (ROOT/'src').rglob('*.py')}
assert current==base,'Root source must equal exact pre-promotion112-file checkpoint'
items={}
for name,row in changed.items():
    source=FULL/name;assert sha(source)==row['after']==expected[name]
    items[name]={'source':str(source),'before':row['before'],'after':row['after']}
for name,digest in tests.items():
    source=FULL/'snapshot'/name;assert sha(source)==digest
    assert not (ROOT/name).exists(),'New approved support file already exists; root must review its identity'
    items[name]={'source':str(source),'before':None,'after':digest}
plan={'status':'REVIEW_ONLY_NOT_APPLIED','apply_requested':args.apply,'source_checkpoint':SOURCE,
      'full_receipt_sha256':sha(FULL/'result.json'),'custom_receipt_sha256':sha(CUSTOM),'review_sha256':sha(REVIEW),
      'items':items,'scope':'Only the four approved application files and four new test/support files; no git, UI, Store or live-service change.'}
if not args.apply:
    print(json.dumps(plan,indent=2));raise SystemExit
out=STAGE/'attempts'/uuid.uuid4().hex;out.mkdir(parents=True)
(out/'plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
for name,row in items.items():
    target=(ROOT/name).resolve();assert target.is_relative_to(ROOT.resolve())
    if target.exists():
        assert sha(target)==row['before'];backup=out/'before'/name;backup.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(target,backup)
    target.parent.mkdir(parents=True,exist_ok=True)
    temporary=target.with_name(target.name+'.edf-promotion-'+uuid.uuid4().hex+'.tmp')
    shutil.copyfile(row['source'],temporary);assert sha(temporary)==row['after'];temporary.replace(target)
assert {p.relative_to(ROOT).as_posix():sha(p) for p in (ROOT/'src').rglob('*.py')}==expected
assert all(sha(ROOT/name)==row['after'] for name,row in items.items())
env=os.environ.copy();env['PYTHONPATH']=str(ROOT/'src');env.pop('OMA_EXECUTABLE_BUILD',None)
actual=subprocess.check_output([str(ROOT/'.venv/Scripts/python.exe'),'-c','from oma.build_identity import checker_version;print(checker_version())'],cwd=ROOT,env=env,text=True).strip()
assert actual==full['checker_version']
plan.update(status='EXACT_EDF_SOURCE_AND_TESTS_PROMOTED_NO_LIVE_HANDOVER',current_checker_version=actual)
(out/'result.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
shutil.copyfile(__file__,out/'executed-promotion.py');print(out)
