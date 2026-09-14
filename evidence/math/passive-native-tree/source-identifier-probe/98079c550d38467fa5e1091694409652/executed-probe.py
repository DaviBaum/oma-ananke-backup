"""Check whether a legal sink ID can collide with the internal source label."""
from pathlib import Path
from copy import deepcopy
import hashlib,json,sys,uuid
from oma.routing.passive_tree_pressure import derive_passive_tree_model,evaluate_passive_tree
from oma.routing.network_scenario import NetworkDesign
from oma.routing.passive_tree_scenario import PassiveTreeBoundary
from oma.build_identity import checker_version

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
STAGE=ROOT/'.oma/development/passive-native-tree'
BASE=STAGE/'evidence/native-three-sink/5c0e4ad0641d4acab0aca886eb023bf0'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def main():
    out=STAGE/'evidence/source-identifier-probe'/uuid.uuid4().hex;out.mkdir(parents=True)
    b=read(BASE/'new-boundary-declaration.json');n=read(BASE/'specification.json');m=read(BASE/'native-metrics.json')
    # Change only the symbolic sink identity; all geometry, ports and numerical
    # boundaries stay identical. Relabels a new fixture, never an accepted mission.
    n['sinks'][0]['id']='source'
    next(p for p in n['demand_paths'] if p['sink_id']=='sink-a')['sink_id']='source'
    for key in ('sink_total_pressures_pa','minimum_sink_flows_m3_s'):
        b[key]['source']=b[key].pop('sink-a')
    validated=NetworkDesign.model_validate(n);PassiveTreeBoundary.model_validate(b)
    m['network_root']=digest(validated.model_dump(mode='json',by_alias=True))
    model,derivation=derive_passive_tree_model(b,n,m,context={'probe':'new symbolic identifier only'})
    result=evaluate_passive_tree(b,n,m,context={'probe':'new symbolic identifier only'})
    root_node=next(row['node'] for row in derivation['quotient_nodes'] if ['trunk','a'] in row['slots'])
    renamed_sink_node=next(row['node'] for row in derivation['quotient_nodes'] if ['arm-a','b'] in row['slots'])
    record={'status':'SOURCE_BOUNDARY_ID_COLLISION_REPRODUCED' if root_node not in model['boundary_heads'] else 'SOURCE_BOUNDARY_RETAINED',
        'checker_version':checker_version(),'network_schema_accepts_id':True,'boundary_schema_accepts_id':True,
        'requested_boundary_count':4,'derived_boundary_count':len(model['boundary_heads']),
        'actual_source_node':root_node,'renamed_sink_node':renamed_sink_node,'model':model,'derivation':derivation,'evaluation':result,
        'mutated_new_fixture':{'boundary':b,'network':n,'metrics':m},'original_native_files_written':False,
        'scope':'Adapter derivation/evaluation under trusted supplied native metrics. No ordinary API or geometry acceptance claim; requests four physical boundaries but model source may disappear.'}
    (out/'result.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    (out/'executed-probe.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'directory':str(out),'status':record['status'],'requested_boundaries':4,'actual_boundaries':len(model['boundary_heads']),
        'evaluation_status':result['status'],'service_verdict':result['verdict']}))

if __name__=='__main__':main()
