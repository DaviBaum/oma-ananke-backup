"""Read-only completion audit of an existing native run; never reruns tests."""
import argparse
import json
from pathlib import Path

from native_prepare import sha, json_write
from native_package_evidence import verify_suite_xml, verify_test_snapshot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--result', type=Path, required=True)
    parser.add_argument('--driver-edited-during-run', action='store_true')
    args = parser.parse_args()
    result_path = args.result.resolve()
    result = json.loads(result_path.read_text())
    assert result['status'] == 'CUSTOM_NATIVE_NEW_CHECKPOINT_FULL_SUITE_PASS'
    directory = result_path.parent
    manifest_path = directory / 'test-source-manifest.json'
    assert sha(manifest_path) == result['test_source_manifest_sha256']
    manifest = json.loads(manifest_path.read_text())
    nodes_path = Path(result['test_node_manifest'])
    assert sha(nodes_path) == result['test_node_manifest_sha256']
    nodes = nodes_path.read_text().splitlines()
    assert len(nodes) == result['test_node_count']
    xml = directory / 'tests.xml'
    assert sha(xml) == result['test_xml_sha256']
    accounting = verify_suite_xml(xml, nodes, direct_interpreter=False)
    assert accounting['passed'] == result['passed'] and result['failed'] == result['skipped'] == 0
    copy_inventory = verify_test_snapshot(Path(result['destination']) / 'test-suite', manifest['files'], allow_generated_evidence=True)
    declaration = directory / 'declared-test-snapshot.json'
    assert sha(declaration) == result['test_snapshot_declaration_sha256']
    declared = json.loads(declaration.read_text())
    assert declared['snapshot_files'] == manifest['files']
    origin_inventory = verify_test_snapshot(declared['test_snapshot'], manifest['files'], allow_generated_evidence=True)
    identity_path = directory / 'identity-comparison.json'
    identity = json.loads(identity_path.read_text())
    assert identity['original']['checker_version'] == declared['checker_version'] == 'oma-independent-checker/2:' + result['source_checkpoint']
    candidate = identity['candidate']
    assert candidate['checker_version'] == result['runtime']['OMA_EXECUTABLE_BUILD']
    assert candidate['extension_sha256'] == result['native_extension_sha256']
    assert sha(Path(candidate['extension_path'])) == candidate['extension_sha256']
    source = Path(result['runtime']['PYTHONPATH']) / 'oma'
    assert {p.relative_to(source).as_posix(): sha(p) for p in source.rglob('*.py')} == candidate['source_files'] == identity['original']['source_files']
    command_path = Path(result['test_suite_record'])
    command = json.loads(command_path.read_text())
    assert command['status'] == 'PASS'
    assert Path(command['cwd']).resolve() == (Path(result['destination']) / 'test-suite').resolve()
    assert '@' + str(nodes_path) in command['command'] and '--junitxml=' + str(xml) in command['command']
    audit = {'status': 'EXISTING_NATIVE_RUN_EXACT_INPUT_NODE_XML_IDENTITY_AUDIT_PASS',
        'result_sha256': sha(result_path), 'source_checkpoint': result['source_checkpoint'],
        'checker_version': candidate['checker_version'], 'source_python_files': len(candidate['source_files']),
        'test_input_files': len(manifest['files']), 'test_node_count': len(nodes), 'accounting': accounting,
        'xml_sha256': sha(xml), 'command_record_sha256': sha(command_path), 'identity_comparison_sha256': sha(identity_path),
        'original_snapshot': origin_inventory, 'copied_snapshot': copy_inventory,
        'driver_edited_during_run': args.driver_edited_during_run,
        'driver_identity_scope': ('The old driver recorded its mutable pathname hash at completion; that field is not treated as a launch identity. This separate audit binds the saved completed command, exact frozen application and test inputs, node identities, and XML.' if args.driver_edited_during_run else 'The run declares its startup driver identity separately.'),
        'tests_rerun': False, 'audit_script_sha256': sha(Path(__file__))}
    json_write(directory / 'post-run-exact-audit.json', audit)
    print(json.dumps({k: audit[k] for k in ('status', 'checker_version', 'test_input_files', 'test_node_count', 'tests_rerun')}), flush=True)


if __name__ == '__main__':
    main()
