# Grouped traversal for the exact shared-tree top-K certificate

This private change improves the existing finite catalogue algorithm without changing its certificate schema, catalogue universe, exact counts, nominal order, or proposal dictionaries. It preserves the sealed `d04f2ad9...` implementation and its evidence. It does not change the full-ledger implementation or any native adapter.

The original read-only source is `math1/math1/the 5 things that combine ceiling router with ananke.docx`, SHA256 `72379f535f744b15ccbdcbbb6f68904f6c1177ace27a8fcc028229039b8bd129`. ALG-RTR17, OOXML paragraphs P5526–5527, supplies the finite exact-DP direction and explicitly retains exponential dependence on terminals. ALG-RTR18, P5528–5529, requires independent terminal/junction/loop/class/embedding/context checks. This optimization advances the bounded discrete DP component. It does not implement all those source obligations or supply native embedding/service authority.

## Parallel edges and exposed-slot substitution

Group every actual connector ID by its exact directed `(from node, from port, to node, to port)` pair. The admitted catalogue parser already binds the corresponding complete cap positions, directions, section and immutable catalogue roots. Each group retains its **complete integer multiplicity**. Only its first K connectors under exact nominal cost and connector-ID tie order are required for top-K reconstruction.

To justify truncation, fix an outside tree using a discarded connector. The K earlier connectors in the group all consume the same exposed source slot and target node. None can already occur elsewhere in that outside tree: each would use the same source slot a second time. Replacing the discarded connector therefore gives K distinct valid catalogue trees. Adding identical outside costs preserves nominal order. At a cost tie, sorted disjoint connector-set union preserves lexicographic order, because the smallest member of the symmetric difference is unchanged. Thus the discarded connector cannot belong to the first K complete trees.

An auxiliary attachment state is `(parent tee, labelled outlet, exact sink mask, exact used-tee mask)`. It includes both the outgoing connector and its child subtree. Different child-root alternatives can be merged here: the same parent outlet is exposed to the outside, and precisely the same node identities are consumed. The child root and connector remain present in each complete label. This merge does not replace a b outlet by a branch outlet, drop tee identities, or assume physical equivalence of different geometries.

For each child-root alternative, the full attachment count is `number_of_parallel_connectors * complete_child_count`. Sum over every admitted target root/leaf. All alternatives are disjoint: the connector word determines the selected outgoing connector and target root uniquely. Label truncation does not affect that full count.

## Complete parent recurrence

For each parent state, partition its sink mask and its non-root tee mask into the two labelled outlet masks. Join the corresponding attachments only when their exact node masks are disjoint. The parent count is the sum of the product of both complete attachment counts. Add the parent tee cost exactly once. The complete source-edge recurrence remains unchanged.

The producer constructs attachments bottom-up from actual outgoing groups and discovered child states. It enumerates right masks directly from the complement of each left mask, instead of first forming incompatible Cartesian products. The checker independently visits every potential root state, enumerates every labelled mask partition, scans all possible child roots for each attachment, reparses the full admitted connector and tee costs, and reconstructs the count and top-K labels. A directed induced-reachability failure remains only a necessary zero-state test. Passing it does not bypass the recurrence.

Sorted component label products are monotone in both indices under their fixed disjoint outside component. The producer traverses rows and uses sorted binary insertion. The checker traverses columns and uses an independently maintained unsorted worst-element buffer. Once the smallest remaining product in a row/column cannot beat the current Kth label, no later product in that row/column can enter the top K. If the first product in a row/column is dominated, all later rows/columns are dominated too. Exact rational-plus-pi comparisons must resolve every comparison used for this pruning; uncertainty returns `UNKNOWN`.

The original certificate still lists every positive-count `(root tee, sink mask, tee mask)` state, its complete count, its exact K labels, and the final source prefix. Auxiliary attachments are reconstructed implementation data, not trusted certificate claims. New and old implementations can verify each other's certificates. The same successfully computed input and K have byte-identical certificates; only operation counts and attainable resource limits change.

## Bounded work and limitations

The public API and all existing hard limits are unchanged. Candidate mask partitions, attachment scans, edge comparisons and label products consume work; products are charged before construction. Every auxiliary record is charged and checked before allocation. Each producer attachment table has at most `max_states` records; total cached attachment records on either side are at most `4*max_states + 2*number_of_sinks*number_of_tees`. Captured input/proof parsing, rational/count-bit limits and the final no-callback mutation guard remain unchanged. Caller exceptions retain identity. Resource failures publish no partial prefix or count authority.

With n sinks and exactly n−1 available tees in a dense catalogue, the complete parent partition count is

`(n−1) * sum(C(n,a) C(n−a,b) C(n−2,a−1) C(n−1−a,b−1), a,b≥1, a+b≤n)`.

