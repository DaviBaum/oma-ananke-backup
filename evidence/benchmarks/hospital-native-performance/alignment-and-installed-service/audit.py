"""Read-only audit of retained Hospital datums and complete semantic inventories.

No geometry extraction, transform approval, mission creation, or Store mutation.
"""
from pathlib import Path
import collections
import hashlib
import json
import time
import zlib

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
BASE = ROOT / 'evidence/benchmarks/hospital-generated-tree/full-federation-1e87dd6ad9af48b5962cd500603fdfdc'

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()

def record(path):
    return {'path': path.relative_to(ROOT).as_posix(), 'bytes': path.stat().st_size, 'sha256': sha(path)}

start = time.monotonic()
datum_path = BASE / 'datums/actual-datum-records.json'
anchor_path = BASE / 'datums/current-shared-anchor-result.json'
datums = json.loads(datum_path.read_text(encoding='utf-8'))
anchors = json.loads(anchor_path.read_text(encoding='utf-8'))
audit_paths = sorted((BASE / 'source-audits').glob('*.json.z'))
models = [json.loads(zlib.decompress(p.read_bytes())) for p in audit_paths]
originals = [Path(m['source_path']) for m in models]
before = {str(p): sha(p) for p in originals}
assert all(before[m['source_path']] == m['source_sha256'] for m in models)
datum_summary = []
reference = datums[0]
for d, a in zip(datums, anchors['observations']):
    assert d['sha256'] == a['source_sha256']
    datum_summary.append({
        'source': d['source'], 'sha256': d['sha256'], 'units_to_m': d['units_to_m'],
        'site_matrix_m': d['sites'][0]['matrix_m'], 'true_north': a['true_north'],
        'site_z_minus_arc_m': d['sites'][0]['matrix_m'][2][3] - reference['sites'][0]['matrix_m'][2][3],
        'storeys': [{k: s[k] for k in ('guid', 'name', 'elevation_m')} for s in d['storeys']],
        'site_geospatial': a['site_geospatial'],
        'map_conversion_count': len(d['map_conversions']), 'projected_crs_count': len(d['projected_crs']),
        'grid_count': len(d['grids']),
    })

source_summary, candidate_records = [], []
physical_name_maps = {}
for m in models:
    name = Path(m['source_path']).name
    products = {x['step_id']: x for x in m['products']}
    used = collections.Counter(p for c in m['explicit_connections'] for p in (c['port_a_step_id'], c['port_b_step_id']))
    owned = collections.defaultdict(list)
    for p in m['ports']:
        owned[p.get('owner_step_id')].append(p)
    flow_pressure_keys = collections.Counter()
    names = collections.defaultdict(list)
    for x in m['products']:
        for values in x.get('properties', {}).values():
            if isinstance(values, dict):
                flow_pressure_keys.update(k for k in values if 'flow' in k.lower() or 'pressure' in k.lower())
        if x.get('physical') and x.get('name'):
            names[(x['type'], x['name'])].append(x)
    physical_name_maps[name] = names
    source_summary.append({
        'source': name, 'sha256': m['source_sha256'], 'product_count': m['product_count'],
        'product_counts': m['product_counts'], 'ports': len(m['ports']),
        'explicit_connections': len(m['explicit_connections']),
        'unconnected_ports': sum(used[p['step_id']] == 0 for p in m['ports']),
        'multiply_connected_ports': sum(used[p['step_id']] > 1 for p in m['ports']),
        'connection_endpoints_outside_inventory': sorted(set(used) - {p['step_id'] for p in m['ports']}),
        'owner_classes': dict(collections.Counter(products.get(p.get('owner_step_id'), {}).get('type', 'MISSING') for p in m['ports'])),
        'systems': [{k: s.get(k) for k in ('step_id', 'ifc_guid', 'name', 'predefined_type')} for s in m['systems']],
        'property_key_flow_pressure_occurrences': dict(flow_pressure_keys),
        'property_scan_scope': 'Imported product property-set keys, not numeric interpretation of free-text names',
    })
    # Identity-bearing examples, never proposals or authorized connection points.
    candidates = [x for x in m['products'] if x['type'] == 'IfcFireSuppressionTerminal' or
                  (x['type'] == 'IfcBuildingElementProxy' and any(t in (x.get('name') or '').lower() for t in ('toilet', 'lavatory', 'sink', 'pump', 'boiler')))]
    by_family = collections.defaultdict(list)
    for x in candidates:
        by_family[(x.get('name') or '').split(':')[0]].append(x)
    for family, xs in sorted(by_family.items()):
        x = xs[0]
        candidate_records.append({'source': name, 'family': family, 'count': len(xs), 'example': {
            k: x.get(k) for k in ('step_id', 'ifc_guid', 'name', 'type', 'container_name', 'placement_matrix_m', 'properties', 'system_ids')},
            'example_ports': [{k: p.get(k) for k in ('step_id', 'ifc_guid', 'flow_direction', 'flow_axis', 'placement_matrix_m')} for p in owned[x['step_id']]],
            'authority': 'IDENTIFIABLE_EXISTING_ASSET_ONLY; no source/delivery contract or modification authorization'})

arc = physical_name_maps['arc_ifc4.ifc']
name_matches = []
for source, names in physical_name_maps.items():
    if source == 'arc_ifc4.ifc':
        continue
    matches = [list(k) for k, xs in names.items() if len(xs) == 1 and len(arc.get(k, [])) == 1]
    name_matches.append({'source': source, 'unique_exact_physical_type_and_name_matches_to_arc': matches})
after = {str(p): sha(p) for p in originals}
assert before == after
result = {
    'status': 'READ_ONLY_AUDIT_COMPLETE_ALIGNMENT_AND_SERVICE_AUTHORITY_UNRESOLVED',
    'input_files': [record(p) for p in [datum_path, anchor_path, *audit_paths]],
    'original_sources': [record(p) for p in originals], 'original_hashes_unchanged': True,
    'datums': datum_summary, 'source_inventory': source_summary,
    'unique_name_anchor_probe': name_matches,
    'candidate_asset_records_file': 'installed-asset-examples.json',
    'alignment_claim': 'No transform inferred or approved. Similar rotation/origins and storey labels are proposal clues only.',
    'all_ports': sum(s['ports'] for s in source_summary),
    'all_explicit_connections': sum(s['explicit_connections'] for s in source_summary),
    'all_unconnected_ports': sum(s['unconnected_ports'] for s in source_summary),
    'negative_claim_scope': 'No authenticated cross-discipline identity established by inspected datums/GUIDs/exact physical type+name. Geometric correspondence search was not performed.',
    'elapsed_seconds': time.monotonic() - start,
    'not_performed': ['native CAD check', 'geometry matching', 'new service mission', 'transform change', 'source/Store/Git mutation'],
}
for name, value in [('result.json', result), ('installed-asset-examples.json', candidate_records)]:
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({k: result[k] for k in ('status', 'all_ports', 'all_explicit_connections', 'all_unconnected_ports', 'elapsed_seconds')}))
