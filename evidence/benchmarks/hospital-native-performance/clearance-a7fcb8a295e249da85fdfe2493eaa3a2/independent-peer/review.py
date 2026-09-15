"""Independent exact-corner/rounding checks plus real IFC lazy-loader guards.

No native Hospital run and no modification of original inputs. This checks
private helper boundaries, not authenticity of arbitrary caller CadObjects.
"""
from pathlib import Path
from fractions import Fraction as Q
import hashlib
import importlib.util
import itertools
import json
import random
import sys
import tempfile
import numpy as np

HERE = Path(__file__).resolve().parent

def load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m

cad = load('oma.ifc.review_cad', 'cad.py')
enclosure = load('oma.ifc.review_enclosure', 'enclosure.py')
fixture = load('review_enclosure_fixture', 'fixture_source.py').fixture
source = '1' * 64

def obstacle(lo, hi):
    certificate = {'status': 'ENCLOSURE_CHECKED', 'source_sha256': source,
                   'product_step_id': 7, 'frame': 'IFC_LOCAL_ENGINEERING_METRES',
                   'bounds_m': [[str(v) for v in lo], [str(v) for v in hi]]}
    bounds = tuple(np.nextafter(float(x), -np.inf) for x in lo) + tuple(np.nextafter(float(x), np.inf) for x in hi)
    return cad.CadObject(source + ':7', 'source-guid', 7, source, 'IfcBuildingElementProxy',
                         None, bounds, None, 0., False, 'enclosure', 'exact_source_support_enclosure',
                         {'exact_source_enclosure': certificate})

def route(bounds):
    # A private-helper fixture with native disposition; no native report emitted.
    return cad.CadObject('route:8', 'route-guid', 8, '2' * 64, 'IfcPipeSegment', object(), tuple(bounds), 1., 1e-7, True)

rng = random.Random(773119)
corners_checked = far_checks = 0
for case in range(96):
    lo = [Q(rng.randrange(-100, 100), 7) for _ in range(3)]
    hi = [x + Q(rng.randrange(1, 10), 11) for x in lo]
    matrix = np.eye(4)
    theta = case % 4
    matrix[:2, :2] = [(1., 0.), (0., 1.)] if theta == 0 else (
        [(0., -1.), (1., 0.)] if theta == 1 else (
        [(0.6, -0.8), (0.8, 0.6)] if theta == 2 else [(-0.8, 0.6), (-0.6, -0.8)]))
    matrix[:3, 3] = [rng.randrange(-100, 100) / 8 for _ in range(3)]
    obj = obstacle(lo, hi)
    transformed = cad._transform_object(obj, matrix)
    exact_points = []
    for point in itertools.product(*zip(lo, hi)):
        transformed_point = [Q.from_float(float(matrix[i, 3])) + sum(
            Q.from_float(float(matrix[i, j])) * point[j] for j in range(3)) for i in range(3)]
        exact_points.append(transformed_point)
        assert all(Q.from_float(float(transformed.bounds[i])) <= transformed_point[i] <=
                   Q.from_float(float(transformed.bounds[i + 3])) for i in range(3))
        corners_checked += 1
    exact_lo = [min(p[i] for p in exact_points) for i in range(3)]
    exact_hi = [max(p[i] for p in exact_points) for i in range(3)]
    for displacement in (0., 100.):
        r = route([displacement, 0., 0., displacement + 1., 1., 1.])
        decision = cad._enclosure_far_from_routes(obj, [r], .01, 1e-6, matrix)
        budget = sum(Q.from_float(float(v)) for v in (.01, 1e-6, r.kernel_tolerance_m))
        if decision:
            assert any(Q.from_float(r.bounds[i]) - exact_hi[i] > budget or
                       exact_lo[i] - Q.from_float(r.bounds[i + 3]) > budget for i in range(3))
        far_checks += 1
    assert cad._enclosure_far_from_routes(obj, [], .01, 1e-6, matrix) is False
    near = route(tuple(transformed.bounds))
    assert cad._enclosure_far_from_routes(obj, [route([100.,100.,100.,101.,101.,101.]), near], .01, 1e-6, matrix) is False

