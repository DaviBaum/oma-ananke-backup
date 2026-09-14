# Source-bound IFC route-cell proposals

`routing/certified_cells.py` connects the bounded inner/outer cell kernel to freshly read physical IFC support. Its result is a set of geometric path proposals. Each still needs materialization, actual fitting geometry, every native clearance obligation, and the requested service checks before candidate acceptance.

## API and fixed scope

`build_certified_cell_proposals(source_specs, scenario, context_root=..., coordinate_evidence=None, cache_directory=None, grid_divisions=4, max_cells=256, max_work=500000, max_outer_boxes=128, numerical_allowance_m=1e-6, deadline=None, checkpoint=None)` takes the complete baseline source sequence. Each source entry has exactly `path`, `sha256`, and `transform_m`. The caller must bind the context root to the actual baseline, complete source list, fixed scenario and coherent executable.

The result includes `status`, `proposals`, `certificate`, `independent_check`, `model`, `coverage`, `assumptions`, `timing`, source/frame evidence and model/coverage/report roots. `report_root` covers the report before adding its own root and nondeterministic timing field. The complete coverage ledger includes cache/load diagnostics, so its identity describes that execution and is not a canonical geometry-equivalence key.

`CHECKED_GEOMETRIC_PROPOSALS` means at least one freshly checked translating-ball embedding is available. `UNKNOWN` means the declared bounded graph, rounding, work or elapsed-time budget did not produce a checked path. `BLOCKED` records incomplete or mismatched source support. `BLOCKED_NOT_APPLICABLE` is returned for an authorized opening: original host support cannot certify the edited-host model. None of these outcomes asserts physical infeasibility or accepts a fabricated route.

## Source and frame gates

Every source is freshly hashed before loading, after loading, and before proposal publication. Duplicate source hashes are rejected. Single-source local engineering coordinates require the unchanged identity matrix. Multiple sources require a fresh shared-site/building anchor audit with a matching complete source denominator and matrices. Unsupported, missing, reflected or nonrigid frames block. The audit establishes declared local correspondence, not survey accuracy or global geospatial truth.

The adapter independently enumerates every `IfcElement` except `IfcFeatureElementSubtraction`. Every loaded object must have the matching source, STEP and GUID identity and appear exactly once. A representation-free assembly may be accounted through children only when all branches are physical, nonempty, acyclic, and grounded in actually loaded checked support. A space-only, void-only, missing-geometry or cyclic branch cannot disappear from the denominator. All loader failures remain visible blockers.

Native geometry requires valid native topology, finite bounds, a nonnegative finite kernel tolerance and complete represented-body support. A valid native fragment after partial source conversion is insufficient. Alternatively, a freshly rebuilt exact source enclosure must bind the same product, immutable source bytes and source-local metre frame. Invalid native geometry remains invalid when an exact source outer enclosure is used. The source vertex-hull completion interpretation is available only through the scenario's explicit existing policy.

Native boxes are expanded by the object's kernel tolerance plus the declared numerical allowance in source metres. The assumption that native conversion and BRep bounds cover the represented source is explicit. Cached BReps retain the existing local-checker-produced provenance assumption; adjacent hashes and topology revalidation are not proof against a hostile coherent cache replacement. No mesh bounds or stored scalar PASS values provide support authority.

The source box is mapped using exact rational interval arithmetic at the declared binary64 affine coefficients. This gives an exact enclosure of that declared box image. The independent coverage checker verifies every transformed source-box corner lies in the resulting outer box. It does not upgrade numerical frame or native-source assumptions to formal real-world facts.

## Complete finite coverage and paths

Every obstacle is either included in a model group or has a rational separating plane proving strict separation from the complete eroded centre domain by more than body radius plus clearance. The omission checker independently recomputes support extrema and the squared gap inequality. An obstacle is never excluded merely because a display AABB appears far from a sampled route.

Remaining obstacles are deterministically grouped if necessary. Each group's box encloses every assigned complete obstacle box; the checker verifies all members and the complete group denominator. Grouping may obscure a feasible route, so it can produce UNKNOWN. It cannot establish occupied inner support. **The inner-obstacle family is always empty.** No outer-cut result is transferred to physical IFC infeasibility.

The default uniform grid has 64 cells; callers can choose a small bounded refinement. The producer compiles a certificate and the independent kernel verifies every cell and graph witness. Binary64 proposal coordinates are checked again with exact capsule-to-box and allowed-region predicates. Optional orthogonal detours use offsets from the certified path, and their entire new embeddings are independently checked. Their larger physical elbows are not covered by the ball-path certificate.

Kernel work and proposal embedding work have separate bounded budgets. Deadline checks surround source and kernel phases and occur throughout object loading and proposal checks. Native calls are cooperative and may finish after the deadline; a containing worker supplies hard termination. Expiry produces no geometric proposal authority. A change to the loaded geometry dependency files before publication also blocks the result.

## Reproduction

`tests/test_certified_cells.py` covers an actual native IFC wall detour; missing or duplicate objects; wrong source identities; partial native support; nonfinite tolerance; original/hash/frame mismatches; exact planar and explicitly opted-in nonplanar source enclosures; complete assembly grounding; exact grouping and out-of-zone omission; changed model witnesses; two-source audited transforms; and bounded UNKNOWN behavior.

`scripts/corpus_certified_cells_benchmark.py` retains an analytic IFC wall, cell report, materialized detour and separate full native check. It also reopens the immutable Office source from an existing imported baseline and recomputes one explicitly declared scenario with the complete source physical denominator. The historical candidate's acceptance is not reused. Evidence is under `evidence/math/certified-cells`.

The 29 focused tests pass. The retained analytic run checks a 216-cell wall model, then independently materializes and checks the first orthogonal detour: all five physical route-part–wall pairs pass. The Office run reads source `7108485ac8d2856922a83f1353aea8c6eaab60ff393546750bf648200617a544`, accounting for 805 physical records as 803 supported objects and two grounded assemblies, with no blockers. All 803 objects have exact separation proofs from the complete declared local centre domain, so this particular model needs no retained obstacle groups and returns one direct proposal. The final source-bound proposal rerun after the inventory/CAD/cache checkpoint took 16.329 seconds (the earlier pinned run took 16.485 seconds). This is an actual-source local model result, not a difficult-detour performance claim or a whole-project clearance result.

`latest.json` selects the immutable attempt directory and its summary. Each report retains the precise geometry dependency hashes; subsequent implementation changes do not update or re-certify older evidence. An initial benchmark rerun encountered an existing immutable export destination; that aborted cell report is explicitly excluded, and the original analytic source bytes were restored exactly against the retained source SHA. Subsequent runs use unique attempt directories.

The ordinary routing integration in `routing/proposals.py` was independently reviewed. It binds baseline/scenario/executable context, runs the bounded cell method after the direct baseline, preserves candidate/time limits and heuristic fallback, and records proposal roots as diagnostic provenance. The ordinary engine still materializes every selected proposal and invokes its complete independent physical checker; it does not reuse a native PASS or infer physical impossibility from the cell result.
