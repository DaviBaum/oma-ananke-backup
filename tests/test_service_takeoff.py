from fractions import Fraction as Q
import hashlib
import json

import ifcopenshell
import ifcopenshell.guid
import pytest

from oma.ifc.service_takeoff import extract_service_takeoff
from oma.store import digest


class Source:
    def __init__(self, tmp_path, prefix=None, feet=False):
        self.path = tmp_path/'source.ifc'
        self.m = ifcopenshell.file(schema='IFC4')
        self.unit = self.m.create_entity('IfcSIUnit', UnitType='LENGTHUNIT', Name='METRE', Prefix=prefix)
        if feet:
            factor = self.m.create_entity('IfcMeasureWithUnit', ValueComponent=self.m.create_entity('IfcLengthMeasure', 0.3048), UnitComponent=self.unit)
            dims = self.m.create_entity('IfcDimensionalExponents', 1,0,0,0,0,0,0)
            self.unit = self.m.create_entity('IfcConversionBasedUnit', Dimensions=dims, UnitType='LENGTHUNIT', Name='foot', ConversionFactor=factor)
        units = self.m.create_entity('IfcUnitAssignment', Units=[self.unit])
        self.project = self.named('IfcProject', UnitsInContext=units)
        self.context = self.m.create_entity('IfcGeometricRepresentationContext', ContextType='Model', CoordinateSpaceDimension=3,
                                           Precision=1e-5, WorldCoordinateSystem=self.axis())
        self.project.RepresentationContexts = [self.context]
        self.types = {}

    def named(self, kind, **kw):
        return self.m.create_entity(kind, GlobalId=ifcopenshell.guid.new(), **kw)

    def point(self, xyz):
        return self.m.create_entity('IfcCartesianPoint', Coordinates=tuple(float(x) for x in xyz))

    def direction(self, xyz):
        return self.m.create_entity('IfcDirection', DirectionRatios=tuple(float(x) for x in xyz))

    def axis(self, xyz=(0,0,0), x=(1,0,0), z=(0,0,1)):
        return self.m.create_entity('IfcAxis2Placement3D', Location=self.point(xyz), RefDirection=self.direction(x), Axis=self.direction(z))

    def rep(self, item, name='Body'):
        return self.m.create_entity('IfcShapeRepresentation', ContextOfItems=self.context, RepresentationIdentifier=name,
                                    RepresentationType='SweptSolid' if name=='Body' else 'Curve3D', Items=[item])

    def segment(self, depth=2, profile='circle', kind='IfcPipeSegment', radius=.1, dims=(.4,.2), type_name='same',
                solid_position=None, product_position=None):
        if profile=='circle':
            shape = self.m.create_entity('IfcCircleProfileDef', ProfileType='AREA', Radius=float(radius))
        elif profile=='hollow':
            shape = self.m.create_entity('IfcCircleHollowProfileDef', ProfileType='AREA', Radius=float(radius), WallThickness=.01)
        else:
            shape = self.m.create_entity('IfcRectangleProfileDef', ProfileType='AREA', XDim=float(dims[0]), YDim=float(dims[1]))
        solid = self.m.create_entity('IfcExtrudedAreaSolid', SweptArea=shape, Position=solid_position or self.axis(), ExtrudedDirection=self.direction((0,0,1)), Depth=float(depth))
        p = self.named(kind, Name='Installed segment', ObjectPlacement=self.m.create_entity('IfcLocalPlacement', RelativePlacement=product_position or self.axis()),
                       Representation=self.m.create_entity('IfcProductDefinitionShape', Representations=[self.rep(solid)]))
        if type_name is not None:
            key = kind,type_name
            if key not in self.types:
                self.types[key] = self.named(kind+'Type', Name=type_name, PredefinedType='NOTDEFINED')
            self.named('IfcRelDefinesByType', RelatingType=self.types[key], RelatedObjects=[p])
        return p, solid

    def axis_curve(self, p, points):
        curve = self.m.create_entity('IfcPolyline', Points=[self.point(x) for x in points])
        p.Representation.Representations = [*p.Representation.Representations, self.rep(curve, 'Axis')]
        return curve

    def ports(self, p, points):
        ports=[]
        for pt in points:
            port = self.named('IfcDistributionPort', FlowDirection='NOTDEFINED', ObjectPlacement=self.m.create_entity('IfcLocalPlacement', PlacementRelTo=p.ObjectPlacement, RelativePlacement=self.axis(pt)))
            self.named('IfcRelNests', RelatingObject=p, RelatedObjects=[port]); ports.append(port)
        return ports

    def map(self, p, scale=1, scale2=None, origin=(0,0,0), target=(0,0,0), x=(1,0,0), z=(0,0,1)):
        rep = p.Representation.Representations[0]
        source = self.m.create_entity('IfcRepresentationMap', MappingOrigin=self.axis(origin), MappedRepresentation=rep)
        args=dict(LocalOrigin=self.point(target), Scale=float(scale), Axis1=self.direction(x), Axis2=self.direction((0,1,0)), Axis3=self.direction(z))
        if scale2 is not None:
            args.update(Scale2=float(scale2),Scale3=float(scale)); kind='IfcCartesianTransformationOperator3DnonUniform'
        else:
            kind='IfcCartesianTransformationOperator3D'
        op=self.m.create_entity(kind, **args)
        item=self.m.create_entity('IfcMappedItem', MappingSource=source, MappingTarget=op)
        p.Representation.Representations=[self.rep(item)]
        return item

    def write(self):
        self.m.write(str(self.path))
        products=self.m.by_type('IfcProduct'); ports=self.m.by_type('IfcDistributionPort')
        owners={p.id():[] for p in ports}; relations={p.id():[] for p in ports}
        for r in self.m.by_type('IfcRelNests'):
            for p in r.RelatedObjects:
                if p.id() in owners:owners[p.id()].append(r.RelatingObject.id());relations[p.id()].append(r.id())
        systems=[]; memberships={p.id():[] for p in products}
        for s in self.m.by_type('IfcSystem'):
            members=[p.id() for r in s.IsGroupedBy for p in r.RelatedObjects]
            for pid in members:memberships[pid].append(s.id())
            systems.append({'step_id':s.id(),'type':s.is_a(),'ifc_guid':s.GlobalId,'name':s.Name,'members':members})
        audit={'audit_version':'oma-ifc-audit/1','schema':'IFC4','source_sha256':hashlib.sha256(self.path.read_bytes()).hexdigest(),
               'products':[{'step_id':p.id(),'type':p.is_a(),'ifc_guid':p.GlobalId,'physical':p.is_a('IfcElement') and not p.is_a('IfcFeatureElementSubtraction'),'system_ids':memberships[p.id()]} for p in products],
               'ports':[{'step_id':p.id(),'owner_step_ids':owners[p.id()],'owner_relationship_step_ids':relations[p.id()],'flow_direction':p.FlowDirection} for p in ports],
               'explicit_connections':[], 'systems':systems}
        return audit

    def run(self, **kw):
        audit=self.write(); return extract_service_takeoff(audit,self.path,**kw)


