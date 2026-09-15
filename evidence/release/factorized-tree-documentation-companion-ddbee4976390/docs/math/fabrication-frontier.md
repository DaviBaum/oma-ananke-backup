# Exact fitting-count frontier on the finite fabrication graph

`optimization/fabrication_frontier.py` computes a separate nominal cost optimum for each exact number of 90-degree fittings from zero through a declared maximum. An independent checker verifies every reachable count and proves the remaining counts unreachable in that same finite graph. This preserves intermediate choices that a weighted fitting penalty can miss.

The source-bound route proposal pipeline now uses this bounded component when an immutable joint mission supplies a new-fitting budget. The mathematical kernel does not select a simultaneous route set or accept an IFC candidate. The separate actual IFC checker enforces the aggregate resource budget.

## Source and scope

The supplied integration SHA is `72379f535f744b15ccbdcbbb6f68904f6c1177ace27a8fcc028229039b8bd129`. ALG-RTR15 at native paragraphs 5522–5523 requires a finite or explicitly bounded fabrication/size state lift. ALG-RTR22 at paragraphs 5536–5537 requires checked column costs. ALG-RTR26 and ALG-RTR28 at paragraphs 5544–5549 require the complete represented pricing domain and preserve UNKNOWN without closure. ALG-RTR38 at paragraphs 5568–5569 describes independently checking the path, exact cost and potential inequalities.

The exact count coordinate and the rational-only frontier algorithm are a new bounded specialization of those obligations. They do not complete general resource pricing, branch-and-price, physical-fiber closure or continuous topology search. The underlying graph is exactly the existing [fabrication lift](fabrication-lifted-search.md), including its conservative outer-box geometry, straight debt, fixed round section and quarter-circle fittings.

## API and output

```python
compile_fabrication_frontier(problem, objective, max_fittings,
    max_states=24000, max_work=1000000,
    max_certificate_bytes=16 * 1024 * 1024, checkpoint=None)

verify_fabrication_frontier(problem, objective, max_fittings, certificate,
    max_states=24000, max_work=1000000,
    max_certificate_bytes=16 * 1024 * 1024, checkpoint=None)
```

`problem` is the existing `oma.fabrication-grid-problem/1` object, with the same rational/binary-float input semantics, full source identities, context, grid, dimensions, obstacle family and allowed bounds. `objective` is the existing `oma.fabrication-grid-cost/1` object with nonnegative length and fitting weights, at least one positive. `max_fittings` is an exact integer in `[0,32]`; booleans, floats, negative counts and larger domains are invalid inputs.

A complete producer result has status `CERTIFIED`, a rooted input/graph/objective/count domain, `states`, and an ordered `frontier` list containing exactly `max_fittings + 1` entries. Entry k is one of:

* `OPTIMAL_PATH`: `fittings=k`, exact `cost=[a,b]` meaning `a+b*pi`, seven-integer `path_states`, and rational string `points_m`.
* `NO_PATH_AT_EXACT_COUNT`: `fittings=k`, with no cost, states or polyline for that entry.

The latter means no accepting graph walk with **exactly** k turns. It does not mean no path with at most k turns. Counts above the declared maximum are unexamined. The caller may apply an at-most budget to the complete set of independently checked entries, but this module does not compare different counts or choose an aggregate policy.

The verifier returns PASS with all model roots, `counts_checked`, `reachable_counts`, `states_checked`, reconstructed transition count and actual checker work. It does not trust producer work metadata. Exhaustion returns UNKNOWN; no partial frontier is published and no unvisited count is labeled unreachable. A producer UNKNOWN receives no proof authority from the verifier.

## Product graph and exact costs

An ordinary graph state is the existing six-coordinate fabrication state plus a seventh coordinate k. The initial state has k=0. Continuing a straight run leaves k unchanged; an admitted 90-degree turn increases k by one. Transitions beyond the declared maximum are excluded explicitly from this product domain. The initial direction choice is not a fitting.

Let the length weight be wL, fitting weight wF and bend radius R. Every path with exactly k fittings has the same pi coefficient:

`b(k) = wL * R * k / 2`.

The producer therefore minimizes only the rational coefficient on the product graph. It uses nonnegative rational costs:

* Initial direction and straight continuation: zero.
* Turning after completed run length L with prior trim t: `wL * (L - t*R - R) + wF`.
* Accepting at a goal with final run length L and prior trim t: `wL * (L - t*R)`.

The strict graph feasibility checks require every charged straight remainder to exceed the declared minimum, so these costs are nonnegative. The producer runs rational Dijkstra to exhaustion, retaining a minimum rational terminal value at each k. It then restores the fixed coefficient b(k). There is no pi approximation or precision comparison budget in this algorithm; no cross-count symbolic ordering is needed.

