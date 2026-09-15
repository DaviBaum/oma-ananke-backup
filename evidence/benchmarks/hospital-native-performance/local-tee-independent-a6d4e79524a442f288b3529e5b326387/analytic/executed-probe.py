from pathlib import Path
import hashlib,io,json,math,sys,time,uuid,shutil
import numpy as np
ROOT=Path.cwd();STAGE=ROOT/'.oma/development/hospital-outcome-audit';SOURCE=ROOT/'.oma/development/hospital-clearance-20260915/runtimes/f716dd5cbdd84134a50d855b217b91a886832abc582ee761b1340cec2026b8e7/src';sys.path.insert(0,str(SOURCE))
import ifcopenshell,ifcopenshell.geom
from oma.ifc.cad import _inspect_shape
from OCP.TopoDS import TopoDS_Shape
from OCP.BRepTools import BRepTools
from OCP.BRep import BRep_Builder
out=STAGE/'analytic-conversion-probes'/uuid.uuid4().hex;out.mkdir(parents=True);shutil.copyfile(__file__,out/'executed-probe.py')
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def model_for(radius,takeout,origin,R,style):
 m=ifcopenshell.file(schema='IFC4')
 def point(p):return m.create_entity('IfcCartesianPoint',Coordinates=[float(x) for x in p])
 def direction(d):return m.create_entity('IfcDirection',DirectionRatios=[float(x) for x in np.asarray(d)/np.linalg.norm(d)])
 def axis(p,z=(0,0,1),x=(1,0,0)):return m.create_entity('IfcAxis2Placement3D',Location=point(p),Axis=direction(z),RefDirection=direction(x))
 context=m.create_entity('IfcGeometricRepresentationContext',ContextType='Model',CoordinateSpaceDimension=3,Precision=1e-5,WorldCoordinateSystem=axis((0,0,0)))
 units=m.create_entity('IfcUnitAssignment',Units=[m.create_entity('IfcSIUnit',UnitType='LENGTHUNIT',Name='METRE')]);m.create_entity('IfcProject',GlobalId=ifcopenshell.guid.new(),RepresentationContexts=[context],UnitsInContext=units)
 def cylinder(start,end):
  d=np.asarray(end)-start;d=d/np.linalg.norm(d);seed=np.array([1.,0.,0.]) if abs(d[0])<.8 else np.array([0.,1.,0.]);x=seed-d*np.dot(seed,d)
  profile=m.create_entity('IfcCircleProfileDef',ProfileType='AREA',Radius=radius)
  return m.create_entity('IfcExtrudedAreaSolid',SweptArea=profile,Position=axis(start,d,x),ExtrudedDirection=direction((0,0,1)),Depth=float(np.linalg.norm(np.asarray(end)-start)))
 points=[np.array([-takeout,0,0]),np.array([takeout,0,0]),np.zeros(3),np.array([0,takeout,0])]
 if style=='world':points=[R@p+origin for p in points];placement=axis((0,0,0))
 elif style=='local_translate':points=[R@p for p in points];placement=axis(origin)
 else:placement=axis(origin,R[:,2],R[:,0])
 first=cylinder(points[0],points[1]);second=cylinder(points[2],points[3]);solid=m.create_entity('IfcBooleanResult',Operator='UNION',FirstOperand=first,SecondOperand=second)
 rep=m.create_entity('IfcShapeRepresentation',ContextOfItems=context,RepresentationIdentifier='Body',RepresentationType='CSG',Items=[solid])
 entity=m.create_entity('IfcPipeFitting',GlobalId=ifcopenshell.guid.new(),ObjectPlacement=m.create_entity('IfcLocalPlacement',RelativePlacement=placement),Representation=m.create_entity('IfcProductDefinitionShape',Representations=[rep]),PredefinedType='JUNCTION')
 return m,entity
angle=.37;R=np.array([[math.cos(angle),-math.sin(angle),0],[math.sin(angle),math.cos(angle),0],[0,0,1.]])
rot=np.array([[1.,0,0],[0,math.cos(.63),-math.sin(.63)],[0,math.sin(.63),math.cos(.63)]])@R
poses=[('origin',np.zeros(3),np.eye(3)),('hospital',np.array([33.,64.,173.875]),np.eye(3)),('rigid',np.array([1000.,-2000.,300.]),rot)]
result={'status':'RUNNING','scope':'Analytic union of two perpendicular equal-radius solid cylinders; nominal primitive formula unchanged. Private synthetic IFCs only; no acceptance authority.','rows':[]}
for radius,takeout in [(3/64,1/8),(.025,.2),(.1,.3)]:
 for pose,origin,rotation in poses:
  for style in ['world','local_translate','local_rigid']:
   m,e=model_for(radius,takeout,origin,rotation,style);path=out/f'{len(result["rows"]):03}.ifc';m.write(str(path))
   for precision in [None,1e-7]:
    settings=ifcopenshell.geom.settings();settings.set('iterator-output',ifcopenshell.ifcopenshell_wrapper.SERIALIZED);settings.set('use-world-coords',True)
    if precision:settings.set('precision',precision)
    started=time.perf_counter();it=ifcopenshell.geom.iterator(settings,m,1,include=[e]);assert it.initialize();raw=it.get();shape=TopoDS_Shape();BRepTools.Read_s(shape,io.BytesIO(raw.geometry.brep_data.encode()),BRep_Builder());bounds,volume,tolerance,valid,reason=_inspect_shape(shape)
    expected=math.pi*radius**2*3*takeout-8*radius**3/3;error=volume-expected
    result['rows'].append(dict(radius=radius,takeout=takeout,pose=pose,style=style,precision=precision,volume=volume,analytic=expected,error=error,threshold=max(1e-9,expected*1e-7),within_existing_threshold=abs(error)<=max(1e-9,expected*1e-7),kernel_tolerance=tolerance,valid=valid,reason=reason,seconds=time.perf_counter()-started,ifc_sha256=sha(path)))
   (out/'result.json').write_text(json.dumps(result,indent=2))
result['status']='ANALYTIC_CONVERSION_MATRIX_COMPLETE';(out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps({'output':str(out),'count':len(result['rows']),'failures':[r for r in result['rows'] if not r['valid'] or not r['within_existing_threshold']]}))