@pytest.mark.parametrize('prefix,feet,depth,want', [(None,False,2,'2'),('MILLI',False,2500,'5/2'),(None,True,10,'15240000000000001/5000000000000000')])
def test_circle_exact_units_and_original_preserved(tmp_path,prefix,feet,depth,want):
    s=Source(tmp_path,prefix,feet);p,_=s.segment(depth=depth);audit=s.write();before=s.path.read_bytes()
    out=extract_service_takeoff(audit,s.path);piece,=out['pieces']
    assert piece['length_m']==want and piece['stock_kind']=='PIPE'
    assert piece['id']==audit['source_sha256']+':#'+str(p.id())
    assert piece['batch_id']==piece['network_id']
    assert out['audit_root']==digest(audit) and s.path.read_bytes()==before
    assert not piece['geometry_evidence']['hydraulic_bore_inferred']


def test_source_decimal_not_binary_float_length(tmp_path):
    s=Source(tmp_path);_,solid=s.segment(depth=.1);audit=s.write()
    text=s.path.read_text();needle=str(solid)
    source_line=next(x for x in text.splitlines() if x.startswith('#'+str(solid.id())+'='))
    changed=source_line.rsplit(',',1)[0]+',0.100000000000000000000000003);'
    s.path.write_text(text.replace(source_line,changed));audit['source_sha256']=hashlib.sha256(s.path.read_bytes()).hexdigest()
    piece,=extract_service_takeoff(audit,s.path)['pieces']
    assert Q(piece['length_m'])==Q('0.100000000000000000000000003')


