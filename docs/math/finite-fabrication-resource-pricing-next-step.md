# Next resource integration: an explicit joint fitting budget

This is a read-only implementation assessment. No new mission field, resource rule or production pricing module is implemented by this document.

The smallest useful next step is an optional, explicitly requested **maximum number of new fabricated elbows across the independent joint routes**. A generic new resource-toll shortest-path solver would otherwise duplicate capability: the existing exact fabrication pricing kernel already represents a nonnegative per-elbow toll by increasing `fitting_weight`.

## Actual consumer and fixed resource meaning

An optional joint mission field such as `max_new_fittings` would declare a nonnegative integer budget B. Its precise initial meaning should be the number of new 90-degree round elbows in the current independent-route model, summed over newly requested routes only. Existing protected routes are excluded from this incremental budget. Straights do not consume it. Every physical elbow belongs to exactly one new route. Shared trunks, tees, reducers, other fitting types, penetrations and replacement of old fittings remain outside this resource contract.

The independent composite checker can recompute the count from the complete current IFC route component inventory and its already checked primitive/directrix correspondence. It can reject a current candidate whose count exceeds B before the full obstacle scan. A source declaration, path label or nominal proof alone cannot discharge this actual component count. The current request and aggregate mission must bind B, and old requests without this field retain their current meaning.

The joint proposal pipeline can use the same budget to request lower-fitting alternatives from each demand's current bounded graph. Its accepted candidates still require full current native, semantic and service checks, including all cross-route interactions. This is a real consumer of a resource coordinate; it does not invent corridor capacity from geometric proximity.

## The exact bounded mathematical component

Let P_i be the complete walk/path family of the particular finite fabrication graph for new demand i, using the existing source, fitting-state, domain and budget semantics. For a path p, let k_i(p) be its number of turns, and let c_i(p) be the declared nominal objective `length_weight * length(p) + fitting_weight * k_i(p)`. Length and cost remain exact expressions a+b*pi.

For a rational multiplier lambda >= 0, compile each current graph with unchanged length weight and `fitting_weight + lambda`. The existing independently verified pricing result supplies

`q_i(lambda) = min over p in P_i of [c_i(p) + lambda * k_i(p)]`.

The aggregator has a short independent proof. For any represented tuple satisfying `sum k_i <= B`, including any additional collision restrictions,

`sum c_i >= sum q_i(lambda) - lambda * sum k_i >= sum q_i(lambda) - lambda * B`.

Thus `L(lambda) = sum q_i(lambda) - lambda * B` is a lower bound for the **coupled nominal finite-graph family**, even though the per-net pricing ignores cross-route collisions. Those collisions restrict the tuple family; ignoring them is a relaxation. This bound does not cover heuristic routes outside the declared graphs, other graph refinements, different physical fibers, or continuous routes.

In master notation, choose `alpha_i = q_i(lambda)`. Every represented path has reduced cost `c_i(p) + lambda*k_i(p) - alpha_i >= 0`. Subtract alpha once from the completed path value. It is not an edge toll. Nonnegative lambda adds a nonnegative cost at each completed turn, so the existing deferred straight-cost and terminal-cost construction retains nonnegative edges and its sparse potential proof. No negative-cycle machinery is needed for this resource.

The native checker currently measures physical lengths numerically. No numerical length error enclosure has been supplied that would turn this nominal bound into a lower bound for the native measured objective. Reports must therefore distinguish `nominal_graph_resource_lower_bound` from the actual incumbent cost and leave the existing physical `global_lower_bound` and `global_gap` absent. A numerical CAD PASS does not bridge objective semantics. A finite nominal gap is meaningful only if its upper-bound tuple is itself independently certified in exactly the same declared graph/resource/objective family.

## Integration-ready API proposal

Prefer a small adapter and independent aggregator over another path solver:

```
compile_joint_fitting_price(
    demands=[{id, fabrication_problem, nominal_objective}],
    max_new_fittings=B,
    multiplier=lambda,
    context_root=immutable_joint_request_and_sources,
    budgets=..., checkpoint=...)

verify_joint_fitting_price(the_same_inputs, certificate, budgets=..., checkpoint=...)
```

