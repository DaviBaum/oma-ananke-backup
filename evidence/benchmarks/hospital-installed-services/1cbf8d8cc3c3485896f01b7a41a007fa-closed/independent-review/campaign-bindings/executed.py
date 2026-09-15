"""Run the new supervised job on every installed Hospital source/network."""
from pathlib import Path
import hashlib, json, os, shutil, sqlite3, sys, time, uuid

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'AGENTS.md').is_file())
sys.path.insert(0, str(ROOT / 'src'))
from oma.store import Store, _Connection, digest
from oma.build_identity import frozen_environment
from oma.export_checks import supervise_check

STAGE = Path(__file__).resolve().parent

def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def write(p, value):
    Path(p).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')

class ReadOnly(Store):
    def __init__(self, path):
        self.directory = Path(path).resolve()
        self.database = self.directory / 'oma.sqlite3'
        self.blobs = self.directory / 'blobs'
    def connect(self):
        db = sqlite3.connect(self.database.as_uri() + '?mode=ro', uri=True, factory=_Connection)
        db.row_factory = sqlite3.Row
        return db
    def put(self, value):
        raise RuntimeError('Historical source store is read-only')

def main():
    started = time.monotonic()
    out = STAGE / 'campaigns' / uuid.uuid4().hex
    out.mkdir(parents=True)
    shutil.copyfile(__file__, out / 'executed.py')
    env = frozen_environment(STAGE)
    source = Path(env['PYTHONPATH'])
    app = {p.relative_to(source).as_posix(): sha(p) for p in source.rglob('*.py')}
    old = ReadOnly(ROOT / '.oma/development/hospital-generated-tree/stores/6f55c59953f5457daba32dc8223101b2')
    previous = old.project('2e10933dc650425d88a0bd5d0a989174')
    state = old.get(previous['state_root'])
    labels = {'arc_ifc4.ifc': 'ARCHITECTURE', 'str_ifc4.ifc': 'STRUCTURE', 'mech_ifc4.ifc': 'HVAC',
              'plumb_ifc4.ifc': 'PLUMBING', 'elec_ifc4.ifc': 'ELECTRICAL', 'sprinkle_ifc4.ifc': 'FIRE', 'fire_ifc4.ifc': 'FIRE'}
    assert {s['name'] for s in state['sources']} == set(labels) and len(state['sources']) == 7
    before = {s['immutable_path']: sha(s['immutable_path']) for s in state['sources']}
    assert all(before[s['immutable_path']] == s['sha256'] for s in state['sources'])
    store = Store(STAGE / 'stores' / out.name)
    for s in state['sources']:
        audit = old.get(s['audit_root'])
        assert store.put(audit) == s['audit_root']
    project = store.create_project('Hospital - all installed MEP services', state)
    request = {'operation': 'design_services', 'budget_seconds': 1200, 'scope': [], 'mission': {
        'schema': 'oma.building-service-design/1',
        'source_disciplines': {s['id']: labels[s['name']] for s in state['sources']}, 'contracts': []}}
    run = store.create_run(project['id'], request)
    declaration = {'checker_version': env['OMA_EXECUTABLE_BUILD'], 'application_sources': app,
        'original_project': previous, 'new_project': project, 'source_files': before, 'request': request,
        'request_root': digest(request), 'run_id': run['id'], 'store': str(store.directory),
        'source_labels': 'Explicit dataset discipline labels for complete coverage, not engineering role or service-duty inference',
        'scope': 'All seven actual Hospital source audits and installed service networks, no invented example terminals or design demands',
        'native_geometry_checks': False, 'source_path': str(source)}
    write(out / 'predeclaration.json', declaration)
    result = {'status': 'RUNNING', 'directory': str(out), 'store': str(store.directory), 'run_id': run['id']}
    write(out / 'result.json', result)
    write(STAGE / 'campaign-active.json', result)
    print(json.dumps(result), flush=True)
    execution = supervise_check([sys.executable, '-m', 'oma.worker', str(store.directory), run['id']],
        environment=env, directory=out / 'supervision', deadline=time.monotonic() + 1200, memory_limit_bytes=16*1024**3)
    final = store.run(run['id'])
    events = []
    after = 0
    while batch := store.events(project['id'], after, 1000):
        events.extend(batch)
        after = batch[-1]['seq']
    completed = [e for e in events if e.get('run_id') == run['id'] and e.get('stage') == 'service_design_complete']
    result.update(execution=execution, run=final, project=store.project(project['id']))
    assert execution['status'] == 'COMPLETED' and len(completed) == 1, final
    packet_root = completed[0]['payload']['service_design_artifact_root']
    packet = store.get(packet_root)
    write(out / 'whole-project-service-report.json', packet)
    write(out / 'events.json', events)
    source_results = []
    for s in packet['sources']:
        graph = store.get(s['network_inventory_root'])
        write(out / 'networks' / (s['name'] + '.json'), graph) if False else None
        target = out / 'networks' / (s['name'] + '.json')
        target.parent.mkdir(exist_ok=True)
        write(target, graph)
        source_results.append({**s, 'graph_sha256': sha(target)})
    assert before == {p: sha(p) for p in before}
    assert app == {p.relative_to(source).as_posix(): sha(p) for p in source.rglob('*.py')}
    assert store.project(project['id']) == project and old.project(previous['id']) == previous
    assert not store.candidates(project['id'])
    result.update(status='WHOLE_PROJECT_SERVICE_JOB_COMPLETED_WITH_DESIGN_INPUTS_REQUIRED', report_root=packet_root,
        report_sha256=sha(out / 'whole-project-service-report.json'), sources=source_results,
        summary=packet['summary'], source_inputs_unchanged=True, project_revision_unchanged=True,
        whole_building_optimized=packet['whole_building_optimized'], seconds=time.monotonic()-started)
    write(out / 'result.json', result)
    print(json.dumps({k: result[k] for k in ('status','directory','summary','seconds','whole_building_optimized')}), flush=True)

if __name__ == '__main__':
    main()
