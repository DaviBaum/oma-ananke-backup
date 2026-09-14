"""Bound candidate command provenance and explicit surviving-process recovery."""
from datetime import datetime
import json
from pathlib import Path

from native_prepare import sha


RECOVERY_KIND = 'SURVIVING_EXACT_PYTEST_PROCESS_COMPLETION_NO_RERUN'


def validate_exit_observation(command, observation, command_sha256):
    """A terminal observation is evidence of this process, never a guessed exit."""
    assert command['status'] == 'RUNNING'
    assert observation['status'] == 'EXISTING_PROCESS_EXIT_OBSERVED'
    assert type(observation['exit_code']) is int and observation['exit_code'] == 0
    assert observation['tests_restarted'] is False
    assert observation['pid'] == command['pid']
    assert observation['retained_process_handle'] is True
    assert observation['handle_pid'] == command['pid']
    assert abs(observation['handle_creation_time'] - observation['creation_time']) < .00001
    assert Path(observation['handle_executable']).resolve() == Path(command['command'][0]).resolve()
    assert observation['command'] == command['command']
    assert Path(observation['cwd']).resolve() == Path(command['cwd']).resolve()
    assert observation['original_command_record_sha256'] == command_sha256
    assert observation['original_started_utc'] == command['started_utc']
    assert observation['original_budget_seconds'] == command['budget_seconds']
    start = datetime.fromisoformat(command['started_utc']).timestamp()
    monitor_start = datetime.fromisoformat(observation['monitor_started_utc']).timestamp()
    end = datetime.fromisoformat(observation['completed_utc']).timestamp()
    assert abs(observation['creation_time'] - start) < 5
    assert start <= monitor_start <= end <= start + command['budget_seconds']
    assert 0 < observation['peak_observed_rss_bytes'] <= 48 * 1024**3
    return {'original_start_to_monitor_seconds': monitor_start - start,
            'original_start_to_exit_seconds': end - start,
            'unobserved_interval': 'Parent interruption until replacement monitor began; no process-tree supervision claimed during that interval'}


def verify_recovered_command(recovery, command_path, validation_directory, full_suite):
    assert recovery['kind'] == RECOVERY_KIND and recovery['tests_rerun'] is False
    directory = Path(recovery['directory']).resolve()
    assert directory.is_relative_to(Path(validation_directory).resolve() / 'attempts')
    assert Path(command_path).resolve() == Path(recovery['original_command_record']).resolve()
    assert sha(command_path) == recovery['original_command_record_sha256']
    raw = directory / 'command-running.json'
    assert sha(raw) == recovery['original_command_record_sha256']
    raw_wrapper = directory / 'bundled-full-suite-running.json'
    assert sha(raw_wrapper) == recovery['raw_wrapper_receipt_sha256']
    previous = json.loads(raw_wrapper.read_text())
    assert previous['status'] == 'RUNNING'
    assert full_suite['status'] == 'BUNDLED_EXACT_FROZEN_FULL_SUITE_PASS_WITH_DECLARED_DIRECT_INTERPRETER_NOT_APPLICABLE'
    for key, value in previous.items():
        if key != 'status':
            assert full_suite[key] == value
    drivers = Path(previous['directory']) / 'driver-sources'
    assert previous['driver_source_files']
    for name, expected in previous['driver_source_files'].items():
        assert Path(name).name == name and sha(drivers / name) == expected
    observation_path = directory / 'monitor-result.json'
    observation = json.loads(observation_path.read_text())
    assert sha(observation_path) == recovery['monitor_result_sha256']
    assert sha(directory / 'monitor.py') == observation['monitor_source_sha256']
    scope = validate_exit_observation(json.loads(raw.read_text()), observation, sha(raw))
    assert recovery['observation_scope'] == scope
    return scope


