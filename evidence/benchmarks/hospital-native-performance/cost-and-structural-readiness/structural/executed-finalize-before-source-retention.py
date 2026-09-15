"""Close the bounded read-only audit; retains hashes rather than original IFC copies."""
from pathlib import Path
import hashlib,json,datetime
ROOT=Path(__file__).resolve().parents[3];STAGE=Path(__file__).resolve().parent
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8'))
base=STAGE/'attempts/49cfce2e41154622b3bf1453f9f14f00'
app=load(base/'app-sources.json')
actual={str(p.relative_to(ROOT/'src')).replace('\\','/'):sha(p) for p in (ROOT/'src/oma').rglob('*.py')}
assert actual==app and len(app)==114
adjacent=load(base/'adjacent-input-files.json')
data=ROOT/'data/ifc-bench/projects/west_riverside_hospital'
assert {p.name for p in data.iterdir() if p.is_file()}==set(adjacent)
assert all(sha(data/name)==v['sha256'] and (data/name).stat().st_size==v['bytes'] for name,v in adjacent.items())
results={
 'inventory':'attempts/49cfce2e41154622b3bf1453f9f14f00/result.json',
 'assignments':'details/6641d905bea44776ab251cc68f40175c/result.json',
 'backend_peer':'backend-peer/result.json',
 'authored_steel_volumes':'quantity-review/f0536fb6e0cb42779040f2f317ae6258/result.json',
 'nominal_bill_peer':'bill-peer/08c64febd0c544d9a7baced19b481e8a/result.json'}
assert load(base/'result.json')['all_inputs_and_application_unchanged']
assert load(STAGE/results['authored_steel_volumes'])['all_inputs_unchanged']
assert load(STAGE/results['nominal_bill_peer'])['all_inputs_unchanged']
paths=sorted(p for p in STAGE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='handoff.json')
mapping={str(p.relative_to(STAGE)).replace('\\','/'):{'sha256':sha(p),'bytes':p.stat().st_size} for p in paths}
handoff={'schema':'oma.hospital-structural-readiness-audit/1','status':'READ_ONLY_SOURCE_AND_BACKEND_READINESS_AUDIT_COMPLETE','closed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'application_checkpoint':'06aa865600b4ab2dc8f42f77b2cb5f82816dec99bbf8a1ff5f67673fb44c1949','source_python_files':114,'adjacent_supplied_files':len(adjacent),'all_current_source_and_adjacent_original_inputs_unchanged':True,'structural_safety':'NOT_CERTIFIED','structural_redesign_verification_backend':'NOT_IMPLEMENTED_IN_AUDITED_CHECKPOINT','result_records':{k:{'path':v,'sha256':sha(STAGE/v)} for k,v in results.items()},'findings':'FINDINGS.md','retained_files':mapping,'file_count':len(mapping),'bytes':sum(v['bytes'] for v in mapping.values()),'scope':'IFC4/IFC2X3 supplied structural-file inventory, literal material/classification/quantity review, independent current backend capability review, and symbolic unpriced bill corroboration. No source/Git/UI/live/Store edit, native CAD rerun, structural design calculation, rate estimate or structural safety/appearance acceptance.'}
(STAGE/'handoff.json').write_text(json.dumps(handoff,indent=2),encoding='utf-8')
assert all(sha(STAGE/p)==v['sha256'] for p,v in mapping.items())
print(json.dumps({'handoff':str(STAGE/'handoff.json'),'sha256':sha(STAGE/'handoff.json'),'files':len(mapping),'bytes':handoff['bytes']}))
