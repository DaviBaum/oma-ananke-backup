"""Actual two-tee IFC fixture; geometric checks have no hydraulic authority."""
from pathlib import Path
import copy
import math

import ifcopenshell
import ifcopenshell.api
import numpy as np

from oma.ifc.audit import sha256_file
from oma.ifc.network import export_network, check_network_semantics
from oma.ifc.cad import cad_check_routes, load_cad


ZONE = {'min': [-1.3,3.7,2.7], 'max': [3.3,5.3,3.3]}


def three_sink_spec():
    def segment(name,a,b):
        return {'id':name,'kind':'segment','system_type':'PRESSURE_PIPE','diameter_m':.1,'insulation_m':.02,
                'geometry':{'start_m':a,'end_m':b},'ports':{'a':'SINK','b':'SOURCE'}}
    def tee(name,x):
        return {'id':name,'kind':'tee','system_type':'PRESSURE_PIPE','diameter_m':.1,'insulation_m':.02,
                'geometry':{'frame_m':[[1,0,0,x],[0,1,0,4],[0,0,1,3],[0,0,0,1]],'trunk_takeout_m':.2,'branch_takeout_m':.2},
                'ports':{'a':'SINK','b':'SOURCE','branch':'SOURCE'}}
    def slot(component,port):return {'component':component,'port':port}
    def joint(a,p,b):return {'source':slot(a,p),'sink':slot(b,'a')}
    def step(component,exit_port='b'):return {'component':component,'entry_port':'a','exit_port':exit_port}
    return {'schema':'oma-physical-network/1','network_id':'explicit-positive-common-loss-three-sink-tree','system_type':'PRESSURE_PIPE',
        'components':[segment('trunk',[-1,4,3],[-.2,4,3]),tee('tee-1',0),
            segment('arm-a',[0,4.2,3],[0,5,3]),segment('inter-tee',[.2,4,3],[1.8,4,3]),tee('tee-2',2),
            segment('arm-b',[2.2,4,3],[3,4,3]),segment('arm-c',[2,4.2,3],[2,5,3])],
        'connections':[joint('trunk','b','tee-1'),joint('tee-1','branch','arm-a'),joint('tee-1','b','inter-tee'),
                       joint('inter-tee','b','tee-2'),joint('tee-2','b','arm-b'),joint('tee-2','branch','arm-c')],
        'source':slot('trunk','a'),
        'sinks':[{'id':'sink-'+s,'endpoint':slot('arm-'+s,'b')} for s in ('a','b','c')],
        'demand_paths':[{'demand_id':'demand-a','sink_id':'sink-a','steps':[step('trunk'),step('tee-1','branch'),step('arm-a')]},
            {'demand_id':'demand-b','sink_id':'sink-b','steps':[step('trunk'),step('tee-1'),step('inter-tee'),step('tee-2'),step('arm-b')]},
            {'demand_id':'demand-c','sink_id':'sink-c','steps':[step('trunk'),step('tee-1'),step('inter-tee'),step('tee-2','branch'),step('arm-c')]}]}


def explicit_pressure_assumptions():
    return {'schema':'oma.private-three-sink-oracle-declaration/1','density_kg_m3':'1000','darcy_friction_factor':'1/50',
        'gravity_m_s2':'9.80665','source_total_pressure_pa':'100','sink_total_pressures_pa':{'sink-a':'0','sink-b':'0','sink-c':'0'},
        'pressure_reference':'TOTAL_PRESSURE_P_PLUS_KINETIC_EXCLUDING_ELEVATION',
        'hydraulic_section_interpretation':'IDEAL_CIRCULAR_BORE_FROM_NATIVE_ENVELOPE_MINUS_DECLARED_INSULATION',
        'tee_loss_interpretation':'EACH_TEE_HAS_EQUAL_POSITIVE_TOTAL_INLET_REFERENCED_LOSS_AT_BOTH_OUTLETS',
        'tee_total_loss_coefficients':{'tee-1':{'a:b':'1/5','a:branch':'1/5'},'tee-2':{'a:b':'3/10','a:branch':'3/10'}},
        'tee_darcy_included_in_total_loss':True,'elbow_additional_loss_coefficient':'1/5',
        'boundary_control_assumption':'New hypothetical regulated total-pressure terminals; no prior mission is reinterpreted',
        'physical_scope':'Ideal declared bore and loss model; native IFC encodes outer solid envelopes, not measured internal hydraulic bores'}


