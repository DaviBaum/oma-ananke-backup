"""Read-only authored-quantity review, not CAD takeoff or structural certification."""
from pathlib import Path
from collections import Counter, defaultdict
from decimal import Decimal, localcontext
import hashlib, json, re, shutil, sys, uuid
import ifcopenshell

ROOT = Path(__file__).resolve().parents[3]
STAGE = Path(__file__).resolve().parent
SOURCE = ROOT / 'data/ifc-bench/projects/west_riverside_hospital/str_ifc4.ifc'
RAW = ROOT / '.oma/development/hospital-cost-readiness/first-inventory/str_ifc4-inventory.json'
DETAIL = STAGE / 'details/6641d905bea44776ab251cc68f40175c/str_ifc4.ifc/element-assignments.json'
EXPECTED = '7eed88eb21dafdc5a5950d9b1ee18df3fd00fcd376a14fd1bae80658e371975e'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def dump(p, value):
    p.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')

def main():
    out = STAGE / 'quantity-review' / uuid.uuid4().hex
    out.mkdir(parents=True)
    shutil.copyfile(__file__, out / 'executed-quantity-review.py')
    inputs = {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for p in (SOURCE, RAW, DETAIL, Path(__file__))}
    assert sha(SOURCE) == EXPECTED
    raw = json.loads(RAW.read_text(encoding='utf-8'), parse_float=Decimal)
    elements = json.loads(DETAIL.read_text(encoding='utf-8'), parse_float=Decimal)
    assert raw['source_sha256'] == EXPECTED
    model = ifcopenshell.open(str(SOURCE))
    projects = model.by_type('IfcProject')
    assert len(projects) == 1
    units = projects[0].UnitsInContext.Units
    volume_units = [u for u in units if getattr(u, 'UnitType', None) == 'VOLUMEUNIT']
    assert len(volume_units) == 1
    unit = volume_units[0]
    assert unit.is_a('IfcSIUnit') and unit.Prefix is None and unit.Name == 'CUBIC_METRE'
    selected = [e for e in elements if e['type'] in ('IfcBeam', 'IfcColumn') and e['material_labels'] == ['Metal - Steel - 345 MPa']]
    assert Counter(e['type'] for e in selected) == {'IfcBeam': 1970, 'IfcColumn': 219}
    selected_ids = {e['step_id'] for e in selected}
    assignment = defaultdict(list)
    quantity_uses = Counter()
    name_units = Counter()
    for qset in raw['quantity_sets']:
        for q in qset['quantities']:
            if q['type'].startswith('IfcQuantity'):
                name_units[(q['Name'], q['type'], str(q['Unit']))] += 1
                quantity_uses[q['id']] += len(qset['direct_object_step_ids']) + len(qset['type_object_step_ids'])
        for eid in qset['direct_object_step_ids']:
            assignment[eid].append(qset)
    source_text = SOURCE.read_text(encoding='utf-8')
    source_rows = {int(a): b for a, b in re.findall(r'^#(\d+)\s*=\s*(.*);\s*$', source_text, flags=re.M)}
    contributions = []
    totals = defaultdict(Decimal)
    with localcontext() as ctx:
        ctx.prec = 100
        for e in sorted(selected, key=lambda row: row['step_id']):
            eid = e['step_id']
            assert len(assignment[eid]) == 1, ('nonunique quantity set', eid)
            qset = assignment[eid][0]
            assert qset['name'] == 'BaseQuantities' and qset['direct_object_step_ids'] == [eid] and not qset['type_object_step_ids']
            volumes = [q for q in qset['quantities'] if q['type'] == 'IfcQuantityVolume']
            assert len(volumes) == 1
            q = volumes[0]
            assert q['Name'] == 'GrossVolume' and q['Unit'] is None and quantity_uses[q['id']] == 1
            qentity = model.by_id(q['id'])
            assert qentity.is_a('IfcQuantityVolume') and qentity.Name == 'GrossVolume' and qentity.Unit is None
            native_sets = [r.RelatingPropertyDefinition for r in model.by_id(eid).IsDefinedBy if r.is_a('IfcRelDefinesByProperties') and r.RelatingPropertyDefinition.is_a('IfcElementQuantity')]
            assert [s.id() for s in native_sets] == [qset['step_id']]
            literal = source_rows[q['id']]
            match = re.fullmatch(r"IFCQUANTITYVOLUME\('GrossVolume',\$,\$,([^,]+),\$\)", literal, flags=re.I)
            assert match, literal
            value = Decimal(match.group(1))
            assert value.is_finite() and value > 0
            assert float(value) == float(q['VolumeValue']) == qentity.VolumeValue
            totals[e['type']] += value
            contributions.append({'element_step_id': eid, 'guid': e['guid'], 'type': e['type'], 'material_label': e['material_labels'][0], 'quantity_set_step_id': qset['step_id'], 'quantity_step_id': q['id'], 'authored_gross_volume_m3_decimal': str(value), 'literal_step': literal})
        total = sum(totals.values(), Decimal(0))
    piles = []
    for relation in model.by_type('IfcRelAssociatesClassification'):
        c = relation.RelatingClassification
        if c.is_a('IfcClassificationReference') and c.Name == 'Piles - Steel Pipe':
            for e in relation.RelatedObjects:
                assert e.is_a('IfcFooting')
                piles.append({'element_step_id': e.id(), 'guid': e.GlobalId, 'name': e.Name, 'classification_step_id': c.id(), 'classification_id': c.Identification, 'classification_name': c.Name, 'relationship_step_id': relation.id()})
    assert len(piles) == len({p['element_step_id'] for p in piles}) == 444
    steel_footing_ids = {e['step_id'] for e in elements if e['type'] == 'IfcFooting' and e['material_labels'] == ['Metal - Steel - 345 MPa']}
    assert steel_footing_ids == {p['element_step_id'] for p in piles}
    assert all(not assignment[eid] for eid in steel_footing_ids)
    dump(out / 'contributions.json', contributions)
    dump(out / 'steel-pipe-piles.json', piles)
    dump(out / 'inputs.json', inputs)
    shutil.copyfile(RAW, out / 'bound-raw-quantity-inventory.json')
    assert sha(out / 'bound-raw-quantity-inventory.json') == sha(RAW)
    unchanged = all(sha(ROOT / key) == value for key, value in inputs.items())
    assert unchanged
    result = {'status': 'AUTHORED_STEEL_BEAM_COLUMN_QUANTITIES_UNAMBIGUOUS', 'source_sha256': EXPECTED, 'input_sha256': sha(out / 'inputs.json'), 'element_counts': dict(Counter(e['type'] for e in selected)), 'authored_gross_volume_m3': {k: str(v) for k, v in totals.items()}, 'combined_authored_gross_volume_m3': str(total), 'volume_unit_step': str(unit), 'quantity_names_and_types': [{'name': name, 'type': kind, 'unit_override': override, 'count': count} for (name, kind, override), count in sorted(name_units.items())], 'steel_pipe_piles_typed_as_footing_without_QTO': len(piles), 'all_inputs_unchanged': unchanged, 'scope': 'Exact decimal sum of original authored GrossVolume literals for 1970 steel-labelled beams and 219 steel-labelled columns only. Each element has one directly associated quantity set and one unshared GrossVolume. No CAD calculation, density/mass inference, double-schema sum, other steel component extrapolation, engineering capacity, installed completeness or structural certification.', 'python': sys.executable, 'ifcopenshell_version': ifcopenshell.version}
    dump(out / 'result.json', result)
    print(json.dumps({'directory': str(out), 'result_sha256': sha(out / 'result.json'), 'totals': result['authored_gross_volume_m3'], 'combined': str(total)}))

if __name__ == '__main__':
    main()
