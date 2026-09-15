from pathlib import Path
import hashlib,io,json,math,sys,time,uuid,shutil
ROOT=Path.cwd();STAGE=ROOT/'.oma/development/hospital-outcome-audit'
SOURCE=ROOT/'.oma/development/hospital-clearance-20260915/runtimes/f716dd5cbdd84134a50d855b217b91a886832abc582ee761b1340cec2026b8e7/src'
sys.path.insert(0,str(SOURCE))
import ifcopenshell,ifcopenshell.geom
from oma.ifc.cad import _inspect_shape
from OCP.TopoDS import TopoDS_Shape
from OCP.BRepTools import BRepTools
from OCP.BRep import BRep_Builder
out=STAGE/'precision-probes'/uuid.uuid4().hex;out.mkdir(parents=True)
shutil.copyfile(__file__,out/'executed-probe.py')
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
materials={
'old':ROOT/'.oma/development/hospital-generated-tree/campaigns/eac181c60f1748f4841b0796dfd69e00/candidates/85453f9ad960487297bf0231cd549a79/materialization.json',
'new':ROOT/'.oma/development/hospital-clearance-20260915/campaign-v1/campaigns/426104a1bed4497ab1fe00902b92014d/candidates/d5e66650ce5a4e09ae9958cc0600d7de/materialization.json'}
result={'status':'RUNNING','observations':{},'scope':'Same immutable IFC inputs, varied numerical conversion precision only; no input mutation, no threshold relaxation.'}
def save():
 (out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps({'output':str(out),**result}),flush=True)
for name,path in materials.items():
 material=json.loads(path.read_text());source=Path(material['export_path']);assert sha(source)==material['export_sha256'];model=ifcopenshell.open(str(source));tee=next(p for p in material['added_parts'] if p['kind']=='tee');entity=model.by_guid(tee['ifc_guid'])
 obs={'ifc_sha256':sha(source),'guid':tee['ifc_guid'],'contexts':[str(c) for c in model.by_type('IfcGeometricRepresentationContext')],'rows':[]};result['observations'][name]=obs
 for precision in [None,1e-5,1e-6,1e-7,1e-8,1e-9]:
  settings=ifcopenshell.geom.settings();settings.set('iterator-output',ifcopenshell.ifcopenshell_wrapper.SERIALIZED);settings.set('use-world-coords',True)
  if precision is not None:settings.set('precision',precision)
  started=time.perf_counter();iterator=ifcopenshell.geom.iterator(settings,model,1,include=[entity]);assert iterator.initialize();serialized=iterator.get();assert serialized.id==entity.id();shape=TopoDS_Shape();BRepTools.Read_s(shape,io.BytesIO(serialized.geometry.brep_data.encode()),BRep_Builder());bounds,volume,tolerance,valid,reason=_inspect_shape(shape)
  brep=out/f'{name}-{precision}.brep';BRepTools.Write_s(shape,str(brep));obs['rows'].append({'precision':precision,'actual_setting':settings.get('precision'),'precision_factor':settings.get('precision-factor'),'volume':volume,'error':volume-(math.pi*(3/64)**2*(3/8)-8*(3/64)**3/3),'tolerance':tolerance,'valid':valid,'reason':reason,'seconds':time.perf_counter()-started,'brep_sha256':sha(brep)});save()
 assert sha(source)==material['export_sha256']
result['status']='UNCHANGED_IFC_CONVERSION_PRECISION_PROBE_COMPLETE';save()
