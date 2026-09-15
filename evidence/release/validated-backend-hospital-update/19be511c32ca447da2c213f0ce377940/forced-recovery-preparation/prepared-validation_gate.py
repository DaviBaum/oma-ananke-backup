"""Read-only original-native full-suite and explicitly supplied Hospital gate.

No automatic campaign/source selection; no custom or portable success implied.
"""
from pathlib import Path
from collections import Counter
import hashlib
import json
import re
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / 'AGENTS.md').is_file())

def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()

def inventory(path, *, python_only=False):
    root = Path(path)
    result = {}
    for p in root.rglob('*.py' if python_only else '*'):
        assert not p.is_symlink() and not p.is_junction()
        if p.is_file() and not {'__pycache__', '.pytest_cache'}.intersection(p.relative_to(root).parts):
            result[p.relative_to(root).as_posix()] = sha(p)
    return result

def xml_check(path, nodes):
    expected = []
    for node in nodes:
        bits = node.split('::')
        assert bits[0].endswith('.py') and len(bits) > 1
        cls = bits[0][:-3].replace('/', '.').replace('\\', '.')
        if len(bits) > 2:
            cls += '.' + '.'.join(bits[1:-1])
        expected.append((cls, bits[-1]))
    root = ET.parse(path)
    cases = root.findall('.//testcase')
    assert Counter((c.attrib['classname'], c.attrib['name']) for c in cases) == Counter(expected)
    assert all(not root.findall('.//' + name) for name in ('error', 'failure', 'skipped'))