def test_cable_tray_transverse_extrusion_not_mistaken_for_length(tmp_path):
    s=Source(tmp_path);p,_=s.segment(depth=.125,profile='rectangle',kind='IfcCableCarrierSegment',dims=(4,.25))
    s.ports(p,[(-2,0,.0625),(2,0,.0625)])
    piece,=s.run()['pieces']
    assert piece['length_m']=='4' and piece['stock_kind']=='CABLE_CARRIER'
    assert piece['profile_si']['height_m']=='1/8'
    assert piece['geometry_evidence']['longitudinal_prism_axis']==0


@pytest.mark.parametrize('method',['ports','axis'])
def test_rectangular_length_requires_and_binds_exact_endpoints(tmp_path,method):
    s=Source(tmp_path);p,_=s.segment(profile='rectangle',kind='IfcDuctSegment',solid_position=s.axis((3,4,5),x=(0,1,0),z=(1,0,0)))
    (s.ports if method=='ports' else s.axis_curve)(p,[(3,4,5),(5,4,5)])
    piece,=s.run()['pieces']
    assert piece['length_m']=='2' and piece['stock_kind']=='DUCT_RECTANGULAR'
    assert piece['geometry_evidence']['axis_evidence']['exact_body_endpoints_matched']


def test_irrational_rectangle_rotation_has_outward_interval_axis_witness(tmp_path):
    s=Source(tmp_path)
    p,_=s.segment(depth=.125,profile='rectangle',kind='IfcCableCarrierSegment',dims=(4,.25),
                  solid_position=s.axis(x=(1,1,0)))
    s.ports(p,[(-1.4142135623730951,-1.4142135623730951,.0625),
               (1.4142135623730951,1.4142135623730951,.0625)])
    piece,=s.run()['pieces'];axis=piece['geometry_evidence']['axis_evidence']
    assert piece['length_m']=='4' and piece['geometry_evidence']['longitudinal_prism_axis']==0
    assert not axis['exact_body_endpoints_matched'] and axis['bounded_body_endpoints_matched']
    assert axis['unique_axis_proven_within_declared_precision'] and not axis['body_dimension_adjusted']
    assert Q(axis['maximum_endpoint_residual_squared_m2']) < Q(axis['endpoint_tolerance_m'])**2


@pytest.mark.parametrize('offset,eligible',[(.005,True),(.02,False)])
def test_declared_precision_is_si_scaled_and_mismatch_must_fit_it(tmp_path,offset,eligible):
    s=Source(tmp_path,prefix='MILLI');s.context.Precision=.01
    p,_=s.segment(depth=2000,profile='rectangle',dims=(400,200))
    s.ports(p,[(offset,0,0),(offset,0,2000)])
    out=s.run();assert bool(out['pieces']) is eligible
    if eligible:
        piece,=out['pieces'];assert piece['length_m']=='2'
        assert piece['geometry_evidence']['axis_evidence']['endpoint_tolerance_m']=='1/100000'


@pytest.mark.parametrize('precision,offset',[(None,.000001),(1,.01),(.00001,.00002)])
def test_precision_fallback_never_invents_or_expands_a_tolerance(tmp_path,precision,offset):
    s=Source(tmp_path);s.context.Precision=precision
    p,_=s.segment(profile='rectangle');s.ports(p,[(offset,0,0),(offset,0,2)])
    out=s.run();assert not out['pieces']


def test_endpoint_tolerance_is_euclidean_not_coordinatewise(tmp_path):
    s=Source(tmp_path);s.context.Precision=.00001
    p,_=s.segment(profile='rectangle')
    d=.000008;s.ports(p,[(d,d,d),(d,d,2+d)])
    assert not s.run()['pieces']


