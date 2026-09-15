"""Retain exact completed original-native full f73 validation; no test rerun."""
import hashlib,json,shutil,sys
from pathlib import Path
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
ORIGIN=ROOT/'.oma/development/factorized-tree-pressure/combined-validation/d6d1204384b84bc6b0a5c5e47c5540ad'
OUT=ROOT/'evidence/release/compact-tree-original-full-d6d1204384b8'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
sys.path.insert(0,str(ROOT/'scripts'))
from native_package_evidence import verify_test_snapshot,verify_suite_xml
r=read(ORIGIN/'result.json');inputs=read(ORIGIN/'inputs.json')['files'];nodes=read(ORIGIN/'test-nodes.json')
assert r['status']=='PASS' and r['passed']==len(nodes)==3275 and r['returncode']==0
assert r['source_unchanged'] and r['inputs_unchanged'] and r['native_unchanged']
assert sha(ORIGIN/'test-nodes.json')==r['exact_collected_nodes_sha256']
assert sha(ORIGIN/'tests.xml')==r['test_xml_sha256']
accounting=verify_suite_xml(ORIGIN/'tests.xml',nodes,direct_interpreter=False)
inventory=verify_test_snapshot(r['snapshot'],inputs,allow_generated_evidence=True)
assert len(inputs)==305 and len(inventory['generated_evidence'])==6
source=Path(r['source_directory'])
assert {p.relative_to(source).as_posix():sha(p) for p in source.rglob('*.py')}==r['source_files']
assert len(r['source_files'])==114
OUT.mkdir(exist_ok=False)
def copy(p,target):
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target);assert sha(p)==sha(target)
for name,digest in inputs.items():
    p=Path(r['snapshot'])/name;assert sha(p)==digest;copy(p,OUT/'snapshot'/name)
for name,digest in r['source_files'].items():
    p=source/name;assert sha(p)==digest;copy(p,OUT/'src'/name)
for name,digest in inventory['generated_evidence'].items():
    p=Path(r['snapshot'])/name;assert sha(p)==digest;copy(p,OUT/'derived-outputs'/name)
for p in ORIGIN.iterdir():
    if p.is_file():copy(p,OUT/p.name)
copy(Path(__file__),OUT/'executed-retention.py')
verify_test_snapshot(OUT/'snapshot',inputs)
assert {p.relative_to(OUT/'src').as_posix():sha(p) for p in (OUT/'src').rglob('*.py')}==r['source_files']
handoff={'status':'ORIGINAL_F73_3275_EXACT_PUBLIC_RETENTION_PASS','original_receipt':str(ORIGIN/'result.json'),
    'original_receipt_sha256':sha(ORIGIN/'result.json'),'checker_version':r['checker_version'],
    'source_files':114,'input_files':305,'nodes':3275,'accounting':accounting,'derived_outputs':6,
    'snapshot_inputs':inputs,'source_manifest':r['source_files'],'test_nodes_sha256':sha(OUT/'test-nodes.json'),
    'test_xml_sha256':sha(OUT/'tests.xml'),'native_environment_sha256':sha(OUT/'native-environment.json'),
    'scope':'Exact114 application and305 input bytes,3275 node identities and six declared test outputs. Both current package drivers are included in the frozen305 inputs. No test rerun or original mutation.',
    'retained_files':{p.relative_to(OUT).as_posix():sha(p) for p in OUT.rglob('*') if p.is_file()}}
(OUT/'handoff.json').write_text(json.dumps(handoff,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'directory':str(OUT),'handoff_sha256':sha(OUT/'handoff.json'),'files':len(handoff['retained_files'])}))
