"""Independent finite catalogue fixture. No complete trees occur in its input."""
from copy import deepcopy
from fractions import Fraction as Q
from itertools import combinations
from pathlib import Path
import hashlib
import json
import math

SECTION = {'diameter_m': '1/8', 'insulation_m': '1/32'}
ZONE = {'min': [-2.5, -.5, 2.5], 'max': [4.5, 3.5, 4.5]}

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')

def vector(p): return [str(Q(x)) for x in p]
def cap(p, direction): return {'position_m': vector(p), 'flow_direction': direction}

def scenario(points):
    return {'start': [float(Q(x)) for x in points[0]], 'end': [float(Q(x)) for x in points[-1]],
            'system_type': 'PRESSURE_PIPE', 'diameter_m': .125, 'insulation_m': .03125,
            'bend_radius_m': .25, 'minimum_straight_m': .125, 'clearance_m': .125,
            'allowed_zone': deepcopy(ZONE), 'scenario_terminals': True}

def make_catalogue(sink_count, source_sha):
    from oma.optimization.fabrication import compile_orthogonal_fabrication, verify_orthogonal_fabrication
    from oma.ifc.export import fillet_route
    assert sink_count in (2, 3)
    loss = {'schema': 'oma.reference-fixed-tee-loss/1', 'a:b': '1/5', 'a:branch': '1/5',
            'scope': 'Explicit hypothetical fixed-flow loss declaration; no pressure operating claim.'}
    context = {'schema': 'oma.independent-native-catalogue-fixture/1', 'sinks': sink_count,
               'source_sha256': source_sha, 'bend_radius_m': '1/4', 'minimum_straight_m': '1/8',
               'clearance_m': '1/8', 'allowed_zone_m': ZONE,
               'declared_sink_flows_m3_s': {f'sink-{s}': '1/1000' for s in 'abc'[:sink_count]},
               'service_scope': 'Geometry/fabrication reference only; hydraulic service not checked.'}
    policy = {'schema': 'oma.reference-nominal-skeleton-cost/1', 'straight': 'exact centerline length',
              'elbow': 'R*pi/2 per quarter turn', 'tee': '2*trunk_takeout+branch_takeout counted once',
              'native_objective_lower_bound': False}
    tees = []
    tee_shapes = {}
    for name, x in zip('ABCD'[:2 if sink_count == 2 else 4], range(4)):
        shape = {'kind': 'tee', 'center_m': vector([x, 0, 3]), 'axis_x': [1, 0, 0], 'axis_y': [0, 1, 0],
                 'trunk_takeout_m': '1/4', 'branch_takeout_m': '1/4', 'section': SECTION}
        tee_shapes[name] = shape
        tees.append({'id': name, 'catalogue_root': digest(shape), 'loss_contract_root': digest(loss),
                     **{k: shape[k] for k in ('center_m', 'axis_x', 'axis_y', 'trunk_takeout_m', 'branch_takeout_m')},
                     'nominal_cost': ['3/4', '0']})
    sinks = [{'id': 'sink-a', 'demand_id': 'demand-a', 'cap': cap([1, 3, 3], [0, 1, 0])},
             {'id': 'sink-b', 'demand_id': 'demand-b', 'cap': cap([3 if sink_count == 2 else 4, 0, 3], [1, 0, 0])}]
    if sink_count == 3: sinks.append({'id': 'sink-c', 'demand_id': 'demand-c', 'cap': cap([2, 3, 3], [0, 1, 0])})
    source = {'id': 'source', 'cap': cap([-2, 0, 3], [1, 0, 0])}
    endpoints = {('source', 'out'): source['cap'], **{(s['id'], 'in'): s['cap'] for s in sinks}}
    for t in tees:
        p = list(map(Q, t['center_m']))
        endpoints[t['id'], 'a'] = cap([p[0]-Q(1, 4), p[1], p[2]], [1, 0, 0])
        endpoints[t['id'], 'b'] = cap([p[0]+Q(1, 4), p[1], p[2]], [1, 0, 0])
        endpoints[t['id'], 'branch'] = cap([p[0], p[1]+Q(1, 4), p[2]], [0, 1, 0])
    connectors, artifacts = [], {}
    def add(name, a, b, interior=()):
        start, end = endpoints[a], endpoints[b]
        points = [start['position_m'], *[vector(p) for p in interior], end['position_m']]
        geometry = {'schema': 'oma.reference-manhattan-connector/1', 'points_m': points,
                    'bend_radius_m': '1/4', 'minimum_straight_m': '1/8', 'section': SECTION}
        cert = compile_orthogonal_fabrication(scenario(points), points, context_root=digest(context))
        checked = verify_orthogonal_fabrication(scenario(points), points, cert, context_root=digest(context))
        assert checked['status'] == checked['fabrication_status'] == 'PASS', (name, checked)
        native = fillet_route([[float(Q(x)) for x in p] for p in points], .25, .125)
        assert len(native) == len(cert['components'])
        for n, exact in zip(native, cert['components']):
            assert n['kind'] == exact['kind']
            for key in ('start', 'end') + (('center', 'normal') if n['kind'] == 'elbow' else ()):
                assert n[key] == [float(Q(x)) for x in exact[key]], (name, key)
        length = sum((Q(p['length_m']) for p in cert['components'] if p['kind'] == 'segment'), Q(0))
        pi_coefficient = Q(sum(p['kind'] == 'elbow' for p in native), 8)
        connectors.append({'id': name, 'from': {'node': a[0], 'port': a[1]}, 'to': {'node': b[0], 'port': b[1]},
                           'start_cap': deepcopy(start), 'end_cap': deepcopy(end), 'section': deepcopy(SECTION),
                           'geometry_root': digest(geometry), 'fabrication_root': digest(cert),
                           'nominal_cost': [str(length), str(pi_coefficient)]})
        artifacts[name] = {'geometry': geometry, 'fabrication': cert, 'independent_fabrication_check': checked,
                           'native_fillet_parts': native}
    add('source-A', ('source', 'out'), ('A', 'a'))
    add('source-B', ('source', 'out'), ('B', 'a'))
    add('A-a', ('A', 'branch'), ('sink-a', 'in'), [(0, Q(9, 4), 3), (1, Q(9, 4), 3)])
    add('B-a', ('B', 'branch'), ('sink-a', 'in'))
    if sink_count == 2:
        add('A-b', ('A', 'b'), ('sink-b', 'in')); add('B-b', ('B', 'b'), ('sink-b', 'in'))
    else:
        add('A-C', ('A', 'b'), ('C', 'a')); add('B-C', ('B', 'b'), ('C', 'a'))
        add('C-b', ('C', 'b'), ('sink-b', 'in')); add('C-c', ('C', 'branch'), ('sink-c', 'in'))
        add('source-C', ('source', 'out'), ('C', 'a')); add('C-D', ('C', 'b'), ('D', 'a'))
        add('D-b', ('D', 'b'), ('sink-b', 'in'))
        add('D-a', ('D', 'branch'), ('sink-a', 'in'), [(3, 1, 3), (3, 1, 4), (1, 1, 4),
                                                    (1, Q(9, 4), 4), (1, Q(9, 4), 3)])
    model = {'schema': 'oma.shared-tree-catalogue/1', 'context_root': digest(context),
             'source_roots': {'original_ifc': source_sha}, 'cost_policy_root': digest(policy),
             'section': deepcopy(SECTION), 'source': source, 'sinks': sinks, 'tee_instances': tees, 'connectors': connectors}
    return model, {'context': context, 'cost_policy': policy, 'loss_contract': loss, 'tee_geometry': tee_shapes, 'connectors': artifacts}

