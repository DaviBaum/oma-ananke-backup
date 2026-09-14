"""Packaging receipts are local provenance; these fixtures make no CAD claim."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import zlib

import pytest


@pytest.fixture
def helper():
    scripts = Path(__file__).resolve().parents[1] / 'scripts'
    sys.path.insert(0, str(scripts))
    try:
        spec = importlib.util.spec_from_file_location('package_evidence_test_subject', scripts / 'native_package_evidence.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.path.remove(str(scripts))


def _json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf8')


def _put(store, value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf8')
    root = hashlib.sha256(raw).hexdigest()
    (store / 'blobs').mkdir(parents=True, exist_ok=True)
    (store / 'blobs' / (root + '.json.z')).write_bytes(zlib.compress(raw))
    return root


@pytest.fixture
def receipt_case(tmp_path, helper):
    package, store = tmp_path / 'package', tmp_path / 'isolated'
    store.mkdir()
    source = tmp_path / 'source.ifc'
    source.write_text('Synthetic packaging fixture; not an IFC model')
    export_sha = helper.sha(source)
    geometry = _put(store, {'export_sha256': export_sha, 'export_path': str(source)})
    state = {'routes': [{'id': r, 'geometry_artifact': geometry} for r in ('a', 'b')],
             'sources': [{'sha256': export_sha, 'immutable_path': str(source)}]}
    state_root = _put(store, state)
    cad_roots = {}
    for route in ('a', 'b'):
        cad_roots[route] = _put(store, {'route_guids': [route], 'route_count': 1, 'obstacle_count': 1,
            'pairs_accounted': 1, 'coordination_status': 'PASS', 'self_interference_status': 'PASS',
            'failed_pairs': 0, 'unknown_pairs': 0, 'blocked_pairs': 0, 'export_sha256': export_sha,
            'sources': state['sources']})
    rows = [{'id': r + ':physical-interference-and-clearance', 'status': 'PASS', 'witness': {'artifact': cad_roots[r]}} for r in ('a', 'b')]
    rows += [{'id': 'joint-new-fitting-budget', 'status': 'PASS', 'witness': {'count_complete': True,
        'candidate_root': state_root, 'checker_version': 'current', 'per_new_route': {'a': 0, 'b': 0},
        'count': 0, 'declared_budget': 0}}, {'id': 'cross-route-interference', 'status': 'PASS',
        'witness': {'complete_component_coverage': True, 'pairs_accounted': 1}}]
    report = {'status': 'PASS', 'candidate_root': state_root, 'checker_version': 'current', 'objective': {'length': 2}, 'results': rows,
              'mission_hash': 'mission', 'rule_hash': 'rules'}
    report_root = _put(store, report)
    prior = copy.deepcopy(report)
    prior['checker_version'] = 'prior'
    prior_root = _put(store, prior)
    target = {'candidate_id': 'candidate', 'candidate_root': state_root, 'prior_report_root': prior_root,
        'prior_checker_version': 'prior', 'physical_kind': 'physical_route_set', 'original_store': str(tmp_path / 'original'),
        'expected_export_sha256': export_sha}
    second = dict(target, candidate_id='second', physical_kind='physical_network')
    plan = {'schema': 'oma.portable-real-model-inputs/1', 'source_checkpoint': 'source',
            'roles': {'joint_fitting_budget': target, 'pressure_network': second}}
    plan_path = package / 'provenance/real-model-validation-inputs.json'
    _json(plan_path, plan)
    portable = {'package': str(package), 'identity': {'checker_version': 'current'}, 'source_checkpoint': 'source',
        'real_model_validation_inputs_sha256': helper.sha(plan_path), 'validated_payload_manifest_sha256': 'payload'}
    portable_result = tmp_path / 'portable.json'
    _json(portable_result, portable)
    receipt = {**{k: target[k] for k in ('candidate_id', 'candidate_root', 'prior_report_root', 'prior_checker_version', 'physical_kind', 'original_store')},
        'validation_role': 'joint_fitting_budget', 'real_model_validation_inputs_sha256': helper.sha(plan_path),
        'package': str(package), 'portable_validation_result_sha256': helper.sha(portable_result),
        'validated_payload_manifest_sha256': 'payload', 'status': 'REAL_EXPORTED_OFFICE_RECHECK_PASS',
        'checker_version': 'current', 'source_checkpoint': 'source', 'original_bytes_and_head_unchanged': True,
        'original_candidate_and_run_unchanged': True, 'same_objective_and_obligation_dispositions': True,
        'active_store_write_mode': 'READ_ONLY', 'isolated_store': str(store), 'report_root': report_root, 'report': report,
        'physical_record_ids': ['a', 'b'], 'source_and_exported_files': {str(source): export_sha},
        'execution': {'execution_id': 'execution', 'status': 'COMPLETED', 'report_published': True,
            'report_root': report_root, 'candidate_id': 'candidate', 'supervision': {'status': 'COMPLETED',
                'checker_version': 'current', 'command': [str(package / 'runtime/python.exe')]}}}
    receipt['execution'].update(directory='private', observed_receipt={'report_root': report_root},
        publication_authority='PARENT', report_status='PASS', request_root='request')
    execution_evidence = _put(store, {k: v for k, v in receipt['execution'].items() if k != 'report_published'})
    receipt['execution']['evidence_root'] = execution_evidence
    binding = {k: report[k] for k in ('mission_hash', 'rule_hash')}
    binding['source_manifest_hash'] = helper.canonical_digest(state['sources'])
    binding.update(candidate_id='candidate', candidate_root=state_root, checker_version='current', prior_report_root=prior_root)
    original = Path(target['original_store'])
    original.mkdir()
    (store / 'copied.ifc').write_bytes(source.read_bytes())
    with sqlite3.connect(original / 'oma.sqlite3') as db:
        db.executescript('CREATE TABLE asset_aliases(original_path,relative_path); CREATE TABLE metadata(key,value);')
    with sqlite3.connect(store / 'oma.sqlite3') as db:
        db.executescript('CREATE TABLE candidates(id,status,state_root,report_root); CREATE TABLE check_executions(execution_id,status,report_root,evidence_root,binding); CREATE TABLE candidate_check_executions(candidate_id,execution_id); CREATE TABLE asset_aliases(original_path,relative_path); CREATE TABLE metadata(key,value);')
        db.execute('INSERT INTO asset_aliases VALUES(?,?)', (str(source), 'copied.ifc'))
        db.execute('INSERT INTO candidates VALUES(?,?,?,?)', ('candidate', 'CHECKED', state_root, report_root))
        db.execute('INSERT INTO check_executions VALUES(?,?,?,?,?)', ('execution', 'COMPLETED', report_root, execution_evidence, json.dumps(binding)))
        db.execute('INSERT INTO candidate_check_executions VALUES(?,?)', ('candidate', 'execution'))
    return package, portable, portable_result, receipt


def test_intact_bound_receipt_reads_current_completed_store(helper, receipt_case):
    scope = helper.verify_real_model_receipt(*receipt_case[:3], 'joint_fitting_budget', receipt_case[3])
    assert scope['source_pairs'] == 2 and scope['cross_route_pairs'] == 1 and scope['fittings'] == 0


@pytest.mark.parametrize('field,value', [('validation_role', 'pressure_network'), ('candidate_id', 'second'),
    ('candidate_root', '0' * 64), ('prior_report_root', '1' * 64), ('prior_checker_version', 'current'),
    ('physical_kind', 'physical_network'), ('portable_validation_result_sha256', 'wrong'),
    ('validated_payload_manifest_sha256', 'wrong'), ('real_model_validation_inputs_sha256', 'wrong'),
    ('original_bytes_and_head_unchanged', False), ('physical_record_ids', ['a', 'a']), ('source_and_exported_files', {})])
def test_receipt_cannot_substitute_role_identity_or_evidence(helper, receipt_case, field, value):
    receipt_case[3][field] = value
    with pytest.raises(AssertionError):
        helper.verify_real_model_receipt(*receipt_case[:3], 'joint_fitting_budget', receipt_case[3])


@pytest.mark.parametrize('attack', ['new_token', 'timeout', 'report_blob', 'source_bytes', 'changed_plan', 'forged_interpreter'])
def test_late_mutations_cannot_seal(helper, receipt_case, attack):
    package, portable, result, receipt = receipt_case
    if attack in ('new_token', 'timeout'):
        with sqlite3.connect(Path(receipt['isolated_store']) / 'oma.sqlite3') as db:
            if attack == 'new_token':
                db.execute("UPDATE candidate_check_executions SET execution_id='superseded'")
            else:
                db.execute("UPDATE check_executions SET status='UNKNOWN_TIMEOUT'")
    elif attack == 'report_blob':
        path = Path(receipt['isolated_store']) / 'blobs' / (receipt['report_root'] + '.json.z')
        path.write_bytes(zlib.compress(b'{}'))
    elif attack == 'source_bytes':
        Path(next(iter(receipt['source_and_exported_files']))).write_text('changed')
    elif attack == 'forged_interpreter':
        receipt['execution']['supervision']['command'].append('changed')
    else:
        (package / 'provenance/real-model-validation-inputs.json').write_text('{}')
    with pytest.raises(AssertionError):
        helper.verify_real_model_receipt(package, portable, result, 'joint_fitting_budget', receipt)


def test_snapshot_allows_only_named_derived_outputs_and_detects_added_code(helper, tmp_path):
    (tmp_path / 'tests').mkdir()
    source = tmp_path / 'tests/test_a.py'
    source.write_text('pass')
    expected = {'tests\\test_a.py': helper.sha(source)}
    helper.verify_test_snapshot(tmp_path, expected)
    output = tmp_path / 'evidence/release/joint-fitting-budget-audit' / ('a' * 32) / 'result.json'
    _json(output, {'fixture': 'generated evidence'})
    with pytest.raises(AssertionError):
        helper.verify_test_snapshot(tmp_path, expected)
    assert len(helper.verify_test_snapshot(tmp_path, expected, allow_generated_evidence=True)['generated_evidence']) == 1
    (output.parent / 'conftest.py').write_text('pass')
    with pytest.raises(AssertionError):
        helper.verify_test_snapshot(tmp_path, expected, allow_generated_evidence=True)


@pytest.mark.parametrize('mutant', ['duplicate', 'different', 'skipped'])
def test_native_xml_requires_exact_identity_and_no_skips(helper, tmp_path, mutant):
    path = tmp_path / 'tests.xml'
    first = '<testcase classname="tests.test_a" name="test_one" />'
    second = '<testcase classname="tests.test_a" name="test_two" />'
    nodes = ['tests/test_a.py::test_one', 'tests/test_a.py::test_two']
    path.write_text('<testsuite>' + first + second + '</testsuite>')
    assert helper.verify_suite_xml(path, nodes, direct_interpreter=False)['passed'] == 2
    if mutant == 'duplicate':
        second = first
    elif mutant == 'different':
        second = second.replace('test_two', 'test_other')
    else:
        second = second.replace('/>', '><skipped /></testcase>')
    path.write_text('<testsuite>' + first + second + '</testsuite>')
    with pytest.raises(AssertionError):
        helper.verify_suite_xml(path, nodes, direct_interpreter=False)
