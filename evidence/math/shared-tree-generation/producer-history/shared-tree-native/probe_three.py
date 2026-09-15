from pathlib import Path
import json,sys,time,uuid
p=Path(__file__).resolve().parent
sys.path[:0]=[str(p/'src'),str(p/'tests')]
from oma.build_identity import frozen_environment
from oma.routing.shared_tree_proposals import compile_shared_tree_proposals
from test_shared_tree_proposals import fixture
env=frozen_environment(p)
r,s,c=fixture()
r['sinks'][0]['end_m']=[4,0,3]
r['sinks'].append({'id':'sink-c','demand_id':'demand-c','end_m':[2,3,3],
    'required_flow_m3_s':.001,'available_static_pressure_pa':100})
s['sink_directions']['sink-c']=[0,1,0]
s['tee_instances'][1]['id']='tee-c';s['tee_instances'][1]['center_m']=[2,0,3]
start=time.perf_counter()
result=compile_shared_tree_proposals(r,s,context=c,max_results=8)
out=p/'three-probe'/uuid.uuid4().hex;out.mkdir(parents=True)
(out/'result.json').write_text(json.dumps({'requirements':r,'search':s,'context':c,'result':result,
    'checker_version':env['OMA_EXECUTABLE_BUILD'],'seconds':time.perf_counter()-start},indent=2)+'\n',encoding='utf8')
print(json.dumps({'path':str(out),'status':result['status'],'reason':result.get('reason'),'work':result['work'],
    'count':result.get('synthesis',{}).get('assignment_count'),
    'costs':[x['nominal_cost'] for x in result.get('independent_check',{}).get('proposals',[])],
    'parts':[len(x['components']) for x in (result.get('mission') or {}).get('network_alternatives',[])]}))
