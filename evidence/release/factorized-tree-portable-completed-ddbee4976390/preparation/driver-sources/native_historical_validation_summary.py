"""Retain completed mechanics evidence for a known-defective immutable payload."""
import argparse
import json
from pathlib import Path
import shutil

from native_prepare import sha, json_write
from native_package_evidence import verify_payload, verify_checkpoint_inputs, verify_suite_xml, verify_real_model_receipt, REAL_MODEL_ROLES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    result_path = args.result.resolve()
    directory = result_path.parent
    portable = json.loads(result_path.read_text())
    package = Path(portable['package']).resolve()
    blocker = json.loads((directory / 'PROMOTION-BLOCKED.json').read_text())
    assert blocker['source_checkpoint'] == portable['source_checkpoint']
    assert blocker['checker_version'] == portable['identity']['checker_version']
    assert portable['status'] == 'ISOLATED_NATIVE_PORTABLE_OFFLINE_WORKFLOW_PASS'
    assert not (package / 'artifact-files.json').exists(), 'This summary does not reseal an existing package'
    payload = verify_payload(package, portable)
    checkpoint, declaration = verify_checkpoint_inputs(package, portable)
    full = json.loads((directory / 'bundled-full-suite.json').read_text())
    assert full['status'] == 'BUNDLED_EXACT_FROZEN_FULL_SUITE_PASS_WITH_DECLARED_DIRECT_INTERPRETER_NOT_APPLICABLE'
    assert full['checker_version'] == portable['identity']['checker_version']
    assert Path(full['package']).resolve() == package and full['portable_validation_result_sha256'] == sha(result_path)
    assert full['validated_payload_manifest_sha256'] == portable['validated_payload_manifest_sha256']
    assert full['test_source_manifest'] == declaration
    nodes = package / 'provenance/checkpoint-validation/selected-tests.args'
    assert sha(nodes) == checkpoint['test_node_manifest_sha256'] == full['test_node_manifest_sha256']
    assert sha(directory / 'bundled-tests.xml') == full['test_xml_sha256']
    accounting = verify_suite_xml(directory / 'bundled-tests.xml', nodes.read_text().splitlines())
    assert all(full[k] == value for k, value in accounting.items())
    guard = json.loads((directory / 'offline-guard-probe.json').read_text())
    assert guard['package_validation_sha256'] == sha(result_path)
    assert len(guard['records']) == 2 and {r['mode'] for r in guard['records']} == {'BUNDLED', 'FROZEN_CHECKER'}
    assert all(r['status'] == 'PYTHON_SOCKET_CONNECT_DENIED' and r['checker_version'] == full['checker_version'] for r in guard['records'])
    scopes = {role: verify_real_model_receipt(package, portable, result_path, role,
        json.loads((directory / filename).read_text())) for role, (filename, _) in REAL_MODEL_ROLES.items()}
    index = directory / 'historical-payload-index.json'
    assert not index.exists()
    shutil.copyfile(package / 'validated-payload.json', index)
    assert sha(index) == portable['validated_payload_manifest_sha256']
    summary = {'status': 'HISTORICAL_MECHANICS_VALIDATION_COMPLETE_PROMOTION_BLOCKED',
        'package': str(package), 'source_checkpoint': portable['source_checkpoint'], 'checker_version': full['checker_version'],
        'package_sealed': False, 'promotion_blocked': True, 'source_or_payload_replaced': False, 'live_runtime_modified': False,
        'known_defect': blocker['known_defect'], 'portable_validation_result_sha256': sha(result_path),
        'payload_index_sha256': sha(index), 'payload_file_count': len(payload['files']),
        'logical_payload_bytes': sum(row['bytes'] for row in payload['files'].values()),
        'source_python_files': len(portable['source_python_files']), 'test_input_files': len(declaration['files']),
        'custom_native_passed': checkpoint['passed'], 'bundled_accounting': accounting,
        'real_model_scopes': scopes, 'evidence_files': {name: sha(directory / name) for name in
            ('bundled-full-suite.json', 'bundled-tests.xml', 'offline-guard-probe.json', 'workflow.json',
             'real-office-validation.json', 'real-office-pressure-validation.json', 'PROMOTION-BLOCKED.json', 'ui-byte-equivalence.json')},
        'scope': 'Complete retained mechanics checks of this historical payload. The known fixed-flow defect blocks corrected-release promotion and is not cleared by these successes.',
        'summary_script_sha256': sha(Path(__file__))}
    json_write(directory / 'historical-validation-summary.json', summary)
    print(json.dumps({k: summary[k] for k in ('status', 'payload_file_count', 'custom_native_passed', 'bundled_accounting')}), flush=True)


if __name__ == '__main__':
    main()
