from pathlib import Path
import hashlib
import json
import runpy
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'src'))
Source = runpy.run_path(str(ROOT / 'tests/test_service_takeoff.py'))['Source']
out = Path(__file__).parent
d = out/'occurrence_predefined'; d.mkdir(exist_ok=True)
s = Source(d)
a,_ = s.segment(depth=2)
b,_ = s.segment(depth=2)
a.PredefinedType = 'RIGIDSEGMENT'
b.PredefinedType = 'FLEXIBLESEGMENT'
r = s.run()
result = {'source_sha256':hashlib.sha256((ROOT/'src/oma/ifc/service_takeoff.py').read_bytes()).hexdigest(),
          'authored_predefined_types':{str(a.id()):a.PredefinedType,str(b.id()):b.PredefinedType},
          'eligible_pieces':[{k:p[k] for k in ('step_id','stock_group','stock_kind','ifc_types')} for p in r['pieces']],
          'distinct_groups':len(r['stock_groups'])}
(out/'group-result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