def test_more_than_one_prism_axis_within_precision_is_not_selected(tmp_path):
    s=Source(tmp_path);s.context.Precision=.00001
    p,_=s.segment(depth=.000002,profile='rectangle',dims=(.000002,.000002))
    s.ports(p,[(-.0000001,0,.000001),(.0000001,0,.000001)])
    out=s.run();assert not out['pieces']
    assert out['retained_objects'][0]['reason']=='AXIS_BODY_LENGTH_OR_ALIGNMENT_AMBIGUOUS'


def test_mapped_irrational_frame_retains_forward_origin_composition(tmp_path):
    s=Source(tmp_path)
    p,_=s.segment(profile='rectangle')
    s.map(p,origin=(0,0,2),target=(10,0,0),x=(1,0,-1),z=(1,0,1))
    s.axis_curve(p,[(11.414213562373095,0,1.4142135623730951),
                    (12.82842712474619,0,2.8284271247461903)])
    piece,=s.run()['pieces'];assert piece['length_m']=='2'
    assert piece['geometry_evidence']['axis_evidence']['bounded_body_endpoints_matched']


@pytest.mark.parametrize('mode',['missing','wrong','curved','multi_axis','nonrelative_ports'])
def test_ambiguous_rectangle_remains_retained(tmp_path,mode):
    s=Source(tmp_path);p,_=s.segment(profile='rectangle')
    if mode=='wrong':s.axis_curve(p,[(0,0,0),(0,0,3)])
    if mode=='curved':s.axis_curve(p,[(0,0,0),(1,0,1),(0,0,2)])
    if mode=='multi_axis':s.axis_curve(p,[(0,0,0),(0,0,2)]);s.axis_curve(p,[(0,0,0),(0,0,2)])
    if mode=='nonrelative_ports':
        for port in s.ports(p,[(0,0,0),(0,0,2)]):port.ObjectPlacement.PlacementRelTo=None
    out=s.run();assert not out['pieces'];assert out['retained_objects'][0]['status']=='RETAINED_UNSUPPORTED_LINEAR_TAKEOFF'


def test_circle_contradictory_axis_is_not_ignored(tmp_path):
    s=Source(tmp_path);p,_=s.segment();s.axis_curve(p,[(0,0,0),(0,0,3)])
    assert not s.run()['pieces']


def test_rigid_nested_mapping_preserves_exact_circle_quantity(tmp_path):
    s=Source(tmp_path);p,_=s.segment();s.map(p,origin=(5,0,0),target=(50,20,-3),x=(0,0,-1),z=(1,0,0));s.map(p)
    piece,=s.run()['pieces'];assert piece['length_m']=='2' and len(piece['geometry_evidence']['mapping_step_ids'])==2


@pytest.mark.parametrize('axis_x,eligible',[(15,True),(5,False)])
def test_nonidentity_mapping_origin_applies_forward_before_target(tmp_path,axis_x,eligible):
    s=Source(tmp_path);p,_=s.segment(profile='rectangle')
    s.map(p,origin=(5,0,0),target=(10,0,0))
    s.axis_curve(p,[(axis_x,0,0),(axis_x,0,2)])
    out=s.run();assert bool(out['pieces']) is eligible


@pytest.mark.parametrize('relation',['IfcRelAggregates','IfcRelNests'])
def test_physical_child_assembly_does_not_duplicate_linear_stock(tmp_path,relation):
    s=Source(tmp_path);parent,_=s.segment();child,_=s.segment()
    s.named(relation,RelatingObject=parent,RelatedObjects=[child])
    out=s.run();assert [p['step_id'] for p in out['pieces']]==[child.id()]
    assert next(r for r in out['retained_objects'] if r['step_id']==parent.id())['reason']=='COMPOSITE_SEGMENT_REQUIRES_COMPONENT_TAKEOFF'


def test_storey_is_explicit_spatial_ancestry_not_elevation_guess(tmp_path):
    s=Source(tmp_path);p,_=s.segment();space=s.named('IfcSpace');storey=s.named('IfcBuildingStorey',Name='Named level')
    s.named('IfcRelContainedInSpatialStructure',RelatedElements=[p],RelatingStructure=space)
    s.named('IfcRelAggregates',RelatingObject=storey,RelatedObjects=[space])
    piece,=s.run()['pieces'];assert piece['storey_step_ids']==[storey.id()] and piece['storey_status']=='EXPLICIT_UNIQUE'


