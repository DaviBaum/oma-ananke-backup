"""Read-only, source-hashed semantic metadata audit. Does not establish compliance."""
from __future__ import annotations
import collections, hashlib, json, re, sys, time
from pathlib import Path
import ifcopenshell

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'AGENTS.md').is_file())
OUT = Path(__file__).resolve().parent
INDEX = ROOT / 'evidence/benchmarks/hospital-whole-procurement/2f25fd1064cb4547ae3667b9bbd4e69b/original-source-index.json'
TERMS = re.compile(r'(?i)(\b(?:code|approved?|approval|certificate|certification|standard|NFPA|ASHRAE|SMACNA|NEC|IEC|IBC|IPC|IMC|UL|FM|ASTM|BS|EN|SCDF|BCA|jurisdiction|permit)\b|fire.?rat|flow.?rate|voltage|current|watt|load|demand|pressure|hazard|occupan|air.?change|ventilat|slope|hydraulic|resistance|insulation|conductor|wire.?size|short.?circuit|ampacity|temperature|sprinkler|k.?factor|density|wall.?thickness|duct.?gauge|yield|compressive|seismic|wind|bending|rating|capacity)')

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def value(x):
    if isinstance(x, ifcopenshell.entity_instance):
        if x.id()==0:
            return {'type':x.is_a(), 'value':value(x[0]) if len(x) else None}
        return {'step_id':x.id(),'ifc_type':x.is_a(),'name':getattr(x,'Name',None),'description':getattr(x,'Description',None)}
    if isinstance(x,(tuple,list)):return [value(v) for v in x]
    if isinstance(x,dict):return {str(k):value(v) for k,v in x.items()}
    return x

def record(x):return value(x.get_info())

def bytype(f,t):
    try:return f.by_type(t)
    except RuntimeError:return []

