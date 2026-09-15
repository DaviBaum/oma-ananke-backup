"""Proposal-only screening from complete imported bounds; never native authority."""
import json,os,sys,time,uuid
from pathlib import Path
import numpy as np
from oma.store import Store,digest
from oma.ifc.audit import atomic_json,sha256_file
from oma.build_identity import checker_version

STAGE=Path(__file__).resolve().parent
def main():
    result_path=Path(sys.argv[1]);r=json.loads(result_path.read_text(encoding='utf8'))
    assert r['status']=='IMPORTED_CURRENT_SOURCE_INVENTORY'
    store=Store(r['store']);project=store.project(r['project_id']);state=store.get(project['state_root'])
    out=STAGE/'screening'/uuid.uuid4().hex;out.mkdir(parents=True)
    levels=[168.875,173.875,178.875,183.875]
    origins=[[float(x),float(y),z] for z in levels for x in range(16,69,4) for y in range(64,125,4)]
    pre={'schema':'oma.hospital-proposal-screen/1','baseline_root':project['state_root'],'checker_version':checker_version(),
        'source_sha256s':[s['sha256'] for s in state['sources']], 'script_sha256':sha256_file(Path(__file__)),
        'candidate_origins_m':origins,'zone_offsets_m':{'min':[-.25,-.25,-.25],'max':[4.25,1.25,.25]},
        'policy':'Complete imported represented physical AABBs for proposal ranking only; prefer empty zone near existing MEP, no geometry/clearance verdict or object deletion.'}
    atomic_json(out/'predeclaration.json',pre)
    rows=[e for e in state['entities'] if e['geometry']['status']=='represented' and e['geometry'].get('bounds')]
    lo=np.array([e['geometry']['bounds']['min'] for e in rows]);hi=np.array([e['geometry']['bounds']['max'] for e in rows])
    mep=np.array([i for i,e in enumerate(rows) if e.get('discipline') in ('plumb_ifc4','mech_ifc4','sprinkle_ifc4')])
    if not len(mep):mep=np.arange(len(rows))
    probes=[]
    for point in origins:
        p=np.array(point);lower=p+[-.25,-.25,-.25];upper=p+[4.25,1.25,.25]
        overlap=np.all(hi>=lower,axis=1)&np.all(lo<=upper,axis=1)
        center=p+[2,.5,0];dist=np.linalg.norm(np.maximum(np.maximum(lo[mep]-center,center-hi[mep]),0),axis=1)
        nearest=int(mep[int(np.argmin(dist))])
        probes.append({'origin_m':point,'overlapping_imported_boxes':int(sum(overlap)),
            'nearest_mep_box_distance_m':float(min(dist)),'nearest_mep_entity_id':rows[nearest]['id'],
            'overlap_examples':[rows[i]['id'] for i in np.flatnonzero(overlap)[:8]]})
    ordered=sorted(probes,key=lambda p:(p['overlapping_imported_boxes'],abs(p['nearest_mep_box_distance_m']-1),p['origin_m']))
    result={'status':'PROPOSAL_SCREEN_COMPLETE','predeclaration_root':digest(pre),'baseline_root':project['state_root'],
        'federation_status':state['derived_artifacts']['local_coordinate_evidence']['status'],
        'represented_bound_count':len(rows),'all_probes':probes,'ranked_first_12':ordered[:12],
        'selected_proposal':ordered[0],'source_inventory':r['sources']}
    atomic_json(out/'result.json',result);print(json.dumps({'output':str(out),'federation':result['federation_status'],'selected':ordered[:4]}),flush=True)
if __name__=='__main__':main()
