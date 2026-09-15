"""Independent byte/inventory/XML replay of a retained full-run packet; no tests."""
from collections import Counter
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET

def checksum(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def require(condition, message):
    if not condition:
        raise ValueError(message)

def run(packet, output):
    packet, output = packet.resolve(), output.resolve()
    require(not output.exists(), 'Audit output already exists')
    manifest = read(packet / 'handoff.json')
    required = manifest['retained_files']
    before = checksum(packet / 'handoff.json')
    actual = {p.relative_to(packet).as_posix(): checksum(p) for p in packet.rglob('*') if p.is_file() and p != packet / 'handoff.json'}
    require(actual == required, 'Whole retained packet differs from indexed bytes')
    result = read(packet / 'result.json')
    source = read(packet / 'source.json')
    inputs = read(packet / 'inputs.json')['files']
    derived = read(packet / 'derived-outputs.json')
    nodes = read(packet / 'test-nodes.json')
    require(result['status'] == 'PASS' and result['returncode'] == 0, 'Original full run did not pass')
    require(manifest['source_build'] == '06aa865600b4ab2dc8f42f77b2cb5f82816dec99bbf8a1ff5f67673fb44c1949', 'Wrong source build')
    require(len(source) == 114 and len(inputs) == 309 and len(nodes) == len(set(nodes)) == 3317, 'Wrong exact denominator')
    require({k[4:]: v for k, v in actual.items() if k.startswith('src/')} == source == result['source_files'], 'Source inventory mismatch')
    require({k[9:]: v for k, v in actual.items() if k.startswith('snapshot/')} == {**inputs, **derived}, 'Snapshot inventory mismatch')
    require(inputs == result['snapshot_files'] and derived == result['derived_outputs'], 'Receipt inventory mismatch')
    require(len(derived) == 6, 'Unexpected generated file denominator')
    generated_groups = {}
    for name in derived:
        parts = Path(name).parts
        require(parts[:2] == ('evidence', 'release') and len(parts) == 5, 'Unexpected generated path')
        require(len(parts[3]) == 32 and all(c in '0123456789abcdef' for c in parts[3]), 'Unexpected generated attempt ID')
        generated_groups.setdefault(parts[2], set()).add(parts[4])
    require(generated_groups == {'joint-fitting-budget-audit': {'declared-source.ifc', 'source-after-pause.ifc', 'result.json'},
                                 'joint-probe-native-audit': {'current-separated.ifc', 'transient-overlap.ifc', 'result.json'}}, 'Generated artifact scope differs')
    xml = ET.parse(packet / 'tests.xml')
    cases = xml.findall('.//testcase')
    require(not any(xml.findall('.//' + tag) for tag in ('failure', 'error', 'skipped')), 'XML has failure/error/skip')
    expected = Counter()
    for node in nodes:
        bits = node.split('::')
        require(bits[0].endswith('.py'), 'Invalid collected module')
        cls = bits[0][:-3].replace('/', '.').replace('\\', '.')
        if len(bits) > 2:
            cls += '.' + '.'.join(bits[1:-1])
        expected[cls, bits[-1]] += 1
    require(Counter((c.get('classname'), c.get('name')) for c in cases) == expected, 'Exact XML node multiset differs')
    require(len(cases) == result['passed'] == 3317, 'Incorrect passed count')
    require(checksum(packet / 'tests.xml') == result['test_xml_sha256'], 'XML receipt hash differs')
    require(checksum(packet / 'test-nodes.json') == result['exact_collected_nodes_sha256'], 'Collected-node hash differs')
    copy_map = read(packet / 'copy-map.json')
    require(len({r['retained'] for r in copy_map}) == len(copy_map), 'Duplicate copy-map path')
    for row in copy_map:
        destination = (packet / row['retained']).resolve()
        require(destination.is_relative_to(packet), 'Escaped retained path')
        require(checksum(Path(row['original'])) == checksum(destination) == row['sha256'], 'Original/copy SHA disagreement')
        require(destination.stat().st_size == row['bytes'], 'Original/copy size disagreement')
    native = read(packet / 'native-environment.json')
    require(checksum(Path(native['interpreter'])) == native['python_sha256'], 'Interpreter changed')
    for item in native['native_extensions'].values():
        require(checksum(Path(item['path'])) == item['sha256'], 'Native extension changed')
    require(checksum(packet / 'handoff.json') == before, 'Packet manifest changed during audit')
    require({p.relative_to(packet).as_posix(): checksum(p) for p in packet.rglob('*') if p.is_file() and p != packet / 'handoff.json'} == actual, 'Packet changed during audit')
    output.mkdir(parents=True)
    shutil.copyfile(__file__, output / 'executed-verify.py')
    report = {'status': 'INDEPENDENT_RETAINED_FULL_HASH_NODE_VERIFY_PASS', 'retained_handoff': str(packet / 'handoff.json'),
              'retained_handoff_sha256': before, 'source_build': manifest['source_build'],
              'source_files': 114, 'input_files': 309, 'derived_files': 6, 'exact_xml_nodes': len(cases),
              'failures': 0, 'errors': 0, 'skips': 0, 'indexed_files_verified': len(actual), 'original_copy_pairs_verified': len(copy_map),
              'original_receipt_sha256': checksum(packet / 'result.json'), 'xml_sha256': checksum(packet / 'tests.xml'),
              'node_list_sha256': checksum(packet / 'test-nodes.json'), 'retained_packet_unchanged': True,
              'new_tests_or_CAD': False, 'live_operations': False,
              'scope': 'Original local native full regression packet only. No Hospital outcome, live upgrade, custom environment or mathematical-completeness claim.'}
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    index = {p.name: checksum(p) for p in output.iterdir() if p.is_file()}
    (output / 'handoff.json').write_text(json.dumps({'status': report['status'], 'retained_files': index}, indent=2) + '\n', encoding='utf-8')
    return {'directory': str(output), 'status': report['status'], 'handoff_sha256': checksum(output / 'handoff.json')}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.packet, args.output)))
