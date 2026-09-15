# Generated unequal-pressure trees with fixed physical tee identities

The useful first implementation should generate trees using **exactly the already-declared pressure tee IDs**, with one fixed placement/frame per ID. This preserves the existing `CoupledTreeBoundary` and permits new connector paths, sink/outlet assignments and root/child topology. It needs no new pressure theorem, coefficient renaming or user-authored complete tree menu.

This document is a read-only design. Its scripts retain source bytes and a small exact abstract incidence oracle; they do not modify application modules or claim native feasibility.

## Current contract and source basis

The reviewed source copies and SHA256 manifest are in `evidence/reviewed-source/` and `evidence/assessment.json`.

* `routing/coupled_tree_scenario.py:33` defines `oma.coupled-tree-boundary/1`. Exact pressure intervals, exact per-sink minima and proof search boxes are independent of the alternative geometry. `tee_outlet_loss_coefficients` keys are physical tee IDs, with separately positive `b` and `branch` coefficients referenced to total inlet flow. The source total-pressure convention and all fixed-loss/ideal-bore/applicability statements remain mandatory.
* `routing/network_scenario.py:318` requires a mutually exclusive pressure-pipe engineering-service mode, with exact minima only in the boundary. At line 351, **every complete alternative's tee set must equal the full coefficient-key set**. The same module's `network_fixed_requirements` excludes the replaceable design menu and keeps the pressure declaration. It is the relevant unchanged-obligation projection; the complete scenario/menu/mission hashes necessarily change when the alternative menu changes.
* `routing/shared_tree_proposals.py:221` and `routing/shared_tree_catalogue_check.py` currently reject pressure-specific generation. The nominal geometry equations do not require fixed flow, but the present loss root is `digest(physics)`, which is insufficient to identify a coupled tee's actual coefficient contract. Merely removing the rejection would leave the intended provenance binding incomplete.
* `routing/coupled_tree_pressure.py:140`, `:208` and `:252` independently reconstruct paths, native dimensional coefficients and polynomial rows. Its `_checked_proofs` at line 460 requires current local and global model/parameter bindings. `network_checker.py:179` invokes the native-metric adapter, and its operating-point check requires independent, local and global PASS. This existing path should remain the service authority.

Original unchanged source: `math1/math1/the 5 things that combine ceiling router with ananke.docx`, SHA256 `72379f535f744b15ccbdcbbb6f68904f6c1177ace27a8fcc028229039b8bd129`. Retained native paragraph excerpts identify ADD-SIR2.1 P3787-P3806 (branched carriers and junction realizations), DEF-RTR39-44 P4472-P4513 (fitting/section states and terminal skeletons), DEF-RTR45 P4516-P4517 (aggregate shared-trunk flow), THM-RTR50-53 P5254-P5265 (connection realization, finite topology difficulty, sharing and trunk sizing), and ALG-RTR17-22 P5526-P5537 (multi-terminal proposal, independent skeleton and physical fiber checks). These require consistent shared-flow and fitting realizations; they do not authorize arbitrary coefficient reassignment when topology changes. Full source-algorithm implementation flags remain false.

## First slice: fixed IDs and fixed sites

Keep the current `oma.shared-tree-native-search/1` syntax. For `coupled_tree` requests add the following profile, checked independently by producer and catalogue verifier:

1. Exactly two or three sinks, with `PRESSURE_PIPE` and `ENGINEERING_SERVICE`; `physics`, `pressure_driven` and `passive_tree` are absent. The complete existing coupled boundary validates unchanged. Legacy sink fixed flows/static budgets remain forbidden.
2. Search tee IDs are unique and equal the complete `tee_outlet_loss_coefficients` key set. Their count is exactly `number_of_sinks - 1`. Every ID has one authored center, frame and takeout pair. A tee ID is not a freely renamable root/child label.
3. The exact current boundary root is bound into each tee's nominal loss-contract identity. The agreed form is `digest({"model":"oma.coupled-tree-boundary/1", "tee_id":id, "outlet_coefficients":normalized_boundary["tee_outlet_loss_coefficients"][id], "boundary_root":digest(normalized_boundary)})`. Keep the old `digest(physics)` branch byte-for-byte for existing fixed-flow requests; the new binding applies only to the explicit coupled mode.
4. Nominal coordinate, radius, cap, fabrication, unique-ID, component and cost rules remain unchanged. Every supplied connector and all original request/search/context roots pass the current independent catalogue provenance checker, using the new explicit loss binding only in this mode.
5. The pure finite topology kernel is unchanged. A full binary tree with n leaves contains n-1 tees. Since the supplied catalogue contains exactly n-1 distinct fixed IDs, every valid complete assignment must use all declared IDs. No postfilter or truncated-prefix exception is needed to establish the tee-key condition.
6. Expand checked assignments into `NetworkDesign` without renaming physical tee IDs or exchanging `b` and `branch`. Construct the complete `SharedNetworkScenario` from the unchanged normalized requirements plus the new alternatives and revalidate it. Compare its canonical fixed-requirements projection to the current authored projection (using the same source ID); retain the original raw request root too.

For two sinks this admits both labeled outlet assignments for the one tee, with all supplied connector choices. For three sinks, the abstract unconstrained topology count is 24: two ordered root/child ID choices, two root outlets that can feed the child, and six sink permutations. Actual caps, frames, template inventory and native feasibility may eliminate any number. The design does not assert that 24 physically realizable options exist.

This is more than relabeling complete input trees: the request contains only tee sites, directions, stubs and optional planes, and the producer constructs connector macros and whole component/path networks. Fixed sites still permit different source-to-tee, inter-tee and sink connector paths and different shared-flow subtrees. It deliberately does not claim free tee placement or arbitrary numbers of tees/sinks.

