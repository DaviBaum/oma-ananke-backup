# Certified residual fabrication proposals

The bounded residual frontier recovers a useful route when the sole nominal minimum at a particular fitting count is incompatible with another route. It excludes complete already-generated graph words, proves the minimum remaining nominal cost separately for every represented exact fitting count, and supplies additional proposals to the existing native joint checker. The exclusion is an enumeration operation. It never declares a native-rejected word, prefix or edge physically infeasible in other joint contexts.

This document describes the integrated working application checkpoint `1abe9a077844a184ec17e1c8a0a390aa4bf33d05dd302a6eefff7d770a0ff719`. The original design and failed/positive evidence remain unchanged. The portable evidence index is [latest.json](../../evidence/math/fabrication-residual/latest.json). No complete original source algorithm is marked implemented.

## Source and implemented specialization

The read-only original is `math1/math1/the 5 things that combine ceiling router with ananke.docx`, SHA-256 `72379f535f744b15ccbdcbbb6f68904f6c1177ace27a8fcc028229039b8bd129`. Native paragraph locators include all `word/document.xml` paragraph elements, including table cells. The retained [source basis](../../evidence/math/fabrication-residual/source-basis.json) contains exact text and per-paragraph digests.

| Original body | Native paragraphs | Bounded implemented component |
| --- | --- | --- |
| DEF-RTR39–41; ALG-RTR15 | P4472–4484; P5522–5523 | Fixed-size orthogonal fabrication state, exact fitting count, and a finite prefix-trie state; explicit state/work exhaustion |
| ALG-RTR22 | P5536–5537 | Independent graph/proof replay followed by source/frame/body correspondence and complete current native checks |
| ALG-RTR26 | P5544–5545 | Complete represented residual graph language and independent nominal optimum certificate; incomplete pricing remains UNKNOWN |
| ALG-RTR27 | P5546–5547 | Additional bounded candidate proposals; failure to generate an acceptable candidate does not close physical search |

Supporting RTR14 P5520–5521 and RTR16 P5524–5525 motivate the finite automaton product and path/potential checking. The trie, exact-count cost specialization and the explicit whole-word enumeration policy are new executable refinements; the source does not supply this implementation. General fitting catalogs, variable sizes, supports, slope states, homotopy presentations, node-dual resource pricing and continuous route closure remain open.

## Kernel API and proof

```python
compile_fabrication_alternatives(
    problem, objective, max_fittings, excluded_words,
    *, max_states=24000, max_work=1000000,
    max_excluded_words=16, max_excluded_steps=8192,
    max_input_bytes=1048576, max_certificate_bytes=16777216,
    checkpoint=None)

verify_fabrication_alternatives(
    problem, objective, max_fittings, excluded_words, certificate,
    *, same_independent_budgets)
```

The implementation is `oma.optimization.fabrication_alternatives`. `problem` and `objective` use the existing finite fabrication graph and nonnegative nominal length/fitting weights. Exact rational inputs use strings. `max_fittings=K` is a strict integer in 0…32. Each excluded word contains every original seven-coordinate graph/count state, including initial and final states. A word must follow independently reconstructed transitions and end at an accepting goal. Duplicate words, invalid transitions, nonterminal prefixes, incorrect counts, boolean coordinates and oversized encodings fail input validation.

Schema `oma.fabrication-residual-frontier/1` binds input, graph, objective, count domain, exclusions, trie, residual model and certificate content roots. Each product state has the original seven coordinates plus one trie ID. A matching prefix has a unique trie node; after divergence the absorbing SAFE state is `-1`. Trie storage is linear in total excluded steps. Producer and verifier independently rebuild the trie and validate every excluded input word. The verifier scans child symbols independently of the producer's keyed transition map.

Only exact excluded terminal words lose permission to stop. Their outgoing graph transitions remain available. The verifier reconstructs all successors, including successors from ordinary and excluded goal states. A longer walk may reach a goal, leave it, and later return. Shared prefixes and edges remain usable. Distinct words can simplify to the same materialized polyline; this is bounded duplicate work, not a proof of physical uniqueness.

For every listed reachable state, an earlier valid predecessor grounds reachability. Complete successor closure prevents omitted states or arcs. Rational potential inequalities bound every admissible path from below. A realizing path for each reachable exact count attains its terminal bound. A count without an eligible terminal is marked `NO_PATH_IN_DECLARED_RESIDUAL_LANGUAGE_AT_EXACT_COUNT` only after complete reachable closure.

For fixed count `k`, cost is `a+b*pi`, with `b=length_weight*R*k/2`. Straight continuation edges cost zero; a turn charges the completed run minus preceding and new trims, plus the fitting weight. The accepting terminal separately pays the remaining straight debt exactly once. These rational costs are nonnegative under the graph's strict straight/fitting conditions. The independent checker reconstructs costs and counts rather than trusting producer labels, work estimates or claimed terminal values.

The certificate contains exactly `K+1` entries in count order, each a residual optimum with exact points/path/cost or checked residual no-path. It does not certify the original language optimum, an ordering of all next-best paths, all tied minima, native objective bounds or continuous infeasibility. Sequential ranking would additionally require an independently checked chain of previous optimality/exclusion decisions.

## Resource and callback contract

The graph has at most 1,024 vertices. Each nonreversing signed-axis run advances through distinct axis coordinates; every direction change increases count. Therefore a word has at most `(K+1)*(max_axis_nodes-1)` transitions, including goal-revisiting walks. Defaults allow 16 words and 8,192 total excluded transitions; configurable hard ceilings are 128 words and 65,536 transitions.

