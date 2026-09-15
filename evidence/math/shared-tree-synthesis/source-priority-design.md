# Next bounded implementation: finite shared-tree synthesis

The next useful step is to generate shared physical tree candidates from a finite tee-and-connector catalogue. Existing pressure checks can evaluate an explicitly supplied unequal two-tee tree; another pressure verifier would not remove the present synthesis bottleneck.

This is a recommendation and independent small oracle, not a completed algorithm. All production and original-source files remain unchanged.

## Directive and original-source basis

The current production directive requires shared trunks and branch topology (lines 641–647), complete physical solids and nonduplicated trunks (673–679), multiple route/topology/configuration candidates (701), and staged corridor → topology → routing → fitting → engineering search (719–721). It explicitly distinguishes a local pathfinder from the complete optimizer (723–725), and permits alternative trunk/branch arrangements (733). This task directly advances those requirements.

The original is `math1/math1/the 5 things that combine ceiling router with ananke.docx`, SHA256 `72379f535f744b15ccbdcbbb6f68904f6c1177ace27a8fcc028229039b8bd129`. Paragraph identities below are native OOXML paragraph ordinals, not reconstructed chapter numbers. The repeated Prompt 2 later in the original is not a second independent source.

| Original body | Exact native paragraphs | Relevant obligation |
|---|---:|---|
| ADD-SIR2.1 | 3787–3806 | Branched carrier is a finite embedded graph, with edge sweeps and actual junction bodies; single centerline notation is insufficient. |
| DEF-RTR39–41 | 4472–4484 | Incoming direction, straight-run, fitting and section state affect admissible transitions and safe dominance. |
| DEF-RTR42–44 | 4487–4513 | Complete terminals, topology, fitting slots and context; Steiner placements require compatible fittings. Unit connectivity flows alone do not establish fitting validity. |
| DEF-RTR45 | 4516–4517 | A shared trunk carries aggregate branch demand. |
| THM-RTR50–53 | 5254–5265 | Realized fittings and compatible edge configurations are essential; general finite multi-terminal pricing contains Steiner Tree; no automatic preference for sharing and no branch-wise trunk sizing. |
| ALG-RTR17–18 | 5526–5529 | Propose connected multi-terminal skeletons, then independently check topology, terminals, embedding, junction degrees and context. |
| ALG-RTR19–22 | 5530–5537 | Compile/check the physical fiber and complete route column after skeleton synthesis. |
| DEF-RTR81 | 4875–4880 | Resource arguments cannot ignore demand reduction or coupling from explicitly modeled shared trunks. |

`evidence/source-excerpts.json` retains the exact source text and per-paragraph hashes. The source register labels RTR17 and RTR18 partial and `full_algorithm_implemented:false`. This extension must keep those full-body flags false.

## Actual gap and compatible consumer

`routing/network_engine.py:33` loops over `scenario.network_alternatives`; the caller supplies every complete tree. `routing/network_scenario.py:290` requires 1–32 such alternatives. `NetworkDesign` already validates complete slot usage, rooted connectivity, terminal paths and section compatibility. `ifc/network.py:18` materializes segments, elbows and tees. `ifc/network_semantics.py:254` measures each unique component once. The independent network checker, managed publication, service proof and finite postchecked selection already consume the resulting full candidates.

The new component should fill the space before that loop. It must generate the connections and source-to-sink paths, rather than merely rename a provided list of trees. Existing fixed, passive-common and unequal-tree hydraulic missions keep their meanings. The freshly integrated unequal adapter is an available downstream consumer, not evidence that all source physical-fiber algorithms are implemented.

## Smallest useful finite universe

Use exactly two or three fixed labelled sinks, one source, one fixed round section and explicit source/sink flow directions. A tee instance is a finite catalogue choice with a placement, one of the 24 proper signed-axis frames, trunk/branch takeouts, exact derived caps, and separate catalogue/loss identities. A connector is one finite directed straight/90-degree-elbow chain between actual caps. It carries exact endpoint directions, section, geometry/fabrication roots and a nominal cost pair `a + b*pi`.

Inputs contain tee instances and individual connectors, never whole trees. A two-sink result uses one tee and three connectors. A three-sink result uses two distinct tee instances and five connectors. For each ordered pair of tees there are twelve labelled binary assignments: choose the root's isolated sink, choose which root outlet feeds the child, then assign the remaining two sinks to the child's named outlets. Outlet labels retain their loss laws when sink assignments change.