## Physical law stays attached to each fitting

For a selected component c with descendant leaf set D, the pipe/elbow pressure term remains

`rho/(2*A_c^2) * (f*L_c/D_c + K_excess) * (sum_{j in D} q_j)^2`.

For tee t, outlet o and the outlet's leaf subset E contained in D_t, it remains

`rho*K[t,o]/(2*A_t^2) * (sum_{j in D_t} q_j)^2`, applied only to rows in E.

The tee coefficient references **all inlet descendants**, not just the outlet flow. There is no tee skeleton Darcy charge or common-outlet-head substitution. Changing which sinks use outlet `branch` changes the affected equations; it must not change the coefficient attached to that outlet. Native per-component bore intervals, measured lengths and every cap elevation are freshly derived for each materialized alternative, with current roots and original numerical/applicability scope.

The abstract exact oracle in `scripts/assess.py` uses unequal coefficients A=(1/5,3/10), C=(1/4,2/5), positive pipe terms and leaf flows (3,2,1)/1000. For one fixed assignment, exchanging the two physical tee coefficient records while keeping the same manufactured available heads produces nonzero residuals `(9/2500000,27/20000000,9/10000000)`. All IDs still occur once, so a tee-count/set check alone cannot detect a semantic loss reassignment. The independent binding must include the actual ID and named outlet coefficients. This oracle is an abstract path-law counterexample, not a native operating-point proof.

## Existing proof and service chain

Every resulting candidate still needs complete current native semantics, full source/self/contact/zone coverage, the native pressure metric inventory, independent model derivation, local Banach proof and global nonnegative-univalence proof. The global proof needs the actual complete laminar descendant family and a strictly positive singleton contribution per sink. Terminal pipes with positive whole native length and positive Darcy coefficient may establish the premise; generation does not simply assert it.

The proof-proposal box is the unchanged exact `flow_search_box_m3_s` keyed by sink ID. The generator may not move its midpoint, widen it or reduce delivery minima to rescue an alternative. A local proof failure or a root outside that box gives UNKNOWN for that candidate, even if the same finite catalogue has another candidate that proves and serves. With both proofs passing, the positive root is unique among nonnegative roots for each fixed parameter tuple; the separate current per-port forward-flow, minimum-delivery and velocity checks still determine service. A proof scope or applicability failure is not physical infeasibility.

Nominal length/fitting ordering remains proposal ordering. It does not optimize pressure loss, pumping power or native service, and supplies no lower bound for those objectives. `max_results` can hide a pressure-feasible option later in the same catalogue; bounded output or UNKNOWN candidates must not become complete physical-universe exclusion. Existing residual/next-best proposal mechanisms can be considered separately after this first integration.

## Why multiple sites per role is a separate extension

The present pure catalogue requires unique tee-instance IDs. Giving one boundary tee ID several centers violates that inventory. Giving sites fresh IDs violates the existing exact boundary-key condition, unless the caller changes the fixed requirement contract. Silently moving coefficients between site IDs makes the result a different mission.

A future explicit schema could keep the pressure boundary keyed by persistent roles and put a finite `role -> site options` declaration in the search specification. Each option would have a separate site ID, exact geometry and an immutable role reference. A complete assignment would need exactly one site per role, an injective physical-ID projection, no reused site, a full component/connection relabeling witness, and every loss identity bound to the role's exact original named outlets. The final physical network may use role IDs while its proposal certificate retains site IDs, but that correspondence requires independent proof.

The existing kernel does not enforce those color/role multiplicities. Filtering its first eight nominal assignments for role-validity can omit a cheaper or the only valid assignment later in the ranked list. A sound extension must either add a checked role constraint to the full enumeration or enumerate the full bounded product of one site per role, verify each subcatalogue completely, and independently merge their complete ranked ledgers. All subcatalogues, empty cases, budgets and duplicate physical realizations must remain accounted for. That is useful subsequent work, not part of the recommended fixed-ID first slice.

## Implementation and independent validation plan

The small implementation change belongs to the generator's explicit mode gate/loss binding and the independent catalogue checker's corresponding profile. The field parser and complete mission validator are retained. The pure topology, local coupled and global univalence kernels need no changes. Root-owned generated-job/admission/export consumers should retain the whole boundary in the request, fixed projection, normalized catalogue roots and current candidate context.

Focused independent checks should include exact tee-key count/set rejection before macro work; old fixed-flow output/root equality; source/sink pressure/minimum/box immutability; different coefficients per ID and outlet; a forged ID permutation; missing/extra roles; a coherent geometry/proof reseal with the wrong loss root; source-to-leaf path incidence after root/child reversal; callback mutation and bounded UNKNOWN; and mandatory local/global proof/service results in the final report.

Use a newly declared **dyadic** two-tee/three-sink native fixture compatible with current exact macro arithmetic. Fix terminals, sites, dimensions, unequal coefficients, total-pressure brackets, minimum deliveries and one flow box before the campaign. Manufacture an independent nominal reference only to select a meaningful bounded fixture; retain its distinction from interval/native proof. Generate alternatives from sites/templates only. Require at least two genuinely different full physical trees, fresh native metric/pressure proof replay for each completed candidate, and one complete accepted/exported/freshly rechecked result. Preserve a rejected or UNKNOWN alternative as a separate disposition; do not alter the physical contract after seeing failure. This is a proposed validation campaign, not evidence already executed here.

The retained design oracle covers the 24 abstract label templates and the coefficient-swap counterexample. It is intentionally independent of the producer, topology kernel and pressure solvers, and grants no geometric template count or native acceptance authority.
