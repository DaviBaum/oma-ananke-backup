"""Reproduce a scoped original P3 projected hotel floor, without physics claims."""
from collections import Counter
import gzip
import hashlib
from itertools import product
import json
from pathlib import Path
import runpy
import time

from oma.optimization.separator import Region, compile_separator, verify_separator


ROOT = Path(__file__).resolve().parents[1]
SCOPE = "original-pages-p3-projected-synthetic-hotel-floor-v1"
SOURCE = "0ad4cd0c72cdb8fac573b3bfd262d86d9580a8218a98657c828b01eaba92d970"


def make_model():
    assignments = {}
    for values in product((0, 1), repeat=8):
        s, g, h, e, v, c, b, d = values
        if (g and h and d) or (c and not h and d):
            continue
        assignments[''.join(map(str, values))] = (g, 1-h+e, 2-v, e, s)
    carriers, outputs, regions, signatures = {}, {}, [], {}
    for i in range(4):
        name = f'bay{i+1}'
        signatures[name] = dict(assignments)
        carriers[name] = tuple(assignments)
        outputs[name] = dict(assignments)
        regions.append(Region(name, (), {state: {(): state} for state in assignments}))
    previous = 'bay1'
    for i in range(2, 5):
        name, child = f'floor{i}', f'bay{i}'
        table, target_signatures = {}, {}
        for a, b in product(signatures[previous], signatures[child]):
            first, second = signatures[previous][a], signatures[child][b]
            aggregate = tuple(max(x, y) if j in (2, 3) else x+y
                              for j, (x, y) in enumerate(zip(first, second)))
            state = ','.join(map(str, aggregate))
            target_signatures[state] = aggregate
            table[a, b] = state
        signatures[name] = target_signatures
        carriers[name] = tuple(sorted(target_signatures))
        outputs[name] = target_signatures
        regions.append(Region(name, (previous, child), {'compose': table}))
        previous = name
    return carriers, regions, outputs


def independent_projected_count_oracle():
    # Independent recurrence on exactly the 32 admitted projected bay profiles,
    # using their source-label multiplicity. Does not read compiled transitions.
    profiles = Counter()
    for s, g, h, e, v, c, b, d in product((0, 1), repeat=8):
        if not (g and h and d) and not (c and not h and d):
            profiles[g, 1-h+e, 2-v, e, s] += 1
    floor = profiles
    counts = [len(floor)]
    for _ in range(3):
        next_floor = Counter()
        for (l, f, o, u, r), count in floor.items():
            for (dl, df, do, du, dr), number in profiles.items():
                next_floor[l+dl, f+df, max(o, do), max(u, du), r+dr] += count * number
        floor = next_floor
        counts.append(len(floor))
    return counts, floor


def main():
    code_paths = [ROOT/'src/oma/optimization'/name for name in ('separator.py', 'fdqa.py', 'finite.py')]
    before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in code_paths}
    started = time.perf_counter()
    carriers, regions, outputs = make_model()
    preparation = time.perf_counter() - started
    started = time.perf_counter()
    certificate = compile_separator(carriers, regions, outputs, root_region='floor4', context_root=SCOPE, max_work=10_000_000)
    compilation = time.perf_counter() - started
    started = time.perf_counter()
    verification = verify_separator(carriers, regions, outputs, certificate, root_region='floor4', context_root=SCOPE, max_work=10_000_000)
    checking = time.perf_counter() - started
    if verification['status'] != 'PASS':
        raise RuntimeError(verification)
    oracle_counts, oracle = independent_projected_count_oracle()
    ids = {tuple(state): i for i, state in enumerate(certificate['fdqa']['states'])}
    expected = Counter()
    for profile, count in oracle.items():
        state = ','.join(map(str, profile))
        expected[certificate['fdqa']['block_of'][ids['floor4', state]]] += count
    assert expected == {row['block']: row['count'] for row in certificate['messages']['floor4']}
    assert oracle_counts == [32, 126, 320, 650]
    assert sum(expected.values()) == 192**4
    # Small complete assignment ground truth is independent of the compiler.
    fixture = runpy.run_path(str(ROOT/'tests/test_optimization_separator.py'))
    small_carriers, small_regions, small_outputs = fixture['shared_capacity_model']()
    small_cert = compile_separator(small_carriers, small_regions, small_outputs, root_region='R', context_root='small-exhaustive')
    small_counts, _ = fixture['exhaustive'](small_carriers, small_regions, small_outputs, small_cert)
    assert small_counts == {row['block']: row['count'] for row in small_cert['messages']['R']}
    after = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in code_paths}
    if before != after:
        raise RuntimeError('Implementation changed during benchmark')
    encoded = (json.dumps(certificate, sort_keys=True, separators=(',', ':'))+'\n').encode('utf8')
    artifact = ROOT/'evidence/math/original-separator-hotel-floor-certificate.json.gz'
    artifact.write_bytes(gzip.compress(encoded, mtime=0))
    report = {
        'status': 'PASS', 'source_sha256': SOURCE,
        'source_ranges': ['1-10:P7423-P10005', '1-10:P10074-P10166'],
        'source_objects': ['ALG-DS1', 'ALG-DS3', 'THM-DS19.1', 'THM-DS20.1', 'THM-DS13A'],
        'scope': 'Synthetic feasible hotel assignments under explicitly approved aggregate observation projection',
        'corrections': ['Projection of cost, schedule and facade observations is not conditioning all 192 assignments into a fixed stratum',
                        'Original choice labels and multiplicity are retained; arbitrary menu deduplication is not certified',
                        'Root message memory is included separately from nonroot separator width'],
        'not_claimed': ['Physical IFC validity', 'Whole building closure', 'Automatic compact physics discovery', 'Measured speedup against exhaustive 192**4 evaluation'],
        'source_label_count_per_bay': 192, 'projected_message_counts': oracle_counts,
        'metrics': certificate['metrics'], 'independent_checker': verification,
        'small_exhaustive_assignment_count': sum(small_counts.values()),
        'timings_seconds': {'explicit_input_preparation': preparation, 'compilation_and_dp': compilation, 'independent_check': checking},
        'implementation_sha256': before, 'certificate': str(artifact.relative_to(ROOT)),
        'certificate_uncompressed_sha256': hashlib.sha256(encoded).hexdigest(),
        'certificate_compressed_sha256': hashlib.sha256(artifact.read_bytes()).hexdigest(),
        'certificate_compressed_bytes': artifact.stat().st_size,
    }
    (ROOT/'evidence/math/original-separator-hotel-floor-benchmark.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
