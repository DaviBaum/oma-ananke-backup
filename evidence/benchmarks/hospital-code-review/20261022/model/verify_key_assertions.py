"""Check retained receipts and independently replay segment inheritance via IFC utilities."""
from pathlib import Path
import hashlib,json
import ifcopenshell
import ifcopenshell.util.element as element

OUT=Path(__file__).resolve().parent
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def canonical_hash(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
index=json.loads((OUT/'index.json').read_text())
source_index=json.loads((ROOT/'evidence/benchmarks/hospital-whole-procurement/2f25fd1064cb4547ae3667b9bbd4e69b/original-source-index.json').read_text())
assert index['script_sha256']==sha(OUT/'audit_metadata.py')
recovery=json.loads((OUT/'ifc2x3-property-recovery.json').read_text())
assert recovery['script_sha256']==sha(OUT/'check_ifc2x3_recovery.py')
summary=json.loads((OUT/'summary.json').read_text())
assert summary['script_sha256']==sha(OUT/'summarize_metadata.py')
assert summary['counterpart_recovery_sha256']==sha(OUT/'ifc2x3-property-recovery.json')
sources=[]; independent=[]
for row in index['files']:
    p=OUT/row['result'];assert sha(p)==row['result_sha256']
    d=json.loads(p.read_text(encoding='utf-8'));sources.append(d)
    expected=next(s for s in source_index if s['name']==d['source_name'])
    assert d['source_sha256_before']==d['source_sha256_after']==expected['original_sha256']
    # Utility traversal differs from the producer's aggregated relation-set intersection.
    if d['including_subtypes_counts']['IfcFlowSegment']:
        src=Path(expected['original_path']);before=sha(src);assert before==expected['original_sha256']
        f=ifcopenshell.open(str(src));segments=f.by_type('IfcFlowSegment')
        populated_psets=[];populated_material=[]
        for segment in segments:
            if element.get_psets(segment,psets_only=True,should_inherit=True):populated_psets.append(segment.id())
            if element.get_material(segment,should_inherit=True) is not None:populated_material.append(segment.id())
        assert len(segments)==d['assignment_coverage']['IfcFlowSegment']['total']
        assert not populated_psets and not populated_material
        after=sha(src);assert before==after
        independent.append({'source_name':d['source_name'],'sha256_before':before,'sha256_after':after,'segment_count':len(segments),'segment_step_ids_sha256':canonical_hash(sorted(s.id() for s in segments)),'inherited_pset_nonempty_count':len(populated_psets),'inherited_material_nonempty_count':len(populated_material)})
        print(json.dumps(independent[-1]),flush=True)
assert sum(r['segment_count'] for r in independent)==19352
mep_names={'mech_ifc4.ifc','plumb_ifc4.ifc','sprinkle_ifc4.ifc','elec_ifc4.ifc','fire_ifc4.ifc'}
mep4={d['source_name']:sorted({n for p in d['property_set_summary'].values() for n in p['properties']}) for d in sources if d['source_name'] in mep_names}
allowed={'Reference','IsExternal','Manufacturer','AboveGround','NumberOfStoreys'}
assert all(set(names)<=allowed for names in mep4.values())
mep23={Path(d['file']).name:{'property_names':sorted({n for p in d['property_sets'].values() for n in p}),'nominal_value_type_counts':d['property_nominal_value_type_counts']} for d in recovery['files'] if Path(d['file']).name.replace('ifc2x3','ifc4') in mep_names}
assert len(mep23)==5
assert all(set(d['property_names'])<=allowed for d in mep23.values())
assert all(set(d['nominal_value_type_counts'].get('Reference',{}))<={'IfcIdentifier'} for d in mep23.values())
zero_types=['IfcSpace','IfcZone','IfcApproval','IfcRelAssociatesApproval','IfcDocumentInformation','IfcDocumentReference','IfcStructuralAnalysisModel','IfcStructuralLoad','IfcStructuralLoadGroup','IfcStructuralResultGroup']
assert all(d['including_subtypes_counts'][t]==0 for d in sources for t in zero_types)
assert all(d['IfcSpace_count']==0 and d['source_unchanged'] for d in recovery['files'])
classification_values=sorted({(r['Name'],r['Edition']) for d in sources for r in d['project_identity_approval_and_reference_records'] if r['type']=='IfcClassification'})
assert classification_values==[('Uniformat','1998')]
result={'status':'METADATA_ASSERTIONS_REPLAYED_NOT_CODE_APPROVAL','source_count':7,'source_product_count':sum(d['including_subtypes_counts']['IfcProduct'] for d in sources),'assertions':[{'id':'segment_assignments','result':'PASS_FOR_STATED_METADATA_ASSERTION','total':19352,'direct_or_type_associated_property_set_count':0,'direct_or_type_associated_material_count':0,'independent_replay':'ifcopenshell.util.element.get_psets(psets_only=True, should_inherit=True) and get_material(should_inherit=True) on every segment','per_source':independent,'scope_exclusions':['Textual names, ObjectType, geometry/profile dimensions, parent/system metadata and other indirect associations are not claimed absent.','Generic proxies may represent equipment; absence of typed equipment classes is not equipment absence.']},{'id':'mep_property_names','result':'PASS_FOR_STATED_METADATA_ASSERTION','IFC4_names_by_source':mep4,'IFC2X3_names_and_nominal_types_by_source':mep23,'interpretation':'No separately named duty/flow/pressure/circuit/hydraulic criterion fields occur in these MEP property sets. IFC2X3 Reference values are IfcIdentifier text, not numeric measure fields. Those labels could still contain numbers or design descriptions; they are not authenticated project duty constraints.'},{'id':'missing_semantic_record_types','result':'PASS_FOR_STATED_METADATA_ASSERTION','zero_in_all_seven_IFC4_files':zero_types,'IFC2X3_zero_IfcSpace_in_all_seven':True,'interpretation':'An absent entity/property is an evidence gap and not a code violation.'},{'id':'classification','result':'PASS_FOR_STATED_METADATA_ASSERTION','name_edition_pairs':classification_values,'interpretation':'Uniformat classification metadata is not governing-code adoption or approval evidence.'}],'generic_proxy_counts':{d['source_name']:d['exact_entity_counts'].get('IfcBuildingElementProxy',0) for d in sources},'no_code_compliance_pass':True,'no_code_violation_inferred':True,'inputs':{'index_sha256':sha(OUT/'index.json'),'summary_sha256':sha(OUT/'summary.json'),'counterpart_recovery_sha256':sha(OUT/'ifc2x3-property-recovery.json')},'script_sha256':sha(Path(__file__)),'reader_version':ifcopenshell.version}
(OUT/'verified-key-assertions.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({'status':result['status'],'sha256':sha(OUT/'verified-key-assertions.json')}),flush=True)
