# Finite shared-tree catalogue synthesis

This component generates complete two- and three-sink tree assignments from individual tee instances and connector options. It does not take a list of complete networks. It proves exact cap/section compatibility, rooted slot incidence, complete terminal paths, unique nominal component accounting and a ranked prefix in the entire declared finite catalogue.

The module is `oma.optimization.shared_tree_synthesis`. Its producer and independent verifier are `compile_shared_tree_catalogue` and `verify_shared_tree_catalogue`. Both use only the Python standard library and exact rationals. The implementation is private; no production source or original mathematical document was changed.

## Source and scope

Original: `math1/math1/the 5 things that combine ceiling router with ananke.docx`, SHA256 `72379f535f744b15ccbdcbbb6f68904f6c1177ace27a8fcc028229039b8bd129`.

The native paragraphs are ADD-SIR2.1 3787–3806 (branched carrier, edge sweeps and actual junctions), DEF-RTR39–44 4472–4513 (fitting/section states, connected terminal-spanning skeletons, allowed placements and fittings), DEF-RTR45 4516–4517 (aggregate shared-trunk flow), THM-RTR50–53 5254–5265 (physical junction compatibility, general Steiner complexity, sharing and trunk sizing), and ALG-RTR17–22 5526–5537 (multi-terminal proposal, independent skeleton check, physical fiber and route-column checks).

This is one bounded implementation component of ALG-RTR17/18. The source algorithms' full-body completion flags remain false. The topology certificate alone does not discharge geometry, physics, supports, slope, sizing, homotopy or complete route-column obligations.

## Input model

The exact JSON schema is `oma.shared-tree-catalogue/1`:

```text
context_root: SHA256
source_roots: nonempty map of named SHA256 identities
cost_policy_root: SHA256
section: {diameter_m: positive rational string, insulation_m: nonnegative rational string}
source: {id, cap}
sinks: [{id, demand_id, cap}]                  # exactly 2 or 3
tee_instances: [{id, catalogue_root, loss_contract_root,
  center_m, axis_x, axis_y, trunk_takeout_m, branch_takeout_m,
  nominal_cost: [a,b]}]
connectors: [{id, from: {node,port}, to: {node,port}, start_cap, end_cap,
  section, geometry_root, fabrication_root, nominal_cost: [a,b]}]
cap: {position_m: [rational string,rational string,rational string],
      flow_direction: [strict integer,strict integer,strict integer]}
```

All node IDs are globally unique bounded ASCII identifiers. Connector IDs are unique in their own inventory. Sink demand IDs are distinct. SHA256 strings are lowercase hexadecimal. Cost coefficients `a,b` are nonnegative rational strings and mean `a + b*pi` under the bound nominal cost policy. They are not measured native costs.

`axis_x`, `axis_y` and flow directions are signed coordinate unit vectors. Tee axes are orthogonal, yielding one of the 24 proper frames when the third axis is their cross product. Takeouts exceed the complete nominal outer radius. The derived caps are:

* `a`: center minus trunk takeout along x; forward flow direction x;
* `b`: center plus trunk takeout along x; forward flow direction x;
* `branch`: center plus branch takeout along y; forward flow direction y.

The source port is `out`, sink ports are `in`. Every connector must go source→tee.a, tee.outlet→tee.a, or tee.outlet→sink. Exact endpoint positions, forward directions and section must match the declared or derived caps. Forward directions on the two sides of a contact agree; their outward surface normals point oppositely. Self-connected connector records are rejected. Multiple distinct connector records for the same directed cap pair are allowed.

The input contains the complete declared catalogue, including unused options. An empty or insufficient catalogue can have zero complete assignments. This is a statement about that catalogue only. Geometry/fabrication/catalogue/loss roots bind identities; their physical validity and their relationship to current native geometry remain external assumptions requiring independent replay by the adapter.

## Producer and independent coverage proof

With n sinks, every supported rooted full binary tee tree has n−1 tees and 2n−1 connector macros. Every selected tee uses exactly one `a` input and both named outputs; every sink is a leaf; no connector joins an existing tee or sink a second time.

For two sinks, the producer tries each tee and both labelled outlet assignments. For three sinks it tries every ordered pair of distinct tees, chooses the root outlet feeding the child, and permutes the three sink labels. This is twelve templates per ordered tee pair. For each template it enumerates the full product of available connector options for all required cap pairs. An empty required pair makes only that template empty.

The verifier does not call that template generator. It starts with the source output as an open slot and independently follows every outgoing connector. Reaching an unused tee adds its two output slots; reaching an unused sink closes one slot. Reusing a tee/sink is disallowed. A completed branch of this search must contain all required sinks and exactly n−1 tees. Each expansion adds an unused node, so it is rooted and acyclic, and every physical port is accounted for.

Conversely, take any tree in the declared directed catalogue satisfying those rules. Starting at its source, the verifier has the connector chosen by that tree available at each open slot. Its unique-parent and acyclic properties prevent every reuse rejection; it therefore reaches the same complete assignment. The producer's one/two-tee template enumeration covers the same class by the full-binary-tree count and the unique root/child structure for at most three leaves. This establishes complete finite coverage, without a Steiner or continuous-domain claim.

The certificate includes every feasible assignment, canonically ordered by its sorted connector IDs. Each row contains `tee_ids`, `connector_ids`, the exact summed `nominal_cost`, and an `assignment_root` bound to the normalized problem. The verifier reconstructs its own complete ledger and checks exact equality. Omissions, duplicates, altered costs, altered assignments and stale roots all fail.

## Ranked prefix and accounting

