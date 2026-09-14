"""Exact portable payload and frozen-test evidence checks shared by build/seal."""
from collections import Counter
from pathlib import Path
import json
import re
import hashlib
import sqlite3
import zlib
import xml.etree.ElementTree as ET

from native_prepare import sha

PAYLOAD_DIRECTORIES = ("src", "runtime", "ui", "wheelhouse", "docs", "scripts")
PAYLOAD_FILES = ("OMA.cmd", "Start-OMA.ps1", "Install-OMA.ps1", "README.md", "requirements-runtime.lock")
REAL_MODEL_ROLES = {"joint_fitting_budget": ("real-office-validation.json", "physical_route_set"),
                    "pressure_network": ("real-office-pressure-validation.json", "physical_network")}


def real_model_inputs(package, portable):
    path = Path(package) / "provenance/real-model-validation-inputs.json"
    assert sha(path) == portable["real_model_validation_inputs_sha256"]
    declaration = json.loads(path.read_text())
    assert declaration["schema"] == "oma.portable-real-model-inputs/1"
    assert declaration["source_checkpoint"] == portable["source_checkpoint"]
    assert set(declaration["roles"]) == set(REAL_MODEL_ROLES)
    assert len({r['candidate_id'] for r in declaration['roles'].values()}) == 2
    for role, row in declaration["roles"].items():
        assert row["physical_kind"] == REAL_MODEL_ROLES[role][1]
        for key in ("candidate_root", "prior_report_root", "expected_export_sha256"):
            assert re.fullmatch('[0-9a-f]{64}', row[key])
        assert Path(row["original_store"]).is_absolute()
    return declaration


class ReadOnlyBlobs:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()

    def get(self, root):
        assert re.fullmatch('[0-9a-f]{64}', root)
        value = json.loads(zlib.decompress((self.directory / 'blobs' / (root + '.json.z')).read_bytes()))
        encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf8')
        assert hashlib.sha256(encoded).hexdigest() == root
        return value


