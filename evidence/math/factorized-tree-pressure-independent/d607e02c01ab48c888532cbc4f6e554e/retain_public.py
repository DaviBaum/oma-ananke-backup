"""Publish exact independent math and retained native-workflow review evidence."""
from pathlib import Path
import hashlib,json,shutil,uuid
STAGE=Path(__file__).resolve().parent
ROOT=next(p for p in STAGE.parents if (p/'AGENTS.md').exists())
SOURCE=ROOT/'.oma/development/factorized-tree-pressure/runtimes/73d7eed7accfd706f9972e1548e750009127e24c6106cc25d98c812239a836ee/src'
OUT=ROOT/'evidence/math/factorized-tree-pressure-independent'/uuid.uuid4().hex;OUT.mkdir(parents=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf8')
mapping=[]
def cp(p,d):
    h=sha(p);d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,d);assert sha(p)==sha(d)==h
    mapping.append({'original_path':str(p),'path':d.relative_to(OUT).as_posix(),'sha256':h})
for origin,label in [(STAGE/'handoffs/bf2602ded73a41a08b0039ae982ea265','kernel-peer'),(STAGE/'native-replays','native-replays'),
    (STAGE/'fallback-gates/9e986d6912a94315804d3d847c11eeea','fallback-review')]:
    for p in sorted(origin.rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts:cp(p,OUT/label/p.relative_to(origin))
for p in sorted(SOURCE.rglob('*.py')):cp(p,OUT/'native-source'/p.relative_to(SOURCE))
for name in ('result.json','runner.py','tests.xml','pytest.log'):
    cp(ROOT/'.oma/development/factorized-tree-pressure/validation/027d04f6bea045f3970c29ce9c644247'/name,OUT/'root-native-validation'/name)
cp(Path(__file__),OUT/'retain_public.py')
(OUT/'README.md').write_text('''# Independent factorized pressure and native five-sink review

The independent review passed. No production source, authored physical requirement, original IFC or original Store was changed, and no native geometry run was repeated.

`kernel-peer/` retains the Fraction-only polynomial/interval oracle and 41 producer-disabled certificate gates against the frozen `bc37fb0d` module. The exact original five-sink model and ±1% box certify with infinity norm bound 0.08848603562531682 and smallest strict inclusion margin 6.3931223811050825e-6. Complete exact fractions, shared-parameter/signed-weight checks and the distinct-parameter counterexample are included.

`native-replays/7b7374e18b4c4d1c8352b890e011251d/` audits the actual native workflow on frozen application `73d7eed7accfd706f9972e1548e750009127e24c6106cc25d98c812239a836ee`. The first candidate was rejected for positive native common volume with an original obstacle. Normal selection chose candidate `9246175acf184b3a93b19bf3f27e37a8`, accepted at revision 2. Fresh exported candidate `401c675192fe455a98eb6251572109e5` passed under the same build. Both passing reports account for 17 components, 38 physical ports, two original obstacles, 34 source pairs, 136 unique component pairs and five deliveries. All 49 original parsed records were checked by the retained native semantics.

The selected and exported IFC bytes have SHA `c9197bc8376d466ed1e9e7b4bb164b6b855e9ec67196890a1b457c7707d3ff67`. The audit rehashes those exact files and sources, verifies report/state/mission/rule/execution bindings, original revision lineage and nine export-release bindings, and independently reconstructs every metric radius/length/measured-port enclosure from native receipts. All local/global/full-service certificate consumers were replayed with producer routines disabled. The original physical coefficient/head model and original flow box remain identical after export; identity roots change to bind the fresh candidate. Every original Store file and frozen Python source remained unchanged.

Two initial read-only audit wrapper errors are retained. The first passed a materialization-only transform field to the stricter network schema. The second incorrectly demanded identical decimal spelling for an elbow cap at 0.24999999999999997 and its checked port at 0.25. The corrected audit verifies the identity transform separately, authenticates measured port ownership/cap correspondence within the declared tolerance, and checks exact metric intervals around those measured ports. Neither was a native failure; neither required geometry regeneration.

`fallback-review/` has nine controlled dispatch tests on these saved physical inputs. Resource exhaustion, invalid input and unrecognized failures do not invoke the new method. Only the two explicit failed sufficient-test reasons trigger it, with the identical model and box and a strictly decreasing shared work allowance. Independent local/global verification still runs before service authority. The stubs test dispatch; the native PASS evidence remains the separately retained actual reports and producer-disabled replays.

The 46-case parent validation receipt is copied for context. The native-source tree binds this integration separately from the earlier kernel-only source. This is a bounded analytic five-sink workflow, not hospital routing, arbitrary-network coverage or a claim that every positive box can be certified. Hospital outcomes are retained separately as unresolved seven-source alignment and architecture-only native timeout.

`files.json` and `handoff.json` bind every retained byte. The nested kernel handoff inventory is preserved unchanged. Historical absolute paths remain provenance; `public-mapping.json` maps each copied artifact to this portable location. No live database or native cache is copied.
''',encoding='utf8')
dump(OUT/'public-mapping.json',{'files':mapping})
rows=[{'path':p.relative_to(OUT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(OUT.rglob('*')) if p.is_file()]
dump(OUT/'files.json',{'files':rows,'excluded':['files.json','handoff.json']})
for row in rows:assert sha(OUT/row['path'])==row['sha256']
nested=json.loads((OUT/'kernel-peer/files.json').read_text(encoding='utf8'))
for row in nested['files']:assert sha(OUT/'kernel-peer'/row['path'])==row['sha256']
handoff={'status':'INDEPENDENT_FACTOR_PRESSURE_AND_NATIVE5_REVIEW_PASS','path':str(OUT),'files':len(rows),
    'bytes':sum(r['bytes'] for r in rows),'index_sha256':sha(OUT/'files.json'),'nested_index_rechecked':True,
    'original_source_or_store_changes':False,'native_geometry_rerun':False}
dump(OUT/'handoff.json',handoff);print(json.dumps(handoff))
