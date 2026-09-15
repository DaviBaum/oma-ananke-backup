"""Continue saved generation after correcting only the replay's output-limit argument."""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import sys
import time
import traceback
import uuid
from campaign import ROOT, STAGE, BUILD, BASELINE, collect, events
from support import Original, PRIOR_RUN, PRIOR_CANDIDATE
from oma.build_identity import checker_version
from oma.export_checks import supervise_check
from oma.exporting import export_project
from oma.ifc.audit import atomic_json, sha256_file
from oma.store import Store, digest

def main():
    original_output=STAGE/'evidence/5f68a587a8654bd187768d03f913388d'
    old=json.loads((original_output/'result.json').read_text())
    declaration=json.loads((original_output/'predeclaration.json').read_text())
    packet=json.loads((original_output/'generated-packet.json').read_text())
    out=original_output/'continuations'/uuid.uuid4().hex;out.mkdir(parents=True)
    src=Path(os.environ['PYTHONPATH']);version='oma-independent-checker/2:'+BUILD
    assert checker_version()==os.environ['OMA_EXECUTABLE_BUILD']==version
    assert {p.relative_to(src).as_posix():sha256_file(p) for p in src.rglob('*.py')}==declaration['application_sources']
    original=Original();store=Store(Path(old['store']));project=store.project(old['project_id'])
    assert project['state_root']==BASELINE and not store.candidates(project['id'])
    assert store.get(old['generation_artifact_root'])==packet
    bound={str(p):sha256_file(p) for p in [original_output/'result.json',original_output/'predeclaration.json',original_output/'generated-packet.json',Path(__file__),STAGE/'campaign.py',STAGE/'support.py']}
    continuation={'schema':'oma.office-finite-generation-continuation/1','inputs':bound,'checker_version':version,
        'change':'Only pass authored max_results=4 into independent finite verifier; old default32/header mismatch remains retained',
        'native_work_previously_run':False,'mission_regenerated':False,'authored_query_root':declaration['authored_query_root']}
    atomic_json(out/'predeclaration.json',continuation)
    for p in (Path(__file__),STAGE/'campaign.py',STAGE/'support.py'):shutil.copyfile(p,out/p.name)
    result={'status':'RUNNING','continuation_root':digest(continuation),'store':str(store.directory),'project_id':project['id'],
        'original_evidence':str(original_output),'checker_version':version}
    atomic_json(out/'result.json',result);started=time.monotonic()
    print(json.dumps({'stage':'CONTINUATION_PREDECLARED','output':str(out)}),flush=True)
    try:
        from oma.optimization import shared_tree_synthesis as kernel
        def forbidden(*a,**k):raise AssertionError('Producer called')
        kernel.compile_shared_tree_catalogue=forbidden
        generated=packet['result'];limit=packet['authored_query']['max_results'];assert limit==4
        checked=kernel.verify_shared_tree_catalogue(generated['generation']['catalogue'],generated['synthesis']['certificate'],max_results=limit)
        assert checked['status']=='PASS' and checked['proposals']==generated['synthesis']['proposals']
        atomic_json(out/'independent-finite-kernel.json',checked)
        result['generation']={'alternatives':len(generated['mission']['network_alternatives']),
            'connectors':len(generated['generation']['catalogue']['connectors']),
            'tee_sites':len(generated['generation']['catalogue']['tee_instances']),'kernel_status':'PASS',
            'full_generated_provenance':'SEPARATE_CHECK_PENDING','nominal_proposals':checked['proposals']}
        atomic_json(out/'generated-mission.json',generated['mission'])
        run=store.create_run(project['id'],{'operation':'optimize','mission':deepcopy(generated['mission']),'budget_seconds':900})
        result['optimization_run_id']=run['id'];atomic_json(out/'result.json',result)
        worker=supervise_check([sys.executable,'-m','oma.worker',str(store.directory),run['id']],environment=dict(os.environ),directory=out/'native-worker',deadline=time.monotonic()+900,memory_limit_bytes=12*1024**3)
        result['native_worker']=worker
        candidates=[c for c in store.candidates(project['id']) if c['run_id']==run['id']]
        result['candidates']=[collect(store,c,out) for c in candidates]
        current_events=events(store,project['id']);atomic_json(out/'optimization-events.json',current_events)
        assert worker['status']=='COMPLETED' and store.run(run['id'])['status']=='COMPLETED'
        complete=next(e for e in reversed(current_events) if e['run_id']==run['id'] and e['stage']=='complete')
        selected,=complete['payload']['selected_candidate_ids'];candidate=store.candidate(selected)
        assert candidate['status']=='CHECKED';result['selected_candidate_id']=selected
        result['accepted']=store.accept(project['id'],selected,project['revision'],'office-generated:'+run['id'],checker_version=version)
        assert result['accepted']['revision']==project['revision']+1
        atomic_json(out/'result.json',result);print(json.dumps({'stage':'ACCEPTED','candidate_id':selected,'elapsed':time.monotonic()-started}),flush=True)
        exported=export_project(store,project['id'],selected,draft=False,budget_seconds=900);result['export']=exported
        assert exported['status']=='CHECKED_LOCAL_SCOPE' and exported['round_trip']=='PASS'
        manifest=store.get(exported['artifact_root']);atomic_json(out/'export-manifest.json',manifest)
        assert len(manifest['checking']['release_bindings'])==9 and all(v is True for v in manifest['checking']['release_bindings'].values())
        fresh=store.candidate(manifest['checking']['exported_candidate_id']);result['fresh_export']=collect(store,fresh,out)
        assert fresh['status']=='CHECKED' and fresh['state_root']!=candidate['state_root']
        result['status']='GENERATED_SELECTED_ACCEPTED_FRESH_EXPORT_PASS'
    except BaseException:
        result.update(status='INCOMPLETE_OR_FAILED',failure=traceback.format_exc());raise
    finally:
        result['original_guards']={'source_bytes_unchanged':all(sha256_file(p)==h for p,h in declaration['original_files'].items()),
            'head_unchanged':original.project(declaration['original_head']['id'])==declaration['original_head'],
            'run_and_mission_unchanged':original.run(PRIOR_RUN)==declaration['original_run'],
            'candidate_unchanged':original.candidate(PRIOR_CANDIDATE)==declaration['original_candidate'],
            'input_files_unchanged':all(sha256_file(p)==h for p,h in bound.items()),
            'saved_packet_unchanged':store.get(old['generation_artifact_root'])==packet,
            'app_sources_unchanged':{p.relative_to(src).as_posix():sha256_file(p) for p in src.rglob('*.py')}==declaration['application_sources']}
        if not all(result['original_guards'].values()):result['status']='INPUT_MUTATION'
        result['elapsed_seconds']=time.monotonic()-started
        atomic_json(out/'final-events.json',events(store,project['id']));atomic_json(out/'final-project.json',store.project(project['id']))
        if result.get('optimization_run_id'):atomic_json(out/'optimization-run.json',store.run(result['optimization_run_id']))
        atomic_json(out/'result.json',result)
        print(json.dumps({'stage':'FINISHED','status':result['status'],'evidence':str(out),'elapsed_seconds':result['elapsed_seconds']}),flush=True)

if __name__=='__main__':main()