def test_ratio_measure_conversion_unit_is_exact_source_number(tmp_path):
    s=Source(tmp_path,feet=True);s.unit.ConversionFactor.ValueComponent=s.m.create_entity('IfcRatioMeasure',.5)
    s.segment(depth=3);piece,=s.run()['pieces'];assert piece['length_m']=='3/2'


def test_unresolved_global_frame_retains_local_quantity_with_explicit_limit(tmp_path):
    s=Source(tmp_path);p,_=s.segment();audit=s.write()
    axis=p.ObjectPlacement.RelativePlacement.Axis
    text=s.path.read_text();text='\n'.join(line for line in text.splitlines() if not line.startswith('#'+str(axis.id())+'='))+'\n'
    s.path.write_text(text);audit['source_sha256']=hashlib.sha256(s.path.read_bytes()).hexdigest()
    piece,=extract_service_takeoff(audit,s.path)['pieces']
    assert piece['length_m']=='2'
    assert piece['geometry_evidence']['global_placement']['status']=='UNRESOLVED_GLOBAL_PLACEMENT'
    assert not piece['geometry_evidence']['global_geometry_verified']


def test_parser_modified_private_snapshot_rejected(tmp_path,monkeypatch):
    s=Source(tmp_path);s.segment();audit=s.write();open_ifc=ifcopenshell.open;calls=[]
    def parser(path):
        result=open_ifc(path);calls.append(path)
        if len(calls)==2:
            from pathlib import Path
            private=Path(path);private.write_bytes(private.read_bytes()+b'\n')
        return result
    monkeypatch.setattr(ifcopenshell,'open',parser)
    with pytest.raises(ValueError,match='private source changed'):extract_service_takeoff(audit,s.path)


@pytest.mark.parametrize('scale,scale2',[(2,None),(1,2),(-1,None),(0,None)])
def test_scaled_mapping_not_eligible(tmp_path,scale,scale2):
    s=Source(tmp_path);p,_=s.segment();s.map(p,scale=scale,scale2=scale2)
    out=s.run();assert not out['pieces'];assert out['retained_objects'][0]['reason']=='NONRIGID_MAPPING_SCALE'


def test_mapping_cycle_is_bounded(tmp_path):
    s=Source(tmp_path);p,_=s.segment();item=s.map(p);item.MappingSource.MappedRepresentation.Items=[item]
    out=s.run();assert not out['pieces'];assert 'CYCLE' in out['retained_objects'][0]['reason']


@pytest.mark.parametrize('change',['multi','oblique','zero','profile','opening'])
def test_unsupported_solid_is_not_zero_length_or_bbox(tmp_path,change):
    s=Source(tmp_path);p,solid=s.segment()
    if change=='multi':p.Representation.Representations[0].Items=[solid,solid]
    if change=='oblique':solid.ExtrudedDirection=s.direction((1,0,1))
    if change=='zero':solid.Depth=0.
    if change=='profile':solid.SweptArea=s.m.create_entity('IfcEllipseProfileDef',ProfileType='AREA',SemiAxis1=.2,SemiAxis2=.1)
    if change=='opening':
        opening=s.named('IfcOpeningElement');s.named('IfcRelVoidsElement',RelatingBuildingElement=p,RelatedOpeningElement=opening)
    out=s.run()
    if change=='opening':
        # Openings alter gross extrusion stock applicability and must fail closed.
        assert not out['pieces']
    else:assert not out['pieces']


def test_hollow_profile_retains_authored_wall_without_bore_inference(tmp_path):
    s=Source(tmp_path);s.segment(profile='hollow');piece,=s.run()['pieces']
    assert piece['profile_si']['authored_wall_thickness_m']=='1/100'
    assert 'bore' not in piece['profile_si']


def test_every_device_portless_proxy_and_nonservice_product_accounted(tmp_path):
    s=Source(tmp_path);s.segment();s.named('IfcAlarm');proxy=s.named('IfcBuildingElementProxy');wall=s.named('IfcWall')
    out=s.run(source_discipline='ARCHITECTURE')
    assert out['summary']['service_object_count']==3 and len(out['pieces'])==1
    assert proxy.id() in {r['step_id'] for r in out['retained_objects']}
    assert wall.id() in out['accounting']['all_other_source_products_accounted_by_category']['ARCHITECTURE']


