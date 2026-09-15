"""Preserve a partial artifact as diagnostics only, never candidate authority."""
import json,sqlite3,zlib,uuid,shutil
from pathlib import Path
from datetime import datetime,timezone
from oma.store import digest
from oma.ifc.audit import atomic_json,sha256_file
stage=Path(__file__).resolve().parent
root=stage/'stores/2cda40ea47794a7b9335d9cd5774e476'
db=sqlite3.connect((root/'oma.sqlite3').resolve().as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
candidate=dict(db.execute('SELECT * FROM candidates WHERE id=?',('85453f9ad960487297bf0231cd549a79',)).fetchone())
def get(identity):
    result=json.loads(zlib.decompress((root/'blobs'/(identity+'.json.z')).read_bytes()));assert digest(result)==identity;return result
state=get(candidate['state_root']);material=get(state['physical_networks'][0]['geometry_artifact'])
semantic_root='3a4550e673a8e90863fb8aa7f3663ac39e9be0bfb8cf0f62d6c81971d2781a04';semantic=get(semantic_root)
assert semantic['status']=='PASS'
assert {p['ifc_guid'] for p in semantic['parts']}=={p['ifc_guid'] for p in material['added_parts']}
assert sha256_file(Path(material['source_path']))==material['source_sha256']
assert sha256_file(Path(material['export_path']))==material['export_sha256']
out=stage/'observations'/uuid.uuid4().hex;out.mkdir(parents=True);shutil.copyfile(__file__,out/'executed.py')
atomic_json(out/'partial-native-semantics.json',semantic);atomic_json(out/'materialization.json',material)
atomic_json(out/'result.json',{'status':'PARTIAL_NATIVE_SEMANTICS_ARTIFACT_OBSERVED','observed_at':datetime.now(timezone.utc).isoformat(),
    'candidate':candidate,'semantic_root':semantic_root,'new_components':semantic['physical_components'],'ports':semantic['physical_ports'],
    'original_parsed_records_checked':semantic['original_records_checked'],'source_products_converted_count':None,
    'authority':'Diagnostic partial child artifact only. Full source clearance, candidate report and acceptance remain unestablished; no late/partial PASS publication.'})
print(str(out))
