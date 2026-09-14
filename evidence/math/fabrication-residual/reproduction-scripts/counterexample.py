"""Retain a small source-model/native counterexample; not a new route kernel."""
from pathlib import Path
import hashlib
import itertools
import json
import os
import subprocess
import sys

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'src/oma/build_identity.py').is_file())
STAGE = Path(__file__).resolve().parents[1]


def main():
    from fractions import Fraction as Q
    from oma.build_identity import checker_version
    from oma.optimization import fabrication_frontier as frontier, fabrication_search as graph
    from oma.optimization.fabrication import compile_orthogonal_fabrication, verify_orthogonal_fabrication
    from oma.routing.scenario import RoutingScenario
    from oma.ifc.audit import sha256_file
    from oma.ifc.export import export_route
    from oma.ifc.cad import load_cad, check_pair, cad_check_routes
    from oma.routing.checker import _semantics
    from oma.store import digest
    from test_ifc_pipeline import make_fixture
    from test_optimization_fabrication import actual_ifc_correspondence

    out = STAGE / 'evidence' / 'analytic-two-detours'
    out.mkdir(parents=True, exist_ok=False)
    source = make_fixture(out / 'source.ifc')
    source_hash = sha256_file(source)
    problem = {'schema':'oma.fabrication-grid-problem/1', 'context_root':'NEXT_BEST_SYNTHETIC_SOURCE_PLUS_SEPARATE_ROUTE',
        'source_roots':{'source_sha256':source_hash, 'coverage':'one actual analytic 0..2 metre box; competing route explicitly outside single-route source graph'},
        'allowed_bounds':[[-2,-2,0],[4,5,2]], 'grid_axes':[[-1,0,1,2,3],[-1,0,1,2,4],[1,'3/2']],
        'start':[-1,1,1], 'goal':[3,1,1], 'diameter_m':'1/4', 'insulation_m':'0',
        'bend_radius_m':'1/2', 'minimum_straight_m':'1/8', 'clearance_m':'1/8',
        'outer_obstacles':[{'id':'complete-analytic-wall','bounds':[[0,0,0],[2,2,2]]}]}
    objective = {'schema':'oma.fabrication-grid-cost/1','length_weight':'1','fitting_weight':'0'}
    certificate = frontier.compile_fabrication_frontier(problem, objective, 2)
    verified = frontier.verify_fabrication_frontier(problem, objective, 2, certificate)
    assert verified['status'] == 'PASS', verified
    chosen = certificate['frontier'][2]
    assert chosen['cost'] == ['6','1/2'], chosen
    lower = [[-1,1,1],[-1,-1,1],[3,-1,1],[3,1,1]]
    upper = [[-1,1,1],[-1,4,1],[3,4,1],[3,1,1]]
    assert chosen['points_m'] == [[str(v) for v in p] for p in lower], chosen
    scenario = RoutingScenario(start=lower[0], end=lower[-1], system_type='PRESSURE_PIPE',
        diameter_m=.25, insulation_m=0, bend_radius_m=.5, minimum_straight_m=.125,
        clearance_m=.125, allowed_zone={'min':problem['allowed_bounds'][0], 'max':problem['allowed_bounds'][1]}, scenario_terminals=True)
    options = {'context_root':'independent-complete-polyline', 'outer_obstacles':problem['outer_obstacles'], 'outer_model_root':digest(problem['outer_obstacles'])}
    # Independent complete k=2 contracted-polyline enumeration for these equal
    # transverse endpoint coordinates: the axis sequence must be y-x-y or z-x-z.
    # No search successor/cost/parent or frontier table is used by this oracle.
    enumeration = []
    for axis in (1,2):
        for value in problem['grid_axes'][axis]:
            value = Q(value)
            if value == Q(problem['start'][axis]): continue
            points = [list(map(Q,problem['start'])) for _ in range(4)]
            points[1][axis] = value
            points[2] = list(map(Q,problem['goal'])); points[2][axis] = value
            points[3] = list(map(Q,problem['goal']))
            binary = [[float(x) for x in p] for p in points]
            proof = compile_orthogonal_fabrication(scenario, binary, **options)
            replay = verify_orthogonal_fabrication(scenario, binary, proof, **options)
            length = sum(sum(abs(b-a) for a,b in zip(p,q)) for p,q in zip(points,points[1:]))
            cost = [str(length-2*Q(problem['bend_radius_m'])*2), '1/2']
            enumeration.append({'points_m':[[str(v) for v in p] for p in points], 'cost':cost,
                'fabrication_status':proof['status'], 'independent_check':replay})
    admitted = [e for e in enumeration if e['fabrication_status']=='PASS']
    assert len(admitted)==2 and sorted(e['cost'][0] for e in admitted)==['6','8'], enumeration

    def materialize(name, points):
        spec = {'route_id':name, 'points_m':points, 'system_type':'PRESSURE_PIPE', 'diameter_m':.25,
            'insulation_m':0, 'bend_radius_m':.5, 'minimum_straight_m':.125, 'assumption_root':digest(scenario.model_dump(mode='json'))}
        path = out / (name+'.ifc')
        manifest = export_route(source,path,spec,fresh_recheck=False)
        (out/(name+'.manifest.json')).write_text(json.dumps(manifest,indent=2),encoding='utf8')
        ids = {p['ifc_guid'] for p in manifest['added_parts']}
        geometry, errors = load_cad(path,guids=ids)
        assert not errors and len(geometry)==len(ids) and all(g.valid for g in geometry), errors
        native = cad_check_routes([source],path,ids,clearance_m=.125)
        assert native['coordination_status']==native['self_interference_status']=='PASS', native
        assert native['obstacle_count']==1 and native['pairs_accounted']==len(ids)
        return path, manifest, geometry, native

    cross_points = [[1,-1,.5],[1,-1,1.5]]
    cross_path,cross_manifest,cross_objects,cross_native = materialize('current-competing-route', cross_points)
    native_options = []
    for name,points,cost in [('nominal-minimum',lower,['6','1/2']),('retained-alternative',upper,['8','1/2'])]:
        path,manifest,objects,native = materialize(name,points)
        proof = compile_orthogonal_fabrication(scenario,points,**options)
        replay = verify_orthogonal_fabrication(scenario,points,proof,**options)
        correspondence = actual_ifc_correspondence(path,manifest,proof)
        semantics = _semantics(path,source,manifest,scenario)
        assert not semantics['errors'] and semantics['fitting_count']==2
        assert correspondence['status']=='PASS' and replay['fabrication_status']=='PASS'
        pairs = [check_pair(a,b,clearance_m=.125) for a in objects for b in cross_objects]
        status = 'FAIL' if any(p['status']=='FAIL' for p in pairs) else 'PASS' if all(p['status']=='PASS' for p in pairs) else 'UNKNOWN'
        expected = 'FAIL' if name=='nominal-minimum' else 'PASS'
        assert status==expected and len(pairs)==5, pairs
        native_options.append({'name':name, 'points_m':points, 'exact_fittings':2, 'nominal_cost':cost,
            'export_sha256':sha256_file(path), 'source_coordination':native, 'independent_fabrication':replay,
            'ifc_correspondence':correspondence, 'ifc_semantics':semantics,
            'complete_current_cross_route_pairs':pairs,'cross_route_status':status})
    assert sha256_file(source)==source_hash
    result = {'schema':'oma.next-best-fabrication-design-counterexample/1','status':'REPRODUCED',
        'build':checker_version(), 'script_sha256':sha256_file(__file__), 'problem':problem,'objective':objective,
        'original_frontier':certificate,'independent_frontier_check':verified,
        'independent_exact_two_turn_polyline_enumeration':enumeration,
        'current_competing_route':{'points_m':cross_points,'export_sha256':sha256_file(cross_path),'source_coordination':cross_native},
        'options':native_options,'original_source_unchanged':True,
        'finding':'The sole exact-k nominal minimum fails a fresh current cross-route predicate; a nominally costlier same-k path passes every represented source and cross-route pair.',
        'full_joint_acceptance_executed':False,'continuous_or_native_cost_optimality':False,
        'proposal_policy_omission_not_false_frontier_theorem':True}
    (out/'result.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf8')
    print(json.dumps({'status':result['status'],'build':result['build'],'directory':str(out),
        'nominal_costs':[e['nominal_cost'] for e in native_options], 'cross_route_status':[e['cross_route_status'] for e in native_options]},indent=2))


if __name__=='__main__':
    sys.path.insert(0,str(ROOT/'tests'))
    if '--worker' in sys.argv:
        main()
    else:
        sys.path.insert(0,str(ROOT/'src'))
        from oma.build_identity import frozen_environment
        env=frozen_environment(STAGE/'evidence'/'immutable-builds')
        raise SystemExit(subprocess.call([sys.executable,str(Path(__file__).resolve()),'--worker'],env=env))
