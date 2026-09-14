# Implemented private residual fabrication kernel

`src/oma/optimization/fabrication_alternatives.py` is implemented in this private staging tree, based on immutable production `bac10b7f...`. Production sources and the original corpus remain unchanged. [The design handoff](design.md) explains the source obligations and retained candidate-loss example. This document supersedes its proposed direction-only input encoding: the implemented API takes full seven-coordinate graph-state words, directly compatible with existing frontier paths.

## Interface

```
compile_fabrication_alternatives(
    problem, objective, max_fittings, excluded_words,
    *, max_states=24000, max_work=1000000,
    max_excluded_words=16, max_excluded_steps=8192,
    max_input_bytes=1048576, max_certificate_bytes=16777216,
    checkpoint=None)

verify_fabrication_alternatives(
    problem, objective, max_fittings, excluded_words, certificate,
    *, same independent budgets)
```

`problem` and `objective` retain the existing finite graph and nonnegative nominal length/fitting policy. Inputs must be bounded JSON-compatible values; exact rational quantities use strings. `max_fittings` is a strict integer from zero to 32. `excluded_words` is a list of complete paths, each a list of seven-integer states: the exact six-coordinate fabrication state followed by cumulative turn count. Every word starts at the exact source, follows only independently checked adjacent graph transitions, and ends at an accepting terminal. Empty words, duplicate complete words, prefixes that are not accepting routes, fabricated transitions, wrong counts, booleans and oversized integers are invalid inputs.

For an initial frontier entry, pass its existing `path_states` unchanged. A residual certificate adds a trie ID as its eighth state coordinate; extract a subsequent exclusion as `[state[:7] for state in entry['path_states']]`. The final source and terminal states must remain in the word. Exclusions mark already-generated proposals, not universally infeasible physical routes.

Producer outcomes are CERTIFIED, UNKNOWN without partial count authority, or INVALID_INPUT. Verifier outcomes are PASS, UNKNOWN without proof authority, or FAIL. Invalid work-budget construction or an invalid/noncallable callback can raise immediately, as in the underlying graph budget API. Exceptions deliberately raised by a caller checkpoint preserve their original object and type, including exceptions with the same type as internal budget exhaustion.

## Certificate and independent proof

Schema is `oma.fabrication-residual-frontier/1`, scope `EXACT_COUNT_NOMINAL_OPTIMUM_IN_DECLARED_RESIDUAL_GRAPH_WORD_LANGUAGE`. The certificate includes input, graph, objective, exact-count-domain, exclusion, automaton, residual-model and content roots. It records exact exclusion/step/node counts and the source-derived maximum word length. Canonical exclusions are sorted complete words; input order does not alter the mathematical certificate.

Every product state has eight integers: original seven coordinates and a trie ID. Zero is the empty-prefix state and -1 is permanent divergence from all excluded prefixes. Other nodes correspond to one concrete source prefix. The trie stores each node once as parent, last seven-coordinate symbol, and terminal flag, using linear storage in total excluded steps. Node IDs are deterministic first insertion under lexicographically sorted words. The certificate does not supply trusted trie transitions; both invocations rebuild the trie from independently validated input words. Producer transitions use a keyed map; verifier transitions independently scan matching child symbols. Forbidden terminal IDs are separately reconstructed by replaying each excluded word.

The producer closes the complete reachable product and emits one nonnegative rational potential and an earlier predecessor per row. The verifier independently reconstructs all graph geometry, cost/count transitions, trie changes, predecessor validity, successor closure and potential inequalities. Reaching an excluded terminal disables only that choice to stop. Both ordinary and excluded goal states retain every graph successor, so longer goal-revisiting words remain available. A compact 256-state straight-word test verifies linear trie allocation; complete cube-walk oracles retain repeated vertices and goal revisits.

