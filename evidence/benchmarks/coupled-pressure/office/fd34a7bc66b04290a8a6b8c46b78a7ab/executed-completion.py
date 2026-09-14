"""Independent retained-byte/denominator/math replay after the native campaign."""
from pathlib import Path
from fractions import Fraction as Q
from itertools import combinations
import argparse
import json
import shutil
import sqlite3
import zlib
from prepare import read,write,sha,digest,original_rows,STAGE

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',type=Path,required=True);args=parser.parse_args()
    out=args.attempt.resolve();assert out.is_relative_to(STAGE/'evidence')
    result=read(out/'run-result.json');frozen=read(out/'frozen-mission.json');manifest=read(out/'export-manifest.json')
    assert result['status']=='SELECTED_ACCEPTED_EXPORTED_FRESH_NATIVE_AND_PRESSURE_PASS'
    assert all(v is True for v in result['original_guards'].values()) and result['accepted']['revision']==1
    assert len(result['candidates'])==1 and result['candidates'][0]['candidate_id']==result['selected_candidate_id']
    store=Path(result['store']);report_files=[];checked=[]
    def get(root):
        raw=zlib.decompress((store/'blobs'/(root+'.json.z')).read_bytes());assert __import__('hashlib').sha256(raw).hexdigest()==root
        return json.loads(raw)
    from oma.build_identity import checker_version
    from oma.optimization import coupled_tree_pressure as local
    from oma.optimization import coupled_tree_univalence as global_proof
    assert checker_version()==frozen['checker_version']
    assert sha(local.__file__)=='ce5a264c7815b860b9ce0b8001e1b35cc3ecf7f4acacafc4925f7a6e37060c90'
    assert sha(global_proof.__file__)=='f433e0c007912aa9501306b2bfc95f0809a135e46b5ad898421410eabe10e4df'
    prefixes=[result['selected_candidate_id'],'export-recheck']
    for prefix in prefixes:
        candidate=read(out/(prefix+'.candidate.json'));state=read(out/(prefix+'.state.json'));report=read(out/(prefix+'.report.json'))
        assert candidate['state_root']==report['candidate_root']==digest(state) and digest(report)==candidate['report_root']
        assert report['status']=='PASS' and report['checker_version']==checker_version()
        checks={x['id']:x for x in report['results']};assert len(checks)==len(report['results'])
        assert all(x['status']=='PASS' for x in report['results'])
        sem=get(checks['network-native-semantics']['witness']['artifact']);cad=get(checks['network-all-source-clearance']['witness']['artifact'])
        guids=[p['ifc_guid'] for p in sem['parts']];cids=[p['component_id'] for p in sem['parts']]
        assert len(guids)==len(set(guids))==len(cids)==len(set(cids))==7
        port_ids=[p['port_guid'] for p in sem['ports']];port_slots={(p['component_id'],p['slot']) for p in sem['ports']}
        assert len(port_ids)==len(set(port_ids))==len(port_slots)==16
        assert (cad['route_count'],cad['obstacle_count'],cad['pairs_accounted'])==(7,803,5621)
        assert cad['coordination_status']==cad['self_interference_status']=='PASS'
        assert len(cad['self_pair_results'])==21
        assert {frozenset(p['participant_guids']) for p in cad['self_pair_results']}=={frozenset(p) for p in combinations(guids,2)}
        assert all(p['status']=='PASS' for p in cad['self_pair_results'])
        calculation=read(out/(prefix+'.pressure-calculation.json'));packet=calculation['certificate'];service=calculation['service']
        assert service['counts']=={'physical_ports':16,'deliveries':3,'conservation_identities':17,'head_path_identities':19}
        assert {(p['component'],p['port']) for p in service['physical_ports']}==port_slots
        assert {p['sink'] for p in service['deliveries']}=={'sink-a','sink-b','sink-c'}
        assert all(p['status']=='PASS' for p in service['deliveries'])
        assert all(p['forward_status']==p['maximum_velocity_status']=='PASS' for p in service['physical_ports'])
        assert all(p['difference']=={} for p in service['conservation_identities'])
        # Recheck both mathematical certificates on the actual retained model;
        # native metric authenticity is supplied by the independently retained CAD/semantic report.
        proof=global_proof.verify_coupled_tree_nonnegative_family(packet['model'],packet['flow_box'],packet['local_certificate'],packet['univalence_certificate'])
        assert proof['status']=='PASS' and proof['model_root']==calculation['independent_check']['model_root']
        write(out/(prefix+'.independent-equilibrium-replay.json'),proof)
        material=read(out/(prefix+'.materialization.json'));ifc=out/'actual-ifcs'/(prefix+'.ifc')
        assert sha(ifc)==material['export_sha256']
        original_file=next(iter(read(out/'execution-predeclaration.json')['original_files']))
        assert sha(original_file)==material['source_sha256']=='7108485ac8d2856922a83f1353aea8c6eaab60ff393546750bf648200617a544'
        import ifcopenshell
        before=ifcopenshell.open(original_file);after=ifcopenshell.open(str(ifc))
        missing=[];changed=[]
        for e in before:
            try:other=after.by_id(e.id())
            except RuntimeError:missing.append(e.id());continue
            if str(e)!=str(other):changed.append(e.id())
        assert len(list(before))==62930 and not missing and not changed
        with sqlite3.connect((store/'oma.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
            db.row_factory=sqlite3.Row
            rows=[dict(x) for x in db.execute('SELECT e.* FROM check_executions e JOIN candidate_check_executions h ON h.execution_id=e.execution_id WHERE h.candidate_id=?',(candidate['id'],))]
        execution,=rows;assert execution['status']=='COMPLETED' and execution['report_root']==candidate['report_root']
        evidence=get(execution['evidence_root']);assert evidence['status']==evidence['supervision']['status']=='COMPLETED'
        assert evidence['supervision']['containment']['active_processes']==0
        checked.append({'candidate_id':candidate['id'],'report_root':candidate['report_root'],'ifc_sha256':sha(ifc),
            'model_root':proof['model_root'],'local_root':proof['local_certificate_root'],'global_root':proof['univalence_certificate_root'],
            'native_denominators':{'components':7,'ports':16,'source_obstacles':803,'source_pairs':5621,'self_pairs':21},
            'service_denominators':service['counts'],'original_parsed_entities':62930,'original_entities_unchanged':True,
            'execution_id':execution['execution_id'],'managed_supervision':'COMPLETED_KERNEL_JOB_EMPTY'})
    assert checked[0]['model_root']!=checked[1]['model_root']
    assert read(out/(prefixes[0]+'.pressure-calculation.json'))['service']['deliveries']==read(out/(prefixes[1]+'.pressure-calculation.json'))['service']['deliveries']
    assert len(manifest['checking']['release_bindings'])==9 and all(x is True for x in manifest['checking']['release_bindings'].values())
    for value in frozen['original_stores'].values():assert original_rows(Path(value['directory']),value['run']['id'],value['candidate']['id'])==value
    for p in (store/'checks').rglob('*'):
        if p.is_file():
            target=out/'retained-checks'/p.relative_to(store/'checks');target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():assert sha(target)==sha(p)
            else:shutil.copyfile(p,target)
    audit={'status':'PASS','checker_version':checker_version(),'campaign_result_sha256':sha(out/'run-result.json'),
        'mission_root':frozen['mission_root'],'elapsed_seconds':result['elapsed_seconds'],'cases':checked,
        'all_candidates_retained':len(result['candidates']),'accepted_revision':1,'fresh_delivery_bounds_identical':True,
        'original_stores_unchanged':True,'original_source_bytes_unchanged':True,
        'scope':'New hypothetical unequal-outlet Office mission. Native/metric/model assumptions explicit; no whole-building adequacy or unrestricted topology optimum.'}
    write(out/'independent-completion.json',audit);shutil.copyfile(__file__,out/'executed-completion.py')
    (out/'README.md').write_text('The single predeclared Office unequal-outlet three-sink candidate passed, was normally selected and accepted at revision 1, and its actual exported IFC passed fresh native and pressure checks under one frozen build. Both reports cover seven components, 803 original obstacles (5,621 pairs), 21 unique self pairs, 16 ports, three deliveries, 17 continuity identities and 19 head-path identities. Separate local and global certificates are independently replayed on each retained current model.\n\nThe exact source bytes, both original Stores and all 62,930 canonical parsed original entity strings are unchanged. The exported model has new certificate roots and identical delivery bounds. Raw serialized record spelling is not claimed unchanged. The old common-tee mission remains separate. The new coefficients/regulators and ideal-bore model are explicitly hypothetical assumptions; one declared geometry alternative makes no improvement or unrestricted topology optimality claim.\n',encoding='utf-8')
    inventory=[{'path':p.relative_to(out).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(out.rglob('*')) if p.is_file() and p!=out/'files.json']
    write(out/'files.json',{'files':inventory})
    print(json.dumps({'status':'PASS','audit_sha256':sha(out/'independent-completion.json'),'index_sha256':sha(out/'files.json'),'files':len(inventory),'bytes':sum(x['bytes'] for x in inventory)}))

if __name__=='__main__':main()
