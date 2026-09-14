"""Read-only follow-up: exact omission, mandatory inventory, frozen input hashes."""
from pathlib import Path
import json
import sqlite3
import sys

from oma.build_identity import checker_version
from oma.ifc.audit import atomic_json, sha256_file
from oma.routing.selection import _complete_check_obligations, try_selection_evidence
from oma.store import Store, _Connection, digest

HERE = Path(__file__).resolve().parent


class ReadOnly(Store):
    def __init__(self, directory):
        self.directory = Path(directory)
        self.database = self.directory / 'oma.sqlite3'
        self.blobs = self.directory / 'blobs'

    def connect(self):
        db = sqlite3.connect(self.database.as_uri() + '?mode=ro', uri=True, factory=_Connection)
        db.row_factory = sqlite3.Row
        return db

    def put(self, value):
        raise RuntimeError('Read-only audit')


def main():
    initial = json.loads((HERE / 'result.json').read_text())
    assert checker_version() == initial['checker_version']
    intact = json.loads((HERE / 'intact-native-report.json').read_text())
    narrow = json.loads((HERE / 'narrowed-report.json').read_text())
    expected = {**intact, 'results': [r for r in intact['results'] if r['id'] != 'network-pressure-operating-point']}
    assert expected == narrow
    original = ReadOnly(HERE / 'native-fixture/store')
    candidate = original.candidate(initial['intact_candidate_id'])
    run = original.run(candidate['run_id'])
    state = original.get(candidate['state_root'])
    weights = state['mission']['objective_weights']
    original_selection, original_error = try_selection_evidence(original, run, candidate['id'], 'physical_network', weights)
    assert original_selection and original_error is None
    mandatory = _complete_check_obligations(original, state, original.get(run['base_root']), 'physical_network')
    assert set(mandatory) - {r['id'] for r in narrow['results']} == {'network-pressure-operating-point'}
    with original.connect() as db:
        execution = dict(db.execute('SELECT e.* FROM candidate_check_executions h JOIN check_executions e ON e.execution_id=h.execution_id WHERE h.candidate_id=?', (candidate['id'],)).fetchone())
    assert execution['status'] == 'COMPLETED' and execution['report_root'] == candidate['report_root']
    checks = {}
    for mode, outcome in initial['cases'].items():
        store = ReadOnly(HERE / mode)
        copied = store.candidate(outcome['candidate_id'])
        evidence, error = try_selection_evidence(store, store.run(copied['run_id']), copied['id'], 'physical_network', weights)
        assert evidence is None and error['reason'] == 'Physical report omits, duplicates, adds or weakens a mandatory check obligation'
        checks[mode] = {'actual_objective_weights': weights, 'selection': error, 'accepted_revision': store.project(copied['project_id'])['revision']}
    manifest = {str(p.relative_to(HERE)).replace('\\', '/'): sha256_file(p) for directory in ('tests', 'docs') for p in (HERE / directory).rglob('*') if p.is_file() and p.suffix != '.pyc'}
    result = {'status': 'CONFIRMED', 'checker_version': checker_version(), 'initial_result_sha256': sha256_file(HERE / 'result.json'),
        'original_native_managed_execution': execution, 'only_report_change': 'Remove network-pressure-operating-point',
        'original_complete_selection_root': digest(original_selection), 'mandatory_checks': mandatory,
        'cases': checks, 'frozen_fixture_files': manifest,
        'harness_correction': 'Initial ancillary selection call used ad hoc fallback objective weights; this read-only follow-up uses the exact persisted mission weights and confirms rejection specifically for the missing obligation. Original record/accept reproductions are unaffected.'}
    atomic_json(HERE / 'audit.json', result)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
