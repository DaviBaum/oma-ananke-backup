"""Read-only actual Hospital STR IFC readiness inventory, no structural solver."""
from pathlib import Path
from collections import Counter,defaultdict
import hashlib,json,re,shutil,sys,time,uuid
import ifcopenshell
import ifcopenshell.util.element
import ifcopenshell.util.unit
ROOT=Path(__file__).resolve().parents[3];STAGE=Path(__file__).resolve().parent;DATA=ROOT/'data/ifc-bench/projects/west_riverside_hospital'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,data):p.write_text(json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
def value(v):
 if isinstance(v,ifcopenshell.entity_instance):
  return {'type':v.is_a(),'value':value(v.wrappedValue)} if v.id()==0 and hasattr(v,'wrappedValue') else {'step_id':v.id(),'type':v.is_a(),'name':getattr(v,'Name',None)}
 if isinstance(v,(tuple,list)):return [value(x) for x in v]
 return v
out=STAGE/'attempts'/uuid.uuid4().hex;out.mkdir(parents=True);shutil.copyfile(__file__,out/'executed-audit.py')
started=time.perf_counter();adjacent={p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(DATA.iterdir()) if p.is_file()};dump(out/'adjacent-input-files.json',adjacent)
provenance={}
for name in ['evidence/ifc/dataset-lock.json','evidence/ifc/acquisition.json','evidence/ifc/federations/west_riverside_hospital-ifc4.json','evidence/ifc/federations/west_riverside_hospital-ifc2x3.json','data/ifc-bench/projects/west_riverside_hospital/model_card.md','data/ifc-bench/projects/west_riverside_hospital/license.txt']:
 p=ROOT/name
 if p.exists():provenance[name]={'sha256':sha(p),'bytes':p.stat().st_size};target=out/'provenance'/p.name;target.parent.mkdir(exist_ok=True);shutil.copyfile(p,target)
source_map={p.relative_to(ROOT/'src').as_posix():sha(p) for p in (ROOT/'src').rglob('*.py')};dump(out/'app-sources.json',source_map)
engineering=re.compile(r'load|moment|shear|axial|stress|yield|compress|tensile|young|elastic|poisson|massdensity|strength|reinforc|rebar|bearing|concrete|steel|grade|structural|support|boundary|section|modulus|force|standard|design|analysis|capacity|reaction|stiffness|resistan|weight|area',re.I)
results=[]
for filename in ['str_ifc4.ifc','str_ifc2x3.ifc']:
 path=DATA/filename;source_hash=sha(path);model=ifcopenshell.open(str(path));counts=Counter(e.is_a() for e in model);dest=out/filename;dest.mkdir()
 schema=ifcopenshell.ifcopenshell_wrapper.schema_by_name(model.schema)
 names={d.name() for d in schema.declarations()}
 relevant=sorted(n for n in names if n.startswith(('IfcStructural','IfcBoundary','IfcReinforc','IfcTendon')) or n in ['IfcRelConnectsStructuralMember','IfcRelConnectsWithEccentricity','IfcRelConnectsStructuralActivity','IfcRelConnectsStructuralElement','IfcRelConnectsElements','IfcRelConnectsPathElements','IfcRelConnectsWithRealizingElements','IfcMaterialProperties','IfcMechanicalMaterialProperties','IfcMechanicalConcreteMaterialProperties','IfcMechanicalSteelMaterialProperties','IfcGeneralMaterialProperties','IfcGeneralProfileProperties','IfcStructuralProfileProperties','IfcProfileProperties','IfcDocumentInformation','IfcDocumentReference','IfcRelAssociatesDocument','IfcClassificationReference'])
 inventories={}
 for name in relevant:
  try:items=model.by_type(name)
  except RuntimeError:continue
  inventories[name]={'including_subtypes':len(items),'exact':counts[name]}
 dump(dest/'entity-counts.json',dict(sorted(counts.items())));dump(dest/'structural-entity-denominators.json',inventories)
 groups=defaultdict(list);property_rows=[];matched=[]
 for prop in model.by_type('IfcProperty'):
  row={k:value(v) for k,v in prop.get_info().items()};row['step']=str(prop);property_rows.append(row)
  if engineering.search(prop.Name or ''):matched.append(row)
 dump(dest/'all-properties.json',property_rows);dump(dest/'engineering-named-properties.json',matched)
 for pset in model.by_type('IfcPropertySet'):
  groups[pset.Name].append(pset.id())
 dump(dest/'property-set-inventory.json',{name:{'count':len(ids),'step_ids':ids} for name,ids in sorted(groups.items())})
 materials=[{**{k:value(v) for k,v in m.get_info().items()},'step':str(m)} for m in model.by_type('IfcMaterial')];dump(dest/'materials.json',materials)
 material_props=[{'type':e.is_a(),'step_id':e.id(),'step':str(e)} for e in model if ('MaterialProperties' in e.is_a() or 'ProfileProperties' in e.is_a())]
 dump(dest/'material-and-profile-properties.json',material_props)
 profiles=[{**{k:value(v) for k,v in p.get_info().items()},'step':str(p)} for p in model.by_type('IfcProfileDef')];dump(dest/'profiles.json',profiles)
 material_links=[{'step':str(e),'related':[{'step_id':p.id(),'type':p.is_a(),'guid':getattr(p,'GlobalId',None)} for p in e.RelatedObjects],'material':value(e.RelatingMaterial)} for e in model.by_type('IfcRelAssociatesMaterial')];dump(dest/'material-assignments.json',material_links)
 product_rows=[];materials_by_type=defaultdict(Counter);reps=Counter();axis_count=0
 for product in model.by_type('IfcElement'):
  material=ifcopenshell.util.element.get_material(product,should_skip_usage=False,should_inherit=True)
  materials_by_type[product.is_a()]['with_material' if material else 'without_material']+=1
  representations=[{'identifier':rep.RepresentationIdentifier,'representation_type':rep.RepresentationType,'item_types':[i.is_a() for i in rep.Items]} for rep in product.Representation.Representations] if product.Representation else []
  for rep in representations:reps[str((rep['identifier'],rep['representation_type']))]+=1
  axis_count+=any(r['identifier']=='Axis' for r in representations)
  product_rows.append({'step_id':product.id(),'guid':product.GlobalId,'type':product.is_a(),'name':product.Name,'object_type':product.ObjectType,'predefined_type':getattr(product,'PredefinedType',None),'material':value(material),'representations':representations})
 dump(dest/'physical-products.json',product_rows)
 docs=[{'type':e.is_a(),'step_id':e.id(),'step':str(e)} for e in model if e.is_a() in ['IfcDocumentInformation','IfcDocumentReference','IfcRelAssociatesDocument','IfcClassificationReference','IfcRelAssociatesClassification']];dump(dest/'document-classification-records.json',docs)
 units=[{'step':str(u),'type':u.is_a(),'unit_type':getattr(u,'UnitType',None)} for a in model.by_type('IfcUnitAssignment') for u in a.Units]
 grade_values=Counter((row['Name'],json.dumps(row.get('NominalValue'),sort_keys=True)) for row in matched)
 summary={'filename':filename,'sha256':source_hash,'bytes':path.stat().st_size,'schema':model.schema,'step_entity_count':sum(counts.values()),'products':len(model.by_type('IfcProduct')),'physical_elements':len(product_rows),'physical_counts':dict(Counter(r['type'] for r in product_rows)),'storeys':[{'step_id':e.id(),'name':e.Name,'elevation':e.Elevation} for e in model.by_type('IfcBuildingStorey')],'header':{'file_name':str(model.header.file_name),'file_description':str(model.header.file_description),'file_schema':str(model.header.file_schema)},'length_unit_scale_to_m':ifcopenshell.util.unit.calculate_unit_scale(model),'units':units,'structural_denominators':inventories,'material_count':len(materials),'material_property_entities':len(material_props),'profile_counts':dict(Counter(p['type'] for p in profiles)),'material_assignment_counts_by_product_type':{k:dict(v) for k,v in materials_by_type.items()},'representation_counts':dict(reps),'physical_products_with_axis_representation':axis_count,'property_set_counts':{k:len(v) for k,v in groups.items()},'property_count':len(property_rows),'engineering_property_value_groups':[{'name':name,'value':json.loads(val),'count':count} for (name,val),count in sorted(grade_values.items())],'document_and_classification_records':len(docs)}
 assert sha(path)==source_hash;dump(dest/'summary.json',summary);results.append(summary)
 print(json.dumps({'file':filename,'physical':summary['physical_counts'],'structural_present':{k:v for k,v in inventories.items() if v['including_subtypes']},'material_properties':len(material_props),'engineering_values':summary['engineering_property_value_groups']}),flush=True)
assert adjacent=={p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(DATA.iterdir()) if p.is_file()}
assert source_map=={p.relative_to(ROOT/'src').as_posix():sha(p) for p in (ROOT/'src').rglob('*.py')}
result={'status':'READ_ONLY_STRUCTURAL_IFC_INVENTORY_COMPLETE','seconds':time.perf_counter()-started,'application_sources':len(source_map),'models':results,'provenance':provenance,'all_inputs_and_application_unchanged':True,'scope':'File-level inventory of the two supplied STR schema exports and their adjacent supplied project directory. No assertion that missing information does not exist in the real project or in unprovided engineering documents. No native CAD calculation, structural analysis, model alteration or code-compliance certification performed.'}
dump(out/'result.json',result);print(json.dumps({'output':str(out),'status':result['status'],'seconds':result['seconds']}))
