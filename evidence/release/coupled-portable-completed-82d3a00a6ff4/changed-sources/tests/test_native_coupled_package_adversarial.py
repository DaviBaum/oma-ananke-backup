"""Packaging summary attacks use genuine native coupled-tree evidence.

An explicit read-only Office override allows evidence replay without another native
run. The default analytic fixture keeps the tests portable in frozen suites.
These are trusted-caller summary tests, not ordinary API exploit claims.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys

import pytest

from test_native_real_model_validation_script import ReadOnly, _script


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


@pytest.fixture(scope="module")
def coupled_package_case(tmp_path_factory):
    if os.environ.get("OMA_COUPLED_PACKAGE_STORE"):
        store = ReadOnly(os.environ["OMA_COUPLED_PACKAGE_STORE"])
        candidate = store.candidate(os.environ["OMA_COUPLED_PACKAGE_CANDIDATE"])
        report = store.get(candidate["report_root"])
    else:
        from test_coupled_tree_integration import coupled_tree_scenario, run_native
        store, _, _, candidate, report, _ = run_native(
            tmp_path_factory.mktemp("coupled-package-native"), coupled_tree_scenario())
    assert candidate["status"] == "CHECKED" and report["status"] == "PASS"
    state = store.get(candidate["state_root"])
    assert state["derived_artifacts"]["network_contract"]["scenario"]["coupled_tree"]
    return store, candidate, state, report


def summary(case, tmp_path, *, report=None, state=None, overlay=None):
    original, candidate, original_state, original_report = case

    class Changed:
        def get(self, root):
            return copy.deepcopy(overlay[root] if overlay and root in overlay else original.get(root))

    scripts = str(Path(__file__).resolve().parents[1] / "scripts")
    sys.path.insert(0, scripts)
    try:
        return _script().network_validation_evidence(
            Changed(), copy.deepcopy(original_state if state is None else state),
            copy.deepcopy(original_report if report is None else report), tmp_path, "peer", retain=False,
            baseline_root=original.run(candidate["run_id"])["base_root"])
    finally:
        sys.path.remove(scripts)


def replace_artifact(report, overlay, old_root, replacement):
    """Rebind every direct witness to a correctly hashed altered packet."""
    root = digest(replacement)
    overlay[root] = copy.deepcopy(replacement)
    for row in report["results"]:
        witness = row.get("witness")
        if isinstance(witness, dict):
            for key, value in list(witness.items()):
                if value == old_root:
                    witness[key] = root
    return root


def pressure_change(case, fault):
    store, _, _, original = case
    report = copy.deepcopy(original)
    rows = {r["id"]: r for r in report["results"]}
    old = rows["network-pressure-operating-point"]["witness"]["artifact"]
    calc = copy.deepcopy(store.get(old))
    fault(calc)
    # All exposed copies agree: a checker must validate the actual proof/service,
    # rather than reject only a duplicated summary that was forgotten by the test.
    if "certificate" in calc:
        proof = calc["certificate"]
        proof.pop("certificate_root", None)
        proof["certificate_root"] = digest(proof)
        calc["independent_check"]["certificate_root"] = proof["certificate_root"]
    rows["network-demand-conditioned-service"]["witness"]["calculation"] = copy.deepcopy(calc)
    overlay = {}
    replace_artifact(report, overlay, old, calc)
    return report, overlay


def mutate_service(calc, transform):
    for service in (calc["service"], calc["independent_check"]["service"], calc["certificate"]["service"]):
        transform(service)


def test_genuine_coupled_native_summary_keeps_all_physical_denominators(tmp_path, coupled_package_case):
    answer = summary(coupled_package_case, tmp_path)
    assert answer["complete_native_status"] == "PASS"
    assert answer["physical_components"] == 7 and answer["physical_ports"] == 16
    assert answer["component_pairs"] == 21
    assert answer["source_pairs"] == 7 * answer["original_obstacles"]
    assert answer["operating_point_status"] == answer["service_status"] == "PASS"


SERVICE_FAULTS = [
    "missing_port", "duplicate_port", "wrong_port", "reversed_port", "velocity_fail",
    "missing_delivery", "duplicate_delivery", "delivery_fail", "missing_continuity",
    "duplicate_continuity", "invented_continuity", "nonzero_continuity", "missing_head_path",
    "duplicate_head_path", "invented_head_path", "forged_port_flow", "forged_port_pressure",
]


@pytest.mark.parametrize("fault", SERVICE_FAULTS)
def test_resealed_coupled_service_inventory_is_not_a_valid_packaging_summary(tmp_path, coupled_package_case, fault):
    def mutate(service):
        ports = service["physical_ports"]
        if fault == "missing_port": ports.pop()
        elif fault == "duplicate_port": ports[-1] = copy.deepcopy(ports[0])
        elif fault == "wrong_port": ports[0]["port"] = "unrepresented"
        elif fault == "reversed_port": ports[0]["forward_status"] = "FAIL"
        elif fault == "velocity_fail": ports[0]["maximum_velocity_status"] = "FAIL"
        elif fault == "missing_delivery": service["deliveries"].pop()
        elif fault == "duplicate_delivery": service["deliveries"][-1] = copy.deepcopy(service["deliveries"][0])
        elif fault == "delivery_fail": service["deliveries"][0]["status"] = "FAIL"
        elif fault == "missing_continuity": service["conservation_identities"].pop()
        elif fault == "duplicate_continuity": service["conservation_identities"][-1] = copy.deepcopy(service["conservation_identities"][0])
        elif fault == "invented_continuity": service["conservation_identities"][0]["id"] = "invented"
        elif fault == "nonzero_continuity": service["conservation_identities"][0]["difference"] = {"sink-a": 1}
        elif fault == "missing_head_path": service["head_path_identities"].pop()
        elif fault == "duplicate_head_path": service["head_path_identities"][-1] = copy.deepcopy(service["head_path_identities"][0])
        elif fault == "invented_head_path": service["head_path_identities"][0]["id"] = "invented"
        elif fault == "forged_port_flow": ports[0]["flow_m3_s"] = {"lower": "100", "upper": "100"}
        elif fault == "forged_port_pressure": ports[0]["total_pressure_pa"] = {"lower": "100", "upper": "100"}
        else: raise AssertionError(fault)
    report, overlay = pressure_change(coupled_package_case, lambda calc: mutate_service(calc, mutate))
    with pytest.raises((AssertionError, ValueError, KeyError)):
        summary(coupled_package_case, tmp_path, report=report, overlay=overlay)


@pytest.mark.parametrize("fault", ["missing_global", "global_unknown", "local_unknown", "wrong_global_model",
                                   "wrong_parameter_root", "wrong_local_root", "wrong_input_root", "wrong_native_root",
                                   "wrong_boundary_root", "missing_polynomial_term", "univalence_singleton_omission"])
def test_resealed_coupled_proof_or_native_binding_cannot_certify_package(tmp_path, coupled_package_case, fault):
    def mutate(calc):
        check = calc["independent_check"]
        if fault == "missing_global": check.pop("global_check")
        elif fault == "global_unknown": check["global_check"]["status"] = "UNKNOWN"
        elif fault == "local_unknown": check["local_check"]["status"] = "UNKNOWN"
        elif fault == "wrong_global_model": check["global_check"]["model_root"] = "0" * 64
        elif fault == "wrong_parameter_root": check["global_check"]["parameter_root"] = "0" * 64
        elif fault == "wrong_local_root": check["local_check"]["certificate_root"] = "0" * 64
        elif fault == "wrong_input_root": check["input_root"] = "0" * 64
        elif fault == "wrong_native_root": calc["certificate"]["derivation"]["native_evidence_root"] = "0" * 64
        elif fault == "wrong_boundary_root": calc["certificate"]["derivation"]["boundary_root"] = "0" * 64
        elif fault == "missing_polynomial_term": calc["certificate"]["model"]["terms"].pop()
        elif fault == "univalence_singleton_omission": calc["certificate"]["univalence_certificate"] = {}
        else: raise AssertionError(fault)
    report, overlay = pressure_change(coupled_package_case, mutate)
    with pytest.raises((AssertionError, ValueError, KeyError)):
        summary(coupled_package_case, tmp_path, report=report, overlay=overlay)


@pytest.mark.parametrize("fault", ["missing_operating", "missing_service", "service_na", "duplicate_row", "wrong_metric_root"])
def test_coupled_report_obligations_must_be_complete(tmp_path, coupled_package_case, fault):
    report = copy.deepcopy(coupled_package_case[3]); rows = {r["id"]: r for r in report["results"]}
    if fault == "missing_operating": report["results"].remove(rows["network-pressure-operating-point"])
    elif fault == "missing_service": report["results"].remove(rows["network-demand-conditioned-service"])
    elif fault == "service_na": rows["network-demand-conditioned-service"]["status"] = "NOT_APPLICABLE"
    elif fault == "duplicate_row": report["results"].append(copy.deepcopy(rows["network-pressure-operating-point"]))
    elif fault == "wrong_metric_root": rows["network-pressure-operating-point"]["witness"]["native_metrics_artifact"] = "0" * 64
    with pytest.raises((AssertionError, ValueError, KeyError, FileNotFoundError)):
        summary(coupled_package_case, tmp_path, report=report)


@pytest.mark.parametrize("fault", ["duplicate_pair", "missing_part", "duplicate_port", "missing_native_port", "missing_source_pair"])
def test_current_coupled_native_denominator_cannot_be_narrowed(tmp_path, coupled_package_case, fault):
    store, _, _, old = coupled_package_case; report = copy.deepcopy(old); rows = {r["id"]:r for r in report["results"]}
    key = "network-all-source-clearance" if fault in ("duplicate_pair", "missing_source_pair") else "network-native-semantics"
    root = rows[key]["witness"]["artifact"]; artifact = copy.deepcopy(store.get(root))
    if fault == "duplicate_pair": artifact["self_pair_results"][-1] = copy.deepcopy(artifact["self_pair_results"][0])
    elif fault == "missing_source_pair": artifact["pairs_accounted"] -= 1
    elif fault == "missing_part": artifact["parts"].pop()
    elif fault == "duplicate_port": artifact["ports"][-1] = copy.deepcopy(artifact["ports"][0])
    elif fault == "missing_native_port": artifact["ports"].pop()
    overlay = {}; replace_artifact(report, overlay, root, artifact)
    with pytest.raises((AssertionError, ValueError, KeyError)):
        summary(coupled_package_case, tmp_path, report=report, overlay=overlay)


@pytest.mark.parametrize("fault", [None, "legacy_v1", "missing_coupled", "missing_old_pressure", "missing_joint",
                                   "duplicate_candidate", "wrong_physical_kind", "legacy_with_third", "unbound_rewrite"])
def test_three_role_package_declaration_is_complete_and_bound(tmp_path, fault):
    scripts = str(Path(__file__).resolve().parents[1] / "scripts")
    sys.path.insert(0, scripts)
    try:
        from native_package_evidence import real_model_inputs
        roles = {}
        for index, (role, kind) in enumerate((('joint_fitting_budget', 'physical_route_set'),
                                              ('pressure_network', 'physical_network'),
                                              ('coupled_pressure_network', 'physical_network'))):
            roles[role] = {'candidate_id': str(index + 1) * 32, 'physical_kind': kind,
                           'candidate_root': 'a' * 64, 'prior_report_root': 'b' * 64,
                           'expected_export_sha256': 'c' * 64, 'original_store': str(tmp_path / 'source-store')}
        declaration = {'schema': 'oma.portable-real-model-inputs/2', 'source_checkpoint': 'd' * 64, 'roles': roles}
        if fault == 'legacy_v1':
            declaration['schema'] = 'oma.portable-real-model-inputs/1';roles.pop('coupled_pressure_network')
        elif fault == 'missing_coupled': roles.pop('coupled_pressure_network')
        elif fault == 'missing_old_pressure': roles.pop('pressure_network')
        elif fault == 'missing_joint': roles.pop('joint_fitting_budget')
        elif fault == 'duplicate_candidate': roles['coupled_pressure_network']['candidate_id'] = roles['pressure_network']['candidate_id']
        elif fault == 'wrong_physical_kind': roles['coupled_pressure_network']['physical_kind'] = 'physical_route_set'
        elif fault == 'legacy_with_third': declaration['schema'] = 'oma.portable-real-model-inputs/1'
        package = tmp_path / 'package';(package / 'provenance').mkdir(parents=True)
        path = package / 'provenance/real-model-validation-inputs.json'
        path.write_text(json.dumps(declaration), encoding='utf-8')
        portable = {'source_checkpoint': declaration['source_checkpoint'],
                    'real_model_validation_inputs_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        if fault == 'unbound_rewrite': path.write_text(json.dumps(declaration)+' ', encoding='utf-8')
        if fault in (None, 'legacy_v1'):
            assert real_model_inputs(package, portable) == declaration
        else:
            with pytest.raises(AssertionError): real_model_inputs(package, portable)
    finally:
        sys.path.remove(scripts)
