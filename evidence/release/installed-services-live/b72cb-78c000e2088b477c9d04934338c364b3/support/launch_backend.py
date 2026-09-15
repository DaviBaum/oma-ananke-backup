"""Guarded loopback launcher for the separately cloned whole-services Store."""
from pathlib import Path
import hashlib
import json
import os
import socket
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
manifest = json.loads((HERE / 'manifest.json').read_text())


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


regression_path = Path(manifest['regression_result'])
regression = json.loads(regression_path.read_text())
assert regression['status'] == 'PASS', 'Full regression has not passed; refusing startup'
assert regression['checker_version'] == manifest['checker_version']
assert regression['source_files'] == manifest['source_files']
assert len(manifest['source_files']) == 117
assert regression['passed'] == regression['test_node_count'] == 3426
assert regression['exact_case_identity_multiset'] and regression['source_unchanged'] and regression['native_unchanged']
xml_path = regression_path.parent / 'tests.xml'
assert sha(xml_path) == regression['test_xml_sha256']
xml = ET.parse(xml_path).getroot()
assert len(xml.findall('.//testcase')) == 3426
assert not any(xml.findall('.//' + name) for name in ('failure', 'error', 'skipped'))
runtime = Path(manifest['runtime'])
source = runtime / 'src'
actual = {p.relative_to(source).as_posix(): sha(p) for p in source.rglob('*.py')}
assert actual == manifest['source_files'], 'Runtime source inventory/hash differs from exact tested source'
for relative, expected in manifest['support_files'].items():
    assert sha(runtime / relative) == expected
native = manifest['native_environment']
assert Path(sys.executable).resolve() == Path(native['interpreter']).resolve()
assert sha(sys.executable) == native['python_sha256']
for entry in native['native_extensions'].values():
    assert sha(entry['path']) == entry['sha256']
assert manifest['host'] == '127.0.0.1' and manifest['port'] == 8769
assert manifest['recover'] is False and manifest['timeout_graceful_shutdown'] == 10
with socket.socket() as probe:
    if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    probe.bind((manifest['host'], manifest['port']))
sys.path.insert(0, str(source))
os.environ['PYTHONPATH'] = str(source)
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
os.environ['OMA_EXECUTABLE_BUILD'] = manifest['checker_version']
os.environ['OMA_SHARED_TREE_SOURCE'] = str(source / 'oma/optimization/shared_tree_synthesis.py')
os.environ['OMA_DATA_DIR'] = manifest['store']
from oma.build_identity import checker_version
assert checker_version() == manifest['checker_version']
from oma.api import create_app
import uvicorn
app = create_app(manifest['store'], recover=False)
receipt = {'status': 'REGRESSION_AND_RUNTIME_IDENTITIES_VERIFIED_STARTING', 'pid': os.getpid(),
           'checker_version': checker_version(), 'python': sys.executable, 'source': str(source),
           'store': manifest['store'], 'host': manifest['host'], 'port': manifest['port'],
           'recover': False, 'timeout_graceful_shutdown': 10,
           'regression_result_sha256': sha(regression_path), 'manifest_sha256': sha(HERE / 'manifest.json')}
(HERE / 'startup-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
print(json.dumps(receipt), flush=True)
uvicorn.run(app, host=manifest['host'], port=manifest['port'], timeout_graceful_shutdown=10)
