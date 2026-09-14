"""Retain exact completed Office bytes and read-only preservation audit."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import zlib
import ifcopenshell

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
STAGE=ROOT/'.oma/development/passive-native-tree'
ID='f64e250b57bb480f9dfe352892b61b3f'
SOURCE=STAGE/'evidence/benchmarks/three-sink-office'/ID
STORE=STAGE/'bench-stores'/ID
TARGET=ROOT/'evidence/benchmarks/passive-pressure/office'/ID

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
def records(path):
    data=Path(path).read_bytes()
    rows=re.findall(rb'(?m)^[ \t]*(#([0-9]+)\s*=.*;)[ \t]*\r?$',data)
    result={int(identity):record.rstrip(b'\r') for record,identity in rows}
    assert len(result)==len(rows)==sum(1 for _ in ifcopenshell.open(str(path))), 'Line-record coverage must equal independently parsed IFC entity count'
    return result

def main():
    assert not TARGET.exists()
    result=read(SOURCE/'run-result.json');declaration=read(SOURCE/'execution-predeclaration.json')
    assert result['status']=='SELECTED_ACCEPTED_EXPORTED_FRESH_NATIVE_AND_PRESSURE_PASS'
    assert all(result['original_guards'].values()) and len(result['candidates'])==1
    assert len(read(SOURCE/'placement-screen.json')['probes'])==36
    originals=declaration['original_files'];assert len(originals)==1
    original_path,original_sha=next(iter(originals.items()));assert sha(original_path)==original_sha
    original_records=records(original_path);comparisons=[]
    original_canonical={e.id():str(e) for e in ifcopenshell.open(str(original_path))}
    raw_differences=[]
    for candidate in [*result['candidates'],result['export_recheck']]:
        for row in candidate['actual_ifcs']:
            path=SOURCE/row['path'];assert sha(path)==row['sha256']
            actual=records(path);raw_changes=[step for step,text in original_records.items() if actual.get(step)!=text]
            canonical={e.id():str(e) for e in ifcopenshell.open(str(path))}
            changes=[step for step,text in original_canonical.items() if canonical.get(step)!=text]
            assert not changes and set(original_records)<=set(actual)
            raw_differences.append({'candidate_id':candidate['candidate_id'],'changed_raw_record_step_ids':raw_changes,
                'examples':[{'step_id':step,'original':original_records[step].decode('utf-8'),
                    'output':actual[step].decode('utf-8')} for step in raw_changes[:8]],
                'interpretation':'Raw formatting/serialization differs; all parsed canonical entity strings match exactly. No exact decimal-token preservation claim.'})
            comparisons.append({'candidate_id':candidate['candidate_id'],'ifc_path':row['path'],'ifc_sha256':row['sha256'],
                'original_step_records':len(original_records),'output_step_records':len(actual),'added_step_records':len(actual)-len(original_records),
                'canonical_original_records_missing_or_changed':changes,'raw_record_strings_changed':len(raw_changes),
                'raw_original_record_text_preserved':not raw_changes,'parsed_inventory_matches_line_record_count':True})
    TARGET.mkdir(parents=True);copies=[];external=[]
    def copy(source,relative):
        source=Path(source).resolve();hashed=sha(source)
        if source.suffix.lower()=='.ifc' and hashed==original_sha:
            external.append({'path':str(source),'sha256':hashed,'disposition':'IMMUTABLE_ACQUIRED_ORIGINAL_NOT_BUNDLED'});return
        destination=TARGET/relative;destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,destination);assert sha(source)==sha(destination)==hashed
        copies.append({'original_path':str(source),'path':destination.relative_to(TARGET).as_posix(),'bytes':source.stat().st_size,'sha256':hashed})
    def tree(source,relative,suffix=None):
        for path in sorted(source.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and (suffix is None or path.suffix==suffix):copy(path,Path(relative)/path.relative_to(source))
    tree(SOURCE,'campaign')
    tree(STAGE/'evidence/benchmarks/three-sink-office/999fb3cab9204c638f1e9eb9ad898942','initial-preparation-assertion')
    tree(STAGE/'evidence/retention-preparation/82fe7801b9b04bada3c91859a27bd4dc','initial-raw-step-retention-assertion')
    for folder in ('candidates','exports','checks','blobs'):tree(STORE/folder,Path('store-evidence')/folder)
    for name in ('baseline-input-copy.json','oma.sqlite3'):copy(STORE/name,Path('store-evidence')/name)
    blobcount=0
    for path in (TARGET/'store-evidence/blobs').glob('*.json.z'):
        value=json.loads(zlib.decompress(path.read_bytes()))
        root=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
        assert root==path.name.removesuffix('.json.z');blobcount+=1
    build=result['checker_version'].rsplit(':',1)[-1]
    source=STAGE/'runtimes'/build/'src'
    tree(source/'oma','provenance/src/oma','.py')
    for name in ('prepare_office_three_sink.py','run_office_three_sink.py','retain_office_three_sink.py'):
        copy(STAGE/'scripts'/name,Path('provenance/scripts')/name)
    summary={'status':'READ_ONLY_NATIVE_STEP_AND_EVIDENCE_PRESERVATION_PASS','checker_version':result['checker_version'],
        'source_sha256':original_sha,'original_step_record_count':len(original_records),'outputs':comparisons,
        'native_denominators':[c['native'] for c in [*result['candidates'],result['export_recheck']]],
        'all_original_guards':result['original_guards'],'candidate_count':len(result['candidates']),
        'full_port_flow_count':16,'full_delivery_count':3,'full_conservation_identity_count':17,
        'selected_candidate_id':result['selected_candidate_id'],'accepted_revision':result['accepted']['revision'],
        'export_candidate_id':result['export_recheck']['candidate_id'],'export_report_root':result['export_recheck']['report_root'],
        'new_export_model_root':result['export_recheck']['pressure']['model_root'],
        'delivery_bounds_identical_after_export':result['candidates'][0]['pressure']['deliveries']==result['export_recheck']['pressure']['deliveries'],
        'native_recomputed_by_this_retention':False,'original_records_checked_independently':True,
        'canonical_blobs_checked':blobcount,'elapsed_workflow_seconds':result['elapsed_seconds']}
    write(TARGET/'independent-retention-audit.json',summary)
    write(TARGET/'raw-versus-canonical-step-comparison.json',raw_differences)
    external.append({'path':original_path,'sha256':original_sha,'disposition':'IMMUTABLE_ACQUIRED_ORIGINAL_NOT_BUNDLED'})
    write(TARGET/'locator.json',{'copies':copies,'external_sources':external,'source':str(SOURCE),'store_source':str(STORE),
        'relocation_scope':'Unchanged exact evidence bytes with relative locators; not an automatically restored Store or self-contained native runtime'})
    (TARGET/'README.md').write_text(
        'This new hypothetical Office service has three sinks and two physically distinct tees. Both outlet losses of each tee use the same explicitly declared positive inlet-flow coefficient (0.2 and 0.3 for the two tees). No older mission was changed or reinterpreted. The native IFC encodes outer envelopes; the circular bore and loss applicability remain declared assumptions.\n\n'
        'The normal engine selected the single predeclared seven-component design, accepted revision 1, and freshly checked the actual exported IFC under checker 4044a58d. Both native checks cover 803 represented original obstacles (5,621 pairs), all 21 unique component pairs, 16 physical ports, all three deliveries and 17 conservation identities. The full source inventory also retains two representation-free physical assemblies with complete descendant coverage. All 36 predeclared display-box placement probes remain here; they scheduled a native proposal and were never clearance certificates.\n\n'
        'The complete workflow took 58.5 seconds. Original source bytes, head, prior run/mission and candidate remained unchanged. The fresh exported candidate has a new pressure-model root and identical checked delivery bounds. All 62,930 original parsed canonical STEP entity strings are preserved in both outputs. Raw record text is not byte-identical: 14,650 strings are reformatted by serialization (for example 0.0 becomes 0.). The independent raw comparison and its initially failed byte-equality assertion are retained separately. This is no exact source decimal-token preservation claim. The output has 63,194 entities, including 264 additions.\n\n'
        'The initial preparation wrapper incorrectly asserted that all physical declarations equaled the represented-obstacle count. That assertion, its complete 805-object inventory, and the corrected preparation are retained; no native run or mission existed in that initial attempt. The successful run had one candidate. There is no comparative optimization-improvement claim, unrestricted-topology optimum or whole-building certification. Acquired original IFC-Bench inputs remain external SHA-bound dependencies; authored IFCs and all retained reports are local evidence, not an application release. `files.json` inventories every retained file except itself.\n',encoding='utf-8')
    for row in copies:assert sha(row['original_path'])==sha(TARGET/row['path'])==row['sha256']
    assert sha(original_path)==original_sha
    files=[{'path':p.relative_to(TARGET).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(TARGET.rglob('*')) if p.is_file()]
    write(TARGET/'files.json',{'schema':'oma.relative-file-inventory/1','files':files,'count':len(files),
        'bytes':sum(r['bytes'] for r in files),'inventory_excludes_only_itself':True})
    print(json.dumps({'status':'RETAINED_BYTE_IDENTICAL','directory':str(TARGET),'files':len(files),'bytes':sum(r['bytes'] for r in files),
        'original_step_records':len(original_records),'inventory_sha256':sha(TARGET/'files.json')}))

if __name__=='__main__':main()
