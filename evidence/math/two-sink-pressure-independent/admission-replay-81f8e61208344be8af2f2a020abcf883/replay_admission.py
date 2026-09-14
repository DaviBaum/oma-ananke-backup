"""Actual native positive control and adversarial Store admission replay.

All Stores and physical files are private to the new evidence directory. The
trusted local caller deliberately supplies incomplete reports; no API exploit
or process-supervision bypass is asserted. Historical CHECKED rows are injected
only into unmanaged private candidates to independently exercise acceptance.
"""
from pathlib import Path
import argparse
import copy
import importlib
import json
import os
import shutil
import sqlite3
import sys
import time
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[3]
STAGE = ROOT / '.oma/development/two-sink-pressure'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--checker-version', required=True)
    args = parser.parse_args()
    output = Path(__file__).resolve().parent / ('admission-replay-' + uuid.uuid4().hex)
    output.mkdir()
    for directory in ('tests', 'docs'):
        (output / directory).mkdir()
    for name in ('test_network_pressure.py', 'test_network_integration.py', 'test_network_scenario.py', 'test_ifc_pipeline.py'):
        source = STAGE / 'tests' / name
        if not source.is_file():
            source = ROOT / 'tests' / name
        shutil.copyfile(source, output / 'tests' / name)
    shutil.copyfile(ROOT / 'docs/ifc-network-spec.json', output / 'docs/ifc-network-spec.json')
    shutil.copyfile(Path(__file__), output / 'replay_admission.py')
    args.source = args.source.resolve()
    sys.path[:0] = [str(args.source), str(output / 'tests')]
    os.environ['PYTHONPATH'] = str(args.source)
    os.environ['OMA_EXECUTABLE_BUILD'] = args.checker_version
    os.chdir(output)
    from oma.build_identity import checker_version
    from oma.ifc.audit import atomic_json, sha256_file
    from oma.models import VerificationReport
    from oma.routing.engine import route_project_run
    from oma.routing.selection import try_selection_evidence
    from oma.store import Store, digest
    from oma.worker import WorkerControl
    imported_project = importlib.import_module('test_network_integration').imported_project
    pressure_scenario = importlib.import_module('test_network_pressure').pressure_scenario
    assert checker_version() == args.checker_version
    result = {'status': 'RUNNING', 'checker_version': checker_version(), 'source': str(args.source),
        'output': str(output), 'scope': __doc__, 'original_live_store_access': 'NONE', 'cases': {},
        'snapshot_files': {p.relative_to(output).as_posix(): sha256_file(p)
            for folder in ('tests', 'docs') for p in (output / folder).rglob('*') if p.is_file()},
        'script_sha256': sha256_file(Path(__file__))}
    atomic_json(output / 'result.json', result)
    print(json.dumps({'stage': 'STARTED', 'output': str(output), 'checker_version': args.checker_version}), flush=True)
    started = time.perf_counter()

    def copy_store(source, target):
        target.mkdir()
        with source.connect() as db, sqlite3.connect(target / 'oma.sqlite3') as out:
            db.backup(out)
        shutil.copytree(source.blobs, target / 'blobs')
        return Store(target)

    try:
        fixture = output / 'native-fixture'
        fixture.mkdir()
        store, project = imported_project(fixture)
        mission = pressure_scenario()
        atomic_json(output / 'mission.json', mission)
        run = store.create_run(project['id'], {'operation': 'optimize', 'mission': mission, 'budget_seconds': 90})
        route_project_run(store, run, WorkerControl(store, run['id']))
        candidate, = store.candidates(project['id'])
        intact = store.get(candidate['report_root'])
        state = store.get(candidate['state_root'])
        assert candidate['status'] == 'CHECKED' and intact['status'] == 'PASS', intact
        rows = {r['id']: r for r in intact['results']}
        assert rows['network-pressure-operating-point']['status'] == 'PASS'
        original_head = store.project(project['id'])
        with store.connect() as db:
            original_execution = dict(db.execute('SELECT e.* FROM candidate_check_executions h JOIN check_executions e ON e.execution_id=h.execution_id WHERE h.candidate_id=?', (candidate['id'],)).fetchone())
        assert original_execution['status'] == 'COMPLETED' and original_execution['report_root'] == candidate['report_root']
        for name, value in [('intact-report', intact), ('intact-candidate', candidate), ('intact-state', state), ('intact-execution', original_execution)]:
            atomic_json(output / (name + '.json'), value)
        for identity, name in [('network-all-source-clearance', 'cad'), ('network-native-semantics', 'semantics'), ('network-pressure-operating-point', 'pressure')]:
            atomic_json(output / ('intact-' + name + '.json'), store.get(rows[identity]['witness']['artifact']))
        materialized = store.get(state['physical_networks'][0]['geometry_artifact'])
        input_files = {str(store.resolve_path(s['immutable_path'])): s['sha256'] for s in state['sources']}
        input_files[str(store.resolve_path(materialized['export_path']))] = materialized['export_sha256']
        assert all(sha256_file(Path(p)) == h for p, h in input_files.items())
        result.update(intact_candidate_id=candidate['id'], intact_report_root=candidate['report_root'], input_files=input_files)
        weights = state['mission']['objective_weights']
        mutations = {}
        for variant in ('intact', 'missing', 'duplicate', 'wrong_applicability', 'wrong_scope', 'wrong_mission', 'wrong_rule'):
            report = copy.deepcopy(intact)
            if variant == 'missing':
                report['results'] = [r for r in report['results'] if r['id'] != 'network-pressure-operating-point']
            elif variant == 'duplicate':
                report['results'].append(copy.deepcopy(rows['network-pressure-operating-point']))
            elif variant == 'wrong_applicability':
                next(r for r in report['results'] if r['id'] == 'network-pressure-operating-point')['status'] = 'NOT_APPLICABLE'
            elif variant == 'wrong_scope':
                report['scope'] = 'Narrowed geometric-only scope without the declared pressure service'
            elif variant == 'wrong_mission':
                report['mission_hash'] = '0' * 64
            elif variant == 'wrong_rule':
                report['rule_hash'] = '0' * 64
            mutations[variant] = report
            atomic_json(output / ('report-' + variant + '.json'), report)
        for mode in ('unmanaged_record', 'managed_finish', 'historical_accept'):
            for variant, report in mutations.items():
                label = mode + '-' + variant
                target = copy_store(store, output / label)
                new = target.add_candidate(run['id'], state, {'kind': 'physical_network', 'changed_ids': candidate['changed_ids']})
                outcome = {'candidate_id': new['id'], 'variant': variant, 'mode': mode, 'before_head': target.project(project['id'])}
                execution = None
                try:
                    if mode == 'historical_accept':
                        # Explicit isolated database fixture for an already-stored
                        # same-build report; do not route around a managed token.
                        root = target.put(report)
                        with target.transaction() as db:
                            assert not db.execute('SELECT 1 FROM candidate_check_executions WHERE candidate_id=?', (new['id'],)).fetchone()
                            db.execute("UPDATE candidates SET status='CHECKED',report_root=? WHERE id=?", (root, new['id']))
                        outcome['historical_fixture'] = 'Unmanaged same-build CHECKED row installed in this private copied Store only'
                    elif mode == 'unmanaged_record':
                        target.record_verification(new['id'], report)
                    else:
                        owner = target.create_run(project['id'], {'operation': 'recheck', 'candidate_id': new['id'], 'budget_seconds': 60})
                        execution = uuid.uuid4().hex
                        target.begin_check_execution(new['id'], execution, checker_version=checker_version(),
                            control_run_id=owner['id'], deadline=time.monotonic() + 60)
                        target.finish_check_execution(new['id'], execution, status='COMPLETED', report=report)
                    outcome['publication'] = 'RETURNED'
                except Exception as exc:
                    outcome.update(publication='REJECTED', publication_error={'type': type(exc).__name__, 'message': str(exc)})
                current = target.candidate(new['id'])
                outcome['candidate_after_publication'] = current
                evidence, error = try_selection_evidence(target, target.run(run['id']), new['id'], 'physical_network', weights)
                outcome.update(selection_accepted=evidence is not None, selection_error=error)
                try:
                    accepted = target.accept(project['id'], new['id'], original_head['revision'], label, checker_version=checker_version())
                    outcome.update(acceptance='ACCEPTED', accepted=accepted)
                except Exception as exc:
                    outcome.update(acceptance='REJECTED', acceptance_error={'type': type(exc).__name__, 'message': str(exc)})
                outcome['after_head'] = target.project(project['id'])
                if variant == 'intact':
                    correct = (outcome['publication'] == 'RETURNED' and current['status'] == 'CHECKED'
                        and outcome['selection_accepted'] and outcome['acceptance'] == 'ACCEPTED'
                        and outcome['after_head']['revision'] == original_head['revision'] + 1)
                else:
                    correct = (outcome['acceptance'] == 'REJECTED' and outcome['after_head'] == outcome['before_head']
                        and not outcome['selection_accepted']
                        and (mode == 'historical_accept' or (outcome['publication'] == 'REJECTED' and current['status'] != 'CHECKED')))
                outcome['status'] = 'PASS' if correct else 'FAIL'
                result['cases'][label] = outcome
                atomic_json(output / (label + '.json'), outcome)
                atomic_json(output / 'result.json', result)
        result['input_files_unchanged'] = all(sha256_file(Path(p)) == h for p, h in input_files.items())
        result['native_fixture_head_unchanged'] = store.project(project['id']) == original_head
        result['snapshot_unchanged'] = all(sha256_file(output / p) == h for p, h in result['snapshot_files'].items())
        result['status'] = 'PASS' if (all(r['status'] == 'PASS' for r in result['cases'].values())
            and result['input_files_unchanged'] and result['native_fixture_head_unchanged'] and result['snapshot_unchanged']) else 'FAIL'
    except BaseException:
        result.update(status='HARNESS_FAILED', error=traceback.format_exc())
        raise
    finally:
        result['seconds'] = time.perf_counter() - started
        atomic_json(output / 'result.json', result)
        print(json.dumps({'status': result['status'], 'seconds': result['seconds'], 'output': str(output),
            'case_results': {k: v['status'] for k, v in result['cases'].items()}}), flush=True)
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