For n=5,6,7,8 this is 2,280; 21,210; 195,216; and 1,785,672 respectively, before the unchanged source recurrence. This fits the 2M transition ceiling for eight sinks, but does not guarantee byte, work, precision or elapsed-time completion. More available tees, larger K and physical catalogue growth remain separately bounded.

The new validation freezes six exact source/dependency files and fourteen test/config/support inputs. Its 303 passing cases include all 261 previous tests and 42 new cases: byte-identical old certificates with bidirectional replay; an independent incoming-edge-function oracle; exact complete parallel multiplicities; rational/pi/zero ties; extra tee alternatives; the actual dense six-sink count; producer-disabled checking; resealed state/count/cost/edge attacks; late mutation; and exact work boundaries. The copied old module is a pinned test fixture, not a new production dependency.

The initial preparation diagnostic used incorrect field names `start/end` while inspecting group sizes; it failed before any kernel call and is retained. A first draft passed all 261 previous cases; its later allocation audit moved a total auxiliary-record bound from the end of a size round to immediately before each allocation. Both snapshots and receipts remain separate. Earlier d04 dense six–eight transition failures and the first grouped eight-sink 16MiB byte failure remain intact.

Actual authored benchmark declarations, exact source copies, raw inputs, full proof/check outputs and phase limits are retained under `evidence/`. The final handoff identifies their individual statuses and hashes. Runtime figures are measured on this machine, not guaranteed service budgets.

## Final frozen results and application budget boundary

Final module SHA256 is `116390796eab23e2921915d982130ee9739439d8696d11e1694c96b76e79e063`. The 303-case receipt is `validation/1993e0b4475f44398780d4789f143d75/result.json` (17.32s, no failures/errors/skips, exact XML node multiset and unchanged inputs). Independent peer evidence under `evidence/peer-review/04523011a8cc4d28b3b956fec93b2465` checks 14 catalogues by fixed-size edge subsets, degree equations and reachability, not subtree recurrence. All 42 K/count/certificate-root cases match d04, including extra tees and parallel/zero-tie edges; producer-disabled replay and seven resealed attacks pass.

The final authored run is `evidence/final-authored/51bf73e7ebec4ff4984a33cbada14369/result.json`, SHA256 `f6666b9c961cf2142e155879f5d1d0b192afd18f366f1589a56d0a3c5171b797`. Every row below is producer CERTIFIED and independently checked PASS on that exact final module.

| Sinks | K | Complete assignments | Certificate bytes | Producer + checker work | Producer + checker seconds |
|---:|---:|---:|---:|---:|---:|
| 5 | 8 | 3,012,582 | 510,292 | 689,154 | 1.10 |
| 6 | 8 | 801,286,604 | 2,735,241 | 3,443,186 | 6.45 |
| 7 | 2 | 311,249,632,706 | 3,684,701 | 5,904,974 | 9.74 |
| 8 | 1 | 166,262,214,109,624 | 9,551,978 | 25,724,155 | 47.79 |
| 8 | 2 | 166,262,214,109,624 | 17,859,221 | 35,098,589 | 70.28 |

Each phase used an explicitly declared 60s cooperative deadline and at most 20M work, 2M transitions, 10M label products, 50,000 states and 512 connectors. The eight-sink K2 query explicitly permits 32MiB; all other final rows permit 16MiB. Eight-sink K2 uses 1,785,685 transitions and 2,188,108/2,153,861 producer/checker label products; the latter exceeds the unchanged default 2M label-product allowance. Its producer/checker work is 15,662,515/19,436,074, each below the unchanged 20M per-stage hard maximum. An earlier declared 16MiB K2 run returned BYTE_BUDGET with no certificate; it remains retained rather than relabelled as successful.

These are kernel phase totals, not application end-to-end totals. `evidence/composite-policy/result.json` independently counts the retained eight-sink request and generated-output snapshots and includes generation and catalogue-verification work. The accounted subtotal is 28,537,345 for K1 or 37,911,779 for K2, before small mission-conversion and parent overhead. A proposed **explicit** COMPACT-only 40M composite budget must use one cumulative parent accumulator and pass `min(remaining, callee_hard_max)` to each nested phase. It must not pass the larger parent maximum directly to a 20M-limited kernel or restart the accumulator between phases. Existing defaults and full-ledger budgets remain unchanged. K2 also needs a separately explicit larger enclosing output budget; certificate fit alone does not prove the complete generated artifact fits. The actual application/native execution must verify these recommendations before admission.

All claims concern connector-ID trees in the complete supplied finite catalogue and their additive nominal cost. Two connector words may materialize identical geometry. Neither same-cap grouping nor attachment substitution transfers collision freedom, pressure feasibility, service satisfaction, physical uniqueness, native acceptance or an unrestricted continuous optimum. A rejected nominal prefix does not rule out a physically feasible later tree. All original full-algorithm flags remain false.
