# Source-aware bounded fabrication grid enrichment

`routing/fabrication_grid.py` proposes exact additional grid coordinates from the supplied complete retained outer-box family and optional fitting dimensions. It preserves every baseline coordinate and terminal. Its independent checker establishes coordinate provenance, the full source-plane denominator, baseline retention and budgets. Neither the proposal nor its checker proves free space, physical feasibility, a complete continuous route family or native acceptance.

## Source and algorithm boundary

The supplied integration source SHA is `72379f535f744b15ccbdcbbb6f68904f6c1177ace27a8fcc028229039b8bd129`. ALG-RTR15, native paragraphs 5522–5523, requires finite or explicitly bounded fabrication/size states; ALG-RTR16, paragraphs 5524–5525, distinguishes checked finite-graph paths from physical infeasibility. ALG-RTR27, paragraphs 5546–5547, permits budgeted heuristic candidates without closure. These are the relevant implementation boundaries.

The coordinate construction here is a new bounded heuristic specialization, not an algorithm explicitly supplied in those bodies. It is not ALG-RTR10's complete inner/outer CEGAR refinement: no exact spurious counterexample, complete outer abstraction or continuous refinement theorem is claimed. Every proposed path still passes through the existing exact graph, independent path/pricing checker, converted binary64 fabrication checker and actual native/semantic/service checks.

## API

```
enrich_fabrication_grid(base_axes, start, goal, allowed_bounds,
    outer_obstacles, radius_m, clearance_m,
    guard_m="1/1000000", bend_radius_m=None, minimum_straight_m=None,
    max_vertices=1024, max_axis_values=10, max_work=100000, checkpoint=None)

verify_fabrication_grid_enrichment(same positional inputs, result,
    same keyword parameters)
```

The supplied radius is the exact full round body radius, diameter/2 plus insulation. All inputs have the rational/binary-float convention used by the fabrication graph. The baseline must already contain the distinct exact terminals and fit inside the supplied allowed body box eroded by that radius. The routine does not change allowed bounds or silently discard an oversized baseline. Source boxes must be a complete explicit list with unique bounded identities; support authenticity and frame applicability belong to the caller.

A `PROPOSED_GRID` returns exact string `grid_axes`, normalized `input`, `input_root`, full `plane_records`, baseline/proposed vertex counts, limitations and `result_root`. A budgeted UNKNOWN returns no replacement axes. The verifier returns PASS/FAIL/UNKNOWN; PASS includes `baseline_preserved`, `source_planes_accounted`, `proposed_vertices` and the exact input/result roots. PASS means this coordinate proposal is justified, not that a route exists.

## Coordinates and deterministic allocation

For every box and axis, two source planes are proposed:

* Lower face minus `radius + clearance + guard`.
* Upper face plus `radius + clearance + guard`.

If bend radius R and minimum straight s are provided together, each terminal and signed axis also proposes distances `R + max(s, exact_binary(1e-9)) + guard` and `2R + max(s, exact_binary(1e-9)) + guard`. These generic first-turn and two-trim seeds help avoid grids whose apparent detours are too close to pay the fitting's straight debt. They do not assert that the rest of a route can realize those dimensions.

The positive guard is a declared search offset. It is not an estimated or certified CAD error bound. A caller can separately shrink the permitted body box to encourage proposals away from a native boundary; the current application uses a 100 micrometre body-box search inset. That leaves the original mission unchanged and still requires independent native containment. Source outer boxes already carry their own explicitly scoped enclosure assumptions.

First-turn seeds rank before obstacle-face seeds; two-trim seeds rank afterward. Obstacle candidates rank by exact squared distance from their source box to the source–goal coordinate bounding box, then by coordinate distance to the terminal span, source identity and side. This is a heuristic priority, not a collision test. Coordinates outside the eroded allowed region are recorded but not added; existing and duplicate coordinates are retained once with complete provenance.

Allocation repeatedly considers the least-populated axis with pending candidates. The default per-axis cap of ten limits the full three-dimensional grid to at most 1000 vertices and avoids filling one axis while starving the others. Custom tighter product limits remain enforced, with skipped candidates explicitly marked. The independent verifier checks budget reasons against the final monotone coordinate sets; it does not claim the producer's ranking is uniquely optimal or canonical. Axis-permutation tests cover the default allocation; exact symmetry under an asymmetric custom final-slot tie is not asserted.

The application now supplies a tighter cap of eight when its preserved baseline permits it. This bounds the grid by 512 vertices. For axis counts n1,n2,n3 and V vertices, the lifted graph has at most `V × sum(ni−1) + sum(ni−1) + 1` ordinary structural states: one directed trimmed-run state per distinct run-origin coordinate, plus initial untrimmed rays and the source. At 8×8×8, that is 10774 states, or 10775 including the pricing sink, below the existing 12000-state budget. This counts possible states; it does not guarantee completion within a time, work or precision limit.

Every added coordinate has exactly one addition witness. All other occurrences are recorded as retained duplicates. The checker separately reconstructs both box-face formulas and terminal trim formulas and verifies every expected source-plane identity exactly once. It rejects deleted baseline points, invented coordinates, shifted planes, fake budget exhaustion, duplicate additions and altered roots/scope. Callback exceptions propagate unchanged; state/work limits and bounded source/list/rational inputs prevent unbounded enumeration.

## Evidence and interpretation

The initial 27 focused tests include exact face offsets and trim thresholds, six axis permutations, balanced and tight allocation budgets, duplicate source coverage, root-preserving forgeries, cancellation and producer-independent verification. The Office evidence uses a retained, explicitly historical source-support model plus freshly hashed original IFC and newly materialized native checks. `scripts/corpus_fabrication_grid_benchmark.py` retains the baseline and enriched finite pricing certificates, source artifact identities, binary64 proof, native pair denominator, native whole-shape zone witness and actual primitive correspondence.

The routine contains no building names, IDs or benchmark-specific coordinate exceptions. In the retained Office model, an old uniform detour coordinate was only 0.345 metres from a terminal, while its fixed bend plus straight required more than 0.35 metres. Nearby obstacle-face coordinates alone were even closer. Generic first-turn threshold seeds resolve that sampling gap. Any improvement is a result for that finite declared model and separately checked native proposal; it does not establish continuous optimality or close missing source physics.

The fresh Office probe passed all 4015 native route/obstacle pairs against 803 physical obstacles, self-interference, whole-shape native zone containment and actual semantics. On the 100 micrometre guarded domain its uniform-grid nominal optimum was approximately 2.256278 metres; enrichment produced approximately 2.096480 metres. Cap eight retained the same path as cap ten; its measured pricing and independent verification together took about 0.16 seconds on this machine. An independent analytic-wall adapter probe at 8×8×8 used 5621 explicit potential states and completed its optional pricing phase in about 2.33 seconds, within the six-second phase budget. These are observed local timings, not worst-case guarantees. All old failed or less efficient attempts remain separate evidence.
