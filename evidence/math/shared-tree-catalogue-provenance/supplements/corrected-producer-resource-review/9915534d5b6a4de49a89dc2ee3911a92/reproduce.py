"""Replay bounded adapter-only probes against the retained module or argv[1]."""
from pathlib import Path
import importlib.util
import sys
import json
import hashlib

HERE=Path(__file__).resolve().parent
ROOT=HERE
PRIVATE=HERE
sys.path.insert(0,str(PRIVATE/'src'))
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
source=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else HERE/'src/oma/routing/shared_tree_proposals.py'
p=load('reviewed_adapter',source)
fixture=load('retained_fixture',HERE/'test_shared_tree_proposals.py');fixture.p=p
r,s,c=fixture.fixture()
seen=[];budget=p._Budget(2000,seen.append)
for _ in range(10):budget.use(129)
polls={'work':budget.work,'callbacks':seen}
budget=p._Budget(2000000,None)
p._snapshot({'requirements':r,'search':s,'context':c},budget,2097152)
limit=budget.work+1
boundary=p.compile_shared_tree_proposals(r,s,context=c,max_work=limit)
r2,s2,c2=fixture.fixture();r2['diameter_m']='0.1'
generated=p.build_connector_catalogue(r2,s2,context=c2)
section={'status':generated['status'],'reason':generated.get('reason')}
if generated['status']=='CATALOGUE_PROPOSED':
    section['catalogue_section']=generated['catalogue']['section']
    section['fabrication_manifest']=next(iter(generated['connector_macros'].values()))['certificate']['manifest']
print(json.dumps({'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
    'polling_jump':polls,'exact_remaining_work':{'limit':limit,'result':boundary},
    'decimal_string_dimension':section,'scope':'Adapter-only; no native or Store acceptance action'},indent=2))
