"""Same raw hospital products, complete output comparison before/after project scan fix."""
from pathlib import Path
import gc,hashlib,importlib.util,json,sys,time
import ifcopenshell
from oma.ifc import enclosure
from oma.ifc.inventory import physical_inventory
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
STAGE=Path(__file__).resolve().parent
SOURCE=ROOT/'data/ifc-bench/projects/west_riverside_hospital/arc_ifc4.ifc'
oldpath=STAGE/'enclosure-before.py'
spec=importlib.util.spec_from_file_location('oma.ifc.enclosure_before',oldpath)
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(SOURCE)=='230afa4d72a59c9ce18cdd9a7bc7c5c3e409a46078de6e14b19741b4cf92cf09'
model=ifcopenshell.open(str(SOURCE))
products=[p for p in physical_inventory(model)['products'] if p.Representation is not None][:200]
rows=[];outputs={}
for label,module in [('before',old),('after',enclosure)]:
    start=time.monotonic();reader=module.ExactIfcEncloser(SOURCE,model,vertex_hull_completion=True)
    init=time.monotonic()-start;begin=time.monotonic();results=[]
    for index,product in enumerate(products):
        result=reader.enclose_product(product);result.pop('checker_code_sha256')
        results.append(result)
        if (index+1)%50==0:print(json.dumps({'mode':label,'products':index+1,'seconds':time.monotonic()-begin}),flush=True)
    rows.append({'mode':label,'init_seconds':init,'product_seconds':time.monotonic()-begin,
        'products':len(products),'source_records':len(reader.raw.index),'checked':sum(r['status']=='ENCLOSURE_CHECKED' for r in results)})
    outputs[label]=results;del reader;gc.collect()
assert outputs['before']==outputs['after'],'Complete source support outcomes changed'
result={'status':'SAME_HOSPITAL_SUPPORT_OUTPUTS_PASS','source_sha256':sha(SOURCE),'before_code_sha256':sha(oldpath),
    'after_code_sha256':sha(enclosure.__file__),'timings':rows,'speedup':rows[0]['product_seconds']/rows[1]['product_seconds'],
    'equality_scope':'All certificate fields except checker implementation identity; exact bounds/coverage/status/unknown reasons match',
    'whole_hospital_clearance_claim':False}
(STAGE/'enclosure-profile-results.json').write_text(json.dumps(result,indent=2))
(STAGE/'enclosure-profile-outputs.json').write_text(json.dumps(outputs['after'],indent=2))
print(json.dumps(result),flush=True)
