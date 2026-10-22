"""Execute an all-source Hospital purchasing mission on immutable application bytes."""
from pathlib import Path
import argparse, hashlib, json, shutil, sqlite3, sys, time, uuid

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'AGENTS.md').is_file())
sys.path.insert(0, str(ROOT / 'src'))
from oma.store import Store, _Connection, digest
from oma.build_identity import frozen_environment
from oma.export_checks import supervise_check

STAGE = Path(__file__).resolve().parent

def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')

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
        raise RuntimeError('Historical Store is read-only')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mission', type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    mission = json.loads(args.mission.read_text(encoding='utf-8'))
    out = STAGE / 'campaigns' / uuid.uuid4().hex
    out.mkdir(parents=True)
    shutil.copyfile(__file__, out / 'executed.py')
    write(out / 'mission.json', mission)
    env = frozen_environment(STAGE)
    source = Path(env['PYTHONPATH'])
    app = {p.relative_to(source).as_posix(): sha(p) for p in source.rglob('*.py')}
    old = ReadOnly(ROOT / '.oma/development/hospital-generated-tree/stores/6f55c59953f5457daba32dc8223101b2')
    previous = old.project('2e10933dc650425d88a0bd5d0a989174')
    state = old.get(previous['state_root'])
    expected = {'arc_ifc4.ifc', 'str_ifc4.ifc', 'mech_ifc4.ifc', 'plumb_ifc4.ifc',
                'elec_ifc4.ifc', 'sprinkle_ifc4.ifc', 'fire_ifc4.ifc'}
    assert {s['name'] for s in state['sources']} == expected and len(state['sources']) == 7
    before = {s['immutable_path']: sha(s['immutable_path']) for s in state['sources']}
    assert all(before[s['immutable_path']] == s['sha256'] for s in state['sources'])
    store = Store(STAGE / 'stores' / out.name)
    for s in state['sources']:
        assert store.put(old.get(s['audit_root'])) == s['audit_root']
    project = store.create_project('Hospital - whole-building material purchasing', state)
    request = {'operation': 'optimize_procurement', 'budget_seconds': 1200, 'scope': [], 'mission': mission}
    run = store.create_run(project['id'], request)
    declaration = {'checker_version': env['OMA_EXECUTABLE_BUILD'], 'application_sources': app,
        'original_project': previous, 'new_project': project, 'source_files': before,
        'request': request, 'request_root': digest(request), 'run_id': run['id'],
        'store': str(store.directory), 'source_path': str(source),
        'scope': 'Every imported Hospital source; eligible authored linear stock quantities only. No installed geometry or design duty changes.',
        'mission_source': str(args.mission.resolve()), 'mission_file_sha256': sha(args.mission)}
    write(out / 'predeclaration.json', declaration)
    result = {'status': 'RUNNING', 'directory': str(out), 'store': str(store.directory), 'run_id': run['id']}
    write(out / 'result.json', result)
    write(STAGE / 'campaign-active.json', result)
    print(json.dumps(result), flush=True)
    execution = supervise_check([sys.executable, '-m', 'oma.worker', str(store.directory), run['id']],
        environment=env, directory=out / 'supervision', deadline=time.monotonic()+1200,
        memory_limit_bytes=16*1024**3)
    final = store.run(run['id'])
    events, after = [], 0
    while batch := store.events(project['id'], after, 1000):
        events.extend(batch)
        after = batch[-1]['seq']
    write(out / 'events.json', events)
    result.update(execution=execution, run=final, project=store.project(project['id']))
    completed = [e for e in events if e.get('run_id') == run['id'] and e.get('stage') == 'procurement_complete']
    if execution['status'] != 'COMPLETED' or len(completed) != 1 or final['status'] != 'COMPLETED':
        result.update(status='FAILED', seconds=time.monotonic()-started)
        write(out / 'result.json', result)
        raise RuntimeError(json.dumps(final))
    packet_root = completed[0]['payload']['procurement_artifact_root']
    packet = store.get(packet_root)
    plans = store.get(packet['purchasing_plan_root'])
    write(out / 'report.json', packet)
    write(out / 'purchasing-plans.json', plans)
    for s in packet['sources']:
        write(out / 'takeoffs' / (s['name'] + '.json'), store.get(s['takeoff_root']))
    assert before == {p: sha(p) for p in before}
    assert app == {p.relative_to(source).as_posix(): sha(p) for p in source.rglob('*.py')}
    assert store.project(project['id']) == project and old.project(previous['id']) == previous
    assert not store.candidates(project['id'])
    result.update(status='ALL_SEVEN_SOURCE_PURCHASING_SCENARIOS_COMPLETED', packet_root=packet_root,
        purchasing_plan_root=packet['purchasing_plan_root'], summary=packet['summary'],
        comparisons=packet['comparisons'], source_inputs_unchanged=True,
        frozen_source_unchanged=True, project_revision_unchanged=True,
        whole_building_networks_redesigned=False, seconds=time.monotonic()-started)
    write(out / 'result.json', result)
    print(json.dumps({k: result[k] for k in ('status', 'directory', 'summary', 'comparisons', 'seconds')}), flush=True)

if __name__ == '__main__':
    main()
