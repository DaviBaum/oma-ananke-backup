"""Freeze and validate only this private theorem package; no production writes."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
DRIVER = Path(__file__).read_bytes()
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')
def inventory(directory):
    return {p.relative_to(directory).as_posix(): sha(p) for p in sorted(directory.rglob('*.py'))}


def main():
    source = inventory(ROOT / 'src')
    source_root = hashlib.sha256(json.dumps(source, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    runtime = ROOT / 'runtimes' / source_root / 'src'
    for relative, digest in source.items():
        target = runtime / relative
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / 'src' / relative, target)
        assert sha(target) == digest
    assert inventory(runtime) == source
    directory = ROOT / 'validation' / uuid.uuid4().hex
    (directory / 'tests').mkdir(parents=True)
    tests = inventory(ROOT / 'tests')
    for relative, digest in tests.items():
        target = directory / 'tests' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / 'tests' / relative, target)
        assert sha(target) == digest
    (directory / 'pytest.ini').write_text('[pytest]\naddopts =\npythonpath =\n')
    (directory / 'executed-driver.py').write_bytes(DRIVER)
    env = os.environ.copy()
    env.update(PYTHONPATH=str(runtime), PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    for name in ('OMA_EXECUTABLE_BUILD', 'OMA_CONTROL_RUN_ID'): env.pop(name, None)
    base = [sys.executable, '-m', 'pytest', '-c', str(directory / 'pytest.ini'), '-o', 'pythonpath=' + str(runtime), '-q']
    started = time.monotonic()
    result = {'status': 'RUNNING', 'source_root': source_root, 'runtime': str(runtime),
              'source_files': source, 'test_files': tests, 'python': sys.version,
              'driver_sha256': hashlib.sha256(DRIVER).hexdigest(),
              'scope': 'Private declared-polynomial univalence theorem and composition tests; no native or production integration claim'}
    write(directory / 'result.json', result)
    try:
        collection = subprocess.run([*base, '--collect-only', 'tests'], cwd=directory, env=env, text=True, capture_output=True, timeout=60)
        (directory / 'collection.log').write_text(collection.stdout + collection.stderr)
        assert collection.returncode == 0
        nodes = [line for line in collection.stdout.splitlines() if line.startswith('tests/') and '::' in line]
        assert nodes and len(set(nodes)) == len(nodes)
        node_path = directory / 'selected-tests.args'
        node_path.write_text('\n'.join(nodes) + '\n')
        command = [*base, '@' + str(node_path), '--junitxml=' + str(directory / 'tests.xml')]
        run = subprocess.run(command, cwd=directory, env=env, text=True, capture_output=True, timeout=60)
        (directory / 'pytest.log').write_text(run.stdout + run.stderr)
        cases = list(ET.parse(directory / 'tests.xml').getroot().iter('testcase'))
        expected = Counter((node.split('::')[0][:-3].replace('/', '.'), '::'.join(node.split('::')[1:])) for node in nodes)
        actual = Counter((row.attrib['classname'], row.attrib['name']) for row in cases)
        assert run.returncode == 0 and actual == expected
        assert all(row.find('failure') is None and row.find('error') is None and row.find('skipped') is None for row in cases)
        assert inventory(runtime) == source == inventory(ROOT / 'src')
        assert inventory(directory / 'tests') == tests == inventory(ROOT / 'tests')
        assert Path(__file__).read_bytes() == DRIVER
        result.update(status='PRIVATE_UNIVALENCE_EXACT_FROZEN_SUITE_PASS', passed=len(cases), failed=0, skipped=0,
                      command=command, test_nodes=nodes, test_node_manifest_sha256=sha(node_path),
                      xml_sha256=sha(directory / 'tests.xml'), all_frozen_inputs_unchanged=True)
    except BaseException as error:
        result.update(status='INCOMPLETE_OR_FAILED', error=repr(error))
        raise
    finally:
        result['seconds'] = time.monotonic() - started
        write(directory / 'result.json', result)
        print(json.dumps({'status': result['status'], 'source_root': source_root, 'passed': result.get('passed'),
                          'seconds': result['seconds'], 'receipt': str(directory / 'result.json')}), flush=True)


if __name__ == '__main__': main()
