# Finite fabrication-state route search

`optimization/fabrication_search.py` searches a declared finite Cartesian grid with explicit direction, straight-run origin and bend trim debt. It can find a supported route around an obstacle while carrying fitting constraints through the search, or certify that no route exists in this particular conservative graph. It does not close the continuous physical routing universe.

## Source specialization

The supplied integration source SHA is `72379f535f744b15ccbdcbbb6f68904f6c1177ace27a8fcc028229039b8bd129`. DEF-RTR39, native paragraphs 4472-4473, requires incoming direction, bend state and straight run among the fabrication coordinates. DEF-RTR40, paragraphs 4474-4475, adds section/insulation/clearance size state. DEF-RTR41, paragraphs 4476-4484, defines admitted transitions, including bend and minimum-straight compatibility. ALG-RTR15, paragraphs 5522-5523, calls for a finite or bounded lifted graph and an explicit unresolved outcome when its state space exceeds budget. THM-SIR25, paragraphs 1289-1290, supplies the zero-width versus finite-bend counterexample.

The implementation fixes diameter, insulation, bend radius and clearance for one route. It supplies the direction/straight/bend part of the lift; it does not implement manufacturer catalogues, size changes, reducers, support phase, gravity slope, access, service physics, homotopy classification or state dominance.

## Input and API

The complete problem has these keys:

```
schema: "oma.fabrication-grid-problem/1"
context_root: nonempty string
source_roots: nonempty mapping of named source identities
allowed_bounds: [min3, max3]
grid_axes: [x_values, y_values, z_values]
start: point3
goal: point3
diameter_m, insulation_m, bend_radius_m, minimum_straight_m, clearance_m
outer_obstacles: [{id, bounds: [min3, max3]}]
```

Numbers may be finite native numbers or rational strings. Floats mean their exact binary values; derived diameter/2 plus insulation is an exact rational sum. Grid axes are strictly increasing, with at least two entries each and at most 1024 total vertices. Every vertex lies inside the allowed box eroded by the full round radius. Start and goal must be distinct exact grid vertices. At most 256 obstacle boxes are admitted. Structural limits are checked before expensive input traversal. Rational encoding and integer bit limits also bound pathological arithmetic inputs.

`compile_fabrication_search(problem, max_states=12000, max_work=500000, checkpoint=None)` returns a CERTIFIED PATH, a CERTIFIED NO_PATH_IN_DECLARED_GRAPH, or UNKNOWN. A path's `points_m` contains normalized rational strings. It omits collinear intermediate grid vertices, retaining actual corner points and endpoints.

`verify_fabrication_search(problem, certificate, same keyword budgets)` returns proof status PASS, FAIL or UNKNOWN and, for a valid certificate, `geometry_outcome`. Producer and verifier have independent work limits. A callback receives stage strings periodically during construction, expansion and verification; caller exceptions propagate unchanged. Callback presence does not change deterministic certificate contents.

## Exact graph semantics

A state is six integers: current x/y/z grid indices, incoming signed coordinate direction, the run origin index on that direction's axis, and whether the preceding corner consumed a bend trim. A unique initial state has no incoming direction. Every successor advances one adjacent grid step. A continuation retains the run origin and debt. A turn changes to a perpendicular coordinate direction; a U-turn is excluded.

At a quarter turn with radius R, the incoming run must satisfy `length > previous_trim + R + minimum`, where previous_trim is zero for the first run and R otherwise. The new run starts with trim debt R. The goal accepts only when its final run satisfies `length > previous_trim + minimum`. Here minimum is the greater of the declared minimum straight and the exact binary value of 1e-9, matching the supported writer's strict nominal construction convention. Thus short grid steps can accumulate a sufficiently long straight; the search does not require every individual grid edge to fit a complete elbow.

Every untrimmed straight grid edge's finite-cylinder AABB must fit inside the allowed region and have exact squared box distance greater than clearance squared from every declared obstacle outer box. Every turn additionally checks the complete insulated quarter-torus AABB. The producer derives signed coordinate ranges. The independent checker reconstructs attained cap-disk support points. These predicates are sufficient conservative body checks. A failed outer-box predicate means the graph excludes that edge; it does not establish a physical collision.

Joining successive collinear edge boxes covers the complete untrimmed run. The trimmed realized straight is a subset, so it retains the same separation guarantee. The separate turn support check covers the entire bend, including portions away from the unfilleted centreline. Consequently a checked state path realizes the declared fixed round components under the input obstacle-cover assumptions. Nonadjacent component self-interference still needs the native checker.

## Certificate interpretation

A path certificate binds the normalized problem root and graph rule, includes its complete state sequence and compressed polyline, and is checked by independently reconstructing outgoing transitions. The verifier does not call the search or the producer's bound constructors.

A negative certificate contains a unique finite set containing the initial state, closed under every admitted outgoing transition, and containing no accepting goal state. Closure proves absence of a path in the defined graph even when the set contains additional unreachable states. It does not prove continuous infeasibility, homotopy completeness, missing-physics infeasibility or a global objective bound. Breadth-first producer ordering is not exposed as a length-optimality certificate. Work/state exhaustion returns UNKNOWN without a completed cut.

## Physical adapter boundary and evidence

An adapter must authenticate the source identities, complete physical obstacle denominator, source support and coordinate frames. It must not reuse omissions certified for a different radius or centre domain. The current integration design rechecks omissions against the entire allowed body region with clearance, then independently verifies grouping of every remaining support box. Native BRep enclosure assumptions remain explicit. A converted binary64 path receives a fresh nominal fabrication proof before actual IFC materialization, and actual native geometry, clearance, ports, preservation and service checks remain authoritative for candidate acceptance.

The 41-test kernel checkpoint includes a complete small-cube polyline oracle across seven bend radii, strict threshold and two-trim failures, an obstacle inside an otherwise clear unfilleted corner, an obstacle detour, forged paths and closed sets, budget/cancellation checks and independent full-polyline fabrication replay. Native tests materialize actual IFC4 detours in metres and millimetres and independently check all five route/obstacle pairs, self-interference, actual directrices and native primitive correspondence. `scripts/corpus_fabrication_search_benchmark.py` retains these artifacts plus a checked finite-graph cut; it grants no accepted candidate or whole-building claim.