The final straight debt is charged even when all graph step costs were zero. Reaching a goal coordinate with insufficient straight remainder is not an accepting terminal. The graph continues to admit outgoing steps after an accepting goal; accordingly the bounded frontier covers the existing graph's walks, including walks that visit the goal and later return. It must not silently substitute a simple-path family. Nonadjacent self-interference is still outside this graph model and is checked during physical realization.

## Independent certificate proof

Each state-table row contains a unique product state, a nonnegative rational potential and a predecessor row index. The first row must be the exact source with zero potential and no predecessor. Every other predecessor index is strictly earlier. The checker independently reconstructs all outgoing fabrication transitions and their count increments, using the graph's checker-side geometry construction rather than the producer transition generator.

It checks that every predecessor relationship is an actual admitted edge. Induction over row order proves every listed state reachable from the source. It also checks that every admitted successor within the count domain occurs in the table. Induction along any finite graph walk proves every reachable state listed. Together these establish the exact reachable-state set, rather than trusting a producer's reachability flag or merely accepting a possibly ungrounded cycle.

For every admitted edge u→v with rational cost a(u,v), the checker verifies

`potential(v) <= potential(u) + a(u,v)`.

For every accepting state u at count k, it verifies

`frontier_cost_rational(k) <= potential(u) + final_straight_cost(u)`.

Since the source potential is zero, summing inequalities along any accepting walk gives the claimed rational frontier value as a lower bound. The checker separately reconstructs each returned path, requires its exact final count and actual terminal, recomputes every cost including terminal debt, and checks that its total equals the claimed value. This supplies the matching upper bound. The fixed pi coefficient is independently derived from wL, R and k, so rational optimality proves nominal a+b*pi optimality at that exact count.

If no listed state accepts at k, complete grounded closure proves that count unreachable. An accepting state at any count without a realizing path, or an omitted successor that might reach another count, invalidates the entire certificate. No stale potential, omitted count or fabricated no-path entry is trusted.

## Budgets and cancellation

The product-state budget is bounded by 100000 states and is checked before adding a newly discovered state. The work budget is bounded by 10000000 units. Costs have a 12000-bit numerator/denominator cap and bounded canonical integer/fraction string encodings. The certificate byte budget is configurable from 1024 bytes to 64 MiB, with a 16 MiB default.

Count and state limits are checked before graph parsing. Proof list lengths, state coordinates, predecessor indexes and cost string shapes are checked before parsing large cost Fractions. A streamed, store-compatible canonical JSON hash verifies the complete byte budget before allocating the verifier's rational labels and adjacency bookkeeping. Producer serialization charges a conservative size estimate before appending output; this can return UNKNOWN even when a less conservatively encoded certificate could fit. Certificate size is not a promise that all intermediate Python allocations fit within that many bytes; state, arithmetic and work budgets separately bound them.

Callbacks run during expansion, closure/path replay, serialization, streamed hashing and final completion. Caller exceptions propagate unchanged, including exceptions with the same class as an internal budget exception. Deterministic certificate contents do not depend on callback behavior when it completes normally.

Adding a count coordinate can multiply the current graph's reachable states substantially. In particular, there is no claim that an eight-value-per-axis application grid fits these defaults for a large count maximum. The adapter must allocate explicit time/state/work limits and retain UNKNOWN if they are exhausted.

Application search callbacks retain every mathematical checkpoint while coalescing ordinary running-state database reads for at most 25 milliseconds. Pauses, step grants, cancellation, terminal states and errors never acquire this cache. Publication, materialization, final proposal results and checking still force a current control read. On one retained synthetic 8-by-8-by-8 graph with count cap two, the same 2,078 states, 4,928 callbacks and complete certificate/check objects took 0.765 seconds with 24 database reads versus 7.610 seconds with 4,928 reads. This is a measured single-graph improvement, not a general performance guarantee. The before/after record is `evidence/benchmarks/joint-fitting-budget/office/script-smoke/9e3cb11a68f640e2a98d86fcba869db7/control-polling-before-after.json`; despite that directory name, this diagnostic is explicitly synthetic. Seventeen control and actual source-adapter publication tests pass on `e3fde02b...` in `evidence/math/joint-fitting-budget/proposal-forced-controls.xml`.

## Evidence and application boundary

