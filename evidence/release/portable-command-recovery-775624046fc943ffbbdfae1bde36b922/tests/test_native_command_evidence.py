"""Adversarial command provenance and surviving-process identity boundaries."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from native_command_evidence import candidate_command_closure, validate_exit_observation, RECOVERY_KIND


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def campaign(tmp_path):
    package = tmp_path / 'package'
    commands = tmp_path / 'commands'
    validation = tmp_path / 'validation'
    native = tmp_path / 'native'
    bundled = tmp_path / 'bundled'
    def command(name, stage, cwd, status='PASS'):
        path = commands / name / 'record.json'
        path.parent.mkdir(parents=True)
        (path.parent / 'output.log').write_text('actual retained command log\n')
        value = {'stage': stage, 'cwd': str(cwd), 'status': status, 'exit_code': 0,
                 'command': [str(package / 'runtime/python.exe'), '-m', 'pytest'],
                 'log_sha256': hashlib.sha256((path.parent / 'output.log').read_bytes()).hexdigest()}
        write(path, value)
        return str(path)
    old = command('native-history', 'compile', tmp_path)
    handoff = {'status': 'ISOLATED_NATIVE_CANDIDATE_BUILT_AND_VALIDATED_NOT_PROMOTED',
               'commands': [{'path': old, 'sha256': hashlib.sha256(Path(old).read_bytes()).hexdigest()}]}
    portable = {'native_handoff_sha256': write(package / 'provenance/native-build/handoff.json', handoff),
                'installation_record': command('install', 'candidate-bundle-offline-install', package),
                'workflow_record': command('workflow', 'candidate-bundle-offline-workflow', package)}
    checkpoint = {'destination': str(native),
                  'test_collection_record': command('native-collection', 'checkpoint-test-collection', native / 'test-suite'),
                  'test_suite_record': command('native-suite', 'checkpoint-full-suite', native / 'test-suite')}
    suite = {'directory': str(bundled),
             'installation_record': command('tools', 'bundled-external-test-tools', bundled),
             'collection_record': command('collection', 'bundled-full-suite-collection', bundled / 'test-suite'),
             'suite_record': command('suite', 'bundled-exact-full-suite', bundled / 'test-suite')}
    actual = {role: {'command_record': command(role, 'real-office-export-recheck', tmp_path)}
              for role in ('joint_fitting_budget', 'pressure_network')}
    def closure():
        return candidate_command_closure(package, portable, checkpoint, suite, actual,
                                         workspace=tmp_path, commands_root=commands, validation_directory=validation)
    return locals()


def observation(command):
    command.update(status='RUNNING', pid=123, started_utc='2026-09-14T22:00:00+00:00', budget_seconds=2400)
    start = 1789423200.0
    return {'status': 'EXISTING_PROCESS_EXIT_OBSERVED', 'exit_code': 0, 'tests_restarted': False,
            'pid': 123, 'command': command['command'], 'cwd': command['cwd'],
            'original_started_utc': command['started_utc'], 'original_budget_seconds': 2400,
            'original_command_record_sha256': '', 'creation_time': start + .008,
            'monitor_started_utc': '2026-09-14T22:10:00+00:00', 'completed_utc': '2026-09-14T22:20:00+00:00',
            'peak_observed_rss_bytes': 1024, 'retained_process_handle': True,
            'handle_pid': 123, 'handle_creation_time': start + .008,
            'handle_executable': command['command'][0]}


def test_unrelated_running_or_malformed_jobs_do_not_enter_candidate_closure(campaign):
    c = campaign
    path = c['commands'] / 'unrelated-live' / 'record.json'
    write(path, {'status': 'RUNNING'})
    path.write_text('not even valid JSON')
    result = c['closure']()
    assert len(result['commands']) == 10
    assert 'unrelated-live' not in result['commands']
    assert {r for row in result['commands'].values() for r in row['roles']} >= {'bundled.full', 'real.pressure_network'}


@pytest.mark.parametrize('attack', ['current_running', 'wrong_cwd', 'wrong_stage', 'changed_log', 'history_mutation', 'missing_pressure', 'missing_collection', 'foreign_command'])
def test_missing_or_misbound_required_command_cannot_seal(campaign, attack):
    c = campaign
    path = Path(c['suite']['suite_record'])
    row = json.loads(path.read_text())
    if attack == 'current_running':
        row['status'] = 'RUNNING'
    elif attack == 'wrong_cwd':
        row['cwd'] = str(c['package'])
    elif attack == 'wrong_stage':
        row['stage'] = 'unrelated-success'
    elif attack == 'changed_log':
        (path.parent / 'output.log').write_text('different completed run')
    elif attack == 'history_mutation':
        Path(c['old']).write_text('{}')
    elif attack == 'missing_pressure':
        del c['actual']['pressure_network']
    elif attack == 'missing_collection':
        del c['checkpoint']['test_collection_record']
    elif attack == 'foreign_command':
        foreign = c['tmp_path'] / 'foreign' / 'record.json'
        write(foreign, row)
        c['suite']['suite_record'] = str(foreign)
    write(path, row)
    with pytest.raises((AssertionError, KeyError)):
        c['closure']()


@pytest.mark.parametrize('attack', ['no_handle', 'wrong_pid', 'wrong_creation', 'wrong_image', 'wrong_command', 'nonzero_exit', 'bool_exit', 'deadline', 'wrong_digest', 'unknown_exit'])
def test_xml_cannot_replace_bound_handle_exit_authority(campaign, attack):
    command = json.loads(Path(campaign['suite']['suite_record']).read_text())
    observed = observation(command)
    observed['original_command_record_sha256'] = 'bound'
    if attack == 'no_handle': observed['retained_process_handle'] = False
    elif attack == 'wrong_pid': observed['handle_pid'] = 999
    elif attack == 'wrong_creation': observed['handle_creation_time'] += 1
    elif attack == 'wrong_image': observed['handle_executable'] = str(campaign['tmp_path'] / 'other/python.exe')
    elif attack == 'wrong_command': observed['command'] = ['other']
    elif attack == 'nonzero_exit': observed['exit_code'] = 1
    elif attack == 'bool_exit': observed['exit_code'] = False
    elif attack == 'deadline': observed['completed_utc'] = '2026-09-14T23:00:00+00:00'
    elif attack == 'wrong_digest': observed['original_command_record_sha256'] = 'unrelated'
    elif attack == 'unknown_exit': observed['status'] = 'MONITOR_INCOMPLETE'
    with pytest.raises(AssertionError):
        validate_exit_observation(command, observed, 'bound')


def test_explicit_bound_recovery_keeps_raw_running_record(campaign):
    c = campaign
    path = Path(c['suite']['suite_record'])
    command = json.loads(path.read_text())
    observed = observation(command)
    digest = write(path, command)
    attempt = c['validation'] / 'attempts/retained-handle'
    assert write(attempt / 'command-running.json', command) == digest
    observed['original_command_record_sha256'] = digest
    (attempt / 'monitor.py').write_text('# frozen observer fixture; no process was launched\n')
    observed['monitor_source_sha256'] = hashlib.sha256((attempt / 'monitor.py').read_bytes()).hexdigest()
    monitor_hash = write(attempt / 'monitor-result.json', observed)
    c['suite']['recovery'] = {'kind': RECOVERY_KIND, 'tests_rerun': False, 'directory': str(attempt),
        'original_command_record': str(path), 'original_command_record_sha256': digest,
        'monitor_result_sha256': monitor_hash, 'completed_output_log_sha256': command['log_sha256'],
        'observation_scope': validate_exit_observation(command, observed, digest)}
    result = c['closure']()
    assert result['commands']['suite']['raw_status'] == 'RUNNING'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    # A new coherent command body still cannot use the old exact observation.
    command['pid'] = 124
    write(path, command)
    with pytest.raises(AssertionError):
        c['closure']()