def make_original(path, *, millimeters=False, blocking=False):
    path=Path(path)
    if path.exists():raise ValueError('Fixture original already exists')
    model=ifcopenshell.api.run('project.create_file',version='IFC4')
    project=ifcopenshell.api.run('root.create_entity',model,ifc_class='IfcProject',name='Private three-sink native fixture')
    ifcopenshell.api.run('unit.assign_unit',model,length={'is_metric':True,'raw':'MILLIMETERS' if millimeters else 'METERS'})
    units=model.by_type('IfcUnitAssignment')[0]
    units.Units=list(units.Units)+[model.create_entity('IfcSIUnit',UnitType='PLANEANGLEUNIT',Name='RADIAN')]
    context=ifcopenshell.api.run('context.add_context',model,context_type='Model')
    body=ifcopenshell.api.run('context.add_context',model,context_type='Model',context_identifier='Body',target_view='MODEL_VIEW',parent=context)
    storey=ifcopenshell.api.run('root.create_entity',model,ifc_class='IfcBuildingStorey',name='Original protected storey')
    ifcopenshell.api.run('aggregate.assign_object',model,products=[storey],relating_object=project)
    boxes=[((0.,0.,0.),(2.,2.,2.))]
    if blocking:boxes.append(((1.1,3.9,2.9),(.2,.2,.2)))
    for index,(origin,size) in enumerate(boxes):
        element=ifcopenshell.api.run('root.create_entity',model,ifc_class='IfcBuildingElementProxy',name=f'Protected obstacle {index}')
        rep=ifcopenshell.api.run('geometry.add_wall_representation',model,context=body,length=size[0],thickness=size[1],height=size[2])
        ifcopenshell.api.run('geometry.assign_representation',model,product=element,representation=rep)
        transform=np.eye(4);transform[:3,3]=origin
        ifcopenshell.api.run('geometry.edit_object_placement',model,product=element,matrix=transform)
        ifcopenshell.api.run('spatial.assign_container',model,products=[element],relating_structure=storey)
    path.parent.mkdir(parents=True,exist_ok=True);model.write(str(path))
    return path


def complete_native_evidence(source,output,spec=None):
    spec=copy.deepcopy(three_sink_spec() if spec is None else spec)
    before=sha256_file(source)
    manifest=export_network(source,output,spec)
    semantic=check_network_semantics(output,source,manifest)
    guids=[p['ifc_guid'] for p in manifest['added_parts']]
    cad=cad_check_routes([source],output,guids,clearance_m=.1,numerical_tolerance_m=1e-6)
    actual,errors=load_cad(output,guids=set(guids))
    zone=[]
    for obj in actual:
        margin=min(*(obj.bounds[i]-ZONE['min'][i] for i in range(3)),*(ZONE['max'][i]-obj.bounds[i+3] for i in range(3)))
        zone.append({'guid':obj.guid,'bounds_m':list(obj.bounds),'margin_m':margin,'kernel_tolerance_m':obj.kernel_tolerance_m,
                     'status':'PASS' if obj.valid and math.isfinite(margin) and margin>1e-6+obj.kernel_tolerance_m else 'UNKNOWN'})
    ports={(p['component_id'],p['slot']):p for p in semantic['ports']}
    pair_rows=[]
    for connection in spec['connections']:
        a,b=(ports[(connection[k]['component'],connection[k]['port'])] for k in ('source','sink'))
        distance=float(np.linalg.norm(np.asarray(a['position_m'])-b['position_m']))
        normals=float(np.dot(a['physical_outward_normal'],b['physical_outward_normal']))
        axes=float(np.dot(a['flow_axis'],b['flow_axis']))
        assert a['flow_direction']=='SOURCE' and b['flow_direction']=='SINK'
        assert distance<1e-8 and abs(normals+1)<1e-8 and abs(axes-1)<1e-8
        pair_rows.append({'connection':connection,'source_port_guid':a['port_guid'],'sink_port_guid':b['port_guid'],
            'cap_distance_m':distance,'physical_normal_dot':normals,'encoded_flow_axis_dot':axes})
    assert before==sha256_file(source)
    return {'source_sha256':before,'export_sha256':sha256_file(output),'manifest':manifest,'semantics':semantic,'cad':cad,
        'zone':{'declared_bounds_m':ZONE,'status':'PASS' if not errors and len(zone)==7 and all(x['status']=='PASS' for x in zone) else 'UNKNOWN','parts':zone},
        'native_connection_signs':pair_rows,'source_unchanged':True}
