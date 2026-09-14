# Bounded next-best fabrication proposals: design handoff

Status: design and analytic/native counterexample only. No new production kernel, API or test suite has been implemented. All artifacts are private to `.oma/development/next-best-fabrication/`.

## Concrete candidate loss

The existing exact-count frontier is correct, but returns only one minimizing graph walk per count. Its documentation and certificate explicitly disclaim preservation of all equal-cost paths or the complete physical route universe. A separate current joint route can invalidate that one nominal minimum while a different path of the same exact fitting count remains physically usable. The native rejection depends on the other route; it is not an unconditional property of the excluded word.

The retained counterexample uses the actual analytic IFC wall `[0,2]^3`, source `(-1,1,1)`, sink `(3,1,1)`, diameter `1/4`, bend radius `1/2`, minimum remaining straight `1/8`, and clearance `1/8`. Its fixed grid is:

```
x = [-1,0,1,2,3]
y = [-1,0,1,2,4]
z = [1,3/2]
```

Exactly two contracted polylines with two turns pass this complete nominal wall model:

| Path | Interior corners | Nominal cost | Fresh current cross-route result |
|---|---|---|---|
| Unique nominal minimum | `(-1,-1,1), (3,-1,1)` | `6 + pi/2` | FAIL |
| Alternative with the same two fittings | `(-1,4,1), (3,4,1)` | `8 + pi/2` | PASS |

The separately materialized competing route is the straight segment `(1,-1,1/2)` to `(1,-1,3/2)`. Each detour has five native parts, passes all five original-wall pairs, its own complete self checks, exported semantics, and the separate exact-to-IFC fabrication correspondence. The lower path has positive native common volume `0.010416666657585602 m^3` with the competing route. All five cross-route pairs pass for the upper path. The exact frontier checker closes 32 reachable count-product states and reconstructs 46 transitions. Independent enumeration of all two-turn contracted polylines gives only these two admitted paths: equal transverse endpoint coordinates force axis sequence y-x-y or z-x-z; every available nonzero transverse displacement is checked.

Evidence: `../evidence/analytic-two-detours/result.json`, original/source and three actual exported IFC files, and `../scripts/counterexample.py`. The run used immutable executable `bac10b7f20d44219f13fe5df2a70600f22b4fe69a4021dbe0e8e2172f76743ac`. It did not execute Store acceptance, service physics, or an aggregate joint mission. It establishes the stated geometric proposal omission, not whole-project feasibility or a false frontier theorem.

## Original source basis

Read-only original: `math1/math1/the 5 things that combine ceiling router with ananke.docx`, SHA-256 `72379f535f744b15ccbdcbbb6f68904f6c1177ace27a8fcc028229039b8bd129`. Locators are native `word/document.xml` paragraphs, including table cells. The exact source text and current implementation hashes/line signatures are pinned in `../evidence/source-basis.json`; the pinning script reopens the original ZIP read-only and compares the text against retained extraction.

- DEF-RTR39–41, P4472–4484: fabrication direction, bend/straight state, size and admitted transitions. These are the existing base graph's scoped obligations.
- ALG-RTR15, P5522–5523: finite or explicitly bounded fabrication/size product; state explosion remains UNKNOWN.
- ALG-RTR22, P5536–5537: a proposed route column still requires independent geometry, physics, resource, cost, compatibility and version checks under the fixed request.
- ALG-RTR26, P5544–5545: an exact pricing result refers to its complete represented domain, including its branch automaton. This supports explicitly rooting the residual word language; it does not turn nominal length into true reduced cost.
- ALG-RTR27, P5546–5547: budgeted proposals may return no candidate without closure. This remains the physical proposal pipeline's scope even when a residual finite graph optimum is exactly certified.
- ALG-RTR16, P5524–5525, and ALG-RTR38, P5568–5569: independently checked path/potential certificates and no physical infeasibility from absent inner paths.
- ALG-RTR29, P5550–5551: deletion requires context-valid dominance evidence. Being more costly nominally at the same fitting count does not dominate a different joint-compatible shape.

