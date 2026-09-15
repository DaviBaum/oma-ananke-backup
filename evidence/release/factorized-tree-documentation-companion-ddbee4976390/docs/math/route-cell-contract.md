# Certified inner and outer route geometry

`oma.optimization.route_cells` implements a bounded specialization of integration DEF-RTR12-24, native paragraphs 4293-4367, and the exact/interval obligations at 4369-4432. The independently reviewed source distinguishes a safe inner embedding from an outer abstraction containing every admissible path. This kernel preserves that distinction.

The geometric body is a closed ball translated along a continuous centre path. Its swept support is a union of capsules. The allowed domain is one rational AABB, eroded by the body radius. Obstacles are described by two distinct, root-bound families:

```
union(occupied inner boxes) subset O subset union(complete outer boxes)
```

An outer BIM enclosure supplies the right inclusion only. It cannot be assumed occupied and used to prove impossibility. Every supplied inner box must fit one named outer box; this checks consistency of the declared bounds, not their authenticity relative to IFC or physical reality. Empty inner families preserve uncertainty. Raw floats mean exact binary values; decimal source rationals should use strings.

## Cell and graph proofs

The three supplied sorted partition axes must cover the entire eroded centre domain, with no gap or duplicate coordinate. Every Cartesian cell is accounted for. Contact with an obstacle clearance threshold is forbidden; contact with the allowed-domain boundary is permitted when the complete ball remains within it.

A FREE cell has a separating-plane witness for every outer obstacle. The checker independently evaluates exact cell upper and obstacle lower support values along the proposed nonzero normal. A positive projected gap with squared gap greater than `(radius + clearance)^2 * norm_squared` proves strict full-cell clearance. The compiler obtains suitable normals from closest AABB coordinates; the checker does not trust that construction.

A BLOCKED cell names one occupied inner box and an occupied-point witness within the radius-plus-clearance ball around each of its eight corners. The Minkowski sum of that one convex box and a closed ball is convex. Containment of every cell vertex therefore proves containment of the entire cell in the forbidden set. Corners covered by different obstacle boxes cannot justify this inference. Every other cell remains MIXED and belongs to the outer relaxation.

Retained outer cells connect whenever their closures intersect, including edge and vertex contact. For this Cartesian partition these are all 26 neighboring index offsets. Any continuous admissible centre path has a connected image covered by finitely many retained closed cells. The intersection graph of the cells meeting that image connects a start cell to a goal cell. Thus an independently verified graph cut rules out every continuous path in the declared model, even though the partition is finite. This is not a claim that a finite inner graph contains every physical path.

An outer PATH is checked directly. An outer CUT contains every retained start cell, contains no retained goal cell, and is closed under every retained neighbor. The checker does not rerun the producer's breadth-first search. A missed adjacency invalidates the cut. An outer path alone proves no feasible physical route.

An inner path is built either from a directly checked segment or through certified FREE cells using shared portal points. Joining diagonal cell centers directly can leave their union, so the producer uses portal points. The independent checker recomputes exact capsule-to-every-outer-box clearance and full allowed-box containment for every emitted segment. No path found means UNKNOWN unless a separately checked outer cut proves model-relative impossibility.

The certificate also carries a universally valid straight-line lower bound on Euclidean centreline length and an interval upper bound on an actual inner path. The verifier checks exact squared-norm inequalities and interval addition. It makes no continuous optimum claim and supplies no upper bound when there is no checked path.

`verify_route_cell_refinement` checks both certificates, unchanged model and applicability identities, retention of every coarse partition boundary, and preservation of coarse FREE/BLOCKED regions in their refined cells. It certifies inner growth and outer contraction for that supplied pair, without proving eventual termination or resolution of all contact boundaries. Changing obstacles or authority is a model change, not refinement.

## API and integration boundary

`compile_route_cells(problem, max_cells=2048, max_work=500000)` emits a candidate certificate. `verify_route_cells(problem, certificate, max_cells=2048, max_work=750000)` independently checks it. Inputs include `allowed_bounds`, `body_radius`, `clearance`, `outer_obstacles`, `inner_obstacles`, `grid_axes`, `start`, `goal`, `context_root`, and `source_roots`. Outer records have `id,bounds`; inner records also name `outer_id`. Source roots are exactly `outer_cover,inner_occupancy,frame,body_model`. Budget exhaustion returns UNKNOWN, and unsupported/malformed producer inputs raise `ValueError`.

The checked geometric outcomes are INNER_PATH_CHECKED, OUTER_INFEASIBLE, or UNKNOWN. These refer only to the stated continuous translating-ball model under the declared obstacle inclusions. They do not authenticate source geometry, coordinate frames or units, and do not check fabrication, elbow shapes, orientation, slope, supports, access or service physics.

For a physical IFC route adapter, an inner path requires a proved containment of every actual component/fitting in the checked swept envelope or its own independent native check. Transferring OUTER_INFEASIBLE requires a necessary body model: enlarging a real route to a conservative outer capsule is suitable for safe-path proofs but is not automatically suitable for impossibility. Exact opening remainder cells certify a declared rational support model; a numerical native equality check cannot silently convert them into unconditional exact inner support of arbitrary native geometry.

## Evidence

Fifty focused tests pass. They cover full-wall impossibility, coarse-grid uncertainty despite a known route, an actual certified detour, diagonal Euclidean clearance, invalid union-of-corner blocking, missing cells and cut edges, changed roots, false length bounds, no compiler/search call in verification, and thirty seeded wall cases with an independent intermediate-value obstruction. Refinement tests distinguish added partition resolution from changed obstacle geometry.

`scripts/corpus_route_cells_benchmark.py` reproduces a rational slab model: one coarse cell remains UNKNOWN; a refined 125-cell model proves the uncut slab blocks every path; four independently certified through-opening remainder cells permit a three-metre capsule path. The edit is explicitly a changed model, while the coarse-to-fine uncut comparison is a checked fixed-model refinement. Artifacts are under `evidence/math/route-cells`. These are exact synthetic ground truths, not a real IFC benchmark.
