# Certified cost pricing on the finite fabrication graph

`optimization/fabrication_pricing.py` adds a nominal objective and an independently checked optimum to the existing fixed-size fabrication graph. It returns one optimal path, a checked finite graph cut, or UNKNOWN. It does not prove a lower bound for native numeric geometry, continuous routes, a larger route family or a multi-net resource master.

## Supplied source and specialization

Integration source SHA `72379f535f744b15ccbdcbbb6f68904f6c1177ace27a8fcc028229039b8bd129` binds this reading. ALG-RTR22, native paragraphs 5536–5537, requires cost enclosure as part of independently checking a route column. ALG-RTR26, paragraphs 5544–5545, requires a full represented pricing domain and distinguishes untrusted search from trusted optimality checking. ALG-RTR28, paragraphs 5548–5549, requires pricing closure for every net and preserves UNKNOWN. ALG-RTR38, paragraphs 5568–5569, explicitly describes a path, exact cost and optional potential bound checked through path and dual-edge obligations.

This module implements the finite graph cost and potential component. It does not implement GPU execution, node-dual resource pricing, branch automata, all-net closure, topology-complete pricing or branch-and-price. In particular, a positive nominal route cost is not evidence that every reduced cost in a master is nonnegative. Resource dual terms can create negative edges and invalidate the proof used here; they cannot simply be added to this API.

The graph's source specialization and conservative geometry assumptions remain those in [fabrication-lifted-search.md](fabrication-lifted-search.md). Exact radius, insulated body bounds, straight trim debt, quarter turns and independently reconstructed transitions are unchanged.

## API and rooted inputs

```
compile_fabrication_pricing(problem, objective,
    max_states=12000, max_work=500000, max_pi_terms=256, checkpoint=None)
verify_fabrication_pricing(problem, objective, certificate,
    max_states=12000, max_work=500000, max_pi_terms=256, checkpoint=None)
```

`problem` is the complete `oma.fabrication-grid-problem/1` schema. The exact objective schema is:

```
{
  "schema": "oma.fabrication-grid-cost/1",
  "length_weight": "1",
  "fitting_weight": "1/5"
}
```

Both weights are nonnegative exact rationals and at least one is positive. The first weights nominal component directrix length in metres; the second is a fixed charge per quarter elbow. They do not encode material, installation or service costs unless a caller independently establishes that interpretation. Native floating inputs mean their exact binary values, as in the graph kernel.

A certified result binds normalized input, graph, objective and pricing roots. It contains `geometry_outcome`, `pricing_outcome`, exact string `points_m`, the complete `path_states`, and `cost: [a,b]` meaning **a + bπ**. An `OPTIMAL_PATH` also contains explicit state `potentials` and `default_potential` equal to the terminal cost. A `NO_PATH_IN_DECLARED_GRAPH` has no finite optimum and contains a complete successor-closed set. The certificate root is a content binding, not source authenticity or execution authority.

The independent verifier returns PASS/FAIL/UNKNOWN and the checked outcome, roots and objective. PASS validates the named certificate; it does not grant candidate acceptance. Incomplete producer output never becomes an optimality statement.

## Nonnegative deferred costs

Let R be the fixed bend radius, d the completed straight-run distance, and t either zero or R according to whether its start has a preceding elbow. A continuation or first grid step costs zero. An admitted turn charges

`wL × (d − t − R) + wF + (wL × R/2)π`.

An explicit terminal-sink edge charges `wL × (d − t)`. This sink is separate from merely arriving at the goal coordinate: the final outstanding straight debt must be discharged and charged before comparing completed route objectives.

The graph admits a turn only when `d − t − R > minimum`, and accepts the goal only when `d − t > minimum`. Therefore all edge coefficients are nonnegative. Summing the deferred charges counts every realized straight once and every quarter-circle arc once. For a compressed orthogonal polyline of Manhattan length L with k bends, the objective is

`wL × (L − 2Rk) + wF × k + (wL × Rk/2)π`.

The independent tests compute this whole-polyline expression separately from the edge implementation. Rounded corners shorten a Manhattan polyline, so minimizing length can favor additional turns. On the open 5×5×3 test grid, length-only pricing selects four bends with cost `4+π`; adding a fitting weight of one selects one bend with cost `8+π/4`. Both are independently fabricated and checked in the declared model. Neither objective makes a claim about unmodeled installation preferences.

## Exact comparisons with a precision budget

Costs remain rational coefficient pairs throughout search and verification. Coefficientwise order and identical pairs need no approximation. Other comparisons bound π with Machin's identity

`π = 16 atan(1/5) − 4 atan(1/239)`.