The frontier contains exactly K+1 entries in count order. Each is `RESIDUAL_OPTIMAL_PATH` with `cost`, eight-coordinate `path_states` and exact string `points_m`, or `NO_PATH_IN_DECLARED_RESIDUAL_LANGUAGE_AT_EXACT_COUNT` with no cost/path. The cost remains a rational pair `[a,b]` representing a+b*pi; b is independently fixed to `length_weight*R*k/2`. Every accepting terminal pays the final straight debt exactly once. The independent realizing path matches the claimed rational lower bound, count, terminal eligibility and contracted points.

PASS returns the same model/content roots, checked count/state/transition denominators and actual verifier work. No all-tie, original-count optimum, sequence rank, native cost bound, physical-infeasibility, physical uniqueness, acceptance, or continuous-universe claim is granted. A later adapter may certify an enumeration rank only by independently binding the entire previous-minimum/exclusion chain. A residual certificate alone establishes only its declared remaining language optimum.

## Bounds and mutation handling

Strict default limits are 16 excluded words and 8,192 total transitions; configurable hard ceilings are 128 words and 65,536 total transitions. The graph remains limited to 1,024 vertices and K<=32. Every word is independently limited by `(K+1)*(max_axis_nodes-1)`: no U-turn is allowed, every direction change adds a count, and each fixed signed-axis run advances monotonically through distinct coordinates.

Graph/count states, encoded certificate bytes, work, individual tokens/integers, nesting, exclusion counts and total transitions are bounded. Inputs are snapshot into their exact bounded canonical JSON bytes before graph arithmetic; the verifier snapshots and byte-checks the certificate before parsing cost Fractions. Each invocation has its own work budget and ignores producer work as arithmetic authority. Partial closure cannot mark any count unreachable. Even a complete proof may return UNKNOWN if its final input validation exceeds the caller's resource budget.

The last public checkpoint occurs before a bounded final guard with callbacks disabled. The guard rehashes current caller input bytes and, for verification, current caller certificate bytes against the original snapshots. A callback cannot modify the input after the last normalization and obtain a mislabeled success. This is same-invocation callback protection, not an atomic guarantee against an independently racing filesystem/process or unsynchronized concurrent memory writer. Source-file and native input applicability remain adapter obligations.

## Validation and evidence

The stable private kernel SHA-256 is `16857629268db3b601340d84c6dd9c563452ecdf9daf0e5bd212d387be2d7910`. The frozen private build is `1d8467cf5bda99a3992f9bc01a33a07fff29f629ea8be2f5336114be8ee47d10`.

- `tests/test_optimization_fabrication_alternatives.py`: 79 PASS in 7.45 seconds; `evidence/kernel-tests.xml`.
- Independent cube/anisotropic walk enumeration checks four complete residual rounds under length-only, fitting-only and mixed rational objectives. All six tied two-turn cube paths are recovered before residual closure; shared prefixes remain available. Tests cover zero-count debt, longer goal revisits, input order, omitted states/counts, forbidden-word/path/trie/cost/root forgeries, altered objectives/context, all resource guards, producer independence, final callback mutation and exception identity.
- Actual residual-to-IFC result: `evidence/native-residual/bb60216bcaa9463f8d9f3223dcb804a0/result.json`, receipt indexed by `evidence/native-residual-latest.json`. An initial exact count-two minimum costs `6+pi/2`; after excluding that complete generated word the independently verified residual minimum costs `8+pi/2`. The new path is converted and freshly materialized as five native components with two actual elbows. It passes all five original-wall pairs, all five separately materialized competing-route pairs, its own self checks, IFC semantics, and exact/native fabrication correspondence. Original fixture source bytes are unchanged. No aggregate joint acceptance is asserted.
- `evidence/analytic-two-detours/result.json` retains the preceding original-behavior counterexample and positive native common-volume failure of the sole cheaper proposal. It remains unchanged.
- `evidence/source-basis.json` pins the read-only original document SHA and exact native paragraphs for RTR15/22/26/27 and supporting graph/checking obligations. No complete original source algorithm is marked implemented.

The root agent separately owns staged adapter integration and its tests. This kernel handoff confers no new authority on the actual routing/acceptance pipeline until that integration is independently tested.
