"""Retain finished private experiments, without rerunning native work."""
from pathlib import Path
import gzip,hashlib,json,shutil,uuid
STAGE=Path(__file__).resolve().parent;ROOT=next(p for p in STAGE.parents if (p/'AGENTS.md').exists())
PEER=ROOT/'evidence/math/hospital-prerequisite-review/786fd7b9ef6648c8b05ec1ee8f425fdf'
OUT=ROOT/'evidence/benchmarks/hospital-native-performance'/uuid.uuid4().hex;OUT.mkdir(parents=True)
def sha(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf8'))
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf8')
old_index=read(STAGE/'handoff/ac5b2fc6a720436e989adda774c065b7/index.json')
for row in old_index['files']:
    p=STAGE/row['path'];assert sha(p)==row['sha256'] and p.stat().st_size==row['bytes']
peer_index=read(PEER/'file-index.json')
assert all(sha(PEER/p)==h for p,h in peer_index.items())
assert read(PEER/'result.json')['tests']==6 and read(PEER/'result.json')['status']=='PASS'
assert read(STAGE/'validation/80997a76c2694cc385db89872d8b6afe/result.json')['counts']=={'tests':140,'failure':0,'error':0,'skipped':0}
source_decl=read(STAGE/'source-declaration.json');mapping=[]
def retain(source,relative,compress=False):
    original_sha=sha(source);target=OUT/relative;target.parent.mkdir(parents=True,exist_ok=True)
    data=source.read_bytes()
    if compress:
        target=target.with_name(target.name+'.gz');target.write_bytes(gzip.compress(data,compresslevel=9,mtime=0))
        assert gzip.decompress(target.read_bytes())==data
    elif target.exists():assert target.read_bytes()==data
    else:shutil.copyfile(source,target)
    assert sha(source)==original_sha
    mapping.append({'original_path':str(source),'retained_path':target.relative_to(OUT).as_posix(),
        'encoding':'gzip' if compress else 'identity','original_bytes':len(data),'original_sha256':original_sha,'retained_sha256':sha(target)})
for source in sorted(STAGE.rglob('*')):
    if source.is_file() and not {'__pycache__','.pytest_cache'}.intersection(source.relative_to(STAGE).parts):
        assert not source.is_symlink()
        retain(source,Path('performance')/source.relative_to(STAGE),source.suffix=='.brep')
# Preserve the peer's declared exact inventory. Its duplicate112 source files
# map to the already retained byte-identical private runtime; no duplicate
# temporary IFC directories, caches, or unindexed data trees are copied.
for relative in sorted(set(peer_index)|{'file-index.json'}):
    source=PEER/relative
    if relative.startswith('src/'):
        target=Path('performance')/relative
        assert sha(source)==source_decl['private_files'][relative.removeprefix('src/')]
    else:target=Path('independent-peer')/relative
    retain(source,target)
write(OUT/'public-mapping.json',mapping)
arc=ROOT/'data/ifc-bench/projects/west_riverside_hospital/arc_ifc4.ifc'
assert sha(arc)=='230afa4d72a59c9ce18cdd9a7bc7c5c3e409a46078de6e14b19741b4cf92cf09'
assert sha(ROOT/'src/oma/ifc/cad.py')==source_decl['base_files']['oma/ifc/cad.py']
write(OUT/'governing-hospital-results.json',{'arc_original_sha256':sha(arc),
    'full_federation':'evidence/benchmarks/hospital-generated-tree/full-federation-1e87dd6ad9af48b5962cd500603fdfdc/handoff.json',
    'architecture_only':'evidence/benchmarks/hospital-generated-tree/architecture-d3e1be8f981146fcadede8107addadbe/handoff.json',
    'original_ifc_archives':'The exact originals and licenses are already retained under those handoffs; no duplicate imported Store or full IFC copied here.',
    'full_federation_result':'MISSING_INPUTS_UNRESOLVED_ALIGNMENT_NO_CANDIDATE',
    'architecture_only_result':'UNKNOWN_TIMEOUT_1800_SECONDS_NO_CLEARANCE_REPORT_ACCEPTANCE_OR_EXPORT'})
(OUT/'README.md').write_text('''# Hospital native performance: bounded private experiment

The governing hospital outcomes remain unchanged: the seven-discipline federation lacks a verified alignment, and the separate ARC-only workflow timed out after 1,800 seconds without a complete native clearance report, acceptance or export.

The initial90-second observer emitted736 of14,409 represented ARC products. Native inspection and shell promotion dominated the observed serial stages. A private reorder defers expensive topology validation until the existing complete-solid prerequisites pass. A matching90-second observer emitted748 products. This does not establish a material whole-loader or whole-hospital speedup.

On20 retained actual native BReps (the first12 plus eight observed slow products), two alternating raw-inspection rounds took11.825 seconds before and0.291 seconds after. Promotion plus final solid inspection took21.0 and21.3 seconds respectively. Every raw result tuple and promotion disposition matched. This deliberately chosen sample is not a corpus performance estimate.

The private change passed140 focused cases and six independent loader/inventory/cancellation cases. It changes the failure path when an old analyzer would throw on a non-solid shape: the existing separately checked promotion or exact support enclosure may then run. Successful native-solid predicates and complete product accounting remain mandatory. The private CAD change is not integrated into the root backend.

A separate90-second exact-enclosure-first observation completed707 products:573 checked enclosures and134 UNKNOWN. No lazy exclusion pipeline or reduced obstacle denominator was introduced.

All initial harness failures are retained: the observer's non-JSON iterator return, the missing supervisor build environment before launch, and the missing copied network test fixture (139 passes/one harness failure, followed by140 passes on unchanged app source). The missing-environment attempt has its original declaration/scripts and the contemporaneous summary; no raw stderr file was available for that attempt.

The complete private112-file source, exact scripts, observations, tests, peer-declared artifacts and20 BRep samples are retained. BReps are losslessly gzip-compressed with decoded SHA bindings; duplicated peer runtime sources map to the same retained files. Caches, peer temporary/unindexed data, full Store copies and already-backed-up full IFCs are excluded. `public-mapping.json` preserves original absolute provenance and each retained encoding. Run `python verify.py` for standard-library byte/index verification only; it performs no native geometry or tests.
''',encoding='utf8')
verify='''from pathlib import Path
import gzip,hashlib,json
root=Path(__file__).resolve().parent
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
index=json.loads((root/'files.json').read_text());rows=index['files']
assert len(rows)==len({r['path'] for r in rows})
assert {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}=={r['path'] for r in rows}|{'files.json','handoff.json'}
for row in rows:
    p=root/row['path'];assert p.resolve().is_relative_to(root) and not p.is_symlink()
    assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
for row in json.loads((root/'public-mapping.json').read_text()):
    p=root/row['retained_path'];assert sha(p)==row['retained_sha256']
    data=gzip.decompress(p.read_bytes()) if row['encoding']=='gzip' else p.read_bytes()
    assert len(data)==row['original_bytes'] and hashlib.sha256(data).hexdigest()==row['original_sha256']
handoff=json.loads((root/'handoff.json').read_text());assert sha(root/'files.json')==handoff['index_sha256']
print(json.dumps({'status':'EXACT_RETAINED_BYTES_AND_MAPPING_PASS','files':len(rows),'original_mappings':len(json.loads((root/'public-mapping.json').read_text()))}))
'''
(OUT/'verify.py').write_text(verify,encoding='utf8')
files=[p for p in OUT.rglob('*') if p.is_file()]
index={'schema':'oma.indexed-private-performance-evidence/1','files':[{'path':p.relative_to(OUT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(files)]}
write(OUT/'files.json',index)
handoff={'status':'HOSPITAL_PRIVATE_PERFORMANCE_EVIDENCE_RETAINED_NO_HOSPITAL_VERIFICATION',
    'index_sha256':sha(OUT/'files.json'),'files':len(files),'retained_bytes':sum(r['bytes'] for r in index['files']),
    'original_mappings':len(mapping),'native_brep_samples':sum(r['encoding']=='gzip' for r in mapping),
    'private_cad_sha256':source_decl['private_files']['oma/ifc/cad.py'],'root_cad_sha256':sha(ROOT/'src/oma/ifc/cad.py'),
    'private_only_not_integrated':True,'full_loader_90s_emitted_before_after':[736,748],
    'sample_promotion_seconds_before_after':[20.97329110004648,21.303473399981158],
    'focused_tests_passed':140,'independent_tests_passed':6,'native_or_test_rerun':False,'original_inputs_modified':False}
write(OUT/'handoff.json',handoff)
for row in index['files']:assert sha(OUT/row['path'])==row['sha256']
print(json.dumps({'directory':str(OUT),**handoff},indent=2))
