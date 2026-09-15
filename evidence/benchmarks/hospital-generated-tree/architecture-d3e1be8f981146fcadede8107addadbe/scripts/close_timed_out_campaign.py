"""Close only this owned interrupted execution after retained kernel-job termination."""
import json, shutil, uuid
from pathlib import Path
from oma.store import Store, digest
from oma.ifc.audit import atomic_json, sha256_file
from oma.build_identity import checker_version

STAGE = Path(__file__).resolve().parent
CAMPAIGN = STAGE / 'campaigns/eac181c60f1748f4841b0796dfd69e00'
def read(p): return json.loads(p.read_text(encoding='utf8'))

raw = read(CAMPAIGN / 'result.json')
declaration = read(CAMPAIGN / 'predeclaration.json')
supervision = raw['native_supervision']
assert raw['status'] == 'NO_CHECKED_INCUMBENT'
assert supervision['status'] == 'UNKNOWN_TIMEOUT'
assert supervision['termination']['method'] == 'TerminateJobObject'
assert supervision['termination']['active_processes_after'] == 0
assert supervision['termination']['remaining_pids'] == []
assert supervision['containment']['assigned_before_resume'] is True
assert supervision['containment']['completion_authority'] == 'KERNEL_JOB_ACTIVE_PROCESSES_ZERO'
assert raw['app_unchanged'] and raw['original_bytes_unchanged']
assert checker_version() == declaration['checker_version']
store = Store(raw['store'])
before = store.project(raw['project_id'])
assert before == declaration['project_before'] == raw['project_after']
run = store.run(raw['optimization_run_id'])
assert run['status'] == 'CHECKING' and run['base_root'] == declaration['baseline_root']
assert supervision['command'][-2:] == [str(store.directory), run['id']]
candidates = [c for c in store.candidates(raw['project_id']) if c['run_id'] == run['id']]
assert len(candidates) == 1
candidate, = candidates
assert candidate['status'] == 'CHECKING' and candidate['report_root'] is None
assert candidate['id'] == raw['candidates'][0]['id']
with store.connect() as db:
    execution = dict(db.execute('SELECT e.* FROM candidate_check_executions h JOIN check_executions e ON e.execution_id=h.execution_id WHERE h.candidate_id=?', (candidate['id'],)).fetchone())
assert execution['status'] == 'RUNNING' and execution['candidate_id'] == candidate['id']
binding = json.loads(execution['binding'])
assert binding['origin_run_id'] == binding['control_run_id'] == run['id']
assert binding['candidate_root'] == candidate['state_root']
out = STAGE / 'completion' / uuid.uuid4().hex
out.mkdir(parents=True)
shutil.copyfile(__file__, out / 'executed.py')
evidence = {'schema':'oma.hospital-owned-timeout-reconciliation/1',
    'raw_result_path':str(CAMPAIGN/'result.json'), 'raw_result_sha256':sha256_file(CAMPAIGN/'result.json'),
    'raw_supervision':supervision, 'run_before':run, 'candidate_before':candidate,
    'execution_before':execution, 'project_before':before,
    'reason':'Outer shared deadline terminated the complete owned kernel job before the inner parent could close its execution; incomplete native result has no publication authority',
    'application_changes':False, 'original_ifc_changes':False}
atomic_json(out/'before.json', evidence)
root = store.put(evidence)
closed = store.finish_check_execution(candidate['id'], execution['execution_id'], status='UNKNOWN_TIMEOUT', evidence_root=root)
assert closed['status'] == 'UNKNOWN' and closed['report_root'] is None
closed_run = store.update_run(run['id'], 'TIMED_OUT', 'Retained outer kernel-job timeout; full source clearance unfinished, no physical verdict', stage='hospital_timeout_reconciliation', artifacts=[root])
assert store.project(raw['project_id']) == before
assert sha256_file(CAMPAIGN/'result.json') == evidence['raw_result_sha256']
assert all(sha256_file(Path(p)) == h for p,h in declaration['original_files'].items())
result = {'status':'OWNED_TIMEOUT_CLOSED_WITHOUT_REPORT', 'evidence_root':root,
    'raw_result_unchanged':True, 'project_head_unchanged':True, 'original_bytes_unchanged':True,
    'candidate_after':closed, 'run_after':closed_run,
    'native_full_source_clearance':'UNKNOWN_NOT_COMPLETED', 'accepted':False, 'exported':False}
atomic_json(out/'result.json', result)
print(json.dumps({'output':str(out), 'status':result['status'], 'candidate_status':closed['status'], 'run_status':closed_run['status']}))