def candidate_command_closure(package, portable, checkpoint, full_suite, real_receipts,
                              *, workspace, commands_root, validation_directory):
    """Collect only pinned native history and this candidate's required commands.

    Unrelated command directories are neither read nor treated as authority.
    Raw interrupted history remains raw; one exact surviving suite requires its
    separately bound completion observation plus the caller's XML/input checks.
    """
    package, workspace, commands_root = map(lambda p: Path(p).resolve(), (package, workspace, commands_root))
    handoff_path = package / 'provenance/native-build/handoff.json'
    assert sha(handoff_path) == portable['native_handoff_sha256']
    handoff = json.loads(handoff_path.read_text())
    assert handoff['status'] == 'ISOLATED_NATIVE_CANDIDATE_BUILT_AND_VALIDATED_NOT_PROMOTED'
    selected = {}

    def add(value, role, *, expected_hash=None, stage=None, cwd=None, historical=False, argv=None):
        path = Path(value)
        path = (path if path.is_absolute() else workspace / path).resolve()
        assert path.name == 'record.json' and path.parent.parent == commands_root
        if expected_hash:
            assert sha(path) == expected_hash
        record = json.loads(path.read_text())
        if stage:
            assert record['stage'] == stage
        if cwd:
            assert Path(record['cwd']).resolve() == Path(cwd).resolve()
        if argv is not None:
            assert record['command'] in [[str(value) for value in variant] for variant in argv]
        if historical:
            assert record['status'] in ('PASS', 'FAIL', 'FAILED_TO_START', 'STOPPED_BY_RESOURCE_OR_TIME_LIMIT')
        elif role == 'bundled.full' and record['status'] == 'RUNNING':
            verify_recovered_command(full_suite['recovery'], path, validation_directory, full_suite)
        else:
            assert record['status'] == 'PASS' and record['exit_code'] == 0
        log = path.parent / 'output.log'
        if historical and record['status'] == 'FAILED_TO_START':
            assert isinstance(record.get('error'), str) and record['error']
            if 'log_sha256' in record:
                assert sha(log) == record['log_sha256']
        elif record['status'] != 'RUNNING':
            assert sha(log) == record['log_sha256']
        else:
            assert sha(log) == full_suite['recovery']['completed_output_log_sha256']
        files = {}
        for member in path.parent.rglob('*'):
            assert not member.is_symlink()
            if member.is_file():
                files[member.relative_to(path.parent).as_posix()] = sha(member)
        row = selected.setdefault(path.parent.name, {'source': str(path.parent), 'roles': [],
                                  'record_sha256': sha(path), 'files': files, 'raw_status': record['status']})
        assert row['record_sha256'] == sha(path) and row['files'] == files
        row['roles'].append(role)

    assert handoff['commands']
    for index, row in enumerate(handoff['commands']):
        add(row['path'], f'native-history.{index}', expected_hash=row['sha256'], historical=True)
    python = package / 'runtime/python.exe'
    outer_python = workspace / '.venv/Scripts/python.exe'
    native_root = workspace / '.release/native-build'
    native_python = native_root / 'test-venv/Scripts/python.exe'
    pip = [outer_python, '-m', 'pip', 'install', '--no-index', '--no-deps', '--no-compile', '--ignore-installed']
    add(portable['installation_record'], 'package.install', stage='candidate-bundle-offline-install', cwd=package,
        argv=[[*pip, '--find-links', package / 'wheelhouse', '--target', package / 'runtime/Lib/site-packages', '-r', package / 'requirements-runtime.lock']])
    add(portable['workflow_record'], 'package.workflow', stage='candidate-bundle-offline-workflow', cwd=package,
        argv=[[python, '-s', package / 'scripts/verify_portable_preview.py', '--child', package]])
    native_snapshot = Path(checkpoint['destination']) / 'test-suite'
    add(checkpoint['test_collection_record'], 'checkpoint.collection', stage='checkpoint-test-collection', cwd=native_snapshot,
        argv=[[native_python, '-m', 'pytest', '--collect-only', '-q', '-o', 'pythonpath=', 'tests']])
    native_xml = commands_root.parent / 'checkpoint-validation' / Path(checkpoint['destination']).name / 'tests.xml'
    add(checkpoint['test_suite_record'], 'checkpoint.full', stage='checkpoint-full-suite', cwd=native_snapshot,
        argv=[[native_python, '-m', 'pytest', '-q', '-o', 'pythonpath=', '@' + checkpoint['test_node_manifest'], '--junitxml=' + str(native_xml)]])
    bundled_directory = Path(full_suite['directory'])
    wheels = [native_root / 'test-wheels' / row['name'] for row in full_suite['test_tool_wheels']]
    assert wheels and all(path.parent == native_root / 'test-wheels' for path in wheels)
    add(full_suite['installation_record'], 'bundled.tools', stage='bundled-external-test-tools', cwd=bundled_directory,
        argv=[[*pip, '--target', full_suite['external_test_tools'], *wheels]])
    add(full_suite['collection_record'], 'bundled.collection', stage='bundled-full-suite-collection', cwd=bundled_directory / 'test-suite',
        argv=[[python, '-B', '-s', '-m', 'pytest', '--collect-only', '-q', '-o', 'pythonpath=', 'tests']])
    add(full_suite['suite_record'], 'bundled.full', stage='bundled-exact-full-suite', cwd=bundled_directory / 'test-suite',
        argv=[[python, '-B', '-s', '-m', 'pytest', '-q', '-o', 'pythonpath=', '@' + str(bundled_directory / 'selected-tests.args'),
               '--junitxml=' + str(Path(validation_directory).resolve() / 'bundled-tests.xml')]])
    assert set(real_receipts) == {'joint_fitting_budget', 'pressure_network'}
    for role, receipt in real_receipts.items():
        targets = json.loads((package / 'provenance/real-model-validation-inputs.json').read_text())['roles']
        argv = [python, workspace / 'scripts/native_real_model_validation.py', '--child-directory', receipt['isolated_store'],
                '--candidate-id', receipt['candidate_id'], '--source-checkpoint', portable['source_checkpoint'],
                '--expected-export-sha256', targets[role]['expected_export_sha256'], '--prior-checker-version', receipt['prior_checker_version']]
        variants = [[*argv, '--original-store', receipt['original_store']]]
        if Path(receipt['original_store']).resolve() == workspace / '.oma':
            variants.append(argv)
        add(receipt['command_record'], 'real.' + role, stage='real-office-export-recheck', cwd=workspace, argv=variants)
    return {'schema': 'oma.portable-command-closure/1', 'commands': selected,
            'scope': 'Pinned native build history and the exact candidate validation dependencies only; unrelated ongoing jobs supply no validation authority'}
