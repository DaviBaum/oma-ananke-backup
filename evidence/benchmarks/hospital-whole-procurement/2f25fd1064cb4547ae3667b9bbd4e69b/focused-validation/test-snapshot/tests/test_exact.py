from fractions import Fraction as F
import random
import pytest

from oma.exact import (orient2d, orient3d, segment_segment_distance_squared,
    segment_triangle_intersection, segment_box_distance_squared, capsule_box_clearance, capsule_within_box)


def test_orientations_arbitrary_precision_and_degenerate_zero():
    n = 10**80
    assert orient2d((0, 0), (n, 0), (0, n)) == n*n
    assert orient3d((0, 0, 0), (n, 0, 0), (0, n, 0), (0, 0, n)) == n**3
    assert orient3d((0, 0, 0), (n, 0, 0), (0, n, 0), (n, n, 0)) == 0


@pytest.mark.parametrize("start,end,expected", [
    ((0, 0, -1), (0, 0, 1), "CONTACT"),
    ((2, 2, -1), (2, 2, 1), "NONE"),
    ((-2, 0, 0), (2, 0, 0), "COPLANAR_CONTACT"),
    ((2, 2, 0), (3, 3, 0), "NONE"),
    ((0, 0, 1), (1, 0, 1), "NONE"),
])
def test_triangle_intersections_with_coplanar_cases(start, end, expected):
    triangle = ((-1, -1, 0), (1, -1, 0), (0, 1, 0))
    assert segment_triangle_intersection(start, end, *triangle)["status"] == expected


def test_degenerate_triangle_and_point_segment():
    assert segment_triangle_intersection((1, -1, 0), (1, 1, 0), (0, 0, 0), (1, 0, 0), (2, 0, 0))["status"] == "COPLANAR_CONTACT"
    assert segment_segment_distance_squared((0, 0, 0), (0, 0, 0), (1, 0, 0), (1, 0, 0))["distance_squared"] == 1
    assert segment_segment_distance_squared((0, 0, 0), (1, 0, 0), (0, 1, 1), (0, 1, -1))["distance_squared"] == 1


def test_segment_box_containment_and_thin_obstacle():
    box = ((0, 0, 0), (1, 1, 1))
    assert segment_box_distance_squared((F(1, 4), F(1, 4), F(1, 4)), (F(3, 4), F(3, 4), F(3, 4)), *box)["distance_squared"] == 0
    assert segment_box_distance_squared((-1, F(1, 2), F(1, 2)), (2, F(1, 2), F(1, 2)), (0, 0, 0), (F(1, 10**40), 1, 1))["distance_squared"] == 0


def test_exact_clearance_contact_and_legal_negative_control():
    args = ((-1, 2, F(1, 2)), (2, 2, F(1, 2)), 1, (0, 0, 0), (1, 1, 1))
    assert capsule_box_clearance(*args)["verdict"] == "FAIL"
    assert capsule_box_clearance(*args, contact_allowed=True)["relation"] == "CONTACT"
    assert capsule_box_clearance(*args, contact_allowed=True)["verdict"] == "PASS"
    assert capsule_box_clearance(args[0], args[1], 1 + F(1, 10**40), args[3], args[4], contact_allowed=True)["verdict"] == "FAIL"
    assert capsule_box_clearance(args[0], args[1], 1 - F(1, 10**40), args[3], args[4])["verdict"] == "PASS"
    contained = capsule_box_clearance((F(1, 2), F(1, 2), F(1, 2)), (F(1, 2), F(1, 2), F(1, 2)), 0, (0, 0, 0), (1, 1, 1), contact_allowed=True)
    assert contained["relation"] == "OVERLAP" and contained["verdict"] == "FAIL"


def test_exact_box_distance_symmetry_and_dense_rational_upper_samples():
    rng = random.Random(10291)
    for _ in range(30):
        a, b = [tuple(rng.randint(-4, 4) for _ in range(3)) for _ in range(2)]
        result = segment_box_distance_squared(a, b, (0, 0, 0), (1, 1, 1))
        assert result["distance_squared"] == segment_box_distance_squared(b, a, (0, 0, 0), (1, 1, 1))["distance_squared"]
        for t in [F(k, 20) for k in range(21)]:
            p = tuple(a[i] + t * (b[i] - a[i]) for i in range(3))
            sampled = sum((max(0, -v, v - 1)**2 for v in p), F(0))
            assert result["distance_squared"] <= sampled


def test_nonfinite_and_invalid_box_rejected():
    with pytest.raises(ValueError):
        orient2d((float("nan"), 0), (0, 0), (1, 1))
    with pytest.raises(ValueError):
        segment_box_distance_squared((0, 0, 0), (1, 1, 1), (1, 1, 1), (0, 0, 0))


def test_allowed_region_is_eroded_by_entire_body():
    assert capsule_within_box((0, 5, 5), (5, 5, 5), 1, (0, 0, 0), (10, 10, 10))["verdict"] == "FAIL"
    assert capsule_within_box((1, 5, 5), (9, 5, 5), 1, (0, 0, 0), (10, 10, 10))["verdict"] == "PASS"
    assert capsule_within_box((1, 5, 5), (9, 5, 5), 1, (0, 0, 0), (10, 10, 10), contact_allowed=False)["verdict"] == "FAIL"