def audit(row):
    path=Path(row['original_path']); before=digest(path)
    assert before==row['original_sha256']
    start=time.monotonic(); f=ifcopenshell.open(str(path))
    counts=collections.Counter(x.is_a() for x in f)
    count_types=['IfcProduct','IfcSpace','IfcZone','IfcSystem','IfcDistributionSystem','IfcFlowSegment','IfcPipeSegment','IfcDuctSegment','IfcCableSegment','IfcCableCarrierSegment','IfcFlowFitting','IfcFlowController','IfcFlowTerminal','IfcFlowMovingDevice','IfcEnergyConversionDevice','IfcDistributionControlElement','IfcStructuralAnalysisModel','IfcStructuralLoad','IfcStructuralLoadGroup','IfcStructuralResultGroup','IfcApproval','IfcRelAssociatesApproval','IfcDocumentInformation','IfcDocumentReference','IfcClassification','IfcClassificationReference','IfcRelAssociatesClassification','IfcMaterial','IfcRelAssociatesMaterial','IfcMaterialProperties','IfcPropertySet','IfcRelDefinesByProperties','IfcRelDefinesByType','IfcElementQuantity']
    identity=[]
    for t in ['IfcProject','IfcSite','IfcBuilding','IfcPostalAddress','IfcProjectedCRS','IfcMapConversion','IfcApproval','IfcRelAssociatesApproval','IfcDocumentInformation','IfcDocumentReference','IfcClassification','IfcClassificationReference','IfcApplication']:
        identity.extend(record(x) for x in bytype(f,t))
    psets=[]; property_targets=set(); type_property_targets=set(); quantity_targets=set()
    for rel in bytype(f,'IfcRelDefinesByProperties'):
        definition=rel.RelatingPropertyDefinition
        if definition.is_a('IfcPropertySet'):property_targets.update(x.id() for x in rel.RelatedObjects)
        if definition.is_a('IfcElementQuantity'):quantity_targets.update(x.id() for x in rel.RelatedObjects)
    for rel in bytype(f,'IfcRelDefinesByType'):
        if getattr(rel.RelatingType,'HasPropertySets',None):type_property_targets.update(x.id() for x in rel.RelatedObjects)
    for pset in bytype(f,'IfcPropertySet'):
        psets.append({'step_id':pset.id(),'name':pset.Name,'description':pset.Description,'properties':[record(p) for p in pset.HasProperties]})
    materials=[record(x) for x in bytype(f,'IfcMaterial')]
    material_targets=set()
    for rel in bytype(f,'IfcRelAssociatesMaterial'):material_targets.update(x.id() for x in rel.RelatedObjects)
    material_types={x.id() for x in bytype(f,'IfcTypeObject') if x.id() in material_targets}
    material_type_targets=set()
    for rel in bytype(f,'IfcRelDefinesByType'):
        if rel.RelatingType.id() in material_types:material_type_targets.update(x.id() for x in rel.RelatedObjects)
    target_counts={}
    for t in ['IfcProduct','IfcFlowSegment','IfcPipeSegment','IfcDuctSegment','IfcCableCarrierSegment','IfcCableSegment','IfcFlowFitting','IfcFlowTerminal','IfcFlowMovingDevice','IfcEnergyConversionDevice','IfcDistributionControlElement','IfcBeam','IfcColumn','IfcSlab']:
        xs=bytype(f,t); ids={x.id() for x in xs}
        target_counts[t]={'total':len(ids),'instance_property_set':len(ids&property_targets),'type_property_set':len(ids&type_property_targets),'instance_material':len(ids&material_targets),'type_material':len(ids&material_type_targets),'quantity_set':len(ids&quantity_targets)}
    semantic_hits=[]
    for x in f:
        if x.is_a().startswith(('IfcProperty','IfcQuantity','IfcClassification','IfcDocument','IfcApproval','IfcMaterial','IfcStructuralLoad')):
            info=record(x)
            if TERMS.search(json.dumps(info,ensure_ascii=False)):semantic_hits.append(info)
    summaries=collections.defaultdict(lambda:{'instances':0,'properties':collections.defaultdict(set)})
    for p in psets:
        g=summaries[p['name']]; g['instances']+=1
        for prop in p['properties']:
            k=prop.get('Name',''); attrs={a:v for a,v in prop.items() if a not in ['id','type','Name']}
            g['properties'][k].add(json.dumps(attrs,ensure_ascii=False,sort_keys=True))
    summary={k:{'instances':v['instances'],'properties':{n:[json.loads(a) for a in sorted(vals)] for n,vals in v['properties'].items()}} for k,v in summaries.items()}
    after=digest(path); assert before==after
    result={'source_name':row['name'],'source_path':str(path),'source_sha256_before':before,'source_sha256_after':after,'source_unchanged':before==after,'schema':f.schema,'reader':'ifcopenshell '+ifcopenshell.version,'elapsed_seconds':round(time.monotonic()-start,3),'exact_entity_counts':dict(sorted(counts.items())),'including_subtypes_counts':{t:len(bytype(f,t)) for t in count_types},'project_identity_approval_and_reference_records':identity,'property_set_summary':summary,'property_sets':psets,'materials':materials,'assignment_coverage':target_counts,'semantic_keyword_hits':semantic_hits,'limitations':['This is a semantic metadata and assignment audit, not a geometry or code-compliance check.','Keyword matches may be type labels or default values, not authenticated engineering criteria.','No jurisdiction is inferred from default coordinates, source donor, repository country, or model title.','Missing metadata is unresolved evidence, not proof of a violation.']}
    target=OUT/(row['name']+'.metadata.json');target.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'file':row['name'],'seconds':result['elapsed_seconds'],'counts':result['including_subtypes_counts'],'property_set_names':list(summary),'out':str(target)}),flush=True)
    return result

if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    rows=json.loads(INDEX.read_text())
    results=[audit(row) for row in rows]
    index={'status':'SEMANTIC_METADATA_AUDIT_COMPLETE_NOT_CODE_APPROVAL','source_count':len(results),'all_sources_unchanged':all(r['source_unchanged'] for r in results),'files':[{'name':r['source_name'],'sha256':r['source_sha256_before'],'result':r['source_name']+'.metadata.json','result_sha256':digest(OUT/(r['source_name']+'.metadata.json'))} for r in results],'script_sha256':digest(Path(__file__))}
    (OUT/'index.json').write_text(json.dumps(index,indent=2),encoding='utf-8')