The trie construction below is a new bounded specialization, not textually prescribed implementation. It completes none of these full source algorithms and is not general node-dual, resource-toll, topology or continuous pricing closure.

## Recommended smallest mechanism

Use a deterministic finite prefix trie over explicitly excluded *complete graph words*. Multiply the current six-coordinate fabrication state and exact count by that trie state. Reuse the existing rational fixed-count cost rule; there is no need for symbolic-pi comparisons or a general K-shortest simple-path algorithm.

A word is the sequence of signed-axis symbols `0..5` for every adjacent grid step from the fixed source, followed by the decision to terminate. The base graph/root, start, objective, full count cap, and word set are all bound. A direction sequence uniquely determines its base path because every transition advances to the adjacent coordinate. Forbidden words must be independently replayed as valid accepting graph walks in the declared count range. Exclusion means `ALREADY_GENERATED_PROPOSAL_WORD`; no native-failure validity is required or inferred.

The automaton starts at the empty prefix. Matching the next symbol advances along a trie edge. The first absent edge enters an absorbing SAFE state, because no listed complete word can subsequently match the already divergent prefix. At an ordinary graph goal, termination is allowed if and only if the trie node is not marked as one of the excluded complete words. A marked node can have children and **must retain every outgoing graph transition**. Excluding a short goal-reaching word must not exclude a longer walk that leaves that goal and eventually returns, unless that longer word is separately listed. Prefix, edge, substring and suffix bans are different, stronger languages and are not permitted implicitly.

At count k the residual language is exactly:

```
L_k(graph) minus the finite set of excluded complete words at count k.
```

A proof of no residual path says only that this remaining finite graph language is empty. It does not prove physical infeasibility of the original graph words, of another joint context, or of continuous routes. Prefixes and edges shared with excluded paths remain available.

## Finite structure and useful sparse bound

The existing graph forbids immediate U-turns. A fixed signed direction advances strictly through ordered adjacent coordinates; every direction change is perpendicular and increments k. A walk with k <= K therefore has at most K+1 monotone straight runs, each with at most `max_axis_nodes - 1` steps. Thus every accepted word has length at most `(K+1)*(max_axis_nodes-1)`, including walks that revisit a coordinate or visit a goal before terminating. The implementation and checker must derive these premises from the actual transitions; a future graph with zero steps, uncounted reversals, or different transitions would invalidate this bound and require a new rule/root.

A full rectangular Cartesian product is unnecessary. Every non-SAFE trie node is one exact prefix word and can correspond to only one deterministic base/count state. Reachable SAFE nodes contribute at most one state per reachable base/count state. If the latter has N states and the trie has T nodes, the reachable product has at most N+T states, rather than N*T. Grounded closure verifies which of these states actually exist. Separate producer/checker geometry caches remain private to each invocation.

This preserves finite graph walks, including possible self-overlap. It does not silently impose simple paths. Nonadjacent self-interference remains an independent physical check.

## Proposed API and proof fields

New module suggestion: `oma.optimization.fabrication_alternatives` (not implemented).

```
compile_fabrication_alternatives(
    problem, objective, max_fittings, excluded_words,
    *, max_states=24000, max_work=1000000,
    max_excluded_words=16, max_excluded_steps=8192,
    max_certificate_bytes=16777216, checkpoint=None)

verify_fabrication_alternatives(
    problem, objective, max_fittings, excluded_words, certificate,
    *, same independent budgets)
```

`excluded_words` is a bounded list of complete direction lists, not caller-supplied trie transitions or trusted string hashes. Reject booleans/noninteger symbols and duplicates. Validate list sizes, total step count, source/count-derived word length and canonical certificate byte limits before large allocations or Fraction parsing. Canonical trie node IDs are reconstructed from sorted prefix words rather than trusted producer IDs. Input root binds the exact normalized exclusion set; each word identity binds graph root, symbols, terminal decision and independently reconstructed exact count. Optional provenance lives in the adapter's separately rooted generation ledger.

