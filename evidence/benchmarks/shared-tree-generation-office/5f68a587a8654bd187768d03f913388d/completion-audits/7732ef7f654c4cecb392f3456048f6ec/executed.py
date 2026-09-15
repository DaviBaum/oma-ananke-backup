"""Read-only completion audit and portable evidence retention for the saved run."""
from itertools import combinations
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import uuid
from support import Original, PRIOR_RUN, PRIOR_CANDIDATE
from oma.ifc.audit import sha256_file
from oma.store import digest

STAGE=Path(__file__).resolve().parent
ROOT=next(p for p in STAGE.parents if (p/'AGENTS.md').exists())
BASE=STAGE/'evidence/5f68a587a8654bd187768d03f913388d'
RUN=BASE/'continuations/cc49aa722c1b4bb29c766592180e440e'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):Path(p).write_text(json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')

def main():
    started=time.monotonic();out=BASE/'completion-audits'/uuid.uuid4().hex;out.mkdir(parents=True)
    shutil.copy2(__file__,out/'executed.py')
    declaration=read(BASE/'predeclaration.json');raw=read(RUN/'result.json');packet=read(BASE/'generated-packet.json')
    hashes={str(p):sha256_file(p) for p in [BASE/'result.json',BASE/'predeclaration.json',BASE/'generated-packet.json',RUN/'result.json',RUN/'predeclaration.json']}
    assert raw['status']=='INPUT_MUTATION' and raw['original_guards']['head_unchanged'] is False
    original=Original();store=Original(Path(raw['store']))
    before=declaration['original_head'];current=original.project(before['id'])
    assert before==current
    incorrectly_decoded=json.loads((BASE/'predeclaration.json').read_text(encoding='cp1252'))['original_head']
    differences={k:{'incorrectly_decoded':incorrectly_decoded.get(k),'actual_utf8_and_db':current.get(k)} for k in current if incorrectly_decoded.get(k)!=current.get(k)}
    assert set(differences)=={'name'}
    assert all(v for k,v in raw['original_guards'].items() if k!='head_unchanged')
    assert original.run(PRIOR_RUN)==declaration['original_run'] and original.candidate(PRIOR_CANDIDATE)==declaration['original_candidate']
    assert all(sha256_file(p)==h for p,h in declaration['original_files'].items())
    src=Path(declaration['application_source'])
    assert {p.relative_to(src).as_posix():sha256_file(p) for p in src.rglob('*.py')}==declaration['application_sources']
    assert digest(packet['authored_query'])==declaration['authored_query_root']
    initial=read(BASE/'result.json');assert store.get(initial['generation_artifact_root'])==packet
    project=store.project(raw['project_id']);selected=store.candidate(raw['selected_candidate_id'])
    assert project['revision']==1 and project['state_root']==selected['state_root'] and project['status']=='ACCEPTED'
    run=store.run(raw['optimization_run_id']);assert run['status']=='COMPLETED' and run['request']['mission']==packet['result']['mission']
    manifest=read(RUN/'export-manifest.json');assert store.get(raw['export']['artifact_root'])==manifest
    expected_bindings={'passing_report','candidate_root','checker_version','mission_hash','rule_hash','objective','scope','check_set','exported_bytes'}
    assert set(manifest['checking']['release_bindings'])==expected_bindings and all(manifest['checking']['release_bindings'].values())
    allrows=raw['candidates']+[raw['fresh_export']];assert len(raw['candidates'])==4
    cases=[]
    for row in allrows:
        candidate=store.candidate(row['candidate_id']);report=store.get(candidate['report_root']);state=store.get(candidate['state_root'])
        assert candidate['status']=='CHECKED' and report['status']=='PASS' and candidate['state_root']==report['candidate_root']
        assert report['checker_version']==declaration['checker_version']
        assert store.get(row['report_root'])==report
        checks={r['id']:r for r in report['results']};assert len(checks)==len(report['results'])
        assert all(x['status'] in ('PASS','NOT_APPLICABLE') for x in checks.values())
        network,=state['physical_networks'];material=store.get(network['geometry_artifact'])
        assert sha256_file(store.resolve_path(material['export_path']))==material['export_sha256']
        directory=RUN/'candidates'/row['candidate_id'];assert sha256_file(directory/'actual.ifc')==material['export_sha256']
        cad=store.get(checks['network-all-source-clearance']['witness']['artifact'])
        sem=store.get(checks['network-native-semantics']['witness']['artifact'])
        guids=[p['ifc_guid'] for p in sem['parts']];ids=[p['component_id'] for p in sem['parts']];n=len(guids)
        assert len(set(guids))==len(set(ids))==n and set(cad['route_guids'])==set(guids)
        assert cad['route_count']==n and cad['obstacle_count']==803 and cad['pairs_accounted']==803*n
        assert len(cad['self_pair_results'])==n*(n-1)//2 and all(p['status']=='PASS' for p in cad['self_pair_results'])
        assert {frozenset(p['participant_guids']) for p in cad['self_pair_results']}=={frozenset(p) for p in combinations(guids,2)}
        assert not any(cad[k] for k in ('failed_pairs','unknown_pairs','blocked_pairs'))
        service=checks['network-demand-conditioned-service']['witness']['calculation']
        assert service['verdict']=='PASS' and set(service['components'])==set(ids) and service['unique_physical_components']==n
        assert service['source_flow_m3_s']=='1/1000'
        assert set(service['paths'])=={'sink-a','sink-b'} and len(service['connections'])==n-1
        assert all(p['status']=='PASS' for p in service['paths'].values()) and all(p['status']=='PASS' for p in service['connections'])
        assert all(x=='PASS' for c in service['components'].values() for x in c['checks'].values())
        port_count=sum(len(c['flow_m3_s']) for c in service['components'].values())
        assert sem['physical_ports']==len(sem['ports'])==port_count
        assert service['section_model']['native_inner_bore_or_wall_thickness_measured'] is False
        assert service['operating_point_solution']=='NOT_ESTABLISHED'
        with store.connect() as db:
            token=db.execute('SELECT e.status,e.report_root,e.evidence_root FROM candidate_check_executions h JOIN check_executions e ON e.execution_id=h.execution_id WHERE h.candidate_id=?',(candidate['id'],)).fetchone()
        assert token[0]=='COMPLETED' and token[1]==candidate['report_root']
        execution=store.get(token[2]);assert execution['status']==execution['supervision']['status']=='COMPLETED'
        assert execution['supervision']['containment']['active_processes']==0
        preservation=row['parsed_preservation'];assert preservation['original_entities']==62930 and not preservation['changed_ids']
        cases.append({'candidate_id':candidate['id'],'state_root':candidate['state_root'],'report_root':candidate['report_root'],
            'native':row['native'],'objective':report['objective'],'export_sha256':material['export_sha256'],
            'service_paths':service['paths'],'port_flow_count':port_count,'connection_conservation_count':n-1,
            'component_conservation_count':n,'managed_completion':'KERNEL_JOB_ACTIVE_PROCESSES_ZERO',
            'original_parsed_entities':62930,'changed_original_entities':0})
    selected_row=next(x for x in cases if x['candidate_id']==selected['id'])
    assert selected_row['objective']=={'fitting_count':1.0,'length_m':5.0}
    assert min(x['objective']['length_m'] for x in cases[:4])==5.0
    assert raw['fresh_export']['candidate_id']==manifest['checking']['exported_candidate_id']
    assert cases[-1]['state_root']!=selected_row['state_root'] and cases[-1]['report_root']!=selected_row['report_root']
    peer=ROOT/'.oma/development/shared-tree-native-workflow-review/catalogue-peer/94c96e0e809943d5a716e1fad5b8ee15'
    provenance=read(peer/'office-check.json')
    assert provenance['status']=='PASS' and provenance['generated_root']==digest(packet['result']['generation'])
    shutil.copy2(peer/'office-check.json',out/'independent-catalogue-provenance.json')
    shutil.copy2(peer/'result.json',out/'catalogue-peer-review.json')
    retained=BASE/'retained-blobs';retained.mkdir(exist_ok=True)
    for blob in store.blobs.glob('*.json.z'):
        shutil.copy2(blob,retained/blob.name);assert sha256_file(blob)==sha256_file(retained/blob.name)
    originals=BASE/'original-ifcs';originals.mkdir(exist_ok=True)
    for p,h in declaration['original_files'].items():
        target=originals/(h+'.ifc');shutil.copy2(p,target);assert sha256_file(target)==h
    assert all(sha256_file(p)==h for p,h in hashes.items())
    result={'status':'PASS','checker_version':declaration['checker_version'],'elapsed_seconds':time.monotonic()-started,
        'raw_results_preserved':hashes,'initial_wrapper_failures':['Exact requested max_results omitted in extra kernel replay; default32 mismatched certificate4',
            'Continuation bootstrap used pre-normalization baseline root instead of generation run base_root',
            'Post-run head name guard used cp1252 decoding of UTF-8 declaration'],
        'utf8_decoding_reconciliation':differences,'original_head_run_candidate_mission_bytes_unchanged':True,
        'authored_query_root':declaration['authored_query_root'],'generation_artifact_root':initial['generation_artifact_root'],
        'generated_catalogue_check':provenance,'cases':cases,'selected_candidate_id':selected['id'],'accepted_revision':1,
        'fresh_export_candidate_id':cases[-1]['candidate_id'],'export_manifest_root':raw['export']['artifact_root'],
        'workflow_elapsed_seconds':raw['elapsed_seconds'],'native_rerun_for_reconciliation':False,
        'scope':'New hypothetical fixed-flow two-sink Office mission; supplied finite catalogue rank and supplied macro provenance, actual native all-original obstacles and fresh export; no all-template/topology/global optimum or pressure-driven operating point claim'}
    write(out/'result.json',result)
    (BASE/'README.md').write_text('A new hypothetical two-sink Office mission was declared before computation from two tee sites, directed Manhattan stubs and one detour plane; no complete trees were authored. The generator returned four alternatives. All four passed native geometry, source clearance and fixed-flow service. Normal selection chose the 5 m, one-tee tree; the other three measure 5.8926990817 m with three fittings. The selected tree was accepted at revision 1 and its exported IFC freshly rechecked.\n\nSelected and fresh export each account for 4 physical components, 9 ports, all 803 original obstacles / 3,212 source pairs and 6 unique component pairs. Each alternative with 8 components accounts for 6,424 source pairs and 28 component pairs. Both prescribed .0005 m³/s deliveries and explicit 100 Pa available-static-pressure requirements pass under the declared ideal-bore/fixed-loss model. This is not a pressure-driven operating-point solution.\n\nOriginal source bytes, original head/run/candidate/mission and all 62,930 canonical parsed original IFC entities remain unchanged. The parsed entity comparison does not claim byte-identical raw serializer spelling. The new mission differs from earlier Office missions; no improvement against them is claimed. Finite catalogue/template membership is checked separately, without claiming all possible templates, topologies or continuous routes are covered.\n\nAll reporting-only failures remain preserved: output-limit replay mismatch before native work; a continuation bootstrap comparison to the unnormalized original root; and the UTF-8 project-name decoding error after a successful native workflow. The independent completion audit reconciles these without regenerating geometry or rerunning native checks.\n',encoding='utf-8')
    files={p.relative_to(BASE).as_posix():{'sha256':sha256_file(p),'bytes':p.stat().st_size} for p in BASE.rglob('*') if p.is_file() and p.name!='files.json'}
    write(BASE/'files.json',{'files':files,'count':len(files),'bytes':sum(x['bytes'] for x in files.values()),'scope':'Path-relative retained evidence inventory; excludes this self-index'})
    print(json.dumps({'status':'PASS','audit':str(out),'files':len(files),'index_sha256':sha256_file(BASE/'files.json')}))

if __name__=='__main__':main()