For q>1, consecutive partial sums of the alternating series for `atan(1/q)` enclose its exact value. This follows directly by integrating the finite geometric-series remainder for `1/(1+x²)` over `[0,1/q]`; the remainder has its stated alternating sign and magnitude at most the next term. The underlying arctangent expansion is recorded in the [NIST Digital Library of Mathematical Functions](https://dlmf.nist.gov/4.24.E3), and its computational use is described in [DLMF §4.45](https://dlmf.nist.gov/4.45).

The identity itself can be checked without decimal π: the tangent double-angle formula gives `tan(4 atan(1/5))=120/119`; subtracting `atan(1/239)` gives tangent exactly one. The angle lies between zero and π/2, selecting π/4. The producer uses a power recurrence; the verifier separately sums explicit rational powers and oriented remainder bounds. Stored producer precision metadata is never an authority for a comparison.

When the comparison interval contains zero, the series length doubles up to the caller's limit, at most 512 terms per arctangent. If the sign remains unresolved, the entire producer or verifier returns `UNKNOWN: PI_COMPARISON_PRECISION_BUDGET`; it does not invent a tie. A public regression with fitting weight `97/452`, very close to the length/fitting threshold `1−π/4`, exercises this behavior in the actual graph. No claim of universal termination within a fixed precision budget is made.

## Complete sparse dual proof

The producer runs Dijkstra with exact certified comparisons and stops only when the terminal sink is settled at cost C. It serializes settled ordinary-state labels and uses C as the default potential for every other structurally valid state, including unreachable states. The sink also has potential C. Labels at C need not be expanded for the mathematical default argument; the current producer serializes the ordinary states it actually settled.

The verifier does not run Dijkstra or trust reachability, predecessor distances or settlement order. It checks:

1. The source is an explicit state with potential zero; every explicit potential lies between zero and C.
2. For **every admitted outgoing edge of every explicit state**, including terminal-sink edges, `p(v) ≤ p(u) + cost(u,v)`. Missing explicit successors use the declared default C.
3. The provided path consists entirely of independently admitted transitions, ends at an accepting goal with its sink charge, has the returned polyline, and sums to exactly C.

For any edge whose source is an omitted state, `p(u)=C`; every target has potential at most C and every graph edge cost is nonnegative. Hence its dual inequality holds without enumerating the omitted region. The certificate thus defines a total feasible potential over the entire finite graph. Telescoping inequalities along any source-to-sink path gives cost at least C, while the checked realizing path attains C. This is a complete finite-graph optimum proof, not a frontier heuristic.

The no-path case instead independently checks a unique source-containing, successor-closed set with no accepting goal. It makes no claim about physical infeasibility outside that conservative graph. The producer's tie handling is deterministic for fixed normalized inputs; only one optimum is returned. The checker proves optimal cost, not canonical tie choice or preservation of every human-selectable equal-cost alternative.

## Budgets, trust and actual evidence

Graph input budgets are unchanged. Work and state limits apply to both phases, checkpoint callbacks propagate caller cancellation unchanged, and proof-list lengths are checked before traversal. Proof encoding is limited to 16 MiB. The producer also uses a conservative preallocation bound; the verifier checks the complete bounded canonical encoding before allocating all rational labels. Serialization checkpoints occur every 128 rows/corners and streamed hashing checkpoints every 256 JSON chunks, with a final completion checkpoint. The streamed digest is identical to the store's canonical JSON digest. Rational cost arithmetic is capped at 12000 bits per numerator/denominator; certificate cost strings accept integer/fraction syntax only, so a malicious decimal exponent cannot expand before checking. These are operational limits, not complexity guarantees for arbitrary input arithmetic or native CAD.

The 46 core tests include complete small-cube path ground truth, signed terminal directions, length/fitting tradeoffs, zero-cost edges, a complete audit of the omitted-potential theorem on hundreds of valid states, forged duals and paths, a genuinely admissible but more expensive route, exact precision ambiguity, independent checker isolation and cancellation. A separate agent's adversarial suite checks minimal zero-cost certificates, signed pi labels, untrusted producer metadata and late callback exceptions. One actual IFC4 wall detour is independently materialized and checked for the complete native obstacle-pair denominator, self-interference, actual directrices and primitive symmetric difference. The original source remains unchanged. `scripts/corpus_fabrication_pricing_benchmark.py` retains the proof and separate native evidence; linked XML artifacts record the exact independently run test sets.

An application adapter must authenticate source/frame/outer-cover applicability and bind the objective to the active mission. It must freshly check binary64 conversion, actual fabricated IFC geometry and all native/service/semantic requirements. The exact nominal certificate remains useful proposal and finite-model optimization evidence; an excluded graph edge, failed native candidate or optimal nominal path does not close the larger physical route universe.
