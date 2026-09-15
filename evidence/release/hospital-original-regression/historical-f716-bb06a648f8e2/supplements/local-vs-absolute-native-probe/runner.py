from pathlib import Path
import hashlib,io,json,math,sys,time,uuid,shutil
import numpy as np
ROOT=Path.cwd();STAGE=Path(__file__).resolve().parent
sys.path.insert(0,str(STAGE/'runtimes/f716dd5cbdd84134a50d855b217b91a886832abc582ee761b1340cec2026b8e7/src'))
import ifcopenshell,ifcopenshell.geom
from oma.ifc.cad import _inspect_shape
from oma.ifc.network_semantics import read_component_geometry
from OCP.TopoDS import TopoDS_Shape
from OCP.BRepTools import BRepTools
from OCP.BRep import BRep_Builder
out=STAGE/'local-tee-probes'/uuid.uuid4().hex;out.mkdir(parents=True)
shutil.copyfile(__file__,out/'runner.py')
path=STAGE/'campaign-v1/campaigns/426104a1bed4497ab1fe00902b92014d/candidates/d5e66650ce5a4e09ae9958cc0600d7de/materialization.json'
material=json.loads(path.read_text());source=Path(material['export_path'])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(source)==material['export_sha256']
model=ifcopenshell.open(str(source));entity=model.by_guid(next(p['ifc_guid'] for p in material['added_parts'] if p['kind']=='tee'))
original=read_component_geometry(model,entity);result={'source_sha256':sha(source),'original_geometry':original,'observations':[]}
solid=entity.Representation.Representations[0].Items[0]
origin=np.asarray(original['center_m'])/0.001
for mode in ('absolute','local_translation'):
 if mode=='local_translation':
  for operand in (solid.FirstOperand,solid.SecondOperand):
   operand.Position.Location.Coordinates=(np.asarray(operand.Position.Location.Coordinates)-origin).tolist()
  entity.ObjectPlacement.RelativePlacement.Location.Coordinates=origin.tolist()
 facts=read_component_geometry(model,entity)
 assert all(np.allclose(facts['caps'][k]['position_m'],v['position_m'],rtol=0,atol=1e-12) for k,v in original['caps'].items())
 settings=ifcopenshell.geom.settings();settings.set('iterator-output',ifcopenshell.ifcopenshell_wrapper.SERIALIZED);settings.set('use-world-coords',True)
 start=time.perf_counter();iterator=ifcopenshell.geom.iterator(settings,model,1,include=[entity]);assert iterator.initialize();serialized=iterator.get()
 shape=TopoDS_Shape();BRepTools.Read_s(shape,io.BytesIO(serialized.geometry.brep_data.encode()),BRep_Builder())
 bounds,volume,tol,valid,reason=_inspect_shape(shape);BRepTools.Write_s(shape,str(out/(mode+'.brep')))
 result['observations'].append({'mode':mode,'volume':volume,'volume_error':volume-facts['analytic_volume_m3'],'tolerance':tol,'valid':valid,'reason':reason,'bounds':bounds,'geometry':facts,'seconds':time.perf_counter()-start})
 (out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps({'out':str(out),**result}),flush=True)
assert sha(source)==material['export_sha256']