Separate bounds cover encoded input/certificate bytes, individual tokens and integers, nesting, states and work. Certificate size is checked before cost Fractions are parsed. Producer exhaustion returns UNKNOWN without a partial frontier claim. Verifier exhaustion returns UNKNOWN without proof authority. A coarse success does not enlarge the declared graph/count domain. Invalid budget-constructor arguments can raise immediately under the underlying graph API. Caller checkpoint exceptions propagate with their original identity.

After the final public checkpoint, a bounded guard with callbacks disabled compares the current input/certificate bytes to their original canonical snapshots. This closes same-invocation callback mutation; it is not an atomic guarantee against arbitrary concurrent memory or filesystem writers. Native source bytes, current frames and physical applicability are separate adapter obligations.

## Source-bound adapter and joint consumer

`routing.certified_fabrication.build_certified_fabrication_proposals` retains the authenticated complete source obstacle inventory, independently checked outer grouping/omissions, guarded body domain and exact graph construction. Its residual phase is disabled by default. The actual `routing.proposals.project_proposals` consumer enables one round only when the joint mission explicitly provides `max_new_fittings`. It binds that full mission budget, original run/base/request/demand, source hashes and frames, scenario, objective, support model, coverage and current executable.

The represented count cap remains `min(B,32)`, whereas the declared native joint budget may reach 1,024. Counts above 32 remain outside this proposal proof. The optional residual phase defaults to three seconds, 24,000 states, one million work units and eight conversion attempts, additionally bounded by remaining overall time. It does not promise that a large eight-axis grid closes within those limits.

`routing.fabrication_residual.residual_proposals` takes original count-frontier proposals only after independent verification. Its generation ledger binds each original entry, complete excluded word and original binary64 body certificate. The residual kernel and verifier receive precisely those words, never a native collision result. Each residual entry is converted to binary64, then the existing orthogonal fabrication producer and independent verifier recheck the complete converted body against the full outer model. Exact count and `k+2` contracted vertices must agree. Duplicates and unresolved conversions consume bounded attempts; no missing physical alternative is claimed impossible.

Proposal metadata includes `path_certificate_kind=FABRICATION_RESIDUAL_FRONTIER`, exact count, residual certificate/entry/count/exclusion/model roots and generation-ledger root. `nominal_exact_count_residual_optimality` is true; original-count, scalar-graph and binary64 objective optimality are false. `shared_native_budget_feasibility` remains `NOT_CHECKED`, and the proposal grants no acceptance authority. Local residual exhaustion retains earlier checked proposal options. Global cancellation or changed source/model/context/build inputs suppress publication, including after the last callback.

Ordinary materialization, complete current source/self/cross-route checks, actual native fitting counts, finite joint selection, managed acceptance and fresh exported-file verification remain required. The finite menu is frozen after proposal enumeration. One extra round and finite output limits do not establish the complete Cartesian product of physical routes.

## Retained validation

The kernel SHA is `16857629268db3b601340d84c6dd9c563452ecdf9daf0e5bd212d387be2d7910`. Its 79 tests passed in 7.45 seconds on frozen kernel checkpoint `1d8467cf5bda99a3992f9bc01a33a07fff29f629ea8be2f5336114be8ee47d10`. Independent cube and anisotropic vertex-walk enumeration checks multiple objectives and residual rounds without using producer transitions or potentials. Adversarial cases cover ties, shared prefixes, goal revisits, omitted closure states, forged paths/costs/counts/roots, bounded encodings, callbacks and final mutation. A separate actual IFC correspondence case checks the costlier residual against five wall pairs and five competing-route pairs; that earlier case alone did not perform Store acceptance.

The complete joint workflow test `tests/test_joint_residual_fabrication.py` passed in 19.55 seconds on `1abe9a…` after strengthening exact denominator assertions. It freezes a synthetic IFC wall, a thin permitted vertical range and two declared demands before running the genuine proposal pipeline. No producer, verifier or native checker is stubbed.

The direct candidate is rejected by the wall. The original two-fitting nominal minimum, costing `33749/5000 + pi/2`, is rejected for positive native common volume with the second route. The residual two-fitting route costs `73749/10000 + pi/2` and is selected. The test freshly replays the residual certificate, verifies its complete exclusion/generation/proposal binding, and checks every native report obligation. Each complete original and exported-file check covers five main-route source pairs, one second-route source pair, five cross-route pairs, complete self checks and actual fitting counts `[2,0]` within budget two.

Candidate `c6515647427a49289503ce72a04b3814` is accepted at revision 2. Fresh exported IFC verification passes under a different candidate root, `00cb3f38b2da839f9f64d02ba2ff207200ed79a9dbb1eed3f3704b551170b7d6`, while preserving proof references and independently replaying nominal evidence. The original source SHA and raw run mission remain unchanged. The retained original/revised reports contain the complete checks, immutable artifacts and exported IFC bytes.

This is an analytic IFC integration benchmark, not a real Office measurement or whole-building release. Kernel, adapter and native receipts remain separate; their test counts are not added as though disjoint. Historical failed adapter/pipeline receipts are retained alongside corrected receipts. The full frozen original-native regression passes all 1,847 cases in 692.48 seconds, with an independent audit of every test identity, all 106 input hashes and six generated evidence files. The original wrapper's three-file inventory rejection is preserved beside the successful audit. See [retained full regression](../../evidence/release/residual-full-backend-14bff19b88c54779af3d15b1295b5d8b/retention.json). The same exact suite passes in the separate custom-native environment in 681.75 seconds. Standalone package mechanics are being validated; final promotion is held for the separately reproduced older fixed-flow section defect recorded in PROGRESS.md.
