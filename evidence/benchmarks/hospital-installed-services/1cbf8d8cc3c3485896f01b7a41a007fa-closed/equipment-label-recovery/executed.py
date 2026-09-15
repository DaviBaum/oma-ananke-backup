"""Read-only recovery of authored Hospital engineering data. No inferred loads."""
from pathlib import Path
import collections, gc, gzip, hashlib, json, re, shutil, time, uuid
import ifcopenshell

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'AGENTS.md').exists())
MANIFEST = ROOT / '.oma/development/hospital-cost-readiness/first-inventory/input-manifest.json'

def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def ident(e):
    return {'step_id': e.id(), 'type': e.is_a(), **{k: getattr(e,k,None) for k in ('GlobalId','Name','Description','ObjectType','ElementType','Tag')}}

def enc(x):
    if isinstance(x, ifcopenshell.entity_instance):
        return {'step_id':x.id(),'type':x.is_a(),'step':str(x)}
    if isinstance(x, (list,tuple)): return [enc(v) for v in x]
    if isinstance(x, dict): return {k:enc(v) for k,v in x.items()}
    return x

def write(p, obj):
    p.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')

def writegz(p,obj):
    raw=(json.dumps(obj,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n').encode()
    with p.open('wb') as f:
        with gzip.GzipFile(filename='',mode='wb',fileobj=f,mtime=0) as g: g.write(raw)
    return {'file':p.name,'bytes':p.stat().st_size,'sha256':sha(p),'decoded_bytes':len(raw),'decoded_sha256':hashlib.sha256(raw).hexdigest()}

def main():
    start=time.monotonic()
    out=Path(__file__).parent/uuid.uuid4().hex
    out.mkdir()
    shutil.copyfile(__file__,out/'executed.py')
    shutil.copyfile(MANIFEST,out/'input-manifest.json')
    items=json.loads(MANIFEST.read_text())['original_sources']
    rows=[]
    for source in items:
        path=ROOT/source['path']; before=sha(path)
        assert before==source['sha256']
        model=ifcopenshell.open(str(path))
        counts=collections.Counter(e.is_a() for e in model)
        psets={e.id():e for e in model.by_type('IfcPropertySet')}
        prop_to_psets=collections.defaultdict(set)
        for pset in psets.values():
            for prop in pset.HasProperties or ():
                prop_to_psets[prop.id()].add(pset.id())
        pset_occurrences=collections.defaultdict(set)
        for rel in model.by_type('IfcRelDefinesByProperties'):
            defs=rel.RelatingPropertyDefinition
            for d in defs if isinstance(defs,tuple) else (defs,):
                if d: pset_occurrences[d.id()].update(e.id() for e in rel.RelatedObjects)
        pset_types=collections.defaultdict(set)
        types=model.by_type('IfcTypeObject')
        for typ in types:
            for d in typ.HasPropertySets or ():
                pset_types[d.id()].add(typ.id())
        type_occurrences=collections.defaultdict(set)
        for rel in model.by_type('IfcRelDefinesByType'):
            type_occurrences[rel.RelatingType.id()].update(e.id() for e in rel.RelatedObjects)
        props=[]
        for prop in model.by_type('IfcProperty'):
            defs=prop_to_psets[prop.id()]
            direct=set().union(set(),*(pset_occurrences[d] for d in defs))
            type_ids=set().union(set(),*(pset_types[d] for d in defs))
            inherited=set().union(set(),*(type_occurrences[t] for t in type_ids))
            props.append({'property':enc(prop.get_info()),'step':str(prop),
                          'property_sets':[ident(psets[d]) for d in sorted(defs)],
                          'direct_object_step_ids':sorted(direct),'type_object_step_ids':sorted(type_ids),
                          'inherited_occurrence_step_ids':sorted(inherited)})
        systems=[]
        for e in model.by_type('IfcSystem'):
            member_ids=sorted({m.id() for rel in e.IsGroupedBy or () for m in rel.RelatedObjects})
            systems.append({**ident(e),'step':str(e),'member_step_ids':member_ids,
                            'member_type_counts':dict(collections.Counter(model.by_id(i).is_a() for i in member_ids))})
        type_records=[{**ident(e),'step':str(e),'occurrence_step_ids':sorted(type_occurrences[e.id()])} for e in types]
        products=[{**ident(e),'step':str(e)} for e in model.by_type('IfcProduct') if not e.is_a('IfcDistributionPort')]
        # Retain every label, even if it is not an English label and the clue regex misses it.
        label_clue=re.compile(r'flow|pressure|volt|current|power|watt|amp|circuit|demand|capacity|\b[0-9]+(?:[.,][0-9]+)?\s*(?:k?w|k?va|l/s|m3/h|m³/h|cfm|gpm|pa|kpa|bar|psi|amp|vdc|vac)\b',re.I)
        clues=[e for e in type_records+products+systems if label_clue.search(' '.join(str(e.get(k) or '') for k in ('Name','Description','ObjectType','ElementType','Tag')))]
        meaningful_classes=[k for k in counts if any(t in k for t in ('Performance','TimeSeries','PropertyTable','PropertyBounded','PropertyEnumerated','PropertyReference','Electrical','Circuit','DistributionSystem','RelFlowControl','LoadGroup'))]
        special={k:[enc(e.get_info()) for e in model.by_type(k,include_subtypes=False)] for k in meaningful_classes}
        report={'schema':'oma.hospital-authored-engineering-input-recovery/1','source':source,
                'entity_counts':dict(sorted(counts.items())),
                'property_name_counts':dict(sorted(collections.Counter(p['property']['Name'] for p in props).items())),
                'all_property_records':props,'type_records':type_records,'all_product_labels':products,
                'systems':systems,'label_clues_unvalidated':clues,'special_engineering_classes':special,
                'units':[enc(e.get_info()) for e in model.by_type('IfcUnitAssignment')],
                'source_unchanged':sha(path)==before,
                'scope':'Authored data recovery only. Labels are not authenticated ratings or design requirements. No inferred demands, circuits, pressures, serviceability, costs or code compliance.'}
        assert report['source_unchanged']
        artifact=writegz(out/(path.stem+'.json.gz'),report)
        brief={'source':path.name,'sha256':before,'property_count':len(props),'property_name_counts':report['property_name_counts'],
               'type_count':len(type_records),'product_label_count':len(products),'system_count':len(systems),
               'system_names':[{k:e[k] for k in ('step_id','type','Name','Description','ObjectType')} for e in systems],
               'label_clue_count':len(clues),'type_labels':[{k:e[k] for k in ('step_id','type','Name','Description','ObjectType','ElementType')} for e in type_records],
               'special_engineering_classes':{k:len(v) for k,v in special.items()},'artifact':artifact}
        write(out/(path.stem+'-summary.json'),brief)
        rows.append({k:v for k,v in brief.items() if k not in ('type_labels','system_names')})
        print(json.dumps(rows[-1]),flush=True)
        del model, report, props, products, type_records, special, systems
        gc.collect()
    result={'status':'READ_ONLY_AUTHORED_ENGINEERING_RECOVERY_COMPLETE','elapsed_seconds':time.monotonic()-start,'sources':rows,
            'original_sources_unchanged':all(sha(ROOT/i['path'])==i['sha256'] for i in items),'inferred_contracts_created':0,
            'script_sha256':sha(out/'executed.py'),'manifest_sha256':sha(out/'input-manifest.json')}
    assert result['original_sources_unchanged']
    write(out/'result.json',result)
    write(Path(__file__).parent/'active.json',{'directory':str(out),'result_sha256':sha(out/'result.json')})
    print(json.dumps({'directory':str(out),'status':result['status'],'seconds':result['elapsed_seconds']}),flush=True)

if __name__=='__main__': main()
