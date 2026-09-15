from pathlib import Path
from collections import Counter,defaultdict
import hashlib,json,shutil,time,uuid
import ifcopenshell,ifcopenshell.util.element
ROOT=Path(__file__).resolve().parents[3];STAGE=Path(__file__).resolve().parent;DATA=ROOT/'data/ifc-bench/projects/west_riverside_hospital'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False),encoding='utf-8')
def simple(v):
 if isinstance(v,ifcopenshell.entity_instance):return {'type':v.is_a(),'step_id':v.id(),'value':v.wrappedValue} if hasattr(v,'wrappedValue') else {'type':v.is_a(),'step_id':v.id()}
 if isinstance(v,(tuple,list)):return [simple(x) for x in v]
 return v
out=STAGE/'details'/uuid.uuid4().hex;out.mkdir(parents=True);shutil.copyfile(__file__,out/'executed-details.py');results=[]
for filename in ['str_ifc4.ifc','str_ifc2x3.ifc']:
 p=DATA/filename;before=sha(p);model=ifcopenshell.open(str(p));coverage=Counter();qcoverage=Counter();qnames=Counter();pset_values=Counter();rows=[]
 for e in model.by_type('IfcElement'):
  materials=ifcopenshell.util.element.get_materials(e,should_inherit=True)
  labels=tuple(sorted({m.Name for m in materials}));coverage[(e.is_a(),labels)]+=1
  psets=ifcopenshell.util.element.get_psets(e,psets_only=True);qtos=ifcopenshell.util.element.get_psets(e,qtos_only=True)
  for name,props in psets.items():
   for key,v in props.items():
    if key in ['LoadBearing','Reference','Span','Slope']:pset_values[(e.is_a(),name,key,str(v))]+=1
  qcoverage[(e.is_a(),bool(qtos))]+=1
  for qset,vals in qtos.items():
   for q in vals:
    if q!='id':qnames[(e.is_a(),qset,q)]+=1
  rows.append({'guid':e.GlobalId,'step_id':e.id(),'type':e.is_a(),'material_labels':labels,'property_sets':psets,'quantity_sets':qtos})
 relations=[{'step':str(r),'relating_type':r.RelatingElement.is_a(),'related_type':r.RelatedElement.is_a(),'relating_guid':r.RelatingElement.GlobalId,'related_guid':r.RelatedElement.GlobalId} for r in model.by_type('IfcRelConnectsElements')]
 materials=[{'step':str(m),'material':m.Name,'assigned_to_products':sum(count for (kind,labels),count in coverage.items() if m.Name in labels)} for m in model.by_type('IfcMaterial')]
 allprops=Counter(p.Name for p in model.by_type('IfcProperty'));summary={'source':filename,'sha256':before,'material_label_coverage':[{'type':kind,'labels':labels,'count':count} for (kind,labels),count in sorted(coverage.items())],'material_labels':materials,'property_names':dict(allprops),'quantity_coverage':[{'type':kind,'has_quantity_set':present,'count':count} for (kind,present),count in sorted(qcoverage.items())],'quantity_names':[{'type':kind,'set':qset,'name':name,'count':count} for (kind,qset,name),count in sorted(qnames.items())],'load_bearing_assignments':[{'type':kind,'set':pset,'value':v,'count':count} for (kind,pset,key,v),count in pset_values.items() if key=='LoadBearing'],'section_reference_labels':[{'type':kind,'set':pset,'value':v,'count':count} for (kind,pset,key,v),count in pset_values.items() if key=='Reference'],'physical_connection_types':dict(Counter((r['relating_type']+'->'+r['related_type']) for r in relations)),'site_and_project':[{'step':str(e),'info':{k:simple(v) for k,v in e.get_info().items()}} for name in ['IfcProject','IfcSite','IfcBuilding'] for e in model.by_type(name)],'source_unchanged':sha(p)==before}
 assert summary['source_unchanged'];dest=out/filename;dest.mkdir();dump(dest/'element-assignments.json',rows);dump(dest/'physical-connections.json',relations);dump(dest/'summary.json',summary);results.append(summary)
dump(out/'result.json',{'status':'STRUCTURAL_LABEL_AND_QTO_COVERAGE_RECORDED','models':results,'scope':'Literal material labels and IFC quantities; no conversion of a label to authenticated strength or code-design capacity.'});print(json.dumps({'output':str(out),'materials':results[0]['material_label_coverage'],'load_bearing':results[0]['load_bearing_assignments'],'physical_connection_types':results[0]['physical_connection_types'],'property_names':results[0]['property_names']}))
