"""Freeze a new hypothetical three-sink Office mission before native solving.

Placement screening uses retained display bounds only to schedule the first
native proposal. It certifies no physical clearance and changes no prior mission.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import uuid

import ifcopenshell
import numpy as np
from oma.build_identity import checker_version
from oma.ifc.audit import atomic_json, sha256_file
from oma.ifc.inventory import physical_inventory, inventory_evidence
from oma.routing.network_scenario import SharedNetworkScenario
from oma.store import Store, _Connection, digest

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
STAGE = ROOT/'.oma/development/passive-native-tree'
sys.path.insert(0, str(STAGE/'tests'))
from native_three_sink_fixture import three_sink_spec

PRIOR_RUN = 'deb6bc686d184021aeb3646dd0f67e6c'
PRIOR_CANDIDATE = '123924e355164a5ba330e5b30cc72384'
EXPECTED_SOURCE = '7108485ac8d2856922a83f1353aea8c6eaab60ff393546750bf648200617a544'
EXPECTED_BASELINE = '791776cfca7101c54ee90c0ed45e01a309955e535a1f6fa19110f7a22edc4de2'
BOUNDARY = STAGE/'tests/fixtures/passive-native-tree/new-boundary-declaration.json'
ANCHOR = [24.519774999999974, -7.091475000000081, 5.892220999999475]
ROTATIONS = [[[1,0,0],[0,1,0],[0,0,1]], [[0,-1,0],[1,0,0],[0,0,1]],
             [[-1,0,0],[0,-1,0],[0,0,1]], [[0,1,0],[-1,0,0],[0,0,1]]]


class Original(Store):
    def __init__(self):
        self.directory = (ROOT/'.oma').resolve()
        self.database = self.directory/'oma.sqlite3'
        self.blobs = self.directory/'blobs'
    def connect(self):
        db=sqlite3.connect(self.database.as_uri()+'?mode=ro',uri=True,factory=_Connection)
        db.row_factory=sqlite3.Row
        return db
    def put(self,value):
        raise RuntimeError('Original inputs are read-only')


def placed_spec(rotation, anchor):
    result=deepcopy(three_sink_spec())
    rotation=np.asarray(rotation,dtype=float)
    def point(value):
        return list(rotation@(np.asarray(value)-[0,4,3])+anchor)
    for component in result['components']:
        g=component['geometry']
        if component['kind']=='segment':
            for key in ('start_m','end_m'):g[key]=point(g[key])
        else:
            old=np.asarray(g['frame_m']); frame=np.eye(4)
            frame[:3,:3]=rotation@old[:3,:3]
            frame[:3,3]=point(old[:3,3]);g['frame_m']=frame.tolist()
    return result


def proposed_bounds(spec):
    result=[]
    for c in spec['components']:
        g=c['geometry'];r=c['diameter_m']/2+c['insulation_m']
        if c['kind']=='segment':points=np.array([g['start_m'],g['end_m']])
        else:
            f=np.array(g['frame_m']);L=g['trunk_takeout_m'];B=g['branch_takeout_m']
            points=np.array([f[:3,:3]@v+f[:3,3] for v in ([-L,0,0],[L,0,0],[0,B,0])])
        result.append({'component_id':c['id'],'min':(points.min(axis=0)-r).tolist(),'max':(points.max(axis=0)+r).tolist()})
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',required=True)
    args=parser.parse_args()
    assert checker_version()=='oma-independent-checker/2:'+args.build
    original=Original();prior=original.run(PRIOR_RUN);head=original.project(prior['project_id'])
    candidate=original.candidate(PRIOR_CANDIDATE);baseline=original.get(prior['base_root'])
    assert prior['base_root']==EXPECTED_BASELINE and not baseline.get('routes') and not baseline.get('physical_networks')
    source,=baseline['sources'];assert source['sha256']==EXPECTED_SOURCE
    path=original.resolve_path(source['immutable_path']);assert sha256_file(path)==EXPECTED_SOURCE
    boundary=json.loads(BOUNDARY.read_text(encoding='utf-8'))
    identity=uuid.uuid4().hex;output=STAGE/'evidence/benchmarks/three-sink-office'/identity
    output.mkdir(parents=True)
    # No geometry has been screened when this complete ordered table is written.
    offsets=[(0,0),(-3,0),(3,0),(0,-3),(0,3),(-3,-3),(3,-3),(-3,3),(3,3)]
    poses=[{'id':f'p{i:02d}-r{j}', 'rotation':r, 'tee1_center_m':[ANCHOR[0]+dx,ANCHOR[1]+dy,ANCHOR[2]]}
        for i,(dx,dy) in enumerate(offsets) for j,r in enumerate(ROTATIONS)]
    declaration={'schema':'oma.office-three-sink-placement-input/1','checker_version':checker_version(),
        'script_sha256':sha256_file(Path(__file__)), 'fixture_sha256':sha256_file(STAGE/'tests/native_three_sink_fixture.py'),
        'boundary_path':str(BOUNDARY),'boundary_sha256':sha256_file(BOUNDARY),'new_boundary':boundary,
        'source_path':str(path),'source_sha256':EXPECTED_SOURCE,'baseline_root':prior['base_root'],
        'prior_run':prior,'prior_candidate':candidate,'original_head':head,'poses':poses,
        'screen':'Approximate imported display boxes expanded by the complete proposed envelope and 0.1 m clearance; proposal scheduling only',
        'selection':'First zero-overlap pose in the complete ordered table; if none, stop without a mission or native PASS',
        'scope':'New hypothetical three-sink common-tee mission. No prior mission is changed or reinterpreted.'}
    atomic_json(output/'placement-predeclaration.json',declaration)
    shutil.copyfile(Path(__file__),output/Path(__file__).name)
    shutil.copyfile(STAGE/'tests/native_three_sink_fixture.py',output/'native_three_sink_fixture.py')
    model=ifcopenshell.open(str(path));inventory=physical_inventory(model)
    inv=inventory_evidence(inventory,EXPECTED_SOURCE);atomic_json(output/'source-inventory.json',inv)
    entities={e['provenance']['step_id']:e for e in baseline['entities']}
    assert len(entities)==len(baseline['entities'])
    physical=inventory['physical_step_ids'];assert len(physical)==803
    bounds=[];missing=[]
    for step in physical:
        entity=entities.get(step);box=entity.get('geometry',{}).get('bounds') if entity else None
        if not box:missing.append(step)
        else:bounds.append({'step_id':step,'guid':entity['provenance']['guid'],'min':box['min'],'max':box['max']})
    atomic_json(output/'approximate-source-screen-bounds.json',{'physical_step_ids':physical,'bounds':bounds,'missing_step_ids':missing,
        'source_inventory_root':inv['root'],'authority':'APPROXIMATE_DISPLAY_BOUNDS_ONLY; NO_PHYSICAL_VERDICT'})
    probes=[];chosen=None
    for pose in poses:
        spec=placed_spec(pose['rotation'],pose['tee1_center_m']);boxes=proposed_bounds(spec);overlaps=[]
        for b in boxes:
            for o in bounds:
                if all(b['max'][axis]+.1>=o['min'][axis] and b['min'][axis]-.1<=o['max'][axis] for axis in range(3)):
                    overlaps.append({'component_id':b['component_id'],'obstacle_step_id':o['step_id'],'obstacle_guid':o['guid']})
        probe={'pose_id':pose['id'],'proposed_bounds':boxes,'overlapping_box_pairs':overlaps,
            'all_803_display_bounds_present':not missing,'screen_status':'SCHEDULE_NATIVE_CHECK' if not missing and not overlaps else 'SCREEN_NOT_ELIGIBLE',
            'physical_clearance':'NOT_CHECKED'}
        probes.append(probe)
        if chosen is None and probe['screen_status']=='SCHEDULE_NATIVE_CHECK':chosen=(pose,spec,boxes)
    atomic_json(output/'placement-screen.json',{'predeclaration_root':digest(declaration),'all_poses_tested':len(probes),'probes':probes})
    result={'status':'NO_ELIGIBLE_DISPLAY_SCREEN' if chosen is None else 'MISSION_PREPARED_NATIVE_NOT_RUN',
        'attempt_id':identity,'output':str(output),'placement_predeclaration_root':digest(declaration),
        'poses_predeclared':len(poses),'poses_screened':len(probes),'native_checks_run':0,'checker_version':checker_version()}
    if chosen:
        pose,spec,boxes=chosen;components={c['id']:c for c in spec['components']}
        lower=[min(b['min'][i] for b in boxes)-.2 for i in range(3)]
        upper=[max(b['max'][i] for b in boxes)+.2 for i in range(3)]
        raw={'mission_type':'shared_network','system_type':'PRESSURE_PIPE','start_m':components['trunk']['geometry']['start_m'],
            'sinks':[{'id':s['id'],'demand_id':'demand-'+s['id'][-1],'end_m':components[s['endpoint']['component']]['geometry']['end_m']} for s in spec['sinks']],
            'diameter_m':.1,'insulation_m':.02,'clearance_m':.1,'minimum_straight_m':.05,'minimum_bend_radius_m':.1,
            'allowed_zone':{'min':lower,'max':upper},'scenario_terminals':True,'target_modality':'ENGINEERING_SERVICE',
            'source_representation_policy':'NATIVE_CAD_WITH_SOURCE_VERTEX_HULL_ENCLOSURES',
            'network_alternatives':[spec],'passive_tree':boundary,
            'assumptions':['New hypothetical Office service with three regulated outlet total pressures and two positive common-loss tees',
                'Native IFC outer envelopes with explicitly assumed ideal circular hydraulic bores and declared loss coefficients',
                'Scenario terminals are new hypothetical terminals; no connection to original building ports is claimed',
                'Every original Office physical source object remains in the full native obstacle denominator']}
        mission=SharedNetworkScenario.model_validate(raw).model_dump(mode='json',by_alias=True)
        frozen={'schema':'oma.office-three-sink-frozen-mission/1','mission':mission,'mission_root':digest(mission),
            'baseline_root':prior['base_root'],'source_sha256':EXPECTED_SOURCE,'checker_version':checker_version(),
            'placement_predeclaration_root':digest(declaration),'selected_pose':pose,'source_inventory_root':inv['root'],
            'physical_screen_verdict':'NOT_CHECKED','expected_native_denominators':{'parts':7,'source_obstacles':803,'source_pairs':5621,'self_pairs':21,'ports':16,'connections':6,'deliveries':3},
            'comparison_scope':'One new explicitly declared hypothetical mission; no improvement or old-mission comparison'}
        atomic_json(output/'frozen-mission.json',frozen)
        result.update(mission_root=digest(mission),frozen_mission_sha256=sha256_file(output/'frozen-mission.json'),selected_pose=pose)
    result['originals_unchanged']=(original.run(PRIOR_RUN)==prior and original.project(prior['project_id'])==head
        and original.candidate(PRIOR_CANDIDATE)==candidate and sha256_file(path)==EXPECTED_SOURCE)
    assert result['originals_unchanged']
    atomic_json(output/'preparation-result.json',result)
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
