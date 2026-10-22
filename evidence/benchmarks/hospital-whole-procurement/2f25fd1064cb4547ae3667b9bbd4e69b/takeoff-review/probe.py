from pathlib import Path
import hashlib
import json
import runpy
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'src'))
Source = runpy.run_path(str(ROOT / 'tests/test_service_takeoff.py'))['Source']
import ifcopenshell.geom
import ifcopenshell.util.placement

out = Path(__file__).parent
results = {'source_sha256': hashlib.sha256((ROOT/'src/oma/ifc/service_takeoff.py').read_bytes()).hexdigest(), 'probes': []}

d = out/'nested_physical'; d.mkdir(exist_ok=True)
s = Source(d)
parent, _ = s.segment(depth=2)
child, _ = s.segment(depth=2)
s.named('IfcRelNests', RelatingObject=parent, RelatedObjects=[child])
r = s.run()
results['probes'].append({'case':'nested_physical_segments', 'parent_step_id':parent.id(), 'child_step_id':child.id(),
                         'parent_IsDecomposedBy_count': len(parent.IsDecomposedBy), 'parent_IsNestedBy_count':len(parent.IsNestedBy),
                         'eligible_ids': [p['step_id'] for p in r['pieces']], 'total_length_m':r['summary']['total_eligible_length_m'],
                         'parent_should_be_retained_composite':parent.id() not in {p['step_id'] for p in r['pieces']}})

for axis_x in (5, 15):
    d = out/f'mapping_axis_{axis_x}'; d.mkdir(exist_ok=True)
    s = Source(d)
    p, _ = s.segment(depth=2, profile='rectangle', kind='IfcDuctSegment')
    mapped = s.map(p, origin=(5,0,0), target=(10,0,0))
    s.axis_curve(p, [(axis_x,0,0),(axis_x,0,2)])
    r = s.run()
    transform = ifcopenshell.util.placement.get_mappeditem_transformation(mapped).tolist()
    settings = ifcopenshell.geom.settings()
    shape = ifcopenshell.geom.create_shape(settings,p)
    verts = shape.geometry.verts
    bounds = [[min(verts[i::3]), max(verts[i::3])] for i in range(3)]
    results['probes'].append({'case':f'mapping_axis_{axis_x}', 'native_body_bounds':bounds,
                             'ifcopenshell_mapping_matrix':transform,
                             'eligible':bool(r['pieces']),
                             'retained_reason':r['retained_objects'][0]['reason'],
                             'evidence':r['pieces'][0]['geometry_evidence'] if r['pieces'] else None})

(out/'result.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print(json.dumps(results,indent=2))