def test_exact_group_shared_across_systems_but_not_profiles_materials_or_types(tmp_path):
    s=Source(tmp_path);a,_=s.segment();b,_=s.segment();c,_=s.segment(radius=.10000000000001);d,_=s.segment(type_name='other')
    e,_=s.segment();material=s.m.create_entity('IfcMaterial',Name='Declared copper')
    s.named('IfcRelAssociatesMaterial',RelatedObjects=[e],RelatingMaterial=material)
    for p in (a,b):
        system=s.named('IfcSystem');s.named('IfcRelAssignsToGroup',RelatingGroup=system,RelatedObjects=[p])
    pieces={p['step_id']:p for p in s.run()['pieces']}
    assert pieces[a.id()]['stock_group']==pieces[b.id()]['stock_group']
    assert len({pieces[p.id()]['stock_group'] for p in (a,c,d,e)})==4
    assert pieces[a.id()]['system_step_ids']!=pieces[b.id()]['system_step_ids']


@pytest.mark.parametrize('field,values',[('PredefinedType',('RIGIDSEGMENT','FLEXIBLESEGMENT')),('ObjectType',('Socket ends','Threaded ends'))])
def test_occurrence_stock_declarations_are_not_erased_by_shared_type(tmp_path,field,values):
    s=Source(tmp_path);a,_=s.segment();b,_=s.segment()
    setattr(a,field,values[0]);setattr(b,field,values[1])
    out=s.run();assert len(out['stock_groups'])==2


def test_type_material_inheritance_is_recorded(tmp_path):
    s=Source(tmp_path);p,_=s.segment();material=s.m.create_entity('IfcMaterial',Name='Authored material')
    s.named('IfcRelAssociatesMaterial',RelatedObjects=[s.types[('IfcPipeSegment','same')]],RelatingMaterial=material)
    piece,=s.run()['pieces'];assert piece['materials'][0]['step_id']==material.id()
    assert piece['material_status']=='AUTHORED_ASSOCIATIONS_NOT_QUALIFIED'


def test_no_type_does_not_pool_and_deterministic_without_mutation(tmp_path):
    s=Source(tmp_path);s.segment(type_name=None);s.segment(type_name=None);audit=s.write()
    out=extract_service_takeoff(audit,s.path);again=extract_service_takeoff(audit,s.path)
    assert out==again and len(out['stock_groups'])==2


@pytest.mark.parametrize('mutation',['source','audit'])
def test_final_callback_mutation_fails_closed(tmp_path,mutation):
    s=Source(tmp_path);s.segment();audit=s.write()
    def pulse(stage):
        if stage=='service_takeoff_complete':
            if mutation=='source':s.path.write_bytes(s.path.read_bytes()+b'\n')
            else:audit['products'][0]['ifc_guid']='changed'
    with pytest.raises(ValueError,match='changed'):extract_service_takeoff(audit,s.path,checkpoint=pulse)


def test_source_omission_rejected_before_takeoff(tmp_path):
    s=Source(tmp_path);s.segment();audit=s.write();audit['products']=[]
    with pytest.raises(ValueError,match='denominator'):extract_service_takeoff(audit,s.path)


def test_callback_exception_and_byte_limits_not_swallowed(tmp_path):
    s=Source(tmp_path);s.segment();audit=s.write();error=RuntimeError('stop')
    def pulse(stage):
        if stage=='service_takeoff_products':raise error
    with pytest.raises(RuntimeError) as caught:extract_service_takeoff(audit,s.path,checkpoint=pulse)
    assert caught.value is error
    with pytest.raises(ValueError,match='byte budget'):extract_service_takeoff(audit,s.path,max_source_bytes=10)


def test_takeoff_never_calls_cad_geometry(tmp_path,monkeypatch):
    import ifcopenshell.geom
    monkeypatch.setattr(ifcopenshell.geom,'create_shape',lambda *a,**k:pytest.fail('No CAD required'))
    s=Source(tmp_path);s.segment();assert s.run()['summary']['eligible_piece_count']==1