Result status is CERTIFIED only for a complete residual frontier. Certificate contains input/graph/objective/count/exclusion/automaton/product-model roots; original maximum count; exactly K+1 count entries; grounded reachable product rows with rational potentials and predecessor indexes; and one realizing product path and contracted points for each reachable exact count. Entry names should explicitly be `RESIDUAL_OPTIMAL_PATH` or `NO_PATH_IN_DECLARED_RESIDUAL_LANGUAGE_AT_EXACT_COUNT`. Retain `all_equal_cost_paths_retained=false`, original/continuous/physical closure false, native objective lower bound false, and native acceptance authority false. Returned k is exact k, not at most k.

Each entry contains cost `[a,b]` with fixed `b = length_weight * R * k / 2`. At every turn, rational edge cost remains `length_weight*(completed_run - previous_trim - R) + fitting_weight`, and straight continuations cost zero. Termination discharges `length_weight*(final_run - previous_trim)` once. These costs are nonnegative under the existing strict straight predicates. The trie changes terminal admissibility and remembered history, never cost, geometry, turn counting or radius.

The independent verifier must:

1. Reconstruct the normalized graph, valid exclusion words, canonical trie and all roots from caller inputs; distrust producer automaton, work and reachability metadata.
2. Verify each row's structural base/count/trie compatibility, unique state, source zero label, and an actual strictly earlier predecessor edge. This establishes that all listed states are reachable.
3. Reconstruct **all** allowed graph successors with checker-side geometry and update the trie independently. Require every reachable successor in the table, including successors of accepting or excluded goal states. This establishes complete residual reachability.
4. Check every nonnegative rational edge inequality and every accepting terminal inequality for that count. Do not impose a terminal lower-bound inequality at an excluded stop; its outgoing transitions remain covered.
5. Independently replay each realizing path and its automaton trajectory, count, terminal eligibility, exact rational cost, fixed pi coefficient, and contracted polyline. The realizing cost equals the terminal lower bound. Unreachable entries have no accepting state and no invented path/cost.

Source-zero potential plus all edge inequalities lower-bounds every accepting residual path; grounded closure excludes invented or omitted reachable states. The realizing path supplies the matching upper bound. This is the same proof structure as the current frontier with an explicitly checked regular-language product.

## Sequential next-best enumeration and actual consumer

The first integration should generate a small number of diverse proposals before the joint menu is frozen. This fits the current pipeline: `routing/certified_fabrication.py` produces graph/frontier proposals, `routing/proposals.py` deduplicates and persists them, and `routing/joint.py` enumerates the frozen finite option menu before assignment checks. It needs no mutable feedback channel or change to accepted physical predicates.

Start with the already independently checked ordinary exact-count frontier. Add emitted valid graph words to the exclusion set and perform one bounded residual-frontier round. Retain at most one newly checked alternative per represented count in that round, with a small explicit per-count/total output quota. One extra round already recovers the retained counterexample's longer two-fitting route. Further rounds may be configured within hard budgets; no promise is made that default eight-axis models finish.

For a given count, if each exclusion is exactly a previously generated and independently checked residual minimum, round j returns the next nominal minimum among not-yet-generated words. Ties remain eligible and the sequence is nondecreasing, not necessarily strictly increasing. To claim this ordinal property, replay the complete root-bound round chain and prove the next exclusion set is exactly the prior set plus those prior generated words. Without that chain, the certificate claims only a residual optimum, never 'j-th overall'. No within-tie rank is claimed beyond deterministic output choice.

Each proposal binds residual certificate/entry/exclusion/round roots, graph/source/frame/current request/build roots, exact k, and a fresh binary64 fixed-fabrication proof. Source hashes and complete support accounting remain rechecked before publication, as today. A rounded or exporter-simplified duplicate is a recorded `DUPLICATE_MATERIALIZATION_PROPOSAL`, consumes a bounded attempt, and may cause that exact graph word to enter the already-generated list for the next round. Do not extrapolate that one word's exclusion to every word sharing its rounded points, and do not claim physical uniqueness or completeness. Exact paths that fail binary64 correspondence similarly yield no materialized proposal while preserving an honest attempt ledger.