Each selected tee and connector contributes its nominal cost exactly once. Source-to-sink paths may contain the same trunk connector; summing those path costs would double-charge shared components and can reverse the ranking. The independent toy oracle retained in the design evidence demonstrates that reversal with costs `22/5 < 5` but incorrect path sums `25/2 > 8`.

The verifier recomputes the complete nominal order. Equal coefficient pairs tie and use canonical connector-ID order. For unequal pairs, coefficientwise signs may decide; otherwise separate producer/checker Machin-series rational pi enclosures establish a strict sign. An unresolved comparison returns UNKNOWN. No midpoint or approximate tie is used.

`max_results` limits the returned prefix, not the finite universe. All assignments are still checked. The certificate binds the requested prefix size; verification must use the same `max_results`. A fully enumerated empty catalogue is certified with an empty prefix, without a physical infeasibility claim. A truncated or budget-exhausted enumeration publishes no certified prefix.

## Results, controls and limits

Successful production returns `status:CERTIFIED`, `proof_complete:true`, `certificate`, `certificate_root`, raw `input_root`, normalized `problem_root`, `proposals`, `counts`, `scope` and `work`. Verification returns `status:PASS` with independently reconstructed proposals and the same roots/scope. A proposal has assignment IDs/cost, the source endpoint, every sink/demand endpoint and connector path, plus the complete selected connector incidence list.

Invalid input gives producer `INVALID_INPUT`; forged/invalid proof gives verifier `FAIL`. Supported resource exhaustion gives `UNKNOWN`. Every non-success has an empty proposal list and `proof_complete:false`. Caller callback exceptions propagate with the original exception object, including exceptions sharing the module's exhaustion class.

Defaults are 16 tee instances, 256 connectors, 100,000 complete assignments, 32 returned proposals, 2,000,000 counted work units, 16 MiB per input/certificate JSON, 4,096-bit rational arithmetic and 128 terms per Machin arctangent. Explicit supported maxima are checked strictly; booleans are not integers. Defaults are ceilings, not promises that every domain beneath each individual ceiling can finish under all the other budgets.

Shape checks precede copies, and captured shapes are checked again after callbacks. Strict bounded JSON copying/hash accounting precedes rational parsing. Complete certificate byte accounting includes its own digest field. Final callbacks precede final current-input/proof hashing with no further callbacks. Work includes these tails. This is a cooperative in-memory binding guard, not an atomic cross-thread/filesystem transaction or native runtime guarantee.

## Native consumer boundary

The parent-owned native adapter constructs endpoint-direction-aware Manhattan connector options, checks supported finite fillets, calculates each nominal cost from the actual declared macro and binds its complete descriptors. It turns checked assignments into complete `NetworkDesign` objects, materializes actual IFC, and runs the full existing native/service/managed-publication pipeline. Original missions retain their meanings.

The first adapter restricts nominal catalogue arithmetic to exactly representable dyadic coordinates for its promised nominal/native correspondence. This kernel also accepts general rational cap data but grants no binary64 or native equality to them. Per-outlet tee loss identities must remain attached to `b` and `branch` when sink assignments change. Shared flows and every applicable delivery/velocity/pressure obligation are downstream checks.

Native failure of one tree cannot be transferred to a connector, prefix or another assignment. Passing only the nominal best tree is insufficient when another native-feasible same-catalogue assignment may be better than the surviving checked set. Full physical finite-universe optimality requires every relevant native disposition or a separately justified bound; this component supplies neither. No unchanged native PASS is reused.

## Retained validation

Frozen component source root: `d1245404a41acadc38880a45a584757654c867aeb15971d7260cccf817551cb7`. This identifies only the new module snapshot, not a complete OMA executable. Module SHA256: `0034130d057fbb012d031fb31a69ce89aac857ce6aeaf4d8a73f55c2d1a23d43`.

The exact frozen suite passed 85 tests with zero skips/failures/errors in receipt `validation/b65849341dc342fda724bf4ec9cd67e8`. The module, test and four portable fixture files were hashed before and after. Coverage includes independent choose-edge graph oracles, sparse catalogues, all 24 signed tee frames, all labelled three-sink assignments, multiple connector alternatives, false ledger/ranking/cap/section/root witnesses, near-pi ordering, exact work/byte limits, pre-parser resource checks, final callback mutation and disabled-producer verification.

An independent peer's native catalogue contains two two-sink assignments and three three-sink assignments. The kernel's cost order and complete connector paths match its independently enumerated oracle. That peer separately materialized all five complete trees: the planted-obstacle alternatives B and BC failed source clearance; A, AC and CD passed their full native geometry checks. Service and managed acceptance were explicitly NOT_RUN in that reference. These are separate native receipts, not 85 new native executions in this suite. Their original evidence is retained under `shared-tree-native-reference/evidence/4d1dc2c5572143f3a8a3e8a8b0d5a300`.

The initial byte-boundary test used a catalogue whose input was larger than its certificate, invalidating the test's assumed governing boundary. That 81-pass/1-test-failure receipt and exact test/module copies are retained. The fixture was enlarged; no mathematical claim depended on the failed assumption. Static resource review also prompted constant-time dictionary-length rejection before allocating a key set. No combinatorial or nominal-ranking false certificate was found in the bounded reviews.

Independent frozen-kernel review `58764f599a45413fbed5b5f25070a51a` passed both actual native-catalogue correspondence cases, 32 resealed/input/final-mutation attacks, eight explicit budget exhaustions, and separate exact Machin ordering of five parallel choices including a rational-versus-pi near-tie and an exact tie. The verifier still passed with producer helpers disabled. A deliberately false native artifact identity was accepted only as a pure changed input identity and rejected by the actual artifact binding, confirming the declared authority boundary. Review result SHA256: `de62faad90901f99c8adda5fa43ba2bbbf3d524a68106a9f8605d472a297a990`.