def completed_validation():
    cfg = read(HERE / 'configuration.json')
    assert cfg.get('configuration_status') == 'FROZEN_VALIDATION_DECLARED', 'The explicitly named replacement source still needs its exact full-validation declaration'
    directory = Path(cfg['full_directory']).resolve()
    full = read(directory / 'result.json')
    assert full['status'] == 'PASS', 'Full original-native suite has not completed PASS'
    assert type(cfg['test_count']) is int and cfg['test_count'] >= 3306
    assert full['phase'] == 'full' and full['passed'] == cfg['test_count'] and full['returncode'] == 0
    assert all(full[k] is True for k in ('exact_case_identity_multiset', 'inputs_unchanged', 'source_unchanged', 'native_unchanged'))
    build = 'oma-independent-checker/2:' + cfg['target_build']
    assert full['checker_version'] == build
    assert Path(full['source_directory']).resolve() == Path(cfg['source_directory']).resolve()
    for name, expected in cfg['immutable_validation_inputs'].items():
        assert sha(directory / name) == expected
    sources = read(directory / 'source.json')
    inputs = read(directory / 'inputs.json')['files']
    nodes = read(directory / 'test-nodes.json')
    assert type(cfg['input_count']) is int and cfg['input_count'] >= 308
    assert len(sources) == cfg['source_count'] == 114 and len(inputs) == cfg['input_count']
    assert len(nodes) == len(set(nodes)) == cfg['test_count']
    assert sources == full['source_files'] and inputs == full['snapshot_files']
    assert inventory(cfg['source_directory'], python_only=True) == sources
    assert sha(directory / 'test-nodes.json') == full['exact_collected_nodes_sha256']
    assert sha(directory / 'tests.xml') == full['test_xml_sha256']
    xml_check(directory / 'tests.xml', nodes)
    actual = inventory(full['snapshot'])
    extras = {k: v for k, v in actual.items() if k not in inputs}
    assert {k: v for k, v in actual.items() if k not in extras} == inputs
    assert extras == full['derived_outputs'] == read(directory / 'derived-outputs.json')
    assert len(extras) == 6 and all(re.fullmatch(r'evidence/release/(?:joint-fitting-budget-audit/[0-9a-f]{32}/(?:declared-source\.ifc|source-after-pause\.ifc|result\.json)|joint-probe-native-audit/[0-9a-f]{32}/(?:current-separated\.ifc|transient-overlap\.ifc|result\.json))', k) for k in extras)
    native = read(directory / 'native-environment.json')
    assert native['checker_version'] == build
    python = ROOT / '.venv/Scripts/python.exe'
    assert Path(native['interpreter']).resolve() == python.resolve() and sha(python) == native['python_sha256']
    assert len(native['native_extensions']) >= 2
    for record in native['native_extensions'].values():
        assert sha(record['path']) == record['sha256']
    assert full['command'] == [str(python), '-m', 'pytest', '-q', '-o', 'pythonpath=' + Path(cfg['source_directory']).as_posix(), 'tests', '--junitxml=' + str(directory / 'tests.xml'), '--basetemp=' + str(directory / 'native-stores')]
    kernel = Path(cfg['source_directory']) / 'oma/optimization/shared_tree_synthesis.py'
    assert Path(full['kernel_direct_load_path']).resolve() == kernel.resolve() and sha(kernel) == sources['oma/optimization/shared_tree_synthesis.py']

    # Root supplies this exact completed receipt; failed 426104 remains historical.
    pointer = HERE / cfg['outcome_pointer']
    assert pointer.is_file(), 'No explicitly approved completed Hospital outcome receipt supplied'
    approved = read(pointer)
    assert approved['status'] == 'ROOT_APPROVED_COMPLETED_HOSPITAL_EVIDENCE'
    campaign = Path(approved['campaign_directory']).resolve()
    audit_dir = Path(approved['audit_directory']).resolve()
    pinned = {
        campaign / 'result.json': approved['campaign_result_sha256'],
        campaign / 'predeclaration.json': approved['campaign_predeclaration_sha256'],
        audit_dir / 'result.json': approved['audit_result_sha256'],
        audit_dir / 'inputs.json': approved['audit_inputs_sha256'],
        audit_dir / 'executed-audit.py': approved['audit_script_sha256'],
    }
    assert all(sha(p) == value for p, value in pinned.items())
    current, declaration = read(campaign / 'result.json'), read(campaign / 'predeclaration.json')
    assert current['status'] == 'ACCEPTED_AND_FRESH_EXPORT_CHECKED'
    assert current['original_bytes_unchanged'] is True and current['app_unchanged'] is True
    assert declaration['checker_version'] == build and declaration['app_sources'] == sources
    assert declaration['authored_query_root'] == cfg['authored_query_root'] == digest(declaration['authored_query'])
    assert current['accepted']['status'] == 'ACCEPTED' and current['accepted']['revision'] == declaration['project_before']['revision'] + 1
    assert current['project_after']['revision'] == current['accepted']['revision']
    assert current['project_after']['state_root'] == current['accepted']['state_root']
    assert current['export']['status'] == 'CHECKED_LOCAL_SCOPE' and current['export']['round_trip'] == 'PASS'
    audit, audit_inputs = read(audit_dir / 'result.json'), read(audit_dir / 'inputs.json')
    assert audit['status'] == 'BOTH_FIXED_ALTERNATIVES_AND_SELECTED_FRESH_EXPORT_AUDITED'
    assert all(audit[k] is True for k in ('files_unchanged', 'app_unchanged', 'store_project_unchanged'))
    assert audit_inputs['app'] == sources
    assert audit_inputs['files'][str(campaign / 'result.json')] == approved['campaign_result_sha256']
    assert audit_inputs['files'][str(campaign / 'predeclaration.json')] == approved['campaign_predeclaration_sha256']
    assert audit['selection']['selected'] == current['selected_candidate_id']
    assert audit['acceptance']['revision']['root'] == current['accepted']['state_root']
    assert audit['acceptance']['revision']['status'] == 'ACCEPTED'
    assert audit['acceptance']['revision']['candidate_id'] == current['selected_candidate_id']
    assert audit['acceptance']['event']['state_root'] == current['accepted']['state_root']
    assert audit['fresh_export']['status'] == 'CHECKED'
    for p, value in declaration['original_files'].items():
        assert sha(p) == value
    for row in [*audit['candidates'], audit['fresh_export']]:
        material = read(audit_dir / row['id'] / 'materialization.json')
        assert sha(material['export_path']) == material['export_sha256'] == row['actual_ifc_sha256']
    return {'checker_version': build, 'source_directory': cfg['source_directory'], 'files': sources,
            'original_full_receipt': str(directory / 'result.json'), 'original_full_receipt_sha256': sha(directory / 'result.json'),
            'original_nodes_sha256': sha(directory / 'test-nodes.json'), 'input_manifest_sha256': sha(directory / 'inputs.json'),
            'hospital_campaign': str(campaign), 'hospital_audit': str(audit_dir),
            'approved_outcome_sha256': sha(pointer), 'completed_evidence_hashes': {str(p): value for p, value in pinned.items()},
            'validation_scope': cfg['validation_scope']}
