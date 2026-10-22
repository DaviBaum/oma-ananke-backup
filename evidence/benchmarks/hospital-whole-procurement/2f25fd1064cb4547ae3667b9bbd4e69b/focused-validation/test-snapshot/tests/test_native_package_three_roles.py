"""Optional v2 three-role package declarations preserve v1 provenance semantics."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from native_package_evidence import real_model_inputs, sha
from test_native_command_evidence import campaign, write


def make_three(campaign):
    c = campaign
    path = c['package'] / 'provenance/real-model-validation-inputs.json'
    declaration = json.loads(path.read_text())
    declaration['schema'] = 'oma.portable-real-model-inputs/2'
    role = 'coupled_pressure_network'
    declaration['roles'][role] = dict(declaration['roles']['pressure_network'], candidate_id=role, expected_export_sha256='d' * 64)
    c['portable']['real_model_validation_inputs_sha256'] = write(path, declaration)
    receipt = dict(c['actual']['pressure_network'], candidate_id=role, isolated_store=str(c['tmp_path'] / role))
    command = json.loads(Path(receipt['command_record']).read_text())
    for option, value in (('--candidate-id', role), ('--child-directory', receipt['isolated_store']), ('--expected-export-sha256', 'd' * 64)):
        command['command'][command['command'].index(option) + 1] = value
    command_path = c['commands'] / role / 'record.json'
    command_path.parent.mkdir()
    original_log = Path(receipt['command_record']).parent / 'output.log'
    (command_path.parent / 'output.log').write_bytes(original_log.read_bytes())
    write(command_path, command)
    receipt['command_record'] = str(command_path)
    c['actual'][role] = receipt
    return path, declaration


def test_legacy_two_roles_and_new_three_role_closure_are_distinct(campaign):
    c = campaign
    assert set(real_model_inputs(c['package'], c['portable'])['roles']) == {'joint_fitting_budget', 'pressure_network'}
    assert len(c['closure']()['commands']) == 10
    make_three(c)
    assert len(real_model_inputs(c['package'], c['portable'])['roles']) == 3
    closure = c['closure']()
    assert len(closure['commands']) == 11
    assert any('real.coupled_pressure_network' in row['roles'] for row in closure['commands'].values())


@pytest.mark.parametrize('fault', ['missing_third', 'unknown_role', 'duplicate_candidate', 'wrong_kind', 'wrong_schema', 'downgraded_schema', 'old_hash', 'wrong_source'])
def test_coherently_changed_three_role_declarations_fail_closed(campaign, fault):
    c = campaign
    path, declaration = make_three(c)
    if fault == 'missing_third': declaration['roles'].pop('coupled_pressure_network')
    if fault == 'unknown_role': declaration['roles']['other'] = declaration['roles'].pop('coupled_pressure_network')
    if fault == 'duplicate_candidate': declaration['roles']['coupled_pressure_network']['candidate_id'] = 'pressure_network'
    if fault == 'wrong_kind': declaration['roles']['coupled_pressure_network']['physical_kind'] = 'physical_route_set'
    if fault == 'wrong_schema': declaration['schema'] = 'oma.portable-real-model-inputs/3'
    if fault == 'downgraded_schema': declaration['schema'] = 'oma.portable-real-model-inputs/1'
    if fault == 'old_hash': declaration['roles']['coupled_pressure_network']['expected_export_sha256'] = 'e' * 64
    if fault == 'wrong_source': declaration['source_checkpoint'] = 'another-build'
    digest = write(path, declaration)
    if fault != 'old_hash': c['portable']['real_model_validation_inputs_sha256'] = digest
    with pytest.raises(AssertionError):
        real_model_inputs(c['package'], c['portable'])


@pytest.mark.parametrize('fault', ['missing_receipt', 'wrong_command_candidate', 'wrong_command_bytes', 'substituted_old_receipt'])
def test_declared_coupled_role_needs_its_exact_own_completed_command(campaign, fault):
    c = campaign
    make_three(c)
    role = 'coupled_pressure_network'
    if fault == 'missing_receipt':
        c['actual'].pop(role)
    elif fault == 'substituted_old_receipt':
        c['actual'][role] = deepcopy(c['actual']['pressure_network'])
    else:
        path = Path(c['actual'][role]['command_record'])
        command = json.loads(path.read_text())
        flag, value = ('--candidate-id', 'pressure_network') if fault == 'wrong_command_candidate' else ('--expected-export-sha256', 'e' * 64)
        command['command'][command['command'].index(flag) + 1] = value
        write(path, command)
    with pytest.raises(AssertionError):
        c['closure']()
