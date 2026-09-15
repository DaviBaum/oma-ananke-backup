from pathlib import Path
import hashlib,json,sys,uuid
p=Path(__file__).resolve().parent
sys.path[:0]=[str(p/'src'),str(p/'tests')]
from oma.routing.shared_tree_proposals import build_connector_catalogue
from oma.store import digest
from shared_tree_coupled_fixture import fixture
r,s,c=fixture()
out=p/'authored-fixtures'/uuid.uuid4().hex;out.mkdir(parents=True)
for name,value in (('requirements',r),('search',s),('context',c)):
    (out/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
(out/'predeclaration.json').write_text(json.dumps({'input_root':digest({'requirements':r,'search':s,'context':c}),
    'fixture_author_sha256':hashlib.sha256((p/'tests/shared_tree_coupled_fixture.py').read_bytes()).hexdigest(),
    'complete_input_network_trees':0,'scope':'Hypothetical authored pressures and nominal generation only; no native checking'},indent=2)+'\n',encoding='utf8')
generated=build_connector_catalogue(r,s,context=c)
(out/'generated.json').write_text(json.dumps(generated,indent=2)+'\n',encoding='utf8')
print(json.dumps({'path':str(out),'status':generated['status'],'reason':generated.get('reason'),'work':generated['work'],
    'macro_count':len((generated.get('catalogue') or {}).get('connectors',[])),
    'pressures':r['coupled_tree']['sink_total_pressures_pa']}))
