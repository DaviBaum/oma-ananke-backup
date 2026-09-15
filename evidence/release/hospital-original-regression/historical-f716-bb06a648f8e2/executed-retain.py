"""Retain one CLOSED exact original-native regression, excluding native Stores."""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json
import re
import shutil
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / 'AGENTS.md').is_file())

def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')

def files(directory):
    result = {}
    for p in directory.rglob('*'):
        assert not p.is_symlink() and not p.is_junction()
        if p.is_file() and not {'__pycache__', '.pytest_cache'}.intersection(p.relative_to(directory).parts):
            result[p.relative_to(directory).as_posix()] = sha(p)
    return result

def retain(full, destination, build, case_count, input_count, supplements):
    full, destination = Path(full).resolve(), Path(destination).resolve()
    receipt = read(full / 'result.json')
    assert receipt['status'] in {'PASS', 'FAIL'}, 'Only a terminal receipt can be retained'
    assert receipt['phase'] == 'full' and receipt['checker_version'] == 'oma-independent-checker/2:' + build
    initial_receipt_sha = sha(full / 'result.json')
    source, snapshot = Path(receipt['source_directory']), Path(receipt['snapshot'])
    sources, inputs, nodes = read(full / 'source.json'), read(full / 'inputs.json')['files'], read(full / 'test-nodes.json')
    assert len(sources) == 114 and len(inputs) == input_count and len(nodes) == len(set(nodes)) == case_count
    assert sources == receipt['source_files'] and inputs == receipt['snapshot_files']
    assert sha(full / 'test-nodes.json') == receipt['exact_collected_nodes_sha256']
    actual_source = {p.relative_to(source).as_posix(): sha(p) for p in source.rglob('*.py')}
    actual_snapshot = files(snapshot)
    extras = {k: v for k, v in actual_snapshot.items() if k not in inputs}
    differences = {'source': sorted(k for k in set(sources) | set(actual_source) if sources.get(k) != actual_source.get(k)),
                   'inputs': sorted(k for k, v in inputs.items() if actual_snapshot.get(k) != v)}
    counts, exact_nodes = None, False
    if (full / 'tests.xml').is_file():
        xml = ET.parse(full / 'tests.xml')
        cases = xml.findall('.//testcase')
        counts = {key: len(xml.findall('.//' + key)) for key in ('testcase', 'failure', 'error', 'skipped')}
        expected = []
        for node in nodes:
            parts = node.split('::')
            classname = parts[0][:-3].replace('/', '.').replace('\\', '.')
            if len(parts) > 2:
                classname += '.' + '.'.join(parts[1:-1])
            expected.append((classname, parts[-1]))
        exact_nodes = Counter((c.attrib['classname'], c.attrib['name']) for c in cases) == Counter(expected)
    if receipt['status'] == 'PASS':
        assert receipt['passed'] == case_count and receipt['returncode'] == 0
        assert not any(differences.values()) and exact_nodes
        assert counts == {'testcase': case_count, 'failure': 0, 'error': 0, 'skipped': 0}
        assert all(receipt[k] is True for k in ('exact_case_identity_multiset', 'inputs_unchanged', 'source_unchanged', 'native_unchanged'))
        assert sha(full / 'tests.xml') == receipt['test_xml_sha256']
        assert extras == receipt['derived_outputs'] == read(full / 'derived-outputs.json')
        assert len(extras) == 6 and all(re.fullmatch(r'evidence/release/(?:joint-fitting-budget-audit/[0-9a-f]{32}/(?:declared-source\.ifc|source-after-pause\.ifc|result\.json)|joint-probe-native-audit/[0-9a-f]{32}/(?:current-separated\.ifc|transient-overlap\.ifc|result\.json))', k) for k in extras)
    native = read(full / 'native-environment.json')
    assert native['checker_version'] == receipt['checker_version']
    native_current = {'interpreter': sha(native['interpreter']) == native['python_sha256'],
                      'extensions': {key: sha(v['path']) == v['sha256'] for key, v in native['native_extensions'].items()}}
    if receipt['status'] == 'PASS':
        assert native_current['interpreter'] and all(native_current['extensions'].values())

    assert not destination.exists(), 'Never overwrite retained evidence'
    destination.mkdir(parents=True)
    mapping = []
    def copy(path, relative):
        path = Path(path).resolve()
        target = (destination / relative).resolve()
        assert target.is_relative_to(destination) and not target.exists()
        target.parent.mkdir(parents=True, exist_ok=True)
        before = sha(path)
        shutil.copyfile(path, target)
        assert before == sha(path) == sha(target)
        mapping.append({'original': str(path), 'retained': target.relative_to(destination).as_posix(), 'bytes': target.stat().st_size, 'sha256': before})
    for name in ('result.json', 'inputs.json', 'source.json', 'test-nodes.json', 'native-environment.json', 'runner.py', 'collection.log', 'pytest.log', 'tests.xml', 'derived-outputs.json'):
        if (full / name).is_file():
            copy(full / name, name)
    for relative in sorted(sources):
        copy(source / relative, 'src/' + relative)
    for relative in sorted(inputs):
        copy(snapshot / relative, 'snapshot/' + relative)
    for relative in sorted(extras):
        copy(snapshot / relative, 'snapshot/' + relative)
    supplement_records = []
    for item in supplements:
        folder = Path(item['directory']).resolve()
        if item.get('handoff_sha256'):
            assert sha(folder / 'handoff.json') == item['handoff_sha256']
            handoff = read(folder / 'handoff.json')
            expected = handoff['retained_files']
            assert all(sha(folder / k) == v for k, v in expected.items())
        supplied = files(folder)
        for relative in sorted(supplied):
            copy(folder / relative, 'supplements/' + item['label'] + '/' + relative)
        supplement_records.append({'label': item['label'], 'input_directory': str(folder), 'files': supplied})
    copy(Path(__file__), 'executed-retain.py')
    assert sha(full / 'result.json') == initial_receipt_sha
    assert {p.relative_to(source).as_posix(): sha(p) for p in source.rglob('*.py')} == actual_source
    assert files(snapshot) == actual_snapshot
    write(destination / 'copy-map.json', mapping)
    report = {'status': 'EXACT_ORIGINAL_NATIVE_FULL_RETENTION_PASS' if receipt['status'] == 'PASS' else 'HISTORICAL_FAILED_FULL_RUN_RETAINED',
              'original_status': receipt['status'], 'original_receipt_sha256': initial_receipt_sha,
              'source_build': build, 'source_count': len(sources), 'input_count': len(inputs), 'test_count': case_count,
              'xml_counts': counts, 'exact_case_identity_multiset': exact_nodes, 'input_differences': differences,
              'source_manifest': sources, 'snapshot_inputs': inputs, 'derived_outputs': extras,
              'test_nodes_sha256': sha(full / 'test-nodes.json'), 'native_files_current_match_receipt': native_current,
              'original_snapshot_and_receipt_unchanged_during_copy': True, 'supplements': supplement_records,
              'native_temp_stores_copied': False, 'new_test_or_CAD_run': False,
              'scope': 'Closed original local native regression only. No custom/portable/full-building or current live-upgrade claim. f716 and06aa remain distinct checkpoints.'}
    write(destination / 'retention-result.json', report)
    (destination / 'README.md').write_text(
        '# Closed Hospital-backend regression evidence\n\n'
        + f'Original status: {receipt["status"]}. Source: `{build}`. Exact declared tests: {case_count}.\n\n'
        + '`result.json` is the unchanged original receipt. `retention-result.json` independently reconciles the exact source/test inventory and XML node multiset. `copy-map.json` maps original paths to portable relative retained files. Native temporary Stores were excluded. The six bounded generated test artifacts, when present, remain in their original snapshot-relative locations.\n\n'
        + 'For reproduction, use the separately provided original Python/native dependency environment and repository original mathematical inputs as applicable, set PYTHONPATH to this `src` and OMA_SHARED_TREE_SOURCE to `src/oma/optimization/shared_tree_synthesis.py`, then run the frozen `snapshot/tests` with pytest `-o pythonpath=ABSOLUTE_RETAINED_SRC`. This evidence is not a self-contained interpreter package. No new tests or Hospital CAD checks were run while retaining it.\n\n'
        + 'The local-tee comparison supplements retain their own failures, exact source identities and limited geometry scope. A Hospital campaign acceptance/export requires its separate current receipt; this full regression alone does not establish it.\n', encoding='utf-8')
    index = files(destination)
    write(destination / 'handoff.json', {'status': report['status'], 'source_build': build, 'original_status': receipt['status'],
                                        'original_receipt_sha256': initial_receipt_sha, 'retained_files': index})
    return {'directory': str(destination), 'status': report['status'], 'handoff_sha256': sha(destination / 'handoff.json')}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full-directory', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--build', required=True)
    parser.add_argument('--expected-tests', type=int, required=True)
    parser.add_argument('--expected-inputs', type=int, required=True)
    parser.add_argument('--supplements', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(retain(args.full_directory, args.destination, args.build, args.expected_tests, args.expected_inputs, read(args.supplements))))
