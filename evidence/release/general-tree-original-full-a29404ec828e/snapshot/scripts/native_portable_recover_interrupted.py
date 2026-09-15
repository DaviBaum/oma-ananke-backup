"""Recover a completed surviving pytest instance; never launch or rerun tests."""
import argparse
import json
from pathlib import Path

from native_prepare import sha, json_write
from native_package_evidence import verify_payload, verify_checkpoint_inputs, verify_test_snapshot, verify_suite_xml
from native_command_evidence import RECOVERY_KIND, validate_exit_observation, verify_recovered_command


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--result', type=Path, required=True)
    parser.add_argument('--suite-record', type=Path, required=True)
    parser.add_argument('--collection-record', type=Path, required=True)
    parser.add_argument('--attempt-directory', type=Path, required=True)
    args = parser.parse_args()
    result_path, attempt = args.result.resolve(), args.attempt_directory.resolve()
    output = result_path.parent / 'bundled-full-suite.json'
    assert attempt.is_relative_to(result_path.parent / 'attempts')
    previous = json.loads(output.read_text())
    assert previous['status'] == 'RUNNING'
    assert sha(output) == sha(attempt / 'bundled-full-suite-running.json')
    portable = json.loads(result_path.read_text())
    package = Path(portable['package']).resolve()
    assert portable['status'] == 'ISOLATED_NATIVE_PORTABLE_OFFLINE_WORKFLOW_PASS'
    assert Path(previous['package']).resolve() == package
    assert previous['portable_validation_result_sha256'] == sha(result_path)
    assert previous['validated_payload_manifest_sha256'] == portable['validated_payload_manifest_sha256']
    assert previous['source_checkpoint'] == portable['source_checkpoint']
    assert previous['checker_version'] == previous['identity']['checker_version'] == portable['identity']['checker_version']
    assert Path(previous['identity']['python']).resolve() == package / 'runtime/python.exe'
    checkpoint, declaration = verify_checkpoint_inputs(package, portable)
    assert previous['test_source_manifest'] == declaration
    assert previous['test_node_manifest_sha256'] == checkpoint['test_node_manifest_sha256']
    snapshot = Path(previous['directory']).resolve() / 'test-suite'
    copied_nodes = snapshot.parent / 'selected-tests.args'
    assert sha(copied_nodes) == previous['test_node_manifest_sha256']
    nodes = copied_nodes.read_text().splitlines()
    assert len(nodes) == len(set(nodes)) == previous['test_node_count'] == checkpoint['test_node_count']
    for name, expected in previous['driver_source_files'].items():
        assert Path(name).name == name
        assert sha(snapshot.parent / 'driver-sources' / name) == expected
    command_path = args.suite_record.resolve()
    assert sha(command_path) == sha(attempt / 'command-running.json')
    command = json.loads(command_path.read_text())
    observation = json.loads((attempt / 'monitor-result.json').read_text())
    assert sha(attempt / 'monitor.py') == observation['monitor_source_sha256']
    observation_scope = validate_exit_observation(command, observation, sha(command_path))
    expected_command = [str(package / 'runtime/python.exe'), '-B', '-s', '-m', 'pytest', '-q', '-o', 'pythonpath=',
                        '@' + str(copied_nodes), '--junitxml=' + str(result_path.parent / 'bundled-tests.xml')]
    assert command['command'] == expected_command
    assert Path(command['cwd']).resolve() == snapshot
    collection = json.loads(args.collection_record.read_text())
    assert collection['status'] == 'PASS' and collection['exit_code'] == 0
    assert collection['stage'] == 'bundled-full-suite-collection'
    assert Path(collection['cwd']).resolve() == snapshot
    assert collection['command'] == [str(package / 'runtime/python.exe'), '-B', '-s', '-m', 'pytest', '--collect-only', '-q', '-o', 'pythonpath=', 'tests']
    assert sha(args.collection_record.parent / 'output.log') == collection['log_sha256']
    collected = [line for line in (args.collection_record.parent / 'output.log').read_text().splitlines()
                 if line.startswith('tests/') and '::' in line]
    assert collected == nodes
    xml = result_path.parent / 'bundled-tests.xml'
    accounting = verify_suite_xml(xml, nodes)
    inventory = verify_test_snapshot(snapshot, declaration['files'], allow_generated_evidence=True)
    verify_payload(package, portable)
    recovery = {'kind': RECOVERY_KIND, 'tests_rerun': False, 'directory': str(attempt),
                'raw_wrapper_receipt_sha256': sha(attempt / 'bundled-full-suite-running.json'),
                'original_command_record': str(command_path), 'original_command_record_sha256': sha(command_path),
                'monitor_result_sha256': sha(attempt / 'monitor-result.json'),
                'completed_output_log_sha256': sha(command_path.parent / 'output.log'),
                'observation_scope': observation_scope, 'recovery_script_sha256': sha(Path(__file__)),
                'helper_sha256': sha(Path(__file__).with_name('native_command_evidence.py'))}
    recovered = {**previous, **accounting,
                 'status': 'BUNDLED_EXACT_FROZEN_FULL_SUITE_PASS_WITH_DECLARED_DIRECT_INTERPRETER_NOT_APPLICABLE',
                 'test_xml_sha256': sha(xml), 'collection_record': str(args.collection_record.resolve()),
                 'suite_record': str(command_path), 'final_test_snapshot_inventory': inventory,
                 'driver_sha256': previous['driver_source_files']['native_portable_full_suite.py'],
                 'seconds': observation_scope['original_start_to_exit_seconds'],
                 'seconds_basis': 'Observed exit minus original pytest start; interrupted wrapper duration is unavailable',
                 'recovery': recovery}
    verify_recovered_command(recovery, command_path, result_path.parent, recovered)
    # The raw wrapper/command records remain separately unchanged and hash-bound.
    json_write(output, recovered)
    print(json.dumps({'status': recovered['status'], **accounting, 'tests_rerun': False}), flush=True)


if __name__ == '__main__':
    main()
