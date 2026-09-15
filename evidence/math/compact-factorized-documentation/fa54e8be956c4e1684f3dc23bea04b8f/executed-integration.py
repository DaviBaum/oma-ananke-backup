"""Root-reviewed final documentation and examples; never alter runtime inputs."""
from pathlib import Path
import hashlib,json,shutil,uuid
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
STAGE=ROOT/'.oma/development/f73-promotion-documentation'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
h=read(STAGE/'handoff.json');assert h['status']=='FINAL_PRIVATE_F73_DOCUMENTATION_READY'
assert sha(STAGE/'handoff.json')=='6f3e58a717a97d4fe0457b63e5d8215ac9042620b2f8fea0d59c8e8d01a681f4'
for name,digest in h['completed_receipts'].items():assert sha(ROOT/name)==digest
items={name:{'source':STAGE/h['replacement_directory']/name,'after':digest,'before':h['root_files_before'][name]} for name,digest in h['replacement_files'].items()}
examples=ROOT/'.oma/development/factorized-tree-pressure/promotion/examples'
for p in examples.glob('*.json'):
    name='examples/'+p.name;assert not (ROOT/name).exists()
    items[name]={'source':p,'after':sha(p),'before':None}
assert len(items)==10
for name,row in items.items():
    assert sha(row['source'])==row['after']
    assert (sha(ROOT/name) if (ROOT/name).is_file() else None)==row['before'],name
out=ROOT/'evidence/math/compact-factorized-documentation'/uuid.uuid4().hex;out.mkdir(parents=True)
for name,row in items.items():
    if (ROOT/name).is_file():
        target=out/'before'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
history=ROOT/'docs/checkpoint-edf-before-compact.md';assert not history.exists()
history.write_text('# Historical EDF checkpoint before compact/factorized promotion\n\nThe following is the prior checkpoint report. See [PROGRESS.md](PROGRESS.md) for the current runtime.\n\n'+(ROOT/'docs/PROGRESS.md').read_text(encoding='utf-8'),encoding='utf-8')
for name,row in items.items():
    target=ROOT/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(row['source'],target);assert sha(target)==row['after']
shutil.copyfile(STAGE/'handoff.json',out/'reviewed-handoff.json')
shutil.copyfile(STAGE/'final-v2/review.patch',out/'reviewed.patch')
shutil.copyfile(__file__,out/'executed-integration.py')
receipt={'status':'ROOT_REVIEWED_F73_DOCUMENTATION_AND_EXAMPLES_INTEGRATED','source_checkpoint':h['source_checkpoint'],
    'files':{name:row['after'] for name,row in items.items()},'historical_progress':history.relative_to(ROOT).as_posix(),
    'history_sha256':sha(history),'application_source_modified':False,'full_original_math_complete':False,
    'retained_files':{p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file()}}
(out/'handoff.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':receipt['status'],'directory':str(out),'handoff_sha256':sha(out/'handoff.json')}))
