"""Exact approved5-source/43-test promotion. Root may execute after review only."""
import argparse,json,os,shutil,subprocess,uuid
from pathlib import Path
from validation_gate import ROOT,FULL,BUILD,completed_validation,read,sha
STAGE=Path(__file__).resolve().parent
REVIEW=ROOT/'.oma/development/factorized-tree-pressure/promotion/review.json'
parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
gate=completed_validation();review=read(REVIEW);sources=gate['files'];assert review['source_checkpoint']==gate['checker_version']
assert len(review['source_changes'])==5 and len(review['test_support_changes'])==43
before=dict(sources)
for name,row in review['source_changes'].items():
    assert sources[name]==row['after']
    if row['before'] is None:before.pop(name)
    else:before[name]=row['before']
current={p.relative_to(ROOT/'src').as_posix():sha(p) for p in (ROOT/'src').rglob('*.py')}
assert current==before and len(current)==112,'Root must still be the exact reviewed EDF baseline'
inputs=read(FULL/'inputs.json')['files']
for name,expected_after in inputs.items():
    expected_before=review['test_support_changes'].get(name,{'before':expected_after})['before']
    assert (sha(ROOT/name) if (ROOT/name).is_file() else None)==expected_before,'Unexpected current test/support change: '+name
items={}
for group,prefix,origin in (('source_changes','src/',FULL/'src'),('test_support_changes','',FULL/'snapshot')):
    for name,row in review[group].items():
        source=origin/name;target=ROOT/(prefix+name);assert sha(source)==row['after']
        assert (sha(target) if target.is_file() else None)==row['before']
        items[prefix+name]={'source':str(source),**row}
plan={'status':'REVIEW_ONLY_NOT_APPLIED','gate':gate,'review_sha256':sha(REVIEW),'items':items}
if not args.apply:print(json.dumps(plan,indent=2));raise SystemExit
out=STAGE/'promotion-attempts'/uuid.uuid4().hex;out.mkdir(parents=True)
(out/'plan.json').write_text(json.dumps(plan,indent=2),encoding='utf8');shutil.copyfile(__file__,out/'executed.py')
# Validate all inputs before the first replacement; preserve every replaced byte.
for name,row in items.items():
    target=(ROOT/name).resolve();assert target.is_relative_to(ROOT)
    if target.exists():
        assert sha(target)==row['before'];backup=out/'before'/name;backup.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(target,backup)
for name,row in items.items():
    target=ROOT/name;target.parent.mkdir(parents=True,exist_ok=True)
    assert (sha(target) if target.is_file() else None)==row['before'] and sha(row['source'])==row['after']
    tmp=target.with_name(target.name+'.f73-'+uuid.uuid4().hex+'.tmp');shutil.copyfile(row['source'],tmp);assert sha(tmp)==row['after'];os.replace(tmp,target)
assert {p.relative_to(ROOT/'src').as_posix():sha(p) for p in (ROOT/'src').rglob('*.py')}==sources
assert all(sha(ROOT/name)==row['after'] for name,row in items.items())
assert all(sha(ROOT/name)==digest for name,digest in inputs.items())
env=os.environ.copy();env['PYTHONPATH']=str(ROOT/'src');env.pop('OMA_EXECUTABLE_BUILD',None);env['PYTHONDONTWRITEBYTECODE']='1'
actual=subprocess.check_output([str(ROOT/'.venv/Scripts/python.exe'),'-c','from oma.build_identity import checker_version;print(checker_version())'],cwd=ROOT,env=env,text=True).strip()
assert actual==gate['checker_version'];plan.update(status='EXACT_F73_5_SOURCE_43_TEST_PROMOTION_COMPLETE_NO_LIVE_CHANGE',checker_version=actual)
(out/'result.json').write_text(json.dumps(plan,indent=2),encoding='utf8');print(out)
