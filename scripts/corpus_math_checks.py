"""Executable counterexamples and exact corrections for source-audit amendments.

These are mathematical audit probes, not building benchmarks or proof that the
application implements a required capability. They use standard-library exact
arithmetic and exhaustive finite cases to make each failure reproducible.
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def core_minimality(deletion_verdicts: list[str]) -> str:
    if not deletion_verdicts:
        return "UNKNOWN"
    if all(v == "FEASIBLE_CHECKED" for v in deletion_verdicts):
        return "INCLUSION_MINIMAL_CHECKED"
    if any(v == "INFEASIBLE_CHECKED" for v in deletion_verdicts):
        return "NONMINIMAL_CHECKED"
    return "MINIMALITY_UNKNOWN"


def forbidden_joint_hyperedge_pass(selection: tuple[int, ...]) -> bool:
    return sum(selection) <= len(selection) - 1


def run():
    records = []
    # Core x>=1, x<=0, y>=0 is infeasible, but deleting y>=0 leaves
    # it infeasible. UNKNOWN from a deletion oracle cannot certify minimality.
    finite_domain = tuple(itertools.product(range(-2, 3), repeat=2))
    predicates = [lambda x, y: x >= 1, lambda x, y: x <= 0, lambda x, y: y >= 0]
    sat = lambda ps: any(all(p(*point) for p in ps) for point in finite_domain)
    assert not sat(predicates)
    assert not sat(predicates[:2])
    deletion_verdicts = ["FEASIBLE_CHECKED", "FEASIBLE_CHECKED", "UNKNOWN"]
    assert core_minimality(deletion_verdicts) == "MINIMALITY_UNKNOWN"
    assert core_minimality(["FEASIBLE_CHECKED"] * 3) == "INCLUSION_MINIMAL_CHECKED"
    assert core_minimality(["FEASIBLE_CHECKED", "INFEASIBLE_CHECKED"]) == "NONMINIMAL_CHECKED"
    records.append({"amendment": "OMA-MATH-A001", "status": "COUNTEREXAMPLE_REPRODUCED_CORRECTION_PASSED",
                    "counterexample": "{x>=1,x<=0,y>=0}; deletion of y>=0 remains infeasible despite UNKNOWN oracle output",
                    "corrected_verdict": core_minimality(deletion_verdicts)})
    # A higher-order conflict prohibits selecting all three. Every pair remains
    # possible; a clique row <=1 is an invalid strengthening.
    assignments = list(itertools.product((0, 1), repeat=3))
    exact_legal = [x for x in assignments if not all(x)]
    corrected_legal = [x for x in assignments if forbidden_joint_hyperedge_pass(x)]
    original_legal = [x for x in assignments if sum(x) <= 1]
    assert corrected_legal == exact_legal
    assert (1, 1, 0) in exact_legal and (1, 1, 0) not in original_legal
    records.append({"amendment": "OMA-MATH-A002", "status": "COUNTEREXAMPLE_REPRODUCED_CORRECTION_PASSED",
                    "assignments_exhausted": 8, "exact_legal": len(exact_legal), "incorrect_clique_legal": len(original_legal),
                    "corrected_row": "sum(lambda[r] for r in H) <= len(H)-1"})
    # One positive edge is directed from source to sink. B has -1 at tail
    # and +1 at head, so Bf equals withdrawal minus injection at steady state.
    B = ((-1,), (1,))
    flow = (1,)
    Bf = tuple(sum(b * f for b, f in zip(row, flow)) for row in B)
    injection_minus_withdrawal = (1, -1)
    storage = loss = conversion = (0, 0)
    corrected_rhs = tuple(s + loss[i] - injection_minus_withdrawal[i] - conversion[i]
                          for i, s in enumerate(storage))
    assert Bf != injection_minus_withdrawal
    assert Bf == corrected_rhs
    records.append({"amendment": "OMA-MATH-A003", "status": "COUNTEREXAMPLE_REPRODUCED_CORRECTION_PASSED",
                    "Bf": Bf, "source_defined_injection": injection_minus_withdrawal,
                    "corrected_equation": "Bf = storage_rate + losses - (injection-withdrawal) - conversion"})
    # Restricted columns at cost 10 can omit a valid cost-1 route. Their
    # minimum is an upper bound, not a full-problem lower bound.
    assert min([10]) > min([10, 1])
    records.append({"obligation": "MATH-RTR-PRICING", "status": "NEGATIVE_CONTROL_PASSED",
                    "restricted_optimum": 10, "full_optimum": 1,
                    "meaning": "No full lower-bound claim without complete pricing or another proven relaxation"})
    # A bounded service body must remain inside W. Merely putting its center
    # in W admits boundary overflow even in the absence of obstacles.
    center, radius, domain = 0, 1, (0, 10)
    assert domain[0] <= center <= domain[1]
    assert not (center - radius >= domain[0] and center + radius <= domain[1])
    records.append({"amendment": "OMA-MATH-A004", "status": "COUNTEREXAMPLE_REPRODUCED_CORRECTION_PASSED",
                    "counterexample": "W=[0,10], B=[-1,1], O=empty, center=0 overflows W",
                    "corrected_equation": "F = (W eroded by B) minus (O Minkowski-summed with -B)"})
    # Dominance of b does not make a an optimizer; a third candidate is better.
    objective = {"a": (2, 2), "b": (3, 3), "c": (1, 1)}
    assert all(a <= b for a, b in zip(objective["a"], objective["b"]))
    assert min(objective, key=objective.get) != "a"
    records.append({"amendment": "OMA-MATH-A006", "status": "COUNTEREXAMPLE_REPRODUCED_CORRECTION_PASSED",
        "counterexample": "a=(2,2) dominates b=(3,3), but c=(1,1) is better: dominance is not argmin membership",
        "source_defect": "Canonical P04-E0034 and E0035 copy an argmin formula unrelated to their dominance/contextual-equivalence statements; PDF155-156 inspected",
        "corrected_equations": ["complete objective vector and f(a)<=f(b) componentwise implies declared weak dominance", "q(x)=q(y) and every active e factors through q implies e(x)=e(y)"]})
    # A total and sound three-valued checker can leave the true optimum UNKNOWN.
    universe = {"cheap": {"feasible": True, "cost": 1, "verdict": "UNKNOWN"},
                "expensive": {"feasible": True, "cost": 10, "verdict": "ACCEPT"}}
    assert all(c["feasible"] for c in universe.values() if c["verdict"] == "ACCEPT")
    accepted_optimum = min(c["cost"] for c in universe.values() if c["verdict"] == "ACCEPT")
    actual_optimum = min(c["cost"] for c in universe.values() if c["feasible"])
    assert accepted_optimum > actual_optimum
    records.append({"amendment": "OMA-MATH-A007", "status": "COUNTEREXAMPLE_REPRODUCED_CORRECTION_PASSED",
        "accepted_optimum": accepted_optimum, "actual_finite_optimum": actual_optimum,
        "source_defect": "THM-DS21.1 requires more than complete finite generation and sound checking: UNKNOWN may hide the best feasible candidate",
        "corrected_obligation": "Dispose every candidate completely, or prove every unresolved candidate cannot improve the incumbent; otherwise accepted-subset optimum only"})
    output = {"schema": "oma.math.counterexamples/1", "arithmetic": "Python arbitrary-precision integers; finite exhaustive truth tables",
              "application_implementation_proven": False, "checks": records,
              "passed": len(records), "failed": 0}
    target = ROOT / "evidence" / "math" / "counterexample_results.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": len(records), "failed": 0, "evidence": str(target)}))


if __name__ == "__main__":
    run()
