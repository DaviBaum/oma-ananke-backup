"""Read-only property-name recovery check on alternate-schema exports."""
import collections, hashlib, json
from pathlib import Path
import ifcopenshell

OUT=Path(__file__).resolve().parent
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
results=[]
for name in ['arc','str','mech','plumb','elec','sprinkle','fire']:
    p=ROOT/'data/ifc-bench/projects/west_riverside_hospital'/f'{name}_ifc2x3.ifc'
    before=digest(p); f=ifcopenshell.open(str(p))
    props=collections.defaultdict(collections.Counter)
    nominal_types=collections.defaultdict(collections.Counter)
    for s in f.by_type('IfcPropertySet'):
        for prop in s.HasProperties:
            props[s.Name][prop.Name]+=1
            nominal=getattr(prop,'NominalValue',None)
            nominal_types[prop.Name][nominal.is_a() if nominal is not None else 'NO_NOMINAL_VALUE']+=1
    after=digest(p);assert before==after
    r={'file':str(p),'sha256_before':before,'sha256_after':after,'source_unchanged':before==after,'schema':f.schema,'IfcSpace_count':len(f.by_type('IfcSpace')),'property_sets':{n:dict(v) for n,v in props.items()},'property_nominal_value_type_counts':{n:dict(v) for n,v in nominal_types.items()},'scope':'Recovery inventory of property names and nominal value types; not authentication of design values or compliance. Reference text can contain descriptive numerical labels and is not an engineering-duty contract.'}
    results.append(r);print(json.dumps(r),flush=True)
(OUT/'ifc2x3-property-recovery.json').write_text(json.dumps({'files':results,'script_sha256':digest(Path(__file__))},indent=2),encoding='utf-8')
