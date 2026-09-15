"""Append-only public evidence retention; no application or Store writes."""
from pathlib import Path
import hashlib,json,shutil,uuid
STAGE=Path(__file__).resolve().parent;ROOT=next(p for p in STAGE.parents if (p/'AGENTS.md').exists())
AUDIT=STAGE/'final-packet-guard/3a8050a305fb4c63b718a9a22d7a4bc1'
FROZEN=ROOT/'.oma/development/factorized-tree-pressure/native-model-probes/4623a210ad0447ddaeda012624a080d0'
OUT=ROOT/'evidence/math/factorized-tree-pressure-independent'/('final-packet-'+uuid.uuid4().hex);OUT.mkdir(parents=True)
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf8')
mapping=[]
def copy(source,target):
    assert source.is_file() and not source.is_symlink();target.parent.mkdir(parents=True,exist_ok=True)
    before=sha(source);shutil.copyfile(source,target);assert sha(target)==sha(source)==before
    mapping.append({'original_path':str(source),'retained_path':target.relative_to(OUT).as_posix(),'sha256':before})
for source in AUDIT.iterdir():
    if source.is_file():copy(source,OUT/'review'/source.name)
for source in (FROZEN/'src').rglob('*.py'):copy(source,OUT/'runtime/src'/source.relative_to(FROZEN/'src'))
for count in ('7','8'):
    for name in ('boundary','network','metrics','context','model','box','envelope'):
        copy(FROZEN/count/(name+'.json'),OUT/'inputs'/count/(name+'.json'))
copy(Path(__file__),OUT/'retain.py')
write(OUT/'public-mapping.json',mapping)
(OUT/'README.md').write_text('The final producer returns a bounded detached copy of the successful consumer result and checks the entire producer packet after the last callback. Independent late local/global/service/caller-input mutations fail closed; a held consumer-result alias cannot change the detached returned service; cancellation identity and late token budgets remain enforced.\n\nThe unchanged seven/eight-sink certificates pass at 1,268,666 and 1,882,615 work units under the existing two-million cap. Eight-sink exact-work succeeds and one less returns UNKNOWN. A separate full consumer replay with producers disabled passes. This is a pure proof/native-metric packet audit; no native geometry, acceptance or export was rerun. The actual native identities remain in their original receipts.\n\nThe exact executed review script, complete frozen Python source and both exact input/proof fixtures are retained. public-mapping.json preserves original absolute provenance and the corresponding portable files.\n',encoding='utf8')
files=[p for p in OUT.rglob('*') if p.is_file()]
index={'schema':'oma.independent-evidence-index/1','files':[{'path':p.relative_to(OUT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(files)]}
write(OUT/'index.json',index)
handoff={'status':'FINAL_PRESSURE_PACKET_GUARD_PEER_HANDOFF_COMPLETE','index_sha256':sha(OUT/'index.json'),
    'files':len(files),'logical_bytes':sum(r['bytes'] for r in index['files']),'review_sha256':sha(OUT/'review/result.json'),
    'adapter_sha256':sha(OUT/'runtime/src/oma/routing/coupled_tree_pressure.py'),'source_changed':False,'native_geometry_rerun':False}
write(OUT/'handoff.json',handoff)
for row in index['files']:assert sha(OUT/row['path'])==row['sha256']
print(json.dumps({'directory':str(OUT),**handoff},indent=2))