def enumerate_oracle(model):
    """Independent exhaustive subset/degree oracle, not the synthesis producer."""
    answers = []
    needed = len(model['sinks'])-1
    sinks = {s['id'] for s in model['sinks']}
    for ts in combinations(model['tee_instances'], needed):
        tee_ids = {t['id'] for t in ts}
        used = tee_ids | sinks | {model['source']['id']}
        for edges in combinations(model['connectors'], 2*needed+1):
            if any(e[k]['node'] not in used for e in edges for k in ('from', 'to')): continue
            outgoing = {(e['from']['node'], e['from']['port']): e for e in edges}
            incoming = {(e['to']['node'], e['to']['port']): e for e in edges}
            if len(outgoing) != len(edges) or len(incoming) != len(edges): continue
            if set(outgoing) != {(model['source']['id'], 'out')} | {(t, p) for t in tee_ids for p in ('b', 'branch')}: continue
            if set(incoming) != {(t, 'a') for t in tee_ids} | {(s, 'in') for s in sinks}: continue
            paths = {}
            def visit(node, prefix, visited):
                if node in visited: raise ValueError('cycle')
                if node in sinks: paths[node] = prefix; return
                for p in (('out',) if node == model['source']['id'] else ('b', 'branch')):
                    e = outgoing[node, p]; visit(e['to']['node'], prefix+[e['id']], visited | {node})
            try: visit(model['source']['id'], [], set())
            except ValueError: continue
            if set(paths) != sinks or set().union(*map(set, paths.values())) != {e['id'] for e in edges}: continue
            a, b = [sum((Q(x['nominal_cost'][i]) for x in [*ts, *edges]), Q(0)) for i in (0, 1)]
            answers.append({'tee_ids': sorted(tee_ids), 'connector_ids': sorted(e['id'] for e in edges),
                            'sink_connector_paths': paths, 'nominal_cost': [str(a), str(b)]})
    return sorted(answers, key=lambda x: float(Q(x['nominal_cost'][0])) + math.pi*float(Q(x['nominal_cost'][1])))

