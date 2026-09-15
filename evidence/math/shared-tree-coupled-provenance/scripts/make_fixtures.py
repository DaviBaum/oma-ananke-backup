"""Author nominal-only coupled fixtures using the retained original macro producer.

No pressure solver or native checker is run. The new independent checker does not
call these authoring helpers; producer-disabled tests consume the saved JSON.
"""
from pathlib import Path
import copy,hashlib,json,sys
from fractions import Fraction as Q
STAGE=Path(__file__).resolve().parents[1]
BASE=STAGE/'tests/fixtures/shared-tree-catalogue-check'
dependency=json.loads((STAGE/'dependencies/base.json').read_text(encoding='utf-8'))['root']
sys.path.insert(0,str(STAGE/'dependencies'/dependency/'src'))
from oma.routing.shared_tree_requirements import normalize_shared_tree_requirements
from oma.routing import shared_tree_proposals as producer
from oma.optimization.fabrication import compile_orthogonal_fabrication,verify_orthogonal_fabrication

def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def read(name):return json.loads((BASE/(name+'.json')).read_text(encoding='utf-8'))
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')

for count in (2,3):
 r,s,c,g=(read(name) for name in ('requirements','search','context','generated'))
 r['physics']=None
 for sink in r['sinks']:
  sink.pop('required_flow_m3_s');sink.pop('available_static_pressure_pa')
 if count==2:
  s['tee_instances']=s['tee_instances'][:1]
  g['catalogue']['tee_instances']=g['catalogue']['tee_instances'][:1]
  g['tee_components'].pop('tee-b')
  g['catalogue']['connectors']=[row for row in g['catalogue']['connectors'] if row['from']['node']!='tee-b' and row['to']['node']!='tee-b']
  keep={row['id'] for row in g['catalogue']['connectors']}
  g['connector_macros']={k:v for k,v in g['connector_macros'].items() if k in keep}
 else:
  r['sinks'].append({'id':'sink-c','demand_id':'demand-c','end_m':[2,3,3]})
  s['sink_directions']['sink-c']=[0,1,0]
  g['catalogue']['sinks'].append({'id':'sink-c','demand_id':'demand-c','cap':{'position_m':['2','3','3'],'flow_direction':[0,1,0]}})
 ids=[sink['id'] for sink in r['sinks']]
 boundary={'schema':'oma.coupled-tree-boundary/1',
  'source_total_pressure_pa':{'lower':'200','upper':'200'},
  'sink_total_pressures_pa':{sid:{'lower':'0','upper':'0'} for sid in ids},
  'minimum_sink_flows_m3_s':{sid:'1/10000' for sid in ids},
  'flow_search_box_m3_s':{sid:{'lower':'1/1000','upper':'1/500'} for sid in ids},
  'density_kg_m3':'1000','darcy_friction':'1/50','maximum_velocity_m_s':'2','gravity_m_s2':'0',
  'elbow_loss_coefficient':'1/5','tee_outlet_loss_coefficients':{'tee-a':{'b':'1/5','branch':'3/10'}},
  'applicability':'Explicit hypothetical fixed-loss ideal-bore declaration for NOMINAL CATALOGUE PROVENANCE ONLY; no operating point is asserted.',
  'boundary_control_assumption':'Hypothetical regulated total-pressure boundaries; exact minima and query box remain fixed. No service result is asserted.',
  'pressure_reference':'TOTAL_PRESSURE_P_PLUS_KINETIC_EXCLUDING_ELEVATION','loss_model':'FIXED_COEFFICIENT_STEADY_INCOMPRESSIBLE',
  'hydraulic_section_interpretation':'IDEAL_CIRCULAR_BORE_FROM_NATIVE_ENVELOPE_MINUS_DECLARED_INSULATION','friction_convention':'DARCY',
  'elbow_loss_reference':'EXCESS_LOCAL_LOSS_EXCLUDING_CURVED_PIPE_FRICTION','tee_loss_reference':'OUTLET_SPECIFIC_TOTAL_LOSS_AT_TOTAL_INLET_FLOW',
  'connection_model':'NO_EXTRA_LOSS_AT_CHECKED_MATCHING_CONNECTED_CAPS','boundary_loss_scope':'BETWEEN_PHYSICAL_NETWORK_PORTS_ONLY'}
 if count==3:boundary['tee_outlet_loss_coefficients']['tee-b']={'b':'1/4','branch':'2/5'}
 r['coupled_tree']=boundary;r['assumptions']=['New explicit hypothetical coupled nominal-provenance fixture, no hydraulic proof or native acceptance']
 c={**c,'coupled_provenance_fixture':count};normalized=normalize_shared_tree_requirements(r)
 input_root=digest({'requirements':r,'search':s,'context':c})
 g['normalized_requirements']=normalized;g['input_root']=input_root
 cat=g['catalogue'];cat['context_root']=digest(c)
 cat['source_roots']={'authored_requirements':digest(r),'normalized_requirements':digest(normalized),'search':digest(s)}
 b=normalized['coupled_tree']
 for tee in cat['tee_instances']:
  tee['loss_contract_root']=digest({'model':'oma.coupled-tree-boundary/1','tee_id':tee['id'],
   'outlet_coefficients':b['tee_outlet_loss_coefficients'][tee['id']],'boundary_root':digest(b)})
 if count==3:
  path=[['1','1/4','3'],['1','9/4','3'],['2','9/4','3'],['2','3','3']]
  definition={'from':{'node':'tee-b','port':'branch'},'to':{'node':'sink-c','port':'in'},'points_m':path}
  identity='connector-'+digest(definition)[:24]
  cat['connectors'].append({'id':identity,'from':definition['from'],'to':definition['to'],
   'start_cap':{'position_m':path[0],'flow_direction':[0,1,0]},'end_cap':cat['sinks'][-1]['cap'],
   'section':cat['section'],'geometry_root':'0'*64,'fabrication_root':'0'*64,'nominal_cost':['0','0']})
  g['connector_macros'][identity]={'geometry':{'points_m':path,'components':[]},'certificate':{},'independent_check':{}}
 for row in cat['connectors']:
  macro=g['connector_macros'][row['id']];path=macro['geometry']['points_m']
  scenario=producer._fabrication_scenario(normalized,tuple(map(Q,path[0])),tuple(map(Q,path[-1])))
  cert=compile_orthogonal_fabrication(scenario,path,context_root=input_root,max_points=16)
  checked=verify_orthogonal_fabrication(scenario,path,cert,context_root=input_root,max_points=16)
  assert cert['status']=='PASS' and checked['status']=='PASS',(row['id'],cert,checked)
  geometry={'points_m':path,'components':producer._physical_components(cert,row['id'],normalized)}
  macro.update(geometry=geometry,certificate=cert,independent_check=checked)
  row.update(geometry_root=digest(geometry),fabrication_root=cert['certificate_root'],nominal_cost=producer._cost(cert,(Q(1),Q(0))))
 g['attempts']=[{'from':row['from'],'to':row['to'],'points_m':g['connector_macros'][row['id']]['geometry']['points_m'],
   'status':'NOMINAL_MACRO_ADMITTED','connector_id':row['id']} for row in cat['connectors']]
 out=STAGE/'tests/fixtures/shared-tree-coupled-check'/str(count);out.mkdir(parents=True,exist_ok=True)
 for name,value in zip(('requirements','search','context','generated'),(r,s,c,g)):write(out/(name+'.json'),value)
 print(json.dumps({'sinks':count,'tees':len(cat['tee_instances']),'connectors':len(cat['connectors']),'input_root':input_root}))