rounding_checks = 0
for n in (-1234567, -1, 0, 1, 1234567):
    for denominator in (3, 7, 10**40, 10**45 + 19):
        points = (Q(n, denominator), Q(n + 1, denominator), Q(n - 1, denominator))
        fast = tuple(enclosure._outward(enclosure._iv(v)) for v in points)
        full = enclosure._apply(enclosure._identity(), points)
        assert fast == full
        for v, interval in zip(points, fast):
            scale = 10**32
            expected_lo = Q((v * scale).numerator // (v * scale).denominator, scale)
            expected_hi = -Q((-v * scale).numerator // (-v * scale).denominator, scale)
            assert (interval.lo, interval.hi) == (expected_lo, expected_hi)
            rounding_checks += 1

guard_results = []
with tempfile.TemporaryDirectory(prefix='oma-hospital-independent-review-') as td:
    path = Path(td) / 'source.ifc'
    model, product = fixture(path)
    raw = path.read_bytes()
    r = route((100., 100., 100., 101., 101., 101.))
    real_load = cad.load_cad
    def disabled(*a, **k):
        raise AssertionError('Far enclosure unexpectedly required native conversion')
    cad.load_cad = disabled
    report = {}
    objects, errors = cad._load_cad_route_obstacles(path, [r], clearance_m=.01, numerical_tolerance_m=1e-6, cache_report=report)
    assert not errors and len(objects) == 1 and objects[0].step_id == product.id()
    assert objects[0].valid is False and objects[0].shape is None
    assert report['lazy_support']['enclosure_only_count'] == 1
    guard_results.append('REAL_PLANAR_IFC_FULL_DENOMINATOR_WITH_NATIVE_DISABLED_PASS')
    marker = ValueError('caller cancellation identity')
    def cancel(stage):
        if stage == 'cad_source_support_product':
            raise marker
    try:
        cad._load_cad_route_obstacles(path, [r], clearance_m=.01, numerical_tolerance_m=1e-6, checkpoint=cancel)
        raise AssertionError('Cancellation swallowed')
    except ValueError as caught:
        assert caught is marker
    guard_results.append('CALLER_EXCEPTION_IDENTITY_PRESERVED')
    def mutate(stage):
        if stage == 'cad_support_source_complete':
            path.write_bytes(raw + b'\n')
    try:
        cad._load_cad_route_obstacles(path, [r], clearance_m=.01, numerical_tolerance_m=1e-6, checkpoint=mutate)
        raise AssertionError('Late source mutation accepted')
    except ValueError as caught:
        assert 'Source bytes changed' in str(caught)
    path.write_bytes(raw)
    guard_results.append('FINAL_CALLBACK_SOURCE_MUTATION_REJECTED')
    cad.load_cad = lambda *a, **k: ([], [])
    # A near route requires exact native subset coverage even with empty output.
    try:
        cad._load_cad_route_obstacles(path, [route((0.,1.,2.,4.,4.,4.))], clearance_m=.01, numerical_tolerance_m=1e-6)
        raise AssertionError('Empty native subset accepted')
    except ValueError as caught:
        assert 'denominator' in str(caught)
    guard_results.append('OMITTED_NATIVE_REFINEMENT_DENOMINATOR_REJECTED')
    cad.load_cad = real_load

result = {'status': 'PASS', 'scope': 'Bounded private numerical/guard review, no Hospital CAD rerun',
          'exact_transformed_corner_memberships': corners_checked, 'far_query_soundness_checks': far_checks,
          'identity_rounding_oracle_checks': rounding_checks, 'guards': guard_results,
          'files': [{'path': p.name, 'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                    for p in sorted(HERE.glob('*.py'))],
          'reviewed_static': ['Raw project-ID cache preserves per-request exact unit lookup',
                              'Reference self-map is exact identity after unchanged anchor prerequisites',
                              'Every near or unsupported product is refined; unrepresented leaf errors force original fallback',
                              'Original final route-source Cartesian pair denominator remains complete'],
          'no_claim': ['approved Hospital alignment', 'installed-service applicability', 'native obstacle clearance result']}
(HERE / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: result[k] for k in ('status', 'exact_transformed_corner_memberships', 'far_query_soundness_checks', 'identity_rounding_oracle_checks', 'guards')}))