def materialize(model, artifacts, assignment):
    """Only an oracle output is transformed into a complete native NetworkDesign."""
    components, connections, ends = [], [], {}
    def slot(c, p): return {'component': c, 'port': p}
    def join(c, p, d): connections.append({'source': slot(c, p), 'sink': slot(d, 'a')})
    for tid in assignment['tee_ids']:
        t = next(t for t in model['tee_instances'] if t['id'] == tid)
        x, y, z = map(lambda x: float(Q(x)), t['center_m'])
        components.append({'id': tid, 'kind': 'tee', 'system_type': 'PRESSURE_PIPE', 'diameter_m': .125, 'insulation_m': .03125,
                           'geometry': {'frame_m': [[1,0,0,x],[0,1,0,y],[0,0,1,z],[0,0,0,1]],
                                        'trunk_takeout_m': .25, 'branch_takeout_m': .25},
                           'ports': {'a':'SINK','b':'SOURCE','branch':'SOURCE'}})
    for cid in assignment['connector_ids']:
        ids = []
        for i, p in enumerate(artifacts['connectors'][cid]['native_fillet_parts']):
            name = f'{cid}-{i}'; ids.append(name)
            geometry = {'start_m': p['start'], 'end_m': p['end']}
            if p['kind'] == 'elbow': geometry.update(center_m=p['center'], normal=p['normal'], bend_radius_m=p['bend_radius_m'], angle_rad=p['angle_rad'])
            components.append({'id': name, 'kind': p['kind'], 'system_type': 'PRESSURE_PIPE', 'diameter_m': .125,
                               'insulation_m': .03125, 'geometry': geometry, 'ports': {'a':'SINK','b':'SOURCE'}})
        for a, b in zip(ids, ids[1:]): join(a, 'b', b)
        ends[cid] = ids
    for cid in assignment['connector_ids']:
        edge = next(c for c in model['connectors'] if c['id'] == cid)
        if edge['from']['node'] in assignment['tee_ids']: join(edge['from']['node'], edge['from']['port'], ends[cid][0])
        if edge['to']['node'] in assignment['tee_ids']: join(ends[cid][-1], 'b', edge['to']['node'])
    incoming = {c['to']['node']: c for c in model['connectors'] if c['id'] in assignment['connector_ids']}
    first = next(c['id'] for c in model['connectors'] if c['id'] in ends and c['from']['node'] == model['source']['id'])
    paths = []
    for sink in model['sinks']:
        steps = []
        for cid in assignment['sink_connector_paths'][sink['id']]:
            edge = next(c for c in model['connectors'] if c['id'] == cid)
            if edge['from']['node'] in assignment['tee_ids']:
                steps.append({'component': edge['from']['node'], 'entry_port': 'a', 'exit_port': edge['from']['port']})
            steps.extend({'component': c, 'entry_port': 'a', 'exit_port': 'b'} for c in ends[cid])
        paths.append({'demand_id': sink['demand_id'], 'sink_id': sink['id'], 'steps': steps})
    return {'schema': 'oma-physical-network/1', 'network_id': 'reference-'+'-'.join(assignment['tee_ids']),
            'system_type': 'PRESSURE_PIPE', 'components': components, 'connections': connections,
            'source': slot(ends[first][0], 'a'),
            'sinks': [{'id': s['id'], 'endpoint': slot(ends[incoming[s['id']]['id']][-1], 'b')} for s in model['sinks']],
            'demand_paths': paths}

def make_original(path):
    import ifcopenshell.api
    import numpy as np
    path = Path(path)
    if path.exists(): raise FileExistsError(path)
    model = ifcopenshell.api.run('project.create_file', version='IFC4')
    project = ifcopenshell.api.run('root.create_entity', model, ifc_class='IfcProject', name='Frozen independent shared-tree catalogue source')
    ifcopenshell.api.run('unit.assign_unit', model, length={'is_metric':True,'raw':'METERS'})
    units = model.by_type('IfcUnitAssignment')[0]
    units.Units = list(units.Units)+[model.create_entity('IfcSIUnit',UnitType='PLANEANGLEUNIT',Name='RADIAN')]
    ctx = ifcopenshell.api.run('context.add_context', model, context_type='Model')
    body = ifcopenshell.api.run('context.add_context', model, context_type='Model', context_identifier='Body', target_view='MODEL_VIEW', parent=ctx)
    storey = ifcopenshell.api.run('root.create_entity',model,ifc_class='IfcBuildingStorey',name='Protected original storey')
    ifcopenshell.api.run('aggregate.assign_object',model,products=[storey],relating_object=project)
    for i, (position, size) in enumerate([((0,0,0),(2,2,2)),((.875,1.375,2.875),(.25,.25,.25))]):
        obj = ifcopenshell.api.run('root.create_entity',model,ifc_class='IfcBuildingElementProxy',name=f'Protected obstacle {i}')
        rep = ifcopenshell.api.run('geometry.add_wall_representation',model,context=body,length=size[0],thickness=size[1],height=size[2])
        ifcopenshell.api.run('geometry.assign_representation',model,product=obj,representation=rep)
        frame=np.eye(4);frame[:3,3]=position
        ifcopenshell.api.run('geometry.edit_object_placement',model,product=obj,matrix=frame)
        ifcopenshell.api.run('spatial.assign_container',model,products=[obj],relating_structure=storey)
    path.parent.mkdir(parents=True, exist_ok=True); model.write(str(path))
