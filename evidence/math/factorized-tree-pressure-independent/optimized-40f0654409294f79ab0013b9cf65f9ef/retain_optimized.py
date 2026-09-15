from pathlib import Path
import hashlib,json,shutil,uuid
S=Path(__file__).resolve().parent
R=next(p for p in S.parents if (p/'AGENTS.md').exists())
N=R/'.oma/development/factorized-tree-pressure/native-model-probes/cc7cfcc9e3af4db3bf6c6165d64eb978'
O=R/'evidence/math/factorized-tree-pressure-independent'/('optimized-'+uuid.uuid4().hex);O.mkdir(parents=True)
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def d(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf8')
mapping=[]
for old,label in [(S/'optimized-delta/2c999e3ca56c4981912700c914ce58a3','peer'),(N/'src','source'),(N/'7','original-seven'),(N/'8','original-eight')]:
    for p in sorted(old.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts:continue
        q=O/label/p.relative_to(old);q.parent.mkdir(parents=True,exist_ok=True);before=h(p);shutil.copyfile(p,q);assert h(p)==h(q)==before
        mapping.append({'original_path':str(p),'path':q.relative_to(O).as_posix(),'sha256':before})
shutil.copyfile(__file__,O/'retain_optimized.py')
(O/'README.md').write_text('''# Independent indexed-polynomial and service-proposal delta

The `peer/result.json` audit passed on the exact cc7 snapshot. Indexed reconstruction keeps every declared coefficient identity separate. Complete factorized certificates for the unchanged five-, seven- and eight-sink models/boxes are byte-identical to the reviewed bc37 implementation. New factorized module SHA: 0f07eec6d038efea629a257505adfd4d0650400a3194161d841cae130e582d81. New adapter SHA: 6a5603336f541348df935af8773c05473eac329407c549a27c3cbae746b45ca2.

The eight-sink full envelope verifier passed with all producers disabled. It used 1,164,212 work units; that exact budget passed and one fewer returned UNKNOWN. A service altered only on the proposal call was rejected after the independent consumer recomputed service. Coherently resealed forged local polynomial and global proof packets also returned UNKNOWN without certification. Removing the producer's redundant prechecks therefore did not remove the mandatory final independent local/global/physical-model/service gates in these bounded tests.

These are pure checks of retained native-metric models, not new native geometry runs or seven/eight-sink acceptance evidence. Original physical data and query boxes were unchanged. Root's native integration remains separate. The prior independent theorem/native-five evidence remains unchanged in sibling d607e02c01ab48c888532cbc4f6e554e. Exact probe inputs, executed peer script, both proof packets and frozen source are copied here; historical absolute references can be relocated using public-mapping.json.
''',encoding='utf8')
d(O/'public-mapping.json',{'files':mapping})
rows=[{'path':p.relative_to(O).as_posix(),'bytes':p.stat().st_size,'sha256':h(p)} for p in sorted(O.rglob('*')) if p.is_file()]
d(O/'files.json',{'files':rows,'excluded':['files.json','handoff.json']})
for row in rows:assert h(O/row['path'])==row['sha256']
result={'status':'INDEPENDENT_OPTIMIZED_PRESSURE_DELTA_PASS','path':str(O),'files':len(rows),'bytes':sum(x['bytes'] for x in rows),'index_sha256':h(O/'files.json'),'native_geometry_rerun':False}
d(O/'handoff.json',result);print(json.dumps(result))