The current optional joint fitting limit remains authoritative only after fresh actual IFC counting, native geometric checks, and complete shared assignment checks. A cheaper nominal path's rejection under one competing route is never used as a universally invalid route, shared edge cut, capacity assertion, or cached physical FAIL. A future lazy response to rejection would require separately bound current other-route context and must still use the rejection as a generation hint; it is unnecessary for the first component.

The useful new option identity is `FABRICATION_RESIDUAL_FRONTIER`, with `nominal_exact_count_residual_optimality=true`, `nominal_original_count_optimality=false` unless empty exclusions, explicit original/count/exclusion roots, and `shared_native_budget_feasibility=NOT_CHECKED`. Existing successful earlier rounds remain independently certified if an optional later round is UNKNOWN. Missing count entries, an unclosed later frontier, output quota or timeout never become no-path declarations. Global cancellation, changed source/context/build, or the adapter's overall deadline publish no new proposals from that invocation. Final callbacks and no-callback current-input binding must follow the corrected pressure-kernel pattern; callback exceptions cannot be converted into mathematical UNKNOWN inadvertently.

## Reusable boundaries and required new work

- `optimization/fabrication_search.py`: `_prepare`, `_valid_state`, `_goal`, `_producer_successors`, `_checked_successors`, `_Work`, and normalized root/model primitives. Producer and verifier must use their respective transition generators, never share a producer-generated adjacency table as authority.
- `optimization/fabrication_frontier.py`: `_objective`, `_bounded`, `_producer_edges`, `_checked_edges`, `_terminal`, `_points`, `_checked_points`, and bounded streaming hashing patterns. These are currently private helpers; the initial new module may call them under exact executable version binding, but must not mutate their existing contracts. Row-parent indexes for the trie product must project to base/count states before calling point reconstruction.
- `routing/certified_fabrication.py`: the independent count certificate check, per-entry binary64 conversion and proof binding at lines 296 onward. Add a separately budgeted residual phase after a valid initial frontier, preserve default behavior when disabled, and keep lower-count/resource alternatives within explicit output quotas.
- `routing/proposals.py`: distinct report/certificate kind plus full proof reference persistence and finite duplicate suppression. Root-owned joint assembly consumes the expanded checked proposal menu without treating nominal pricing as physical acceptance.

The existing full frontier producer/verifier cannot directly verify a trie product or filtered terminal language. It needs a new producer and independent verifier; monkeypatching its goal predicate, deleting arbitrary edges, or post-filtering the single minimizing path cannot establish the missing residual optimum.

## Independent oracle and adversarial validation plan

Use small free cube/anisotropic grids and exhaustively enumerate bounded coordinate walks without using either transition generator, parent table or potentials. Independent signed-axis/corner bookkeeping computes straight debts and complete costs. Filter only exact full direction-word equality at the chosen termination, then compare every count and every sequential residual round to enumeration. Fitting-only and zero-fitting objectives exercise zero rational edges, tied optima and final straight debt. Preserve repeated vertices and walks that visit a goal, leave it, and return.

Include: two paths sharing a rejected prefix/edge; excluded word that is a proper prefix of another accepted word; several words with common prefixes; a goal-revisit example whose outgoing edges may not be dropped; all words at one exact count excluded; empty/duplicate/invalid words; missing prefix states and successors; premature SAFE transitions; false forbidden terminal flags; omitted counts; fabricated potentials/costs/roots; cost/cap/grid/context changes; malformed huge encodings; state/work/byte/word budgets; callback exceptions at hashing, closure and final binding; caller mutation during final callbacks; partial later-round results; and binary64 duplicate correspondence.

Replay the retained native wall counterexample using the future residual certificate: initial unique minimum still receives its actual fresh cross-route FAIL; excluding that generated graph word yields the longer same-count path, whose independently materialized current geometry passes all retained pairs. This is an integration test of useful proposal diversity, not a shortcut around the ordinary complete native checker.