`routing/certified_fabrication.build_certified_fabrication_proposals(..., max_fittings=None)` and `routing/proposals.project_proposals(..., max_fittings=None)` preserve the existing priced/feasible proposal behavior and model-root structure when the optional argument is absent. When it is present, the project wrapper requires exact equality with `run.request.mission.max_new_fittings` before yielding a proposal. Its context binds the complete request, base state, route scenario, demand identity where supplied, executable and full budget B. The source adapter independently checks current complete source/frame/outer-support accounting and hashes the original files before and after the work.

The native mission admits B from zero to 1024, while the optional graph frontier represents exact counts from zero through `min(B,32)`. Both full B and that cap enter the graph's source roots. `requested_count_domain_within_kernel_cap` describes this requested range; it is not a closure verdict. Only a PASS from the independent frontier checker proves complete closure of the represented count domain. Counts above 32 remain unexamined when B is larger. No count result becomes a physical impossibility claim.

The default optional frontier phase has 24,000 product states, 1,000,000 work units, the kernel's 16 MiB certificate limit, and at most three seconds or half the remaining overall time, whichever is smaller. It runs after a checked feasible graph path has been retained and before the independent scalar pricing phase. A local timeout or UNKNOWN preserves the feasible/priced fallback without labeling it budget feasible. A global deadline returns no new graph proposals, and caller cancellation propagates unchanged. Source or executable changes discard every new graph proposal. No large-grid closure is promised within these limits.

Each independently checked realizing path is converted to binary64 and freshly passed through the separate fixed-polyline fabrication producer and checker against every retained outer group. The checker must report PASS, the exact same number k of transitions and exactly k+2 polyline vertices. Each output carries `path_certificate_kind=FABRICATION_FRONTIER`, `exact_fittings`, the complete frontier and entry roots, the count-domain root and its own binary64 fabrication proof root. `nominal_exact_count_optimality=true` refers to the exact rational path at that fixed count; `nominal_graph_optimality=false` and `binary64_objective_optimality=false` prevent transferring an unrestricted or rounded-path cost optimum. `shared_native_budget_feasibility=NOT_CHECKED` is explicit.

Outputs retain low counts first, including costlier exact-count optima that unrestricted scalar pricing would omit. At most eight frontier paths are returned by default; the conversion ledger retains the disposition of every represented count, including unreachable counts, failed binary64 correspondence and output-limit omissions. The wrapper's ordinary finite candidate limit can further restrict materialized options. Only one optimum is supplied for each represented count, not all ties or alternative collision-free shapes. Thus neither the adapter nor the eventual Cartesian candidate menu constitutes the complete joint physical route universe. Checked fallback paths may exceed the shared budget and still reach the independent native checker, which alone decides their actual resource compliance.

The initial 71 focused tests include complete cube-walk enumeration through six fittings under nine radius/weight combinations, including repeated-vertex walks; signed straight routes and exact zero-count terminal debt; fitting-only objectives; complete finite cuts; preservation of intermediate count optima; source-grounded reachability and closure attacks; terminal/pi/path/count/root forgeries; byte/state/work limits; producer-independent reconstruction; and callback exception identity throughout both implementations.

An actual analytic IFC wall test independently materializes the k=2 frontier path. It produces five physical parts with exactly two elbows, passes all five route/obstacle pairs and self-interference, passes fresh IFC semantics, and matches the independent exact primitive correspondence check. Original source bytes remain unchanged. The reusable test helper is `native_frontier_wall_case` in `tests/test_optimization_fabrication_frontier.py`; it returns the model, full frontier, independent check, actual native denominator, semantics and correspondence for a separately retained benchmark.

This correspondence result is numerical native geometry evidence for that materialized path. It does not make the whole frontier physically feasible, turn a graph no-path entry into physical infeasibility, or establish a native numeric/continuous objective lower bound. Source/frame authentication, manufacturer catalog validity, gravity/service physics, cross-route capacity and collision selection, and final acceptance remain with their explicit application checkers.

The actual-source adapter regression also starts with an independently loaded analytic IFC wall, retains its complete support denominator, checks the exact two-fitting frontier and binary64 correspondence, then exports five physical parts. Fresh native obstacle/self checks, permitted-zone checks and actual IFC semantics all pass with exactly two elbows. The open-grid source case retains both a more expensive one-fitting option and a cheaper two-fitting option. Additional adapter attacks cover omitted counts, forged paths/no-path entries, changed context/weights/caps, binary64 count mismatches, NaN/bool/oversized inputs, zero and above-cap budgets, output limits, source/build mutation, local/global deadlines and caller exception identity. The scoped test checkpoint is `evidence/release/certified-fabrication-frontier.xml`; reproducible retained source/native evidence is indexed by `evidence/math/fabrication-frontier/latest.json`.