def verify_real_model_receipt(package, portable, portable_result, role, receipt):
    package = Path(package).resolve()
    declaration = real_model_inputs(package, portable)
    target = declaration['roles'][role]
    assert receipt['validation_role'] == role
    assert receipt['real_model_validation_inputs_sha256'] == portable['real_model_validation_inputs_sha256']
    assert Path(receipt['package']).resolve() == package
    assert receipt['portable_validation_result_sha256'] == sha(portable_result)
    assert receipt['validated_payload_manifest_sha256'] == portable['validated_payload_manifest_sha256']
    assert receipt['status'] == 'REAL_EXPORTED_OFFICE_RECHECK_PASS'
    for key in ('candidate_id', 'candidate_root', 'prior_report_root', 'prior_checker_version', 'physical_kind'):
        assert receipt[key] == target[key]
    assert Path(receipt['original_store']).resolve() == Path(target['original_store']).resolve()
    assert receipt['checker_version'] == portable['identity']['checker_version'] != receipt['prior_checker_version']
    assert receipt['source_checkpoint'] == portable['source_checkpoint']
    assert all(receipt[k] is True for k in ('original_bytes_and_head_unchanged', 'original_candidate_and_run_unchanged',
                                           'same_objective_and_obligation_dispositions'))
    assert receipt['active_store_write_mode'] == 'READ_ONLY'
    store = ReadOnlyBlobs(receipt['isolated_store'])
    report = store.get(receipt['report_root'])
    assert report == receipt['report'] and report['status'] == 'PASS'
    assert report['candidate_root'] == target['candidate_root'] and report['checker_version'] == receipt['checker_version']
    prior = store.get(target['prior_report_root'])
    assert prior['checker_version'] == target['prior_checker_version'] and prior['candidate_root'] == target['candidate_root']
    assert prior['status'] == 'PASS' and report['objective'] == prior['objective']
    rows = {r['id']: r for r in report['results']}
    assert len(rows) == len(report['results'])
    assert {k: r['status'] for k, r in rows.items()} == {r['id']: r['status'] for r in prior['results']}
    execution = receipt['execution']
    assert execution['status'] == execution['supervision']['status'] == 'COMPLETED' and execution['report_published'] is True
    assert execution['report_root'] == receipt['report_root'] and execution['candidate_id'] == target['candidate_id']
    assert execution['supervision']['checker_version'] == receipt['checker_version']
    assert Path(execution['supervision']['command'][0]).resolve() == package / 'runtime/python.exe'
    with sqlite3.connect((store.directory / 'oma.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
        current = db.execute('SELECT status,state_root,report_root FROM candidates WHERE id=?', (target['candidate_id'],)).fetchone()
        assert current == ('CHECKED', target['candidate_root'], receipt['report_root'])
        token = db.execute('SELECT e.execution_id,e.status,e.report_root FROM candidate_check_executions h JOIN check_executions e ON e.execution_id=h.execution_id WHERE h.candidate_id=?', (target['candidate_id'],)).fetchone()
        assert token == (execution['execution_id'], 'COMPLETED', receipt['report_root'])
    state = store.get(target['candidate_root'])
    physical = state['routes'] if role == 'joint_fitting_budget' else state['physical_networks']
    assert physical and len({r['id'] for r in physical}) == len(physical)
    assert set(receipt['physical_record_ids']) == {r['id'] for r in physical} and len(receipt['physical_record_ids']) == len(physical)
    assert {store.get(r['geometry_artifact'])['export_sha256'] for r in physical} == {target['expected_export_sha256']}
    for path, expected in receipt['source_and_exported_files'].items():
        assert sha(Path(path)) == expected
    if role == 'pressure_network':
        from native_real_model_validation import network_validation_evidence
        current = network_validation_evidence(store, state, report, store.directory, 'seal', retain=False)
        assert current == receipt['network_evidence']
        assert current['operating_point_status'] == current['service_status'] == 'PASS'
        assert len(current['deliveries']) == 2 and current['physical_components'] > 0
        return current
    budget = rows['joint-new-fitting-budget']
    witness = budget['witness']
    assert budget['status'] == 'PASS' and witness['count_complete'] is True
    assert witness['candidate_root'] == target['candidate_root'] and witness['checker_version'] == receipt['checker_version']
    counts = witness['per_new_route']
    assert counts and all(type(v) is int and v >= 0 for v in counts.values())
    assert sum(counts.values()) == witness['count'] <= witness['declared_budget']
    cad_rows, all_guids = [], []
    for route in physical:
        check = rows[route['id'] + ':physical-interference-and-clearance']
        assert check['status'] == 'PASS'
        cad = store.get(check['witness']['artifact'])
        guids = cad['route_guids']
        assert guids and len(guids) == len(set(guids)) == cad['route_count']
        assert cad['coordination_status'] == cad['self_interference_status'] == 'PASS'
        assert cad['pairs_accounted'] == cad['route_count'] * cad['obstacle_count']
        assert not any(cad[k] for k in ('failed_pairs', 'unknown_pairs', 'blocked_pairs'))
        assert cad['export_sha256'] == target['expected_export_sha256']
        assert sorted(s['sha256'] for s in cad['sources']) == sorted(s['sha256'] for s in state['sources'])
        cad_rows.append({'route_id': route['id'], 'parts': len(guids), 'obstacles': cad['obstacle_count'], 'source_pairs': cad['pairs_accounted'], 'artifact': check['witness']['artifact']})
        all_guids.extend(guids)
    assert len(all_guids) == len(set(all_guids))
    cross = rows['cross-route-interference']
    expected_pairs = sum(a['parts'] * b['parts'] for i, a in enumerate(cad_rows) for b in cad_rows[i+1:])
    assert cross['status'] == 'PASS' and cross['witness']['complete_component_coverage'] is True
    assert cross['witness']['pairs_accounted'] == expected_pairs
    return {'routes': cad_rows, 'source_pairs': sum(r['source_pairs'] for r in cad_rows),
            'cross_route_pairs': expected_pairs, 'fittings': witness['count'], 'fitting_budget': witness['declared_budget']}


def payload_files(package):
    package = Path(package).resolve()
    files = [package / name for name in PAYLOAD_FILES]
    for name in PAYLOAD_DIRECTORIES:
        directory = package / name
        assert directory.is_dir()
        for path in directory.rglob("*"):
            assert not path.is_symlink(), "Payload symlinks are not accepted"
            if path.is_file():
                files.append(path)
    return {path.relative_to(package).as_posix(): {"sha256": sha(path), "bytes": path.stat().st_size}
            for path in sorted(files)}


def verify_payload(package, portable):
    package = Path(package).resolve()
    manifest = package / "validated-payload.json"
    assert sha(manifest) == portable["validated_payload_manifest_sha256"]
    expected = json.loads(manifest.read_text())
    assert expected["checker_version"] == portable["identity"]["checker_version"]
    assert expected["source_checkpoint"] == portable["source_checkpoint"]
    source = {name.removeprefix("src/"): row["sha256"] for name, row in expected["files"].items()
              if name.startswith("src/") and name.endswith(".py")}
    assert source == portable["source_python_files"]
    extension = Path(portable["identity"]["extension"]).resolve()
    assert extension.is_relative_to(package)
    assert expected["files"][extension.relative_to(package).as_posix()]["sha256"] == portable["identity"]["extension_sha256"]
    assert expected["files"] == payload_files(package), "Portable payload changed after its validation boundary"
    return expected


def verify_test_snapshot(directory, expected, *, allow_generated_evidence=False):
    directory = Path(directory).resolve()
    normalized = {str(name).replace('\\', '/'): value for name, value in expected.items()}
    assert len(normalized) == len(expected)
    actual, generated = {}, {}
    for path in directory.rglob('*'):
        if {'__pycache__', '.pytest_cache'}.intersection(path.relative_to(directory).parts):
            continue
        assert not path.is_symlink()
        if path.is_file():
            name = path.relative_to(directory).as_posix()
            if allow_generated_evidence and re.fullmatch(
                r'evidence/release/joint-fitting-budget-audit/[0-9a-f]{32}/(?:declared-source\.ifc|source-after-pause\.ifc|result\.json)', name):
                generated[name] = sha(path)
            else:
                actual[name] = sha(path)
    assert actual == normalized, 'Frozen test/support inventory or bytes changed'
    return {"inputs": actual, "generated_evidence": generated,
            "generated_evidence_producer": "tests/test_joint_fitting_budget_adversarial.py::test_complete_joint_report_rejects_source_changed_at_final_fitting_pause"}


def verify_suite_xml(path, nodes, *, direct_interpreter=True):
    assert len(nodes) == len(set(nodes))
    expected = []
    for node in nodes:
        pieces = node.split("::")
        assert pieces[0].endswith(".py") and len(pieces) >= 2
        classname = pieces[0][:-3].replace("/", ".").replace("\\", ".")
        if len(pieces) > 2:
            classname += "." + ".".join(pieces[1:-1])
        expected.append((classname, pieces[-1]))
    xml = ET.parse(path).getroot()
    cases = xml.findall(".//testcase")
    assert Counter((c.attrib.get("classname"), c.attrib["name"]) for c in cases) == Counter(expected)
    assert not xml.findall(".//failure") and not xml.findall(".//error")
    skipped = [{"classname": c.attrib.get("classname"), "name": c.attrib["name"],
                "reason": c.find("skipped").attrib.get("message")} for c in cases if c.find("skipped") is not None]
    if not direct_interpreter:
        assert not skipped
        return {"passed": len(cases), "failed": 0, "skipped": []}
    allowed = {"test_private_bridge_corruption_is_not_reused[" + f + "]" for f in ("binary", "configuration", "extra_startup")}
    assert len(skipped) == 3 and {c["name"] for c in skipped} == allowed
    assert all(c["classname"] == "tests.test_windows_job_containment"
               and c["reason"] == "Current Python is a direct interpreter and needs no bridge" for c in skipped)
    return {"passed": len(cases) - 3, "failed": 0, "skipped": skipped}
