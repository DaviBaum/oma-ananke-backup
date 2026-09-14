"""Isolated native, trusted-caller missing pressure obligation reproduction."""
from pathlib import Path
import copy
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import time
import traceback
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
STAGE = ROOT / '.oma/development/two-sink-pressure'
FROZEN = STAGE / 'validation-runtimes/runtimes/b61a7a9f20f0f5dccc7f4f69207037e36110e895fdd3835f232d4f3f62d6d895/src'
EXPECTED = 'oma-independent-checker/2:b61a7a9f20f0f5dccc7f4f69207037e36110e895fdd3835f232d4f3f62d6d895'
sys.path.insert(0, str(HERE / 'tests'))
from oma.build_identity import checker_version
from oma.ifc.audit import atomic_json, sha256_file
from oma.models import VerificationReport
from oma.routing.engine import route_project_run
from oma.routing.selection import try_selection_evidence
from oma.store import Store, digest
from oma.worker import WorkerControl
from test_network_integration import imported_project
from test_network_pressure import pressure_scenario


def copied_store(source, target):
    target.mkdir()
    with source.connect() as db, sqlite3.connect(target / 'oma.sqlite3') as out:
        db.backup(out)
    shutil.copytree(source.blobs, target / 'blobs')
    return Store(target)


def main():
    assert checker_version() == EXPECTED == os.environ['OMA_EXECUTABLE_BUILD']
    result = {'status': 'RUNNING', 'checker_version': EXPECTED,
        'scope': 'Trusted report producer/caller boundary, not an ordinary API exploit; genuine native PASS narrowed by one required result only',
        'original_live_store_access': 'NONE', 'source_runtime': str(FROZEN)}
    atomic_json(HERE / 'result.json', result)
    start = time.perf_counter()
    try:
        fixture = HERE / 'native-fixture'
        fixture.mkdir()
        store, project = imported_project(fixture)
        mission = pressure_scenario()
        atomic_json(HERE / 'mission.json', mission)
        run = store.create_run(project['id'], {'operation': 'optimize', 'mission': mission, 'budget_seconds': 90})
        route_project_run(store, run, WorkerControl(store, run['id']))
        candidate, = store.candidates(project['id'])
        intact = store.get(candidate['report_root'])
        state = store.get(candidate['state_root'])
        assert candidate['status'] == 'CHECKED' and intact['status'] == 'PASS', intact
        rows = {r['id']: r for r in intact['results']}
        assert rows['network-pressure-operating-point']['status'] == 'PASS'
        assert rows['network-all-source-clearance']['status'] == 'PASS'
        assert rows['network-all-component-pairs']['status'] == 'PASS'
        atomic_json(HERE / 'intact-native-report.json', intact)
        atomic_json(HERE / 'intact-candidate.json', candidate)
        atomic_json(HERE / 'intact-state.json', state)
        native = store.get(rows['network-all-source-clearance']['witness']['artifact'])
        semantics = store.get(rows['network-native-semantics']['witness']['artifact'])
        pressure = store.get(rows['network-pressure-operating-point']['witness']['artifact'])
        for name, artifact in [('cad', native), ('semantics', semantics), ('pressure', pressure)]:
            atomic_json(HERE / ('intact-' + name + '.json'), artifact)
        materialized = store.get(state['physical_networks'][0]['geometry_artifact'])
        input_files = {str(store.resolve_path(s['immutable_path'])): s['sha256'] for s in state['sources']}
        input_files[str(store.resolve_path(materialized['export_path']))] = materialized['export_sha256']
        assert all(sha256_file(Path(p)) == h for p, h in input_files.items())
        narrowed = copy.deepcopy(intact)
        narrowed['results'] = [r for r in narrowed['results'] if r['id'] != 'network-pressure-operating-point']
        assert len(intact['results']) - len(narrowed['results']) == 1
        report = VerificationReport.model_validate(narrowed)
        assert report.status == 'PASS'
        atomic_json(HERE / 'narrowed-report.json', narrowed)
        original_head = store.project(project['id'])
        result.update(intact_candidate_id=candidate['id'], intact_report_root=candidate['report_root'],
            intact_managed_execution=store.candidate(candidate['id'])['status'],
            changed_report_paths=['results/network-pressure-operating-point (removed)'],
            narrowed_report_root=digest(narrowed), native_denominator={k: native[k] for k in
                ('obstacle_count', 'route_count', 'pairs_accounted', 'failed_pairs', 'unknown_pairs', 'blocked_pairs', 'self_interference_status')},
            unique_native_components=semantics['physical_components'], input_files=input_files,
            cases={})
        for mode in ('unmanaged_record', 'managed_finish'):
            target = copied_store(store, HERE / mode)
            copied_candidate = target.add_candidate(run['id'], state,
                {'kind': 'physical_network', 'changed_ids': candidate['changed_ids']})
            outcome = {'candidate_id': copied_candidate['id'], 'project_head_before': target.project(project['id'])}
            try:
                if mode == 'unmanaged_record':
                    published = target.record_verification(copied_candidate['id'], report)
                else:
                    owner = target.create_run(project['id'], {'operation': 'recheck', 'candidate_id': copied_candidate['id'], 'budget_seconds': 60})
                    execution = uuid.uuid4().hex
                    binding = target.begin_check_execution(copied_candidate['id'], execution,
                        checker_version=checker_version(), control_run_id=owner['id'], deadline=time.monotonic() + 60)
                    outcome.update(control_run_id=owner['id'], execution_id=execution, binding=binding,
                        process_scope='Direct trusted parent finish call using genuine native report with one obligation removed; no fake process supervision receipt claimed')
                    published = target.finish_check_execution(copied_candidate['id'], execution, status='COMPLETED', report=report)
                outcome['published_candidate'] = published
                evidence, error = try_selection_evidence(target, target.run(run['id']), copied_candidate['id'], 'physical_network', mission.get('objective_weights', {'length_m': 1, 'fitting_count': 1}))
                outcome.update(selection_evidence=evidence, selection_error=str(error))
                try:
                    accepted = target.accept(project['id'], copied_candidate['id'], original_head['revision'], mode,
                        checker_version=checker_version())
                    outcome['accepted'] = accepted
                    outcome['status'] = 'MISSING_REQUIRED_OBLIGATION_ACCEPTED'
                except Exception:
                    outcome['status'] = 'ACCEPT_REJECTED'
                    outcome['accept_error'] = traceback.format_exc()
            except Exception:
                outcome['status'] = 'PUBLICATION_REJECTED'
                outcome['publication_error'] = traceback.format_exc()
            outcome['project_head_after'] = target.project(project['id'])
            result['cases'][mode] = outcome
            atomic_json(HERE / (mode + '.json'), outcome)
        assert store.project(project['id']) == original_head
        result['native_fixture_head_unchanged'] = True
        result['input_files_unchanged'] = all(sha256_file(Path(p)) == h for p, h in input_files.items())
        result['status'] = 'REPRODUCED' if any(c['status'] == 'MISSING_REQUIRED_OBLIGATION_ACCEPTED' for c in result['cases'].values()) else 'NOT_REPRODUCED'
    except BaseException:
        result.update(status='HARNESS_FAILED', error=traceback.format_exc())
        raise
    finally:
        result['seconds'] = time.perf_counter() - start
        result['reproducer_sha256'] = sha256_file(Path(__file__))
        atomic_json(HERE / 'result.json', result)
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