The input binds the complete ordered new-demand denominator, every graph root, original nominal objective, resource definition/version, B, lambda and current context. The producer calls the existing pricing kernel under each independently derived tolled objective. The verifier reconstructs those objectives, replays every graph pricing certificate, independently sums their a+b*pi optima, and subtracts lambda*B exactly. It never trusts a stored numeric minimum or a producer-selected subset of demands.

The output includes the per-demand checked path, exact turn count and original/tolled nominal cost, all graph/objective/certificate roots, the exact lower-bound expression, and an explicit `NOMINAL_FINITE_GRAPH_RESOURCE_RELAXATION` scope. It also returns proposed paths for the ordinary joint materializer. Native acceptance authority is false. Missing pricing closure, time/state/work limits or unresolved exact comparisons produce UNKNOWN for the aggregate bound; independently checked feasible paths may still be retained as proposals. One demand's UNKNOWN must not silently disappear from the sum.

There is a useful special case: independently price every demand with `length_weight=0` and `fitting_weight=1`. These certificates establish exact minimum turn counts. If their sum exceeds B, the budget is impossible in those represented graph families. This is a finite resource cut. It is not a physical IFC or continuous infeasibility result and cannot authorize deleting routes from a larger future graph.

## What this does not solve

One or several multipliers do not solve the integer resource allocation problem. For example, three finite path choices with `(fittings, cost)` equal to `(0,100)`, `(1,60)`, `(2,0)` have a budget-one optimum `(1,60)`, but it minimizes `cost + lambda*fittings` for no lambda: comparison with the first requires lambda<=40, while comparison with the last requires lambda>=60. A toll-guided proposal search can miss the constrained optimum even with exact unrestricted pricing.

If the goal is dependable enumeration under a hard shared budget, the stronger next kernel is an exact per-demand fitting-count frontier, followed by bounded allocation over the complete finite menus. Lift the state by the integer count or provide another independently checked count-constrained path certificate. This can recover unsupported choices that scalarization misses. It costs more states and still needs explicit finite budgets and UNKNOWN. The existing exact master can select among the resulting explicit columns with an additive fitting row, but actual collision cuts need the freshly checked applicability contract; the new hint gate alone does not prove cuts invariant across materializations.

General resource use remains open. A scalar corridor row needs units, capacity authority, exact usage and additive sharing semantics; count or cross-sectional area does not prove packability. Whole-path activation and arbitrary conflict membership are not generally edge additive. They need additional path-language state or a complete finite column scan. Shared-trunk savings invalidate a sum of independent per-route usage unless explicitly represented. General branch and Farkas pricing still require their complete represented domains.

## Source and validation

Supplied integration SHA `72379f535f744b15ccbdcbbb6f68904f6c1177ace27a8fcc028229039b8bd129`, DEF-RTR62–63 at paragraphs 4689–4701, requires physical/resource coordinates and proof modality in a column. DEF-RTR67–75 at paragraphs 4729–4788 fixes the universe, dual signs, additive pricing condition and complete closure. DEF-RTR81 at paragraphs 4875–4880 limits resource cuts to valid additive sharing semantics. ALG-RTR23–28 and ALG-RTR31–33 at paragraphs 5538–5559 retain the master/pricing/branch/Farkas obligations. The proposed elbow coordinate is a bounded application specialization; those bodies do not themselves declare a project's elbow budget.

Existing `optimization/master.py` and its independent checker supply exact finite columns, capacities and dual inequalities. Existing `optimization/fabrication_pricing.py` supplies the tolled a+b*pi path optimum without a new shortest-path algorithm. The missing part is the mission-bound resource consumer and independently checked aggregate, followed by a stronger count frontier if constrained selection is required.

Validation should include two real independently materialized routes whose shorter nominal options use more elbows and whose longer options satisfy the declared joint budget. Check the actual component denominator and complete native route set, not only a synthetic master. Exhaustive small graph/menu oracles must confirm the aggregate bound, including lambda=0, zero fitting budget, unequal graph families, ignored collision restrictions and the unsupported scalarization example above. Adversarial tests must reject omitted/duplicated demands, changed budget/resource meaning, changed original weights, alpha charged per edge, missing terminal debt, stale graph/source roots, false turn counts, negative multipliers and any claimed bound when a per-demand price is UNKNOWN.

Recommendation: implement this only together with the explicit optional mission field, actual component check and joint proposal consumer. If that consumer is deferred, retain the assessment and prioritize the count-constrained frontier instead of adding an unused generic toll primitive.
