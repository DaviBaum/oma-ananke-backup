"""Retain the independently tested packaging guards without executable changes."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
output = Path(__file__).resolve().parent
portable = json.loads((output / 'result.json').read_text())
source = ROOT / 'evidence/release/packaging-harness-final-fff4a8b950634c9496b79e4cf3516e69'
receipt = json.loads((source / 'result.json').read_text())
target = Path(portable['package']) / 'provenance/packaging-harness-validation'
assert not target.exists()
files = {**receipt['source_files'], 'tests.xml': receipt['xml_sha256'],
         'result.json': hashlib.sha256((source / 'result.json').read_bytes()).hexdigest()}
for relative, digest in files.items():
    original = source / relative
    assert hashlib.sha256(original.read_bytes()).hexdigest() == digest
    destination = target / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(original, destination)
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == digest
record = {'status': 'FROZEN_PACKAGING_HARNESS_EVIDENCE_RETAINED', 'passed': receipt['passed'],
          'source': str(source), 'destination': str(target), 'files': files,
          'scope': receipt['scope'], 'executable_payload_modified': False}
(output / 'retained-packaging-harness.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({'status': record['status'], 'files': len(files), 'passed': receipt['passed']}))
