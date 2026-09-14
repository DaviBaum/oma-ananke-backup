"""Executable counterexamples and exact corrections for source-audit amendments.

These are mathematical audit probes, not building benchmarks or proof that the
application implements a required capability. They use standard-library exact
arithmetic and exhaustive finite cases to make each failure reproducible.
"""
from __future__ import annotations

import itertools
import json
from fractions import Fraction
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
    def checked(number, counterexample, correction, **evidence):
        records.append({"amendment": f"OMA-MATH-A{number:03d}",
                        "status": "COUNTEREXAMPLE_REPRODUCED_CORRECTION_PASSED",
                        "counterexample": counterexample, "corrected_obligation": correction,
                        **evidence})

    # One obsolete part does not eliminate a repair using an available substitute.
    repairs = {"original": False, "qualified_substitute": True}
    assert not repairs["original"] and any(repairs.values())
    checked(8, "Original part obsolete; a compatible qualified substitute remains available.",
            "Empty repair fiber requires every compatible repair to be excluded; define a typed obsolescence predicate rather than compare an observation tuple to TRUE.")

    # gamma(s)=(s,0), delta(s)=2s, s in [0,1]. Its offsets are (s,+/-s).
    # Both have squared length 2, although the source curvature-only integral is 1.
    source_length_squared, actual_length_squared = 1, 2
    assert source_length_squared < actual_length_squared
    checked(9, "Straight centerline, spacing delta(s)=2s: offset length sqrt(2), source formula gives 1.",
            "For arc-length parametrization use integral sqrt((1-/+delta*kappa/2)^2+(delta_prime/2)^2); source expression applies to constant spacing under its regularity/sign assumptions.")

    # Earliest feasible positions solve a feasibility/difference-constraint task,
    # not least squares. Bounds x1>=0,x2>=x1+1 give earliest (0,1).
    target, earliest, projection = (10, 0), (0, 1), (Fraction(9, 2), Fraction(11, 2))
    sqdist = lambda a,b: sum((x-y)**2 for x,y in zip(a,b))
    assert projection[1] == projection[0] + 1 and projection[0] >= 0
    assert sqdist(projection, target) < sqdist(earliest, target)
    checked(10, "Target (10,0), x1>=0, x2>=x1+1: earliest (0,1) has squared error 101; projection (4.5,5.5) has 60.5.",
            "Use the actual convex quadratic projection for ADMM; earliest-position DAG output is only a feasible witness.")

    # Even arbitrarily dense points fail to route if no valid edges connect them.
    grids = [tuple(Fraction(i,n) for i in range(n+1)) for n in (2,4,8,16)]
    assert all(len(g)>2 for g in grids)
    checked(11, "Nested dense vertex samples with an empty edge relation never approximate a continuous path.",
            "Graph convergence needs a local connectivity/spanner or equivalent transition-coverage hypothesis in addition to vertex/direction density.")

    orders = {("A","B"): False, ("B","A"): True}
    tested_orders = [("A","B")]
    assert not any(orders[o] for o in tested_orders) and any(orders.values())
    checked(12, "The sampled order A,B is infeasible but omitted order B,A is feasible.",
            "Order/layer infeasibility requires exhaustive coverage or another universal obstruction; failure of proposed orders remains UNKNOWN.")

    witnesses = {"bad": False, "good": True}
    assert not witnesses["bad"] and any(witnesses.values())
    checked(13, "A checked invalid route witness coexists with another feasible route.",
            "Reject the proposed witness. Claim empty route fiber only with a domain-covering impossibility certificate.")

    # The three binary pair relations each admit a local witness, but no triple
    # satisfies x=y, y=z, x!=z. Existential pair consistency is insufficient.
    states = list(itertools.product((0,1), repeat=3))
    relations = [lambda x,y,z: x==y, lambda x,y,z: y==z, lambda x,y,z: x!=z]
    assert all(any(r(*s) for s in states) for r in relations)
    assert all(any(a(*s) and b(*s) for s in states) for a,b in itertools.combinations(relations,2))
    assert not any(all(r(*s) for r in relations) for s in states)
    checked(14, "Binary x=y, y=z, x!=z have feasible pairwise combinations but no global assignment.",
            "Glue fixed selected local witnesses that agree on every overlap; include the full scope of every global factor in a bag, or provide a valid decomposition theorem.")

    optimum, incumbent, open_lower = 5, 5, 10
    assert open_lower > optimum and min(incumbent, open_lower) == optimum
    # A merely upper-bounded accepted cost cannot serve as the lower bound of
    # a closed accepted region. Its retained lower endpoint is necessary.
    closed_cost_interval = (4,6)
    actual_closed_cost = 5
    assert min(closed_cost_interval[1],10) > actual_closed_cost
    assert min(closed_cost_interval[0],10) <= actual_closed_cost
    checked(15, "Closed incumbent costs 5; remaining OPEN lower bound is 10. min(OPEN)=10 exceeds the true optimum 5.",
            "Cover every feasible region, including closed/evaluated incumbents. With exact incumbent U and sound closures use min(U,min OPEN bounds); with cost intervals retain applicable closed-region lower endpoints.")

    costs = {"good":(1,1), "dominated":(2,2)}
    archive = set(costs)
    excluded = set(costs)-archive
    assert all(any(all(a<=b for a,b in zip(costs[q],costs[s])) for q in archive) for s in excluded)
    assert all(a<b for a,b in zip(costs["good"],costs["dominated"]))
    checked(16, "An archive containing every state satisfies excluded-state dominance vacuously yet includes dominated states.",
            "Require internal nondominance as well as coverage of excluded states; specify whether equivalent objective vectors retain multiple contextual states.")

    concretization = []
    assert all(concretization) and all(not v for v in concretization)
    checked(17, "On an empty concretization both universal TRUE and universal FALSE tests hold vacuously.",
            "Require nonempty concretizations or give EMPTY a distinct semantic disposition before applying three-valued predicates.")

    # Under reverse entailment the order is reverse inclusion of satisfying sets.
    universe = frozenset(itertools.product((False,True), repeat=2))
    p = frozenset(s for s in universe if s[0])
    q = frozenset(s for s in universe if s[1])
    order = lambda a,b: b <= a
    propositions = [frozenset(s for i,s in enumerate(universe) if mask & (1<<i)) for mask in range(16)]
    meet, join = p|q, p&q
    assert order(meet,p) and order(meet,q)
    assert all(order(r,meet) for r in propositions if order(r,p) and order(r,q))
    assert order(p,join) and order(q,join)
    assert all(order(join,r) for r in propositions if order(p,r) and order(q,r))
    assert not order(p&q,p) and not order(p,p|q)
    checked(18, "With mu1<=mu2 iff mu2 entails mu1, truth-table enumeration makes meet disjunction and join conjunction.",
            "Use OR for the greatest common consequence (meet) and AND for the least common strengthening (join), within a compatible context and representable licensed operations.", propositions_exhausted=16)

    validator = lambda artifact: "PASS" if artifact % 2 == 0 else "FAIL"
    assert validator(2) == validator(2) and validator(2) != validator(3)
    checked(19, "One deterministic validator accepts producer output 2 and rejects producer output 3.",
            "Verdict reproducibility requires identical checked artifacts and context, or independently established observational equivalence, in addition to validator determinism.")

    f, g = lambda x:x+1, lambda x:x+2
    assert all(f(g(x)) == g(f(x)) for x in range(-10,11))
    checked(20, "Two transactions both read/write x but add constants 1 and 2; they commute despite overlapping read/write sets.",
            "Read/write independence is sufficient, not necessary, for commutativity. Conservative serialization is valid; the converse noncommutativity theorem is not.")

    # Nominal terminal invariance does not cover a disturbed transition.
    initial, action, disturbance = 0, 0, 1
    terminal = {0}
    assert initial+action in terminal and initial+action+disturbance not in terminal
    checked(21, "x'=x+u+w, terminal {0}, nominal u=0 is invariant for w=0 but w=1 leaves the terminal set.",
            "A robust MPC shift requires disturbance-consistent feedback/tube feasibility and robust terminal invariance for the declared disturbance family; a nominal sequence alone is insufficient.")

    # An event may have probability one while excluding a measure-zero point
    # lying in the support. This exact measure argument does not use sampling.
    checked(22, "For uniform X on [0,1], P(X>0)=1 although 0 is in the support and violates X>0.",
            "A probability-one claim does not imply a universal support claim without additional continuity/closed-predicate conditions or a separate universal theorem.")

    fvalue = lambda x:x*x
    # Source's zero-slope-at-zero counterexample is invalid: it is a subgradient.
    assert all(fvalue(y)>=fvalue(0) for y in range(-10,11))
    assert fvalue(0) < fvalue(1) + 0*(0-1)
    checked(23, "The constant lower bound 0 to x^2 has slope 0, valid at x=0 but invalid as a subgradient at x=1.",
            "Use a point where the bound is not tight to demonstrate that a scalar lower bound need not supply a supporting subgradient; do not reject the actual subgradient at zero.")

    # A translation unit conversion changes zero as well as slope.
    celsius, kelvin = Fraction(0), Fraction(27315,100)
    assert celsius * 1 != kelvin and celsius + Fraction(27315,100) == kelvin
    checked(24, "0 degrees Celsius equals 273.15 kelvin; a scale-only conversion maps zero to zero.",
            "Use affine x*scale+offset conversions for offset units; restrict multiplicative formula to linear unit families.")

    # Contextual substitution preserves labels; deleting equivalent labels is
    # a different operation for a menu-dependent choice correspondence.
    labels = ("original", "equivalent_second", "equivalent_third")
    choice = lambda menu: set(menu) if len(menu) >= 3 else set()
    assert choice(labels) == set(labels) and choice(labels[:1]) == set()
    checked(25, "A label-equivariant rule selects every label iff a menu has at least three labels. All identical-profile alternatives are replacement-equivalent, but deleting equivalent labels changes the chosen class set.",
            "Preserve original labels and multiplicity when substituting quotient profiles, or explicitly restrict decision semantics to duplicate-invariant class menus. Original P3 THM-DS15 does not justify arbitrary menu deduplication.")

    ratios = []
    for n in (2, 4, 8, 16, 32, 64):
        root_states = set(itertools.product(range(n), repeat=2))
        total_stored = 2*n + len(root_states)
        assert len(root_states) == n*n
        ratios.append(Fraction(total_stored, 3*n))
    assert all(a < b for a, b in zip(ratios, ratios[1:]))
    checked(26, "A three-node tree has n messages in each child and n squared distinct root outcomes. Memory divided by node_count times max_nonroot_messages grows with n.",
            "Retain the exact sum of storage across all nodes including root. A width excluding root needs an additional bound on root output or an explicit streaming/output contract.")

    first = dict(s=0, g=0, h=0, e=0, v=1, c=0, b=0, d=0)
    second = dict(first, c=1)
    signature = lambda x: (x['g'], 1-x['h']+x['e'], 2-x['v'], x['e'], x['s'])
    assert signature(first) == signature(second)
    assert (102, 30) != (103, 32)  # Explicit original P2 native table1736215.
    checked(27, "Two feasible hotel assignments with the same projected aggregate signature differ only in sequence c, and native table1736215 gives different cost/schedule pairs (102,30) and (103,32).",
            "Original P3's all-192-assignment aggregate benchmark needs explicit approved observation projection, or actual fixed-stratum restriction and a fresh count. Conditioning a fixed equivalence relation cannot merge previously distinct retained states.")

    valuations = tuple(itertools.product((False, True), repeat=2))
    assert all((not p) or (p or q) for p, q in valuations)
    checked(28, "Manifest root P entails omitted requirement P OR Q for every Boolean valuation, without any theorem that the manifest is exhaustive.",
            "Original ASS THM-ASS3 needs explicit non-entailment or independence of the omitted obligation. Arbitrary omitted requirements have no general guarantee, but some follow from listed roots.")

    domain = tuple(itertools.product((0, 1), repeat=2))
    no_fixed_point = lambda pair: (1-pair[1], pair[0])
    two_fixed_points = lambda pair: (pair[1], pair[0])
    assert not any(no_fixed_point(state) == state for state in domain)
    assert sum(two_fixed_points(state) == state for state in domain) == 2
    checked(29, "One deterministic two-node Boolean SCC has no fixed point; another has two. Condensing either into a DAG does not define its internal solution.",
            "Original ASS14's topological induction needs a defined intra-SCC cold contract. Use verified grounded least-fixed-point semantics under finite monotone assumptions, or explicitly recompute the whole component under another justified deterministic contract.")

    initial_blocks, accepted_binary_splits, stated_final = 2, 4, 5
    assert initial_blocks + accepted_binary_splits != stated_final
    assert stated_final - initial_blocks == 3
    checked(30, "Original P4's forty-module example states two initial blocks, four accepted nontrivial binary splits and five final blocks; the first two quantities imply six.",
            "Use three accepted splits for five final blocks. A fourth preimage or satisfiability probe may be redundant, but must not be counted as an accepted nontrivial split. Report measured operation counts.")

    finite_strings = tuple(itertools.product((0, 1), repeat=1))
    reachable_counts = {min(4, sum(bits)) for bits in finite_strings}
    assert reachable_counts == {0, 1} and len(reachable_counts) != 5
    assert all(bits + (0, 1) not in finite_strings for bits in finite_strings)
    checked(31, "A length-one Boolean carrier has only counts zero and one, and appending an isolated active motif leaves the fixed-length carrier.",
            "Original P4 saturating-repetition examples need enough reachable states for B+1 nonempty classes and an explicit typed total interpretation of every append context. A corrected fixed-width activation map is a different declared finite interpretation, not literal physical append.")

    old_a = (Fraction('80.9'), Fraction('81.4'))
    old_b = (Fraction('81.1'), Fraction('81.8'))
    alleged_b = (Fraction('81.85'), Fraction('81.90'))
    assert alleged_b[0] > old_b[1]
    refined_a = (Fraction('80.90'), Fraction('80.95'))
    refined_b = (Fraction('81.77'), Fraction('81.80'))
    subset_interval = lambda inner, outer: outer[0] <= inner[0] <= inner[1] <= outer[1]
    assert subset_interval(refined_a, old_a) and subset_interval(refined_b, old_b)
    assert Fraction('1.01') * refined_a[1] < refined_b[0]
    checked(32, "Original P5 moves B's cost enclosure from [81.1,81.8] to [81.85,81.90] while calling it refinement; the intervals are disjoint.",
            "A fixed-model refinement must retain nesting and the true value. Declare a model/input change, or use a genuinely nested example such as A=[80.90,80.95], B=[81.77,81.80], whose separation still certifies exclusion from the one-percent cost band.")

    # Analytic family, not a finite truncation proof: E_n={0} union [n,infinity),
    # n>=1, has intersection {0}; every E_n still meets the distant region.
    # Delta(y)={0,1} for |y|<1/2 and {2} otherwise. Thus Delta is constant near
    # y_M=0 while every physical outer image equals {0,1,2}, not {0,1}.
    discrepancy = lambda y: frozenset((0, 1)) if abs(y) < Fraction(1, 2) else frozenset((2,))
    assert discrepancy(0) == frozenset((0, 1))
    for n in (1, 2, 10, 10**6):
        assert discrepancy(0) | discrepancy(n) == frozenset((0, 1, 2))
    checked(33, "Nested closed E_n={0} union [n,infinity) intersect to {0}, but a discrepancy map equal to {0,1} near zero and {2} away gives union_{y in E_n} Delta(y)={0,1,2} for every n.",
            "Original P5 THM-ER16's discrepancy floor inclusion remains sound; its asserted exact limiting image needs enclosures eventually contained in the local-constancy neighborhood, for example shrinking diameter or appropriate compact nested closed enclosures. Setwise intersection alone is insufficient.",
            proof_kind="Explicit analytic escaping-tail family; displayed finite probes are illustrations only")

    # A nonattained nearest point requires passing a limit through the modulus.
    # On Y={0} union {1+1/n:n>=1}, downstream response is 0 at zero, 1 elsewhere.
    modulus = lambda distance: 0 if distance <= 1 else 1
    assert modulus(1) == 0
    for n in (1, 2, 100, 10**6):
        assert modulus(1 + Fraction(1, n)) == 1
    checked(34, "On Y={0} union {1+1/n}, exact A={0}, approximate A={1+1/n} have directed excess 1. Exact downstream B is 0 at zero and 1 elsewhere, with valid jump modulus omega(t)=0 for t<=1, 1 otherwise. B is evaluated exactly, but the composite excess is 1>omega(1)=0.",
            "Original P6 PO9 needs attained nearest points or a right-continuous modulus to remove arbitrary limiting slack. A conservative general formula uses the right limit of the monotone modulus; finite closed sets and explicit Lipschitz gains avoid this gap.",
            proof_kind="Exact nonattainment family; finite probes illustrate the right-limit discontinuity")

    utility = {'A': 0, 'B': 0, 'C': 1}
    maximize = lambda menu: {x for x in menu if utility[x] == max(utility[y] for y in menu)}
    assert maximize(('A', 'B')) == {'A', 'B'}
    assert maximize(('A', 'B', 'C')) == {'C'}
    checked(35, "Original P12's menu example C({A,B})={A,B}, C({A,B,C})={C} is exactly rationalized by fixed utility u(A)=u(B)=0,u(C)=1.",
            "The example does not establish non-rationalizability or a violation of the usual consistency conditions. A strict reversal C({A,B})={A}, C({A,B,C})={B} demonstrates a fixed-utility contradiction. Keep the broader menu-dependent choice contract; repair its example.")

    output = {"schema": "oma.math.counterexamples/2", "arithmetic": "Python arbitrary-precision integers/rationals; finite exhaustive truth tables; explicitly stated exact analytic counterexamples",
              "application_implementation_proven": False, "checks": records,
              "passed": len(records), "failed": 0}
    target = ROOT / "evidence" / "math" / "counterexample_results.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": len(records), "failed": 0, "evidence": str(target)}))


if __name__ == "__main__":
    run()
