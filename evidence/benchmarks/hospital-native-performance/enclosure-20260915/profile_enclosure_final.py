from pathlib import Path
import hashlib,json,time
import ifcopenshell
from oma.ifc.enclosure import ExactIfcEncloser
from oma.ifc import enclosure
STAGE=Path(__file__).resolve().parent
ROOT=next(p for p in STAGE.parents if (p/'AGENTS.md').is_file())
source=ROOT/'data/ifc-bench/projects/west_riverside_hospital/arc_ifc4.ifc'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
baseline=json.loads((STAGE/'enclosure-profile-outputs.json').read_text())
original=json.loads((STAGE/'enclosure-profile-results.json').read_text())
assert sha(source)==original['source_sha256']
code=Path(enclosure.__file__).read_bytes();(STAGE/'enclosure-final.py').write_bytes(code)
model=ifcopenshell.open(str(source));reader=ExactIfcEncloser(source,model,vertex_hull_completion=True)
start=time.monotonic();checked=[]
for expected in baseline:
    result=reader.enclose_product(model.by_id(expected['product_step_id']));result.pop('checker_code_sha256')
    assert result==expected,expected['product_step_id']
    checked.append(result)
seconds=time.monotonic()-start
assert Path(enclosure.__file__).read_bytes()==code
result={'status':'ALL_200_ORIGINAL_CERTIFICATES_IDENTICAL','source_sha256':sha(source),'source_records':len(reader.raw.index),
    'before_code_sha256':original['before_code_sha256'],'after_code_sha256':hashlib.sha256(code).hexdigest(),
    'baseline_outputs_sha256':sha(STAGE/'enclosure-profile-outputs.json'),
    'products':len(checked),'before_seconds':original['timings'][0]['product_seconds'],'after_seconds':seconds,
    'speedup':original['timings'][0]['product_seconds']/seconds,
    'scope':'Same200 actualsourceproducts; exactcertificatefields exceptimplementationidentity. Previous retained baseline timing; no wholehospital clearance claim.'}
(STAGE/'enclosure-final-profile.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result),flush=True)