The pure kernel checks exact cap positions, forward directions and section equality. The native catalogue adapter must independently establish the relation between each descriptor and its physical geometry. A stored geometry root is an identity, not a proof of geometry. A complete physical connector search is not required for this bounded universe; its omissions remain explicit.

The existing fabrication search has no required initial/final tangent input (`fabrication_search.py:99–117,128–129`). Therefore its cheapest unrestricted route cannot silently stand for all cap-compatible connectors. The first adapter can use a small, endpoint-direction-aware Manhattan template catalogue, independently checking every resulting fillet with the existing fabrication kernel. Root plans exactly representable dyadic coordinates and fresh binary64/native checks; nonrepresentable derived cap geometry is unsupported for that first correspondence contract.

## Kernel and certificate

The planned new API is `compile_shared_tree_catalogue(problem, ..., checkpoint)` and `verify_shared_tree_catalogue(problem, certificate, ..., checkpoint)`. A separate private implementation stage is `.oma/development/shared-tree-synthesis/`. Parent owns a separate native catalogue adapter; neither changes production during the current frozen full suite.

The producer enumerates labelled tee topologies and connector choices. The independent verifier uses directed slot-incidence expansion and reconstructs every reachable full tree, with unique node, port, connector, component and terminal identities. It checks all source-to-sink paths and charges each selected tee and connector once. It does not trust the producer's topology-template enumeration.

A complete certificate contains the full canonical feasible-assignment ledger and a requested ranked prefix. The verifier proves no assignment was omitted and recomputes every cost, then checks prefix ordering. Costs are exact nonnegative coefficient pairs; differences may have opposite signs and require certified pi intervals. Equality means equal coefficient pairs. Unresolved strict comparisons return UNKNOWN. `max_results` only limits output and cannot remove unseen alternatives from the proof denominator.

The certificate proves the nominal order within the exact frozen input catalogue. It does not prove the ranking of actual native objective values, native feasibility, absence of other possible physical connectors/placements, unrestricted Steiner optimality, or continuous closure. Native failure of one tree does not invalidate a connector or another tree using it. Different catalogue words may materialize identical bodies and can consume bounded duplicate work.

Proposed limits bound tee/connector counts, rational bits, input and certificate bytes, enumerated assignments, work and pi precision before expensive allocation. All callbacks propagate caller exceptions. Final input/certificate comparison follows the final callback with no subsequent callback. A work or time limit cannot publish a supposedly complete prefix; already found plans can be retained as diagnostics only until separately checked under an explicitly weaker proposal contract.

## Concrete independent oracle and acceptance experiment

`scripts/assess.py` independently enumerates all 1,024 subsets of ten directed connector records and validates node/port incidence. Exactly two three-sink trees remain. Their correct unique-component nominal costs are `22/5` and `5`; summing demand-path costs gives `25/2` and `8`, reversing the ranking. This is a graph/cost oracle, not a native geometry test. It demonstrates why the new producer must assemble shared networks before cost accounting.

Implementation tests should compare the producer with an independent power-set graph oracle on small randomized catalogues; include all twelve labelled three-sink assignments, multiple connectors per cap pair, missing/duplicate assignments, cycles, reused tees, omitted sinks, swapped b/branch labels, mismatched caps/directions/sections, forged costs/roots, irrational near-ties, output truncation, budget exhaustion and late callback mutations. Verifier tests should disable producer enumeration.

The actual native experiment should freeze caps, placements, section, fitting dimensions and physics before generation. Supply a catalogue with at least two valid assembled trees; an obstacle or independent service check should reject the nominal first choice while the second remains fully accepted. Assert every source pair, self pair, contact, zone, port/connection and applicable service obligation, then acceptance and fresh exported-file verification. All source files remain unchanged. If any required native check is UNKNOWN, the result is not a complete physical finite-universe optimum.

## Deliberately deferred

Larger-terminal Steiner DP, loops/redundancy, section changes/reducers, arbitrary frames, supports/slopes, dynamic geometry, resource dual pricing and certified physical cost lower bounds require separate models and proofs. This first useful synthesis component does not resolve them. Pressure applicability and minimum delivery are checked downstream; topology generation cannot replace those obligations.
