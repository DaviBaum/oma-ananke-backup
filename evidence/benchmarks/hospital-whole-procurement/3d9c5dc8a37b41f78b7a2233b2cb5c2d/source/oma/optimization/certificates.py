"""Small exact arithmetic certificate checkers with explicit finite scope."""
from fractions import Fraction
from .master import rational


def classify_core_minimality(core_ids, deletion_verdicts, *, core_infeasibility_checked):
    """A001: UNKNOWN deletion evidence cannot prove inclusion-minimality.

    Verdict inputs are outputs of an independent checker, not proposer claims.
    This function classifies their logical consequence; it does not check the
    underlying geometry or infeasibility evidence.
    """
    if not core_infeasibility_checked:
        return "CORE_INFEASIBILITY_UNVERIFIED"
    if not core_ids or len(set(core_ids)) != len(core_ids):
        raise ValueError("Nonempty distinct core premise IDs required")
    if set(deletion_verdicts) - set(core_ids):
        raise ValueError("Deletion result outside core")
    statuses = [deletion_verdicts.get(key, "UNKNOWN") for key in core_ids]
    if any(s not in ("FEASIBLE_CHECKED", "INFEASIBLE_CHECKED", "UNKNOWN", "NOT_RUN") for s in statuses):
        raise ValueError("Unsupported deletion evidence status")
    if any(s == "INFEASIBLE_CHECKED" for s in statuses):
        return "NONMINIMAL_CHECKED"
    if all(s == "FEASIBLE_CHECKED" for s in statuses):
        return "INCLUSION_MINIMAL_CHECKED"
    return "MINIMALITY_UNKNOWN"


def verify_farkas(matrix, rhs, ray):
    """For Ax>=b,x>=0: y>=0, A^T y<=0 and b^T y>0 proves emptiness.

    Scope is exactly the supplied finite matrix. Full routing-master infeasibility
    additionally requires independently checked pricing/domain closure.
    """
    matrix = tuple(tuple(rational(x) for x in row) for row in matrix)
    rhs, ray = tuple(map(rational, rhs)), tuple(map(rational, ray))
    if not matrix or len(matrix) != len(rhs) or len(rhs) != len(ray):
        raise ValueError("Matrix, right-hand-side and ray dimensions disagree")
    columns = len(matrix[0])
    if any(len(row) != columns for row in matrix):
        raise ValueError("Ragged constraint matrix")
    lhs = tuple(sum((matrix[i][j] * ray[i] for i in range(len(matrix))), Fraction(0)) for j in range(columns))
    separation = sum((b * y for b, y in zip(rhs, ray)), Fraction(0))
    valid = all(y >= 0 for y in ray) and all(v <= 0 for v in lhs) and separation > 0
    return {"verdict": "PASS" if valid else "FAIL", "column_products": tuple(str(v) for v in lhs),
            "separation": str(separation), "scope": "SUPPLIED_FINITE_LINEAR_SYSTEM",
            "full_routing_infeasibility": "PRICING_AND_DOMAIN_CLOSURE_REQUIRED"}
